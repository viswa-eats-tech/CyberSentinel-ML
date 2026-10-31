# Contributing

Thank you for considering a contribution.

This project is maintained as a portfolio-grade machine learning engineering project. Contributions should preserve reproducibility, transparency and a clear separation between exploratory work and production-like code.

## Development Setup

Use Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

The project expects the UNSW-NB15 training and testing CSV files to be available locally. Dataset files are not committed to Git.

If your dataset is not in the default location, set:

```bash
export UNSW_NB15_DATA_DIR="/path/to/Training and Testing Sets"
```

## Before Opening A Pull Request

Run the same checks used by CI:

```bash
python -m pip check
python -m compileall app src tests
python -m ruff check app src tests
python -m ruff format --check app src tests
python -m pytest -q -ra
```

For model-related changes, also run a smoke training pass:

```bash
python -m src.train --model both --sample-size 5000 --no-save --reports-dir /tmp/netshield-smoke-reports
```

## Contribution Guidelines

- Keep reusable logic in `src/` or `app/`, not only in notebooks.
- Keep notebooks lightweight and exploratory.
- Do not commit raw datasets, processed datasets or generated `.pkl` model binaries.
- Do not commit tokens, credentials, local `.env` files or private traffic samples.
- Update README and reports when changing model behavior, metrics, thresholds or API contracts.
- Add or update tests for changes that affect preprocessing, training, inference, API responses or repository contracts.
- Keep pull requests focused. Avoid unrelated refactors in the same change.
- Prefer clear, reproducible commands over manual-only workflows.

## Dataset Citation

Any public or academic use of this project must also respect the UNSW-NB15 citation requirements described in the README.

Do not redistribute the UNSW-NB15 dataset through this repository.

## Security Issues

Do not report security vulnerabilities through public issues.

Follow the process in `SECURITY.md`.

## Pull Request Checklist

Before submitting, confirm:

- tests pass locally
- Ruff linting and formatting pass
- no generated model binaries are included
- no dataset files are included
- no secrets are included
- documentation is updated where needed
- dataset citations remain present
