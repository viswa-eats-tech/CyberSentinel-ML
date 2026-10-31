from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import HTMLResponse, Response

PREDICTION_REQUESTS = Counter(
    "netshield_prediction_requests_total",
    "Total number of prediction requests.",
)

PREDICTION_ERRORS = Counter(
    "netshield_prediction_errors_total",
    "Total number of prediction errors.",
)

PREDICTION_LATENCY = Histogram(
    "netshield_prediction_latency_seconds",
    "Prediction endpoint latency in seconds.",
)


@dataclass
class MonitoringState:
    total_requests: int = 0
    total_errors: int = 0
    total_latency_seconds: float = 0.0
    last_latency_seconds: float | None = None
    last_prediction_label: str | None = None
    last_attack_probability: float | None = None


_state = MonitoringState()
_lock = Lock()


def record_prediction(
    latency_seconds: float,
    result: dict[str, Any] | None = None,
    error: bool = False,
) -> None:
    with _lock:
        _state.total_requests += 1
        _state.total_latency_seconds += latency_seconds
        _state.last_latency_seconds = latency_seconds

        if error:
            _state.total_errors += 1
            return

        if result:
            _state.last_prediction_label = result.get("prediction_label")
            _state.last_attack_probability = result.get("attack_probability")


def monitoring_snapshot() -> dict[str, Any]:
    with _lock:
        average_latency = (
            _state.total_latency_seconds / _state.total_requests
            if _state.total_requests
            else 0.0
        )
        error_rate = (
            _state.total_errors / _state.total_requests
            if _state.total_requests
            else 0.0
        )

        return {
            "total_requests": _state.total_requests,
            "total_errors": _state.total_errors,
            "error_rate": error_rate,
            "average_latency_seconds": average_latency,
            "last_latency_seconds": _state.last_latency_seconds,
            "last_prediction_label": _state.last_prediction_label,
            "last_attack_probability": _state.last_attack_probability,
        }


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def monitoring_dashboard_response(model_health: dict[str, Any]) -> HTMLResponse:
    snapshot = monitoring_snapshot()
    model_loaded = "Loaded" if model_health.get("model_loaded") else "Not loaded"
    model_status_class = "ok" if model_health.get("model_loaded") else "bad"
    model_name = model_health.get("model_name") or "Unknown"
    generated_at = model_health.get("generated_at") or "n/a"
    threshold = model_health.get("threshold")
    threshold_text = f"{threshold:.2f}" if threshold is not None else "n/a"

    last_probability = snapshot["last_attack_probability"]
    last_probability_text = (
        f"{last_probability:.4f}" if last_probability is not None else "n/a"
    )
    last_latency_text = (
        f"{snapshot['last_latency_seconds'] * 1000:.2f} ms"
        if snapshot["last_latency_seconds"] is not None
        else "n/a"
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>Netshield Monitoring</title>
  <style>
    :root {{
      --bg: #f3f5f8;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --text: #172033;
      --muted: #647084;
      --border: #d8dee8;
      --border-strong: #b8c2d2;
      --blue: #2b65c8;
      --green: #16845b;
      --red: #c83d3d;
      --amber: #b86b00;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }}

    main {{
      width: min(1180px, calc(100vw - 40px));
      margin: 24px auto 44px;
    }}

    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: end;
      margin-bottom: 18px;
    }}

    h1 {{
      margin: 0 0 5px;
      font-size: 28px;
      font-weight: 750;
      letter-spacing: 0;
    }}

    h2 {{
      margin: 0 0 12px;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0;
    }}

    .muted {{ color: var(--muted); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}

    .links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .links a {{
      display: inline-block;
      color: var(--blue);
      background: #eef4ff;
      border: 1px solid #c7d7fe;
      border-radius: 6px;
      padding: 8px 11px;
      text-decoration: none;
      font-weight: 600;
      font-size: 14px;
    }}

    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      border: 1px solid var(--border);
      background: var(--border);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 16px;
    }}

    .metric {{
      background: var(--surface);
      padding: 15px 16px;
      min-height: 88px;
    }}

    .panel {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }}

    .metric span {{
      display: block;
      color: var(--muted);
      margin-bottom: 5px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .03em;
    }}

    .metric strong {{
      display: block;
      font-size: 25px;
      font-weight: 760;
      letter-spacing: 0;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}

    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 10px 8px;
      text-align: left;
    }}

    th {{
      color: var(--muted);
      font-weight: 600;
    }}

    tbody tr:last-child th,
    tbody tr:last-child td {{
      border-bottom: 0;
    }}

    .status {{
      display: inline-block;
      border-radius: 999px;
      padding: 5px 10px;
      font-weight: 700;
      font-size: 13px;
    }}

    .status.ok {{
      color: var(--green);
      background: #e9f8f0;
      border: 1px solid #b8e3cc;
    }}

    .status.bad {{
      color: var(--red);
      background: #fff0f0;
      border: 1px solid #f1b9b9;
    }}

    .good {{ color: var(--green); }}
    .warn {{ color: var(--amber); }}
    .bad {{ color: var(--red); }}

    .status-strip {{
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }}

    .callout {{
      background: var(--surface-soft);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 13px 15px;
      font-size: 14px;
    }}

    @media (max-width: 860px) {{
      main {{ width: min(100vw - 24px, 720px); }}
      header {{ grid-template-columns: 1fr; align-items: start; }}
      .links {{ justify-content: flex-start; margin-top: 14px; }}
      .summary, .grid, .status-strip {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Netshield Monitoring</h1>
        <div class="muted">Runtime view for the FastAPI inference service - refreshes every 5 seconds</div>
      </div>
      <nav class="links" aria-label="Service links">
        <a href="/docs">API Docs</a>
        <a href="/health">Health JSON</a>
        <a href="/metadata">Metadata JSON</a>
        <a href="/metrics">Prometheus Metrics</a>
      </nav>
    </header>

    <section class="status-strip">
      <div class="callout">
        <strong>Service path</strong>
        <div class="muted"><span class="mono">POST /predict</span> records requests, errors and latency. <span class="mono">GET /metrics</span> remains Prometheus-compatible.</div>
      </div>
      <div class="callout">
        <strong>Model state</strong>
        <div><span class="status {model_status_class}">{model_loaded}</span> <span class="muted">{model_name}</span></div>
      </div>
    </section>

    <section class="summary" aria-label="Prediction metrics">
      <div class="metric"><span>Total requests</span><strong>{snapshot["total_requests"]}</strong></div>
      <div class="metric"><span>Total errors</span><strong class="bad">{snapshot["total_errors"]}</strong></div>
      <div class="metric"><span>Average latency</span><strong>{snapshot["average_latency_seconds"] * 1000:.2f} ms</strong></div>
      <div class="metric"><span>Error rate</span><strong>{snapshot["error_rate"] * 100:.2f}%</strong></div>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>Model</h2>
        <table>
          <tbody>
            <tr><th>Status</th><td><span class="status {model_status_class}">{model_loaded}</span></td></tr>
            <tr><th>Model</th><td>{model_name}</td></tr>
            <tr><th>Decision threshold</th><td>{threshold_text}</td></tr>
            <tr><th>Generated at</th><td><span class="mono">{generated_at}</span></td></tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <h2>Last Prediction</h2>
        <table>
          <tbody>
            <tr><th>Label</th><td>{snapshot["last_prediction_label"] or "n/a"}</td></tr>
            <tr><th>Attack probability</th><td>{last_probability_text}</td></tr>
            <tr><th>Latency</th><td>{last_latency_text}</td></tr>
          </tbody>
        </table>
      </article>
    </section>
  </main>
</body>
</html>
"""
    return HTMLResponse(html)
