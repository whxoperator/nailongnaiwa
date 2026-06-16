# Interactive Image Dataset Tool

这个小工具会按关键词爬取图片，下载每张候选图后用系统默认图片查看器打开，然后在终端里问你是正样本还是负样本。

## 运行

```powershell
python interactive_image_dataset.py --query "你的关键词" --max 100 --out dataset
```

如果 Windows 上 `python` 不指向 Python 3.12，可以用：

```powershell
py -3.12 interactive_image_dataset.py --query "你的关键词" --max 100 --out dataset
```

当前这台电脑还能直接使用 Anaconda 自带的 Python：

```powershell
& "C:\Users\hp\Anaconda3\python.exe" interactive_image_dataset.py --query "你的关键词" --max 100 --out dataset
```

## 标注按键

- `p`: 保存为正样本，进入 `dataset/positive`
- `n`: 保存为负样本，进入 `dataset/negative`
- `s`: 跳过当前图片
- `q`: 退出

每次保存时，工具也会更新 `dataset/manifest.csv`，记录文件名、标签、来源 URL、搜索关键词和保存时间。

## 自定义目录名

```powershell
python interactive_image_dataset.py --query "安全帽 工人" --max 200 --out my_dataset --positive-name pos --negative-name neg
```

## 用自己的图片 URL 列表

创建一个文本文件，例如 `urls.txt`，每行一个图片地址，然后运行：

```powershell
python interactive_image_dataset.py --urls-file urls.txt --max 50 --out dataset
```

## 注意

搜索引擎页面结构可能变化，所以关键词爬取不是永久稳定的。如果之后抓不到图，可以继续用 `--urls-file` 模式，或者再把搜索源换成带 API 的图片服务。
