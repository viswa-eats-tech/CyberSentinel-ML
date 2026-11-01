from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from app.schemas import ResearchExperimentRequest

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = PROJECT_ROOT / "reports" / "feature_robustness_results.json"
_lock = threading.Lock()
_state: dict[str, Any] = {
    "status": "idle",
    "message": "No experiment is running.",
    "started_at": None,
    "finished_at": None,
    "return_code": None,
}


def get_results() -> dict[str, Any]:
    if not RESULTS_PATH.exists():
        return {"available": False, "message": "Run the study to create a report."}
    try:
        results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read the feature outage report.")
        return {"available": False, "message": "The saved report could not be read."}
    return {"available": True, "results": results}


def get_status() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def start_experiment(request: ResearchExperimentRequest) -> tuple[bool, dict[str, Any]]:
    with _lock:
        if _state["status"] == "running":
            return False, dict(_state)
        _state.update(
            {
                "status": "running",
                "message": "Training models and evaluating feature outages.",
                "started_at": None,
                "finished_at": None,
                "return_code": None,
            }
        )
        worker = threading.Thread(
            target=_run_experiment,
            args=(request,),
            name="feature-outage-experiment",
            daemon=True,
        )
        worker.start()
        return True, dict(_state)


def _run_experiment(request: ResearchExperimentRequest) -> None:
    from datetime import UTC, datetime

    with _lock:
        _state["started_at"] = datetime.now(UTC).isoformat()
    command = [
        sys.executable,
        "-m",
        "src.robustness_experiment",
        "--review-budget",
        str(request.review_budget),
        "--training-seeds",
        str(request.training_seeds),
        "--random-repeats",
        str(request.random_repeats),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        successful = completed.returncode == 0
        output = (completed.stdout + "\n" + completed.stderr).strip()
        finish_time = datetime.now(UTC).isoformat()
        with _lock:
            _state.update(
                {
                    "status": "complete" if successful else "failed",
                    "message": (
                        "Study finished. The saved dashboard data has been updated."
                        if successful
                        else "The study did not finish. Check that the UNSW-NB15 "
                        "training and testing CSV files are available."
                    ),
                    "finished_at": finish_time,
                    "return_code": completed.returncode,
                    "output": output[-5000:],
                }
            )
    except subprocess.TimeoutExpired:
        with _lock:
            _state.update(
                {
                    "status": "failed",
                    "message": "The study stopped after the one-hour time limit.",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "return_code": None,
                }
            )
    except OSError:
        logger.exception("Could not launch the feature outage experiment.")
        with _lock:
            _state.update(
                {
                    "status": "failed",
                    "message": "Could not start the experiment with this Python environment.",
                    "finished_at": datetime.now(UTC).isoformat(),
                    "return_code": None,
                }
            )
