from __future__ import annotations

import json
import sys

import pandas as pd
import pytest
from src.data_loader import feature_groups, split_features_target
from src.evaluate import evaluate_classifier
from src.preprocessor import build_preprocessor
from src.train import (
    build_pipeline,
    select_threshold_on_validation,
    stratified_sample,
)
from src.train import (
    main as train_main,
)


def make_synthetic_flow_frame(
    row_count: int = 40, label_offset: int = 0
) -> pd.DataFrame:
    rows = []
    for index in range(row_count):
        label = (index + label_offset) % 2
        attack = label == 1
        rows.append(
            {
                "id": index + 1,
                "dur": 0.01 + index * 0.001,
                "proto": "tcp" if index % 3 == 0 else "udp",
                "service": "http" if attack else "-",
                "state": "INT" if attack else "FIN",
                "spkts": 2 + (8 if attack else 0) + index % 3,
                "dpkts": 1 + (4 if not attack else 0) + index % 2,
                "sbytes": 120 + (900 if attack else 0) + index * 7,
                "dbytes": 80 + (400 if not attack else 0) + index * 5,
                "rate": 50.0 + (200.0 if attack else 0.0) + index,
                "sttl": 254 if attack else 62,
                "dttl": 0 if attack else 252,
                "sload": 180363632.0 if attack else 1200.0 + index,
                "dload": 0.0 if attack else 3000.0 + index,
                "attack_cat": "Generic" if attack else "Normal",
                "label": label,
            }
        )
    return pd.DataFrame(rows)


def test_split_features_target_drops_target_and_leakage_columns() -> None:
    data = make_synthetic_flow_frame(6)
    data["label"] = data["label"].astype(str)

    features, target = split_features_target(data)

    assert "label" not in features.columns
    assert "id" not in features.columns
    assert "attack_cat" not in features.columns
    assert target.tolist() == [0, 1, 0, 1, 0, 1]
    assert str(target.dtype).startswith("int")


def test_split_features_target_requires_label_column() -> None:
    data = make_synthetic_flow_frame(4).drop(columns=["label"])

    with pytest.raises(ValueError, match="Missing required target column"):
        split_features_target(data)


def test_feature_groups_identifies_numeric_and_categorical_without_leakage() -> None:
    data = make_synthetic_flow_frame(8)

    numeric_features, categorical_features = feature_groups(data)

    assert categorical_features == ["proto", "service", "state"]
    assert "dur" in numeric_features
    assert "sbytes" in numeric_features
    assert "label" not in numeric_features
    assert "id" not in numeric_features
    assert "attack_cat" not in numeric_features


def test_preprocessor_handles_unseen_categorical_values() -> None:
    data = make_synthetic_flow_frame(12)
    features, _ = split_features_target(data)
    numeric_features, categorical_features = feature_groups(data)
    preprocessor = build_preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        scale_numeric=True,
    )
    preprocessor.fit(features)

    unseen_features = features.head(2).copy()
    unseen_features.loc[:, "proto"] = ["icmp", "sctp"]
    unseen_features.loc[:, "service"] = ["dns", "ssh"]
    unseen_features.loc[:, "state"] = ["CON", "REQ"]

    transformed = preprocessor.transform(unseen_features)

    assert transformed.shape[0] == 2
    assert transformed.shape[1] >= len(numeric_features)


def test_logistic_regression_pipeline_smoke_fit_predicts_probabilities() -> None:
    data = make_synthetic_flow_frame(30)
    features, target = split_features_target(data)
    numeric_features, categorical_features = feature_groups(data)
    pipeline = build_pipeline(
        "logistic_regression",
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_state=42,
    )

    pipeline.fit(features, target)
    probabilities = pipeline.predict_proba(features.head(5))

    assert probabilities.shape == (5, 2)
    assert ((probabilities >= 0) & (probabilities <= 1)).all()


def test_random_forest_pipeline_smoke_evaluates_with_threshold() -> None:
    data = make_synthetic_flow_frame(32)
    features, target = split_features_target(data)
    numeric_features, categorical_features = feature_groups(data)
    pipeline = build_pipeline(
        "random_forest",
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_state=42,
    )

    pipeline.fit(features, target)
    metrics = evaluate_classifier(pipeline, features, target, threshold=0.55)
    matrix = metrics["confusion_matrix"]

    assert 0 <= metrics["accuracy"] <= 1
    assert 0 <= metrics["precision_attack"] <= 1
    assert 0 <= metrics["recall_attack"] <= 1
    assert 0 <= metrics["f1_attack"] <= 1
    assert 0 <= metrics["roc_auc"] <= 1
    assert sum(matrix.values()) == len(data)


def test_stratified_sample_preserves_class_coverage_and_size() -> None:
    data = make_synthetic_flow_frame(40)

    sampled = stratified_sample(data, sample_size=10, random_state=42)

    assert len(sampled) == 10
    assert set(sampled["label"]) == {0, 1}
    assert sampled["label"].value_counts().to_dict() == {0: 5, 1: 5}


def test_threshold_selection_uses_training_validation_split() -> None:
    data = make_synthetic_flow_frame(40)
    features, target = split_features_target(data)
    numeric_features, categorical_features = feature_groups(data)

    selected_threshold, selection = select_threshold_on_validation(
        model_name="random_forest",
        X_train=features,
        y_train=target,
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        random_state=42,
        validation_size=0.25,
        thresholds=[0.3, 0.5, 0.7],
        min_recall=0.8,
    )

    assert selected_threshold in {0.3, 0.5, 0.7}
    assert selection["method"] == "training_validation_split"
    assert selection["candidate_count"] == 3
    assert selection["fit_rows"] + selection["validation_rows"] == len(data)
    assert selection["selected_metrics"]["threshold"] == selected_threshold


def test_training_script_smoke_uses_synthetic_csvs_without_saving_models(
    tmp_path,
    monkeypatch,
) -> None:
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"
    dataset_dir.mkdir()
    make_synthetic_flow_frame(30).to_csv(
        dataset_dir / "UNSW_NB15_training-set.csv",
        index=False,
    )
    make_synthetic_flow_frame(16, label_offset=1).to_csv(
        dataset_dir / "UNSW_NB15_testing-set.csv",
        index=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train.py",
            "--dataset-dir",
            str(dataset_dir),
            "--output-dir",
            str(output_dir),
            "--reports-dir",
            str(reports_dir),
            "--model",
            "logistic_regression",
            "--threshold",
            "0.55",
            "--no-save",
        ],
    )

    train_main()

    results = json.loads((reports_dir / "training_results.json").read_text())
    assert results["train_rows"] == 30
    assert results["test_rows"] == 16
    assert results["decision_threshold"] == 0.55
    assert set(results["models"]) == {"logistic_regression"}
    assert (reports_dir / "training_results.md").exists()
    assert not any(output_dir.glob("*.pkl"))
    assert not (output_dir / "metadata.json").exists()
