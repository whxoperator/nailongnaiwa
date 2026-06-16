# 奶龙 / 奶蛙图像识别器

这是一个基于 PyTorch 的二分类图像识别小项目，用来判断一张输入图片更像 `nailong`（奶龙）还是 `naiwa`（奶蛙）。项目包含数据预处理、平衡采样、神经网络训练、模型保存与一个本地交互式网页界面。

## 功能简介

- 训练一个奶龙 / 奶蛙二分类卷积神经网络。
- 对奶蛙图片右下角常见水印进行弱化预处理。
- 从数量较多的奶龙数据中随机抽取 100 张，与奶蛙数据组成相对平衡的实验数据集。
- 自动拆分训练集、测试集和泛化集。
- 提供本地 Web 交互界面，可以上传新图片并选择不同模型进行判断。
- 如果模型判断正确，可以将新图片随机复制到训练集、测试集或泛化集，便于后续继续迭代数据集。

## 项目结构

```text
.
├── README.md
├── requirements.txt
├── nailong_model.py
├── train_nailong_naiwa.py
├── predict_nailong_naiwa_ui.py
├── preprocess_naiwa_watermarks.py
├── evaluate_nailong_naiwa.py
├── models/
│   └── nailong_naiwa_balanced_cnn.pt
├── nailong_naiwa_10_demo/
│   ├── nailong/                 # 奶龙原始图片
│   ├── naiwa/                   # 奶蛙原始图片
│   └── naiwa_preprocessed/      # 弱化水印后的奶蛙图片
├── nailong_naiwa_balanced_experiment/
│   ├── nailong/                 # 随机抽取的 100 张奶龙图片
│   └── naiwa/                   # 105 张预处理后的奶蛙图片
├── nailong_naiwa_splits/
│   ├── train/
│   ├── test/
│   └── generalization/
├── docs/                        # 实验报告和旧版说明文档
├── tools/                       # 数据采集、标注、报告生成等辅助工具
├── seeds/                       # 图片 URL 种子文件
└── raw_uploads/                 # 本地临时整理的原始图片
```

## 数据来源

本项目中的奶龙部分数据集来源于另一个 GitHub 仓库 `NailongRecognize-main`。在本实验中，因为奶龙图片数量远多于奶蛙图片，所以训练时没有全部使用，而是从奶龙图片中随机抽取 100 张用于实验。

奶蛙图片主要来自本地收集与整理。由于其中不少图片右下角带有平台水印，项目中额外提供了水印弱化预处理脚本。

当前实验使用的数据规模：

```text
nailong: 100 张
naiwa:   105 张
```

拆分后：

```text
train:          nailong=60, naiwa=63
test:           nailong=20, naiwa=21
generalization: nailong=20, naiwa=21
```

## 模型与实现

模型实现位于 `nailong_model.py`。

当前使用的是一个轻量级卷积神经网络 `SmallImageCNN`，主要结构包括：

- 多层 `Conv2d`
- `BatchNorm2d`
- `ReLU`
- `MaxPool2d`
- `AdaptiveAvgPool2d`
- `Dropout`
- 全连接分类层

输入图片会被缩放到固定尺寸，并进行归一化处理。模型最终输出两个类别的概率：

- `nailong`
- `naiwa`

训练时使用了以下增强策略：

- 随机裁剪
- 随机水平翻转
- 随机旋转
- 颜色扰动
- 对奶龙图片右下角进行随机模糊 / 遮挡

这样做的目的是减少模型依赖右下角水印或角落区域的可能性，让模型尽量学习主体本身的视觉特征。

## 水印预处理

奶蛙图片中有不少右下角水印。脚本 `preprocess_naiwa_watermarks.py` 会对图片右下区域进行检测和模糊填补，输出到：

```text
nailong_naiwa_10_demo/naiwa_preprocessed
```

运行：

```powershell
python preprocess_naiwa_watermarks.py
```

需要注意：这个处理只是为了降低训练时水印对模型的干扰，不是专业级图像修复。部分图片的水印仍然可能残留，或出现轻微模糊块。

## 训练模型

运行：

```powershell
python train_nailong_naiwa.py --cpu --epochs 12 --repeats 3 --batch-size 16 --image-size 128 --print-every 3 --out models/nailong_naiwa_balanced_cnn.pt
```

训练脚本会自动完成：

1. 从奶龙数据中随机抽取 100 张。
2. 使用预处理后的奶蛙图片。
3. 重建平衡实验集。
4. 拆分 `train`、`test`、`generalization`。
5. 训练模型并保存到 `models/`。

当前快速实验得到的最好测试集准确率约为：

```text
best test accuracy: 0.902
```

如果希望训练更久，可以提高 `epochs` 和 `repeats`：

```powershell
python train_nailong_naiwa.py --cpu --epochs 60 --repeats 12 --batch-size 12 --out models/nailong_naiwa_balanced_cnn_long.pt
```

如果电脑有 CUDA GPU，可以去掉 `--cpu`。

## 启动交互界面

运行：

```powershell
python predict_nailong_naiwa_ui.py --host 127.0.0.1 --port 8770 --cpu
```

然后打开：

```text
http://127.0.0.1:8770
```

界面支持：

- 从 `models/*.pt` 中选择不同模型。
- 上传一张新图片。
- 输出该图片属于 `nailong` 或 `naiwa` 的概率。
- 如果人工确认判断正确，可以点击按钮将图片随机加入：
  - `nailong_naiwa_splits/train/<类别>`
  - `nailong_naiwa_splits/test/<类别>`
  - `nailong_naiwa_splits/generalization/<类别>`

入库操作是复制图片，不会删除上传原图。

## 现有问题与局限性

这个项目目前仍然是一个小规模实验原型，存在以下局限：

1. **只能在奶龙和奶蛙之间二选一**

   当前模型是二分类模型。也就是说，无论输入什么图片，它都会强制判断为 `nailong` 或 `naiwa`。如果上传的图片既不是奶龙也不是奶蛙，例如普通动物、人物、风景或其他卡通形象，模型目前不能可靠地识别为“其他类别”。

2. **数据量仍然偏少**

   本次实验只使用了 100 张奶龙和 105 张奶蛙。对于深度学习模型来说，这个规模仍然较小，模型可能对图片风格、背景、角度和来源比较敏感。

3. **水印去除效果有限**

   奶蛙图片中右下角水印较多，当前预处理只是弱化水印，不是完全去除。部分图片仍可能保留水印痕迹，模型也可能学到一些与类别无关的边角特征。

4. **泛化能力还需要更多验证**

   当前测试集和泛化集规模都不大，准确率只能说明在现有数据划分上的表现。对于全新来源、无水印、不同画风或复杂背景的图片，效果可能下降。

5. **没有开放集识别能力**

   项目还没有实现置信度阈值、异常检测或 `unknown` 类别，因此不能判断“这张图不属于奶龙 / 奶蛙中的任何一类”。

6. **模型结构较轻量**

   当前模型是自定义小型 CNN，适合课程实验和快速验证。如果追求更高准确率，可以考虑使用迁移学习模型，例如 ResNet、MobileNet 或 EfficientNet。

## 后续改进方向

- 补充更多无水印、多角度、多背景的奶蛙图片。
- 增加 `unknown` 类别，使模型能够拒识不属于奶龙 / 奶蛙的图片。
- 使用迁移学习模型提升小数据集表现。
- 对水印区域进行更精细的标注和修复。
- 增加混淆矩阵、精确率、召回率等更完整的评估指标。
- 将交互界面改为更正式的 Web 应用或桌面应用。

## 相关文件说明

| 文件 | 作用 |
| --- | --- |
| `preprocess_naiwa_watermarks.py` | 弱化奶蛙图片右下角水印 |
| `nailong_model.py` | 模型结构、图像增强、模型保存与加载 |
| `train_nailong_naiwa.py` | 构建平衡数据集并训练模型 |
| `predict_nailong_naiwa_ui.py` | 本地交互式识别网页 |
| `docs/nailong_naiwa_report.pdf` | 实验报告 |
| `docs/README_nailong_naiwa_classifier.md` | 项目过程说明 |
| `tools/` | 数据采集、标注、报告生成等辅助工具 |
| `seeds/` | 图片 URL 种子文件 |

## 免责声明

本项目主要用于学习和实验，不适合作为生产级识别系统直接使用。数据来源、图片版权和模型输出结果请根据实际使用场景自行确认。
