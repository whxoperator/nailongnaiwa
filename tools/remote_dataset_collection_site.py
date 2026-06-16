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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
SPLITS = ("train", "test", "generalization")

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>奶龙 / 奶蛙数据收集站</title>
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
      min-height: 58px;
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #d9e0ea;
      background: white;
      gap: 12px;
    }
    .title { font-size: 18px; font-weight: 750; }
    .subtle { font-size: 13px; color: #667085; }
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
    input, textarea {
      width: 100%;
      border: 1px solid #cfd7e3;
      border-radius: 6px;
      padding: 10px;
      font: inherit;
    }
    textarea { min-height: 86px; resize: vertical; }
    label { display: block; font-weight: 700; margin: 12px 0 6px; }
    button {
      min-height: 42px;
      padding: 0 16px;
      border: 0;
      border-radius: 6px;
      color: white;
      font-weight: 750;
      cursor: pointer;
    }
    .primary { background: #1f6feb; margin-top: 14px; }
    .nailong { background: #107c41; }
    .naiwa { background: #b3261e; }
    .reject { background: #5d6470; }
    .warning {
      border-left: 4px solid #1f6feb;
      background: #edf4ff;
      padding: 12px;
      border-radius: 6px;
      line-height: 1.6;
    }
    .review {
      display: grid;
      grid-template-columns: minmax(240px, 420px) 1fr;
      gap: 18px;
      align-items: start;
    }
    img {
      width: 100%;
      max-height: 540px;
      object-fit: contain;
      border: 1px solid #d9e0ea;
      border-radius: 6px;
      background: white;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(96px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
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
      header { align-items: flex-start; flex-direction: column; }
      .review { grid-template-columns: 1fr; }
      .actions, .metrics { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="title">奶龙 / 奶蛙数据收集站</div>
    <div class="subtle">__HEADER__</div>
  </header>
  <main>
    __BODY__
  </main>
</body>
</html>
"""


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def verify_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return image.size


def page(body: str, header: str = "") -> bytes:
    return (
        PAGE
        .replace("__HEADER__", html.escape(header))
        .replace("__BODY__", body)
        .encode("utf-8")
    )


def notice(text: str) -> str:
    return f'<section class="warning">{html.escape(text)}</section>'


class CollectionState:
    def __init__(self, args: argparse.Namespace) -> None:
        self.data_dir = Path(args.data_dir)
        self.admin_token = args.admin_token
        self.max_bytes = args.max_mb * 1024 * 1024
        self.ratios = {
            "train": args.train_ratio,
            "test": args.test_ratio,
            "generalization": args.generalization_ratio,
        }
        total = sum(self.ratios.values())
        self.ratios = {name: value / total for name, value in self.ratios.items()}
        self.pending_dir = self.data_dir / "pending"
        self.dataset_dir = self.data_dir / "dataset"
        self.rejected_dir = self.data_dir / "rejected"
        self.upload_manifest = self.data_dir / "uploads.csv"
        self.dataset_manifest = self.data_dir / "dataset_manifest.csv"

        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        for split in SPLITS:
            for label in ("nailong", "naiwa"):
                (self.dataset_dir / split / label).mkdir(parents=True, exist_ok=True)

    def choose_split(self) -> str:
        value = random.random()
        running = 0.0
        for name, ratio in self.ratios.items():
            running += ratio
            if value <= running:
                return name
        return "train"

    def all_known_hashes(self) -> set[str]:
        hashes = {path.stem for path in self.pending_dir.glob("*") if path.is_file()}
        hashes.update(path.stem for path in self.dataset_dir.rglob("*") if path.is_file())
        return hashes

    def save_upload(self, filename: str, note: str, data: bytes) -> dict[str, str]:
        if len(data) > self.max_bytes:
            raise ValueError(f"图片太大，最大允许 {self.max_bytes // 1024 // 1024} MB。")

        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            suffix = ".jpg"

        digest = sha1_bytes(data)
        if digest in self.all_known_hashes():
            return {"status": "duplicate", "sha1": digest}

        target = self.pending_dir / f"{digest}{suffix}"
        target.write_bytes(data)
        width, height = verify_image(target)
        self.append_upload_manifest(target, digest, filename, note, width, height)
        return {"status": "saved", "sha1": digest, "path": str(target)}

    def append_upload_manifest(
        self,
        target: Path,
        digest: str,
        filename: str,
        note: str,
        width: int,
        height: int,
    ) -> None:
        is_new = not self.upload_manifest.exists()
        with self.upload_manifest.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "sha1", "filename", "path", "width", "height", "note"],
            )
            if is_new:
                writer.writeheader()
            writer.writerow(
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "sha1": digest,
                    "filename": filename,
                    "path": str(target.relative_to(self.data_dir)),
                    "width": width,
                    "height": height,
                    "note": note,
                }
            )

    def pending_images(self) -> list[Path]:
        return sorted(path for path in self.pending_dir.iterdir() if path.is_file())

    def classify(self, image_name: str, action: str) -> dict[str, str]:
        source = self.pending_dir / image_name
        if not source.exists():
            raise ValueError("待审核图片不存在。")

        if action == "reject":
            target = self.rejected_dir / source.name
            shutil.move(str(source), target)
            return {"action": "reject", "path": str(target)}

        if action not in {"nailong", "naiwa"}:
            raise ValueError("未知分类。")

        split = self.choose_split()
        target = self.dataset_dir / split / action / source.name
        shutil.move(str(source), target)
        self.append_dataset_manifest(target, split, action)
        return {"action": action, "split": split, "path": str(target)}

    def append_dataset_manifest(self, target: Path, split: str, label: str) -> None:
        is_new = not self.dataset_manifest.exists()
        with self.dataset_manifest.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["timestamp", "split", "label", "filename", "sha1"],
            )
            if is_new:
                writer.writeheader()
            writer.writerow(
                {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "split": split,
                    "label": label,
                    "filename": str(target.relative_to(self.dataset_dir)),
                    "sha1": target.stem,
                }
            )

    def metrics(self) -> dict[str, int]:
        result = {"pending": len(self.pending_images()), "rejected": len(list(self.rejected_dir.glob("*")))}
        for split in SPLITS:
            for label in ("nailong", "naiwa"):
                result[f"{split}_{label}"] = len(list((self.dataset_dir / split / label).glob("*")))
        return result


def upload_form(message: str = "") -> str:
    return f"""
    {message}
    <section class="panel">
      <form method="post" action="/submit" enctype="multipart/form-data">
        <label>上传图片</label>
        <input type="file" name="image" accept="image/*" required />
        <label>备注</label>
        <textarea name="note" placeholder="可选：来源、关键词、你认为它更像奶龙还是奶蛙"></textarea>
        <button class="primary" type="submit">提交给管理员审核</button>
      </form>
    </section>
    """


def admin_login() -> str:
    return """
    <section class="panel">
      <form method="get" action="/admin">
        <label>管理员 Token</label>
        <input type="password" name="token" required />
        <button class="primary" type="submit">进入审核</button>
      </form>
    </section>
    """


def image_data_url(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{data}"


def metrics_html(state: CollectionState) -> str:
    metrics = state.metrics()
    cards = [
        ("待审核", metrics["pending"]),
        ("已拒绝", metrics["rejected"]),
        ("train", metrics["train_nailong"] + metrics["train_naiwa"]),
        ("test", metrics["test_nailong"] + metrics["test_naiwa"]),
        ("generalization", metrics["generalization_nailong"] + metrics["generalization_naiwa"]),
    ]
    return "".join(
        f'<div class="metric"><div>{html.escape(name)}</div><strong>{value}</strong></div>'
        for name, value in cards
    )


def admin_page(state: CollectionState, token: str, message: str = "") -> str:
    pending = state.pending_images()
    metrics = f'<section class="panel"><div class="metrics">{metrics_html(state)}</div></section>'
    if not pending:
        return f"{message}{metrics}<section class='panel'>暂无待审核图片。</section>"

    current = pending[0]
    return f"""
    {message}
    {metrics}
    <section class="panel review">
      <img src="{image_data_url(current)}" alt="pending image" />
      <div>
        <h2>审核图片</h2>
        <p class="subtle">文件: {html.escape(current.name)}</p>
        <form method="post" action="/admin/classify">
          <input type="hidden" name="token" value="{html.escape(token)}" />
          <input type="hidden" name="image" value="{html.escape(current.name)}" />
          <div class="actions">
            <button class="nailong" type="submit" name="action" value="nailong">奶龙</button>
            <button class="naiwa" type="submit" name="action" value="naiwa">奶蛙</button>
            <button class="reject" type="submit" name="action" value="reject">拒绝</button>
          </div>
        </form>
      </div>
    </section>
    """


def make_handler(state: CollectionState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def send_page(self, body: str, header: str = "") -> None:
            data = page(body, header)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/admin":
                token = query.get("token", [""])[0]
                if token != state.admin_token:
                    self.send_page(admin_login(), "管理员审核")
                    return
                self.send_page(admin_page(state, token), "管理员审核")
                return

            if parsed.path == "/api/metrics":
                payload = json.dumps(state.metrics(), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            self.send_page(upload_form(), "公开上传")

        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length > state.max_bytes + 1024 * 512:
                self.send_page(upload_form(notice("上传内容太大。")), "公开上传")
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                },
            )

            if self.path == "/submit":
                field = form["image"] if "image" in form else None
                if field is None or not field.filename:
                    self.send_page(upload_form(notice("没有收到图片。")), "公开上传")
                    return
                try:
                    note = form.getfirst("note", "")
                    result = state.save_upload(field.filename, note, field.file.read())
                except Exception as exc:
                    self.send_page(upload_form(notice(f"提交失败: {exc}")), "公开上传")
                    return

                if result["status"] == "duplicate":
                    self.send_page(upload_form(notice("这张图片已经提交过了，未重复保存。")), "公开上传")
                else:
                    self.send_page(upload_form(notice("提交成功，等待管理员分类。")), "公开上传")
                return

            if self.path == "/admin/classify":
                token = form.getfirst("token", "")
                if token != state.admin_token:
                    self.send_page(admin_login(), "管理员审核")
                    return
                try:
                    image_name = form.getfirst("image", "")
                    action = form.getfirst("action", "")
                    result = state.classify(image_name, action)
                except Exception as exc:
                    self.send_page(admin_page(state, token, notice(f"操作失败: {exc}")), "管理员审核")
                    return

                if result["action"] == "reject":
                    message = notice(f"已拒绝: {result['path']}")
                else:
                    message = notice(f"已保存到 {result['split']} / {result['action']}: {result['path']}")
                self.send_page(admin_page(state, token, message), "管理员审核")
                return

            self.send_error(404)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Public upload + admin review site for Nailong/Naiwa datasets.")
    parser.add_argument("--data-dir", default="remote_collection_data")
    parser.add_argument("--admin-token", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--max-mb", type=int, default=8)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--generalization-ratio", type=float, default=0.15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    state = CollectionState(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"Public upload: http://{args.host}:{args.port}")
    print(f"Admin review:  http://{args.host}:{args.port}/admin?token={args.admin_token}")
    print(f"Data dir:      {state.data_dir}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
