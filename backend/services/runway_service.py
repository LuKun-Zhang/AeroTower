"""跑道调度算法服务
多跑道支持：按机场真实跑道数量分配，起飞降落混用每一条跑道。
"""
import os
import json
from ..config import MIN_SEPARATION
from ..models.flight import Flight

# 默认跑道数（配置文件中未收录的机场）
DEFAULT_RUNWAY_COUNT = 1

# 跑道配置文件路径
_RUNWAY_CONFIG_PATH = os.path.normpath(os.path.join(
    os.path.abspath(__file__), '..', '..', 'data', 'airports_runway.json'
))


def _load_runway_config():
    """加载机场跑道数量配置"""
    try:
        with open(_RUNWAY_CONFIG_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


class RunwaySchedulingService:
    """跑道起降调度 — 支持多跑道（起飞降落混用）"""

    def __init__(self):
        self._runway_cfg = _load_runway_config()

    def get_runway_count(self, airport_name):
        """获取机场的真实跑道数量"""
        return self._runway_cfg.get(airport_name, DEFAULT_RUNWAY_COUNT)

    def solve_multi_runway(self, flights, airport_name):
        """
        多跑道调度核心算法
         - 起飞和降落混用所有跑道
         - 按预计时间（降落=到达时间，起飞=出发时间）排序
         - 贪心分配：每架航班分配到最早空闲的跑道
         - 返回：所有调度条目列表（含 runway 字段）
        """
        if not flights:
            return [], self._empty_stats()

        n_runways = self.get_runway_count(airport_name)

        # 按类型分离，计算目标时间（过站航班同时生成降落+起飞两条记录）
        items = []
        for f in flights:
            matched = False
            if f.arrival_airport == airport_name:
                items.append((f, True, f.arrival_minutes))
                matched = True
            if f.departure_airport == airport_name:
                items.append((f, False, f.departure_minutes))
                matched = True
            if not matched:
                continue

        if not items:
            return [], self._empty_stats()

        # 按目标时间升序排列
        items.sort(key=lambda x: x[2])

        # 每条跑道的"下次可用时间"（分钟绝对值，从第0天算起）
        runway_free_at = [0] * n_runways
        # 每条跑道上一次操作的前机类别（用于计算「前机→后机」尾流间隔）
        runway_prev_cat = [None] * n_runways

        schedule = []
        total_delay = 0
        landing_count = 0
        takeoff_count = 0
        landing_delay = 0
        takeoff_delay = 0

        for f, is_landing, target in items:
            # 找最早空闲的跑道
            best_rwy = 0
            earliest_free = runway_free_at[0]
            for r in range(1, n_runways):
                if runway_free_at[r] < earliest_free:
                    earliest_free = runway_free_at[r]
                    best_rwy = r

            cat = self._get_category(f)
            runway_dur = self._get_runway_duration(cat, f.ac_type)

            actual_time = max(target, earliest_free)
            delay = actual_time - target
            end_time = actual_time + runway_dur
            total_delay += delay

            if is_landing:
                landing_count += 1
                landing_delay += delay
            else:
                takeoff_count += 1
                takeoff_delay += delay

            # 日期：降落用到达日期，起飞用出发日期
            if is_landing:
                y, m, d, *_ = f.time_arrival
            else:
                y, m, d, *_ = f.time_departure
            date_str = f"{y}-{m:02d}-{d:02d}"

            schedule.append({
                'flight_id': f.flight_id,
                'flight_no': f.flight_no,
                'airport': airport_name,
                'from': f.departure_airport,
                'to': f.arrival_airport,
                'date': date_str,
                'time_dep': Flight._format_time(f.time_departure),
                'time_arr': Flight._format_time(f.time_arrival),
                'duration': f.timespan,
                'runway_duration': runway_dur,
                'category': cat,
                'ac_type': f.ac_type,
                'type': 'landing' if is_landing else 'takeoff',
                'target_time': target,
                'actual_time': actual_time,
                'end_time': end_time,
                'delay': delay,
                'runway': best_rwy + 1,  # 跑道编号，从1开始
                'runway_total': n_runways,
            })

            # 更新该跑道下次可用时间：本次结束 + 「前机→后机」尾流间隔
            prev_cat = runway_prev_cat[best_rwy]
            sep = self._get_separation(prev_cat, cat) if prev_cat is not None else 0
            runway_free_at[best_rwy] = end_time + sep
            runway_prev_cat[best_rwy] = cat

        stats = {
            'airport': airport_name,
            'runways': n_runways,
            'total_flights': len(schedule),
            'landing_count': landing_count,
            'takeoff_count': takeoff_count,
            'total_delay': total_delay,
            'landing_delay': landing_delay,
            'takeoff_delay': takeoff_delay,
            'avg_delay': round(total_delay / max(len(schedule), 1), 1),
        }

        if landing_count:
            stats['landing_avg_delay'] = round(landing_delay / landing_count, 1)
        if takeoff_count:
            stats['takeoff_avg_delay'] = round(takeoff_delay / takeoff_count, 1)

        return schedule, stats

    # ============== 兼容旧接口 ==============

    def solve_unified(self, flights, max_position_shift=5):
        """
        兼容旧接口 cp_sat：对单个机场执行多跑道调度
        返回: (landing_schedule, takeoff_schedule, stats)
        """
        if not flights:
            return [], [], {}

        if self._current_airport_cfg:
            airport_name = self._current_airport_cfg
        else:
            # 从航班数据推断机场
            apt = set()
            for f in flights:
                if f.arrival_airport:
                    apt.add(f.arrival_airport)
                if f.departure_airport:
                    apt.add(f.departure_airport)
            airport_name = apt.pop() if apt else ''
            if len(apt) > 0:
                # 多机场混合 → 取航班最多的机场
                cnt = {}
                for f in flights:
                    for a in [f.arrival_airport, f.departure_airport]:
                        cnt[a] = cnt.get(a, 0) + 1
                airport_name = max(cnt, key=cnt.get)

        schedule, stats = self.solve_multi_runway(flights, airport_name)

        if not schedule:
            return [], [], {}

        # 分离降落和起飞（保持兼容）
        landings = [s for s in schedule if s['type'] == 'landing']
        takeoffs = [s for s in schedule if s['type'] == 'takeoff']

        return landings, takeoffs, stats

    def solve_fcfs(self, flights, landing=True):
        """
        兼容旧接口：对指定机场执行多跑道 FCFS
        """
        if not flights:
            return []

        # 按到达/出发机场分组
        ap_map = {}
        for f in flights:
            ap = f.arrival_airport if landing else f.departure_airport
            ap_map.setdefault(ap, []).append(f)

        all_schedule = []
        for ap, flist in ap_map.items():
            sched, _ = self.solve_multi_runway(flist, ap)
            # 过滤类型
            filtered = [s for s in sched if s['type'] == ('landing' if landing else 'takeoff')]
            all_schedule.extend(filtered)

        return all_schedule

    def solve_optimized(self, flights, landing=True, max_position_shift=3):
        """
        兼容旧接口：多跑道 ILS-CPS 优化（在每条跑道内局部优化排序）
        """
        if not flights:
            return []

        # 先做多跑道分配拿到初始调度
        ap_map = {}
        for f in flights:
            ap = f.arrival_airport if landing else f.departure_airport
            ap_map.setdefault(ap, []).append(f)

        all_schedule = []
        for ap, flist in ap_map.items():
            sched, _ = self.solve_multi_runway(flist, ap)
            # 优化每条跑道内的排序
            n_rwys = self.get_runway_count(ap)
            for r in range(1, n_rwys + 1):
                rwy_items = [s for s in sched if s['runway'] == r]
                if len(rwy_items) >= 2:
                    rwy_items = self._optimize_runway_ils(rwy_items, max_position_shift)
                all_schedule.extend(rwy_items)

        # 只返回指定类型的
        target_type = 'landing' if landing else 'takeoff'
        return [s for s in all_schedule if s['type'] == target_type]

    def compare(self, flights, landing=True):
        """对比 FCFS 和优化方案"""
        fcfs = self.solve_fcfs(flights, landing)
        opt = self.solve_optimized(flights, landing)

        fcfs_total = sum(s['delay'] for s in fcfs)
        opt_total = sum(s['delay'] for s in opt)
        improvement = round((fcfs_total - opt_total) / max(fcfs_total, 1) * 100, 1)

        return {
            'fcfs': {
                'schedule': fcfs,
                'total_delay': fcfs_total,
                'avg_delay': round(fcfs_total / max(len(fcfs), 1), 1),
            },
            'optimized': {
                'schedule': opt,
                'total_delay': opt_total,
                'avg_delay': round(opt_total / max(len(opt), 1), 1),
            },
            'improvement': improvement,
        }

    # ============== 内部方法 ==============

    def _optimize_runway_ils(self, items, max_position_shift):
        """在单条跑道内做 ILS-CPS 局部搜索优化"""
        import copy

        n = len(items)
        if n <= 1:
            return items

        cats = [item['category'] for item in items]
        targets = [item['target_time'] for item in items]

        def eval_seq(order):
            total = 0
            current = 0
            for i, idx in enumerate(order):
                actual = max(targets[idx], current)
                total += actual - targets[idx]
                dur = items[idx]['runway_duration']
                if i < n - 1:
                    sep = self._get_separation(cats[idx], cats[order[i + 1]])
                    current = actual + dur + sep
            return total

        best_order = list(range(n))
        best_val = eval_seq(best_order)

        improved = True
        iteration = 0
        while improved and iteration < 200:
            improved = False
            iteration += 1
            for i in range(n - 1):
                new_order = best_order[:]
                new_order[i], new_order[i + 1] = new_order[i + 1], new_order[i]
                if abs(new_order[i] - i) > max_position_shift:
                    continue
                v = eval_seq(new_order)
                if v < best_val:
                    best_val = v
                    best_order = new_order
                    improved = True

        # 按优化后的顺序重新计算时间
        result = []
        current = 0
        for j, idx in enumerate(best_order):
            item = dict(items[idx])
            actual = max(item['target_time'], current)
            item['actual_time'] = actual
            item['delay'] = actual - item['target_time']
            item['end_time'] = actual + item['runway_duration']
            if j < n - 1:
                next_cat = cats[best_order[j + 1]]
                sep = self._get_separation(item['category'], next_cat)
                current = actual + item['runway_duration'] + sep
            result.append(item)

        return result

    def _set_airport(self, airport):
        """设置当前处理的机场（兼容旧接口）"""
        self._current_airport_cfg = airport

    def _get_category(self, flight):
        """根据机型返回尾流类别（按《民用航空空中交通管理规则》CCAR-93 机型分类：
        重型 = MTOW≥136000kg；中型 = 7000kg~136000kg；轻型 = ≤7000kg）
        A319/A320/A321 均为中型机。
        """
        ac_type = flight.ac_type
        if ac_type in ['A330', 'A340', 'A350', 'A380', 'B767', 'B777', 'B787', 'B747', 'B787-9']:
            return 'heavy'
        elif ac_type in ['A319', 'A320', 'A321', 'B737', 'B738', 'B739', 'ARJ21', 'C919']:
            return 'medium'
        else:
            return 'light'

    def _get_runway_duration(self, category, ac_type=None):
        """跑道占用时长（分钟）— 考虑机型：重型机占用最久（3 分钟）；
        中型机中 A321 机身最长、占用略久（3 分钟），A319/A320 等 2 分钟。
        """
        if category == 'heavy':
            return 3
        if category == 'medium' and ac_type == 'A321':
            return 3
        return 2

    def _get_separation(self, cat1, cat2):
        """尾流安全间隔（分钟）"""
        return MIN_SEPARATION.get((cat1, cat2), 3)

    @staticmethod
    def _empty_stats():
        return {
            'runways': 1,
            'total_flights': 0,
            'landing_count': 0,
            'takeoff_count': 0,
            'total_delay': 0,
            'avg_delay': 0,
        }
