# Training Results

Generated at: `2026-10-31T11:25:56.570722+00:00`

## Dataset

- Training rows: `175341`
- Testing rows: `82332`
- Target: `label`
- Primary decision threshold: `0.55`
- Model thresholds: `Logistic Regression=0.55, Random Forest=0.55`
- Excluded columns: `id`, `attack_cat`
- Numeric features: `39`
- Categorical features: `proto, service, state`

## Logistic Regression

| Metric | Value |
| --- | ---: |
| Threshold | 0.5500 |
| Accuracy | 0.8499 |
| Precision attack | 0.8317 |
| Recall attack | 0.9120 |
| F1 attack | 0.8700 |
| ROC-AUC | 0.9560 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 28632 |
| False positive | 8368 |
| False negative | 3988 |
| True positive | 41344 |

## Random Forest

| Metric | Value |
| --- | ---: |
| Threshold | 0.5500 |
| Accuracy | 0.8814 |
| Precision attack | 0.8324 |
| Recall attack | 0.9824 |
| F1 attack | 0.9012 |
| ROC-AUC | 0.9800 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 28035 |
| False positive | 8965 |
| False negative | 797 |
| True positive | 44535 |
