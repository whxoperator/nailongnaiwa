from __future__ import annotations

import argparse
import base64
import cgi
import html
import random
import shutil
import tempfile
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch

from nailong_model import load_checkpoint, predict_image


LABEL_TEXT = {"nailong": "奶龙", "naiwa": "奶蛙"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
SPLIT_WEIGHTS = (("train", 0.70), ("test", 0.15), ("generalization", 0.15))


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>奶龙 / 奶蛙识别</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: #f6f7f9;
      color: #17202a;
    }
    header {
      height: 58px;
      padding: 0 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid #d9e0ea;
      background: white;
    }
    header strong { font-size: 18px; }
    main {
      width: min(980px, 100%);
      margin: 0 auto;
      padding: 22px;
      display: grid;
      gap: 16px;
    }
    form, .panel {
      background: white;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      padding: 16px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    select, input[type=file] {
      width: 100%;
      height: 38px;
      border: 1px solid #cfd7e3;
      border-radius: 6px;
      padding: 0 10px;
      background: white;
    }
    input[type=file] { padding-top: 7px; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    button {
      min-height: 40px;
      padding: 0 16px;
      border: 0;
      border-radius: 6px;
      background: #1f6feb;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary { background: #1f9d55; }
    .result {
      display: grid;
      grid-template-columns: minmax(220px, 380px) 1fr;
      gap: 18px;
      align-items: start;
    }
    img.preview {
      width: 100%;
      max-height: 460px;
      object-fit: contain;
      border: 1px solid #d9e0ea;
      border-radius: 6px;
      background: #fff;
    }
    h2 { margin: 0 0 14px; font-size: 22px; }
    .bar {
      height: 30px;
      border-radius: 5px;
      background: #e8edf5;
      overflow: hidden;
      margin: 8px 0 14px;
    }
    .fill {
      height: 100%;
      background: #1f9d55;
      color: white;
      display: flex;
      align-items: center;
      padding-left: 10px;
      min-width: 42px;
      white-space: nowrap;
      font-size: 13px;
      font-weight: 700;
    }
    .muted { color: #667085; font-size: 13px; line-height: 1.55; }
    .message {
      border-left: 4px solid #1f9d55;
      padding: 10px 12px;
      background: #eefaf3;
      border-radius: 4px;
    }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
    @media (max-width: 760px) {
      .grid, .result { grid-template-columns: 1fr; }
      main { padding: 14px; }
    }
  </style>
</head>
<body>
  <header>
    <strong>奶龙 / 奶蛙识别</strong>
    <span class="muted">选择模型，上传图片，确认正确后自动入库</span>
  </header>
  <main>
    __MESSAGE__
    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="action" value="predict" />
      <div class="grid">
        <div>
          <label for="model">模型</label>
          <select id="model" name="model">__MODEL_OPTIONS__</select>
        </div>
        <div>
          <label for="image">新图片</label>
          <input id="image" type="file" name="image" accept="image/*" required />
        </div>
      </div>
      <div class="actions">
        <button type="submit">识别图片</button>
      </div>
    </form>
    __RESULT__
  </main>
</body>
</html>
"""


def model_options(models: list[Path], selected: Path | None) -> str:
    rows = []
    for model in models:
        is_selected = selected and model.resolve() == selected.resolve()
        rows.append(
            f'<option value="{html.escape(str(model))}" {"selected" if is_selected else ""}>'
            f'{html.escape(model.name)}</option>'
        )
    return "\n".join(rows)


def image_data_uri(image_path: Path) -> str:
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def result_html(
    image_path: Path,
    model_path: Path,
    predicted: str,
    scores: dict[str, float],
) -> str:
    rows = []
    for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        width = max(score * 100, 1.0)
        label = f"{name}（{LABEL_TEXT.get(name, name)}）"
        rows.append(
            f"""
            <div>{html.escape(label)}: {score * 100:.1f}%</div>
            <div class="bar"><div class="fill" style="width:{width:.1f}%">{score * 100:.1f}%</div></div>
            """
        )
    predicted_text = f"{predicted}（{LABEL_TEXT.get(predicted, predicted)}）"
    return f"""
    <section class="panel result">
      <img class="preview" src="{image_data_uri(image_path)}" alt="uploaded image" />
      <div>
        <h2>判断结果：{html.escape(predicted_text)}</h2>
        {''.join(rows)}
        <form method="post">
          <input type="hidden" name="action" value="accept" />
          <input type="hidden" name="image_path" value="{html.escape(str(image_path))}" />
          <input type="hidden" name="model" value="{html.escape(str(model_path))}" />
          <input type="hidden" name="predicted" value="{html.escape(predicted)}" />
          <div class="actions">
            <button class="secondary" type="submit">判断正确，随机加入数据集</button>
          </div>
        </form>
        <p class="muted">入库时会复制图片到 train / test / generalization 之一，不会删除原图片。</p>
      </div>
    </section>
    """


def parse_urlencoded(body: bytes) -> dict[str, str]:
    data = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] if values else "" for key, values in data.items()}


def unique_copy(source: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() if source.suffix.lower() in IMAGE_SUFFIXES else ".jpg"
    base = source.stem or "accepted"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    target = target_dir / f"{base}_{timestamp}{suffix}"
    counter = 1
    while target.exists():
        target = target_dir / f"{base}_{timestamp}_{counter:03d}{suffix}"
        counter += 1
    shutil.copy2(source, target)
    return target


def random_split(rng: random.Random) -> str:
    value = rng.random()
    cursor = 0.0
    for split_name, weight in SPLIT_WEIGHTS:
        cursor += weight
        if value <= cursor:
            return split_name
    return SPLIT_WEIGHTS[-1][0]


def make_handler(args: argparse.Namespace):
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    upload_dir = Path(tempfile.mkdtemp(prefix="nailong_predict_uploads_"))
    rng = random.Random(args.seed)
    cache: dict[Path, tuple[torch.nn.Module, list[str], int, dict[str, object]]] = {}

    def available_models() -> list[Path]:
        models = sorted(Path(args.models_dir).glob("*.pt"))
        if args.model:
            chosen = Path(args.model)
            if chosen.exists() and chosen not in models:
                models.insert(0, chosen)
        return models

    def selected_model(value: str | None) -> Path:
        models = available_models()
        if value:
            path = Path(value)
            if path.exists():
                return path
        if args.model and Path(args.model).exists():
            return Path(args.model)
        if models:
            return models[0]
        raise FileNotFoundError("models directory has no .pt model files")

    def get_model(path: Path):
        resolved = path.resolve()
        if resolved not in cache:
            cache[resolved] = load_checkpoint(resolved, device)
        return cache[resolved]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def render(self, result: str = "", message: str = "", selected: Path | None = None) -> None:
            models = available_models()
            if not models:
                result = '<section class="panel">没有找到模型，请先运行训练脚本生成 models/*.pt。</section>'
            message_html = f'<section class="message">{html.escape(message)}</section>' if message else ""
            data = (
                PAGE
                .replace("__MODEL_OPTIONS__", model_options(models, selected))
                .replace("__MESSAGE__", message_html)
                .replace("__RESULT__", result)
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            try:
                self.render(selected=selected_model(None))
            except FileNotFoundError:
                self.render()

        def do_POST(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("multipart/form-data"):
                self.handle_predict()
            else:
                length = int(self.headers.get("Content-Length", "0"))
                form = parse_urlencoded(self.rfile.read(length))
                if form.get("action") == "accept":
                    self.handle_accept(form)
                else:
                    self.render(message="未知操作。")

        def handle_predict(self) -> None:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            })
            model_path = selected_model(form.getfirst("model"))
            field = form["image"] if "image" in form else None
            if field is None or not field.filename:
                self.render(message="没有收到图片。", selected=model_path)
                return

            suffix = Path(field.filename).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                suffix = ".jpg"
            image_path = upload_dir / f"upload_{int(time.time() * 1000)}{suffix}"
            with image_path.open("wb") as f:
                shutil.copyfileobj(field.file, f)

            model, classes, image_size, _metadata = get_model(model_path)
            predicted, scores = predict_image(model, classes, image_path, device, image_size=image_size)
            self.render(result_html(image_path, model_path, predicted, scores), selected=model_path)

        def handle_accept(self, form: dict[str, str]) -> None:
            image_path = Path(form.get("image_path", ""))
            predicted = form.get("predicted", "")
            model_path = selected_model(form.get("model"))
            if predicted not in LABEL_TEXT or not image_path.exists():
                self.render(message="入库失败：图片或类别无效。", selected=model_path)
                return

            split_name = random_split(rng)
            target_dir = Path(args.split_dir) / split_name / predicted
            target = unique_copy(image_path, target_dir)
            message = f"已按 {predicted}（{LABEL_TEXT[predicted]}）复制到 {split_name}：{target}"
            self.render(message=message, selected=model_path)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local Nailong/Naiwa prediction web UI.")
    parser.add_argument("--model", default="models/nailong_naiwa_balanced_cnn.pt")
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--split-dir", default="nailong_naiwa_splits")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--cpu", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args))
    print(f"Open: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
