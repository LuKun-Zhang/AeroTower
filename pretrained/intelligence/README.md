# 正式小模型清单

Git只保存本目录的清单、来源与许可证。权重、训练条件快照、评估报告通过[GitHub Release](https://github.com/LuKun-Zhang/AeroTower/releases/tag/phase2-models-81860180)交付，固定版本为`818601802430426e9e0694555437d6c0`。

在项目环境准备完成后运行：

```powershell
.\.venv\Scripts\python.exe -B scripts/download_pretrained.py
.\.venv\Scripts\python.exe -B scripts/install_pretrained.py
```

下载器固定ZIP的SHA-256，安装器核对manifest.json中的逐文件校验值和运行库版本。默认不覆盖已有不同模型；需要切换时的备份步骤见[交接说明](../../docs/HANDOFF.md)。joblib只加载本项目可信来源并校验过的模型包。

Qwen2.5-1.5B权重另从官方固定修订下载，不在此Release中。数据来源及许可见[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
