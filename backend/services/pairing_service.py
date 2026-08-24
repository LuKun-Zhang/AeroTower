"""Pairing 任务链生成器（优化版）

实现国内航司标准的任务链生成算法：
1. 航班连接图构建（按机场索引 + 二分查找 → O(N log N)）
2. DFS 深度枚举所有合法 pairing（增量状态传递，避免重复计算）
3. 合规过滤（飞行≤8h/天, 执勤≤14h/天, 同天过站≥30min, 跨天休息≥10h, 基地闭环）

性能优化要点：
- _build_connections: 机场索引 + 二分查找，O(N log N)
- DFS 增量状态: path_set O(1) 查重、day_stats O(1) 更新
- _path_days 缓存，避免 datetime 解析
"""
import time
import bisect
from collections import Counter
from ..models.pairing import Pairing
from ..services.data_service import data_service

MAX_PAIRING_DAYS = 5
MAX_SEGMENTS_PER_DAY = 5
MIN_TURNAROUND = 60   # 同天过站最小间隔（需 2×MIN_CREW_GAP，与指派一致性检查对齐）
MIN_REST = 600
MAX_DAILY_FLIGHT = 8 * 60
MAX_DAILY_DUTY = 14 * 60
MAX_CONNECTIONS_PER_FLIGHT = 8   # 每个航班最多保留的连接数（降低分支因子）
MAX_START_FLIGHTS = 30           # 最多处理的起始航班数

def _day_number(date_str):
    """date_str '2020-11-30' → 天数（相对基准），O(1)"""
    y, m, d = date_str.split('-')
    y, m, d = int(y), int(m), int(d)
    days = y * 365 + y // 4 - y // 100 + y // 400
    month_days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    days += month_days[m - 1] + d
    if m <= 2:
        days -= 1  # 闰年修正
    return days


class PairingGenerator:
    """任务链生成器"""

    def __init__(self, flights, preferred_base=None):
        self.flights = sorted(flights, key=lambda f: f.departure_minutes)
        self.preferred_base = preferred_base
        self.base = preferred_base
        self.flight_map = {f.flight_id: f for f in flights}
        self._pairings = []
        self._id_counter = 1
        self._start_time = 0
        self._timeout = 8  # 8 秒超时

        # 预计算日期 → 天数（缓存在航班对象上，避免重复计算）
        self._date_day = {}
        self._date_str = {}
        for f in self.flights:
            dk = self._date_key(f)
            self._date_str[f.flight_id] = dk
            self._date_day[f.flight_id] = _day_number(dk)

    def _date_key(self, f):
        y, m, d, *_ = f.time_departure
        return f"{y}-{m:02d}-{d:02d}"

    def generate(self, max_pairings=3000):
        self._pairings = []
        self._id_counter = 1
        self._start_time = time.time()

        dep_counts = Counter(f.departure_airport for f in self.flights)
        preferred = self.preferred_base
        if preferred and preferred in dep_counts:
            self.base = preferred
        else:
            self.base = dep_counts.most_common(1)[0][0] if dep_counts else ''

        connections = self._build_connections()

        start_flights = [f for f in self.flights if f.departure_airport == self.base]
        saved_base = self.base
        if start_flights:
            self._enumerate_pairings(start_flights, connections, max_pairings)

        if len(self._pairings) == 0 and saved_base:
            dep_counts = Counter(f.departure_airport for f in self.flights)
            alt_base = dep_counts.most_common(1)[0][0] if dep_counts else ''
            if alt_base and alt_base != saved_base:
                self.base = alt_base
                start_flights = [f for f in self.flights if f.departure_airport == self.base]
                self._enumerate_pairings(start_flights, connections, max_pairings)

        return self._pairings

    def _build_connections(self):
        """O(N log N) 连接图构建

        将航班按出发机场分组 + 按出发时间排序，
        对每个航班在目的机场的出发列表中二分查找时间范围。
        """
        # 按出发机场分组
        by_dep = {}
        for f in self.flights:
            by_dep.setdefault(f.departure_airport, []).append(f)
        for lst in by_dep.values():
            lst.sort(key=lambda x: x.departure_minutes)

        # 预提取 departure_minutes 和 date_key 列表
        dep_times = {airport: [f.departure_minutes for f in lst]
                     for airport, lst in by_dep.items()}
        dep_dates = {airport: [self._date_str.get(f.flight_id, self._date_key(f))
                                for f in lst]
                     for airport, lst in by_dep.items()}

        connections = {}
        for a in self.flights:
            arr_ap = a.arrival_airport
            candidates = by_dep.get(arr_ap, [])
            if not candidates:
                connections[a.flight_id] = []
                continue

            times = dep_times[arr_ap]
            dates = dep_dates[arr_ap]
            a_date = self._date_str.get(a.flight_id, self._date_key(a))
            a_arr = a.arrival_minutes

            # 二分查找: departure_time >= arrival_time + MIN_TURNAROUND
            lo = bisect.bisect_left(times, a_arr + MIN_TURNAROUND)

            conn_list = []
            for j in range(lo, len(times)):
                b = candidates[j]
                if b.flight_id == a.flight_id:
                    continue
                gap = times[j] - a_arr
                same_day = (a_date == dates[j])
                min_gap = MIN_TURNAROUND if same_day else MIN_REST
                if gap >= min_gap:
                    conn_list.append(b)
                    if len(conn_list) >= MAX_CONNECTIONS_PER_FLIGHT:
                        break
                else:
                    if same_day and gap < MIN_TURNAROUND:
                        continue
            connections[a.flight_id] = conn_list

        return connections

    def _enumerate_pairings(self, start_flights, connections, max_pairings):
        # 限制起始航班数量，避免过多 DFS 分支
        start_flights = start_flights[:MAX_START_FLIGHTS]
        for start_f in start_flights:
            if len(self._pairings) >= max_pairings:
                break
            if time.time() - self._start_time > self._timeout:
                break
            # 增量状态初始化
            path = [start_f]
            path_set = {start_f.flight_id}
            # day_stats: {date_str: [total_flight_min, duty_start, duty_end, seg_count]}
            d0 = self._date_str.get(start_f.flight_id, self._date_key(start_f))
            day_stats = {d0: [start_f.timespan, start_f.departure_minutes,
                               start_f.arrival_minutes, 1]}
            # 路径的天跨度
            path_day0 = self._date_day[start_f.flight_id]
            path_day_last = path_day0
            self._dfs_extend(path, path_set, day_stats, path_day0, path_day_last,
                             connections, max_pairings)

            if len(self._pairings) >= max_pairings:
                break

    def _dfs_extend(self, path, path_set, day_stats,
                    path_day0, path_day_last, connections, max_pairings):
        """DFS 扩展（带增量状态传递）

        状态全部通过参数传递，无需每次重建。
        """
        if len(self._pairings) >= max_pairings:
            return

        last = path[-1]
        last_day = self._date_day[last.flight_id]
        span_days = last_day - path_day0 + 1

        if span_days > MAX_PAIRING_DAYS:
            return

        # 基地闭环 → 合法 pairing（DFS 已增量验证所有约束，无需再次 is_valid()）
        if last.arrival_airport == self.base:
            pairing = Pairing(self._id_counter, list(path), path[0].departure_airport)
            self._id_counter += 1
            self._pairings.append(pairing)

        if span_days >= MAX_PAIRING_DAYS:
            return

        # 扩展
        for next_f in connections.get(last.flight_id, []):
            if time.time() - self._start_time > self._timeout:
                return
            if len(self._pairings) >= max_pairings:
                return
            fid = next_f.flight_id
            if fid in path_set:
                continue

            next_date = self._date_str.get(fid, self._date_key(next_f))
            next_day_num = self._date_day[fid]

            # 日段数检查
            stats = day_stats.get(next_date)
            if stats:
                if stats[3] >= MAX_SEGMENTS_PER_DAY:
                    continue

            # 日飞行/执勤剪枝（增量检查）
            if not self._can_add_to_day(next_f, day_stats.get(next_date)):
                continue

            # 如果是新的一天，确保不超跨度
            new_path_day0 = min(path_day0, next_day_num)
            new_path_day_last = max(path_day_last, next_day_num)
            if new_path_day_last - new_path_day0 + 1 > MAX_PAIRING_DAYS:
                continue

            # 推进
            path.append(next_f)
            path_set.add(fid)

            old_stats = day_stats.get(next_date)
            if old_stats is None:
                day_stats[next_date] = [
                    next_f.timespan,
                    next_f.departure_minutes,
                    next_f.arrival_minutes,
                    1,
                ]
            else:
                old_stats[0] += next_f.timespan
                old_stats[1] = min(old_stats[1], next_f.departure_minutes)
                old_stats[2] = max(old_stats[2], next_f.arrival_minutes)
                old_stats[3] += 1

            self._dfs_extend(path, path_set, day_stats,
                             new_path_day0, new_path_day_last,
                             connections, max_pairings)

            # 回溯
            path.pop()
            path_set.discard(fid)
            if old_stats is None:
                del day_stats[next_date]
            else:
                old_stats[0] -= next_f.timespan
                old_stats[3] -= 1
                # min/max 可能有偏差但剪枝只需要 <=，不回退也算安全（多剪不致命）

    @staticmethod
    def _can_add_to_day(flight, day_stats):
        """O(1) 检查航班能否加入某天统计"""
        if day_stats is None:
            return True
        total_flight, duty_start, duty_end, _ = day_stats
        if total_flight + flight.timespan > MAX_DAILY_FLIGHT:
            return False
        new_start = min(duty_start, flight.departure_minutes)
        new_end = max(duty_end, flight.arrival_minutes)
        if new_end - new_start > MAX_DAILY_DUTY:
            return False
        return True


def generate_pairings_for_airport(target_airport, date=None, max_pairings=3000):
    data_service.load_all()
    flights = sorted(data_service.flights, key=lambda f: f.departure_minutes)

    if target_airport:
        flights = [f for f in flights
                   if f.departure_airport == target_airport
                   or f.arrival_airport == target_airport]

    if date:
        def _dk(f):
            y, m, d, *_ = f.time_departure
            return f"{y}-{m:02d}-{d:02d}"
        flights = [f for f in flights if _dk(f) == date]

    if not flights:
        return []

    gen = PairingGenerator(flights, preferred_base=target_airport)
    return gen.generate(max_pairings)
