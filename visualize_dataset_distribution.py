from __future__ import annotations

import argparse
from pathlib import Path

from nailong_algorithms import dataset_distribution


def render_text_chart(split_dir: str | Path) -> str:
    distribution = dataset_distribution(split_dir)
    max_count = max(
        [count for labels in distribution.values() for count in labels.values()] or [1]
    )
    lines = [f"Dataset distribution: {split_dir}"]
    for split_name, labels in distribution.items():
        lines.append(f"\n[{split_name}]")
        for label in ("nailong", "naiwa"):
            count = labels.get(label, 0)
            bar = "#" * round((count / max_count) * 36) if max_count else ""
            lines.append(f"{label:8s} {count:4d} | {bar}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print a text chart of Nailong/Naiwa image distribution.")
    parser.add_argument("--split-dir", default="nailong_naiwa_splits")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print(render_text_chart(args.split_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
