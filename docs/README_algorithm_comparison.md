# Algorithm Comparison Features

This project now supports two complementary workflows:

1. Interactive prediction in `predict_nailong_naiwa_ui.py`.
2. Batch algorithm evaluation in `compare_nailong_algorithms.py`.

## Interactive UI

Run:

```powershell
python predict_nailong_naiwa_ui.py --host 127.0.0.1 --port 8770 --cpu
```

Open:

```text
http://127.0.0.1:8770
```

The algorithm menu includes:

- `CNN deep model`
- `Compare all algorithms`
- `Color mean prototype`
- `RGB histogram prototype`
- `Thumbnail kNN`
- `Edge histogram prototype`

The page also shows the train / test / generalization distribution and confidence hints for each prediction.

## Batch Comparison

Run:

```powershell
python compare_nailong_algorithms.py --data nailong_naiwa_splits/test --split-dir nailong_naiwa_splits --models-dir models --out-dir reports --cpu
```

Outputs:

- `reports/algorithm_comparison.md`
- `reports/algorithm_comparison.json`
- `reports/algorithm_predictions.csv`

The report includes accuracy rankings and confusion matrices for each model or algorithm.
