# Changelog

All notable project changes are documented here.

## v0.1.0 - 2026-06-22

Initial portfolio-ready MVP release.

### Added

- End-to-end binary intrusion detection workflow on UNSW-NB15.
- Logistic Regression baseline and Random Forest primary model.
- Reusable scikit-learn preprocessing and model pipelines.
- Fixed operational Random Forest threshold at `0.55`.
- FastAPI inference service with `/health`, `/metadata`, `/predict`, `/metrics`, `/monitoring` and `/monitoring/snapshot`.
- Prometheus-compatible prediction counters, error counters and latency histogram.
- Human-readable monitoring dashboard.
- Docker and Docker Compose support.
- Model evaluation reports, feature importance analysis and threshold analysis.
- Sample prediction request for API smoke testing.
- CI pipeline with compile, lint, format and test checks.
- Ruff configuration for linting and formatting.
- API, contract and synthetic ML pipeline tests.
- Project governance documents: `CONTRIBUTING.md`, `SECURITY.md`, `RESPONSIBLE_USE.md` and `CITATION.cff`.
- Dataset citation section for UNSW-NB15 and its required references.
- Portfolio screenshots under `docs/images/`.

### Documented Limitations

- The project is a portfolio-grade ML engineering prototype, not a production IDS.
- The API does not include authentication, authorization or rate limiting.
- The system does not perform live packet capture, streaming inference or active alerting.
- Metrics are dataset-specific and based on the official UNSW-NB15 test CSV.
- Model binaries and raw datasets are intentionally excluded from Git.
