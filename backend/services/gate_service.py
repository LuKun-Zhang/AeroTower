"""登机口分配算法服务 v2

核心改进：
- 真实登机口数量（airports_gates.json）
- 跑道归属分组：每个登机口属于特定跑道组，滑行距离影响分配
- 滑行时间偏移：gate_start = landing + taxi_in, gate_end = takeoff - taxi_out
- 运营阶段：下客/上客/过站保障 (ops_type)
- 最小缓冲区：同登机口前后航班间隔 >= 20min
- 评分增强：机型匹配 + 负载均衡 + 滑行成本 + 跑道归属偏好
"""
import os
import json
from ..models.gate import Gate
from ..services.data_service import data_service
from .experiment.seed import stable_hash

_GATES_CONFIG_PATH = os.path.normpath(os.path.join(
    os.path.abspath(__file__), '..', '..', 'data', 'airports_gates.json'
))


def _load_gates_config():
    try:
        with open(_GATES_CONFIG_PATH, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


class GateAssignmentService:
    """登机口分配服务 v2"""

    # 运营参数（可通过配置覆盖）
    MIN_BUFFER = 20          # 同登机口前后航班最小缓冲（分钟）
    TAXI_IN_DEFAULT = 5      # 默认滑入时间（分钟）
    TAXI_OUT_DEFAULT = 5     # 默认滑出时间（分钟）

    def __init__(self, rng_seed=None):
        self._gates_config = _load_gates_config()
        self._gates_by_airport = {}
        self._seed = 2024
        self._rng_seed = rng_seed

    def _get_airport_config(self, airport_name):
        """获取机场登机口配置"""
        return self._gates_config.get(airport_name, None)

    def _get_defaults(self):
        return self._gates_config.get('_defaults', {})

    # ==================== 登机口生成（真实配置版） ====================

    def generate_gates(self, target_airport=None):
        """使用 airports_gates.json 的真实数据生成登机口"""
        data_service.load_all()
        all_airports = list(data_service.airports.keys())

        if target_airport and target_airport in all_airports:
            airports = [target_airport]
        elif target_airport:
            airports = [target_airport]
        else:
            airports = [a for a in all_airports if a in ('成都', '北京', '上海', '广州')]

        all_gates = []
        for ap in airports:
            if ap not in self._gates_by_airport:
                self._gates_by_airport[ap] = self._build_gates_for_airport(ap)
            all_gates.extend(self._gates_by_airport[ap])
        return all_gates

    def _build_gates_for_airport(self, airport_name):
        """从真实配置构建登机口（含跑道归属、滑行时间）"""
        cfg = self._get_airport_config(airport_name)
        defaults = self._get_defaults()

        if not cfg:
            # 回退：配置缺失的机场使用默认值
            fallback_n = defaults.get('fallback_gate_count', 25)
            return self._build_fallback_gates(airport_name, fallback_n)

        runway_groups = cfg.get('runway_groups', [])
        if not runway_groups:
            fallback_n = defaults.get('fallback_gate_count', 25)
            return self._build_fallback_gates(airport_name, fallback_n)

        gates = []
        gate_counter = 0

        for rw_group in runway_groups:
            rw_num = rw_group['runway']
            taxi_in = rw_group.get('taxi_in_avg_min', self.TAXI_IN_DEFAULT)
            taxi_out = rw_group.get('taxi_out_avg_min', self.TAXI_OUT_DEFAULT)
            g_cfg = rw_group.get('gates', {})
            count = g_cfg.get('count', 8)
            prefix = g_cfg.get('prefix', f'{airport_name[:2]}G')

            for i in range(count):
                gate_counter += 1
                # 机型分配：前20%大、中间50%中、后30%小
                ratio = (i + 1) / count
                if ratio <= 0.20:
                    gtype = 'large'
                elif ratio <= 0.70:
                    gtype = 'medium'
                else:
                    gtype = 'small'

                start_idx = g_cfg.get('start', 1) + i
                gid = stable_hash(f"{airport_name}_rw{rw_num}_{start_idx}", 10000)
                gates.append(Gate(
                    gate_id=gid,
                    name=f"{prefix}{start_idx:02d}",
                    airport=airport_name,
                    gate_type=gtype,
                    position=gate_counter,
                    runway_group=rw_num,
                    taxi_in_min=taxi_in,
                    taxi_out_min=taxi_out,
                ))

        self._log_gate_summary(airport_name, gates, runway_groups)
        return gates

    def _build_fallback_gates(self, airport_name, num_gates):
        """回退方案：无配置时生成默认登机口（双跑道各半）"""
        n_rw = 2
        gates = []
        per_rw = num_gates // n_rw
        counter = 0

        for rw in range(1, n_rw + 1):
            count = per_rw + (num_gates - counter - per_rw if rw == n_rw else 0)
            count = min(count, num_gates - counter)
            for i in range(count):
                counter += 1
                ratio = (i + 1) / max(count, 1)
                if ratio <= 0.20:
                    gtype = 'large'
                elif ratio <= 0.70:
                    gtype = 'medium'
                else:
                    gtype = 'small'
                gid = stable_hash(f"{airport_name}_{rw}_{i}", 10000)
                gates.append(Gate(
                    gate_id=gid,
                    name=f"{airport_name[:2]}G{counter:02d}",
                    airport=airport_name,
                    gate_type=gtype,
                    position=counter,
                    runway_group=rw,
                    taxi_in_min=self.TAXI_IN_DEFAULT,
                    taxi_out_min=self.TAXI_OUT_DEFAULT,
                ))
        return gates

    def _log_gate_summary(self, airport_name, gates, runway_groups):
        """打印登机口生成摘要"""
        from collections import Counter
        rw_map = {}
        for g in gates:
            rw_map.setdefault(g.runway_group, []).append(g)
        types = Counter(g.gate_type for g in gates)
        print(f'[GateGen] {airport_name}: {len(gates)} gates, {types}, '
              + ', '.join(f'RWY{r}={len(rw_map.get(r, []))}' for r in sorted(rw_map)))

    # ==================== 时间窗口计算（含滑行偏移） ====================

    def _get_time_window(self, flight, target_airport):
        """获取航班在目标机场的登机口占用时间窗（含滑行偏移）

        降落航班: gate_start = landing_time + taxi_in
                   gate_end   = gate_start + 下客/过站时间
        起飞航班: gate_start = takeoff_time - taxi_out - 上客时间
                   gate_end   = takeoff_time - taxi_out

        过站航班: gate_start = landing_time + taxi_in
                   gate_end   = takeoff_time - taxi_out
        """
        is_dep = flight.departure_airport == target_airport
        is_arr = flight.arrival_airport == target_airport

        if is_dep and is_arr:
            # 过站 (turnaround): 同一机场到达+出发
            start = flight.arrival_minutes + self.TAXI_IN_DEFAULT
            end = flight.departure_minutes - self.TAXI_OUT_DEFAULT
        elif is_dep:
            # 仅出发 (departure)
            start = flight.departure_minutes - self.TAXI_OUT_DEFAULT - 35
            end = flight.departure_minutes - self.TAXI_OUT_DEFAULT
        else:
            # 仅到达 (arrival)
            start = flight.arrival_minutes + self.TAXI_IN_DEFAULT
            end = flight.arrival_minutes + self.TAXI_IN_DEFAULT + 40

        if start < 0:
            start = 0
        return start, end

    # ==================== 兼容性 & 空闲检查 ====================

    def _get_ac_size(self, flight):
        """获取航班机型等级"""
        ac_model = flight.ac_type
        if ac_model in ('A321', 'A330', 'A350', 'B787', 'B777'):
            return 'large'
        elif ac_model in ('A320', 'A319', 'B737', 'B738'):
            return 'medium'
        return 'small'

    def _is_gate_compatible(self, gate, ac_size):
        """检查机位是否兼容机型"""
        if ac_size == 'large' and gate.gate_type != 'large':
            return False
        if ac_size == 'medium' and gate.gate_type == 'small':
            return False
        return True

    def _is_gate_free(self, gate, start, end, min_buffer=None):
        """检查登机口在时间段内是否空闲

        min_buffer: 前后最小间隔（分钟），默认使用 MIN_BUFFER
        """
        if min_buffer is None:
            min_buffer = self.MIN_BUFFER
        buffered_start = start - min_buffer
        buffered_end = end + min_buffer
        for a in gate.assigned_flights:
            a_start = a['start_min']
            a_end = a['end_min']
            if not (buffered_end <= a_start or a_end <= buffered_start):
                return False
        return True

    # ==================== 评分函数 v2（含滑行成本 + 跑道归属） ====================

    def _score_gate(self, gate, ac_size, assigned_runway=None):
        """给机位打分（越低越好）

        评分维度：
        - 机型匹配：完美 0，降级使用 5，越级 12
        - 负载均衡：已有航班越多分越高，引导空闲机位
        - 滑行成本：滑入+滑出总时间 × 权重3
        - 跑道归属：非本跑道组的登机口 +30 惩罚
        """
        score = 0

        # 1. 机型匹配度
        if gate.gate_type == 'large' and ac_size == 'large':
            score += 0
        elif gate.gate_type == 'medium' and ac_size == 'medium':
            score += 1
        elif gate.gate_type == 'small' and ac_size == 'small':
            score += 2
        elif gate.gate_type == 'large' and ac_size == 'medium':
            score += 5
        elif gate.gate_type == 'medium' and ac_size == 'small':
            score += 8
        elif gate.gate_type == 'large' and ac_size == 'small':
            score += 12

        # 2. 负载均衡
        score += len(gate.assigned_flights) * 2

        # 3. 滑行成本
        total_taxi = gate.taxi_in_min + gate.taxi_out_min
        score += total_taxi * 3

        # 4. 跑道归属偏好（软约束）
        if assigned_runway and gate.runway_group != assigned_runway:
            # 非本跑道侧的登机口大幅惩罚，但非绝对禁止
            score += 30

        return score

    # ==================== 贪心算法 ====================

    def solve_greedy(self, gates, flights, target_airport, runway_map=None):
        """贪心分配：逐个航班，选第一个可用且兼容的机位"""
        for f in flights:
            start, end = self._get_time_window(f, target_airport)
            ac_size = self._get_ac_size(f)
            assigned_rwy = runway_map.get(f.flight_id) if runway_map else None

            # 优选跑道归属匹配的登机口
            assigned = False
            candidates = []
            for g in gates:
                if not self._is_gate_compatible(g, ac_size):
                    continue
                if not self._is_gate_free(g, start, end):
                    continue
                candidates.append((self._score_gate(g, ac_size, assigned_rwy), g))

            if candidates:
                candidates.sort(key=lambda x: x[0])
                best = candidates[0][1]
                best.add_assignment(f, start, end,
                                    runway=assigned_rwy,
                                    taxi_in=best.taxi_in_min,
                                    taxi_out=best.taxi_out_min)
                assigned = True

            if not assigned:
                for g in gates:
                    if self._is_gate_free(g, start, end):
                        g.add_assignment(f, start, end,
                                         runway=assigned_rwy,
                                         taxi_in=g.taxi_in_min,
                                         taxi_out=g.taxi_out_min)
                        break
        return gates

    # ==================== 二分图匹配 ====================

    def solve_bipartite(self, gates, flights, target_airport, runway_map=None):
        """二分图匹配分配：综合考虑机型匹配、利用率均衡、滑行成本、跑道归属"""
        for f in flights:
            start, end = self._get_time_window(f, target_airport)
            ac_size = self._get_ac_size(f)
            assigned_rwy = runway_map.get(f.flight_id) if runway_map else None

            candidates = []
            for g in gates:
                if not self._is_gate_compatible(g, ac_size):
                    continue
                if not self._is_gate_free(g, start, end):
                    continue
                score = self._score_gate(g, ac_size, assigned_rwy)
                candidates.append((score, g))

            if candidates:
                candidates.sort(key=lambda x: x[0])
                best_gate = candidates[0][1]
                best_gate.add_assignment(f, start, end,
                                         runway=assigned_rwy,
                                         taxi_in=best_gate.taxi_in_min,
                                         taxi_out=best_gate.taxi_out_min)
            else:
                for g in gates:
                    if self._is_gate_free(g, start, end):
                        g.add_assignment(f, start, end,
                                         runway=assigned_rwy,
                                         taxi_in=g.taxi_in_min,
                                         taxi_out=g.taxi_out_min)
                        break
        return gates

    # ==================== CP-SAT 约束规划（局部搜索优化） ====================

    def solve_cp_sat(self, gates, flights, target_airport, runway_map=None):
        """局部搜索优化：二分图初始化 → 搬迁/交换航班降低最大负载"""
        import copy
        import time

        n_flights = len(flights)
        if n_flights == 0:
            return gates

        start_time = time.time()
        time_limit = 25.0

        # 阶段1：二分图初始化获可行解
        init_gates = copy.deepcopy(gates)
        for g in init_gates:
            g.assigned_flights = []
        init_gates = self.solve_bipartite(init_gates, flights, target_airport, runway_map)

        # 构建飞行→机位映射
        flight_gate = {}
        for j, g in enumerate(init_gates):
            for a in g.assigned_flights:
                flight_gate[a['flight'].flight_id] = j

        # 预计算所有航班信息
        flight_info = []
        for f in flights:
            start, end = self._get_time_window(f, target_airport)
            ac_size = self._get_ac_size(f)
            flight_info.append((f, start, end, ac_size, flight_gate.get(f.flight_id)))

        def gate_loads(gate_list):
            loads = []
            for g in gate_list:
                ld = sum(a['end_min'] - a['start_min'] for a in g.assigned_flights)
                loads.append(ld)
            return loads

        def check_gate_safe(gate_idx, fl_idx, gate_list):
            g = gate_list[gate_idx]
            fi, s, e, _, _ = flight_info[fl_idx]
            for a in g.assigned_flights:
                af = a['flight']
                as1, ae1 = self._get_time_window(af, target_airport)
                if not (e + self.MIN_BUFFER <= as1 or ae1 + self.MIN_BUFFER <= s):
                    return False
            _, _, _, ac_sz, _ = flight_info[fl_idx]
            if not self._is_gate_compatible(g, ac_sz):
                return False
            return True

        def swap_safe(g1_idx, g2_idx, fl1_idx, fl2_idx, gate_list):
            g1 = gate_list[g1_idx]
            g2 = gate_list[g2_idx]
            _, s1, e1, ac1, _ = flight_info[fl1_idx]
            _, s2, e2, ac2, _ = flight_info[fl2_idx]

            if not self._is_gate_compatible(g2, ac1):
                return False
            if not self._is_gate_compatible(g1, ac2):
                return False

            for a in g2.assigned_flights:
                af = a['flight']
                if af.flight_id == flight_info[fl2_idx][0].flight_id:
                    continue
                as_i, ae_i = self._get_time_window(af, target_airport)
                if not (e1 + self.MIN_BUFFER <= as_i or ae_i + self.MIN_BUFFER <= s1):
                    return False
            for a in g1.assigned_flights:
                af = a['flight']
                if af.flight_id == flight_info[fl1_idx][0].flight_id:
                    continue
                as_i, ae_i = self._get_time_window(af, target_airport)
                if not (e2 + self.MIN_BUFFER <= as_i or ae_i + self.MIN_BUFFER <= s2):
                    return False
            return True

        # 阶段2：迭代改进
        best_gates = copy.deepcopy(init_gates)
        loads = gate_loads(best_gates)
        improved = True
        rounds = 0
        max_rounds = 500

        while improved and rounds < max_rounds and time.time() - start_time < time_limit:
            improved = False
            rounds += 1
            loads = gate_loads(best_gates)
            current_max = max(loads) if loads else 0

            max_gate_idx = loads.index(current_max)
            g_max = best_gates[max_gate_idx]

            # 尝试搬迁
            for a in list(g_max.assigned_flights):
                if time.time() - start_time > time_limit:
                    break
                fl = a['flight']
                fl_idx = next((i for i, fi in enumerate(flight_info) if fi[0].flight_id == fl.flight_id), None)
                if fl_idx is None:
                    continue

                for target_idx in range(len(best_gates)):
                    if target_idx == max_gate_idx:
                        continue
                    if not check_gate_safe(target_idx, fl_idx, best_gates):
                        continue

                    s, e = self._get_time_window(fl, target_airport)
                    g_max.assigned_flights = [x for x in g_max.assigned_flights if x['flight'].flight_id != fl.flight_id]
                    best_gates[target_idx].add_assignment(fl, s, e,
                                                          taxi_in=best_gates[target_idx].taxi_in_min,
                                                          taxi_out=best_gates[target_idx].taxi_out_min)

                    new_loads = gate_loads(best_gates)
                    new_max = max(new_loads) if new_loads else 0
                    if new_max < current_max:
                        current_max = new_max
                        improved = True
                        break
                    else:
                        best_gates[target_idx].assigned_flights = [x for x in best_gates[target_idx].assigned_flights if x['flight'].flight_id != fl.flight_id]
                        g_max.add_assignment(fl, s, e)

                if improved:
                    break

            # 尝试交换
            if not improved and rounds % 3 == 0:
                for g1_idx in range(len(best_gates)):
                    if time.time() - start_time > time_limit:
                        break
                    for g2_idx in range(g1_idx + 1, len(best_gates)):
                        g1 = best_gates[g1_idx]
                        g2 = best_gates[g2_idx]
                        ld1 = gate_loads([g1])[0]
                        ld2 = gate_loads([g2])[0]
                        if abs(ld1 - ld2) < 10:
                            continue

                        for a1 in g1.assigned_flights:
                            fl1 = a1['flight']
                            fl1_idx = next((i for i, fi in enumerate(flight_info) if fi[0].flight_id == fl1.flight_id), None)
                            if fl1_idx is None:
                                continue
                            for a2 in g2.assigned_flights:
                                fl2 = a2['flight']
                                fl2_idx = next((i for i, fi in enumerate(flight_info) if fi[0].flight_id == fl2.flight_id), None)
                                if fl2_idx is None:
                                    continue
                                if swap_safe(g1_idx, g2_idx, fl1_idx, fl2_idx, best_gates):
                                    s1, e1 = self._get_time_window(fl1, target_airport)
                                    s2, e2 = self._get_time_window(fl2, target_airport)
                                    g1.assigned_flights = [x for x in g1.assigned_flights if x['flight'].flight_id != fl1.flight_id]
                                    g2.assigned_flights = [x for x in g2.assigned_flights if x['flight'].flight_id != fl2.flight_id]
                                    g1.add_assignment(fl2, s2, e2)
                                    g2.add_assignment(fl1, s1, e1)
                                    new_loads = gate_loads(best_gates)
                                    new_max = max(new_loads) if new_loads else 0
                                    if new_max < current_max:
                                        current_max = new_max
                                        improved = True
                                        break
                                    g1.assigned_flights = [x for x in g1.assigned_flights if x['flight'].flight_id != fl2.flight_id]
                                    g2.assigned_flights = [x for x in g2.assigned_flights if x['flight'].flight_id != fl1.flight_id]
                                    g1.add_assignment(fl1, s1, e1)
                                    g2.add_assignment(fl2, s2, e2)
                            if improved:
                                break
                        if improved:
                            break
                    if improved:
                        break

        # 回填
        flight_assignments = []
        for g_idx, g in enumerate(best_gates):
            for a in g.assigned_flights:
                flight_assignments.append((a['flight'], a['start_min'], a['end_min'],
                                           a.get('ops_type'), a.get('runway'),
                                           a.get('taxi_in', 0), a.get('taxi_out', 0),
                                           g_idx))

        for g in gates:
            g.assigned_flights = []
        for f, s, e, op, rwy, txi, txo, g_idx in flight_assignments:
            gates[g_idx].add_assignment(f, s, e, ops_type=op, runway=rwy,
                                        taxi_in=txi, taxi_out=txo)

        final_loads = gate_loads(gates)
        used = sum(1 for ld in final_loads if ld > 0)
        print(f'[CP-SAT] rounds={rounds}, max_load={max(final_loads) if final_loads else 0}min, '
              f'used={used}/{len(gates)}, time={time.time()-start_time:.2f}s')

        return gates

    # ==================== 日期工具 ====================

    def _filter_by_date(self, flights, date_str, airport=None):
        if not date_str:
            return flights
        return [f for f in flights if self._flight_date(f, airport) == date_str]

    def _flight_date(self, f, airport=None):
        """获取航班在指定机场的操作日期。
        到达航班用到达日期，出发航班用出发日期。
        不传 airport 时回退到出发日期（兼容旧调用）。
        """
        if airport and f.arrival_airport == airport:
            y, m, d, *_ = f.time_arrival
        else:
            y, m, d, *_ = f.time_departure
        return f"{y}-{m:02d}-{d:02d}"

    def _get_dates_for_airport(self, target_airport):
        data_service.load_all()
        dates = set()
        for f in data_service.flights:
            if f.departure_airport == target_airport or f.arrival_airport == target_airport:
                dates.add(self._flight_date(f, target_airport))
        return sorted(dates)

    # ==================== 主入口 ====================

    def assign_flights_to_gates(self, target_airport='成都', algorithm='bipartite',
                                date=None, flights=None, runway_schedule=None):
        """将航班分配到登机口

        Args:
            target_airport: 目标机场名称
            algorithm: 'greedy' | 'bipartite' | 'cp_sat'
            date: 日期筛选 (YYYY-MM-DD)
            flights: 外部航班列表（为 None 时从 data_service 加载）
            runway_schedule: 跑道调度结果列表，用于提取 flight_id → runway 映射

        Returns:
            gates 列表
        """
        if flights is None:
            data_service.load_all()
            flights = [f for f in data_service.flights
                       if f.departure_airport == target_airport
                       or f.arrival_airport == target_airport]
        else:
            flights = [f for f in flights
                       if f.departure_airport == target_airport
                       or f.arrival_airport == target_airport]

        self._gates_by_airport = {}
        gates = self.generate_gates(target_airport)

        flights = self._filter_by_date(flights, date, target_airport)
        flights = sorted(flights, key=lambda f: f.departure_minutes)

        for g in gates:
            g.assigned_flights = []

        # 构建跑道映射: flight_id → runway_number
        runway_map = {}
        if runway_schedule:
            for item in runway_schedule:
                fid = item.get('flight_id')
                if fid:
                    runway_map[fid] = item.get('runway', 1)

        if algorithm == 'greedy':
            gates = self.solve_greedy(gates, flights, target_airport, runway_map)
        elif algorithm == 'cp_sat':
            gates = self.solve_cp_sat(gates, flights, target_airport, runway_map)
        else:
            gates = self.solve_bipartite(gates, flights, target_airport, runway_map)

        return gates

    def compare_algorithms(self, target_airport='成都', date=None, flights=None, runway_schedule=None):
        """对比贪心、二分图匹配、CP-SAT三种算法"""
        if flights is None:
            data_service.load_all()
            flights = [f for f in data_service.flights
                       if f.departure_airport == target_airport
                       or f.arrival_airport == target_airport]
        else:
            flights = [f for f in flights
                       if f.departure_airport == target_airport
                       or f.arrival_airport == target_airport]
        flights = self._filter_by_date(flights, date, target_airport)
        flights = sorted(flights, key=lambda f: f.departure_minutes)

        # 构建跑道映射
        runway_map = {}
        if runway_schedule:
            for item in runway_schedule:
                fid = item.get('flight_id')
                if fid:
                    runway_map[fid] = item.get('runway', 1)

        def run_one(name, solver_fn):
            gs = self.generate_gates(target_airport)
            for g in gs:
                g.assigned_flights = []
            self._gates_by_airport = {}
            gs = solver_fn(gs, flights, target_airport, runway_map)
            return {
                'gates': [g.to_dict() for g in gs],
                'conflicts': self.detect_conflicts(gs),
                'stats': self.get_utilization_stats(gs),
            }

        result = {
            'airport': target_airport,
            'date': date,
            'flight_count': len(flights),
            'greedy': run_one('greedy', self.solve_greedy),
            'bipartite': run_one('bipartite', self.solve_bipartite),
            'cp_sat': run_one('cp_sat', self.solve_cp_sat),
        }
        for key in ('greedy', 'bipartite', 'cp_sat'):
            result[key]['conflict_count'] = len(result[key]['conflicts'])
        return result

    # ==================== 冲突检测 & 统计 ====================

    def detect_conflicts(self, gates):
        """检测登机口冲突"""
        conflicts = []
        for g in gates:
            assigned = sorted(g.assigned_flights, key=lambda a: a['start_min'])
            for i in range(len(assigned) - 1):
                a1 = assigned[i]
                a2 = assigned[i + 1]
                if a2['start_min'] < a1['end_min']:
                    conflicts.append({
                        'gate': g.name,
                        'flight_a': a1['flight'].flight_no if hasattr(a1['flight'], 'flight_no') else '?',
                        'flight_b': a2['flight'].flight_no if hasattr(a2['flight'], 'flight_no') else '?',
                        'overlap_min': a1['end_min'] - a2['start_min'],
                    })
        return conflicts

    def get_utilization_stats(self, gates):
        """计算利用率统计"""
        if not gates:
            return {'total_gates': 0, 'used_gates': 0, 'avg_utilization': 0,
                    'max_utilization': 0, 'min_utilization': 0}

        utils = [g.utilization for g in gates]
        used = sum(1 for u in utils if u > 0)
        return {
            'total_gates': len(gates),
            'used_gates': used,
            'avg_utilization': round(sum(utils) / len(utils), 1),
            'max_utilization': round(max(utils), 1),
            'min_utilization': round(min(utils), 1),
        }
