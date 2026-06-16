from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


INPUT_DIR = Path("nailong_naiwa_10_demo") / "naiwa"
OUTPUT_DIR = Path("nailong_naiwa_10_demo") / "naiwa_preprocessed"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def build_watermark_mask(image: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    width, height = image.size

    # Most collected images have the watermark in the lower-right corner.
    left = int(width * 0.52)
    top = int(height * 0.76)
    box = (left, top, width, height)

    corner = image.crop(box).convert("RGB")
    gray = ImageOps.grayscale(corner)

    # White/light text and logos are the usual watermark signal.
    light_mask = gray.point(lambda px: 255 if px >= 176 else 0)

    # Text edges are also useful when the watermark is not pure white.
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mask = edges.point(lambda px: 255 if px >= 24 else 0)

    mask = ImageChops.lighter(light_mask, edge_mask)
    mask = mask.filter(ImageFilter.MaxFilter(9))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=6))
    return mask, box


def soften_watermark(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")
    mask, box = build_watermark_mask(image)
    corner = image.crop(box)

    # Replace detected watermark pixels with a heavily smoothed local texture.
    repaired = corner.filter(ImageFilter.MedianFilter(size=13))
    repaired = repaired.filter(ImageFilter.GaussianBlur(radius=18))

    result = image.copy()
    result.paste(repaired, box, mask)
    return result


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    )

    for index, source in enumerate(files, start=1):
        with Image.open(source) as image:
            processed = soften_watermark(image)
            target = OUTPUT_DIR / source.name
            processed.save(target, quality=95)
        print(f"[{index:03d}/{len(files):03d}] {source.name}")

    print(f"Saved {len(files)} images to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
