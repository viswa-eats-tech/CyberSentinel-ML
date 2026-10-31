from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from starlette.responses import JSONResponse

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
from app.schemas import (
    ErrorResponse,
    HealthResponse,
    MetadataResponse,
    PredictionRequest,
    PredictionResponse,
)

logger = logging.getLogger(__name__)


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
        description="Binary intrusion detection API trained on UNSW-NB15.",
        version="0.1.0",
        lifespan=lifespan,
    )

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(**service.health())

    @api.get("/metadata", response_model=MetadataResponse)
    def metadata() -> MetadataResponse:
        return MetadataResponse(**service.metadata_summary())

    @api.post(
        "/predict",
        response_model=PredictionResponse,
        responses={
            500: {"model": ErrorResponse, "description": "Prediction error"},
            503: {"model": ErrorResponse, "description": "Model unavailable"},
        },
    )
    def predict(payload: PredictionRequest) -> PredictionResponse | JSONResponse:
        PREDICTION_REQUESTS.inc()
        start = perf_counter()
        try:
            result = service.predict(payload)
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
