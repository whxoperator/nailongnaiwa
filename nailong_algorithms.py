from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
TRADITIONAL_ALGORITHMS = {
    "color_mean": "Color mean prototype",
    "color_hist": "RGB histogram prototype",
    "thumbnail_knn": "Thumbnail kNN",
    "edge_hist": "Edge histogram prototype",
}
ALL_ALGORITHMS = {"cnn": "CNN deep model", **TRADITIONAL_ALGORITHMS}


def image_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(
        item
        for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES
    )


def dataset_distribution(split_dir: str | Path) -> dict[str, dict[str, int]]:
    root = Path(split_dir)
    result: dict[str, dict[str, int]] = {}
    for split_name in ("train", "test", "generalization"):
        split_path = root / split_name
        labels: dict[str, int] = {}
        if split_path.exists():
            for class_dir in sorted(item for item in split_path.iterdir() if item.is_dir()):
                labels[class_dir.name] = len(image_files(class_dir))
        result[split_name] = labels
    return result


def _open_rgb(path: str | Path, size: int | None = None) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if size:
        image = image.resize((size, size))
    return image


def _normalize(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        return values
    return [value / total for value in values]


def _color_mean(path: str | Path) -> list[float]:
    image = _open_rgb(path, 64)
    stat = ImageStat.Stat(image)
    return [value / 255.0 for value in stat.mean]


def _color_hist(path: str | Path, bins: int = 8) -> list[float]:
    image = _open_rgb(path, 96)
    hist = image.histogram()
    chunk = 256 // bins
    features: list[float] = []
    for channel in range(3):
        offset = channel * 256
        for index in range(bins):
            start = offset + index * chunk
            features.append(float(sum(hist[start:start + chunk])))
    return _normalize(features)


def _thumbnail(path: str | Path, size: int = 16) -> list[float]:
    image = Image.open(path).convert("L").resize((size, size))
    return [pixel / 255.0 for pixel in image.getdata()]


def _edge_hist(path: str | Path, bins: int = 12) -> list[float]:
    image = Image.open(path).convert("L").resize((128, 128)).filter(ImageFilter.FIND_EDGES)
    hist = image.histogram()
    chunk = 256 // bins
    values = [float(sum(hist[index * chunk:(index + 1) * chunk])) for index in range(bins)]
    return _normalize(values)


def _distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def _prototype(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    width = len(vectors[0])
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(width)]


@lru_cache(maxsize=16)
def _training_index(split_dir: str) -> dict[str, dict[str, object]]:
    train_root = Path(split_dir) / "train"
    labels = [item.name for item in sorted(train_root.iterdir()) if item.is_dir()] if train_root.exists() else []
    index: dict[str, dict[str, object]] = {}

    for algorithm in TRADITIONAL_ALGORITHMS:
        entries: dict[str, object] = {}
        for label in labels:
            paths = image_files(train_root / label)
            if algorithm == "color_mean":
                vectors = [_color_mean(path) for path in paths]
                entries[label] = _prototype(vectors)
            elif algorithm == "color_hist":
                vectors = [_color_hist(path) for path in paths]
                entries[label] = _prototype(vectors)
            elif algorithm == "edge_hist":
                vectors = [_edge_hist(path) for path in paths]
                entries[label] = _prototype(vectors)
            elif algorithm == "thumbnail_knn":
                entries[label] = [(path, _thumbnail(path)) for path in paths]
        index[algorithm] = entries
    return index


def _softmax_from_distances(distances: dict[str, float]) -> dict[str, float]:
    if not distances:
        return {}
    weights = {label: math.exp(-distance * 6.0) for label, distance in distances.items()}
    total = sum(weights.values()) or 1.0
    return {label: value / total for label, value in weights.items()}


def predict_traditional(
    algorithm: str,
    image_path: str | Path,
    split_dir: str | Path,
    k: int = 7,
) -> tuple[str, dict[str, float]]:
    if algorithm not in TRADITIONAL_ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    index = _training_index(str(Path(split_dir).resolve()))
    entries = index.get(algorithm, {})
    if not entries:
        raise ValueError("No training images were found for traditional algorithms.")

    if algorithm == "thumbnail_knn":
        query = _thumbnail(image_path)
        neighbors: list[tuple[float, str]] = []
        for label, samples in entries.items():
            for _path, vector in samples:  # type: ignore[union-attr]
                neighbors.append((_distance(query, vector), label))
        neighbors.sort(key=lambda item: item[0])
        votes = {label: 0.0 for label in entries}
        for distance, label in neighbors[:max(1, k)]:
            votes[label] += 1.0 / (distance + 1e-6)
        total = sum(votes.values()) or 1.0
        scores = {label: vote / total for label, vote in votes.items()}
    else:
        if algorithm == "color_mean":
            query = _color_mean(image_path)
        elif algorithm == "color_hist":
            query = _color_hist(image_path)
        else:
            query = _edge_hist(image_path)
        distances = {
            label: _distance(query, prototype)  # type: ignore[arg-type]
            for label, prototype in entries.items()
            if prototype
        }
        scores = _softmax_from_distances(distances)

    predicted = max(scores, key=scores.get)
    return predicted, scores


def confidence_level(scores: dict[str, float]) -> str:
    if not scores:
        return "unknown"
    top = max(scores.values())
    if top >= 0.78:
        return "high"
    if top >= 0.62:
        return "medium"
    return "low"


def explain_confidence(scores: dict[str, float]) -> str:
    level = confidence_level(scores)
    if level == "high":
        return "High confidence: the leading class is clearly ahead."
    if level == "medium":
        return "Medium confidence: the result is usable, but worth checking."
    if level == "low":
        return "Low confidence: the classes are close, so manual review is recommended."
    return "No confidence score is available."
