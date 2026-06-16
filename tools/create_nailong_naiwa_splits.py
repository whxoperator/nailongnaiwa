from __future__ import annotations

import argparse
import csv
import random
import shutil
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
DEFAULT_CLASSES = ["nailong", "naiwa"]


def image_files(class_dir: Path) -> list[Path]:
    return sorted(
        path for path in class_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def split_class(paths: list[Path], seed: int) -> dict[str, list[Path]]:
    rng = random.Random(seed)
    paths = paths[:]
    rng.shuffle(paths)

    if len(paths) < 3:
        raise ValueError("Each class needs at least 3 images for train/test/generalization.")

    test_count = max(1, round(len(paths) * 0.2))
    generalization_count = max(1, round(len(paths) * 0.2))
    train_count = len(paths) - test_count - generalization_count

    if train_count < 1:
        train_count = 1
        if generalization_count > 1:
            generalization_count -= 1
        else:
            test_count -= 1

    train = paths[:train_count]
    test = paths[train_count:train_count + test_count]
    generalization = paths[train_count + test_count:]

    return {
        "train": train,
        "test": test,
        "generalization": generalization,
    }


def copy_split(
    split_name: str,
    class_name: str,
    paths: list[Path],
    out_dir: Path,
    rows: list[dict[str, str]],
) -> None:
    target_dir = out_dir / split_name / class_name
    target_dir.mkdir(parents=True, exist_ok=True)

    for source in paths:
        target = target_dir / source.name
        shutil.copy2(source, target)
        rows.append(
            {
                "split": split_name,
                "label": class_name,
                "filename": str(target.relative_to(out_dir)),
                "source": str(source),
            }
        )


def write_manifest(out_dir: Path, rows: list[dict[str, str]]) -> None:
    manifest = out_dir / "split_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "label", "filename", "source"])
        writer.writeheader()
        writer.writerows(rows)


def create_splits(args: argparse.Namespace) -> None:
    source_dir = Path(args.source)
    out_dir = Path(args.out)

    if out_dir.exists():
        raise SystemExit(f"Output already exists: {out_dir}")

    rows: list[dict[str, str]] = []
    summary: dict[str, dict[str, int]] = {
        "train": {},
        "test": {},
        "generalization": {},
    }

    for index, class_name in enumerate(args.classes):
        paths = image_files(source_dir / class_name)
        split = split_class(paths, seed=args.seed + index)

        for split_name, split_paths in split.items():
            copy_split(split_name, class_name, split_paths, out_dir, rows)
            summary[split_name][class_name] = len(split_paths)

    write_manifest(out_dir, rows)

    print(f"Created: {out_dir}")
    for split_name in ["train", "test", "generalization"]:
        counts = ", ".join(
            f"{class_name}={summary[split_name].get(class_name, 0)}"
            for class_name in args.classes
        )
        print(f"{split_name}: {counts}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create train/test/generalization splits.")
    parser.add_argument("--source", default="nailong_naiwa_10_demo")
    parser.add_argument("--out", default="nailong_naiwa_splits")
    parser.add_argument("--classes", nargs="+", default=DEFAULT_CLASSES)
    parser.add_argument("--seed", type=int, default=11)
    return parser


def main() -> int:
    create_splits(build_parser().parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
