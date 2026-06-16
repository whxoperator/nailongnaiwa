# Remote Dataset Collection Site

这个版本适合部署到云服务器，而不是把你的电脑暴露给别人。

功能：

- 公开上传页：别人上传奶龙/奶蛙候选图片
- 管理员审核页：你把图片分为 `奶龙`、`奶蛙` 或 `拒绝`
- 自动随机进入 `train`、`test`、`generalization`
- 自动去重
- 保存上传记录和数据集记录

目录结构：

```text
remote_collection_data/
  pending/
  rejected/
  dataset/
    train/
      nailong/
      naiwa/
    test/
      nailong/
      naiwa/
    generalization/
      nailong/
      naiwa/
  uploads.csv
  dataset_manifest.csv
```

本地测试启动：

```powershell
& "C:\Users\hp\AppData\Local\Programs\Python\Python312\python.exe" remote_dataset_collection_site.py --admin-token "change-this-token" --port 8790
```

公开上传页：

```text
http://127.0.0.1:8790
```

管理员审核页：

```text
http://127.0.0.1:8790/admin?token=change-this-token
```

部署建议：

- 不建议直接暴露自己的电脑。
- 推荐放到云服务器、学校服务器、Render、Railway、Fly.io 或 VPS。
- 正式部署时应使用 HTTPS，并把 `--admin-token` 换成随机长字符串。
- 上传目录需要持久化存储，否则平台重启可能丢数据。
- 如果访问量较大，后续应换成对象存储，例如 S3、R2、OSS、COS。
