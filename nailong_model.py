from __future__ import annotations

import random
from pathlib import Path

import torch
from PIL import Image, ImageFilter, ImageOps
from torch import nn
from torchvision import models
from torchvision import transforms


IMAGE_SIZE = 160
CLASSES = ["nailong", "naiwa"]


class RandomCornerOcclusion:
    def __init__(self, probability: float = 0.65) -> None:
        self.probability = probability

    def __call__(self, image: Image.Image) -> Image.Image:
        if random.random() > self.probability:
            return image

        image = image.convert("RGB")
        width, height = image.size
        occ_width = random.randint(max(12, int(width * 0.14)), max(16, int(width * 0.30)))
        occ_height = random.randint(max(12, int(height * 0.07)), max(16, int(height * 0.18)))
        left = random.randint(max(0, width - occ_width - int(width * 0.10)), max(0, width - occ_width))
        top = random.randint(max(0, height - occ_height - int(height * 0.10)), max(0, height - occ_height))
        box = (left, top, min(width, left + occ_width), min(height, top + occ_height))

        patch = image.crop(box)
        mode = random.choice(["blur", "median", "mean"])
        if mode == "blur":
            patch = patch.filter(ImageFilter.GaussianBlur(radius=random.uniform(6, 18)))
        elif mode == "median":
            patch = patch.filter(ImageFilter.MedianFilter(size=9))
        else:
            patch = ImageOps.autocontrast(patch).filter(ImageFilter.GaussianBlur(radius=12))

        result = image.copy()
        result.paste(patch, box)
        return result


class SmallImageCNN(nn.Module):
    def __init__(self, num_classes: int = 2) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 24, kernel_size=3, padding=1),
            nn.BatchNorm2d(24),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(24, 48, kernel_size=3, padding=1),
            nn.BatchNorm2d(48),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(48, 96, kernel_size=3, padding=1),
            nn.BatchNorm2d(96),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(96, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.30),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


class LegacySmallImageCNN(nn.Module):
    def __init__(self, num_classes: int = 2) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 96, kernel_size=3, padding=1),
            nn.BatchNorm2d(96),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.25),
            nn.Linear(96, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


def build_torchvision_classifier(
    architecture: str,
    num_classes: int,
    pretrained: bool = False,
) -> nn.Module:
    architecture = architecture.lower()
    if architecture == "resnet18":
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        model = models.resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        return model
    if architecture == "mobilenet_v3_small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_small(weights=weights)
        in_features = model.classifier[-1].in_features
        model.classifier[-1] = nn.Linear(in_features, num_classes)
        return model
    if architecture == "vit_b_16":
        weights = models.ViT_B_16_Weights.DEFAULT if pretrained else None
        model = models.vit_b_16(weights=weights)
        in_features = model.heads.head.in_features
        model.heads.head = nn.Linear(in_features, num_classes)
        return model
    raise ValueError(f"Unsupported pretrained architecture: {architecture}")


def freeze_backbone(model: nn.Module, architecture: str) -> None:
    architecture = architecture.lower()
    for parameter in model.parameters():
        parameter.requires_grad = False

    if architecture == "resnet18":
        for parameter in model.fc.parameters():
            parameter.requires_grad = True
        return
    if architecture == "mobilenet_v3_small":
        for parameter in model.classifier.parameters():
            parameter.requires_grad = True
        return
    if architecture == "vit_b_16":
        for parameter in model.heads.parameters():
            parameter.requires_grad = True
        return
    raise ValueError(f"Unsupported pretrained architecture: {architecture}")


class ClassAwareImageFolder(torch.utils.data.Dataset):
    def __init__(
        self,
        root: str | Path,
        image_size: int = IMAGE_SIZE,
        augment: bool = True,
        corner_augment_classes: set[str] | None = None,
    ) -> None:
        from torchvision.datasets import ImageFolder

        self.dataset = ImageFolder(root)
        self.classes = self.dataset.classes
        self.class_to_idx = self.dataset.class_to_idx
        self.samples = self.dataset.samples
        self.corner_augment_labels = {
            self.class_to_idx[name]
            for name in (corner_augment_classes or set())
            if name in self.class_to_idx
        }
        common = [
            transforms.Resize((image_size + 36, image_size + 36)),
            transforms.RandomResizedCrop(image_size, scale=(0.72, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(12),
            transforms.ColorJitter(brightness=0.18, contrast=0.18, saturation=0.16, hue=0.02),
        ]
        if augment:
            self.base_transform = transforms.Compose(common)
        else:
            self.base_transform = transforms.Compose([transforms.Resize((image_size, image_size))])
        self.corner_transform = RandomCornerOcclusion(probability=0.75)
        self.final_transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
            ]
        )

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        path, label = self.samples[index]
        image = load_image(path)
        image = self.base_transform(image)
        if label in self.corner_augment_labels:
            image = self.corner_transform(image)
        return self.final_transform(image), label


def predict_transform(image_size: int = IMAGE_SIZE) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )


def load_image(path: str | Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def save_checkpoint(
    path: str | Path,
    model: nn.Module,
    class_to_idx: dict[str, int],
    image_size: int = IMAGE_SIZE,
    metadata: dict[str, object] | None = None,
    architecture: str = "small_cnn",
) -> None:
    payload = {
        "state_dict": model.state_dict(),
        "class_to_idx": class_to_idx,
        "image_size": image_size,
        "metadata": metadata or {},
        "architecture": architecture,
    }
    torch.save(payload, path)


def load_checkpoint(path: str | Path, device: torch.device) -> tuple[nn.Module, list[str], int, dict[str, object]]:
    payload = torch.load(path, map_location=device)
    class_to_idx = payload["class_to_idx"]
    classes = [name for name, _ in sorted(class_to_idx.items(), key=lambda item: item[1])]
    image_size = int(payload.get("image_size", IMAGE_SIZE))
    architecture = str(payload.get("architecture", "small_cnn"))

    if architecture in {"resnet18", "mobilenet_v3_small", "vit_b_16"}:
        model = build_torchvision_classifier(architecture, len(classes), pretrained=False).to(device)
    else:
        first_conv = payload["state_dict"].get("features.0.weight")
        if first_conv is not None and tuple(first_conv.shape[:2]) == (16, 3):
            model = LegacySmallImageCNN(num_classes=len(classes)).to(device)
        else:
            model = SmallImageCNN(num_classes=len(classes)).to(device)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, classes, image_size, dict(payload.get("metadata", {}))


@torch.no_grad()
def predict_image(
    model: nn.Module,
    classes: list[str],
    image_path: str | Path,
    device: torch.device,
    image_size: int = IMAGE_SIZE,
) -> tuple[str, dict[str, float]]:
    image = load_image(image_path)
    tensor = predict_transform(image_size)(image).unsqueeze(0).to(device)
    logits = model(tensor)
    probs = torch.softmax(logits, dim=1)[0].cpu()
    scores = {classes[index]: float(probs[index]) for index in range(len(classes))}
    predicted = max(scores, key=scores.get)
    return predicted, scores
