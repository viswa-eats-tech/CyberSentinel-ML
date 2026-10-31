from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "dur": 0.000011,
                    "proto": "udp",
                    "service": "-",
                    "state": "INT",
                    "spkts": 2,
                    "dpkts": 0,
                    "sbytes": 496,
                    "dbytes": 0,
                    "rate": 90909.0902,
                    "sttl": 254,
                    "dttl": 0,
                    "sload": 180363632.0,
                    "dload": 0.0,
                    "sloss": 0,
                    "dloss": 0,
                    "sinpkt": 0.011,
                    "dinpkt": 0.0,
                    "sjit": 0.0,
                    "djit": 0.0,
                    "swin": 0,
                    "stcpb": 0,
                    "dtcpb": 0,
                    "dwin": 0,
                    "tcprtt": 0.0,
                    "synack": 0.0,
                    "ackdat": 0.0,
                    "smean": 248,
                    "dmean": 0,
                    "trans_depth": 0,
                    "response_body_len": 0,
                    "ct_srv_src": 2,
                    "ct_state_ttl": 2,
                    "ct_dst_ltm": 1,
                    "ct_src_dport_ltm": 1,
                    "ct_dst_sport_ltm": 1,
                    "ct_dst_src_ltm": 2,
                    "is_ftp_login": 0,
                    "ct_ftp_cmd": 0,
                    "ct_flw_http_mthd": 0,
                    "ct_src_ltm": 1,
                    "ct_srv_dst": 2,
                    "is_sm_ips_ports": 0,
                }
            ]
        },
    )

    dur: float = Field(..., ge=0)
    proto: str
    service: str
    state: str
    spkts: int = Field(..., ge=0)
    dpkts: int = Field(..., ge=0)
    sbytes: int = Field(..., ge=0)
    dbytes: int = Field(..., ge=0)
    rate: float = Field(..., ge=0)
    sttl: int = Field(..., ge=0)
    dttl: int = Field(..., ge=0)
    sload: float = Field(..., ge=0)
    dload: float = Field(..., ge=0)
    sloss: int = Field(..., ge=0)
    dloss: int = Field(..., ge=0)
    sinpkt: float = Field(..., ge=0)
    dinpkt: float = Field(..., ge=0)
    sjit: float = Field(..., ge=0)
    djit: float = Field(..., ge=0)
    swin: int = Field(..., ge=0)
    stcpb: int = Field(..., ge=0)
    dtcpb: int = Field(..., ge=0)
    dwin: int = Field(..., ge=0)
    tcprtt: float = Field(..., ge=0)
    synack: float = Field(..., ge=0)
    ackdat: float = Field(..., ge=0)
    smean: int = Field(..., ge=0)
    dmean: int = Field(..., ge=0)
    trans_depth: int = Field(..., ge=0)
    response_body_len: int = Field(..., ge=0)
    ct_srv_src: int = Field(..., ge=0)
    ct_state_ttl: int = Field(..., ge=0)
    ct_dst_ltm: int = Field(..., ge=0)
    ct_src_dport_ltm: int = Field(..., ge=0)
    ct_dst_sport_ltm: int = Field(..., ge=0)
    ct_dst_src_ltm: int = Field(..., ge=0)
    is_ftp_login: int = Field(..., ge=0)
    ct_ftp_cmd: int = Field(..., ge=0)
    ct_flw_http_mthd: int = Field(..., ge=0)
    ct_src_ltm: int = Field(..., ge=0)
    ct_srv_dst: int = Field(..., ge=0)
    is_sm_ips_ports: int = Field(..., ge=0)


class PredictionResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "prediction": 1,
                    "prediction_label": "attack",
                    "attack_probability": 0.7458317542992821,
                    "threshold": 0.55,
                    "model_name": "Random Forest",
                }
            ]
        }
    )

    prediction: int
    prediction_label: str
    attack_probability: float
    threshold: float
    model_name: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "model_loaded": True,
                    "model_name": "Random Forest",
                    "generated_at": "2026-06-17T07:49:02.589247+00:00",
                    "threshold": 0.55,
                    "status_detail": "Model loaded successfully.",
                }
            ]
        }
    )

    status: str
    model_loaded: bool
    model_name: str | None = None
    generated_at: str | None = None
    threshold: float | None = None
    status_detail: str | None = None


class MetadataResponse(BaseModel):
    service_name: str
    service_version: str
    dataset: str
    task: str
    target: str
    primary_model: str | None = None
    primary_model_display_name: str | None = None
    model_loaded: bool
    decision_threshold: float | None = None
    generated_at: str | None = None
    train_rows: int | None = None
    test_rows: int | None = None
    input_features: int | None = None
    excluded_columns: list[str]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "model_not_loaded",
                    "message": "Model is not loaded. Train or restore the model artifact first.",
                    "status_code": 503,
                }
            ]
        }
    )

    error: str
    message: str
    status_code: int
