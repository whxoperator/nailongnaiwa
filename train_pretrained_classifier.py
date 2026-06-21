from __future__ import annotations

import argparse
import os
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from nailong_model import (
    ClassAwareImageFolder,
    IMAGE_SIZE,
    build_torchvision_classifier,
    freeze_backbone,
    save_checkpoint,
)


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


def resolve_image_size(args: argparse.Namespace) -> int:
    if args.image_size is not None:
        return args.image_size
    if args.arch == "vit_b_16":
        return 224
    return IMAGE_SIZE


def train(args: argparse.Namespace) -> Path:
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    image_size = resolve_image_size(args)
    if args.arch == "vit_b_16" and image_size != 224:
        raise SystemExit("vit_b_16 expects --image-size 224 because torchvision ViT uses fixed position embeddings.")

    split_dir = Path(args.split_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch_cache_dir = Path(args.torch_cache)
    torch_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(torch_cache_dir.resolve()))

    train_dataset = ClassAwareImageFolder(
        split_dir / "train",
        image_size=image_size,
        augment=True,
        corner_augment_classes={"nailong"},
    )
    test_dataset = ClassAwareImageFolder(split_dir / "test", image_size=image_size, augment=False)
    generalization_dataset = ClassAwareImageFolder(
        split_dir / "generalization",
        image_size=image_size,
        augment=False,
    )

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)
    generalization_loader = DataLoader(generalization_dataset, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    model = build_torchvision_classifier(
        args.arch,
        num_classes=len(train_dataset.classes),
        pretrained=not args.random_init,
    ).to(device)
    if args.freeze_backbone:
        freeze_backbone(model, args.arch)

    trainable_parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    optimizer = torch.optim.AdamW(trainable_parameters, lr=args.lr, weight_decay=args.weight_decay)

    print(f"Classes: {train_dataset.class_to_idx}")
    print(f"Device: {device}")
    print(f"Architecture: {args.arch}")
    print(f"Image size: {image_size}")
    print(f"Pretrained weights: {not args.random_init}")
    print(f"Freeze backbone: {args.freeze_backbone}")

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
        "architecture": args.arch,
        "pretrained": not args.random_init,
        "freeze_backbone": args.freeze_backbone,
        "best_test_acc": best_test_acc,
    }
    save_checkpoint(
        out_path,
        model,
        train_dataset.class_to_idx,
        image_size=image_size,
        metadata=metadata,
        architecture=args.arch,
    )
    print(f"Saved model: {out_path}")
    print(f"Best test accuracy: {best_test_acc:.3f}")
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fine-tune a pretrained image classifier on the Nailong/Naiwa dataset."
    )
    parser.add_argument("--split-dir", default="nailong_naiwa_splits")
    parser.add_argument("--arch", choices=["resnet18", "mobilenet_v3_small", "vit_b_16"], default="resnet18")
    parser.add_argument("--out", default="models/nailong_naiwa_resnet18_finetuned.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--label-smoothing", type=float, default=0.04)
    parser.add_argument("--image-size", type=int, default=None)
    parser.add_argument("--print-every", type=int, default=2)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--freeze-backbone", action="store_true", help="Only train the downstream classifier head.")
    parser.add_argument("--random-init", action="store_true", help="Do not load ImageNet pretrained weights.")
    parser.add_argument("--torch-cache", default=".torch_cache", help="Project-local cache for pretrained weights.")
    parser.add_argument("--cpu", action="store_true", help="Force CPU training.")
    return parser


def main() -> int:
    train(build_parser().parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
