# 模型包来源与许可说明

正式模型发布包只提供一个小模型版本及其评估、模拟训练条件和语言评测，不包含Qwen权重、私人笔记或运行历史。Git仓库只保留清单与来源说明，权重包从GitHub Release下载。

- AeroTower原项目代码采用MIT许可，见仓库根目录LICENSE；训练与复现代码在本仓库scripts和backend中。
- 日客流历史及调度训练场景由本项目模拟器生成，不能当作真实航司记录。
- 模型包包含AirPassengers历史月客流及其模型。数据说明：[R datasets官方手册](https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/AirPassengers.html)。它记录1949—1960年国际航空月客流，原单位千人；本系统换算为人次。
- R datasets的许可字段为“Part of R”；R整体许可为GPL-2或GPL-3，参见[R许可说明](https://www.r-project.org/Licenses/)和[R源文件](https://github.com/wch/r-source/blob/trunk/src/library/datasets/DESCRIPTION.in)。本目录保留两份GPL许可文本，不把该来源的数据改称MIT。
- AirPassengers来源由R手册列为Box、Jenkins、Reinsel的《Time Series Analysis: Forecasting and Control》第三版；CSV原始来源与版本校验见scripts/download_intelligence_assets.py，公开源数据可按该脚本重新获取，所有训练代码一并提供。
- 外部航班检查使用nycflights13公开数据，许可说明及链接见docs/INTELLIGENCE.md；该CSV不随此模型包分发。
- Qwen2.5-1.5B-Instruct来自Qwen官方，Apache-2.0。权重不在此目录，下载脚本固定修订并保留官方LICENSE。

模型依赖scikit-learn、NumPy、joblib、OR-Tools；这些库的实现不随模型包复制，安装时遵循各自许可。模型评估只证明所列环境与实验范围，不证明真实航空生产效果。
