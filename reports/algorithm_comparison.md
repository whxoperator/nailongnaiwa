# Algorithm Comparison Report

Evaluation set: `nailong_naiwa_splits\test`

## Accuracy

| Algorithm | Correct | Total | Accuracy |
| --- | ---: | ---: | ---: |
| `cnn:nailong_naiwa_balanced_cnn.pt` | 37 | 41 | 90.24% |
| `thumbnail_knn` | 36 | 41 | 87.80% |
| `color_hist` | 35 | 41 | 85.37% |
| `color_mean` | 32 | 41 | 78.05% |
| `edge_hist` | 24 | 41 | 58.54% |
| `cnn:nailong_naiwa_cnn.pt` | 19 | 41 | 46.34% |
| `cnn:nailong_naiwa_split_cnn.pt` | 18 | 41 | 43.90% |

## Confusion Matrix: `cnn:nailong_naiwa_balanced_cnn.pt`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 18 | 2 |
| naiwa | 2 | 19 |

## Confusion Matrix: `thumbnail_knn`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 17 | 3 |
| naiwa | 2 | 19 |

## Confusion Matrix: `color_hist`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 19 | 1 |
| naiwa | 5 | 16 |

## Confusion Matrix: `color_mean`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 18 | 2 |
| naiwa | 7 | 14 |

## Confusion Matrix: `edge_hist`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 9 | 11 |
| naiwa | 6 | 15 |

## Confusion Matrix: `cnn:nailong_naiwa_cnn.pt`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 12 | 8 |
| naiwa | 14 | 7 |

## Confusion Matrix: `cnn:nailong_naiwa_split_cnn.pt`

| expected \ predicted | nailong | naiwa |
| --- | ---: | ---: |
| nailong | 11 | 9 |
| naiwa | 14 | 7 |
