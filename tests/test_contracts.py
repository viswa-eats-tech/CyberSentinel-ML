from __future__ import annotations

import json
from pathlib import Path

from app.main import app
from app.schemas import PredictionRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = PROJECT_ROOT / "models" / "metadata.json"
SAMPLE_REQUEST_PATH = PROJECT_ROOT / "reports" / "sample_prediction_request.json"
README_PATH = PROJECT_ROOT / "README.md"
RUNTIME_REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"
DEV_REQUIREMENTS_PATH = PROJECT_ROOT / "requirements-dev.txt"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
DOCKERIGNORE_PATH = PROJECT_ROOT / ".dockerignore"
SECURITY_PATH = PROJECT_ROOT / "SECURITY.md"
CONTRIBUTING_PATH = PROJECT_ROOT / "CONTRIBUTING.md"
RESPONSIBLE_USE_PATH = PROJECT_ROOT / "RESPONSIBLE_USE.md"
CITATION_PATH = PROJECT_ROOT / "CITATION.cff"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"


def test_sample_prediction_request_matches_api_schema() -> None:
    payload = json.loads(SAMPLE_REQUEST_PATH.read_text(encoding="utf-8"))

    request = PredictionRequest.model_validate(payload)

    assert set(payload) == set(PredictionRequest.model_fields)
    assert request.proto == "udp"
    assert request.service == "-"
    assert request.state == "INT"


def test_metadata_feature_contract_matches_api_schema() -> None:
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    feature_columns = [
        *metadata["numeric_features"],
        *metadata["categorical_features"],
    ]

    assert metadata["dataset"] == "UNSW-NB15"
    assert metadata["task"] == "binary_classification"
    assert metadata["target"] == "label"
    assert metadata["primary_model"] == "random_forest"
    assert metadata["primary_model_display_name"] == "Random Forest"
    assert metadata["decision_threshold"] == 0.55
    assert metadata["model_thresholds"]["random_forest"] == 0.55
    assert metadata["model_thresholds"]["logistic_regression"] == 0.55
    assert metadata["excluded_columns"] == ["id", "attack_cat"]
    assert metadata["primary_model_path"] == "models/random_forest_model.pkl"
    assert len(metadata["numeric_features"]) == 39
    assert metadata["categorical_features"] == ["proto", "service", "state"]
    assert set(feature_columns) == set(PredictionRequest.model_fields)


def test_openapi_schema_documents_core_endpoints() -> None:
    openapi_schema = app.openapi()
    paths = openapi_schema["paths"]

    assert openapi_schema["info"]["title"] == "Network Intrusion Detection System"
    assert "/health" in paths
    assert "/metadata" in paths
    assert "/predict" in paths
    assert "/metrics" in paths
    assert paths["/health"]["get"]["responses"]["200"]
    assert paths["/metadata"]["get"]["responses"]["200"]
    assert paths["/predict"]["post"]["requestBody"]["required"] is True
    assert paths["/predict"]["post"]["responses"]["200"]
    assert paths["/predict"]["post"]["responses"]["500"]
    assert paths["/predict"]["post"]["responses"]["503"]
    assert paths["/metrics"]["get"]["responses"]["200"]

    schemas = openapi_schema["components"]["schemas"]
    assert "ErrorResponse" in schemas
    assert "MetadataResponse" in schemas
    assert schemas["PredictionRequest"]["examples"]


def test_readme_contains_required_dataset_citation() -> None:
    readme = README_PATH.read_text(encoding="utf-8")

    assert "<repository-url>" not in readme
    assert "## Dataset Citation" in readme
    assert "https://research.unsw.edu.au/projects/unsw-nb15-dataset" in readme
    assert "Moustafa" in readme
    assert "Slay" in readme
    assert "Sarhan" in readme
    assert (
        "NetFlow Datasets for Machine Learning-Based Network Intrusion Detection Systems"
        in readme
    )


def test_dependency_files_separate_runtime_and_development_tools() -> None:
    runtime_requirements = RUNTIME_REQUIREMENTS_PATH.read_text(encoding="utf-8")
    dev_requirements = DEV_REQUIREMENTS_PATH.read_text(encoding="utf-8")

    assert "-r requirements.txt" in dev_requirements
    assert "pytest" in dev_requirements
    assert "httpx" in dev_requirements
    assert "ruff" in dev_requirements
    assert "pytest" not in runtime_requirements
    assert "httpx" not in runtime_requirements
    assert "ruff" not in runtime_requirements


def test_tracked_notebooks_are_valid_notebook_documents() -> None:
    notebook_paths = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))

    assert notebook_paths

    for notebook_path in notebook_paths:
        payload = json.loads(notebook_path.read_text(encoding="utf-8"))

        assert payload["nbformat"] >= 4
        assert isinstance(payload.get("cells"), list)
        assert payload["cells"], f"{notebook_path.name} must not be empty"


def test_ignore_rules_cover_local_and_generated_artifacts() -> None:
    gitignore = GITIGNORE_PATH.read_text(encoding="utf-8")
    dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8")

    required_gitignore_patterns = [
        ".venv/",
        ".env",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        "data/raw/",
        "data/processed/",
        "models/*.pkl",
        "!models/metadata.json",
        ".DS_Store",
    ]
    required_dockerignore_patterns = [
        ".venv/",
        ".env",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".git/",
        "data/raw/",
        "data/processed/",
        "notebooks/",
        "reports/*",
        "!reports/sample_prediction_request.json",
    ]

    for pattern in required_gitignore_patterns:
        assert pattern in gitignore

    for pattern in required_dockerignore_patterns:
        assert pattern in dockerignore


def test_project_governance_documents_are_present_and_linked() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    expected_documents = [
        CHANGELOG_PATH,
        SECURITY_PATH,
        CONTRIBUTING_PATH,
        RESPONSIBLE_USE_PATH,
        CITATION_PATH,
    ]

    for document_path in expected_documents:
        assert document_path.exists()
        assert document_path.read_text(encoding="utf-8").strip()
        assert document_path.name in readme


def test_security_document_sets_clear_non_production_scope() -> None:
    security_policy = SECURITY_PATH.read_text(encoding="utf-8")

    assert "not a production intrusion detection system" in security_policy
    assert "Do not open public GitHub issues" in security_policy
    assert "Do not include real credentials" in security_policy


def test_citation_file_contains_project_and_dataset_citation_notice() -> None:
    citation = CITATION_PATH.read_text(encoding="utf-8")

    assert "cff-version: 1.2.0" in citation
    assert 'title: "Network Intrusion Detection System"' in citation
    assert "type: software" in citation
    assert 'license: "MIT"' in citation
    assert 'version: "0.1.0"' in citation
    assert "UNSW-NB15 dataset papers listed in README.md" in citation


def test_changelog_documents_initial_release() -> None:
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    assert "## v0.1.0 - 2026-06-22" in changelog
    assert "Initial portfolio-ready MVP release." in changelog
    assert "Documented Limitations" in changelog
