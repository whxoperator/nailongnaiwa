# 工具脚本目录

这里放置非核心运行路径的辅助脚本。

- `build_nailong_naiwa_pdf_report.py`：生成 PDF 实验报告。
- `build_nailong_naiwa_report.py`：生成 DOCX 实验报告。
- `create_nailong_naiwa_splits.py`：旧版数据集拆分脚本。
- `image_dataset_labeler.py`、`interactive_image_dataset.py`、`web_image_labeler.py`：图片采集和标注工具。
- `random_split_ingest_ui.py`、`remote_dataset_collection_site.py`：早期数据收集和随机拆分相关工具。

核心训练和预测入口仍保留在项目根目录：

- `train_nailong_naiwa.py`
- `predict_nailong_naiwa_ui.py`
- `nailong_model.py`
