from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data_loader import (
    feature_groups,
    load_testing_data,
    load_training_data,
    project_root,
    split_features_target,
)
from src.evaluate import evaluate_attack_categories, evaluate_triage, select_review_rows
from src.train import build_pipeline
from src.utils import ensure_dir, write_json

FEATURE_OUTAGES = {
    "protocol_context": ["proto", "service", "state"],
    "packet_counts": ["spkts", "dpkts"],
    "byte_volume": ["sbytes", "dbytes", "sload", "dload", "smean", "dmean"],
    "timing": ["dur", "rate", "sinpkt", "dinpkt", "sjit", "djit"],
    "ttl_state": ["sttl", "dttl", "ct_state_ttl"],
    "tcp": ["swin", "stcpb", "dtcpb", "dwin", "tcprtt", "synack", "ackdat"],
    "connection_counts": [
        "ct_srv_src",
        "ct_dst_ltm",
        "ct_src_dport_ltm",
        "ct_dst_sport_ltm",
        "ct_dst_src_ltm",
        "ct_src_ltm",
        "ct_srv_dst",
    ],
    "application": [
        "trans_depth",
        "response_body_len",
        "is_ftp_login",
        "ct_ftp_cmd",
        "ct_flw_http_mthd",
        "is_sm_ips_ports",
    ],
    "packet_loss": ["sloss", "dloss"],
}


def main() -> None:
    args = parse_args()
    train_data = load_training_data(args.dataset_dir)
    test_data = load_testing_data(args.dataset_dir)

    X_train, y_train = split_features_target(train_data)
    X_test, y_test = split_features_target(test_data)
    numeric_features, categorical_features = feature_groups(train_data)

    pipeline = build_pipeline(
        "random_forest",
        numeric_features,
        categorical_features,
        args.random_state,
    )
    pipeline.fit(X_train, y_train)

    scenarios: list[tuple[str, list[str]]] = [("clean", [])]
    scenarios.extend(FEATURE_OUTAGES.items())
    scenario_results = []
    category_results = []

    for scenario_name, outage_columns in scenarios:
        test_features = degrade_features(X_test, outage_columns)

        test_scores = pipeline.predict_proba(test_features)[:, 1]
        reviewed, review_cutoff = select_review_rows(
            test_scores,
            args.decision_threshold,
            args.review_budget,
        )
        metrics = evaluate_triage(
            y_test.to_numpy(),
            test_scores,
            threshold=args.decision_threshold,
            reviewed=reviewed,
        )
        metrics.update(
            {
                "scenario": scenario_name,
                "outage_features": outage_columns,
                "review_budget_target": args.review_budget,
                "review_uncertainty_cutoff_in_batch": review_cutoff,
            }
        )
        scenario_results.append(metrics)

        if "attack_cat" in test_data.columns:
            category_results.extend(
                evaluate_attack_categories(
                    test_data["attack_cat"],
                    y_test.to_numpy(),
                    test_scores,
                    reviewed,
                    args.decision_threshold,
                    scenario_name,
                )
            )

        print(
            f"{scenario_name}: review={metrics['review_rate']:.3f}, "
            f"automatic accuracy={metrics['automatic_accuracy']:.3f}, "
            f"baseline errors caught={metrics['baseline_error_capture_rate']:.3f}"
        )

    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": "UNSW-NB15",
        "protocol": {
            "training_rows": int(len(X_train)),
            "official_test_rows": int(len(X_test)),
            "random_state": args.random_state,
            "decision_threshold": args.decision_threshold,
            "review_budget_target": args.review_budget,
            "review_policy": (
                "within each evaluation batch, route the requested fraction of "
                "records closest to the decision threshold for review"
            ),
            "review_count_rule": "floor(review_budget * batch_rows)",
            "test_labels_used_to_select_review_rows": False,
            "attack_cat_used_as_model_input": False,
        },
        "feature_outage_scenarios": FEATURE_OUTAGES,
        "scenarios": scenario_results,
        "attack_category_results": category_results,
    }

    output_path = args.output
    ensure_dir(output_path.parent)
    write_json(output_path, results)
    csv_path = output_path.with_suffix(".csv")
    pd.DataFrame(scenario_results).drop(columns="outage_features").to_csv(
        csv_path, index=False
    )
    if category_results:
        pd.DataFrame(category_results).to_csv(
            output_path.with_name(f"{output_path.stem}_by_attack_category.csv"),
            index=False,
        )
    print(f"Results written to {output_path}")
    print(f"Scenario summary written to {csv_path}")


def degrade_features(data: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    degraded = data.copy()
    available_columns = [column for column in columns if column in degraded.columns]
    for column in available_columns:
        degraded[column] = np.nan
    return degraded


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Random Forest alert triage under network-flow feature outages."
        )
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="Directory containing the official UNSW-NB15 train and test CSVs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "reports" / "feature_robustness_results.json",
        help="Path for the JSON experiment report.",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--decision-threshold",
        type=float,
        default=0.55,
        help="Binary decision threshold used for automatic predictions.",
    )
    parser.add_argument(
        "--review-budget",
        type=float,
        default=0.1,
        help="Target fraction of validation flows routed for review.",
    )
    args = parser.parse_args()
    if not 0 < args.review_budget < 1:
        parser.error("--review-budget must be greater than 0 and less than 1")
    if not 0 <= args.decision_threshold <= 1:
        parser.error("--decision-threshold must be between 0 and 1")
    return args


if __name__ == "__main__":
    main()
