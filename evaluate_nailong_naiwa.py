from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torchvision.datasets import ImageFolder

from nailong_model import load_checkpoint, predict_image


def evaluate(args: argparse.Namespace) -> None:
    data_dir = Path(args.data)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model, classes, image_size, _metadata = load_checkpoint(args.model, device)

    dataset = ImageFolder(data_dir)
    total = 0
    correct = 0

    print(f"Evaluating: {data_dir}")
    print(f"Model classes: {classes}")

    for path, expected_idx in dataset.samples:
        expected = dataset.classes[expected_idx]
        predicted, scores = predict_image(model, classes, path, device, image_size=image_size)
        total += 1
        correct += int(predicted == expected)
        score_text = ", ".join(f"{name}={score:.3f}" for name, score in scores.items())
        print(f"{Path(path).name}: expected={expected}, predicted={predicted}, {score_text}")

    accuracy = correct / max(total, 1)
    print(f"accuracy={accuracy:.3f} ({correct}/{total})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the Nailong/Naiwa classifier.")
    parser.add_argument("--model", default="models/nailong_naiwa_cnn.pt")
    parser.add_argument("--data", required=True)
    parser.add_argument("--cpu", action="store_true")
    return parser


def main() -> int:
    evaluate(build_parser().parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
