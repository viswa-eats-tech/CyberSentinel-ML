# Dataset Overview - UNSW-NB15

## Files Used

For the first version of the project, use the pre-split CSV files:

- `UNSW-NB15 dataset/CSV Files/Training and Testing Sets/UNSW_NB15_training-set.csv`
- `UNSW-NB15 dataset/CSV Files/Training and Testing Sets/UNSW_NB15_testing-set.csv`

These files are smaller and already contain the binary target needed for the MVP.

## Dataset Shape

| Split | Rows | Columns |
| --- | ---: | ---: |
| Training | 175,341 | 45 |
| Testing | 82,332 | 45 |

The feature dictionary is available at:

- `UNSW-NB15 dataset/CSV Files/NUSW-NB15_features.csv`

It contains 49 documented fields. The pre-split train/test files contain 45 columns.

## Target

The binary target is:

- `label = 0`: normal traffic
- `label = 1`: attack traffic

`attack_cat` contains the multiclass attack category and should not be used as an input feature for the binary MVP, because it directly describes the target class.

## Class Distribution

### Training Set

| Label | Meaning | Rows | Share |
| ---: | --- | ---: | ---: |
| 0 | Normal | 56,000 | 31.94% |
| 1 | Attack | 119,341 | 68.06% |

### Testing Set

| Label | Meaning | Rows | Share |
| ---: | --- | ---: | ---: |
| 0 | Normal | 37,000 | 44.94% |
| 1 | Attack | 45,332 | 55.06% |

The dataset is imbalanced, especially in the training split. For this reason, accuracy should not be the main metric.

## Attack Categories In Training

| Category | Rows | Share |
| --- | ---: | ---: |
| Normal | 56,000 | 31.94% |
| Generic | 40,000 | 22.81% |
| Exploits | 33,393 | 19.04% |
| Fuzzers | 18,184 | 10.37% |
| DoS | 12,264 | 6.99% |
| Reconnaissance | 10,491 | 5.98% |
| Analysis | 2,000 | 1.14% |
| Backdoor | 1,746 | 1.00% |
| Shellcode | 1,133 | 0.65% |
| Worms | 130 | 0.07% |

## Columns

```text
id, dur, proto, service, state, spkts, dpkts, sbytes, dbytes, rate,
sttl, dttl, sload, dload, sloss, dloss, sinpkt, dinpkt, sjit, djit,
swin, stcpb, dtcpb, dwin, tcprtt, synack, ackdat, smean, dmean,
trans_depth, response_body_len, ct_srv_src, ct_state_ttl, ct_dst_ltm,
ct_src_dport_ltm, ct_dst_sport_ltm, ct_dst_src_ltm, is_ftp_login,
ct_ftp_cmd, ct_flw_http_mthd, ct_src_ltm, ct_srv_dst,
is_sm_ips_ports, attack_cat, label
```

## Feature Groups

Initial type inference found:

- 41 numeric columns
- 4 text/categorical columns: `proto`, `service`, `state`, `attack_cat`

For the binary model:

- Drop `id`
- Drop `attack_cat`
- Use `label` only as target
- Encode `proto`, `service`, and `state`
- Use the remaining numeric columns as numeric inputs

## Data Quality Notes

Initial scan of the training set:

- Missing values: none detected
- Duplicate rows: none detected
- `service` uses `-` as a category, not as a missing value

## First Modeling Decision

The first ML pipeline should use:

- target: `label`
- excluded columns: `id`, `attack_cat`
- categorical features: `proto`, `service`, `state`
- metrics: precision, recall, F1-score, ROC-AUC, confusion matrix

This is enough to start the baseline Logistic Regression and the main Random Forest model.
