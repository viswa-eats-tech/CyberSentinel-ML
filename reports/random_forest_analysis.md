# Random Forest Analysis

Generated at: `2026-06-17T07:59:51.465499+00:00`

## Operational Threshold

- Current operational threshold: `0.55`

## Threshold Summary

The operational threshold comes from training metadata. The test-set alternatives below are diagnostic, not the rule used to choose deployment behavior.

| Selection | Threshold | Precision attack | Recall attack | F1 attack | False positives | False negatives |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current operational | 0.55 | 0.8329 | 0.9824 | 0.9015 | 8934 | 796 |
| Test-set best F1 | 0.80 | 0.9276 | 0.9251 | 0.9263 | 3272 | 3397 |
| Test-set recall >= 0.98 | 0.55 | 0.8329 | 0.9824 | 0.9015 | 8934 | 796 |

## Error Profile At Operational Threshold 0.55

| Error type | Count | Mean attack probability | P90 attack probability |
| --- | ---: | ---: | ---: |
| False positives | 8934 | 0.7458 | 0.9242 |
| False negatives | 796 | 0.4210 | 0.5333 |

## Top Grouped Features

| Rank | Feature group | Importance | Share |
| ---: | --- | ---: | ---: |
| 1 | `sttl` | 0.083391 | 8.34% |
| 2 | `ct_state_ttl` | 0.057986 | 5.80% |
| 3 | `sload` | 0.052782 | 5.28% |
| 4 | `rate` | 0.052006 | 5.20% |
| 5 | `dload` | 0.050465 | 5.05% |
| 6 | `state` | 0.040475 | 4.05% |
| 7 | `dpkts` | 0.038386 | 3.84% |
| 8 | `sbytes` | 0.037711 | 3.77% |
| 9 | `dttl` | 0.034866 | 3.49% |
| 10 | `smean` | 0.034489 | 3.45% |
| 11 | `ct_srv_dst` | 0.034058 | 3.41% |
| 12 | `dbytes` | 0.032904 | 3.29% |
| 13 | `ct_dst_src_ltm` | 0.032419 | 3.24% |
| 14 | `dur` | 0.030462 | 3.05% |
| 15 | `synack` | 0.030230 | 3.02% |
| 16 | `ct_srv_src` | 0.030070 | 3.01% |
| 17 | `ackdat` | 0.029957 | 3.00% |
| 18 | `tcprtt` | 0.029823 | 2.98% |
| 19 | `sinpkt` | 0.025483 | 2.55% |
| 20 | `dinpkt` | 0.021919 | 2.19% |

## Top Transformed Features

| Rank | Feature | Importance |
| ---: | --- | ---: |
| 1 | `sttl` | 0.083391 |
| 2 | `ct_state_ttl` | 0.057986 |
| 3 | `sload` | 0.052782 |
| 4 | `rate` | 0.052006 |
| 5 | `dload` | 0.050465 |
| 6 | `dpkts` | 0.038386 |
| 7 | `sbytes` | 0.037711 |
| 8 | `dttl` | 0.034866 |
| 9 | `smean` | 0.034489 |
| 10 | `ct_srv_dst` | 0.034058 |
| 11 | `dbytes` | 0.032904 |
| 12 | `ct_dst_src_ltm` | 0.032419 |
| 13 | `dur` | 0.030462 |
| 14 | `synack` | 0.030230 |
| 15 | `ct_srv_src` | 0.030070 |
| 16 | `ackdat` | 0.029957 |
| 17 | `tcprtt` | 0.029823 |
| 18 | `state_INT` | 0.026707 |
| 19 | `sinpkt` | 0.025483 |
| 20 | `dinpkt` | 0.021919 |

## Interpretation

- Threshold tuning controls the trade-off between missed attacks and false alarms.
- The operational threshold is stored in `models/metadata.json` and used by the API.
- Grouped importance combines one-hot encoded categorical levels back into their original feature names.
- Test-set threshold alternatives are diagnostic; deployment thresholds should be chosen from operating requirements and validated separately.
