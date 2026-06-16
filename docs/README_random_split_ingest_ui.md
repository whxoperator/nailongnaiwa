# Random Split Ingest UI

这个本地网站用于把新图片加入数据集：

1. 上传图片
2. 预览确认
3. 点击 `正样本` 或 `负样本`
4. 自动随机保存到 `train`、`test` 或 `generalization`

默认输出目录：

```text
random_split_dataset/
  train/
    nailong/
    naiwa/
  test/
    nailong/
    naiwa/
  generalization/
    nailong/
    naiwa/
  manifest.csv
```

启动：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" random_split_ingest_ui.py --out random_split_dataset --positive-name nailong --negative-name naiwa --port 8780
```

然后打开：

```text
http://127.0.0.1:8780
```

默认随机比例：

- `train`: 70%
- `test`: 15%
- `generalization`: 15%

可以自定义：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" random_split_ingest_ui.py --train-ratio 0.75 --test-ratio 0.15 --generalization-ratio 0.10
```
