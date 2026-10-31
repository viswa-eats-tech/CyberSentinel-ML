# Training Results

Generated at: `2026-06-17T07:49:02.589247+00:00`

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
| Accuracy | 0.8500 |
| Precision attack | 0.8315 |
| Recall attack | 0.9124 |
| F1 attack | 0.8701 |
| ROC-AUC | 0.9559 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 28620 |
| False positive | 8380 |
| False negative | 3972 |
| True positive | 41360 |

## Random Forest

| Metric | Value |
| --- | ---: |
| Threshold | 0.5500 |
| Accuracy | 0.8818 |
| Precision attack | 0.8329 |
| Recall attack | 0.9824 |
| F1 attack | 0.9015 |
| ROC-AUC | 0.9796 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 28066 |
| False positive | 8934 |
| False negative | 796 |
| True positive | 44536 |
