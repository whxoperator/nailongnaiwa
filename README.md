# Nailong / Naiwa Image Classifier

This is a small PyTorch image classification project for distinguishing `nailong` and `naiwa` images. It includes dataset preparation, CNN training, classic image-feature baselines, a local web UI, and algorithm comparison reports.

## Highlights

- Train a lightweight CNN classifier.
- Fine-tune a pretrained torchvision classifier head.
- Preprocess Naiwa watermark regions.
- Build balanced train / test / generalization splits.
- Upload an image in a local web UI and choose the prediction algorithm, including an optional cloud multimodal LLM.
- Compare CNN predictions with classic image algorithms.
- Show image distribution charts in the UI.
- Export accuracy rankings, confusion matrices, and per-image predictions.

## Project Structure

```text
.
|-- nailong_model.py
|-- train_nailong_naiwa.py
|-- train_pretrained_classifier.py
|-- predict_nailong_naiwa_ui.py
|-- multimodal_llm.py
|-- compare_nailong_algorithms.py
|-- visualize_dataset_distribution.py
|-- preprocess_naiwa_watermarks.py
|-- models/
|-- nailong_naiwa_10_demo/
|-- nailong_naiwa_balanced_experiment/
|-- nailong_naiwa_splits/
|-- reports/
|-- docs/
|-- tools/
`-- seeds/
```

## Install

```powershell
pip install -r requirements.txt
```

## Train

```powershell
python train_nailong_naiwa.py --cpu --epochs 12 --repeats 3 --batch-size 16 --image-size 128 --print-every 3 --out models/nailong_naiwa_balanced_cnn.pt
```

The training script rebuilds the balanced experiment dataset, creates splits, trains the CNN, and saves a checkpoint under `models/`.

## Fine-tune a Pretrained Model

```powershell
python train_pretrained_classifier.py --cpu --arch resnet18 --epochs 10 --batch-size 16 --image-size 160 --freeze-backbone --out models/nailong_naiwa_resnet18_head.pt
```

This loads an ImageNet-pretrained backbone, replaces the final classification head with a two-class Nailong/Naiwa head, and fine-tunes it on `nailong_naiwa_splits/train`. The saved `.pt` file can be evaluated and compared with the existing CNN models:

```powershell
python compare_nailong_algorithms.py --data nailong_naiwa_splits/test --split-dir nailong_naiwa_splits --models-dir models --out-dir reports --cpu
```

For a stricter comparison against training from scratch with the same architecture, add `--random-init`.

## Run the UI

```powershell
python predict_nailong_naiwa_ui.py --host 127.0.0.1 --port 8770 --cpu
```

Open:

```text
http://127.0.0.1:8770
```

The UI supports:

- `CNN deep model`
- `Cloud multimodal LLM`
- `Compare all algorithms`
- `Color mean prototype`
- `RGB histogram prototype`
- `Thumbnail kNN`
- `Edge histogram prototype`

It also displays train / test / generalization image distribution and confidence hints.

To enable the cloud multimodal LLM option, set an OpenAI-compatible API key before starting the UI:

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_MODEL="gpt-4o-mini"
python predict_nailong_naiwa_ui.py --host 127.0.0.1 --port 8770 --cpu
```

For another OpenAI-compatible provider, also set `OPENAI_BASE_URL`, for example `https://example.com/v1`. Without `OPENAI_API_KEY`, the CNN and classic algorithms still work, and the LLM option will show a configuration error.

## Compare Algorithms

```powershell
python compare_nailong_algorithms.py --data nailong_naiwa_splits/test --split-dir nailong_naiwa_splits --models-dir models --out-dir reports --cpu
```

Generated outputs:

- `reports/algorithm_comparison.md`
- `reports/algorithm_comparison.json`
- `reports/algorithm_predictions.csv`

Current test-set ranking:

| Algorithm | Accuracy |
| --- | ---: |
| CNN balanced model | 90.24% |
| Thumbnail kNN | 87.80% |
| RGB histogram prototype | 85.37% |
| Color mean prototype | 78.05% |
| Edge histogram prototype | 58.54% |
| ResNet18 pretrained head | 48.78% |

## Dataset Distribution

```powershell
python visualize_dataset_distribution.py --split-dir nailong_naiwa_splits
```

Example split:

```text
train:          nailong=60, naiwa=65
test:           nailong=20, naiwa=21
generalization: nailong=20, naiwa=21
```

## Notes

This is an educational experiment, not a production classifier. The dataset is small, the labels are limited to two classes, and predictions on unrelated images should be manually reviewed.
