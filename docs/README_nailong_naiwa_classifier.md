# 奶龙 / 奶蛙识别器

本项目现在使用平衡实验数据训练二分类神经网络：

- `nailong`：从原始 345 张中随机抽取 100 张
- `naiwa`：使用 `nailong_naiwa_10_demo/naiwa_preprocessed` 中的 105 张去水印弱化图片

训练时使用：

- 方法 3：随机裁剪、翻转、旋转、颜色扰动等数据增强
- 方法 2：对 `nailong` 图片右下角随机模糊/遮挡，减少模型依赖水印或角落特征

## 数据目录

训练脚本会自动重建：

```text
nailong_naiwa_balanced_experiment/
  nailong/  # 100 张
  naiwa/    # 105 张

nailong_naiwa_splits/
  train/
  test/
  generalization/
```

当前拆分数量：

```text
train: nailong=60, naiwa=63
test: nailong=20, naiwa=21
generalization: nailong=20, naiwa=21
```

## 训练

```powershell
python train_nailong_naiwa.py --cpu --epochs 12 --repeats 3 --batch-size 16 --image-size 128 --print-every 3 --out models/nailong_naiwa_balanced_cnn.pt
```

已生成模型：

```text
models/nailong_naiwa_balanced_cnn.pt
```

这次快速 CPU 训练的最好测试集准确率为 `0.902`。

如果想训练更久，可以提高：

```powershell
python train_nailong_naiwa.py --cpu --epochs 60 --repeats 12 --batch-size 12 --out models/nailong_naiwa_balanced_cnn_long.pt
```

## 启动交互界面

```powershell
python predict_nailong_naiwa_ui.py --host 127.0.0.1 --port 8770 --cpu
```

然后打开：

```text
http://127.0.0.1:8770
```

界面功能：

- 从 `models/*.pt` 中选择不同模型
- 上传新图片并判断为 `nailong（奶龙）` 或 `naiwa（奶蛙）`
- 如果判断正确，点击按钮后会把图片随机复制到：
  - `nailong_naiwa_splits/train/<类别>`
  - `nailong_naiwa_splits/test/<类别>`
  - `nailong_naiwa_splits/generalization/<类别>`

入库是复制操作，不会删除上传的原图。
