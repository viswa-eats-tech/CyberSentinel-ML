from __future__ import annotations

import json
from pathlib import Path

from app.inference import ModelService, PredictionFailureError
from app.main import create_app
from app.schemas import PredictionRequest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REQUEST_PATH = PROJECT_ROOT / "reports" / "sample_prediction_request.json"


def load_sample_request() -> dict[str, object]:
    return json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))


def test_api_starts_in_degraded_mode_when_model_artifact_is_missing(tmp_path) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "dataset": "UNSW-NB15",
                "task": "binary_classification",
                "target": "label",
                "primary_model": "random_forest",
                "primary_model_display_name": "Random Forest",
                "decision_threshold": 0.55,
                "numeric_features": ["dur"],
                "categorical_features": ["proto"],
                "excluded_columns": ["id", "attack_cat"],
            }
        ),
        encoding="utf-8",
    )
    service = ModelService(
        model_path=tmp_path / "missing-model.pkl",
        metadata_path=metadata_path,
    )
    api = create_app(service)

    with TestClient(api) as client:
        health_response = client.get("/health")
        predict_response = client.post("/predict", json=load_sample_request())
        metadata_response = client.get("/metadata")

    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert health_payload["status"] == "degraded"
    assert health_payload["model_loaded"] is False
    assert "missing" in health_payload["status_detail"].lower()

    assert predict_response.status_code == 503
    error_payload = predict_response.json()
    assert error_payload == {
        "error": "model_not_loaded",
        "message": "Model is not loaded. Train or restore the model artifact first.",
        "status_code": 503,
    }

    assert metadata_response.status_code == 200
    metadata_payload = metadata_response.json()
    assert metadata_payload["dataset"] == "UNSW-NB15"
    assert metadata_payload["model_loaded"] is False
    assert metadata_payload["decision_threshold"] is None
    assert metadata_payload["input_features"] == 2


class FailingPredictionService:
    def load(self) -> None:
        return None

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "model_loaded": True,
            "model_name": "Random Forest",
            "generated_at": "2026-06-17T07:49:02.589247+00:00",
            "threshold": 0.55,
            "status_detail": "Model loaded successfully.",
        }

    def metadata_summary(self) -> dict[str, object]:
        return {
            "service_name": "Network Intrusion Detection System",
            "service_version": "0.1.0",
            "dataset": "UNSW-NB15",
            "task": "binary_classification",
            "target": "label",
            "primary_model": "random_forest",
            "primary_model_display_name": "Random Forest",
            "model_loaded": True,
            "decision_threshold": 0.55,
            "generated_at": "2026-06-17T07:49:02.589247+00:00",
            "train_rows": 175341,
            "test_rows": 82332,
            "input_features": 42,
            "excluded_columns": ["id", "attack_cat"],
        }

    def predict(self, payload: PredictionRequest) -> dict[str, object]:
        raise PredictionFailureError("Prediction failed during model inference.")


def test_prediction_failures_return_structured_500_response() -> None:
    api = create_app(FailingPredictionService())

    with TestClient(api) as client:
        response = client.post("/predict", json=load_sample_request())
        snapshot_response = client.get("/monitoring/snapshot")

    assert response.status_code == 500
    assert response.json() == {
        "error": "prediction_failed",
        "message": "Prediction failed during model inference.",
        "status_code": 500,
    }

    snapshot = snapshot_response.json()
    assert snapshot["total_requests"] >= 1
    assert snapshot["total_errors"] >= 1
