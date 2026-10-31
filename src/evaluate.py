from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate_classifier(
    model,
    X: pd.DataFrame,
    y: pd.Series,
    threshold: float = 0.5,
) -> dict[str, Any]:
    y_score = _positive_class_score(model, X)
    if y_score is not None:
        y_pred = (y_score >= threshold).astype(int)
    else:
        y_pred = model.predict(X)

    metrics: dict[str, Any] = {
        "threshold": threshold,
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision_attack": float(
            precision_score(y, y_pred, pos_label=1, zero_division=0)
        ),
        "recall_attack": float(recall_score(y, y_pred, pos_label=1, zero_division=0)),
        "f1_attack": float(f1_score(y, y_pred, pos_label=1, zero_division=0)),
        "classification_report": classification_report(
            y,
            y_pred,
            labels=[0, 1],
            target_names=["normal", "attack"],
            output_dict=True,
            zero_division=0,
        ),
    }

    if y_score is not None:
        metrics["roc_auc"] = float(roc_auc_score(y, y_score))
    else:
        metrics["roc_auc"] = None

    tn, fp, fn, tp = confusion_matrix(y, y_pred, labels=[0, 1]).ravel()
    metrics["confusion_matrix"] = {
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }
    return metrics


def metrics_to_markdown(model_name: str, metrics: dict[str, Any]) -> str:
    matrix = metrics["confusion_matrix"]
    lines = [
        f"## {model_name}",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Threshold | {_format_metric(metrics['threshold'])} |",
        f"| Accuracy | {_format_metric(metrics['accuracy'])} |",
        f"| Precision attack | {_format_metric(metrics['precision_attack'])} |",
        f"| Recall attack | {_format_metric(metrics['recall_attack'])} |",
        f"| F1 attack | {_format_metric(metrics['f1_attack'])} |",
        f"| ROC-AUC | {_format_metric(metrics['roc_auc'])} |",
        "",
        "| Confusion Matrix | Value |",
        "| --- | ---: |",
        f"| True negative | {matrix['true_negative']} |",
        f"| False positive | {matrix['false_positive']} |",
        f"| False negative | {matrix['false_negative']} |",
        f"| True positive | {matrix['true_positive']} |",
        "",
    ]
    return "\n".join(lines)


def _positive_class_score(model, X: pd.DataFrame):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]

    if hasattr(model, "decision_function"):
        return model.decision_function(X)

    return None


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def select_review_rows(
    probabilities: np.ndarray,
    decision_threshold: float,
    review_budget: float,
) -> tuple[np.ndarray, float | None]:
    if not 0 < review_budget < 1:
        raise ValueError("review_budget must be greater than 0 and less than 1.")
    uncertainty = np.abs(probabilities - decision_threshold)
    review_count = int(np.floor(review_budget * len(probabilities)))
    reviewed = np.zeros(len(probabilities), dtype=bool)
    if review_count == 0:
        return reviewed, None

    # Stable row order breaks ties reproducibly while keeping the budget exact.
    review_indices = np.lexsort((np.arange(len(uncertainty)), uncertainty))[:review_count]
    reviewed[review_indices] = True
    return reviewed, float(uncertainty[review_indices[-1]])


def evaluate_triage(
    labels: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    reviewed: np.ndarray,
) -> dict[str, float | int]:
    baseline_predictions = (probabilities >= threshold).astype(int)
    automatic = ~reviewed
    baseline_errors = baseline_predictions != labels
    error_count = int(baseline_errors.sum())
    reviewed_error_count = int((baseline_errors & reviewed).sum())
    automatic_count = int(automatic.sum())

    if automatic_count:
        automatic_accuracy = float(
            (baseline_predictions[automatic] == labels[automatic]).mean()
        )
    else:
        automatic_accuracy = 0.0

    total_attacks = int((labels == 1).sum())
    auto_detected_attacks = int(
        ((labels == 1) & (baseline_predictions == 1) & automatic).sum()
    )
    return {
        "rows": int(len(labels)),
        "reviewed_rows": int(reviewed.sum()),
        "review_rate": float(reviewed.mean()),
        "automatic_coverage": float(automatic.mean()),
        "automatic_accuracy": automatic_accuracy,
        "baseline_accuracy": float((baseline_predictions == labels).mean()),
        "baseline_errors": error_count,
        "baseline_errors_sent_to_review": reviewed_error_count,
        "baseline_error_capture_rate": (
            reviewed_error_count / error_count if error_count else 0.0
        ),
        "attack_recall_all_rows": (
            auto_detected_attacks / total_attacks if total_attacks else 0.0
        ),
        "attacks_sent_to_review": int(((labels == 1) & reviewed).sum()),
        "false_alarms_auto": int(
            ((labels == 0) & (baseline_predictions == 1) & automatic).sum()
        ),
    }


def evaluate_attack_categories(
    categories: pd.Series,
    labels: np.ndarray,
    probabilities: np.ndarray,
    reviewed: np.ndarray,
    threshold: float,
    scenario: str,
) -> list[dict[str, Any]]:
    predictions = (probabilities >= threshold).astype(int)
    rows = []
    category_values = categories.fillna("Unknown").astype(str).to_numpy()
    for category in sorted(set(category_values)):
        if category.lower() == "normal":
            continue
        mask = category_values == category
        count = int(mask.sum())
        if not count:
            continue
        rows.append(
            {
                "scenario": scenario,
                "attack_category": category,
                "rows": count,
                "review_rate": float(reviewed[mask].mean()),
                "attack_recall_all_rows": float(
                    ((predictions[mask] == 1) & ~reviewed[mask]).mean()
                ),
                "attacks_caught_by_review": int(
                    ((labels[mask] == 1) & reviewed[mask]).sum()
                ),
            }
        )
    return rows
