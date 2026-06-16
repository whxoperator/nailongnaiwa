#!/usr/bin/env python3
"""
Interactive image crawler and dataset labeler.

Example:
    python interactive_image_dataset.py --query "cat face" --max 100 --out dataset

Keys while labeling:
    p = positive sample
    n = negative sample
    s = skip/delete candidate
    q = quit
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable
from urllib import parse, request
from urllib.error import URLError


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)

REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Referer": "https://tw.cyberlink.com/",
}

SSL_CONTEXT = ssl._create_unverified_context()

IMAGE_EXT_BY_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"BM": ".bmp",
}


def fetch_text(url: str, timeout: int = 20) -> str:
    req = request.Request(url, headers=REQUEST_HEADERS)
    with request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def bing_image_urls(query: str, pages: int = 6) -> Iterable[str]:
    """Yield original image URLs from Bing image search HTML."""
    seen: set[str] = set()
    encoded = parse.urlencode({"q": query, "form": "HDRSC2"})

    for page in range(pages):
        first = page * 35 + 1
        url = f"https://www.bing.com/images/search?{encoded}&first={first}"
        try:
            text = fetch_text(url)
        except URLError as exc:
            print(f"[warn] search failed: {exc}")
            return

        # Bing stores original URLs in murl fields inside HTML/JSON snippets.
        matches = re.findall(r'"murl"\s*:\s*"([^"]+)"', text)
        matches += re.findall(r"&quot;murl&quot;\s*:\s*&quot;(.*?)&quot;", text)

        for raw in matches:
            image_url = html.unescape(raw)
            image_url = image_url.encode("utf-8").decode("unicode_escape", errors="ignore")
            if image_url.startswith(("http://", "https://")) and image_url not in seen:
                seen.add(image_url)
                yield image_url


def baidu_image_urls(query: str, pages: int = 4) -> Iterable[str]:
    """Yield image URLs from Baidu Image Search JSON responses."""
    seen: set[str] = set()

    for page in range(pages):
        params = parse.urlencode(
            {
                "tn": "resultjson_com",
                "ipn": "rj",
                "ct": "201326592",
                "is": "",
                "fp": "result",
                "queryWord": query,
                "cl": "2",
                "lm": "-1",
                "ie": "utf-8",
                "oe": "utf-8",
                "word": query,
                "pn": page * 30,
                "rn": 30,
            }
        )
        url = f"https://image.baidu.com/search/acjson?{params}"
        print(f"[search] baidu page {page + 1}/{pages}: {query}")
        try:
            text = fetch_text(url)
            payload = json.loads(text)
        except Exception as exc:
            print(f"[warn] baidu search failed: {exc}")
            continue

        for item in payload.get("data", []):
            for key in ("objURL", "middleURL", "hoverURL", "thumbURL"):
                image_url = item.get(key)
                if image_url and image_url.startswith(("http://", "https://")):
                    if image_url not in seen:
                        seen.add(image_url)
                        yield image_url


def image_urls_from_file(path: Path) -> Iterable[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            yield line


def extension_from_bytes(data: bytes, fallback_url: str) -> str | None:
    for magic, ext in IMAGE_EXT_BY_MAGIC.items():
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"

    suffix = Path(parse.urlparse(fallback_url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return None


def download_image(url: str, temp_dir: Path, timeout: int = 25) -> Path | None:
    req = request.Request(url, headers=REQUEST_HEADERS)
    try:
        with request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
            data = resp.read(20 * 1024 * 1024)
    except Exception as exc:
        print(f"[skip] download failed: {exc}")
        return None

    ext = extension_from_bytes(data, url)
    if not ext:
        print("[skip] unsupported or unknown image type")
        return None

    digest = hashlib.sha1(data).hexdigest()
    candidate = temp_dir / f"{digest}{ext}"
    candidate.write_bytes(data)
    return candidate


def open_image(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def append_manifest(manifest_path: Path, row: dict[str, str]) -> None:
    is_new = not manifest_path.exists()
    with manifest_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["filename", "label", "source_url", "query", "timestamp"],
        )
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def next_dataset_path(label_dir: Path, candidate: Path) -> Path:
    digest = candidate.stem
    ext = candidate.suffix.lower()
    target = label_dir / f"{digest}{ext}"
    index = 2
    while target.exists():
        target = label_dir / f"{digest}_{index}{ext}"
        index += 1
    return target


def label_images(args: argparse.Namespace, urls: Iterable[str]) -> None:
    out_dir = Path(args.out)
    positive_dir = out_dir / args.positive_name
    negative_dir = out_dir / args.negative_name
    manifest_path = out_dir / "manifest.csv"

    positive_dir.mkdir(parents=True, exist_ok=True)
    negative_dir.mkdir(parents=True, exist_ok=True)

    accepted = 0
    scanned = 0

    with tempfile.TemporaryDirectory(prefix="image_labeler_") as tmp:
        temp_dir = Path(tmp)

        for url in urls:
            if accepted >= args.max:
                break

            scanned += 1
            print(f"\n[{scanned}] fetching: {url}")
            candidate = download_image(url, temp_dir)
            if not candidate:
                continue

            if args.auto_label:
                choice = {"positive": "p", "negative": "n", "skip": "s"}[args.auto_label]
                print(f"[auto] label: {args.auto_label}")
            else:
                if not args.no_preview:
                    try:
                        open_image(candidate)
                    except Exception as exc:
                        print(f"[warn] could not open preview automatically: {exc}")
                        print(f"       candidate saved at: {candidate}")

                while True:
                    choice = input("label? [p]ositive / [n]egative / [s]kip / [q]uit: ")
                    choice = choice.strip().lower()
                    if choice in {"p", "n", "s", "q"}:
                        break
                    print("Please enter p, n, s, or q.")

            if choice == "q":
                print("Stopped.")
                return
            if choice == "s":
                candidate.unlink(missing_ok=True)
                continue

            label = "positive" if choice == "p" else "negative"
            label_dir = positive_dir if choice == "p" else negative_dir
            target = next_dataset_path(label_dir, candidate)
            shutil.move(str(candidate), target)

            append_manifest(
                manifest_path,
                {
                    "filename": str(target.relative_to(out_dir)),
                    "label": label,
                    "source_url": url,
                    "query": args.query or "",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
            accepted += 1
            print(f"[saved] {label}: {target}")
            time.sleep(args.delay)

    print(f"\nDone. Saved {accepted} labeled images into: {out_dir}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl images and interactively label them into a dataset."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--query", help="Search keyword, for example: \"helmet worker\"")
    source.add_argument("--urls-file", type=Path, help="Text file containing one image URL per line")

    parser.add_argument("--max", type=int, default=50, help="Maximum labeled images to save")
    parser.add_argument("--out", default="dataset", help="Output dataset directory")
    parser.add_argument("--positive-name", default="positive", help="Positive sample folder name")
    parser.add_argument("--negative-name", default="negative", help="Negative sample folder name")
    parser.add_argument("--pages", type=int, default=6, help="Search result pages to scan")
    parser.add_argument("--engine", choices=["baidu", "bing"], default="baidu", help="Image search engine")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay after each saved image")
    parser.add_argument("--no-preview", action="store_true", help="Do not open images before labeling")
    parser.add_argument(
        "--auto-label",
        choices=["positive", "negative", "skip"],
        help="Testing helper: label every downloaded image without prompting",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    if args.urls_file:
        urls = image_urls_from_file(args.urls_file)
    elif args.engine == "baidu":
        urls = baidu_image_urls(args.query, pages=args.pages)
    else:
        urls = bing_image_urls(args.query, pages=args.pages)

    try:
        label_images(args, urls)
    except KeyboardInterrupt:
        print("\nStopped by Ctrl+C.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
