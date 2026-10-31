from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.schemas import PredictionRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "model.pkl"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "models" / "metadata.json"
DEFAULT_THRESHOLD = 0.5


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
        self.load_error: str | None = None

    def load(self) -> None:
        self.model = None
        self.metadata = {}
        self.feature_columns = []
        self.threshold = DEFAULT_THRESHOLD
        self.load_error = None

        self.metadata = self._load_metadata()
        self.threshold = self._load_threshold()
        self.feature_columns = [
            *self.metadata.get("numeric_features", []),
            *self.metadata.get("categorical_features", []),
        ]

        if not self.model_path.exists():
            self.load_error = (
                "Model artifact is missing. Train the model before serving predictions."
            )
            raise ModelLoadError(self.load_error)

        try:
            self.model = joblib.load(self.model_path)
        except Exception as exc:
            self.load_error = "Model artifact could not be loaded."
            raise ModelLoadError(self.load_error) from exc

        if not self.feature_columns:
            self.model = None
            self.load_error = "Model metadata does not define input feature columns."
            raise ModelLoadError(self.load_error)

    def is_loaded(self) -> bool:
        return self.model is not None

    def predict(self, payload: PredictionRequest) -> dict[str, Any]:
        if self.model is None:
            raise ModelNotLoadedError(
                "Model is not loaded. Train or restore the model artifact first."
            )

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
            attack_probability = float(self.model.predict_proba(row)[0, 1])
        except Exception as exc:
            raise PredictionFailureError(
                "Prediction failed during model inference."
            ) from exc

        prediction = int(attack_probability >= self.threshold)

        return {
            "prediction": prediction,
            "prediction_label": "attack" if prediction == 1 else "normal",
            "attack_probability": attack_probability,
            "threshold": self.threshold,
            "model_name": self.metadata.get("primary_model_display_name", "unknown"),
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
        }

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
