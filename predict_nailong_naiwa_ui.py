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

from nailong_algorithms import (
    IMAGE_SUFFIXES,
    TRADITIONAL_ALGORITHMS,
    confidence_level,
    dataset_distribution,
    explain_confidence,
    predict_traditional,
)
from nailong_model import load_checkpoint, predict_image


LABEL_TEXT = {"nailong": "Nailong", "naiwa": "Naiwa"}
SPLIT_WEIGHTS = (("train", 0.70), ("test", 0.15), ("generalization", 0.15))
CNN_ALGORITHM = "cnn"
COMPARE_ALL = "compare_all"


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Nailong / Naiwa Classifier</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: #f5f6f8;
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
      width: min(1160px, 100%);
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
      grid-template-columns: 1fr 1fr 1fr;
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
    button.secondary { background: #16834a; }
    .result {
      display: grid;
      grid-template-columns: minmax(240px, 380px) 1fr;
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
    h3 { margin: 0 0 10px; font-size: 16px; }
    .bar {
      height: 30px;
      border-radius: 5px;
      background: #e8edf5;
      overflow: hidden;
      margin: 8px 0 14px;
    }
    .fill {
      height: 100%;
      color: white;
      display: flex;
      align-items: center;
      padding-left: 10px;
      min-width: 42px;
      white-space: nowrap;
      font-size: 13px;
      font-weight: 700;
    }
    .fill.nailong { background: #1f6feb; }
    .fill.naiwa { background: #16834a; }
    .muted { color: #667085; font-size: 13px; line-height: 1.55; }
    .message {
      border-left: 4px solid #16834a;
      padding: 10px 12px;
      background: #eefaf3;
      border-radius: 4px;
    }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
    .split-grid, .compare-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }
    .split-chart, .compare-card {
      border: 1px solid #e0e6ef;
      border-radius: 6px;
      padding: 12px;
      background: #fbfcfe;
    }
    .chart-row {
      display: grid;
      grid-template-columns: 72px 1fr 42px;
      gap: 8px;
      align-items: center;
      margin-top: 10px;
      font-size: 13px;
    }
    .mini-bar {
      height: 18px;
      background: #e8edf5;
      border-radius: 4px;
      overflow: hidden;
    }
    .mini-fill { height: 100%; border-radius: 4px; }
    .mini-fill.nailong { background: #7aa7f7; }
    .mini-fill.naiwa { background: #5fc98c; }
    .algo-badge, .confidence {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 8px;
      border: 1px solid #cfd7e3;
      border-radius: 999px;
      background: #f8fafc;
      font-size: 12px;
      color: #344054;
      margin: 0 8px 12px 0;
    }
    .confidence.high { border-color: #16834a; color: #12623a; background: #eefaf3; }
    .confidence.medium { border-color: #b7791f; color: #7a4d12; background: #fff8e8; }
    .confidence.low { border-color: #c2410c; color: #8a2c0a; background: #fff2ec; }
    .compare-card strong { display: block; margin-bottom: 8px; }
    @media (max-width: 860px) {
      .grid, .result, .split-grid, .compare-grid { grid-template-columns: 1fr; }
      main { padding: 14px; }
    }
  </style>
</head>
<body>
  <header>
    <strong>Nailong / Naiwa Classifier</strong>
    <span class="muted">CNN, classic image features, and algorithm comparison</span>
  </header>
  <main>
    __MESSAGE__
    <form method="post" enctype="multipart/form-data">
      <input type="hidden" name="action" value="predict" />
      <div class="grid">
        <div>
          <label for="algorithm">Algorithm</label>
          <select id="algorithm" name="algorithm">__ALGORITHM_OPTIONS__</select>
        </div>
        <div>
          <label for="model">CNN model</label>
          <select id="model" name="model">__MODEL_OPTIONS__</select>
        </div>
        <div>
          <label for="image">Image</label>
          <input id="image" type="file" name="image" accept="image/*" required />
        </div>
      </div>
      <div class="actions">
        <button type="submit">Classify image</button>
      </div>
    </form>
    __DISTRIBUTION__
    __RESULT__
  </main>
</body>
</html>
"""


def algorithm_options(selected: str) -> str:
    items = [
        (CNN_ALGORITHM, "CNN deep model"),
        (COMPARE_ALL, "Compare all algorithms"),
        *TRADITIONAL_ALGORITHMS.items(),
    ]
    return "\n".join(
        f'<option value="{html.escape(value)}" {"selected" if value == selected else ""}>{html.escape(label)}</option>'
        for value, label in items
    )


def model_options(models: list[Path], selected: Path | None) -> str:
    return "\n".join(
        f'<option value="{html.escape(str(model))}" '
        f'{"selected" if selected and model.resolve() == selected.resolve() else ""}>'
        f"{html.escape(model.name)}</option>"
        for model in models
    )


def image_data_uri(image_path: Path) -> str:
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def label_display(name: str) -> str:
    return f"{name} ({LABEL_TEXT.get(name, name)})"


def distribution_html(split_dir: str | Path) -> str:
    distribution = dataset_distribution(split_dir)
    max_count = max([count for labels in distribution.values() for count in labels.values()] or [1])
    sections = []
    for split_name, labels in distribution.items():
        rows = []
        for label in ("nailong", "naiwa"):
            count = labels.get(label, 0)
            width = (count / max_count * 100) if max_count else 0
            rows.append(
                f"""
                <div class="chart-row">
                  <span>{html.escape(label_display(label))}</span>
                  <div class="mini-bar"><div class="mini-fill {html.escape(label)}" style="width:{width:.1f}%"></div></div>
                  <strong>{count}</strong>
                </div>
                """
            )
        sections.append(f'<div class="split-chart"><h3>{html.escape(split_name)}</h3>{"".join(rows)}</div>')
    return f'<section class="panel"><h2>Image Distribution</h2><div class="split-grid">{"".join(sections)}</div></section>'


def score_rows(scores: dict[str, float]) -> str:
    rows = []
    for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        width = max(score * 100, 1.0)
        rows.append(
            f"""
            <div>{html.escape(label_display(name))}: {score * 100:.1f}%</div>
            <div class="bar"><div class="fill {html.escape(name)}" style="width:{width:.1f}%">{score * 100:.1f}%</div></div>
            """
        )
    return "".join(rows)


def result_html(
    image_path: Path,
    model_path: Path,
    algorithm: str,
    algorithm_label: str,
    predicted: str,
    scores: dict[str, float],
) -> str:
    level = confidence_level(scores)
    return f"""
    <section class="panel result">
      <img class="preview" src="{image_data_uri(image_path)}" alt="uploaded image" />
      <div>
        <span class="algo-badge">{html.escape(algorithm_label)}</span>
        <span class="confidence {html.escape(level)}">{html.escape(level)} confidence</span>
        <h2>Prediction: {html.escape(label_display(predicted))}</h2>
        <p class="muted">{html.escape(explain_confidence(scores))}</p>
        {score_rows(scores)}
        <form method="post">
          <input type="hidden" name="action" value="accept" />
          <input type="hidden" name="image_path" value="{html.escape(str(image_path))}" />
          <input type="hidden" name="model" value="{html.escape(str(model_path))}" />
          <input type="hidden" name="algorithm" value="{html.escape(algorithm)}" />
          <input type="hidden" name="predicted" value="{html.escape(predicted)}" />
          <div class="actions">
            <button class="secondary" type="submit">Accept result and add to dataset</button>
          </div>
        </form>
        <p class="muted">Accepted images are copied into train / test / generalization. The uploaded source is kept.</p>
      </div>
    </section>
    """


def comparison_html(image_path: Path, results: list[dict[str, object]]) -> str:
    cards = []
    for result in sorted(results, key=lambda item: float(item["confidence"]), reverse=True):
        scores = result["scores"]  # type: ignore[assignment]
        level = confidence_level(scores)  # type: ignore[arg-type]
        cards.append(
            f"""
            <div class="compare-card">
              <strong>{html.escape(str(result["label"]))}</strong>
              <span class="confidence {html.escape(level)}">{html.escape(level)}</span>
              <div>Prediction: {html.escape(label_display(str(result["predicted"])))}</div>
              {score_rows(scores)}
            </div>
            """
        )
    return f"""
    <section class="panel result">
      <img class="preview" src="{image_data_uri(image_path)}" alt="uploaded image" />
      <div>
        <h2>Algorithm Comparison</h2>
        <div class="compare-grid">{''.join(cards)}</div>
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
        return Path(args.model)

    def selected_algorithm(value: str | None) -> str:
        if value in {CNN_ALGORITHM, COMPARE_ALL} or value in TRADITIONAL_ALGORITHMS:
            return value
        return CNN_ALGORITHM

    def algorithm_label(value: str) -> str:
        if value == CNN_ALGORITHM:
            return "CNN deep model"
        if value == COMPARE_ALL:
            return "Compare all algorithms"
        return TRADITIONAL_ALGORITHMS[value]

    def get_model(path: Path):
        resolved = path.resolve()
        if resolved not in cache:
            cache[resolved] = load_checkpoint(resolved, device)
        return cache[resolved]

    def run_cnn(model_path: Path, image_path: Path) -> tuple[str, dict[str, float]]:
        model, classes, image_size, _metadata = get_model(model_path)
        return predict_image(model, classes, image_path, device, image_size=image_size)

    def compare_all(model_path: Path, image_path: Path) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        predicted, scores = run_cnn(model_path, image_path)
        results.append(
            {
                "label": f"CNN: {model_path.name}",
                "predicted": predicted,
                "scores": scores,
                "confidence": max(scores.values()),
            }
        )
        for algorithm, label in TRADITIONAL_ALGORITHMS.items():
            predicted, scores = predict_traditional(algorithm, image_path, args.split_dir)
            results.append(
                {
                    "label": label,
                    "predicted": predicted,
                    "scores": scores,
                    "confidence": max(scores.values()),
                }
            )
        return results

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def render(
            self,
            result: str = "",
            message: str = "",
            selected: Path | None = None,
            algorithm: str = CNN_ALGORITHM,
        ) -> None:
            models = available_models()
            if not models and algorithm in {CNN_ALGORITHM, COMPARE_ALL}:
                result = '<section class="panel">No CNN model was found. Run training first to create models/*.pt.</section>'
            message_html = f'<section class="message">{html.escape(message)}</section>' if message else ""
            data = (
                PAGE
                .replace("__ALGORITHM_OPTIONS__", algorithm_options(algorithm))
                .replace("__MODEL_OPTIONS__", model_options(models, selected))
                .replace("__DISTRIBUTION__", distribution_html(args.split_dir))
                .replace("__MESSAGE__", message_html)
                .replace("__RESULT__", result)
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            self.render(selected=selected_model(None))

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
                    self.render(message="Unknown action.")

        def handle_predict(self) -> None:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            })
            model_path = selected_model(form.getfirst("model"))
            algorithm = selected_algorithm(form.getfirst("algorithm"))
            field = form["image"] if "image" in form else None
            if field is None or not field.filename:
                self.render(message="No image was received.", selected=model_path, algorithm=algorithm)
                return

            suffix = Path(field.filename).suffix.lower()
            if suffix not in IMAGE_SUFFIXES:
                suffix = ".jpg"
            image_path = upload_dir / f"upload_{int(time.time() * 1000)}{suffix}"
            with image_path.open("wb") as f:
                shutil.copyfileobj(field.file, f)

            try:
                if algorithm == CNN_ALGORITHM:
                    predicted, scores = run_cnn(model_path, image_path)
                    result = result_html(image_path, model_path, algorithm, algorithm_label(algorithm), predicted, scores)
                elif algorithm == COMPARE_ALL:
                    result = comparison_html(image_path, compare_all(model_path, image_path))
                else:
                    predicted, scores = predict_traditional(algorithm, image_path, args.split_dir)
                    result = result_html(image_path, model_path, algorithm, algorithm_label(algorithm), predicted, scores)
            except Exception as exc:
                self.render(message=f"Prediction failed: {exc}", selected=model_path, algorithm=algorithm)
                return

            self.render(result, selected=model_path, algorithm=algorithm)

        def handle_accept(self, form: dict[str, str]) -> None:
            image_path = Path(form.get("image_path", ""))
            predicted = form.get("predicted", "")
            model_path = selected_model(form.get("model"))
            algorithm = selected_algorithm(form.get("algorithm"))
            if predicted not in LABEL_TEXT or not image_path.exists():
                self.render(message="Import failed: invalid image or class.", selected=model_path, algorithm=algorithm)
                return

            split_name = random_split(rng)
            target_dir = Path(args.split_dir) / split_name / predicted
            target = unique_copy(image_path, target_dir)
            message = f"Copied as {label_display(predicted)} into {split_name}: {target}"
            self.render(message=message, selected=model_path, algorithm=algorithm)

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
