"""航班生成器：客流量 → 航班 + 旅客 + 任务链（多基地全局轮转版）

模型说明：
- 客流量：任意城市对方向流（origin → destination），不再强制一端是成都
- 航线限制：只对「至少一端是川航基地」的城市对开航班（符合真实航线网络）
- 飞机排班（任务链）：全局贪心拼接，链首尾为任意川航基地（可不同），
  允许异地过夜、一天多段，不要求每天回成都
- 三种窄体机型（A319/A320/A321）按川航实际机队比例生成：
  航班按机型各自载客量切批，任务链内保持同机型（一架飞机飞一条链）
"""

import math
from ..models.flight import Flight
from ..models.passenger import Passenger
from ..services.flight_filter import SICHUAN_BASES  # 川航基地（系统统一配置）
from ..services.aircraft_types import (
    type_layout, type_seats, economy_seats, fleet_ratio_list, layout_rows, FLEET_MIX,
)

# 川航基地：与系统其他部分（flight_filter / crew_roster）保持一致
DEFAULT_BASES = sorted(SICHUAN_BASES)

# 座位偏好（真实航司常见分配规则）：靠窗 > 过道 > 中间
ECONOMY_PREF = ['A', 'F', 'C', 'D', 'B', 'E']        # 经济舱列偏好
ECONOMY_COLS = ['A', 'B', 'C', 'D', 'E', 'F']        # 经济舱 3-3 满排列序
BUSINESS_PREF = ['A', 'F', 'C', 'D']                 # 公务舱列偏好（窗 A/F、过道 C/D）
SPECIAL_PREF = ['C', 'D', 'A', 'F', 'B', 'E']        # 特殊旅客：过道优先

# 各城市相对成都的 A319 飞行时长（分钟），成都为 0（用作任意城市对航程的估算基准）
FLIGHT_DURATION = {
    "成都": 0, "北京": 150, "上海": 155, "广州": 130, "深圳": 125,
    "昆明": 70, "杭州": 150, "南京": 145, "武汉": 100,
    "长沙": 95, "西安": 80, "重庆": 45, "贵阳": 60,
    "宜宾": 50, "绵阳": 45,
    "拉萨": 120, "乌鲁木齐": 210, "哈尔滨": 220, "三亚": 160,
    "厦门": 150, "青岛": 155, "大连": 170, "沈阳": 175,
    "郑州": 100, "天津": 145, "济南": 130, "福州": 145,
    "南宁": 100, "南昌": 110, "合肥": 120, "太原": 105,
    "石家庄": 120, "呼和浩特": 130,
}


def duration_between(a, b):
    """估算任意城市对 (a→b) 的飞行时长（分钟）。
    用两城市到成都的时长之和作为代理距离，演示够用。
    """
    return FLIGHT_DURATION.get(a, 150) + FLIGHT_DURATION.get(b, 150)


class _VFerry:
    """轻量虚拟空飞对象：仅用于「孤儿航班拼入任务链」方案的可行性校验，
    不真实创建航班，避免被拒绝的插入方案污染航班列表。"""

    __slots__ = ('departure_airport', 'arrival_airport', 'departure_minutes',
                 'arrival_minutes', 'timespan', 'time_departure')

    def __init__(self, origin, dest, dep, arr, dur):
        self.departure_airport = origin
        self.arrival_airport = dest
        self.departure_minutes = dep
        self.arrival_minutes = arr
        self.timespan = dur
        self.time_departure = minutes_to_datetime(dep)


# 内置默认演示数据（方向流：起点 → 终点，含多基地航线）
DEFAULT_TRAFFIC = [
    # 与成都的双向客流（18 城市）
    {"origin": "北京", "destination": "成都", "daily_pax": 1000},
    {"origin": "成都", "destination": "北京", "daily_pax": 900},
    {"origin": "上海", "destination": "成都", "daily_pax": 900},
    {"origin": "成都", "destination": "上海", "daily_pax": 800},
    {"origin": "广州", "destination": "成都", "daily_pax": 700},
    {"origin": "成都", "destination": "广州", "daily_pax": 650},
    {"origin": "深圳", "destination": "成都", "daily_pax": 600},
    {"origin": "成都", "destination": "深圳", "daily_pax": 550},
    {"origin": "昆明", "destination": "成都", "daily_pax": 500},
    {"origin": "成都", "destination": "昆明", "daily_pax": 450},
    {"origin": "杭州", "destination": "成都", "daily_pax": 450},
    {"origin": "成都", "destination": "杭州", "daily_pax": 400},
    {"origin": "南京", "destination": "成都", "daily_pax": 400},
    {"origin": "成都", "destination": "南京", "daily_pax": 350},
    {"origin": "武汉", "destination": "成都", "daily_pax": 350},
    {"origin": "成都", "destination": "武汉", "daily_pax": 300},
    {"origin": "西安", "destination": "成都", "daily_pax": 350},
    {"origin": "成都", "destination": "西安", "daily_pax": 300},
    {"origin": "重庆", "destination": "成都", "daily_pax": 300},
    {"origin": "成都", "destination": "重庆", "daily_pax": 250},
    {"origin": "长沙", "destination": "成都", "daily_pax": 250},
    {"origin": "成都", "destination": "长沙", "daily_pax": 200},
    {"origin": "贵阳", "destination": "成都", "daily_pax": 200},
    {"origin": "成都", "destination": "贵阳", "daily_pax": 180},
    {"origin": "拉萨", "destination": "成都", "daily_pax": 180},
    {"origin": "成都", "destination": "拉萨", "daily_pax": 150},
    {"origin": "三亚", "destination": "成都", "daily_pax": 250},
    {"origin": "成都", "destination": "三亚", "daily_pax": 200},
    {"origin": "厦门", "destination": "成都", "daily_pax": 200},
    {"origin": "成都", "destination": "厦门", "daily_pax": 180},
    {"origin": "青岛", "destination": "成都", "daily_pax": 200},
    {"origin": "成都", "destination": "青岛", "daily_pax": 180},
    {"origin": "沈阳", "destination": "成都", "daily_pax": 180},
    {"origin": "成都", "destination": "沈阳", "daily_pax": 150},
    {"origin": "哈尔滨", "destination": "成都", "daily_pax": 150},
    {"origin": "成都", "destination": "哈尔滨", "daily_pax": 130},
    # 基地间/基地对航线（多基地演示：基地 = 成都、重庆、昆明、宜宾、绵阳、杭州）
    {"origin": "重庆", "destination": "北京", "daily_pax": 300},
    {"origin": "北京", "destination": "重庆", "daily_pax": 250},
    {"origin": "昆明", "destination": "上海", "daily_pax": 350},
    {"origin": "上海", "destination": "昆明", "daily_pax": 300},
    {"origin": "宜宾", "destination": "杭州", "daily_pax": 200},
    {"origin": "杭州", "destination": "宜宾", "daily_pax": 180},
    {"origin": "宜宾", "destination": "成都", "daily_pax": 120},
    {"origin": "成都", "destination": "宜宾", "daily_pax": 100},
    {"origin": "绵阳", "destination": "成都", "daily_pax": 100},
    {"origin": "成都", "destination": "绵阳", "daily_pax": 80},
    # 三角航线（非基地城市之间的衔接航线，用于飞机轮转）：
    # 只有 成都↔X 的往返航班时，飞机到达 X 后唯一的选择就是飞回成都，
    # 任务链必然退化成「成都↔X 每天往返」。增加城市间衔接航线后，
    # 飞机到站后可以顺路接上下一个城市 → 形成 成都→X→Y→成都 的多城轮转。
    {"origin": "贵阳", "destination": "重庆", "daily_pax": 100},
    {"origin": "重庆", "destination": "贵阳", "daily_pax": 90},
    {"origin": "贵阳", "destination": "昆明", "daily_pax": 100},
    {"origin": "昆明", "destination": "贵阳", "daily_pax": 90},
    {"origin": "广州", "destination": "深圳", "daily_pax": 150},
    {"origin": "深圳", "destination": "广州", "daily_pax": 130},
    {"origin": "广州", "destination": "三亚", "daily_pax": 120},
    {"origin": "三亚", "destination": "广州", "daily_pax": 100},
    {"origin": "广州", "destination": "长沙", "daily_pax": 100},
    {"origin": "长沙", "destination": "广州", "daily_pax": 90},
    {"origin": "武汉", "destination": "长沙", "daily_pax": 100},
    {"origin": "长沙", "destination": "武汉", "daily_pax": 90},
    {"origin": "武汉", "destination": "南京", "daily_pax": 90},
    {"origin": "南京", "destination": "武汉", "daily_pax": 80},
    {"origin": "杭州", "destination": "上海", "daily_pax": 130},
    {"origin": "上海", "destination": "杭州", "daily_pax": 110},
    {"origin": "厦门", "destination": "福州", "daily_pax": 90},
    {"origin": "福州", "destination": "厦门", "daily_pax": 80},
    {"origin": "青岛", "destination": "济南", "daily_pax": 90},
    {"origin": "济南", "destination": "青岛", "daily_pax": 80},
    {"origin": "青岛", "destination": "大连", "daily_pax": 80},
    {"origin": "大连", "destination": "青岛", "daily_pax": 70},
    {"origin": "西安", "destination": "郑州", "daily_pax": 90},
    {"origin": "郑州", "destination": "西安", "daily_pax": 80},
    {"origin": "北京", "destination": "天津", "daily_pax": 100},
    {"origin": "天津", "destination": "北京", "daily_pax": 90},
]


def parse_date(date_str):
    """解析日期字符串 '2020-11-30' → (year, month, day)"""
    parts = date_str.split('-')
    return int(parts[0]), int(parts[1]), int(parts[2])


def minutes_to_datetime(abs_minutes):
    """把「11月1日 00:00 起算的分钟数」反算为 (month, day, hour, minute)。
    与 Flight.departure_minutes 的基准一致：
    departure_minutes = (month-11)*30*24*60 + day*24*60 + hour*60 + minute
    即 11-01 → 1 天，11-30 → 30 天，12-01 → 31 天。
    """
    days = abs_minutes // (24 * 60)
    rem = abs_minutes % (24 * 60)
    hour = rem // 60
    minute = rem % 60
    if days <= 30:
        return 11, max(days, 1), hour, minute
    return 12, days - 30, hour, minute


def allocate_seats(batch, use_business, layout='C8Y124'):
    """为一批（同一航班的）旅客按真实航司偏好分配座位，写回 pax.seat / pax.cabin。

    - 特殊旅客优先：前排过道座位
    - 同预订组尽量同排邻座（优先靠窗侧块）；无法同排时按偏好顺序就近落座
    - 常规偏好：前排优先，靠窗 > 过道 > 中间
    - 座位池按 layout 动态生成（公务 2-2、经济 3-3，经济最后一排可能不满 6 座）
    """
    b_rows, y_rows, y_last = layout_rows(layout)

    # 座位池：行号 -> 该排物理列序（公务舱 2-2，经济舱 3-3）
    row_cols = {}
    if use_business:
        for r in range(1, b_rows + 1):
            row_cols[r] = ['A', 'C', 'D', 'F']
    y_first = b_rows + 1
    for r in range(y_first, y_first + y_rows):
        if r == y_first + y_rows - 1:
            row_cols[r] = ECONOMY_COLS[:y_last]   # 最后一排可能缺列
        else:
            row_cols[r] = ECONOMY_COLS
    row_order = list(row_cols.keys())

    taken = set()  # (row, col) 已占用

    # 左右交替起始侧：由批内首位旅客 ID 尾号奇偶确定性决定，
    # 使不同航班的组旅客先落 A 侧还是 F 侧交替进行，整体左右均衡
    first_pid = batch[0].pax_id if batch else ''
    try:
        seed = int(first_pid.split('-')[-1])
    except (ValueError, IndexError):
        seed = 0
    side_state = {'a_first': seed % 2 == 0}

    def row_free(row):
        return [c for c in row_cols[row] if (row, c) not in taken]

    def best_single(pref):
        """按行前→后、列偏好取第一个空闲座位"""
        for row in row_order:
            free = row_free(row)
            for c in pref:
                if c in free:
                    return row, c
        return None

    def candidate_blocks(row, gsize):
        """该排可视为「邻座」的候选块（同一侧才相邻，跨过道不算）"""
        cols = row_cols[row]
        sides = [cols[:2], cols[2:]] if row <= b_rows else [cols[:3], cols[3:]]
        blocks = []
        for side in sides:
            for s in range(len(side) - gsize + 1):
                blocks.append(side[s:s + gsize])
        return blocks

    def find_block(gsize):
        """找能容纳整组同排邻座的块 (row, block)；优先靠窗侧，A/F 侧交替取块（左右均衡）"""
        best = None
        best_score = None
        for row in row_order:
            free_set = set(row_free(row))
            for block in candidate_blocks(row, gsize):
                if not all(c in free_set for c in block):
                    continue
                window = block[0] == 'A' or block[-1] == 'F'
                a_side = block[0] == 'A'
                # 靠窗优先；同靠窗时按批次起始侧交替，A 侧块与 F 侧块轮流优先
                score = (0 if window else 1, 0 if a_side == side_state['a_first'] else 1)
                if best is None or score < best_score:
                    best = (row, block)
                    best_score = score
        if best is not None:
            side_state['a_first'] = not side_state['a_first']
        return (best[0], best[1]) if best is not None else (None, None)

    def assign(p, row, col):
        p.seat = f"{row}{col}"
        p.cabin = 'business' if row <= b_rows else 'economy'
        taken.add((row, col))

    # 1) 特殊旅客：前排过道优先
    for p in batch:
        if p.special:
            seat = best_single(SPECIAL_PREF)
            if seat:
                assign(p, *seat)

    # 2) 普通旅客按预订组分配（同组尽量同排邻座）
    groups = {}
    singles = []
    for p in batch:
        if p.special:
            continue
        if p.group_id:
            groups.setdefault(p.group_id, []).append(p)
        else:
            singles.append(p)

    for group in groups.values():
        row, block = find_block(len(group))
        if row is not None:
            for col, p in zip(block, group):
                assign(p, row, col)
        else:
            # 无法同排邻座（罕见，如公务舱 2-2 装不下 3 人）：按偏好就近落座
            for p in group:
                seat = best_single(ECONOMY_PREF)
                if seat:
                    assign(p, *seat)

    # 3) 剩余散客：靠窗 > 过道 > 中间，前排优先
    for p in singles:
        seat = best_single(ECONOMY_PREF)
        if seat:
            assign(p, *seat)


class FlightGenerator:
    """从城市客流量生成航班计划、旅客清单、任务链（多基地全局轮转）"""

    def __init__(self, traffic_data):
        """
        traffic_data = {
            "bases": ["成都", "重庆", ...],          # 川航基地集合
            "dates": ["2020-11-30", ...],
            "fleet_mix": [("A319", 10), ("A320", 50), ("A321", 40)],  # 机队机型比例
            "load_factor": 0.78,
            "min_turnaround": 60,
            "max_segments_per_day": 5,
            "max_daily_flight_hours": 8,
            "city_traffic": [
                {"origin": "北京", "destination": "成都", "daily_pax": 1000},
                ...
            ]
        }
        """
        self.bases = traffic_data.get('bases', DEFAULT_BASES)
        self.dates = traffic_data.get('dates',
            ['2020-11-30', '2020-12-01', '2020-12-02',
             '2020-12-03', '2020-12-04', '2020-12-05'])
        self.fleet_mix = traffic_data.get('fleet_mix', FLEET_MIX)
        self.load_factor = traffic_data.get('load_factor', 0.78)
        self.min_turnaround = traffic_data.get('min_turnaround', 60)
        self.max_segments = traffic_data.get('max_segments_per_day', 5)
        self.max_flight_hours = traffic_data.get('max_daily_flight_hours', 8)
        self.num_aircraft = traffic_data.get('num_aircraft', 100)  # 机队规模（对齐飞机排班）
        self.city_traffic = traffic_data.get('city_traffic', DEFAULT_TRAFFIC)
        # 机型轮转列表（按机队比例展开，航班分配机型用）
        self._fleet_seq = fleet_ratio_list()
        self._batch_seq_offset = 0  # 全局批次偏移（切批机型轮转起点）
        self.slot_spacing = 6       # 同一档位内相邻班次的错峰间距（分钟），增大航班起降密度观感
        self._slot_occupy = {}      # 档位占用计数 (date_str, slot) -> 已排班次，用于同档位错峰
        # 载客模式：客座率 > 0.90 才开售公务舱；否则只售经济舱，
        # 此时切批/合并容量必须按经济舱座位数计，否则会分到超出经济舱容量的批次
        self._use_business = self.load_factor > 0.90

        self.flight_counter = 0
        self.pax_counter = 0
        self.all_flights = []
        self.all_passengers = []
        self.all_chains = []
        self.skipped_flows = []  # 两端都非基地、未开航线的客流（提示用）
        self.ferry_count = 0     # 空飞（调机）航班数

    def generate(self):
        """主入口：执行全部生成流程"""
        self.flight_counter = 0
        self.pax_counter = 0
        self.all_flights = []
        self.all_passengers = []
        self.all_chains = []
        self.skipped_flows = []
        self.ferry_count = 0
        self._batch_seq_offset = 0
        self._slot_occupy = {}

        # 步骤 1: 生成旅客池
        self._generate_passenger_pool()

        # 步骤 2 & 3: 按城市对客流生成航班 + 分配座位
        self._generate_flights_and_assign_seats()

        # 步骤 4 & 5: 机队对齐生成任务链（每条链 = 一架飞机的完整排班，首尾基地）
        self._build_chains(self.num_aircraft)

        # 步骤 6: 汇总
        return self._build_output()

    def _generate_passenger_pool(self):
        """步骤 1: 生成旅客池。
        每条方向流（origin → destination）每天生成 daily_pax 个旅客，每人有唯一 ID。
        按确定性规则组成 1~3 人预订组（同组视为一起出行），并标记少量特殊旅客。
        """
        self.group_counter = 0
        for flow in self.city_traffic:
            origin = flow['origin']
            destination = flow['destination']
            daily_pax = flow['daily_pax']

            for date_str in self.dates:
                _, m, d = parse_date(date_str)
                date_code = f"{m:02d}{d:02d}"

                i = 0
                while i < daily_pax:
                    # 确定性组大小：约 60% 单人 / 25% 双人 / 15% 三人
                    h = (i * 7 + 3) % 10
                    gsize = 1 if h < 6 else (2 if h < 8 else 3)
                    gsize = min(gsize, daily_pax - i)

                    self.group_counter += 1
                    group_id = f"G{self.group_counter:05d}"
                    for j in range(gsize):
                        self.pax_counter += 1
                        pax_id = f"Pax-{date_code}-{self.pax_counter:05d}"
                        special = (self.pax_counter * 13 + 5) % 100 < 3
                        self.all_passengers.append(
                            Passenger(pax_id, origin=origin, destination=destination,
                                      date_str=date_str, group_id=group_id,
                                      special=special))
                    i += gsize

        print(f"[FlightGenerator] 旅客池生成完成，共 {len(self.all_passengers)} 人")

    def _generate_flights_and_assign_seats(self):
        """步骤 2 & 3: 按城市对客流生成航班并分配座位。
        - 每个方向每天班次数 = ceil(当日客流 / 有效容量)
        - 起飞时刻按「轮转友好」的时段规划（05:30 起每 30 分钟一档，共 35 档）：
          · 基地→外站：上午 06:00~13:30，飞机清晨出港到外站；
          · 外站→基地：下午 14:00~21:30，飞机完成轮转后傍晚回基地；
          · 外站→外站（三角航线）：上午中段~下午 09:00~19:30，
            飞机到达外站后能顺路接上下一个城市 → 形成 成都→X→Y→成都
            的多城轮转，而不是 成都→X→成都→Y 的每日穿梭。
        """
        use_business = self._use_business

        # 起飞时刻网格（分钟）：05:30 ~ 22:30，共 35 档（slot 0 ~ 34）
        grid_start = 5 * 60 + 30
        grid_step = 30

        # 按方向流 (origin → destination) 分组旅客
        flow_groups = {}
        for p in self.all_passengers:
            key = (p.origin, p.destination)
            flow_groups.setdefault(key, []).append(p)

        pairs = {}
        for (o, d) in flow_groups:
            pairs.setdefault(tuple(sorted([o, d])), []).append((o, d))

        for pair in sorted(pairs.keys()):
            a, b = pair
            if a not in self.bases and b in self.bases:
                a, b = b, a
            ab_pax = flow_groups.get((a, b), [])
            ba_pax = flow_groups.get((b, a), [])
            if not ab_pax and not ba_pax:
                continue
            # 航线限制：city_traffic 即航线网络定义，有客流的方向流均开航班。
            # （三角航线 非基地↔非基地 用于飞机轮转，避免任务链退化成都↔X 穿梭）

            duration = duration_between(a, b)

            # 时段规划：按「飞机轮转」波次分配档位，保证一架飞机一天可飞最多 4 段：
            #   早出(06:00-08:30) → 早回(09:00-11:30) → 中出(12:30-15:00) → 晚回(15:30-18:00)
            # 50 架 × 4 段/天 × 6 天 = 1200 段 ≥ 每日航班需求，才能实现机队全覆盖。
            if a not in self.bases and b not in self.bases:
                # 三角航线（外站↔外站）：沿用旧波次，便于轮转衔接
                ab_waves = [(7, 20)]
                ba_waves = [(15, 28)]
            else:
                # 至少一端是基地：基地出港两波 + 外站回港两波。
                # 波次窗口放宽到 16~19 个档位，避免并发班次挤爆单个时刻；
                # 早回波 08:00 起，飞机 06:00 出港 2h 后 08:00 到外站，
                # 09:00 即可回港 → 11:00 回基地 → 12:00 中波再出 → 4 段轮转。
                ab_waves = [(1, 8), (13, 20)]
                ba_waves = [(7, 16), (21, 28)]

            def wave_slot(k, n, waves):
                """把第 k 个（共 n 个）班次分配到波次表里，波内均分档位"""
                if n <= 1:
                    lo, hi = waves[0]
                    return (lo + hi) // 2
                per, rem = divmod(n, len(waves))
                acc = 0
                for wi, (lo, hi) in enumerate(waves):
                    cnt = per + (1 if wi < rem else 0)
                    if k < acc + cnt:
                        j = k - acc
                        if cnt <= 1:
                            return (lo + hi) // 2
                        return lo + int(round(j * (hi - lo) / (cnt - 1)))
                    acc += cnt
                lo, hi = waves[-1]
                return lo + (hi - lo) // 2

            # 按日期分组
            by_date_ab = {}
            for p in ab_pax:
                by_date_ab.setdefault(p.date_str, []).append(p)
            by_date_ba = {}
            for p in ba_pax:
                by_date_ba.setdefault(p.date_str, []).append(p)

            for date_str in self.dates:
                date_ab = by_date_ab.get(date_str, [])
                date_ba = by_date_ba.get(date_str, [])
                if not date_ab and not date_ba:
                    continue
                # 按机队比例 + 各机型载客量切批：[(ac_type, batch)]，同组旅客不拆散。
                # 往返两方向用「同一机型偏移」切批 → 成都→X 与 X→成都 的同序航班机型一致，
                # 保证每架飞机到外站后总能找到同机型返程航班（往返对），避免飞机滞留外站，
                # 从而使任务链自然形成「成都→X→成都」的日往返轮转、飞机每晚回到基地。
                offset = self._batch_seq_offset
                ab_batches = self._plan_batches(date_ab, offset)
                ba_batches = self._plan_batches(date_ba, offset)
                self._batch_seq_offset = offset + max(len(ab_batches), len(ba_batches))
                n_ab = len(ab_batches)
                n_ba = len(ba_batches)

                y, m, d = parse_date(date_str)
                for k, (ac_type, batch) in enumerate(ab_batches):
                    slot, off = self._wave_dep(date_str, wave_slot(k, n_ab, ab_waves), grid_step)
                    dep = grid_start + slot * grid_step + off
                    self._create_flight(a, b, m, d, dep,
                                        duration, ac_type, batch, use_business)
                for k, (ac_type, batch) in enumerate(ba_batches):
                    slot, off = self._wave_dep(date_str, wave_slot(k, n_ba, ba_waves), grid_step)
                    dep = grid_start + slot * grid_step + off
                    self._create_flight(b, a, m, d, dep,
                                        duration, ac_type, batch, use_business)

        print(f"[FlightGenerator] 航班生成完成，共 {len(self.all_flights)} 个航班；"
              f"跳过非基地航线 {len(self.skipped_flows)} 条")

    def _wave_dep(self, date_str, slot, grid_step):
        """同一档位多班次错峰：第 k 班在该档位基础上偏移 k*spacing 分钟，
        超出档位步长则顺延到下一档重新计数，避免大量航班挤在同一时刻起降。"""
        spacing = self.slot_spacing
        k = self._slot_occupy.get((date_str, slot), 0)
        while k * spacing >= grid_step:
            slot += 1
            k = self._slot_occupy.get((date_str, slot), 0)
        self._slot_occupy[(date_str, slot)] = k + 1
        return slot, k * spacing

    def _plan_batches(self, pax_list, offset=None):
        """按机队机型比例 + 各机型载客量切批。

        返回 [(ac_type, batch)]：机型按 FLEET_MIX 比例序列轮转（全局偏移递增，
        避免小航线连续批次全落在同一机型段），每批旅客数 ≤ 该机型有效载客量
        （座位数 × 载客率），同预订组不拆散。

        offset：可传入显式机型偏移（往返方向共用同一偏移，保证同序航班机型一致）；
        为 None 时使用并推进全局批次偏移。
        """
        total = len(pax_list)
        if total == 0:
            return []
        seq = self._fleet_seq
        base = offset if offset is not None else self._batch_seq_offset
        avg_cap = sum(self._cap_seats(a) for a in seq) / len(seq) * self.load_factor
        # 期望班次数（用加权平均载客量估算），再按需求逐批切分
        n_expected = max(1, math.ceil(total / avg_cap))
        batches = []
        i = 0
        k = 0
        # 按轮转机型有效容量贪心切批；边界落在组中间时整组并入本批。
        # 低客座尾批由 _consolidate_low_load_batches 统一合并（模拟航司合并班次）。
        while i < total and k < n_expected + 3:
            ac_type = seq[(base + k) % len(seq)]
            cap = int(self._cap_seats(ac_type) * self.load_factor)
            end = min(i + cap, total)
            while end < total and pax_list[end - 1].group_id == pax_list[end].group_id:
                end += 1
            batches.append((ac_type, pax_list[i:end]))
            i = end
            k += 1
        if offset is None:
            self._batch_seq_offset += k
        # 合并低客座批次（模拟真实航司的「合并班次」）
        return self._consolidate_low_load_batches(batches)

    def _cap_seats(self, ac_type):
        """当前载客模式下的有效载客座位数：不售公务舱时仅按经济舱座位计"""
        return economy_seats(ac_type) if not self._use_business else type_seats(ac_type)

    def _consolidate_low_load_batches(self, batches, min_rate=0.40):
        """合并低客座批次，模拟真实航司的「合并班次」操作。

        真实航司对低客座航班（一般客座率低于保本线的 40% 左右）会合并到同航线
        相邻班次，避免开「幽灵航班」：
        - 当前批次客座率 < min_rate（按该批次机型有效座位算）且并入前一批不超
          前一机型有效载客座位数时，整批并入前一批（同组旅客保持同航班，不拆散）；
        - 有效座位不可超载，故超限时保留该批（极端场景，客座率仍可能偏低）。
        """
        if len(batches) < 2:
            return batches
        out = []
        for ac_type, batch in batches:
            if out:
                prev_ac, prev_pax = out[-1]
                rate = len(batch) / self._cap_seats(ac_type)
                if rate < min_rate and len(prev_pax) + len(batch) <= self._cap_seats(prev_ac):
                    out[-1] = (prev_ac, prev_pax + batch)
                    continue
            out.append((ac_type, batch))
        return out

    def _create_flight(self, origin, destination, m, d, dep_min, duration,
                       ac_type, batch, use_business):
        """创建一个航班，并为该批次旅客按真实偏好规则分配座位"""
        # dep_min 可能超过 1440（红眼班溢出到次日），统一用基准分钟反算起降日期时刻
        dep_abs = (m - 11) * 30 * 24 * 60 + d * 24 * 60 + dep_min
        arr_abs = dep_abs + duration
        _, dep_m, dep_d, dep_h, dep_mi = [2020, *minutes_to_datetime(dep_abs)]
        _, arr_m, arr_d, arr_h, arr_mi = [2020, *minutes_to_datetime(arr_abs)]

        layout = type_layout(ac_type)
        self.flight_counter += 1
        flight = Flight(
            flight_id=f"gen_{self.flight_counter:05d}",
            flight_no=f"3U{8000 + self.flight_counter}",
            ac_type=ac_type,
            layout=layout,
            departure_airport=origin,
            arrival_airport=destination,
            time_departure=[2020, dep_m, dep_d, dep_h, dep_mi],
            time_arrival=[2020, arr_m, arr_d, arr_h, arr_mi],
            timespan=duration,
        )

        # 按偏好规则分配座位（写回 pax.seat / pax.cabin）
        allocate_seats(batch, use_business, layout)

        for pax in batch:
            pax.flight_no = flight.flight_no

        flight._pax_list = [p.to_dict() for p in batch]
        flight._pax_count = len(batch)
        flight._passenger_manifest = {}
        for p in batch:
            flight._passenger_manifest[p.seat] = p.pax_id

        self.all_flights.append(flight)

    def _build_chains(self, num_aircraft=100):
        """步骤 4 & 5: 机队对齐的任务链生成（懒激活贪心 + 孤儿抢救）。

        以机队规模为核心：航班按时间序处理，优先交给已激活飞机直接衔接
        （先派在出发机场等最久的飞机，同等待时长时优先负载大的飞机，仅同机型
        可衔接）；无直接衔接时用「从当前位置空飞进场」接驳；两者都不可行才
        按需新开一架飞机（从成都空飞进场，同日超限则提前一天）。新开飞机数
        受 num_aircraft 预算控制，因此链数 ≈ 机队规模，天然可被全部覆盖。
        主循环后对剩余孤儿航班做 _salvage_orphans 抢救：先拼入同机型链的空档，
        再跨机型（载客量足够）吸收，使链数收敛到机队规模。链首/链尾由
        _fix_chain_bases 补空飞落到基地；中间允许异地过夜、不必每天回基地。
        """
        flights = sorted(self.all_flights, key=lambda f: (f.departure_minutes, f.flight_id))
        max_min = self.max_flight_hours * 60
        period_start = 30 * 24 * 60  # 11-30 00:00（与 Flight.departure_minutes 基准一致）
        earliest = period_start - 24 * 60  # 允许周期前 1 天调机进场
        base_set = set(self.bases)

        def dk_of(f):
            return (f.time_departure[1], f.time_departure[2])

        def can_day(a, dk, add_seg, add_min):
            return (a['day_seg'].get(dk, 0) + add_seg <= self.max_segments
                    and a['day_min'].get(dk, 0) + add_min <= max_min)

        def assign(a, f):
            dk = dk_of(f)
            a['items'].append(f)
            a['pos_airport'] = f.arrival_airport
            a['pos_time'] = f.arrival_minutes
            a['day_seg'][dk] = a['day_seg'].get(dk, 0) + 1
            a['day_min'][dk] = a['day_min'].get(dk, 0) + f.timespan

        def total_min(a):
            return sum(a['day_min'].values())

        def ferry_plan_fresh(f):
            """全新飞机（成都基地，周期前 1 天即可用）空飞到 f 出发机场。
            同日超限则提前一天进场；返回 (dep, dur) 或 None。"""
            dk = dk_of(f)
            dur = duration_between('成都', f.departure_airport)
            dep = f.departure_minutes - self.min_turnaround - dur
            for _ in range(2):
                if dep < earliest:
                    return None
                fdt = minutes_to_datetime(dep)
                fdk = (fdt[0], fdt[1])
                if fdk == dk:
                    if 2 <= self.max_segments and dur + f.timespan <= max_min:
                        return (dep, dur)
                else:
                    if dur <= max_min and f.timespan <= max_min:
                        return (dep, dur)
                dep -= 24 * 60
            return None

        planes = []   # 已激活的飞机（每架 = 一条任务链）
        opened = 0    # 已激活的飞机数（预算 num_aircraft）
        unassigned = []

        for f in flights:
            dk = dk_of(f)

            # 1) 直接衔接：先派「在出发机场等最久」的飞机（pos_time 最小 → 最早到达/最早就绪），
            #    让滞留外站的飞机尽快被派走，飞机自然形成 成都→X→成都 的日往返循环；
            #    同等待时长时优先负载大的飞机（集中复用）。仅同机型可衔接。
            direct_best = None
            for a in planes:
                if (a['ac_type'] == f.ac_type
                        and a['pos_airport'] == f.departure_airport
                        and a['pos_time'] + self.min_turnaround <= f.departure_minutes
                        and can_day(a, dk, 1, f.timespan)):
                    key = (a['pos_time'], -total_min(a))
                    if direct_best is None or key < direct_best[0]:
                        direct_best = (key, a)
            if direct_best is not None:
                assign(direct_best[1], f)
                continue

            # 2) 已激活飞机空飞（调机）进场：从飞机当前位置飞到 f 出发机场（仅同机型）。
            #    不限基地：飞机滞留外站时也能调机去接下一班，避免「到外站后无同机型返程 → 卡死」
            ferry_best = None
            for a in planes:
                if a['ac_type'] != f.ac_type:
                    continue
                from_airport = a['pos_airport']
                dur = duration_between(from_airport, f.departure_airport)
                if from_airport == f.departure_airport:
                    continue  # 已在出发机场，属情况 1
                dep = f.departure_minutes - self.min_turnaround - dur
                if dep < a['pos_time']:
                    dep -= 24 * 60
                    if dep < a['pos_time'] or dep < earliest:
                        continue
                fdt = minutes_to_datetime(dep)
                fdk = (fdt[0], fdt[1])
                if fdk == dk:
                    if not can_day(a, dk, 2, dur + f.timespan):
                        continue
                else:
                    if not (can_day(a, fdk, 1, dur) and can_day(a, dk, 1, f.timespan)):
                        continue
                key = (dur, total_min(a), a['pos_time'])
                if ferry_best is None or key < ferry_best[0]:
                    ferry_best = (key, a, dep, dur)
            if ferry_best is not None:
                _, a, dep, dur = ferry_best
                if dur > 0:
                    ferry = self._create_ferry_flight(a['pos_airport'], f.departure_airport,
                                                      dep, f.ac_type)
                    assign(a, ferry)
                    self.ferry_count += 1
                else:
                    # 出发地即当前位置：无实际空飞，仅占用一个当日段位（保持负载口径一致）
                    a['day_seg'][dk] = a['day_seg'].get(dk, 0) + 1
                assign(a, f)
                continue

            # 3) 新开飞机（激活预算内）：从成都空飞进场，机型与首个航班一致
            if opened >= num_aircraft:
                unassigned.append(f)
                continue
            plan = ferry_plan_fresh(f)
            if plan is not None:
                dep, dur = plan
                a = {'base': '成都', 'pos_airport': '成都', 'pos_time': earliest,
                     'ac_type': f.ac_type, 'day_seg': {}, 'day_min': {}, 'items': []}
                planes.append(a)
                opened += 1
                if dur > 0:
                    ferry = self._create_ferry_flight('成都', f.departure_airport,
                                                      dep, f.ac_type)
                    assign(a, ferry)
                    self.ferry_count += 1
                else:
                    # 出发地即基地：无实际空飞，仅占用一个当日段位（保持负载口径一致）
                    a['day_seg'][dk] = a['day_seg'].get(dk, 0) + 1
                assign(a, f)
            else:
                unassigned.append(f)

        # 抢救孤儿航班：先把孤儿拼回同机型链的空档，拼不进再跨机型（载客量足够）吸收，
        # 使链数收敛到机队规模，保证每架飞机都有完整任务链、每个航班都有飞机可派。
        if unassigned:
            unassigned = self._salvage_orphans(planes, unassigned)
            print(f"[FlightGenerator] 抢救后剩余孤儿航班 {len(unassigned)} 个")

        # 机队链 + 未能覆盖的孤儿链（孤儿链首/尾由 _fix_chain_bases 补空飞）
        chains = [a['items'] for a in planes if a['items']] + [[f] for f in unassigned]
        chains = self._fix_chain_bases(chains)

        chains.sort(key=lambda c: (c[0].departure_minutes, c[0].flight_id))
        self.all_chains = chains

        based = sum(
            1 for c in self.all_chains
            if c[0].departure_airport in self.bases and c[-1].arrival_airport in self.bases
        )
        print(f"[FlightGenerator] 任务链构建完成：机队 {num_aircraft} 架，共 {len(self.all_chains)} 条链，"
              f"其中首尾均为基地 {based} 条；空飞（调机）航班 {self.ferry_count} 个")

    # ---------- 孤儿航班抢救（链修复） ----------

    @staticmethod
    def _chain_day_budget(items):
        """统计链中每天段数/飞行分钟（空飞按起飞机日期计）"""
        seg, minutes = {}, {}
        for f in items:
            dk = (f.time_departure[1], f.time_departure[2])
            seg[dk] = seg.get(dk, 0) + 1
            minutes[dk] = minutes.get(dk, 0) + f.timespan
        return seg, minutes

    def _chain_valid(self, items):
        """校验整链约束：位置连续（不连续处须已插空飞）+ 过站时间 + 每日段数/时长上限"""
        prev = None
        for f in items:
            if prev is not None:
                if f.departure_airport != prev.arrival_airport:
                    return False
                if f.departure_minutes - prev.arrival_minutes < self.min_turnaround:
                    return False
            prev = f
        seg, minutes = self._chain_day_budget(items)
        for dk in seg:
            if seg[dk] > self.max_segments or minutes[dk] > self.max_flight_hours * 60:
                return False
        return True

    def _try_insert(self, items, i, f):
        """尝试把航班 f 插入链 items 的位置 i（0..len）。

        返回 (plan, extra_minutes) 或 (None, 0)：
        plan 为有序片段列表 [('flight', f) | ('ferry', origin, dest, dep, dur), ...]，
        位置不连续处自动补空飞桥接，空飞最晚起飞、确保过站时间。
        """
        n = len(items)
        left = items[i - 1] if i > 0 else None
        right = items[i] if i < n else None
        plan = []
        extra = 0

        if left is not None and left.arrival_airport != f.departure_airport:
            dur = duration_between(left.arrival_airport, f.departure_airport)
            dep = f.departure_minutes - self.min_turnaround - dur
            if dep < left.arrival_minutes + self.min_turnaround:
                return None, 0
            plan.append(('ferry', left.arrival_airport, f.departure_airport, dep, dur))
            extra += dur

        plan.append(('flight', f))

        if right is not None and f.arrival_airport != right.departure_airport:
            dur = duration_between(f.arrival_airport, right.departure_airport)
            dep = f.arrival_minutes + self.min_turnaround
            if dep + dur + self.min_turnaround > right.departure_minutes:
                return None, 0
            plan.append(('ferry', f.arrival_airport, right.departure_airport, dep, dur))
            extra += dur

        return plan, extra

    def _materialize_plan(self, items, i, plan, ac_type):
        """把 plan 中的空飞创建为真实航班，返回拼接后的新链 items 列表"""
        new_items = list(items[:i])
        for entry in plan:
            if entry[0] == 'flight':
                new_items.append(entry[1])
            else:
                _, origin, dest, dep, dur = entry
                ferry = self._create_ferry_flight(origin, dest, dep, ac_type)
                self.ferry_count += 1
                new_items.append(ferry)
        new_items.extend(items[i:])
        return new_items

    def _salvage_orphans(self, planes, unassigned):
        """把孤儿航班拼入已有任务链，减少无飞机可派的航班。

        策略（保证链内机型 = 飞机机型，便于排班按机型匹配）：
        - 同机型链优先：任意位置均可插入；
        - 同机型拼不进时跨机型：仅插入链的非头部位置（保持链首机型不变），
          且吸收飞机的载客量 ≥ 该航班旅客数（如 A320 可执飞 A319 航班）；
        - 每次选「空飞分钟增量最少」的插入方案。
        返回仍未被覆盖的孤儿航班列表。
        """
        if not unassigned:
            return unassigned

        remaining = []
        for f in sorted(unassigned, key=lambda x: (x.departure_minutes, x.flight_id)):
            best = None  # ((extra, i), plan, pos, plane)
            for allow_cross in (False, True):
                for a in planes:
                    items = a['items']
                    if not items:
                        continue
                    same_type = a['ac_type'] == f.ac_type
                    if same_type:
                        pass
                    elif allow_cross and type_seats(a['ac_type']) >= f._pax_count:
                        pass
                    else:
                        continue
                    for i in range(len(items) + 1):
                        if not same_type and i == 0:
                            continue  # 跨机型不插链头，保持链首机型不变
                        plan, extra = self._try_insert(items, i, f)
                        if plan is None:
                            continue
                        if self._virtual_chain_ok(items, i, plan):
                            key = (extra, i)
                            if best is None or key < best[0]:
                                best = (key, plan, i, a)
                if best is not None:
                    break
            if best is None:
                remaining.append(f)
                continue
            _, plan, i, a = best
            a['items'] = self._materialize_plan(a['items'], i, plan, a['ac_type'])
        return remaining

    def _virtual_chain_ok(self, items, i, plan):
        """用虚拟空飞对象校验「插入 plan 后的链」是否满足约束（不创建真实航班）"""
        merged = list(items[:i])
        for entry in plan:
            if entry[0] == 'flight':
                merged.append(entry[1])
            else:
                _, origin, dest, dep, dur = entry
                merged.append(_VFerry(origin, dest, dep, dep + dur, dur))
        merged.extend(items[i:])
        return self._chain_valid(merged)

    def _create_ferry_flight(self, origin, destination, dep_abs, ac_type='A319'):
        """创建空飞（调机）航班：不载客，仅用于补齐任务链首尾基地，机型随任务链。"""
        duration = duration_between(origin, destination)
        arr_abs = dep_abs + duration
        _, dep_m, dep_d, dep_h, dep_mi = [2020, *minutes_to_datetime(dep_abs)]
        _, arr_m, arr_d, arr_h, arr_mi = [2020, *minutes_to_datetime(arr_abs)]

        self.flight_counter += 1
        flight = Flight(
            flight_id=f"gen_{self.flight_counter:05d}",
            flight_no=f"3U{8000 + self.flight_counter}",
            ac_type=ac_type,
            layout=type_layout(ac_type),
            departure_airport=origin,
            arrival_airport=destination,
            time_departure=[2020, dep_m, dep_d, dep_h, dep_mi],
            time_arrival=[2020, arr_m, arr_d, arr_h, arr_mi],
            timespan=duration,
        )
        flight._pax_list = []
        flight._pax_count = 0
        flight._passenger_manifest = {}
        flight._is_ferry = True
        self.all_flights.append(flight)
        return flight

    def _fix_chain_bases(self, chains):
        """用空飞（调机）航班补齐非基地链的首/尾，让任务链首尾尽量落在基地。

        - 链头非基地：在链头前插入「基地 → 链头出发机场」的空飞；
        - 链尾非基地：在链尾后追加「链尾到达机场 → 基地」的空飞；
        - 链头空飞可提前 1 天到达（飞机提前调机到外站过夜等链头），
          允许在周期开始前 1 天进场，避免挤占链头当天的段数/时长上限；
        - 链尾空飞可推迟到后续日子再调机回基地（最后一天红眼到达也能补）；
        - 空飞只补正常航班衔接不了的断裂，且遵守每日段数/时长约束；
        - 优先选航程短的基地，航程相近时在不同基地间轮转，避免空飞全压在成都。
        """
        period_start = 30 * 24 * 60  # 11-30 00:00 基准分钟
        ferry_earliest = period_start - 24 * 60  # 允许周期前 1 天调机进场
        # 周期结束 + 1 天：允许最后一天深夜/次日到达的链尾补空飞回基地
        period_end = period_start + (len(self.dates) + 1) * 24 * 60 + 4 * 60
        max_min = self.max_flight_hours * 60
        base_usage = {}  # 各基地已作为空飞起降基地的次数（轮转用）

        def day_stats(c):
            seg, minutes = {}, {}
            for f in c:
                dk = (f.time_departure[1], f.time_departure[2])
                seg[dk] = seg.get(dk, 0) + 1
                minutes[dk] = minutes.get(dk, 0) + f.timespan
            return seg, minutes

        def pick_base(city):
            # 在航程接近最优（容差 45 分钟）的基地里，优先选用得少的基地，
            # 避免空飞（调机）永远从成都出发
            durs = sorted((duration_between(b, city), b) for b in self.bases)
            best_dur = durs[0][0]
            candidates = [b for dur, b in durs if dur <= best_dur + 45]
            candidates.sort(key=lambda b: (base_usage.get(b, 0),
                                           duration_between(b, city)))
            return candidates

        def fits(seg, minutes, dk, dur):
            return (seg.get(dk, 0) + 1 <= self.max_segments
                    and minutes.get(dk, 0) + dur <= max_min)

        fixed = []
        for c in chains:
            items = list(c)
            seg, minutes = day_stats(items)

            # --- 链头非基地：插入 基地→链头 的空飞 ---
            head = items[0]
            if head.departure_airport not in self.bases:
                for base in pick_base(head.departure_airport):
                    dur = duration_between(base, head.departure_airport)
                    # 最晚可到达：链头起飞 - 过站 - 航程；可提前调机（最多提前 1 天）
                    latest = head.departure_minutes - self.min_turnaround - dur
                    dep = latest
                    while dep >= ferry_earliest:
                        dt = minutes_to_datetime(dep)
                        dk_dep = (dt[0], dt[1])
                        if fits(seg, minutes, dk_dep, dur):
                            break
                        dep -= 24 * 60  # 提前一天（外站过夜等待链头）
                    if dep < ferry_earliest:
                        continue
                    ferry = self._create_ferry_flight(base, head.departure_airport,
                                                      dep, head.ac_type)
                    items.insert(0, ferry)
                    seg[dk_dep] = seg.get(dk_dep, 0) + 1
                    minutes[dk_dep] = minutes.get(dk_dep, 0) + dur
                    base_usage[base] = base_usage.get(base, 0) + 1
                    self.ferry_count += 1
                    break

            # --- 链尾非基地：追加 链尾→基地 的空飞 ---
            tail = items[-1]
            if tail.arrival_airport not in self.bases:
                for base in pick_base(tail.arrival_airport):
                    dur = duration_between(tail.arrival_airport, base)
                    # 链尾到达 + 过站 后起飞空飞；当天排不下可推迟到后续日子
                    dep = tail.arrival_minutes + self.min_turnaround
                    while dep + dur <= period_end:
                        dt = minutes_to_datetime(dep)
                        dk_dep = (dt[0], dt[1])
                        if fits(seg, minutes, dk_dep, dur):
                            break
                        dep += 24 * 60  # 推迟一天再调机回基地
                    if dep + dur > period_end:
                        continue
                    ferry = self._create_ferry_flight(tail.arrival_airport, base,
                                                      dep, tail.ac_type)
                    items.append(ferry)
                    seg[dk_dep] = seg.get(dk_dep, 0) + 1
                    minutes[dk_dep] = minutes.get(dk_dep, 0) + dur
                    base_usage[base] = base_usage.get(base, 0) + 1
                    self.ferry_count += 1
                    break

            fixed.append(items)

        return fixed

    def _build_output(self):
        """步骤 6: 构建最终输出"""
        flight_dicts = []
        for f in self.all_flights:
            d = f.to_dict()
            d['departure_minutes'] = f.departure_minutes
            d['arrival_minutes'] = f.arrival_minutes
            d['passenger_manifest'] = getattr(f, '_passenger_manifest', {})
            d['pax_list'] = getattr(f, '_pax_list', [])
            d['pax_count'] = getattr(f, '_pax_count', 0)
            d['is_ferry'] = getattr(f, '_is_ferry', False)
            flight_dicts.append(d)

        passenger_dicts = [p.to_dict() for p in self.all_passengers if p.flight_no]

        chains = []
        for idx, chain in enumerate(self.all_chains):
            start = chain[0].departure_airport
            end = chain[-1].arrival_airport
            based = start in self.bases and end in self.bases
            chains.append({
                'chain_id': idx + 1,
                'ac_type': chain[0].ac_type,
                'segments': len(chain),
                'flights': [f.flight_id for f in chain],
                'route': ' → '.join([start] + [f.arrival_airport for f in chain]),
                'start_airport': start,
                'end_airport': end,
                'based': based,
                'total_pax': sum(getattr(f, '_pax_count', 0) for f in chain),
            })

        total_passengers = len(passenger_dicts)
        # 空飞（调机）航班不载客，不占可用座位数；各航班按机型载客量累加
        total_seats = sum(
            type_seats(f.ac_type) for f in self.all_flights
            if not getattr(f, '_is_ferry', False)
        )

        # 覆盖城市数（从航班提取）
        covered_cities = set()
        for f in self.all_flights:
            covered_cities.add(f.departure_airport)
            covered_cities.add(f.arrival_airport)

        return {
            'flights': flight_dicts,
            'passengers': passenger_dicts,
            'chains': chains,
            'stats': {
                'total_flights': len(self.all_flights),
                'total_chains': len(chains),
                'based_chains': sum(1 for c in chains if c['based']),
                'ferry_flights': self.ferry_count,
                'bases': list(self.bases),
                'cities_covered': len(covered_cities),
                'skipped_flows': self.skipped_flows,
                'total_passengers': total_passengers,
                'total_seats': total_seats,
                'avg_load_factor': round(total_passengers / total_seats, 4)
                if total_seats > 0 else 0,
            }
        }
