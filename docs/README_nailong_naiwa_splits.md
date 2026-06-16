# Nailong / Naiwa Dataset Splits

分割目录：

```text
nailong_naiwa_splits/
  train/
    nailong/
    naiwa/
  test/
    nailong/
    naiwa/
  generalization/
    nailong/
    naiwa/
  split_manifest.csv
```

当前图片数量非常少，所以这是最小可用分割：

- `train`: 用来训练模型
- `test`: 用来做训练后的固定测试
- `generalization`: 用来放更接近真实新输入、不同来源或不同风格的图片

重新生成分割：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" create_nailong_naiwa_splits.py --source nailong_naiwa_10_demo --out nailong_naiwa_splits
```

只用训练集重新训练：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" -u train_nailong_naiwa.py --data nailong_naiwa_splits\train --out models\nailong_naiwa_split_cnn.pt --epochs 8 --repeats 6 --batch-size 4 --print-every 1 --cpu
```

评估测试集：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" evaluate_nailong_naiwa.py --model models\nailong_naiwa_split_cnn.pt --data nailong_naiwa_splits\test --cpu
```

评估泛化集：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" evaluate_nailong_naiwa.py --model models\nailong_naiwa_split_cnn.pt --data nailong_naiwa_splits\generalization --cpu
```

注意：如果后面继续爬图，建议每类至少准备：

- 训练集：50 张以上
- 测试集：10 张以上
- 泛化集：10 张以上，尽量来自不同网站、截图、表情包、照片背景或压缩质量
