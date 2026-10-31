from __future__ import annotations

from typing import Any

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
