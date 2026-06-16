import csv
import html
import io
import pathlib
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

try:
    import requests
except ImportError:
    requests = None

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = None
    ImageOps = None
    ImageTk = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass
class ImageCandidate:
    url: str
    image: Image.Image


def search_bing_image_urls(query: str, limit: int) -> list[str]:
    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://www.bing.com/images/search?q={encoded}&form=HDRSC3&first=1"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(search_url, headers=headers, timeout=20)
    response.raise_for_status()

    html_text = response.text
    patterns = [
        r'"murl":"(.*?)"',
        r"murl&quot;:&quot;(.*?)&quot;",
    ]

    found_urls: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.findall(pattern, html_text):
            url = html.unescape(match).replace("\\/", "/")
            if not url.startswith("http"):
                continue
            if url in seen:
                continue
            seen.add(url)
            found_urls.append(url)
            if len(found_urls) >= limit:
                return found_urls

    return found_urls


def download_candidate(url: str) -> ImageCandidate | None:
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.bing.com/"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        image.load()
        return ImageCandidate(url=url, image=image)
    except Exception:
        return None


def prepare_preview(image: Image.Image, max_size: tuple[int, int]) -> ImageTk.PhotoImage:
    preview = image.copy()
    preview = ImageOps.exif_transpose(preview)
    preview.thumbnail(max_size)
    if preview.mode not in ("RGB", "RGBA"):
        preview = preview.convert("RGB")
    return ImageTk.PhotoImage(preview)


class LabelerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Dataset Labeler")
        self.root.geometry("1100x800")

        self.dataset_dir = pathlib.Path.cwd() / "dataset"
        self.dataset_dir.mkdir(exist_ok=True)
        (self.dataset_dir / "positive").mkdir(exist_ok=True)
        (self.dataset_dir / "negative").mkdir(exist_ok=True)
        self.csv_path = self.dataset_dir / "labels.csv"
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["filename", "label", "source_url", "query", "saved_at"])

        self.query = ""
        self.target_count = 30
        self.image_urls: list[str] = []
        self.current_index = -1
        self.current_candidate: ImageCandidate | None = None
        self.current_preview: ImageTk.PhotoImage | None = None
        self.saved_positive = 0
        self.saved_negative = 0
        self.skipped = 0

        self.build_ui()
        self.ask_startup_options()

    def build_ui(self) -> None:
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=12, pady=12)

        self.info_label = tk.Label(
            top_frame,
            text="准备中...",
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 11),
        )
        self.info_label.pack(fill="x")

        self.image_label = tk.Label(self.root, bg="#f2f2f2")
        self.image_label.pack(fill="both", expand=True, padx=12, pady=12)

        button_frame = tk.Frame(self.root)
        button_frame.pack(fill="x", padx=12, pady=(0, 12))

        tk.Button(button_frame, text="正样本 (A)", width=18, command=self.mark_positive).pack(
            side="left", padx=5
        )
        tk.Button(button_frame, text="负样本 (D)", width=18, command=self.mark_negative).pack(
            side="left", padx=5
        )
        tk.Button(button_frame, text="跳过 (S)", width=18, command=self.skip_current).pack(
            side="left", padx=5
        )
        tk.Button(button_frame, text="重新搜索", width=18, command=self.ask_startup_options).pack(
            side="right", padx=5
        )
        tk.Button(button_frame, text="修改保存目录", width=18, command=self.choose_dataset_dir).pack(
            side="right", padx=5
        )

        self.root.bind("<a>", lambda event: self.mark_positive())
        self.root.bind("<A>", lambda event: self.mark_positive())
        self.root.bind("<d>", lambda event: self.mark_negative())
        self.root.bind("<D>", lambda event: self.mark_negative())
        self.root.bind("<s>", lambda event: self.skip_current())
        self.root.bind("<S>", lambda event: self.skip_current())

    def choose_dataset_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.dataset_dir))
        if not selected:
            return
        self.dataset_dir = pathlib.Path(selected)
        self.dataset_dir.mkdir(exist_ok=True)
        (self.dataset_dir / "positive").mkdir(exist_ok=True)
        (self.dataset_dir / "negative").mkdir(exist_ok=True)
        self.csv_path = self.dataset_dir / "labels.csv"
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["filename", "label", "source_url", "query", "saved_at"])
        self.refresh_info("保存目录已更新。")

    def ask_startup_options(self) -> None:
        query = simpledialog.askstring("搜索关键词", "输入你要抓取的图片关键词，例如：猫、nailong、dog")
        if not query:
            self.refresh_info("没有输入关键词。")
            return

        count = simpledialog.askinteger(
            "抓取数量",
            "每轮大约抓取多少张候选图片？",
            initialvalue=30,
            minvalue=1,
            maxvalue=500,
        )
        if not count:
            self.refresh_info("没有输入抓取数量。")
            return

        self.query = query.strip()
        self.target_count = count
        self.saved_positive = 0
        self.saved_negative = 0
        self.skipped = 0
        self.fetch_results()

    def fetch_results(self) -> None:
        self.refresh_info(f"正在搜索：{self.query}")
        self.root.update_idletasks()
        try:
            self.image_urls = search_bing_image_urls(self.query, self.target_count)
        except Exception as exc:
            messagebox.showerror("搜索失败", f"无法抓取图片链接：\n{exc}")
            self.refresh_info("搜索失败。")
            return

        if not self.image_urls:
            messagebox.showwarning("没有结果", "没有拿到图片链接，建议换一个关键词再试。")
            self.refresh_info("没有搜索结果。")
            return

        self.current_index = -1
        self.load_next_candidate()

    def load_next_candidate(self) -> None:
        self.current_candidate = None
        self.current_preview = None

        while True:
            self.current_index += 1
            if self.current_index >= len(self.image_urls):
                self.image_label.configure(image="", text="")
                self.refresh_info("这一轮图片已经标完了，可以重新搜索。")
                return

            url = self.image_urls[self.current_index]
            self.refresh_info(
                f"正在下载第 {self.current_index + 1}/{len(self.image_urls)} 张候选图..."
            )
            self.root.update_idletasks()
            candidate = download_candidate(url)
            if candidate is None:
                continue

            self.current_candidate = candidate
            self.current_preview = prepare_preview(candidate.image, (1000, 650))
            self.image_label.configure(image=self.current_preview, text="")
            self.refresh_info(self.current_status_text())
            return

    def current_status_text(self) -> str:
        return (
            f"关键词：{self.query} | 当前：{self.current_index + 1}/{len(self.image_urls)} | "
            f"正样本：{self.saved_positive} | 负样本：{self.saved_negative} | 跳过：{self.skipped} | "
            f"快捷键：A=正样本, D=负样本, S=跳过"
        )

    def refresh_info(self, text: str) -> None:
        self.info_label.configure(text=f"{text}\n数据集目录：{self.dataset_dir}")

    def save_current(self, label: str) -> None:
        if self.current_candidate is None:
            return

        filename = f"{self.query}_{int(time.time() * 1000)}_{self.current_index:04d}.jpg"
        target_path = self.dataset_dir / label / filename

        image = ImageOps.exif_transpose(self.current_candidate.image)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        image.save(target_path, format="JPEG", quality=95)

        with self.csv_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    str(target_path),
                    label,
                    self.current_candidate.url,
                    self.query,
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )

        if label == "positive":
            self.saved_positive += 1
        else:
            self.saved_negative += 1

        self.load_next_candidate()

    def mark_positive(self) -> None:
        self.save_current("positive")

    def mark_negative(self) -> None:
        self.save_current("negative")

    def skip_current(self) -> None:
        if self.current_candidate is None:
            return
        self.skipped += 1
        self.load_next_candidate()


def check_dependencies() -> None:
    missing = []
    if requests is None:
        missing.append("requests")
    if Image is None:
        missing.append("pillow")

    if missing:
        packages = " ".join(missing)
        message = (
            "缺少依赖："
            f"{', '.join(missing)}\n\n"
            f"请先运行：\npython -m pip install {packages}"
        )
        print(message)
        raise SystemExit(1)


def main() -> None:
    check_dependencies()
    root = tk.Tk()
    app = LabelerApp(root)
    if not app.query:
        root.mainloop()
        return
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
