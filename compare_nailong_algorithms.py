from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch

from nailong_algorithms import IMAGE_SUFFIXES, TRADITIONAL_ALGORITHMS, predict_traditional
from nailong_model import load_checkpoint, predict_image


def iter_labeled_images(data_dir: Path):
    for class_dir in sorted(item for item in data_dir.iterdir() if item.is_dir()):
        for path in sorted(class_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                yield path, class_dir.name


def update_confusion(confusion: dict[str, dict[str, int]], expected: str, predicted: str) -> None:
    confusion.setdefault(expected, {})
    confusion[expected][predicted] = confusion[expected].get(predicted, 0) + 1


def accuracy_from_confusion(confusion: dict[str, dict[str, int]]) -> tuple[int, int, float]:
    total = 0
    correct = 0
    for expected, row in confusion.items():
        for predicted, count in row.items():
            total += count
            if expected == predicted:
                correct += count
    return correct, total, correct / max(total, 1)


def evaluate_cnn(model_path: Path, data_dir: Path, device: torch.device) -> dict[str, object]:
    model, classes, image_size, metadata = load_checkpoint(model_path, device)
    confusion: dict[str, dict[str, int]] = {}
    rows = []
    for path, expected in iter_labeled_images(data_dir):
        predicted, scores = predict_image(model, classes, path, device, image_size=image_size)
        update_confusion(confusion, expected, predicted)
        rows.append(
            {
                "algorithm": f"cnn:{model_path.name}",
                "image": str(path),
                "expected": expected,
                "predicted": predicted,
                "confidence": max(scores.values()),
            }
        )
    correct, total, accuracy = accuracy_from_confusion(confusion)
    return {
        "name": f"cnn:{model_path.name}",
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "confusion": confusion,
        "metadata": metadata,
        "rows": rows,
    }


def evaluate_traditional(algorithm: str, data_dir: Path, split_dir: Path) -> dict[str, object]:
    confusion: dict[str, dict[str, int]] = {}
    rows = []
    for path, expected in iter_labeled_images(data_dir):
        predicted, scores = predict_traditional(algorithm, path, split_dir)
        update_confusion(confusion, expected, predicted)
        rows.append(
            {
                "algorithm": algorithm,
                "image": str(path),
                "expected": expected,
                "predicted": predicted,
                "confidence": max(scores.values()),
            }
        )
    correct, total, accuracy = accuracy_from_confusion(confusion)
    return {
        "name": algorithm,
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "confusion": confusion,
        "rows": rows,
    }


def render_markdown(results: list[dict[str, object]], data_dir: Path) -> str:
    lines = [
        "# Algorithm Comparison Report",
        "",
        f"Evaluation set: `{data_dir}`",
        "",
        "## Accuracy",
        "",
        "| Algorithm | Correct | Total | Accuracy |",
        "| --- | ---: | ---: | ---: |",
    ]
    for result in sorted(results, key=lambda item: float(item["accuracy"]), reverse=True):
        lines.append(
            f"| `{result['name']}` | {result['correct']} | {result['total']} | "
            f"{float(result['accuracy']) * 100:.2f}% |"
        )

    labels = sorted({label for result in results for label in result["confusion"]})  # type: ignore[index]
    for result in results:
        lines.extend(["", f"## Confusion Matrix: `{result['name']}`", ""])
        header = "| expected \\ predicted | " + " | ".join(labels) + " |"
        separator = "| --- | " + " | ".join("---:" for _ in labels) + " |"
        lines.extend([header, separator])
        confusion = result["confusion"]  # type: ignore[assignment]
        for expected in labels:
            row = confusion.get(expected, {})  # type: ignore[union-attr]
            values = [str(row.get(predicted, 0)) for predicted in labels]
            lines.append(f"| {expected} | " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def write_outputs(results: list[dict[str, object]], args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = [
        {
            "name": result["name"],
            "correct": result["correct"],
            "total": result["total"],
            "accuracy": result["accuracy"],
            "confusion": result["confusion"],
        }
        for result in results
    ]
    (out_dir / "algorithm_comparison.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "algorithm_comparison.md").write_text(
        render_markdown(results, Path(args.data)),
        encoding="utf-8",
    )

    with (out_dir / "algorithm_predictions.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["algorithm", "image", "expected", "predicted", "confidence"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerows(result["rows"])  # type: ignore[arg-type]


def evaluate(args: argparse.Namespace) -> list[dict[str, object]]:
    data_dir = Path(args.data)
    split_dir = Path(args.split_dir)
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    results: list[dict[str, object]] = []

    if not args.traditional_only:
        for model_path in sorted(Path(args.models_dir).glob("*.pt")):
            results.append(evaluate_cnn(model_path, data_dir, device))

    for algorithm in TRADITIONAL_ALGORITHMS:
        results.append(evaluate_traditional(algorithm, data_dir, split_dir))

    return sorted(results, key=lambda item: float(item["accuracy"]), reverse=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare CNN and traditional Nailong/Naiwa classifiers.")
    parser.add_argument("--data", default="nailong_naiwa_splits/test")
    parser.add_argument("--split-dir", default="nailong_naiwa_splits")
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--out-dir", default="reports")
    parser.add_argument("--traditional-only", action="store_true")
    parser.add_argument("--cpu", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    results = evaluate(args)
    write_outputs(results, args)
    for result in results:
        print(
            f"{result['name']}: {result['correct']}/{result['total']} "
            f"accuracy={float(result['accuracy']) * 100:.2f}%"
        )
    print(f"Wrote reports to: {Path(args.out_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
