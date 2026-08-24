"""飞机排班算法服务
使用 OR-Tools VRP 求解器 + 二分图最大匹配两种算法

基地闭环约束：
- 四川航空基地：成都、重庆、昆明、宜宾、绵阳、杭州
- 每架飞机必须从川航基地出发、最终回到川航基地（过夜检修）
- 中间可以在外站飞行，但不能"终结"在外地
- 按飞机综合质量指数分配：指数高优先分配，单机限制 max_daily_flights 确保均匀
"""
from ..models.aircraft import Aircraft
from ..services.data_service import data_service, _load_aircraft_index
from ..services.aircraft_types import type_layout

# 四川航空基地机场（飞机过夜维护基地）
SICHUAN_AIRLINES_BASES = {'成都', '重庆', '昆明', '宜宾', '绵阳', '杭州'}


def _create_aircraft_with_index(ac_id, tail_no, base=''):
    """根据指标预设文件创建带综合指数的飞机"""
    index_map = _load_aircraft_index()
    metrics = index_map.get(tail_no, {})
    ac_type = metrics.get('ac_type', 'A319')
    return Aircraft(
        ac_id=ac_id,
        ac_type=ac_type,
        layout=type_layout(ac_type),
        tail_no=tail_no,
        base=base,
        age_years=metrics.get('age_years', 5.0),
        total_flight_hours=metrics.get('total_flight_hours', 25000),
        maintenance_days=metrics.get('maintenance_days', 0),
        cost_per_hour=metrics.get('cost_per_hour', 20000),
        fuel_efficiency=metrics.get('fuel_efficiency', 0.90),
        last_overhaul=metrics.get('last_overhaul', ''),
        on_time_rate=metrics.get('on_time_rate', 0.95),
        cycles=metrics.get('cycles', 10000),
    )


def _get_active_bases(flights):
    """获取航班数据中实际出现的川航基地（按航班数量降序）"""
    base_counts = {}
    for f in flights:
        dep = f.departure_airport
        if dep in SICHUAN_AIRLINES_BASES:
            base_counts[dep] = base_counts.get(dep, 0) + 1
    return sorted(base_counts.keys(), key=lambda b: -base_counts[b])


def _filter_base_closed(aircrafts):
    """过滤：只保留末航班回到川航基地的飞机（基地闭环）"""
    closed = []
    for a in aircrafts:
        if not a.assigned_flights:
            continue
        first_dep = a.assigned_flights[0].departure_airport
        last_arr = a.assigned_flights[-1].arrival_airport
        if first_dep in SICHUAN_AIRLINES_BASES and last_arr in SICHUAN_AIRLINES_BASES:
            closed.append(a)
    return closed


def _chain_max_daily_segments(chain):
    """链中单日最大段数（一架飞机一天最多执行的航班数）。

    任务链是跨多天的完整排班，日上限约束的是「单日段数」而不是整条链的总段数，
    用总段数判断会把合法长链误判为超限。
    """
    counts = {}
    for f in chain:
        dk = (f.time_departure[1], f.time_departure[2])
        counts[dk] = counts.get(dk, 0) + 1
    return max(counts.values()) if counts else 0


class AircraftRoutingService:
    """飞机排班"""

    def __init__(self):
        pass

    def solve_vrp(self, flights, num_aircraft=12, min_gap=60):
        """
        方法1: 平衡贪心分配
        轮询分配航班，确保各飞机负载均衡
        目标：用有限飞机最大化覆盖，按机型匹配
        约束：每架飞机首次航班必须从所属基地出发
        按综合质量指数限制每机每日航班上限
        """
        if not flights:
            return []

        sorted_flights = sorted(flights, key=lambda f: f.departure_minutes)

        ac_types = sorted(set(f.ac_type for f in flights))
        if not ac_types:
            ac_types = ['A319']

        active_bases = _get_active_bases(sorted_flights)

        # 创建飞机，加载综合指数，按指数降序排列（好的优先飞）
        aircrafts = []
        for i in range(num_aircraft):
            atype = ac_types[i % len(ac_types)]
            base = active_bases[i % len(active_bases)] if active_bases else ''
            tail_no = f'B-{6388 + i}'
            ac = _create_aircraft_with_index(i + 1, tail_no, base)
            # 如果预设机型与当前数据不匹配，覆盖机型
            if ac.ac_type not in ac_types:
                ac.ac_type = atype
            aircrafts.append(ac)

        # 按综合质量指数降序排列（好的飞机优先）
        aircrafts.sort(key=lambda a: -a.quality_index)
        # 重新设置 ac_id
        for i, a in enumerate(aircrafts):
            a.ac_id = i + 1

        last_flight = [None] * num_aircraft

        for f in sorted_flights:
            best_ac = None
            best_load = float('inf')
            best_gap = float('inf')
            for i, ac in enumerate(aircrafts):
                if f.ac_type != ac.ac_type:
                    continue
                if len(ac.assigned_flights) >= ac.max_daily_flights:
                    continue
                load = len(ac.assigned_flights)
                if last_flight[i] is None:
                    if f.departure_airport == ac.base:
                        # 优先分配给负载低的飞机
                        if load < best_load:
                            best_load = load
                            best_gap = 0
                            best_ac = i
                elif last_flight[i].can_connect_to(f, min_gap):
                    gap = f.departure_minutes - last_flight[i].arrival_minutes
                    # 主排序：负载低优先；次排序：衔接紧优先
                    if load < best_load or (load == best_load and gap < best_gap):
                        best_load = load
                        best_gap = gap
                        best_ac = i

            if best_ac is not None:
                aircrafts[best_ac].add_flight(f)
                last_flight[best_ac] = f

        active = [a for a in aircrafts if a.assigned_flights]
        closed = _filter_base_closed(active)
        covered = sum(len(a.assigned_flights) for a in closed)
        # 打印均衡统计
        counts = sorted([len(a.assigned_flights) for a in closed])
        idxs = sorted([a.quality_index for a in closed], reverse=True)
        print(f"[VRP/Balanced] {len(flights)} 航班 -> {len(active)} 架原始, "
              f"{len(closed)} 架闭环, 覆盖={covered}班")
        print(f"[VRP/Balanced] 航班分布: {counts}, 质量指数: {idxs}")
        return closed

    def solve_bipartite(self, flights, min_gap=60):
        """
        方法2: 二分图最大匹配（保留原项目算法）
        构建有向图 -> 匈牙利算法 -> 路径覆盖
        增加机型匹配限制
        """
        n = len(flights)

        # 构建邻接矩阵（同机型才能衔接）
        graph = [[False] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j and flights[i].ac_type == flights[j].ac_type \
                        and flights[i].can_connect_to(flights[j], min_gap):
                    graph[i][j] = True

        # 匈牙利算法
        pre_matched = [-1] * n
        post_matched = [-1] * n
        matched_num = 0

        def dfs(x):
            for y in range(n):
                if y == x:
                    continue
                if graph[x][y] and not visited[y]:
                    visited[y] = True
                    if pre_matched[y] == -1 or dfs(pre_matched[y]):
                        pre_matched[y] = x
                        post_matched[x] = y
                        return True
            return False

        for x in range(n):
            visited = [False] * n
            if dfs(x):
                matched_num += 1

        # 路径覆盖
        visited = [False] * n
        paths = []
        for i in range(n):
            if not visited[i]:
                path = []
                # 回溯到路径起点
                x = i
                while pre_matched[x] != -1:
                    x = pre_matched[x]
                # 正向遍历
                while x != -1:
                    visited[x] = True
                    path.append(x)
                    x = post_matched[x]
                paths.append(path)

        # 转换为飞机分配，强制基地闭环约束：
        # 1. 路径首航班必须从川航基地出发（飞机从基地开始一天的工作）
        # 2. 路径末航班必须回到川航基地（飞机回基地过夜检修）
        result = []
        excluded = 0
        for i, path in enumerate(paths):
            if not path:
                continue
            first_f = flights[path[0]]
            last_f = flights[path[-1]]
            # 基地闭环检查
            if first_f.departure_airport not in SICHUAN_AIRLINES_BASES:
                excluded += len(path)
                continue
            if last_f.arrival_airport not in SICHUAN_AIRLINES_BASES:
                excluded += len(path)
                continue

            ac = _create_aircraft_with_index(
                ac_id=len(result) + 1,
                tail_no=f'B-{6388 + len(result)}',
                base=first_f.departure_airport,
            )
            for idx in path:
                ac.add_flight(flights[idx])
            result.append(ac)

        total_in_paths = sum(len(p) for p in paths)
        print(f"[Bipartite] {len(flights)} 航班 -> {len(paths)} 条路径, 匹配数={matched_num}, "
              f"基地闭环={len(result)}条, 排除={excluded}个航班(非基地起降)")
        return result

    def solve_greedy_only(self, flights, num_aircraft=12, min_gap=60):
        """
        方法3: 纯贪心算法
        不依赖 OR-Tools，稳定可靠
        """
        result = self._greedy_routing(flights, num_aircraft, min_gap)
        # 基地闭环后处理
        return _filter_base_closed(result)

    def _greedy_routing(self, flights, num_aircraft, min_gap):
        """贪心分配算法（机型匹配 + 基地闭环 + 按综合指数均匀分配）

        约束：每架飞机首次航班必须从其所属基地出发，
        后续航班通过机场衔接自动延长任务链。
        限制：每架飞机不超过 max_daily_flights
        """
        ac_types = sorted(set(f.ac_type for f in flights)) or ['A319']
        active_bases = _get_active_bases(flights)

        aircrafts = []
        used = [False] * len(flights)
        total_flights = len(flights)
        sorted_indices = list(range(total_flights))

        for ac_idx in range(num_aircraft):
            if all(used):
                break
            atype = ac_types[ac_idx % len(ac_types)]
            base = active_bases[ac_idx % len(active_bases)] if active_bases else ''
            tail_no = f'B-{6388 + ac_idx}'
            ac = _create_aircraft_with_index(ac_idx + 1, tail_no, base)
            if ac.ac_type not in ac_types:
                ac.ac_type = atype
            last_flight = None
            for idx in sorted_indices:
                if used[idx]:
                    continue
                f = flights[idx]
                if f.ac_type != ac.ac_type:
                    continue
                if len(ac.assigned_flights) >= ac.max_daily_flights:
                    break
                if last_flight is None:
                    if f.departure_airport != ac.base:
                        continue
                elif not last_flight.can_connect_to(f, min_gap):
                    continue

                ac.add_flight(f)
                last_flight = f
                used[idx] = True
            if ac.assigned_flights:
                aircrafts.append(ac)

        return aircrafts

    def get_stats(self, aircrafts, total_flights):
        """计算排班统计指标"""
        if not aircrafts:
            return {}

        total_used = len(aircrafts)

        covered = sum(len(a.assigned_flights) for a in aircrafts)
        avg_util = round(sum(a.utilization for a in aircrafts) / max(total_used, 1), 1)
        total_idle = sum(a.idle_time for a in aircrafts)

        # 统计各基地飞机数
        base_distribution = {}
        for a in aircrafts:
            b = a.base
            base_distribution[b] = base_distribution.get(b, 0) + 1

        # 基地闭环验证
        base_closed = 0
        for a in aircrafts:
            if a.assigned_flights and a.base:
                first_dep = a.assigned_flights[0].departure_airport
                last_arr = a.assigned_flights[-1].arrival_airport
                if first_dep in SICHUAN_AIRLINES_BASES and last_arr in SICHUAN_AIRLINES_BASES:
                    base_closed += 1

        return {
            'aircraft_count': total_used,
            'total_flights': total_flights,
            'coverage': round(covered / max(total_flights, 1) * 100, 1),
            'avg_utilization': avg_util,
            'total_idle_time_minutes': total_idle,
            'base_distribution': base_distribution,
            'base_closed_count': base_closed,
        }

    def solve_chain_coverage(self, chains, num_aircraft=100, min_gap=60, excluded_aircraft=None):
        """
        方法4: 链集合覆盖排班（航司标准做法）
        
        1) 贪心集合覆盖选出互不冲突的链子集
        2) 链按总飞行分钟降序 → 匹配到质量指数降序的飞机（好飞机飞飞行时间长的重链）
        
        参数:
            chains: 任务链列表，每个元素是 Flight 对象列表
            num_aircraft: 最大飞机数
            min_gap: 最小过站时间
            excluded_aircraft: 排除的飞机尾号列表（如 ['B-6388', 'B-6390']）
        """
        if not chains:
            return []

        excluded_set = set(excluded_aircraft or [])

        # 收集所有航班ID
        all_fids = set()
        for chain in chains:
            for f in chain:
                all_fids.add(f.flight_id)

        # 构建链索引，只保留满足基地闭环的链
        chain_infos = []
        for ci, chain in enumerate(chains):
            first_dep = chain[0].departure_airport
            last_arr = chain[-1].arrival_airport
            if first_dep not in SICHUAN_AIRLINES_BASES or last_arr not in SICHUAN_AIRLINES_BASES:
                continue  # 不满足基地闭环，跳过
            chain_infos.append({
                'idx': ci,
                'chain': chain,
                'flight_ids': set(f.flight_id for f in chain),
                'length': len(chain),
                'total_min': sum(f.timespan for f in chain),  # 链总飞行分钟（含空飞）
                'ac_type': chain[0].ac_type,
                'base': chain[0].departure_airport,
            })

        # 阶段1：选互不重叠的链（飞行时间长的链优先），每条链完整分配给一架飞机
        chain_infos.sort(key=lambda c: -c['total_min'])
        selected_cfs = []  # 选中的链
        covered_fids = set()
        for cfs in chain_infos:
            if cfs['flight_ids'] & covered_fids:
                continue
            selected_cfs.append(cfs)
            covered_fids |= cfs['flight_ids']

        # 阶段2：飞机按质量降序 + 链按总飞行分钟降序 → 最重的链配最好的飞机
        #        （低指数飞机接到剩余飞行时间短的轻链）；跳过超出飞机段数上限的链
        all_aircrafts = []
        pool_idx = 0
        while len(all_aircrafts) < num_aircraft:
            tail = f'B-{6388 + pool_idx}'
            if tail not in excluded_set:
                ac = _create_aircraft_with_index(pool_idx + 1, tail, base='')
                all_aircrafts.append(ac)
            pool_idx += 1
        all_aircrafts.sort(key=lambda a: -a.quality_index)

        aircrafts = []
        ac_used = [False] * num_aircraft
        assigned_fids = set()

        for cfs in selected_cfs:
            chain = cfs['chain']
            # 找质量最高、机型匹配且未用的飞机（重链优先配好飞机）
            best_ac = None
            best_idx_ac = -1
            for i, ac in enumerate(all_aircrafts):
                if ac_used[i]:
                    continue
                if ac.ac_type != cfs['ac_type']:
                    continue
                # 链单日最大段数不能超过飞机日上限
                if _chain_max_daily_segments(chain) > ac.max_daily_flights:
                    continue
                best_ac = ac
                best_idx_ac = i
                break  # 已按质量降序，第一个匹配的就是最好的
            if best_ac is None:
                # 放宽机型限制
                for i, ac in enumerate(all_aircrafts):
                    if ac_used[i]:
                        continue
                    if _chain_max_daily_segments(chain) > ac.max_daily_flights:
                        continue
                    best_ac = ac
                    best_idx_ac = i
                    break
            if best_ac is None:
                continue  # 没有能装下这条链的飞机，跳过

            for f in chain:
                best_ac.add_flight(f)
                assigned_fids.add(f.flight_id)
            best_ac.base = cfs['base']
            ac_used[best_idx_ac] = True
            aircrafts.append(best_ac)

        covered = sum(len(a.assigned_flights) for a in aircrafts)
        total = len(all_fids)
        used_tails = [ac.tail_no for ac in aircrafts]
        exclude_msg = f", 排除={excluded_set}" if excluded_set else ""
        tail_str = f", 使用: {used_tails[:5]}..." if len(used_tails) > 5 else f", 使用: {used_tails}"
        print(f"[ChainCoverage] {len(chains)}条链(基地闭环={len(chain_infos)}) "
              f"-> {len(aircrafts)}架飞机, 覆盖={covered}/{total}班({covered/total*100:.1f}%)"
              f"{exclude_msg}{tail_str}")
        return aircrafts
