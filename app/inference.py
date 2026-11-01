from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.schemas import BatchPredictionRequest, PredictionRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "model.pkl"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "models" / "metadata.json"
DEFAULT_THRESHOLD = 0.5
MODEL_DISPLAY_NAMES = {
    "random_forest": "Random Forest",
    "bagging": "Bagging Classifier",
    "gradient_boosting": "Gradient Boosting",
}


class ModelServiceError(RuntimeError):
    error_code = "model_service_error"
    status_code = 500

    def __init__(self, public_message: str) -> None:
        super().__init__(public_message)
        self.public_message = public_message


class ModelLoadError(ModelServiceError):
    error_code = "model_load_failed"
    status_code = 503


class ModelNotLoadedError(ModelServiceError):
    error_code = "model_not_loaded"
    status_code = 503


class ModelSelectionError(ModelServiceError):
    error_code = "model_unavailable"
    status_code = 400


class PredictionFailureError(ModelServiceError):
    error_code = "prediction_failed"
    status_code = 500


class ModelService:
    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        metadata_path: Path = DEFAULT_METADATA_PATH,
    ) -> None:
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.model = None
        self.metadata: dict[str, Any] = {}
        self.feature_columns: list[str] = []
        self.threshold = DEFAULT_THRESHOLD
        self.primary_model_name = "random_forest"
        self.model_thresholds: dict[str, float] = {}
        self.model_paths: dict[str, Path] = {}
        self.loaded_models: dict[str, Any] = {}
        self.load_error: str | None = None

    def load(self) -> None:
        self.model = None
        self.metadata = {}
        self.feature_columns = []
        self.threshold = DEFAULT_THRESHOLD
        self.primary_model_name = "random_forest"
        self.model_thresholds = {}
        self.model_paths = {}
        self.loaded_models = {}
        self.load_error = None

        self.metadata = self._load_metadata()
        self.primary_model_name = self.metadata.get("primary_model", "random_forest")
        primary_threshold = self._load_threshold()
        metadata_thresholds = self.metadata.get("model_thresholds", {})
        has_environment_threshold = os.getenv("NETSHIELD_THRESHOLD") is not None
        self.model_thresholds = {
            key: (
                primary_threshold
                if has_environment_threshold
                else float(metadata_thresholds.get(key, primary_threshold))
            )
            for key in MODEL_DISPLAY_NAMES
        }
        self.threshold = self.model_thresholds.get(
            self.primary_model_name, primary_threshold
        )
        self.feature_columns = [
            *self.metadata.get("numeric_features", []),
            *self.metadata.get("categorical_features", []),
        ]

        self.model_paths = self._available_model_paths()
        primary_path = self.model_paths.get(self.primary_model_name, self.model_path)
        if self.model_path != DEFAULT_MODEL_PATH:
            primary_path = self.model_path
            self.model_paths[self.primary_model_name] = primary_path

        if not primary_path.exists():
            self.load_error = (
                "Model artifact is missing. Train the model before serving predictions."
            )
            raise ModelLoadError(self.load_error)

        try:
            self.model = joblib.load(primary_path)
        except Exception as exc:
            self.load_error = "Model artifact could not be loaded."
            raise ModelLoadError(self.load_error) from exc

        if not self.feature_columns:
            self.model = None
            self.load_error = "Model metadata does not define input feature columns."
            raise ModelLoadError(self.load_error)
        self.loaded_models[self.primary_model_name] = self.model

    def is_loaded(self) -> bool:
        return self.model is not None

    def predict(
        self, payload: PredictionRequest, model_name: str | None = None
    ) -> dict[str, Any]:
        model_name = model_name or self.primary_model_name
        model, threshold = self._get_model(model_name)

        features = payload.model_dump()
        missing_features = [
            column for column in self.feature_columns if column not in features
        ]
        if missing_features:
            raise PredictionFailureError(
                "Model metadata is not aligned with the prediction request schema."
            )

        row = pd.DataFrame(
            [{column: features[column] for column in self.feature_columns}]
        )
        try:
            attack_probability = float(model.predict_proba(row)[0, 1])
        except Exception as exc:
            raise PredictionFailureError(
                "Prediction failed during model inference."
            ) from exc

        prediction = int(attack_probability >= threshold)

        return {
            "prediction": prediction,
            "prediction_label": "attack" if prediction == 1 else "normal",
            "attack_probability": attack_probability,
            "threshold": threshold,
            "model_name": MODEL_DISPLAY_NAMES.get(model_name, model_name),
        }

    def predict_batch(
        self, payload: BatchPredictionRequest, model_name: str | None = None
    ) -> dict[str, Any]:
        model_name = model_name or self.primary_model_name
        model, threshold = self._get_model(model_name)

        records = [record.model_dump() for record in payload.records]
        for features in records:
            missing_features = [
                column for column in self.feature_columns if column not in features
            ]
            if missing_features:
                raise PredictionFailureError(
                    "Model metadata is not aligned with the prediction request schema."
                )

        rows = pd.DataFrame(
            [
                {column: features[column] for column in self.feature_columns}
                for features in records
            ]
        )
        try:
            probabilities = model.predict_proba(rows)[:, 1]
        except Exception as exc:
            raise PredictionFailureError(
                "Batch prediction failed during model inference."
            ) from exc

        uncertainty = np.abs(probabilities - threshold)
        review_count = int(np.floor(payload.review_budget * len(records)))
        reviewed = np.zeros(len(records), dtype=bool)
        if review_count:
            review_indices = np.lexsort((np.arange(len(uncertainty)), uncertainty))[
                :review_count
            ]
            reviewed[review_indices] = True

        display_name = MODEL_DISPLAY_NAMES.get(model_name, model_name)
        items = []
        for index, probability in enumerate(probabilities):
            missing_features = [
                column
                for column in self.feature_columns
                if records[index].get(column) is None
            ]
            prediction = int(probability >= threshold)
            prediction_label = "attack" if prediction == 1 else "normal"
            is_review = bool(reviewed[index])
            items.append(
                {
                    "prediction": prediction,
                    "prediction_label": prediction_label,
                    "attack_probability": float(probability),
                    "threshold": threshold,
                    "model_name": display_name,
                    "decision": "review" if is_review else prediction_label,
                    "review_reason": (
                        "This record is among the least certain in the submitted batch."
                        if is_review
                        else None
                    ),
                    "uncertainty_margin": float(uncertainty[index]),
                    "missing_features": missing_features,
                }
            )

        return {
            "review_budget": payload.review_budget,
            "review_count": review_count,
            "review_rate": review_count / len(records),
            "threshold": threshold,
            "items": items,
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.is_loaded() else "degraded",
            "model_loaded": self.is_loaded(),
            "model_name": self.metadata.get("primary_model_display_name"),
            "generated_at": self.metadata.get("generated_at"),
            "threshold": self.threshold if self.is_loaded() else None,
            "status_detail": (
                "Model loaded successfully."
                if self.is_loaded()
                else self.load_error or "Model is not loaded."
            ),
        }

    def metadata_summary(self) -> dict[str, Any]:
        return {
            "service_name": "Network Intrusion Detection System",
            "service_version": "0.1.0",
            "dataset": self.metadata.get("dataset", "UNSW-NB15"),
            "task": self.metadata.get("task", "binary_classification"),
            "target": self.metadata.get("target", "label"),
            "primary_model": self.metadata.get("primary_model"),
            "primary_model_display_name": self.metadata.get(
                "primary_model_display_name"
            ),
            "model_loaded": self.is_loaded(),
            "decision_threshold": self.threshold if self.is_loaded() else None,
            "generated_at": self.metadata.get("generated_at"),
            "train_rows": self.metadata.get("train_rows"),
            "test_rows": self.metadata.get("test_rows"),
            "input_features": len(self.feature_columns) or None,
            "excluded_columns": self.metadata.get("excluded_columns", []),
            "available_models": [item["name"] for item in self.model_options()],
        }

    def model_options(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "display_name": MODEL_DISPLAY_NAMES[name],
                "available": path.exists(),
                "is_default": name == self.primary_model_name,
                "is_loaded": name in self.loaded_models,
            }
            for name, path in self.model_paths.items()
            if name in MODEL_DISPLAY_NAMES
        ]

    def _get_model(self, model_name: str) -> tuple[Any, float]:
        if not self.model_paths:
            raise ModelNotLoadedError(
                "Model is not loaded. Train or restore the model artifact first."
            )
        if model_name not in MODEL_DISPLAY_NAMES:
            raise ModelSelectionError("Choose one of the listed trained models.")
        model_path = self.model_paths.get(model_name)
        if model_path is None or not model_path.exists():
            raise ModelSelectionError(
                f"{MODEL_DISPLAY_NAMES[model_name]} is not available. Train it with "
                "`python -m src.train --model all` first."
            )

        model = self.loaded_models.get(model_name)
        if model is None:
            try:
                model = joblib.load(model_path)
            except Exception as exc:
                raise ModelLoadError(
                    f"Could not load {MODEL_DISPLAY_NAMES[model_name]} artifact."
                ) from exc
            for loaded_name in list(self.loaded_models):
                if loaded_name != self.primary_model_name:
                    del self.loaded_models[loaded_name]
            self.loaded_models[model_name] = model
        threshold = self.model_thresholds.get(model_name, self.threshold)
        return model, threshold

    def _available_model_paths(self) -> dict[str, Path]:
        configured = self.metadata.get("available_models", {})
        configured_is_authoritative = isinstance(configured, dict) and bool(configured)
        paths: dict[str, Path] = {}
        for name in MODEL_DISPLAY_NAMES:
            if configured_is_authoritative and name not in configured:
                continue
            entry = configured.get(name, {}) if isinstance(configured, dict) else {}
            configured_path = entry.get("path") if isinstance(entry, dict) else entry
            if configured_path:
                path = Path(configured_path)
                if not path.is_absolute():
                    path = PROJECT_ROOT / path
            elif self.model_path == DEFAULT_MODEL_PATH:
                path = PROJECT_ROOT / "models" / f"{name}_model.pkl"
            elif name == self.primary_model_name:
                path = self.model_path
            else:
                continue
            if path.exists():
                paths[name] = path

        if self.primary_model_name not in paths and self.model_path.exists():
            paths[self.primary_model_name] = self.model_path
        return paths

    def _load_metadata(self) -> dict[str, Any]:
        if not self.metadata_path.exists():
            return {}

        try:
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.load_error = "Model metadata is not valid JSON."
            raise ModelLoadError(self.load_error) from exc

    def _load_threshold(self) -> float:
        env_threshold = os.getenv("NETSHIELD_THRESHOLD")
        if env_threshold is not None:
            try:
                return float(env_threshold)
            except ValueError as exc:
                self.load_error = "NETSHIELD_THRESHOLD must be a valid number."
                raise ModelLoadError(self.load_error) from exc

        return float(self.metadata.get("decision_threshold", DEFAULT_THRESHOLD))


model_service = ModelService()
