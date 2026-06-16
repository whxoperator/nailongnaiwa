from __future__ import annotations

import argparse
import base64
import cgi
import csv
import hashlib
import html
import json
import random
import shutil
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
DEFAULT_SPLIT_RATIOS = {
    "train": 0.70,
    "test": 0.15,
    "generalization": 0.15,
}

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>随机数据集入库</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", Arial, sans-serif;
      background: #f5f7fb;
      color: #17202a;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      height: 58px;
      padding: 0 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #d9e0ea;
      background: white;
    }
    .title { font-size: 18px; font-weight: 750; }
    .status { font-size: 13px; color: #667085; text-align: right; }
    main {
      width: min(980px, 100%);
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .panel {
      background: white;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      padding: 16px;
    }
    form { margin: 0; }
    input[type=file] { width: 100%; }
    button {
      height: 42px;
      padding: 0 16px;
      border: 0;
      border-radius: 6px;
      color: white;
      font-weight: 750;
      cursor: pointer;
    }
    .upload { margin-top: 14px; background: #1f6feb; }
    .positive { background: #107c41; }
    .negative { background: #b3261e; }
    .ghost {
      background: white;
      color: #344054;
      border: 1px solid #cdd5df;
    }
    .preview {
      display: grid;
      grid-template-columns: minmax(240px, 420px) 1fr;
      gap: 18px;
      align-items: start;
    }
    img {
      width: 100%;
      max-height: 480px;
      object-fit: contain;
      border: 1px solid #d9e0ea;
      border-radius: 6px;
      background: #fff;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(120px, 1fr));
      gap: 12px;
      margin: 14px 0;
    }
    .notice {
      border-left: 4px solid #1f6feb;
      background: #edf4ff;
      padding: 12px;
      border-radius: 6px;
      line-height: 1.6;
    }
    .muted { color: #667085; font-size: 13px; line-height: 1.6; }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }
    .metric {
      border: 1px solid #d9e0ea;
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfe;
    }
    .metric strong { display: block; font-size: 18px; margin-top: 4px; }
    @media (max-width: 760px) {
      main { padding: 14px; }
      header { height: auto; min-height: 58px; align-items: flex-start; flex-direction: column; padding: 10px 14px; gap: 4px; }
      .status { text-align: left; }
      .preview { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="title">随机数据集入库</div>
    <div class="status">输出目录: __OUT_DIR__</div>
  </header>
  <main>
    __MESSAGE__
    __CONTENT__
    <section class="panel">
      <div class="grid">__METRICS__</div>
    </section>
  </main>
</body>
</html>
"""

UPLOAD_FORM = """
<section class="panel">
  <form method="post" action="/preview" enctype="multipart/form-data">
    <input type="file" name="image" accept="image/*" required />
    <button class="upload" type="submit">上传并预览</button>
    <p class="muted">先上传图片，确认内容后再点正样本或负样本。保存时会随机进入训练集、测试集或泛化集。</p>
  </form>
</section>
"""


def file_digest(path: Path) -> str:
    sha1 = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def verify_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.size


def choose_split(ratios: dict[str, float]) -> str:
    value = random.random()
    running = 0.0
    for name, ratio in ratios.items():
        running += ratio
        if value <= running:
            return name
    return "train"


class IngestState:
    def __init__(self, args: argparse.Namespace) -> None:
        self.out_dir = Path(args.out)
        self.positive_name = args.positive_name
        self.negative_name = args.negative_name
        self.positive_display = args.positive_display
        self.negative_display = args.negative_display
        self.ratios = {
            "train": args.train_ratio,
            "test": args.test_ratio,
            "generalization": args.generalization_ratio,
        }
        total = sum(self.ratios.values())
        self.ratios = {name: value / total for name, value in self.ratios.items()}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="random_split_ingest_"))
        self.pending: dict[str, dict[str, str]] = {}
        self.manifest_path = self.out_dir / "manifest.csv"

        for split in self.ratios:
            for label in [self.positive_name, self.negative_name]:
                (self.out_dir / split / label).mkdir(parents=True, exist_ok=True)

    def save_pending(self, source_name: str, data: bytes) -> tuple[str, Path, str, tuple[int, int]]:
        suffix = Path(source_name).suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            suffix = ".jpg"

        token = uuid.uuid4().hex
        path = self.temp_dir / f"{token}{suffix}"
        path.write_bytes(data)
        size = verify_image(path)
        digest = file_digest(path)
        self.pending[token] = {
            "path": str(path),
            "source_name": source_name,
            "digest": digest,
            "suffix": suffix,
            "width": str(size[0]),
            "height": str(size[1]),
        }
        return token, path, digest, size

    def already_exists(self, digest: str) -> Path | None:
        for path in self.out_dir.rglob("*"):
            if path.is_file() and path.stem == digest:
                return path
        return None

    def commit(self, token: str, label_kind: str) -> dict[str, str]:
        if token not in self.pending:
            raise ValueError("Pending image was not found.")

        item = self.pending.pop(token)
        source = Path(item["path"])
        digest = item["digest"]
        existing = self.already_exists(digest)
        if existing:
            source.unlink(missing_ok=True)
            return {
                "status": "duplicate",
                "path": str(existing),
                "split": existing.parts[-3],
                "label": existing.parts[-2],
            }

        label = self.positive_name if label_kind == "positive" else self.negative_name
        split = choose_split(self.ratios)
        target = self.out_dir / split / label / f"{digest}{item['suffix']}"
        shutil.move(str(source), target)
        self.append_manifest(target, split, label, item)
        return {
            "status": "saved",
            "path": str(target),
            "split": split,
            "label": label,
        }

    def append_manifest(self, target: Path, split: str, label: str, item: dict[str, str]) -> None:
        is_new = not self.manifest_path.exists()
        with self.manifest_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "split",
                    "label",
                    "filename",
                    "sha1",
                    "width",
                    "height",
                    "source_name",
                ],
            )
            if is_new:
                writer.writeheader()
            writer.writerow(
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "split": split,
                    "label": label,
                    "filename": str(target.relative_to(self.out_dir)),
                    "sha1": item["digest"],
                    "width": item["width"],
                    "height": item["height"],
                    "source_name": item["source_name"],
                }
            )

    def metrics(self) -> str:
        blocks = []
        for split in ["train", "test", "generalization"]:
            positive = len(list((self.out_dir / split / self.positive_name).glob("*")))
            negative = len(list((self.out_dir / split / self.negative_name).glob("*")))
            blocks.append(
                f"""
                <div class="metric">
                  <div>{split}</div>
                  <strong>{positive + negative}</strong>
                  <div class="muted">{html.escape(self.positive_name)}: {positive} / {html.escape(self.negative_name)}: {negative}</div>
                </div>
                """
            )
        return "".join(blocks)


def render_page(state: IngestState, content: str, message: str = "") -> bytes:
    page = (
        PAGE
        .replace("__OUT_DIR__", html.escape(str(state.out_dir)))
        .replace("__MESSAGE__", message)
        .replace("__CONTENT__", content)
        .replace("__METRICS__", state.metrics())
    )
    return page.encode("utf-8")


def make_preview(state: IngestState, token: str, image_path: Path, source_name: str, size: tuple[int, int]) -> str:
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    safe_name = html.escape(source_name)
    return f"""
    <section class="panel preview">
      <img src="data:{mime};base64,{data}" alt="preview" />
      <div>
        <h2>确认标签</h2>
        <p class="muted">文件: {safe_name}<br />尺寸: {size[0]} x {size[1]}</p>
        <form method="post" action="/commit">
          <input type="hidden" name="token" value="{html.escape(token)}" />
          <div class="actions">
            <button class="positive" type="submit" name="label" value="positive">{html.escape(state.positive_display)}</button>
            <button class="negative" type="submit" name="label" value="negative">{html.escape(state.negative_display)}</button>
          </div>
        </form>
        <form method="get" action="/">
          <button class="ghost" type="submit">重新选择图片</button>
        </form>
      </div>
    </section>
    """


def notice(text: str) -> str:
    return f'<section class="notice">{html.escape(text)}</section>'


def make_handler(state: IngestState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def send_html(self, content: str, message: str = "") -> None:
            data = render_page(state, content, message)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/api/metrics":
                data = json.dumps({"html": state.metrics()}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_html(UPLOAD_FORM)

        def do_POST(self) -> None:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                },
            )

            if self.path == "/preview":
                field = form["image"] if "image" in form else None
                if field is None or not field.filename:
                    self.send_html(UPLOAD_FORM, notice("没有收到图片。"))
                    return
                try:
                    data = field.file.read()
                    token, image_path, digest, size = state.save_pending(field.filename, data)
                except Exception as exc:
                    self.send_html(UPLOAD_FORM, notice(f"图片无法读取: {exc}"))
                    return
                duplicate = state.already_exists(digest)
                message = notice(f"检测到重复图片，已存在于: {duplicate}") if duplicate else ""
                self.send_html(make_preview(state, token, image_path, field.filename, size), message)
                return

            if self.path == "/commit":
                token = form.getfirst("token", "")
                label = form.getfirst("label", "")
                if label not in {"positive", "negative"}:
                    self.send_html(UPLOAD_FORM, notice("标签无效。"))
                    return
                try:
                    result = state.commit(token, label)
                except Exception as exc:
                    self.send_html(UPLOAD_FORM, notice(f"保存失败: {exc}"))
                    return

                if result["status"] == "duplicate":
                    message = notice(f"重复图片，未再次保存。已有位置: {result['path']}")
                else:
                    message = notice(f"已保存到 {result['split']} / {result['label']}: {result['path']}")
                self.send_html(UPLOAD_FORM, message)
                return

            self.send_error(404)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upload, label, and randomly split images into a dataset.")
    parser.add_argument("--out", default="random_split_dataset")
    parser.add_argument("--positive-name", default="nailong")
    parser.add_argument("--negative-name", default="naiwa")
    parser.add_argument("--positive-display", default="奶龙")
    parser.add_argument("--negative-display", default="奶蛙")
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_SPLIT_RATIOS["train"])
    parser.add_argument("--test-ratio", type=float, default=DEFAULT_SPLIT_RATIOS["test"])
    parser.add_argument("--generalization-ratio", type=float, default=DEFAULT_SPLIT_RATIOS["generalization"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    state = IngestState(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"Open: http://{args.host}:{args.port}")
    print(f"Output: {state.out_dir}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
