"""应用配置"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# 数据路径
DATA_DIR = os.path.join(PROJECT_DIR, 'dataProcess')
GRAPH_DIR = os.path.join(DATA_DIR, 'sichuan_big_graph')
EXCEL_DIR = os.path.join(DATA_DIR, '飞机排班测试数据')

# 默认使用的机型
DEFAULT_AC_TYPE = 'A319'
DEFAULT_LAYOUT = 'C8Y124'

# Flask 配置
DEBUG = False
HOST = '0.0.0.0'
PORT = 5000

# 跑道配置
RUNWAYS = ['02L', '02R']
# 尾流间隔（分钟）— 依据《民用航空空中交通管理规则》(CCAR-93) 附件尾流间隔标准。
# 规则：只有「后机比前机轻」的组合才存在强制尾流间隔（重型-重型之间亦需保持）；
# 后机比前机更重或同级别的组合无尾流要求，仅保留最小管制缓冲（1 分钟）。
# 键 = (前机类别, 后机类别)，如 ('heavy', 'medium') = 前重型机后中型机。
MIN_SEPARATION = {
    ('heavy', 'heavy'): 2,    # 重型后随重型：尾流间隔 2 分钟
    ('heavy', 'medium'): 3,   # 重型后随中型：≥3 分钟（CCAR-93 2022 版同一跑道）
    ('heavy', 'light'): 4,    # 重型后随轻型：≥4 分钟
    ('medium', 'light'): 3,   # 中型后随轻型：≥3 分钟
    ('medium', 'medium'): 2,  # 同级别中型：无强制尾流间隔，仅管制缓冲
    ('medium', 'heavy'): 1,   # 后机更重：无尾流要求
    ('light', 'heavy'): 1,
    ('light', 'medium'): 1,
    ('light', 'light'): 1,
}
