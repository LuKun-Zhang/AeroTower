# 第二步改造：同学接手与模型恢复

源码分支交付程序、模型清单、下载脚本以及可公开演示证据；正式小模型通过GitHub Release交付。原调度算法继续执行方案，模型只预测和建议，语言草稿必须人工确认。

## 需要拿到什么

| 内容 | 位置 | 处理方式 |
| --- | --- | --- |
| 源码和版本锁 | backend、demo、scripts、tests | 从功能分支或合并后的main获取 |
| 正式小模型包 | [phase2-models-81860180 Release](https://github.com/LuKun-Zhang/AeroTower/releases/tag/phase2-models-81860180) | 含延误、恢复、排班、客流模型及评测；脚本校验下载，只恢复这一版，无需重训 |
| Qwen2.5-1.5B-Instruct | 不随Git提交 | 用scripts/download_language_model.py下载官方固定修订，权重约3.09GB |
| 实际演示与评测 | docs/intelligence-evidence/index.html | 浏览器打开，包含10张实际运行截图和公开检查摘要 |

模型包不是整个data目录的备份，不包含账户资料、私人开发记录、依赖、缓存、历次实验及旧模型。

## 第一次准备环境

本次验证环境是Windows、Python3.12.14、Node24.13.0/npm11.6.2。小模型反序列化需要匹配版本，完整依赖见Windows锁文件；其它平台没有实测。

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-windows.lock.txt
cd demo
npm ci
cd ..
.\.venv\Scripts\python.exe -B scripts/download_pretrained.py
.\.venv\Scripts\python.exe -B scripts/install_pretrained.py
.\.venv\Scripts\python.exe -B scripts/download_language_model.py
```

下载器校验固定Release ZIP的大小和SHA-256，解压缓存到.artifacts/pretrained/intelligence-81860180；安装器再校验清单及每个文件，然后恢复到data/intelligence。已有内容相同则跳过；已有不同模型或语言评测时默认拒绝覆盖，不删除旧模型或历史。离线交接可复制Release的ZIP，再执行`download_pretrained.py --archive ZIP的本地路径`，校验规则相同。

若确实要切换到Release模型包，先停止服务，再明确执行：

```powershell
.\.venv\Scripts\python.exe -B scripts/install_pretrained.py --activate
```

此时只备份并更新当前模型指针和语言评测，备份位于data/intelligence/import-backups；旧模型目录和实验记录保留。已存在但内容不同的同版本权重仍不会被覆盖，应先查明原因。

Qwen下载会校验官方固定修订的权重。若同学通过本地介质复制已验证的完整Qwen目录，应保留配置、分词器和LICENSE，再运行下载脚本复核，不需要重新下载已经完整且匹配的文件。其它来源模型不要混用本次成绩。

## 启动与第一次核对

1. 双击启动智能调度.cmd，打开 http://127.0.0.1:8080/#/intelligence，原演示账号密码均为user1。
2. 确认模型版本和模型评估可见。正式小模型版本为818601802430426e9e0694555437d6c0；其中的成绩来自交付机器，不自动代表你的电脑已验证。
3. 输入“下周成都基地，客流涨两成，加一场雷暴”，核对草稿再填入表单，最后确认运行。生成草稿不自动运行。
4. 看逐航班命中率、分钟误差、原恢复方案和候选策略；再试客流趋势、原排班建议及正常模型复核。
5. 用完双击停止智能调度.cmd。

1.5B在本机使用CPU、FP32、4线程，约16GB内存环境已验证。加载前需约7GB可用物理内存，不足时回退模板；原始权重磁盘大小仍约3.09GB。未下载Qwen时小模型方向仍可运行，语言先使用模板。

## 怎么理解语言成绩

- 旧24条原流程反馈后16/24，新流程两轮提取合并后24/24；另外24条新留出也24/24。
- 全48条首轮只有29/48；通过的是中文摘录、固定格式转换、最多一次仅含字段名的反馈合并流程，不是模型单次100%正确。
- model_field_sources记录模型值来自哪一轮，来源审计已通过，模板补漏不计模型成功。日期和天数由日历解析器处理。
- 提示或解析文件变更后评测身份会不匹配，系统会先回退模板；应重新运行scripts/evaluate_language.py，不能直接修改成绩。Git属性固定相关文件换行，以保持已验证字节稳定。

## 可选复测与重训

恢复模型不需要重训。若要复核公开数据或重新训练，先准备两个CSV：

```powershell
.\.venv\Scripts\python.exe scripts/download_intelligence_assets.py --skip-model
.\.venv\Scripts\python.exe scripts/train_intelligence.py
.\.venv\Scripts\python.exe scripts/evaluate_intelligence.py
```

它们会生成你自己的新模型版本和评估。使用原报告的源码指纹时，跨平台换行等字节差异可能不同；原报告保留训练时的值，不伪造为新机器重新验收。详细指标、限制及原系统接入见[使用与验收](INTELLIGENCE.md)。

本机真实数据源检查范围有限，所有调度收益仅声称在该系统实验内有效；没有完成生产航空约束或真实航司部署验证。模型包中的数据来源与许可见[来源说明](../pretrained/intelligence/THIRD_PARTY_NOTICES.md)，原项目MIT许可保留。
