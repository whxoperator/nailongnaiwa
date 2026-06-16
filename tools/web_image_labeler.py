#!/usr/bin/env python3
"""
Browser-based image labeler.

Example:
    python web_image_labeler.py --source-dir example_dataset/positive --out ui_labeled_dataset
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import shutil
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request
from urllib.error import URLError


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Image Labeler</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #18202a;
      --muted: #6b7280;
      --line: #d8dee8;
      --panel: #f6f7f9;
      --good: #107c41;
      --bad: #b3261e;
      --skip: #5d6470;
      --bg: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    header {
      height: 56px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 18px;
      gap: 16px;
    }
    .title {
      font-size: 17px;
      font-weight: 650;
      white-space: nowrap;
    }
    .status {
      color: var(--muted);
      font-size: 14px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-align: right;
    }
    main {
      min-height: 0;
      display: grid;
      grid-template-rows: 1fr auto;
      background: var(--panel);
    }
    .stage {
      min-height: 0;
      display: grid;
      place-items: center;
      padding: 18px;
    }
    img {
      max-width: 100%;
      max-height: calc(100vh - 180px);
      object-fit: contain;
      background: white;
      border: 1px solid var(--line);
      border-radius: 6px;
    }
    .empty {
      color: var(--muted);
      font-size: 18px;
    }
    .toolbar {
      border-top: 1px solid var(--line);
      background: white;
      display: grid;
      grid-template-columns: repeat(3, minmax(96px, 180px));
      justify-content: center;
      gap: 12px;
      padding: 14px;
    }
    button {
      height: 44px;
      border: 1px solid transparent;
      border-radius: 6px;
      color: white;
      font-size: 15px;
      font-weight: 650;
      cursor: pointer;
    }
    button:disabled {
      opacity: .45;
      cursor: default;
    }
    .positive { background: var(--good); }
    .negative { background: var(--bad); }
    .skip { background: var(--skip); }
    footer {
      height: 30px;
      padding: 0 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-size: 12px;
      border-top: 1px solid var(--line);
    }
    @media (max-width: 520px) {
      header { height: 64px; align-items: flex-start; flex-direction: column; padding: 8px 12px; }
      .status { width: 100%; text-align: left; }
      .toolbar { grid-template-columns: 1fr; }
      img { max-height: calc(100vh - 260px); }
    }
  </style>
</head>
<body>
  <header>
    <div class="title">图片样本标注</div>
    <div class="status" id="status">加载中...</div>
  </header>
  <main>
    <section class="stage" id="stage"></section>
    <section class="toolbar">
      <button class="positive" id="positive">正样本</button>
      <button class="negative" id="negative">负样本</button>
      <button class="skip" id="skip">跳过</button>
    </section>
  </main>
  <footer id="footer">输出目录</footer>
  <script>
    const stage = document.querySelector("#stage");
    const statusEl = document.querySelector("#status");
    const footer = document.querySelector("#footer");
    const buttons = [...document.querySelectorAll("button")];

    async function loadState() {
      const res = await fetch("/api/state");
      const state = await res.json();
      footer.textContent = `输出目录: ${state.out_dir}`;
      buttons.forEach(button => button.disabled = state.done);

      if (state.done) {
        statusEl.textContent = `完成: ${state.total}/${state.total}`;
        stage.innerHTML = `<div class="empty">全部图片已标注完成</div>`;
        return;
      }

      statusEl.textContent = `${state.index + 1}/${state.total}  ${state.name}`;
      stage.innerHTML = `<img src="/api/image?cache=${Date.now()}" alt="待标注图片" />`;
    }

    async function label(kind) {
      buttons.forEach(button => button.disabled = true);
      await fetch("/api/label", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({label: kind})
      });
      await loadState();
    }

    document.querySelector("#positive").addEventListener("click", () => label("positive"));
    document.querySelector("#negative").addEventListener("click", () => label("negative"));
    document.querySelector("#skip").addEventListener("click", () => label("skip"));
    window.addEventListener("keydown", event => {
      if (event.key.toLowerCase() === "p") label("positive");
      if (event.key.toLowerCase() === "n") label("negative");
      if (event.key.toLowerCase() === "s") label("skip");
    });
    loadState();
  </script>
</body>
</html>
"""


def download(url: str, cache_dir: Path) -> Path:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    with request.urlopen(req, timeout=25) as resp:
        data = resp.read(20 * 1024 * 1024)
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        suffix = ".jpg"
    digest = hashlib.sha1(data).hexdigest()
    path = cache_dir / f"{digest}{suffix}"
    path.write_bytes(data)
    return path


class LabelerState:
    def __init__(self, args: argparse.Namespace) -> None:
        self.out_dir = Path(args.out)
        self.positive_dir = self.out_dir / args.positive_name
        self.negative_dir = self.out_dir / args.negative_name
        self.manifest_path = self.out_dir / "manifest.csv"
        self.positive_dir.mkdir(parents=True, exist_ok=True)
        self.negative_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Path(tempfile.mkdtemp(prefix="web_image_labeler_"))
        self.items = self.load_items(args)
        self.index = 0

    def load_items(self, args: argparse.Namespace) -> list[dict[str, str]]:
        if args.source_dir:
            source_dir = Path(args.source_dir)
            paths = [
                path for path in source_dir.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            ]
            return [{"kind": "file", "path": str(path), "name": path.name} for path in sorted(paths)]

        urls = []
        for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append({"kind": "url", "url": line, "name": line.rsplit("/", 1)[-1]})
        return urls

    @property
    def done(self) -> bool:
        return self.index >= len(self.items)

    def current_path(self) -> Path | None:
        if self.done:
            return None
        item = self.items[self.index]
        if item["kind"] == "file":
            return Path(item["path"])
        if "cached" not in item:
            item["cached"] = str(download(item["url"], self.cache))
        return Path(item["cached"])

    def save_label(self, label: str) -> None:
        source = self.current_path()
        if source is None:
            return

        item = self.items[self.index]
        if label in {"positive", "negative"}:
            label_dir = self.positive_dir if label == "positive" else self.negative_dir
            target = label_dir / source.name
            count = 2
            while target.exists():
                target = label_dir / f"{source.stem}_{count}{source.suffix}"
                count += 1
            shutil.copy2(source, target)
            self.append_manifest(target, label, item)

        self.index += 1

    def append_manifest(self, target: Path, label: str, item: dict[str, str]) -> None:
        is_new = not self.manifest_path.exists()
        with self.manifest_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "label", "source", "timestamp"])
            if is_new:
                writer.writeheader()
            writer.writerow({
                "filename": str(target.relative_to(self.out_dir)),
                "label": label,
                "source": item.get("url") or item.get("path") or "",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })


def make_handler(state: LabelerState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def send_json(self, payload: dict[str, object]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/?"):
                data = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            if self.path.startswith("/api/state"):
                current = None if state.done else state.items[state.index]
                self.send_json({
                    "done": state.done,
                    "index": state.index,
                    "total": len(state.items),
                    "name": "" if current is None else current["name"],
                    "out_dir": str(state.out_dir),
                })
                return

            if self.path.startswith("/api/image"):
                try:
                    path = state.current_path()
                except URLError as exc:
                    self.send_error(502, str(exc))
                    return
                if path is None:
                    self.send_error(404)
                    return
                data = path.read_bytes()
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            self.send_error(404)

        def do_POST(self) -> None:
            if self.path != "/api/label":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            label = payload.get("label")
            if label not in {"positive", "negative", "skip"}:
                self.send_error(400, "Unknown label")
                return
            state.save_label(label)
            self.send_json({"ok": True})

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open a browser UI for positive/negative image labeling.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-dir", help="Directory containing images to label")
    source.add_argument("--urls-file", help="Text file containing one image URL per line")
    parser.add_argument("--out", default="ui_labeled_dataset", help="Output dataset directory")
    parser.add_argument("--positive-name", default="positive", help="Positive sample folder name")
    parser.add_argument("--negative-name", default="negative", help="Negative sample folder name")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    state = LabelerState(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    url = f"http://{args.host}:{args.port}"
    print(f"Open: {url}")
    print(f"Images: {len(state.items)}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
