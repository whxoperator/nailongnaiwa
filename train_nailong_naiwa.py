from __future__ import annotations

import argparse
import csv
import random
import shutil
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from nailong_model import ClassAwareImageFolder, IMAGE_SIZE, SmallImageCNN, save_checkpoint


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
SPLITS = ("train", "test", "generalization")


class RepeatDataset(Dataset):
    def __init__(self, dataset: Dataset, repeats: int) -> None:
        self.dataset = dataset
        self.repeats = repeats

    def __len__(self) -> int:
        return len(self.dataset) * self.repeats

    def __getitem__(self, index: int):
        return self.dataset[index % len(self.dataset)]


def image_files(path: Path) -> list[Path]:
    return sorted(
        item for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES
    )


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_unique(source: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if not target.exists():
        shutil.copy2(source, target)
        return target

    stem = source.stem
    suffix = source.suffix
    counter = 1
    while True:
        candidate = target_dir / f"{stem}_{counter:03d}{suffix}"
        if not candidate.exists():
            shutil.copy2(source, candidate)
            return candidate
        counter += 1


def split_paths(paths: list[Path], rng: random.Random) -> dict[str, list[Path]]:
    paths = paths[:]
    rng.shuffle(paths)
    test_count = max(1, round(len(paths) * 0.20))
    generalization_count = max(1, round(len(paths) * 0.20))
    train_count = len(paths) - test_count - generalization_count
    if train_count < 1:
        train_count = 1
        generalization_count = max(1, generalization_count - 1)
    return {
        "train": paths[:train_count],
        "test": paths[train_count:train_count + test_count],
        "generalization": paths[train_count + test_count:],
    }


def prepare_balanced_dataset(args: argparse.Namespace) -> Path:
    rng = random.Random(args.seed)
    source_root = Path(args.source)
    nailong_source = source_root / "nailong"
    naiwa_source = Path(args.naiwa_source)
    balanced_dir = Path(args.balanced_out)
    split_dir = Path(args.split_out)

    nailong = image_files(nailong_source)
    naiwa = image_files(naiwa_source)
    if len(nailong) < args.nailong_count:
        raise SystemExit(f"nailong only has {len(nailong)} images, need {args.nailong_count}.")
    if len(naiwa) < 3:
        raise SystemExit(f"naiwa needs at least 3 images, found {len(naiwa)}.")

    reset_dir(balanced_dir)
    selected_nailong = sorted(rng.sample(nailong, args.nailong_count), key=lambda p: p.name)
    for source in selected_nailong:
        copy_unique(source, balanced_dir / "nailong")
    for source in naiwa:
        copy_unique(source, balanced_dir / "naiwa")

    reset_dir(split_dir)
    rows: list[dict[str, str]] = []
    for class_index, class_name in enumerate(("nailong", "naiwa")):
        class_paths = image_files(balanced_dir / class_name)
        split = split_paths(class_paths, random.Random(args.seed + class_index + 1000))
        for split_name, paths in split.items():
            target_dir = split_dir / split_name / class_name
            target_dir.mkdir(parents=True, exist_ok=True)
            for source in paths:
                target = copy_unique(source, target_dir)
                rows.append(
                    {
                        "split": split_name,
                        "label": class_name,
                        "filename": str(target.relative_to(split_dir)),
                        "source": str(source),
                    }
                )

    with (split_dir / "split_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["split", "label", "filename", "source"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Balanced dataset: {balanced_dir}")
    print(f"  nailong={len(image_files(balanced_dir / 'nailong'))}")
    print(f"  naiwa={len(image_files(balanced_dir / 'naiwa'))}")
    print(f"Split dataset: {split_dir}")
    for split_name in SPLITS:
        counts = []
        for class_name in ("nailong", "naiwa"):
            counts.append(f"{class_name}={len(image_files(split_dir / split_name / class_name))}")
        print(f"  {split_name}: {', '.join(counts)}")
    return split_dir


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    correct = 0
    seen = 0
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)
            logits = model(images)
            correct += int((logits.argmax(dim=1) == labels).sum().item())
            seen += images.size(0)
    return correct / max(seen, 1)


def train(args: argparse.Namespace) -> Path:
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    split_dir = prepare_balanced_dataset(args)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    train_dataset = ClassAwareImageFolder(
        split_dir / "train",
        image_size=args.image_size,
        augment=True,
        corner_augment_classes={"nailong"},
    )
    test_dataset = ClassAwareImageFolder(split_dir / "test", image_size=args.image_size, augment=False)
    generalization_dataset = ClassAwareImageFolder(split_dir / "generalization", image_size=args.image_size, augment=False)
    dataset = RepeatDataset(train_dataset, repeats=args.repeats)

    train_loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)
    generalization_loader = DataLoader(generalization_dataset, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = SmallImageCNN(num_classes=len(train_dataset.classes)).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.04)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    print(f"Classes: {train_dataset.class_to_idx}")
    print(f"Device: {device}")
    print("Augmentations: random crop/color/rotation + nailong lower-right random blur/occlusion")

    best_test_acc = -1.0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        correct = 0
        seen = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            total_loss += float(loss.item()) * images.size(0)
            correct += int((logits.argmax(dim=1) == labels).sum().item())
            seen += images.size(0)

        train_acc = correct / max(seen, 1)
        avg_loss = total_loss / max(seen, 1)
        test_acc = evaluate(model, test_loader, device)
        if test_acc > best_test_acc:
            best_test_acc = test_acc
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

        if epoch == 1 or epoch % args.print_every == 0 or epoch == args.epochs:
            gen_acc = evaluate(model, generalization_loader, device)
            print(
                f"epoch {epoch:03d}/{args.epochs} "
                f"loss={avg_loss:.4f} train_acc={train_acc:.3f} "
                f"test_acc={test_acc:.3f} gen_acc={gen_acc:.3f}"
            )

    if best_state is not None:
        model.load_state_dict(best_state)

    metadata = {
        "source": str(split_dir),
        "nailong_count": args.nailong_count,
        "naiwa_source": args.naiwa_source,
        "best_test_acc": best_test_acc,
    }
    save_checkpoint(out_path, model, train_dataset.class_to_idx, image_size=args.image_size, metadata=metadata)
    print(f"Saved model: {out_path}")
    print(f"Best test accuracy: {best_test_acc:.3f}")
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a balanced Nailong/Naiwa image classifier.")
    parser.add_argument("--source", default="nailong_naiwa_10_demo", help="Folder containing nailong images")
    parser.add_argument("--naiwa-source", default="nailong_naiwa_10_demo/naiwa_preprocessed")
    parser.add_argument("--balanced-out", default="nailong_naiwa_balanced_experiment")
    parser.add_argument("--split-out", default="nailong_naiwa_splits")
    parser.add_argument("--nailong-count", type=int, default=100)
    parser.add_argument("--out", default="models/nailong_naiwa_balanced_cnn.pt")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--lr", type=float, default=7e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--repeats", type=int, default=12)
    parser.add_argument("--image-size", type=int, default=IMAGE_SIZE)
    parser.add_argument("--print-every", type=int, default=5)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--cpu", action="store_true", help="Force CPU training")
    return parser


def main() -> int:
    train(build_parser().parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
