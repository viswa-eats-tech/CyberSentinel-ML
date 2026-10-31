from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from src.data_loader import load_testing_data, project_root, split_features_target
from src.utils import ensure_dir, write_json, write_text

DEFAULT_THRESHOLDS = [round(value, 2) for value in np.arange(0.05, 0.96, 0.05)]


def main() -> None:
    args = parse_args()
    reports_dir = ensure_dir(args.reports_dir)

    pipeline = joblib.load(args.model_path)
    metadata = load_metadata(args.metadata_path)
    operational_threshold = float(metadata.get("decision_threshold", 0.5))
    test_data = load_testing_data(args.dataset_dir)
    X_test, y_test = split_features_target(test_data)

    probabilities = pipeline.predict_proba(X_test)[:, 1]
    threshold_rows = threshold_analysis(y_test, probabilities, args.thresholds)
    default_row = row_for_threshold(threshold_rows, operational_threshold)
    max_f1_row = max(threshold_rows, key=lambda row: row["f1_attack"])
    high_recall_row = choose_high_recall_threshold(
        threshold_rows, min_recall=args.min_recall
    )

    feature_importance = transformed_feature_importance(pipeline)
    grouped_importance = grouped_feature_importance(feature_importance)
    error_summary = prediction_error_summary(
        y_test,
        probabilities,
        threshold=operational_threshold,
    )

    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model_path": portable_path(args.model_path),
        "test_rows": int(len(test_data)),
        "operational_threshold": operational_threshold,
        "threshold_selection": metadata.get("threshold_selection", {}),
        "default_threshold": default_row,
        "best_f1_threshold": max_f1_row,
        "test_high_recall_threshold": high_recall_row,
        "min_recall_constraint": args.min_recall,
        "error_summary_at_operational_threshold": error_summary,
        "top_transformed_features": feature_importance.head(args.top_n).to_dict(
            orient="records"
        ),
        "top_grouped_features": grouped_importance.head(args.top_n).to_dict(
            orient="records"
        ),
        "threshold_analysis": threshold_rows,
    }

    feature_importance.to_csv(
        reports_dir / "random_forest_feature_importance.csv", index=False
    )
    grouped_importance.to_csv(
        reports_dir / "random_forest_grouped_feature_importance.csv", index=False
    )
    pd.DataFrame(threshold_rows).to_csv(
        reports_dir / "random_forest_threshold_analysis.csv",
        index=False,
    )
    write_json(reports_dir / "random_forest_analysis.json", result)
    write_text(
        reports_dir / "random_forest_analysis.md",
        render_markdown(result, args.top_n),
    )

    print(
        f"Random Forest analysis written to {reports_dir / 'random_forest_analysis.md'}"
    )


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="Analyze the trained Random Forest model."
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=root / "models" / "model.pkl",
        help="Path to the trained Random Forest pipeline.",
    )
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=root / "models" / "metadata.json",
        help="Path to model metadata.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="Directory containing UNSW_NB15_testing-set.csv.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=root / "reports",
        help="Directory where analysis reports are saved.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of feature importance rows to include in the Markdown report.",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.98,
        help="Minimum attack recall used when selecting a recommended threshold.",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="*",
        default=DEFAULT_THRESHOLDS,
        help="Threshold values to evaluate.",
    )
    return parser.parse_args()


def load_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))


def portable_path(path: Path) -> str:
    root = project_root()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def threshold_analysis(
    y_true: pd.Series,
    probabilities: np.ndarray,
    thresholds: list[float],
) -> list[dict[str, Any]]:
    rows = []
    for threshold in thresholds:
        y_pred = (probabilities >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        rows.append(
            {
                "threshold": float(threshold),
                "accuracy": float(accuracy_score(y_true, y_pred)),
                "precision_attack": float(
                    precision_score(y_true, y_pred, pos_label=1, zero_division=0)
                ),
                "recall_attack": float(
                    recall_score(y_true, y_pred, pos_label=1, zero_division=0)
                ),
                "f1_attack": float(
                    f1_score(y_true, y_pred, pos_label=1, zero_division=0)
                ),
                "true_negative": int(tn),
                "false_positive": int(fp),
                "false_negative": int(fn),
                "true_positive": int(tp),
            }
        )
    return rows


def row_for_threshold(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    return min(rows, key=lambda row: abs(row["threshold"] - threshold))


def choose_high_recall_threshold(
    rows: list[dict[str, Any]],
    min_recall: float,
) -> dict[str, Any]:
    candidates = [row for row in rows if row["recall_attack"] >= min_recall]
    if not candidates:
        return max(rows, key=lambda row: row["recall_attack"])

    return max(candidates, key=lambda row: (row["f1_attack"], row["precision_attack"]))


def transformed_feature_importance(pipeline) -> pd.DataFrame:
    preprocessor = pipeline.named_steps["preprocessor"]
    model = pipeline.named_steps["model"]
    feature_names = preprocessor.get_feature_names_out()

    importance = pd.DataFrame(
        {
            "feature": [clean_feature_name(name) for name in feature_names],
            "raw_feature": feature_names,
            "importance": model.feature_importances_,
        }
    )
    return importance.sort_values("importance", ascending=False).reset_index(drop=True)


def grouped_feature_importance(feature_importance: pd.DataFrame) -> pd.DataFrame:
    grouped = feature_importance.copy()
    grouped["feature_group"] = grouped["raw_feature"].map(feature_group_name)
    result = (
        grouped.groupby("feature_group", as_index=False)["importance"]
        .sum()
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    result["importance_pct"] = result["importance"] / result["importance"].sum() * 100
    return result


def prediction_error_summary(
    y_true: pd.Series,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    y_pred = (probabilities >= threshold).astype(int)
    false_positive_scores = probabilities[(y_true.to_numpy() == 0) & (y_pred == 1)]
    false_negative_scores = probabilities[(y_true.to_numpy() == 1) & (y_pred == 0)]

    return {
        "threshold": threshold,
        "false_positive_count": int(len(false_positive_scores)),
        "false_negative_count": int(len(false_negative_scores)),
        "false_positive_probability_mean": optional_mean(false_positive_scores),
        "false_negative_probability_mean": optional_mean(false_negative_scores),
        "false_positive_probability_p90": optional_quantile(false_positive_scores, 0.9),
        "false_negative_probability_p90": optional_quantile(false_negative_scores, 0.9),
    }


def clean_feature_name(name: str) -> str:
    return name.replace("numeric__", "").replace("categorical__", "")


def feature_group_name(raw_name: str) -> str:
    name = clean_feature_name(raw_name)
    for categorical in ("proto", "service", "state"):
        if name == categorical or name.startswith(f"{categorical}_"):
            return categorical
    return name


def optional_mean(values: np.ndarray) -> float | None:
    if len(values) == 0:
        return None
    return float(values.mean())


def optional_quantile(values: np.ndarray, quantile: float) -> float | None:
    if len(values) == 0:
        return None
    return float(np.quantile(values, quantile))


def render_markdown(result: dict[str, Any], top_n: int) -> str:
    default_row = result["default_threshold"]
    high_recall_row = result["test_high_recall_threshold"]
    best_f1_row = result["best_f1_threshold"]
    error_summary = result["error_summary_at_operational_threshold"]
    threshold_selection = result.get("threshold_selection", {})
    random_forest_selection = threshold_selection.get("random_forest", {})

    lines = [
        "# Random Forest Analysis",
        "",
        f"Generated at: `{result['generated_at']}`",
        "",
        "## Operational Threshold",
        "",
        f"- Current operational threshold: `{result['operational_threshold']:.2f}`",
    ]

    if random_forest_selection:
        selected_metrics = random_forest_selection["selected_metrics"]
        lines.extend(
            [
                f"- Selection method: `{random_forest_selection['method']}`",
                f"- Selection rule: {random_forest_selection['selection_rule']}",
                (
                    "- Validation result at selected threshold: "
                    f"recall attack `{selected_metrics['recall_attack']:.4f}`, "
                    f"F1 attack `{selected_metrics['f1_attack']:.4f}`"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## Threshold Summary",
            "",
            (
                "The operational threshold comes from training metadata. "
                "The test-set alternatives below are diagnostic, not the rule used to choose deployment behavior."
            ),
            "",
            "| Selection | Threshold | Precision attack | Recall attack | F1 attack | False positives | False negatives |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            threshold_row_markdown("Current operational", default_row),
            threshold_row_markdown("Test-set best F1", best_f1_row),
            threshold_row_markdown(
                f"Test-set recall >= {result['min_recall_constraint']:.2f}",
                high_recall_row,
            ),
            "",
            f"## Error Profile At Operational Threshold {result['operational_threshold']:.2f}",
            "",
            "| Error type | Count | Mean attack probability | P90 attack probability |",
            "| --- | ---: | ---: | ---: |",
            (
                "| False positives | "
                f"{error_summary['false_positive_count']} | "
                f"{format_optional(error_summary['false_positive_probability_mean'])} | "
                f"{format_optional(error_summary['false_positive_probability_p90'])} |"
            ),
            (
                "| False negatives | "
                f"{error_summary['false_negative_count']} | "
                f"{format_optional(error_summary['false_negative_probability_mean'])} | "
                f"{format_optional(error_summary['false_negative_probability_p90'])} |"
            ),
            "",
            "## Top Grouped Features",
            "",
            "| Rank | Feature group | Importance | Share |",
            "| ---: | --- | ---: | ---: |",
        ]
    )

    for index, row in enumerate(result["top_grouped_features"][:top_n], start=1):
        lines.append(
            f"| {index} | `{row['feature_group']}` | "
            f"{row['importance']:.6f} | {row['importance_pct']:.2f}% |"
        )

    lines.extend(
        [
            "",
            "## Top Transformed Features",
            "",
            "| Rank | Feature | Importance |",
            "| ---: | --- | ---: |",
        ]
    )

    for index, row in enumerate(result["top_transformed_features"][:top_n], start=1):
        lines.append(f"| {index} | `{row['feature']}` | {row['importance']:.6f} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Threshold tuning controls the trade-off between missed attacks and false alarms.",
            "- The operational threshold is stored in `models/metadata.json` and used by the API.",
            "- Grouped importance combines one-hot encoded categorical levels back into their original feature names.",
            "- Test-set threshold alternatives are diagnostic; deployment thresholds should be chosen from operating requirements and validated separately.",
            "",
        ]
    )
    return "\n".join(lines)


def threshold_row_markdown(label: str, row: dict[str, Any]) -> str:
    return (
        f"| {label} | {row['threshold']:.2f} | "
        f"{row['precision_attack']:.4f} | {row['recall_attack']:.4f} | "
        f"{row['f1_attack']:.4f} | {row['false_positive']} | {row['false_negative']} |"
    )


def format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


if __name__ == "__main__":
    main()
