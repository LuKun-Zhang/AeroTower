"""机队机型配置：三种窄体机型号的座位布局 / 载客量 / 机队比例

参考川航（四川航空）全空客窄体机队实际情况（2025 年底）：
- A319 19 架、A320（ceo+neo）94 架、A321（ceo+neo）78 架
- 三种机型占比 ≈ 10% / 50% / 40%
座位布局采用川航经典布局：
- A319 C8Y124（公务 8 + 经济 124 = 132 座）
- A320 C8Y156（公务 8 + 经济 156 = 164 座）
- A321 C8Y186（公务 8 + 经济 186 = 194 座）
"""

import math
import re

# 机型 → 布局 / 总座位数 / 3D 机身相对长度（A320 基准 14，按真实机身长度等比）
AIRCRAFT_TYPES = {
    'A319': {'layout': 'C8Y124', 'seats': 132, 'fuselage_len': 12.6},
    'A320': {'layout': 'C8Y156', 'seats': 164, 'fuselage_len': 14.0},
    'A321': {'layout': 'C8Y186', 'seats': 194, 'fuselage_len': 16.6},
}

# 机队比例（川航实际窄体机队比例，取整到 100 架）
FLEET_MIX = [('A319', 10), ('A320', 50), ('A321', 40)]


def type_layout(ac_type):
    """机型 → 座位布局字符串（如 'C8Y156'）"""
    return AIRCRAFT_TYPES.get(ac_type, AIRCRAFT_TYPES['A319'])['layout']


def type_seats(ac_type):
    """机型 → 总座位数"""
    return AIRCRAFT_TYPES.get(ac_type, AIRCRAFT_TYPES['A319'])['seats']


def economy_seats(ac_type):
    """机型 → 经济舱座位数（不售公务舱时按此容量分配）"""
    return parse_layout(type_layout(ac_type)).get('Y', 124)


def type_fuselage_len(ac_type):
    """机型 → 3D 机身相对长度（前端用）"""
    return AIRCRAFT_TYPES.get(ac_type, AIRCRAFT_TYPES['A319'])['fuselage_len']


def fleet_ratio_list():
    """按机队比例展开为 100 长度的机型序列（均匀交错，每 10 个位置一组
    包含 A319×1 / A320×5 / A321×4），使任意长度的连续批次都尽量混合机型。"""
    seq = []
    for _ in range(10):
        seq.extend(['A320', 'A321', 'A320', 'A321', 'A319',
                    'A320', 'A321', 'A320', 'A321', 'A320'])
    return seq


def _normalize_fleet_mix(fleet_mix):
    """[('A319',10), ...] 或 {'A319':10,...} → (('A319',10),('A320',50),('A321',40))"""
    if isinstance(fleet_mix, dict):
        items = list(fleet_mix.items())
    else:
        items = list(fleet_mix or [])
    counts = {}
    for ac_type, count in items:
        try:
            n = int(count)
        except (TypeError, ValueError):
            continue
        if n > 0 and ac_type in AIRCRAFT_TYPES:
            counts[ac_type] = n
    order = [t for t in ('A319', 'A320', 'A321') if t in counts]
    return tuple((t, counts[t]) for t in order)


def fleet_sequence(fleet_mix=None):
    """按机队配比展开机型序列。

    默认配比 (10/50/40) 直接返回 ``fleet_ratio_list()``，保证改造前后输出一致；
    其它配比用确定性交错算法（按“已用比例最小”优先），避免长串同机型。
    """
    mix = _normalize_fleet_mix(fleet_mix)
    if not mix:
        return fleet_ratio_list()
    if mix == (('A319', 10), ('A320', 50), ('A321', 40)):
        return fleet_ratio_list()

    total = sum(n for _, n in mix)
    counts = dict(mix)
    used = {t: 0 for t in counts}
    seq = []
    for _ in range(total):
        pick = min(
            counts,
            key=lambda t: ((used[t] + 1) / counts[t], -counts[t], t),
        )
        seq.append(pick)
        used[pick] += 1
    return seq


def parse_layout(layout):
    """'C8Y124' → {'C': 8, 'Y': 124}"""
    p = {}
    for m in re.finditer(r'([CY])(\d+)', layout):
        p[m.group(1)] = int(m.group(2))
    return p


def layout_rows(layout):
    """座位布局 → 排数信息。

    公务舱 2-2（每排 4 座），经济舱 3-3（每排 6 座）。
    经济舱最后一排可能不满 6 座（如 A319 Y124 → 21 排，最后排 4 座）。
    返回: (公务排数, 经济排数, 经济最后排列数)
    """
    p = parse_layout(layout)
    business_rows = max(1, p.get('C', 8) // 4)
    y_total = p.get('Y', 124)
    y_rows = max(1, math.ceil(y_total / 6))
    y_last = y_total - (y_rows - 1) * 6
    return business_rows, y_rows, y_last


def layout_seats(layout):
    """座位布局 → 总座位数"""
    p = parse_layout(layout)
    return p.get('C', 0) + p.get('Y', 0)
