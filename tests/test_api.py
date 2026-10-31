from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "models" / "model.pkl"
SAMPLE_REQUEST_PATH = PROJECT_ROOT / "reports" / "sample_prediction_request.json"
METADATA_PATH = PROJECT_ROOT / "models" / "metadata.json"

pytestmark = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="models/model.pkl is required. Run `python -m src.train --model both` first.",
)


def test_health_endpoint_reports_loaded_model() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True
    assert payload["model_name"] == "Random Forest"


def test_predict_endpoint_returns_prediction() -> None:
    sample_request = json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    expected_threshold = metadata.get("decision_threshold", 0.5)

    with TestClient(app) as client:
        response = client.post("/predict", json=sample_request)

    assert response.status_code == 200
    payload = response.json()
    assert payload["prediction"] in {0, 1}
    assert payload["prediction_label"] in {"normal", "attack"}
    assert 0 <= payload["attack_probability"] <= 1
    assert payload["threshold"] == expected_threshold
    assert payload["model_name"] == "Random Forest"


def test_predict_endpoint_rejects_invalid_payload() -> None:
    sample_request = json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))
    sample_request.pop("dur")

    with TestClient(app) as client:
        response = client.post("/predict", json=sample_request)

    assert response.status_code == 422


def test_metrics_endpoint_exposes_prediction_counters() -> None:
    sample_request = json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))

    with TestClient(app) as client:
        client.post("/predict", json=sample_request)
        response = client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert "netshield_prediction_requests_total" in text
    assert "netshield_prediction_errors_total" in text
    assert "netshield_prediction_latency_seconds" in text


def test_monitoring_dashboard_exposes_human_readable_metrics() -> None:
    sample_request = json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))

    with TestClient(app) as client:
        client.post("/predict", json=sample_request)
        response = client.get("/monitoring")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Netshield Monitoring" in response.text
    assert "Total requests" in response.text
    assert "Last Prediction" in response.text


def test_monitoring_snapshot_endpoint_returns_json() -> None:
    sample_request = json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))

    with TestClient(app) as client:
        client.post("/predict", json=sample_request)
        response = client.get("/monitoring/snapshot")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_requests"] >= 1
    assert payload["total_errors"] >= 0
    assert payload["average_latency_seconds"] >= 0
