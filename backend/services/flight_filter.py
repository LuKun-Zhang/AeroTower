"""航班计划筛选模块

职责：从原始航班计划中筛选出能组成合法任务链的航班。

筛选指标（面向川航）：
1. 航司识别：仅保留川航（航班号3U开头）航班
2. 基地闭环：任务链首末必须在川航基地（硬约束）
3. 空间衔接：前序到达机场 == 后续出发机场（飞机不能瞬移）
4. 时间衔接：到达时间 + MIN_TURNAROUND ≤ 下一班出发时间
5. 机型一致：同一条链内机型必须相同
6. 最大天数：单条任务链 ≤ MAX_CHAIN_DAYS 天
7. 最大段数：单天 ≤ MAX_SEGMENTS_PER_DAY 段

输出：
- closed_flights:  能组成基地闭环的航班
- orphan_flights:  暂时无法闭环的航班（含原因说明）
- chains:          所有合法的任务链
- stats:           筛选统计
"""
import bisect
from collections import defaultdict, Counter

from ..services.data_service import data_service

# 川航基地
SICHUAN_BASES = {'成都', '重庆', '昆明', '宜宾', '绵阳', '杭州'}

# 筛选参数
MIN_TURNAROUND = 60       # 最小过站时间（分钟）
MAX_CHAIN_DAYS = 5         # 最大任务链天数
MAX_SEGMENTS_PER_DAY = 5   # 单天最大航段数
MAX_DAILY_FLIGHT_MIN = 8 * 60     # 单天最大飞行时间（分钟）
MAX_DAILY_DUTY_MIN = 14 * 60      # 单天最大执勤时间（分钟）


def _flight_date_key(f):
    """航班日期键 '2020-11-30'"""
    y, m, d, *_ = f.time_departure
    return f"{y}-{m:02d}-{d:02d}"


def _day_number(date_str):
    """将日期字符串转为连续天数（以 2020-11-01 为第 0 天）"""
    parts = date_str.split('-')
    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    days = y * 365 + y // 4 - y // 100 + y // 400
    month_days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    days += month_days[m - 1] + d
    if m <= 2:
        days -= 1
    return days

# 基准日 2020-11-01 的绝对天数（避免递归）
_BASE_DAY = _day_number('2020-11-01')


def filter_flights(max_chains=500, timeout_sec=10, custom_flights=None):
    """主筛选函数

    参数:
        custom_flights: 外部传入的 Flight 对象列表，为 None 时从 data_service 加载

    返回: {
        'closed_flights': [Flight, ...],
        'orphan_flights': [{'flight': Flight, 'reason': str}, ...],
        'chains': [[Flight, ...], ...],
        'stats': {...}
    }
    """
    import time
    start_time = time.time()

    if custom_flights is not None:
        sc_flights = list(custom_flights)
    else:
        data_service.load_all()
        sc_flights = [f for f in data_service.flights if f.flight_no.startswith('3U')]

    # ========== Step 2: 按出发机场分组索引 ==========
    by_dep = defaultdict(list)
    for f in sc_flights:
        by_dep[f.departure_airport].append(f)
    for lst in by_dep.values():
        lst.sort(key=lambda x: x.departure_minutes)

    # 预计算日期
    date_str = {}
    date_day = {}
    for f in sc_flights:
        dk = _flight_date_key(f)
        date_str[f.flight_id] = dk
        date_day[f.flight_id] = _day_number(dk) - _BASE_DAY

    # ========== Step 3: 构建连接图 ==========
    # connections[flight_id] = [可衔接的下一航班列表]
    connections = {}
    for a in sc_flights:
        arr_ap = a.arrival_airport
        candidates = by_dep.get(arr_ap, [])
        if not candidates:
            connections[a.flight_id] = []
            continue

        a_arr = a.arrival_minutes
        a_date = date_str[a.flight_id]
        a_day = date_day[a.flight_id]

        # 二分查找出发时间 >= 到达 + 最小间隔
        dep_mins = [f.departure_minutes for f in candidates]
        lo = bisect.bisect_left(dep_mins, a_arr + MIN_TURNAROUND)

        conn_list = []
        for j in range(lo, len(candidates)):
            b = candidates[j]
            if b.flight_id == a.flight_id:
                continue
            gap = b.departure_minutes - a_arr
            b_date = date_str[b.flight_id]
            b_day = date_day[b.flight_id]
            day_diff = b_day - a_day
            min_gap = MIN_TURNAROUND
            if day_diff >= 1:
                min_gap = 600  # 跨天休息至少10小时
            if gap >= min_gap:
                # 机型必须相同
                if b.ac_type == a.ac_type:
                    conn_list.append(b)
                    if len(conn_list) >= 8:
                        break
            elif gap < MIN_TURNAROUND:
                continue

        connections[a.flight_id] = conn_list

    # ========== Step 4: 迭代式DFS枚举基地闭环任务链 ==========
    chains = []
    covered_ids = set()
    MAX_DEPTH = 20  # 最大链长度限制

    # 从每个基地出发的航班作为起点
    start_flights = [f for f in sc_flights
                     if f.departure_airport in SICHUAN_BASES]
    by_base = defaultdict(list)
    for f in start_flights:
        by_base[f.departure_airport].append(f)

    for base, flist in by_base.items():
        flist.sort(key=lambda x: x.departure_minutes)
        # 每基地配额：少量高质量链，减少重叠
        per_base_quota = max_chains // max(len(by_base), 1)
        base_count = 0
        for start_f in flist[:15]:
            if time.time() - start_time > timeout_sec:
                break
            if base_count >= per_base_quota:
                break

            # 迭代式 DFS 栈: (flight, depth, path_tuple, path_set_frozenset,
            #                 day_stats_json, path_day0, path_day_last)
            path = [start_f]
            path_set = {start_f.flight_id}
            d0 = date_str[start_f.flight_id]
            day_stats = {d0: [start_f.timespan,
                              start_f.departure_minutes,
                              start_f.arrival_minutes, 1]}
            path_day0 = date_day[start_f.flight_id]

            # 栈中存储: (next_flight, depth, 参数副本)
            # 格式: (flight, depth, path_copy, path_set_copy, day_stats_copy, pd0, pd_last)
            stack = [(start_f, 0, path, path_set, day_stats, path_day0, path_day0,
                      iter(connections.get(start_f.flight_id, [])))]

            while stack:
                if time.time() - start_time > timeout_sec:
                    break
                if base_count >= per_base_quota:
                    break

                cur_f, depth, cp, ps, ds, pd0, pd_last, conn_iter = stack[-1]

                try:
                    next_f = next(conn_iter)
                except StopIteration:
                    stack.pop()
                    continue

                fid = next_f.flight_id
                if fid in ps:
                    continue

                next_date = date_str[fid]
                next_day = date_day[fid]
                span_days = max(pd_last, next_day) - pd0 + 1

                if span_days > MAX_CHAIN_DAYS:
                    continue
                if depth + 1 > MAX_DEPTH:
                    continue

                # 日段数检查
                s = ds.get(next_date)
                if s and s[3] >= MAX_SEGMENTS_PER_DAY:
                    continue

                # 日飞行/执勤剪枝
                if not _can_add_to_day(next_f, s):
                    continue

                # 推进
                np = cp + [next_f]
                nps = ps | {fid}
                nds = dict(ds)
                if s is None:
                    nds[next_date] = [next_f.timespan, next_f.departure_minutes,
                                      next_f.arrival_minutes, 1]
                else:
                    ns = nds[next_date]
                    nds[next_date] = [ns[0] + next_f.timespan,
                                      min(ns[1], next_f.departure_minutes),
                                      max(ns[2], next_f.arrival_minutes),
                                      ns[3] + 1]
                npd0 = min(pd0, next_day)
                npd_last = max(pd_last, next_day)

                # 基地闭环检查
                if next_f.arrival_airport in SICHUAN_BASES and len(np) >= 2:
                    chains.append(np)
                    base_count += 1
                    for ff in np:
                        covered_ids.add(ff.flight_id)
                    if base_count >= per_base_quota:
                        break

                # 继续扩展
                if npd_last - npd0 + 1 < MAX_CHAIN_DAYS:
                    stack.append((next_f, depth + 1, np, nps, nds, npd0, npd_last,
                                  iter(connections.get(fid, []))))

            if time.time() - start_time > timeout_sec:
                break
        if time.time() - start_time > timeout_sec:
            break

    # ========== Step 5: 分类航班 ==========
    closed_ids = set()
    for chain in chains:
        for f in chain:
            closed_ids.add(f.flight_id)

    closed_flights = [f for f in sc_flights if f.flight_id in closed_ids]
    orphan_flights = []

    for f in sc_flights:
        if f.flight_id not in closed_ids:
            reasons = []
            if f.departure_airport not in SICHUAN_BASES:
                dep_has_prev = any(
                    b.arrival_airport == f.departure_airport
                    for b in sc_flights if b.flight_id != f.flight_id
                )
                if not dep_has_prev:
                    reasons.append("无前序航班可抵达该出发机场")
                elif f.arrival_airport not in SICHUAN_BASES:
                    reasons.append("出发非基地且无法闭环")
            elif f.arrival_airport not in SICHUAN_BASES:
                has_next = len(connections.get(f.flight_id, [])) > 0
                if not has_next:
                    reasons.append(f"抵达{f.arrival_airport}后无后续航班可衔接回基地")
            else:
                reasons.append("虽从基地出发到基地，但无法与其他航班组成优化任务链")
            if not reasons:
                reasons.append("无法组成完整闭环任务链")

            orphan_flights.append({
                'flight': f.to_dict(),
                'reason': ', '.join(reasons),
            })

    # ========== Step 6: 统计 ==========
    orphan_reasons = Counter(
        r['reason'] for r in orphan_flights
    )

    # 站点覆盖
    closed_cities = set()
    for f in closed_flights:
        closed_cities.add(f.departure_airport)
        closed_cities.add(f.arrival_airport)
    all_cities = set()
    for f in sc_flights:
        all_cities.add(f.departure_airport)
        all_cities.add(f.arrival_airport)

    stats = {
        'total_flights': len(sc_flights),
        'closed_count': len(closed_flights),
        'orphan_count': len(orphan_flights),
        'chain_count': len(chains),
        'coverage_pct': round(len(closed_flights) / len(sc_flights) * 100, 1),
        'city_coverage': f"{len(closed_cities)}/{len(all_cities)}",
        'orphan_reasons': dict(orphan_reasons.most_common(5)),
        'timeout': time.time() - start_time > timeout_sec,
        'elapsed_sec': round(time.time() - start_time, 2),
    }

    return {
        'closed_flights': closed_flights,
        'orphan_flights': orphan_flights,
        'chains': chains,
        'stats': stats,
    }


def _can_add_to_day(flight, day_stats):
    """检查航班能否加入某天"""
    if day_stats is None:
        return True
    total_flight, duty_start, duty_end, _ = day_stats
    if total_flight + flight.timespan > MAX_DAILY_FLIGHT_MIN:
        return False
    new_start = min(duty_start, flight.departure_minutes)
    new_end = max(duty_end, flight.arrival_minutes)
    if new_end - new_start > MAX_DAILY_DUTY_MIN:
        return False
    return True
