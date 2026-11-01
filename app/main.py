from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, JSONResponse

from app.inference import ModelService, ModelServiceError, model_service
from app.monitoring import (
    PREDICTION_ERRORS,
    PREDICTION_LATENCY,
    PREDICTION_REQUESTS,
    metrics_response,
    monitoring_dashboard_response,
    monitoring_snapshot,
    record_prediction,
)
from app.research import get_results, get_status, start_experiment
from app.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    ErrorResponse,
    HealthResponse,
    MetadataResponse,
    PredictionRequest,
    PredictionResponse,
    ResearchExperimentRequest,
)
from src.synthetic_flow import generate_synthetic_flow

logger = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
SAMPLE_INPUT_PATH = APP_DIR.parent / "reports" / "sample_prediction_request.json"
SAMPLE_BATCH_PATH = APP_DIR.parent / "reports" / "sample_batch_records.json"
TRAINING_RESULTS_PATH = APP_DIR.parent / "reports" / "training_results.json"


def sample_random_flows(count: int) -> list[dict[str, object]]:
    return [generate_synthetic_flow() for _ in range(count)]


def error_response(exc: ModelServiceError) -> JSONResponse:
    payload = ErrorResponse(
        error=exc.error_code,
        message=exc.public_message,
        status_code=exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


def create_app(service: ModelService = model_service) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            service.load()
        except ModelServiceError:
            logger.exception("Model service started in degraded mode.")
        yield

    api = FastAPI(
        title="Network Intrusion Detection System",
        description=(
            "UNSW-NB15 intrusion detection API with single-record predictions "
            "and batch-level uncertainty review."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @api.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @api.get("/results", include_in_schema=False)
    def results_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "results.html")

    @api.get("/results/training-data", include_in_schema=False)
    def training_results_data():
        if not TRAINING_RESULTS_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Training results are not available yet. Train the models first.",
            )
        return FileResponse(TRAINING_RESULTS_PATH, media_type="application/json")

    @api.get("/research/feature-outages", include_in_schema=False)
    def feature_outage_study() -> FileResponse:
        return FileResponse(STATIC_DIR / "research.html")

    @api.get("/research/feature-outages/results", include_in_schema=False)
    def feature_outage_results():
        return get_results()

    @api.get("/research/feature-outages/status", include_in_schema=False)
    def feature_outage_status():
        return get_status()

    @api.post("/research/feature-outages/run", include_in_schema=False)
    def run_feature_outage_study(payload: ResearchExperimentRequest):
        started, state = start_experiment(payload)
        if not started:
            raise HTTPException(
                status_code=409,
                detail="A feature outage experiment is already running.",
            )
        return state

    @api.get("/sample-input", include_in_schema=False)
    def sample_input() -> FileResponse:
        return FileResponse(SAMPLE_INPUT_PATH, media_type="application/json")

    @api.get("/sample-batch-input", include_in_schema=False)
    def sample_batch_input() -> FileResponse:
        return FileResponse(SAMPLE_BATCH_PATH, media_type="application/json")

    @api.get("/sample-random-input", include_in_schema=False)
    def sample_random_input():
        return sample_random_flows(1)[0]

    @api.get("/sample-random-batch", include_in_schema=False)
    def sample_random_batch(count: int = Query(default=10, ge=2, le=100)):
        return sample_random_flows(count)

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(**service.health())

    @api.get("/metadata", response_model=MetadataResponse)
    def metadata() -> MetadataResponse:
        return MetadataResponse(**service.metadata_summary())

    @api.get("/models", include_in_schema=False)
    def models():
        return {
            "default_model": service.primary_model_name,
            "models": service.model_options(),
        }

    @api.post(
        "/predict",
        response_model=PredictionResponse,
        responses={
            500: {"model": ErrorResponse, "description": "Prediction error"},
            503: {"model": ErrorResponse, "description": "Model unavailable"},
        },
    )
    def predict(
        payload: PredictionRequest,
        model_name: str | None = Query(default=None),
    ) -> PredictionResponse | JSONResponse:
        PREDICTION_REQUESTS.inc()
        start = perf_counter()
        try:
            result = (
                service.predict(payload, model_name=model_name)
                if model_name
                else service.predict(payload)
            )
        except ModelServiceError as exc:
            latency = perf_counter() - start
            PREDICTION_LATENCY.observe(latency)
            PREDICTION_ERRORS.inc()
            record_prediction(latency, error=True)
            return error_response(exc)

        latency = perf_counter() - start
        PREDICTION_LATENCY.observe(latency)
        record_prediction(latency, result=result)

        return PredictionResponse(**result)

    @api.post(
        "/predict/batch",
        response_model=BatchPredictionResponse,
        responses={
            500: {"model": ErrorResponse, "description": "Batch prediction error"},
            503: {"model": ErrorResponse, "description": "Model unavailable"},
        },
        summary="Predict a batch and route the least certain records for review",
    )
    def predict_batch(
        payload: BatchPredictionRequest,
        model_name: str | None = Query(default=None),
    ) -> BatchPredictionResponse | JSONResponse:
        PREDICTION_REQUESTS.inc()
        start = perf_counter()
        try:
            result = (
                service.predict_batch(payload, model_name=model_name)
                if model_name
                else service.predict_batch(payload)
            )
        except ModelServiceError as exc:
            latency = perf_counter() - start
            PREDICTION_LATENCY.observe(latency)
            PREDICTION_ERRORS.inc()
            record_prediction(latency, error=True)
            return error_response(exc)

        latency = perf_counter() - start
        PREDICTION_LATENCY.observe(latency)
        last_item = result["items"][-1] if result["items"] else None
        record_prediction(latency, result=last_item)
        return BatchPredictionResponse(**result)

    @api.get("/metrics")
    def metrics():
        return metrics_response()

    @api.get("/monitoring", include_in_schema=False)
    def monitoring():
        return monitoring_dashboard_response(service.health())

    @api.get("/monitoring/snapshot", include_in_schema=False)
    def monitoring_snapshot_json():
        return monitoring_snapshot()

    return api


app = create_app()
