from __future__ import annotations

import argparse
from datetime import UTC, datetime
from math import comb
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
from src.evaluate import evaluate_triage, select_review_rows
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

    scenarios: list[tuple[str, list[str]]] = [("clean", [])]
    scenarios.extend(FEATURE_OUTAGES.items())
    seed_scenario_results = []
    seed_category_results = []

    for seed_offset in range(args.training_seeds):
        training_seed = args.random_state + seed_offset
        pipeline = build_pipeline(
            "random_forest",
            numeric_features,
            categorical_features,
            training_seed,
        )
        pipeline.fit(X_train, y_train)

        for scenario_index, (scenario_name, outage_columns) in enumerate(scenarios):
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
            comparison, scenario_categories = compare_uncertainty_with_random(
                labels=y_test.to_numpy(),
                probabilities=test_scores,
                attack_categories=test_data["attack_cat"],
                reviewed=reviewed,
                threshold=args.decision_threshold,
                random_repeats=args.random_repeats,
                random_state=training_seed * 100 + scenario_index,
                scenario=scenario_name,
            )
            metrics.update(
                {
                    "scenario": scenario_name,
                    "training_seed": training_seed,
                    "outage_features": outage_columns,
                    "review_budget_target": args.review_budget,
                    "review_uncertainty_cutoff_in_batch": review_cutoff,
                    **comparison,
                }
            )
            seed_scenario_results.append(metrics)
            seed_category_results.extend(
                {**row, "training_seed": training_seed}
                for row in scenario_categories
            )
            print(
                f"seed={training_seed} {scenario_name}: "
                f"reviewed={metrics['reviewed_rows']}, "
                f"uncertainty caught={metrics['uncertainty_errors_caught']}, "
                f"random mean={metrics['random_mean_errors_caught']:.1f}"
            )

    scenario_results = aggregate_seed_results(
        seed_scenario_results, "scenario", args.training_seeds
    )
    category_results = aggregate_seed_results(
        seed_category_results,
        ("scenario", "attack_category"),
        args.training_seeds,
    )
    apply_fdr_adjustment(scenario_results, category_results)

    results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": "UNSW-NB15",
        "protocol": {
            "training_rows": int(len(X_train)),
            "official_test_rows": int(len(X_test)),
            "random_state": args.random_state,
            "training_seeds": [
                args.random_state + offset for offset in range(args.training_seeds)
            ],
            "training_seed_count": args.training_seeds,
            "decision_threshold": args.decision_threshold,
            "review_budget_target": args.review_budget,
            "random_review_repeats": args.random_repeats,
            "seed_level_analysis": (
                "paired uncertainty-minus-random lift across training seeds; "
                "two-sided exact sign test and Benjamini-Hochberg correction "
                "across scenario and category comparisons"
            ),
            "review_policy": (
                "within each evaluation batch, route the requested fraction of "
                "records closest to the decision threshold for review"
            ),
            "random_baseline": (
                "repeat uniform sampling without replacement at the same review count"
            ),
            "review_count_rule": "floor(review_budget * batch_rows)",
            "test_labels_used_to_select_review_rows": False,
            "attack_cat_used_as_model_input": False,
        },
        "feature_outage_scenarios": FEATURE_OUTAGES,
        "scenarios": scenario_results,
        "attack_category_results": category_results,
        "per_seed_scenarios": seed_scenario_results,
        "per_seed_attack_category_results": seed_category_results,
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
        help="Fraction of test-batch flows routed for review by each policy.",
    )
    parser.add_argument(
        "--random-repeats",
        type=int,
        default=200,
        help="Number of random-review batches used for each scenario.",
    )
    parser.add_argument(
        "--training-seeds",
        type=int,
        default=5,
        help="Number of independently seeded model fits to compare.",
    )
    args = parser.parse_args()
    if not 0 < args.review_budget < 1:
        parser.error("--review-budget must be greater than 0 and less than 1")
    if not 0 <= args.decision_threshold <= 1:
        parser.error("--decision-threshold must be between 0 and 1")
    if args.random_repeats < 1:
        parser.error("--random-repeats must be at least 1")
    if not 2 <= args.training_seeds <= 20:
        parser.error("--training-seeds must be between 2 and 20")
    return args


def aggregate_seed_results(
    rows: list[dict[str, Any]],
    group_keys: str | tuple[str, ...],
    seed_count: int,
) -> list[dict[str, Any]]:
    keys = (group_keys,) if isinstance(group_keys, str) else group_keys
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[key] for key in keys), []).append(row)

    aggregates = []
    for group_key, group in grouped.items():
        result = {key: value for key, value in zip(keys, group_key, strict=True)}
        result["training_seed_count"] = seed_count
        for field in group[0]:
            if field in keys or field in {"training_seed", "outage_features"}:
                continue
            values = [row.get(field) for row in group]
            numeric_values = [value for value in values if isinstance(value, int | float)]
            if numeric_values:
                result[field] = float(np.mean(numeric_values))
        if "outage_features" in group[0]:
            result["outage_features"] = group[0]["outage_features"]

        lifts = [
            float(row["errors_caught_lift_vs_random_mean"])
            for row in group
            if row.get("errors_caught_lift_vs_random_mean") is not None
        ]
        result.update(
            {
                "seeds_beating_random": sum(lift > 0 for lift in lifts),
                "median_lift_vs_random": float(np.median(lifts)) if lifts else None,
                "min_seed_lift_vs_random": min(lifts) if lifts else None,
                "max_seed_lift_vs_random": max(lifts) if lifts else None,
                "sign_test_p_value": exact_sign_test(lifts),
                "fdr_q_value": None,
            }
        )
        if "attack_category" in keys:
            mean_errors = result.get("baseline_errors", 0.0)
            result["uncertainty_error_capture_rate"] = (
                result.get("uncertainty_errors_caught", 0.0) / mean_errors
                if mean_errors
                else None
            )
        aggregates.append(result)
    return aggregates


def exact_sign_test(differences: list[float]) -> float | None:
    nonzero = [difference for difference in differences if difference != 0]
    if not nonzero:
        return None
    positive = sum(difference > 0 for difference in nonzero)
    count = len(nonzero)
    tail = min(positive, count - positive)
    probability = sum(comb(count, index) for index in range(tail + 1)) / (2**count)
    return min(1.0, float(2 * probability))


def apply_fdr_adjustment(
    scenario_results: list[dict[str, Any]],
    category_results: list[dict[str, Any]],
) -> None:
    comparisons = [
        row
        for row in [*scenario_results, *category_results]
        if row.get("sign_test_p_value") is not None
    ]
    comparisons.sort(key=lambda row: row["sign_test_p_value"])
    total = len(comparisons)
    adjusted_values = [0.0] * total
    running_minimum = 1.0
    for index in range(total - 1, -1, -1):
        candidate = comparisons[index]["sign_test_p_value"] * total / (index + 1)
        running_minimum = min(running_minimum, candidate)
        adjusted_values[index] = min(1.0, running_minimum)
    for row, q_value in zip(comparisons, adjusted_values, strict=True):
        row["fdr_q_value"] = q_value


def compare_uncertainty_with_random(
    labels: np.ndarray,
    probabilities: np.ndarray,
    attack_categories: pd.Series,
    reviewed: np.ndarray,
    threshold: float,
    random_repeats: int,
    random_state: int,
    scenario: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    predictions = (probabilities >= threshold).astype(int)
    errors = predictions != labels
    category_values = attack_categories.fillna("Unknown").astype(str).to_numpy()
    category_names = sorted(set(category_values))
    review_count = int(reviewed.sum())
    uncertainty_errors_caught = int((errors & reviewed).sum())

    random_error_counts = np.zeros(random_repeats, dtype=int)
    random_category_errors = {
        name: np.zeros(random_repeats, dtype=int) for name in category_names
    }
    random_category_reviews = {
        name: np.zeros(random_repeats, dtype=int) for name in category_names
    }
    rng = np.random.default_rng(random_state)

    for repeat in range(random_repeats):
        selected_indices = rng.choice(len(labels), size=review_count, replace=False)
        selected_errors = errors[selected_indices]
        random_error_counts[repeat] = int(selected_errors.sum())
        selected_categories = category_values[selected_indices]
        for name in category_names:
            category_mask = selected_categories == name
            random_category_reviews[name][repeat] = int(category_mask.sum())
            random_category_errors[name][repeat] = int(
                (selected_errors & category_mask).sum()
            )

    total_errors = int(errors.sum())
    randomization_p_value = float(
        (np.count_nonzero(random_error_counts >= uncertainty_errors_caught) + 1)
        / (random_repeats + 1)
    )
    random_mean = float(random_error_counts.mean())
    comparison = {
        "uncertainty_errors_caught": uncertainty_errors_caught,
        "uncertainty_error_capture_rate": (
            uncertainty_errors_caught / total_errors if total_errors else 0.0
        ),
        "random_mean_errors_caught": random_mean,
        "random_std_errors_caught": float(random_error_counts.std(ddof=1))
        if random_repeats > 1
        else 0.0,
        "random_95th_percentile_errors_caught": float(
            np.percentile(random_error_counts, 95)
        ),
        "errors_caught_lift_vs_random_mean": uncertainty_errors_caught - random_mean,
        "error_capture_rate_lift_vs_random_mean": (
            uncertainty_errors_caught / total_errors - random_mean / total_errors
            if total_errors
            else 0.0
        ),
        "randomization_p_value": randomization_p_value,
        "random_review_repeats": random_repeats,
        "total_baseline_errors": total_errors,
    }

    category_results = []
    for name in category_names:
        category_mask = category_values == name
        category_errors = errors & category_mask
        error_count = int(category_errors.sum())
        uncertainty_reviewed = int((reviewed & category_mask).sum())
        uncertainty_caught = int((reviewed & category_errors).sum())
        random_counts = random_category_errors[name]
        category_results.append(
            {
                "scenario": scenario,
                "attack_category": name,
                "rows": int(category_mask.sum()),
                "baseline_errors": error_count,
                "uncertainty_reviewed_rows": uncertainty_reviewed,
                "uncertainty_review_rate": float(
                    uncertainty_reviewed / category_mask.sum()
                ),
                "uncertainty_errors_caught": uncertainty_caught,
                "uncertainty_error_capture_rate": (
                    uncertainty_caught / error_count if error_count else None
                ),
                "random_mean_reviewed_rows": float(
                    random_category_reviews[name].mean()
                ),
                "random_mean_errors_caught": float(random_counts.mean()),
                "random_95th_percentile_errors_caught": float(
                    np.percentile(random_counts, 95)
                ),
                "errors_caught_lift_vs_random_mean": uncertainty_caught
                - float(random_counts.mean()),
                "randomization_p_value": float(
                    (
                        np.count_nonzero(random_counts >= uncertainty_caught) + 1
                    )
                    / (random_repeats + 1)
                )
                if error_count
                else None,
            }
        )

    return comparison, category_results


if __name__ == "__main__":
    main()
