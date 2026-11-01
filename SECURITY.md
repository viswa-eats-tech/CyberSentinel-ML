# Security Policy

## Project Scope

This repository is an educational and portfolio-oriented machine learning project for binary intrusion detection on the UNSW-NB15 dataset.

It is not a production intrusion detection system and should not be used as the only security control in a real network environment.

The current version does not provide:

- authentication or authorization
- transport-layer security configuration
- rate limiting
- live packet capture
- active alerting or incident response
- model drift detection
- continuous retraining

These limitations are intentional for the current project scope and are documented in the README.

## Supported Versions

Security review and fixes are focused on the current `main` branch.

No long-term support policy is provided for older commits, tags or forks.

## Reporting Security Issues

Do not open public GitHub issues for suspected security vulnerabilities.

Use GitHub private vulnerability reporting or a private security advisory when available. If private reporting is not available, contact the repository maintainer through their GitHub profile before disclosing technical details publicly.

When reporting an issue, include:

- affected file, endpoint or workflow
- clear reproduction steps
- expected impact
- whether the issue requires local access, repository write access or network access
- any relevant logs or request examples without secrets or sensitive data

Do not include real credentials, private tokens, private network traffic or personal data in a report.

## Responsible Testing

Security testing should be limited to local development environments that you own or are explicitly authorized to test.

Do not use this project to scan, attack, disrupt or profile systems without permission.

## Dependency Security

Dependencies are split between runtime and development requirements:

- `requirements.txt` for application runtime, training and reports
- `requirements-dev.txt` for tests and local quality tooling

Before publishing changes, run:

```bash
python -m pip check
python -m ruff check app src tests
python -m ruff format --check app src tests
python -m pytest -q -ra
```

## Data And Model Artifacts

The repository does not redistribute the UNSW-NB15 dataset or generated model binaries.

Raw datasets, processed local data and `.pkl` model artifacts are intentionally excluded from Git. Contributors must not commit private datasets, generated binary models, tokens or local environment files.
