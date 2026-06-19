import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

process.env.HOME ||= "C:/Users/hp";

const ROOT = process.cwd();
const SKILL_DIR =
  "C:/Users/hp/.codex/plugins/cache/openai-primary-runtime/presentations/26.614.11602/skills/presentations";
const {
  ensureArtifactToolWorkspace,
  importArtifactTool,
  createSlideContext,
  saveBlobToFile,
} = await import(pathToFileURL(path.join(SKILL_DIR, "scripts/artifact_tool_utils.mjs")).href);

const WORKSPACE = path.join(
  process.env.TEMP || process.env.TMP || "C:/Users/hp/AppData/Local/Temp",
  "codex-presentations",
  "manual-nailong-project-ppt",
);
const TMP_DIR = path.join(WORKSPACE, "tmp");
const PREVIEW_DIR = path.join(TMP_DIR, "preview");
const LAYOUT_DIR = path.join(TMP_DIR, "layout");
const QA_DIR = path.join(TMP_DIR, "qa");
const FINAL_PPTX = path.join(ROOT, "reports", "奶龙奶蛙图像分类项目汇报_v2.pptx");
const ASCII_PPTX = path.join(ROOT, "reports", "nailong_naiwa_project_presentation_v2.pptx");

await fs.mkdir(PREVIEW_DIR, { recursive: true });
await fs.mkdir(LAYOUT_DIR, { recursive: true });
await fs.mkdir(QA_DIR, { recursive: true });
await fs.mkdir(path.join(ROOT, "reports"), { recursive: true });

await ensureArtifactToolWorkspace(WORKSPACE);
const { Presentation, PresentationFile } = await importArtifactTool(WORKSPACE);

await fs.writeFile(
  path.join(TMP_DIR, "source-notes.txt"),
  [
    "Sources and provenance",
    "- video_project_introduction_script.md: background, narration, limitations, roadmap, timing.",
    "- Local git log on 2026-06-18: commit timeline and development process.",
    "- reports/algorithm_comparison.md: algorithm accuracy figures and confusion matrix summary.",
    "- README.md: supported UI features and project structure.",
    "- Local dataset images under nailong_naiwa_splits/test: illustrative sample images.",
  ].join("\n"),
  "utf8",
);

await fs.writeFile(
  path.join(TMP_DIR, "slide-plan.txt"),
  [
    "Mode: create",
    "Palette: #0B2545 deep navy, #F4C542 warm yellow, #F6F8FB light background, #23A455 green, #E85D4F coral.",
    "Fonts: Aptos Display for headings; Microsoft YaHei/Aptos for body.",
    "Slides: title, necessity, data samples, pipeline, UI features, algorithm results, commits, development story, limitations, roadmap.",
  ].join("\n"),
  "utf8",
);

const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const W = 1280;
const H = 720;
const C = {
  navy: "#0B2545",
  yellow: "#F4C542",
  bg: "#F6F8FB",
  white: "#FFFFFF",
  green: "#23A455",
  coral: "#E85D4F",
  ink: "#17202A",
  muted: "#617083",
  line: "#D9E0EA",
  softYellow: "#FFF5CE",
  paleBlue: "#EAF1FB",
};

function ctx() {
  return createSlideContext(null, {
    slideSize: { width: W, height: H },
    workspaceDir: WORKSPACE,
    outputDir: PREVIEW_DIR,
    assetDir: path.join(TMP_DIR, "assets"),
    titleFont: "Aptos Display",
    bodyFont: "Microsoft YaHei",
  });
}

function text(slide, x, y, w, h, value, size = 22, color = C.ink, bold = false, align = "left") {
  return ctx().addText(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    text: value,
    fontSize: size,
    color,
    bold,
    align,
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

function shape(slide, x, y, w, h, fill, line = "none", geometry = "rect") {
  return ctx().addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    geometry,
    fill,
    line: { style: "solid", fill: line === "none" ? "#00000000" : line, width: line === "none" ? 0 : 1 },
  });
}

function card(slide, x, y, w, h, fill = C.white, line = C.line) {
  return ctx().addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    geometry: "roundRect",
    fill,
    line: { style: "solid", fill: line, width: 1 },
    borderRadius: "rounded-xl",
  });
}

async function image(slide, imagePath, x, y, w, h, fit = "cover", alt = "") {
  return ctx().addImage(slide, { path: imagePath, left: x, top: y, width: w, height: h, fit, alt });
}

function header(slide, title, kicker = "Nailong / Naiwa Image Classifier") {
  slide.background.fill = C.bg;
  shape(slide, 0, 0, W, 70, C.navy);
  text(slide, 58, 22, 620, 28, kicker, 15, "#DCE8F7", true);
  text(slide, 58, 92, 780, 54, title, 34, C.navy, true);
  shape(slide, 58, 152, 88, 6, C.yellow);
}

function footer(slide, number) {
  text(slide, 1110, 674, 110, 24, String(number).padStart(2, "0"), 14, C.muted, true, "right");
}

const nailongImg = path.join(ROOT, "nailong_naiwa_splits", "test", "nailong", "021697702C6C435DB551A735B36A02ED_17.jpg");
const naiwaImg1 = path.join(ROOT, "nailong_naiwa_splits", "test", "naiwa", "naiwa_from_nailong_zip_001.jpg");
const naiwaImg2 = path.join(ROOT, "nailong_naiwa_splits", "test", "naiwa", "625e2cd7f56c3f5e991d0bed77ceb8d9bd5f659f.jpg");

{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  shape(slide, 0, 0, W, H, C.navy);
  card(slide, 742, 62, 405, 405, "#FFFFFF14", "#FFFFFF30");
  await image(slide, nailongImg, 780, 92, 330, 330, "cover", "nailong sample");
  text(slide, 72, 86, 640, 64, "奶龙还是奶蛙？", 58, C.white, true);
  text(slide, 76, 170, 680, 100, "一个图像分类项目的诞生", 42, C.yellow, true);
  text(
    slide,
    78,
    304,
    610,
    92,
    "从网络图片识别的必要性出发，完成数据整理、CNN 训练、Web 交互、算法对比与 GitHub 版本迭代。",
    24,
    "#DCE8F7",
  );
  card(slide, 78, 472, 250, 44, C.yellow, C.yellow);
  text(slide, 96, 482, 214, 26, "项目汇报 PPT", 20, C.navy, true, "center");
  text(slide, 78, 640, 660, 26, "PyTorch · Local Web UI · Algorithm Comparison · GitHub commits", 14, "#BFD0E6");
}

{
  const slide = presentation.slides.add();
  header(slide, "为什么这个项目是必要的？");
  const items = [
    ["图像是信息载体", "表情包、截图、角色图和二创内容，都需要被机器理解和管理。"],
    ["分类是第一步", "只有先判断“这是什么”，后面才有搜索、归档、清洗和推荐。"],
    ["奶龙 / 奶蛙是具体入口", "对象很可爱，但任务本质是让计算机从相似图片中提取差异。"],
  ];
  items.forEach((item, i) => {
    const x = 82 + i * 382;
    card(slide, x, 220, 330, 250, i === 1 ? C.softYellow : C.white);
    text(slide, x + 28, 248, 270, 42, item[0], 25, C.navy, true);
    text(slide, x + 28, 312, 270, 112, item[1], 20, C.ink);
    shape(slide, x + 28, 444, 70, 6, i === 1 ? C.navy : C.yellow);
  });
  text(slide, 92, 560, 1030, 48, "它不是“做着玩”的分类器，而是数据整理、功能扩展和智能分析的基础环节。", 26, C.navy, true, "center");
  footer(slide, 2);
}

{
  const slide = presentation.slides.add();
  header(slide, "数据来源与样例");
  text(slide, 84, 178, 1020, 46, "数据来自 GitHub 开源项目 spawner1145/NailongRecognize，以及从小红书等平台下载整理的图片。", 22);
  const samples = [
    [nailongImg, "奶龙样例", "典型外观清晰"],
    [naiwaImg1, "奶蛙样例", "场景复杂、风格多样"],
    [naiwaImg2, "奶蛙样例", "带文字与强背景效果"],
  ];
  for (let i = 0; i < samples.length; i += 1) {
    const x = 78 + i * 390;
    card(slide, x, 260, 342, 310);
    await image(slide, samples[i][0], x + 18, 278, 306, 210, "cover", samples[i][1]);
    text(slide, x + 24, 504, 290, 28, samples[i][1], 21, C.navy, true, "center");
    text(slide, x + 24, 536, 290, 26, samples[i][2], 15, C.muted, false, "center");
  }
  footer(slide, 3);
}

{
  const slide = presentation.slides.add();
  header(slide, "从图片到结果：项目流程");
  const steps = [
    ["收集数据", "GitHub + 小红书"],
    ["预处理", "水印弱化 / 数据增强"],
    ["划分数据", "train / test / generalization"],
    ["训练模型", "轻量级 CNN"],
    ["交互预测", "本地 Web UI"],
    ["输出报告", "准确率 / 混淆矩阵"],
  ];
  steps.forEach((step, i) => {
    const x = 82 + (i % 3) * 382;
    const y = 205 + Math.floor(i / 3) * 176;
    card(slide, x, y, 320, 112, i % 2 ? C.white : C.paleBlue);
    text(slide, x + 24, y + 24, 270, 30, step[0], 24, C.navy, true);
    text(slide, x + 24, y + 62, 270, 26, step[1], 17, C.muted);
    if (i < steps.length - 1 && i % 3 !== 2) shape(slide, x + 330, y + 52, 28, 6, C.yellow);
  });
  text(slide, 120, 600, 980, 38, "核心目标：把抽象算法变成可看、可点、可验证的识别流程。", 25, C.navy, true, "center");
  footer(slide, 4);
}

{
  const slide = presentation.slides.add();
  header(slide, "交互界面：让模型真正可用");
  card(slide, 82, 190, 520, 360);
  text(slide, 112, 222, 430, 34, "Web UI 功能", 27, C.navy, true);
  ["上传图片并预览", "选择 CNN 模型或传统算法", "显示预测类别与置信度条", "Compare all algorithms 横向对比", "接受正确结果并补充到数据集"].forEach((item, i) => {
    text(slide, 122, 288 + i * 48, 410, 28, `• ${item}`, 20);
  });
  card(slide, 665, 190, 475, 360, C.softYellow);
  text(slide, 700, 226, 380, 34, "演示时重点讲", 27, C.navy, true);
  text(slide, 700, 294, 380, 124, "用户看到的不只是一个冷冰冰的分类结果，还能知道模型这次到底有多确定。", 24, C.navy, true);
  text(slide, 700, 444, 360, 56, "本地地址：127.0.0.1:8770", 20, C.muted);
  footer(slide, 5);
}

{
  const slide = presentation.slides.add();
  header(slide, "算法对比：CNN 效果最好，但基线也有价值");
  slide.charts.add("bar", {
    position: { left: 94, top: 205, width: 660, height: 330 },
    categories: ["CNN balanced", "Thumbnail kNN", "RGB histogram", "Color mean", "Edge hist"],
    series: [{ name: "Accuracy", values: [90.24, 87.8, 85.37, 78.05, 58.54], fill: C.yellow }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd" },
    yAxis: { majorGridlines: { style: "solid", fill: "#E1E7EF", width: 1 } },
  });
  card(slide, 810, 210, 330, 292);
  text(slide, 838, 240, 270, 30, "测试集结果", 26, C.navy, true);
  text(slide, 840, 294, 250, 58, "37 / 41", 52, C.green, true, "center");
  text(slide, 842, 354, 250, 24, "CNN balanced 正确数", 18, C.muted, false, "center");
  text(slide, 840, 410, 250, 42, "准确率约 90.24%", 30, C.navy, true, "center");
  text(slide, 108, 596, 980, 38, "传统算法作为对照基线，帮助判断深度模型是否真正学到了有效特征。", 23, C.navy, true, "center");
  footer(slide, 6);
}

{
  const slide = presentation.slides.add();
  header(slide, "GitHub commits：从上传到完整流程");
  const commits = [
    ["2026-06-16", "Initial commit / Add files via upload", "项目开始上传，建立基础仓库。"],
    ["2026-06-16", "Add image datasets", "加入图像数据，为训练和测试打基础。"],
    ["2026-06-17", "Selectable algorithms + visualization", "加入算法选择与数据分布展示。"],
    ["2026-06-17", "Add algorithm comparison workflow", "形成批量算法对比与报告输出。"],
    ["2026-06-17", "Refresh project README", "完善 README，并加入 co-author 信息。"],
  ];
  shape(slide, 150, 238, 920, 4, C.line);
  commits.forEach((commit, i) => {
    const x = 150 + i * 230;
    shape(slide, x - 9, 230, 22, 22, i === 4 ? C.yellow : C.navy, C.white, "ellipse");
    text(slide, x - 64, 260, 150, 22, commit[0], 15, C.muted, false, "center");
    card(slide, x - 90, 298, 180, 180, i === 4 ? C.softYellow : C.white);
    text(slide, x - 72, 316, 146, 66, commit[1], 15, C.navy, true, "center");
    text(slide, x - 72, 398, 146, 62, commit[2], 14, C.ink, false, "center");
  });
  text(slide, 116, 580, 980, 54, "这条提交线对应了开发节奏：先传上去，再补数据、补界面、补算法对比，最后整理说明文档。", 23, C.navy, true, "center");
  footer(slide, 7);
}

{
  const slide = presentation.slides.add();
  header(slide, "开发过程：第一次完整上传，也是真的花了力气");
  const rows = [
    ["第一次完整上传 GitHub", "仓库结构、提交记录、README 和文件路径都需要边做边学。"],
    ["功能不是一次成型", "数据、模型、UI、算法对比是在多次 commit 中逐步补齐的。"],
    ["项目价值不只在模型", "完整经历了数据收集、训练、评估、展示和版本管理。"],
  ];
  rows.forEach((row, i) => {
    const y = 202 + i * 126;
    card(slide, 120, y, 1000, 88, i === 1 ? C.paleBlue : C.white);
    text(slide, 152, y + 22, 280, 28, row[0], 24, C.navy, true);
    text(slide, 472, y + 24, 590, 28, row[1], 20);
  });
  text(slide, 154, 600, 900, 36, "课程项目不只是让模型跑起来，也要让项目真正“交得出去、看得明白”。", 24, C.navy, true, "center");
  footer(slide, 8);
}

{
  const slide = presentation.slides.add();
  header(slide, "不足：清楚知道边界，才方便继续扩展");
  const limits = [
    ["数据量偏小", "测试集只有 41 张，准确率有偶然性。"],
    ["类别有限", "只能区分奶龙和奶蛙，不能处理无关图片。"],
    ["泛化仍需验证", "背景、水印、压缩质量都会影响判断。"],
    ["功能未完全实现", "云端数据库、历史记录、多人协作还没做完。"],
  ];
  limits.forEach((item, i) => {
    const x = 92 + (i % 2) * 565;
    const y = 205 + Math.floor(i / 2) * 160;
    card(slide, x, y, 500, 112, i === 3 ? "#FFF0ED" : C.white);
    text(slide, x + 28, y + 22, 420, 30, item[0], 25, i === 3 ? C.coral : C.navy, true);
    text(slide, x + 28, y + 62, 420, 28, item[1], 19);
  });
  text(slide, 132, 596, 960, 36, "时间原因让一些想法没能落地，但这些不足也正好指向后续优化方向。", 24, C.navy, true, "center");
  footer(slide, 9);
}

{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  text(slide, 72, 72, 760, 54, "下一步：从本地小工具走向在线识别系统", 42, C.white, true);
  shape(slide, 76, 150, 120, 7, C.yellow);
  const road = [
    ["扩数据", "更多来源、更多画质、更多背景"],
    ["查错样本", "整理易混淆图片，针对性补充训练"],
    ["强 UI", "批量预测、历史记录、人工修正"],
    ["上云端", "数据库保存上传、预测和标签记录"],
  ];
  road.forEach((item, i) => {
    const x = 92 + i * 286;
    card(slide, x, 258, 236, 180, "#FFFFFF10", "#FFFFFF30");
    text(slide, x + 26, 292, 180, 34, item[0], 30, C.yellow, true, "center");
    text(slide, x + 24, 352, 188, 60, item[1], 19, "#DCE8F7", false, "center");
  });
  text(slide, 116, 555, 1040, 70, "总结：项目虽然不大，但已经完成从数据准备、模型训练、单图预测、算法对比到报告输出的完整闭环。", 30, C.white, true, "center");
  text(slide, 380, 650, 520, 24, "谢谢观看", 22, C.yellow, true, "center");
}

for (const [index, slide] of presentation.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  await saveBlobToFile(await presentation.export({ slide, format: "png", scale: 1 }), path.join(PREVIEW_DIR, `${stem}.png`));
  await fs.writeFile(path.join(LAYOUT_DIR, `${stem}.layout.json`), await (await slide.export({ format: "layout" })).text(), "utf8");
}

await saveBlobToFile(await presentation.export({ format: "webp", montage: true, scale: 1 }), path.join(PREVIEW_DIR, "deck-montage.webp"));
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(FINAL_PPTX);
await fs.copyFile(FINAL_PPTX, ASCII_PPTX);
await fs.writeFile(
  path.join(QA_DIR, "visual-qa.txt"),
  [
    `Generated ${presentation.slides.items.length} rendered slide PNGs and a deck montage.`,
    "Initial automated generation used editable text, shapes, image objects, and a native chart.",
    "Human visual inspection should check Chinese text fitting, image crops, and timeline card density.",
  ].join("\n"),
  "utf8",
);

console.log(JSON.stringify({ FINAL_PPTX, ASCII_PPTX, PREVIEW_DIR, WORKSPACE, slides: presentation.slides.items.length }, null, 2));
