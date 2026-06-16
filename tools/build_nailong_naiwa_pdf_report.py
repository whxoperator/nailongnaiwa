from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin


OUT_PDF = Path("nailong_naiwa_report.pdf")
OUT_DIR = Path("report_pages")
PAGE_W, PAGE_H = 1650, 2134
MARGIN_X = 150
MARGIN_TOP = 120
MARGIN_BOTTOM = 110
BLUE = (46, 116, 181)
DARK = (11, 37, 69)
MUTED = (102, 112, 133)
TEXT = (30, 41, 59)
LIGHT = (246, 247, 249)
GRID = (208, 213, 221)
HEADER_FILL = (242, 244, 247)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\simhei.ttf" if bold else r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\Dengb.ttf" if bold else r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
    ]
    for item in candidates:
        path = Path(item)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT_TITLE = font(44, True)
FONT_SUBTITLE = font(25)
FONT_H1 = font(31, True)
FONT_H2 = font(25, True)
FONT_BODY = font(23)
FONT_BODY_BOLD = font(23, True)
FONT_SMALL = font(20)
FONT_TABLE = font(20)
FONT_TABLE_BOLD = font(20, True)


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        current = ""
        for char in para:
            if text_width(draw, current + char, fnt) <= width:
                current += char
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        if not para:
            lines.append("")
    return lines


class Report:
    def __init__(self) -> None:
        self.pages: list[Image.Image] = []
        self.new_page()

    def new_page(self) -> None:
        self.image = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.y = MARGIN_TOP
        self.page_no = len(self.pages) + 1
        self.draw_footer()

    def draw_footer(self) -> None:
        self.draw.line((MARGIN_X, PAGE_H - 82, PAGE_W - MARGIN_X, PAGE_H - 82), fill=(230, 234, 240), width=2)
        footer = f"奶龙 / 奶蛙识别实验报告    第 {self.page_no} 页"
        self.draw.text((PAGE_W - MARGIN_X - text_width(self.draw, footer, FONT_SMALL), PAGE_H - 62), footer, font=FONT_SMALL, fill=MUTED)

    def commit(self) -> None:
        self.pages.append(self.image)

    def ensure(self, height: int) -> None:
        if self.y + height > PAGE_H - MARGIN_BOTTOM:
            self.commit()
            self.new_page()

    def title_page(self) -> None:
        title = "奶龙 / 奶蛙图像识别神经网络实验报告"
        subtitle = "数据预处理、平衡采样、训练增强与交互式识别系统"
        self.draw.text(((PAGE_W - text_width(self.draw, title, FONT_TITLE)) // 2, 220), title, font=FONT_TITLE, fill=DARK)
        self.draw.text(((PAGE_W - text_width(self.draw, subtitle, FONT_SUBTITLE)) // 2, 292), subtitle, font=FONT_SUBTITLE, fill=MUTED)
        self.y = 390
        self.callout("本实验完成了从数据整理、去水印弱化、平衡采样、神经网络训练到网页交互识别的完整流程。最终生成的新模型 best test accuracy 为 0.902。")
        self.kv_table([
            ("项目路径", r"D:\nndl\nailong"),
            ("任务目标", "识别图片属于 nailong（奶龙）还是 naiwa（奶蛙）"),
            ("最终模型", "models/nailong_naiwa_balanced_cnn.pt"),
            ("交互界面", "http://127.0.0.1:8770"),
            ("报告日期", "2026-06-16"),
        ])

    def h1(self, text: str) -> None:
        self.ensure(70)
        self.y += 20
        self.draw.text((MARGIN_X, self.y), text, font=FONT_H1, fill=BLUE)
        self.y += 52

    def h2(self, text: str) -> None:
        self.ensure(55)
        self.y += 12
        self.draw.text((MARGIN_X, self.y), text, font=FONT_H2, fill=BLUE)
        self.y += 44

    def para(self, text: str) -> None:
        lines = wrap_text(self.draw, text, FONT_BODY, PAGE_W - 2 * MARGIN_X)
        self.ensure(len(lines) * 34 + 20)
        for line in lines:
            self.draw.text((MARGIN_X, self.y), line, font=FONT_BODY, fill=TEXT)
            self.y += 34
        self.y += 10

    def bullets(self, items: list[str]) -> None:
        for item in items:
            lines = wrap_text(self.draw, item, FONT_BODY, PAGE_W - 2 * MARGIN_X - 45)
            self.ensure(len(lines) * 34 + 8)
            self.draw.text((MARGIN_X + 8, self.y), "-", font=FONT_BODY_BOLD, fill=BLUE)
            for idx, line in enumerate(lines):
                self.draw.text((MARGIN_X + 45, self.y), line, font=FONT_BODY, fill=TEXT)
                self.y += 34
            self.y += 6

    def steps(self, items: list[str]) -> None:
        for idx, item in enumerate(items, 1):
            prefix = f"{idx}."
            lines = wrap_text(self.draw, item, FONT_BODY, PAGE_W - 2 * MARGIN_X - 55)
            self.ensure(len(lines) * 34 + 8)
            self.draw.text((MARGIN_X + 5, self.y), prefix, font=FONT_BODY_BOLD, fill=BLUE)
            for line in lines:
                self.draw.text((MARGIN_X + 55, self.y), line, font=FONT_BODY, fill=TEXT)
                self.y += 34
            self.y += 6

    def callout(self, text: str) -> None:
        lines = wrap_text(self.draw, text, FONT_BODY_BOLD, PAGE_W - 2 * MARGIN_X - 70)
        height = len(lines) * 36 + 42
        self.ensure(height + 22)
        x1, y1 = MARGIN_X, self.y
        x2, y2 = PAGE_W - MARGIN_X, self.y + height
        self.draw.rounded_rectangle((x1, y1, x2, y2), radius=10, fill=LIGHT, outline=(229, 231, 235), width=2)
        yy = y1 + 22
        for line in lines:
            self.draw.text((x1 + 28, yy), line, font=FONT_BODY_BOLD, fill=(31, 58, 95))
            yy += 36
        self.y = y2 + 24

    def kv_table(self, rows: list[tuple[str, str]]) -> None:
        self.table(["项目", "内容"], [[a, b] for a, b in rows], [360, PAGE_W - 2 * MARGIN_X - 360])

    def table(self, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
        x = MARGIN_X
        row_heights = []
        all_rows = [headers] + rows
        for row in all_rows:
            max_lines = 1
            for idx, cell in enumerate(row):
                fnt = FONT_TABLE_BOLD if row is headers else FONT_TABLE
                max_lines = max(max_lines, len(wrap_text(self.draw, str(cell), fnt, widths[idx] - 28)))
            row_heights.append(max(54, max_lines * 28 + 24))
        total_h = sum(row_heights)
        self.ensure(total_h + 30)
        yy = self.y
        for ridx, row in enumerate(all_rows):
            xx = x
            fill = HEADER_FILL if ridx == 0 else WHITE
            for cidx, cell in enumerate(row):
                w = widths[cidx]
                self.draw.rectangle((xx, yy, xx + w, yy + row_heights[ridx]), fill=fill, outline=GRID, width=2)
                fnt = FONT_TABLE_BOLD if ridx == 0 else FONT_TABLE
                lines = wrap_text(self.draw, str(cell), fnt, w - 28)
                ty = yy + 14
                for line in lines:
                    self.draw.text((xx + 14, ty), line, font=fnt, fill=TEXT)
                    ty += 28
                xx += w
            yy += row_heights[ridx]
        self.y = yy + 28


def build() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    report = Report()
    report.title_page()

    report.h1("1. 实验背景与目标")
    report.para("本实验面向奶龙与奶蛙两类图像的二分类识别任务。原始数据中，奶龙图片数量明显多于奶蛙图片，且奶蛙图片右下角普遍存在平台水印。若直接训练，模型容易学习到类别无关的水印特征，而不是主体外观特征。")
    report.para("因此，本次工作重点不是单纯训练一个模型，而是建立一套更稳健的数据处理与反馈闭环：先弱化水印影响，再通过平衡采样和数据增强训练模型，最后提供可选择模型的交互界面，并支持将人工确认正确的新图片继续纳入数据集。")

    report.h1("2. 数据整理与预处理")
    report.table(["数据项", "数量 / 路径", "说明"], [
        ["原始 nailong 图片", "345 张", "来自 nailong_naiwa_10_demo/nailong"],
        ["实验 nailong 图片", "100 张", "从 345 张中按随机种子抽样，避免类别不平衡"],
        ["原始 naiwa 图片", "105 张", "来自 nailong_naiwa_10_demo/naiwa"],
        ["预处理 naiwa 图片", "105 张", "输出到 nailong_naiwa_10_demo/naiwa_preprocessed"],
    ], [350, 420, 580])
    report.h2("2.1 水印弱化处理")
    report.para("奶蛙图片右下角存在较多水印。预处理脚本 preprocess_naiwa_watermarks.py 对右下区域建立遮罩，并使用局部平滑与模糊填补方式弱化水印。该处理保留原图不变，另存为 naiwa_preprocessed，用于后续训练。")
    report.bullets([
        "输入目录：nailong_naiwa_10_demo/naiwa",
        "输出目录：nailong_naiwa_10_demo/naiwa_preprocessed",
        "预览文件：nailong_naiwa_10_demo/naiwa_watermark_preview.jpg",
        "目的：减少模型把平台水印等角落特征误学为 naiwa 类别特征的风险。",
    ])
    report.h2("2.2 平衡采样与数据拆分")
    report.para("由于 nailong 图片远多于 naiwa 图片，本次实验按要求只从 nailong 中随机抽取 100 张，与 105 张 naiwa 预处理图片组成平衡实验集。随后将两类图片分别随机拆分为训练集、测试集和泛化集。")
    report.table(["集合", "nailong", "naiwa", "用途"], [
        ["train", "60", "63", "模型训练"],
        ["test", "20", "21", "训练过程中的测试评估"],
        ["generalization", "20", "21", "额外泛化观察"],
        ["合计", "100", "105", "平衡实验集"],
    ], [280, 220, 220, 630])

    report.h1("3. 模型与训练方法")
    report.para("模型使用 PyTorch 实现的小型卷积神经网络 SmallImageCNN。该模型由多层卷积、BatchNorm、ReLU、池化和全局平均池化组成，最后使用 Dropout 与线性分类层输出两个类别概率。")
    report.table(["方法", "实现位置", "作用"], [
        ["方法 3：通用数据增强", "nailong_model.py / ClassAwareImageFolder", "随机裁剪、翻转、旋转、颜色扰动，提高小数据集泛化能力"],
        ["方法 2：右下角随机遮挡/模糊", "nailong_model.py / RandomCornerOcclusion", "对 nailong 训练图也扰动右下角，降低模型依赖角落水印特征的可能性"],
        ["类别平衡", "train_nailong_naiwa.py", "只使用 100 张 nailong，与 105 张 naiwa 保持接近"],
        ["标签平滑", "train_nailong_naiwa.py", "CrossEntropyLoss(label_smoothing=0.04)，降低过拟合"],
    ], [340, 450, 560])
    report.kv_table([
        ("训练命令", "python train_nailong_naiwa.py --cpu --epochs 12 --repeats 3 --batch-size 16 --image-size 128 --print-every 3 --out models/nailong_naiwa_balanced_cnn.pt"),
        ("设备", "CPU"),
        ("训练轮数", "12 epochs"),
        ("批大小", "16"),
        ("图像尺寸", "128 x 128"),
        ("输出模型", "models/nailong_naiwa_balanced_cnn.pt"),
    ])

    report.h1("4. 实验结果")
    report.para("本次训练在 CPU 上完成，训练脚本会保存测试集准确率最高的模型状态。快速实验的最佳测试集准确率为 0.902。")
    report.table(["Epoch", "Loss", "Train Acc", "Test Acc", "Gen Acc"], [
        ["1 / 12", "0.5991", "0.659", "0.780", "0.732"],
        ["3 / 12", "0.4905", "0.770", "0.854", "0.951"],
        ["6 / 12", "0.4849", "0.791", "0.902", "0.927"],
        ["9 / 12", "0.4233", "0.856", "0.878", "0.927"],
        ["12 / 12", "0.4137", "0.854", "0.854", "0.902"],
    ], [260, 260, 280, 280, 270])
    report.callout("结论：在平衡采样和增强策略下，模型已经可以作为奶龙 / 奶蛙识别实验原型使用。由于数据量仍有限，后续继续补充无水印、多角度、多背景图片会进一步提升可靠性。")

    report.h1("5. 交互式识别界面")
    report.para("交互界面由 predict_nailong_naiwa_ui.py 提供，启动后会读取 models 目录下的 .pt 模型文件。用户可以选择不同模型，上传新图片，查看预测类别与概率。如果用户确认判断正确，界面会把该图片随机复制到 train、test 或 generalization 对应类别目录。")
    report.steps([
        "运行命令：python predict_nailong_naiwa_ui.py --host 127.0.0.1 --port 8770 --cpu",
        "在浏览器打开 http://127.0.0.1:8770。",
        "选择模型并上传新图片。",
        "查看 nailong（奶龙）与 naiwa（奶蛙）的概率结果。",
        "如果判断正确，点击“判断正确，随机加入数据集”。",
    ])
    report.table(["功能", "说明"], [
        ["多模型选择", "兼容当前新模型和旧模型，可从 models/*.pt 选择"],
        ["预测展示", "显示预测类别、中文类别名和两个类别概率"],
        ["人工确认入库", "确认正确后复制图片，不删除原上传文件"],
        ["随机归类", "按权重随机进入 train / test / generalization"],
    ], [360, 990])

    report.h1("6. 覆盖与新增的主要文件")
    report.table(["文件", "作用"], [
        ["preprocess_naiwa_watermarks.py", "批量弱化 naiwa 图片右下角水印，输出 naiwa_preprocessed"],
        ["nailong_model.py", "模型结构、图像增强、预测变换、模型保存与加载"],
        ["train_nailong_naiwa.py", "平衡采样、数据拆分、训练与评估"],
        ["predict_nailong_naiwa_ui.py", "交互式网页识别与人工确认入库"],
        ["README_nailong_naiwa_classifier.md", "中文使用说明与实验记录"],
    ], [520, 830])

    report.h1("7. 风险与后续改进建议")
    report.bullets([
        "数据量仍然偏小，建议继续补充更多无水印、不同角度、不同背景的奶蛙图片。",
        "当前去水印是训练友好的弱化处理，不等同于精修级图像修复。",
        "如果后续加入更多图片，应重新运行训练脚本，生成新的模型版本并在交互界面中比较。",
        "建议额外保留一批完全未参与训练和调参的真实新图片，作为最终人工验收集。",
        "若有 GPU，可提高 epochs 和 repeats，训练更充分的模型版本。",
    ])

    report.h1("8. 总结")
    report.para("本次工作已经完成可运行的奶龙 / 奶蛙图像识别原型：数据经过水印弱化和平衡采样，训练阶段加入了通用增强与右下角扰动，模型达到 0.902 的最佳测试集准确率，并提供了可选择模型、可反馈入库的交互式网页界面。该系统已经具备继续迭代数据和模型的基础闭环。")

    report.commit()
    for idx, page in enumerate(report.pages, 1):
        page.save(OUT_DIR / f"page_{idx:02d}.png")
    report.pages[0].save(OUT_PDF, save_all=True, append_images=report.pages[1:], resolution=150.0)
    print(f"saved {OUT_PDF} with {len(report.pages)} pages")


if __name__ == "__main__":
    build()
