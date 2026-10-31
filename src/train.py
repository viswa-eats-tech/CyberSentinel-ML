from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.data_loader import (
    feature_groups,
    load_testing_data,
    load_training_data,
    project_root,
    split_features_target,
)
from src.evaluate import evaluate_classifier, metrics_to_markdown
from src.preprocessor import build_model_pipeline
from src.utils import ensure_dir, write_json, write_text

MODEL_BUILDERS = {
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
}


def main() -> None:
    args = parse_args()
    random_state = args.random_state

    train_data = load_training_data(args.dataset_dir)
    test_data = load_testing_data(args.dataset_dir)

    if args.sample_size:
        train_data = stratified_sample(train_data, args.sample_size, random_state)
        test_data = stratified_sample(
            test_data, min(args.sample_size, len(test_data)), random_state
        )

    X_train, y_train = split_features_target(train_data)
    X_test, y_test = split_features_target(test_data)
    numeric_features, categorical_features = feature_groups(train_data)

    selected_models = (
        ["logistic_regression", "random_forest"]
        if args.model == "both"
        else [args.model]
    )

    output_dir = ensure_dir(args.output_dir)
    reports_dir = ensure_dir(args.reports_dir)

    run_results: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "train_rows": int(len(train_data)),
        "test_rows": int(len(test_data)),
        "target": "label",
        "decision_threshold": None,
        "model_thresholds": {},
        "threshold_selection": {},
        "excluded_columns": ["id", "attack_cat"],
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "models": {},
    }

    model_markdown_sections = []

    for model_name in selected_models:
        print(f"Training {MODEL_BUILDERS[model_name]}...")
        model_threshold = args.threshold
        threshold_selection = None

        if model_name == "random_forest" and args.auto_threshold:
            model_threshold, threshold_selection = select_threshold_on_validation(
                model_name=model_name,
                X_train=X_train,
                y_train=y_train,
                numeric_features=numeric_features,
                categorical_features=categorical_features,
                random_state=random_state,
                validation_size=args.validation_size,
                thresholds=args.thresholds,
                min_recall=args.min_recall,
            )
            run_results["threshold_selection"][model_name] = threshold_selection
            print(
                "Selected Random Forest threshold "
                f"{model_threshold:.2f} on validation split."
            )

        pipeline = build_pipeline(
            model_name, numeric_features, categorical_features, random_state
        )
        pipeline.fit(X_train, y_train)

        metrics = evaluate_classifier(
            pipeline, X_test, y_test, threshold=model_threshold
        )
        if threshold_selection is not None:
            metrics["threshold_selection"] = threshold_selection

        run_results["model_thresholds"][model_name] = model_threshold
        run_results["models"][model_name] = metrics
        model_markdown_sections.append(
            metrics_to_markdown(MODEL_BUILDERS[model_name], metrics)
        )

        if not args.no_save:
            model_path = output_dir / f"{model_name}_model.pkl"
            joblib.dump(pipeline, model_path)
            run_results["models"][model_name]["model_path"] = portable_path(model_path)

            if model_name == "random_forest":
                joblib.dump(pipeline, output_dir / "model.pkl")

    primary_model_name = (
        "random_forest" if "random_forest" in selected_models else selected_models[0]
    )
    run_results["decision_threshold"] = run_results["model_thresholds"][
        primary_model_name
    ]
    markdown_sections = render_training_markdown(run_results, model_markdown_sections)

    if not args.no_save:
        metadata = build_metadata(run_results, primary_model_name)
        write_json(output_dir / "metadata.json", metadata)

    write_json(reports_dir / "training_results.json", run_results)
    write_text(reports_dir / "training_results.md", "\n".join(markdown_sections))

    print(f"Metrics written to {reports_dir / 'training_results.md'}")
    if args.no_save:
        print("Model saving skipped because --no-save was used.")
    else:
        print(f"Models written to {output_dir}")


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(description="Train UNSW-NB15 binary classifiers.")
    parser.add_argument(
        "--model",
        choices=["logistic_regression", "random_forest", "both"],
        default="both",
        help="Model to train. Default: both.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=None,
        help="Directory containing UNSW_NB15_training-set.csv and UNSW_NB15_testing-set.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "models",
        help="Directory where trained models are saved.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=root / "reports",
        help="Directory where metric reports are saved.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Optional stratified row sample for quick smoke tests.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip model serialization. Useful with --sample-size.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for reproducible training.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Decision threshold applied to attack probabilities during evaluation.",
    )
    parser.add_argument(
        "--auto-threshold",
        action="store_true",
        help=(
            "Select the Random Forest threshold on a validation split from the training set. "
            "The final test set is still used only for reporting."
        ),
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.98,
        help="Minimum validation attack recall used by --auto-threshold.",
    )
    parser.add_argument(
        "--validation-size",
        type=float,
        default=0.2,
        help="Training-set fraction used as validation data by --auto-threshold.",
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="*",
        default=[round(value / 100, 2) for value in range(5, 96, 5)],
        help="Candidate threshold values evaluated by --auto-threshold.",
    )
    return parser.parse_args()


def select_threshold_on_validation(
    model_name: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
    random_state: int,
    validation_size: float,
    thresholds: list[float],
    min_recall: float,
) -> tuple[float, dict[str, Any]]:
    if not 0 < validation_size < 1:
        raise ValueError("--validation-size must be between 0 and 1.")

    candidate_thresholds = sorted({float(threshold) for threshold in thresholds})
    if not candidate_thresholds:
        raise ValueError("--thresholds must contain at least one value.")

    X_fit, X_validation, y_fit, y_validation = train_test_split(
        X_train,
        y_train,
        test_size=validation_size,
        random_state=random_state,
        stratify=y_train,
    )

    validation_pipeline = build_pipeline(
        model_name,
        numeric_features,
        categorical_features,
        random_state,
    )
    validation_pipeline.fit(X_fit, y_fit)

    threshold_rows = []
    for threshold in candidate_thresholds:
        metrics = evaluate_classifier(
            validation_pipeline,
            X_validation,
            y_validation,
            threshold=threshold,
        )
        matrix = metrics["confusion_matrix"]
        threshold_rows.append(
            {
                "threshold": float(threshold),
                "accuracy": metrics["accuracy"],
                "precision_attack": metrics["precision_attack"],
                "recall_attack": metrics["recall_attack"],
                "f1_attack": metrics["f1_attack"],
                "roc_auc": metrics["roc_auc"],
                "true_negative": matrix["true_negative"],
                "false_positive": matrix["false_positive"],
                "false_negative": matrix["false_negative"],
                "true_positive": matrix["true_positive"],
            }
        )

    constrained_candidates = [
        row for row in threshold_rows if row["recall_attack"] >= min_recall
    ]
    if constrained_candidates:
        selected_row = max(
            constrained_candidates,
            key=lambda row: (row["f1_attack"], row["precision_attack"]),
        )
        selection_rule = (
            "highest validation F1 among thresholds with "
            f"attack recall >= {min_recall:.2f}"
        )
    else:
        selected_row = max(
            threshold_rows,
            key=lambda row: (row["recall_attack"], row["f1_attack"]),
        )
        selection_rule = (
            "highest validation recall because no threshold reached "
            f"attack recall >= {min_recall:.2f}"
        )

    return float(selected_row["threshold"]), {
        "method": "training_validation_split",
        "selection_rule": selection_rule,
        "min_recall": min_recall,
        "validation_size": validation_size,
        "fit_rows": int(len(X_fit)),
        "validation_rows": int(len(X_validation)),
        "candidate_count": len(threshold_rows),
        "selected_threshold": float(selected_row["threshold"]),
        "selected_metrics": selected_row,
    }


def build_pipeline(
    model_name: str,
    numeric_features: list[str],
    categorical_features: list[str],
    random_state: int,
):
    if model_name == "logistic_regression":
        model = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
            solver="lbfgs",
        )
        return build_model_pipeline(
            model=model,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            scale_numeric=True,
        )

    if model_name == "random_forest":
        model = RandomForestClassifier(
            class_weight="balanced_subsample",
            n_estimators=120,
            n_jobs=-1,
            random_state=random_state,
        )
        return build_model_pipeline(
            model=model,
            numeric_features=numeric_features,
            categorical_features=categorical_features,
            scale_numeric=False,
        )

    raise ValueError(f"Unsupported model: {model_name}")


def build_metadata(
    run_results: dict[str, Any], primary_model_name: str
) -> dict[str, Any]:
    primary_metrics = run_results["models"][primary_model_name]
    return {
        "project": "Network Intrusion Detection System",
        "dataset": "UNSW-NB15",
        "task": "binary_classification",
        "target": run_results["target"],
        "decision_threshold": run_results["decision_threshold"],
        "positive_class": {"label": 1, "meaning": "attack"},
        "negative_class": {"label": 0, "meaning": "normal"},
        "primary_model": primary_model_name,
        "primary_model_display_name": MODEL_BUILDERS[primary_model_name],
        "primary_model_path": primary_metrics.get("model_path", "models/model.pkl"),
        "generated_at": run_results["generated_at"],
        "train_rows": run_results["train_rows"],
        "test_rows": run_results["test_rows"],
        "model_thresholds": run_results["model_thresholds"],
        "threshold_selection": run_results["threshold_selection"],
        "excluded_columns": run_results["excluded_columns"],
        "numeric_features": run_results["numeric_features"],
        "categorical_features": run_results["categorical_features"],
        "metrics": {
            "accuracy": primary_metrics["accuracy"],
            "precision_attack": primary_metrics["precision_attack"],
            "recall_attack": primary_metrics["recall_attack"],
            "f1_attack": primary_metrics["f1_attack"],
            "roc_auc": primary_metrics["roc_auc"],
            "confusion_matrix": primary_metrics["confusion_matrix"],
        },
        "library_versions": {
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }


def portable_path(path: Path) -> str:
    root = project_root()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def render_training_markdown(
    run_results: dict[str, Any],
    model_markdown_sections: list[str],
) -> list[str]:
    threshold_summary = ", ".join(
        f"{MODEL_BUILDERS[model_name]}={threshold:.2f}"
        for model_name, threshold in run_results["model_thresholds"].items()
    )
    lines = [
        "# Training Results",
        "",
        f"Generated at: `{run_results['generated_at']}`",
        "",
        "## Dataset",
        "",
        f"- Training rows: `{run_results['train_rows']}`",
        f"- Testing rows: `{run_results['test_rows']}`",
        "- Target: `label`",
        f"- Primary decision threshold: `{run_results['decision_threshold']:.2f}`",
        f"- Model thresholds: `{threshold_summary}`",
        "- Excluded columns: `id`, `attack_cat`",
        f"- Numeric features: `{len(run_results['numeric_features'])}`",
        f"- Categorical features: `{', '.join(run_results['categorical_features'])}`",
        "",
    ]

    if run_results["threshold_selection"]:
        lines.extend(
            [
                "## Threshold Selection",
                "",
                "| Model | Method | Selected threshold | Validation recall attack | Validation F1 attack |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for model_name, selection in run_results["threshold_selection"].items():
            selected = selection["selected_metrics"]
            lines.append(
                f"| {MODEL_BUILDERS[model_name]} | {selection['method']} | "
                f"{selection['selected_threshold']:.2f} | "
                f"{selected['recall_attack']:.4f} | {selected['f1_attack']:.4f} |"
            )
        lines.extend(
            [
                "",
                (
                    "The threshold is selected from a validation split of the training set. "
                    "The official testing set is used only for final reporting."
                ),
                "",
            ]
        )

    lines.extend(model_markdown_sections)
    return lines


def stratified_sample(
    data: pd.DataFrame, sample_size: int, random_state: int
) -> pd.DataFrame:
    if sample_size >= len(data):
        return data

    label_counts = data["label"].value_counts()
    sample_counts = (label_counts / len(data) * sample_size).round().astype(int)

    count_delta = sample_size - int(sample_counts.sum())
    if count_delta:
        largest_class = sample_counts.idxmax()
        sample_counts.loc[largest_class] += count_delta

    sampled_parts = []
    for label, count in sample_counts.items():
        group = data[data["label"] == label]
        sampled_parts.append(
            group.sample(n=min(int(count), len(group)), random_state=random_state)
        )

    sampled = pd.concat(sampled_parts, axis=0).sample(frac=1, random_state=random_state)
    return sampled.reset_index(drop=True)


if __name__ == "__main__":
    main()
