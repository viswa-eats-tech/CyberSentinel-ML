# Training Results

Generated at: `2026-11-01T14:09:05.887315+00:00`

## Dataset

- Training rows: `175341`
- Testing rows: `82332`
- Target: `label`
- Primary decision threshold: `0.55`
- Model thresholds: `Random Forest=0.55, Bagging Classifier=0.55, Gradient Boosting=0.55`
- Excluded columns: `id`, `attack_cat`
- Numeric features: `39`
- Categorical features: `proto, service, state`

## Random Forest

| Metric | Value |
| --- | ---: |
| Threshold | 0.5500 |
| Accuracy | 0.8815 |
| Precision attack | 0.8328 |
| Recall attack | 0.9819 |
| F1 attack | 0.9012 |
| ROC-AUC | 0.9798 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 28066 |
| False positive | 8934 |
| False negative | 822 |
| True positive | 44510 |

## Bagging Classifier

| Metric | Value |
| --- | ---: |
| Threshold | 0.5500 |
| Accuracy | 0.9080 |
| Precision attack | 0.8751 |
| Recall attack | 0.9716 |
| F1 attack | 0.9209 |
| ROC-AUC | 0.9825 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 30715 |
| False positive | 6285 |
| False negative | 1286 |
| True positive | 44046 |

## Gradient Boosting

| Metric | Value |
| --- | ---: |
| Threshold | 0.5500 |
| Accuracy | 0.9092 |
| Precision attack | 0.9043 |
| Recall attack | 0.9339 |
| F1 attack | 0.9189 |
| ROC-AUC | 0.9775 |

| Confusion Matrix | Value |
| --- | ---: |
| True negative | 32521 |
| False positive | 4479 |
| False negative | 2995 |
| True positive | 42337 |
