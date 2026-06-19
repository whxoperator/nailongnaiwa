from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
LABELS = {"nailong", "naiwa"}


def image_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def parse_llm_json(text: str) -> tuple[str, dict[str, float], str]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM response did not contain JSON.")

    payload = json.loads(text[start:end + 1])
    predicted = str(payload.get("predicted", "")).strip().lower()
    if predicted not in LABELS:
        raise ValueError(f"Unexpected LLM label: {predicted!r}")

    confidence = float(payload.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    other = "naiwa" if predicted == "nailong" else "nailong"
    scores = {predicted: confidence, other: 1.0 - confidence}
    reasoning = str(payload.get("reasoning", "")).strip()
    if not reasoning:
        reasoning = "The multimodal model returned a label without a detailed explanation."
    return predicted, scores, reasoning


def predict_with_multimodal_llm(image_path: str | Path) -> tuple[str, dict[str, float], str]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY before using the cloud multimodal LLM option.")

    base_url = os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    body = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an educational visual classifier for a Nailong/Naiwa image project. "
                    "Return only compact JSON."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Classify this image as exactly one label: nailong or naiwa. "
                            "Return JSON with keys predicted, confidence, reasoning. "
                            "confidence must be a number from 0 to 1."
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
                ],
            },
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM request failed: HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

    text = payload["choices"][0]["message"]["content"]
    return parse_llm_json(text)
