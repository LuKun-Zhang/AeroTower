"""Pairing 指派算法（不相交闭环覆盖版）

将 DFS 生成的闭环候选任务链指派给机组人员。

核心原则（模拟现实航司）：
1. 阶段1: 三种不相交贪心策略取最优覆盖
   A) 成本升序（短链优先）
   B) 效率降序（高价值链优先）
   C) 随机采样 best-of-200（探索更多组合）
2. 阶段2: 日级往返链补充
3. 阶段3: 未覆盖航班 → 报告
"""

import random


def assign_pairings(pairings, flights, crew_pool, rng=None):
    """选不相交的闭环 pairing 子集分配给机组。

    :param rng: 可选的 random.Random 实例；实验传入带种子的实例以保证复现。
                为 None 时退回模块级 random（保持旧行为）。
    :param pairings: 所有候选 Pairing 列表
    :param flights: 所有航班
    :param crew_pool: 机组列表
    :return: (crew_pool, assigned_info, uncovered_flights)
    """
    if not pairings or not flights:
        return crew_pool, [], pairings

    rng = rng or random

    for c in crew_pool:
        c.assigned_flights = []

    flight_map = {f.flight_id: f for f in flights}
    all_fids = set(f.flight_id for f in flights)

    # === 阶段1: 三种不相交策略取最优 ===
    candidates = [
        _select_disjoint(pairings, key=lambda p: p.cost),
        _select_disjoint(pairings, key=lambda p: -p.efficiency),
        _best_random_disjoint(pairings, rng=rng, trials=200),
    ]

    best = candidates[0]
    best_cov = _coverage_of(best)
    for cand in candidates[1:]:
        c = _coverage_of(cand)
        if c > best_cov:
            best_cov = c
            best = cand

    selected = best
    covered_ids = set()
    for p in selected:
        covered_ids.update(p.flight_ids())

    # === 阶段2: 日级往返链 ===
    uncovered_by_id = sorted(all_fids - covered_ids)
    new_chains, new_covered = _build_daily_turnarounds(uncovered_by_id, flight_map)
    if new_chains:
        selected = list(selected) + new_chains
        covered_ids |= new_covered

    # === 阶段3: 指派机组（链式接续） ===
    # 原则：机组飞到X机场后，优先继续接从X出发的pairing（同一机组链式接续）
    captains = [c for c in crew_pool if c.role == 'captain']
    officers = [c for c in crew_pool if c.role == 'first_officer']
    pursers = [c for c in crew_pool if c.role == 'purser']
    attendants = [c for c in crew_pool if c.role == 'attendant']

    assigned_info = []

    # 按出发时间排序pairing
    sorted_pairings = sorted(selected, key=lambda p: p.flights[0].departure_minutes if p.flights else 0)

    # 活跃团队：每个团队是一组5人，记录其最后到达机场和时间、当日执勤起始
    # 跨日逻辑：若下一pairing的间隔≥6h(360min)，算作新执勤日，重置14h钟
    active_teams = []  # [{members, last_airport, last_arrival_min, day_duty_start_day1, day_duty_start_dayN}]

    def _find_continuation_team(pairing):
        """找最近到达此pairing出发机场的活跃团队（跨日接续支持）"""
        p_start = pairing.flights[0].departure_minutes
        p_end = max(f.arrival_minutes for f in pairing.flights)
        p_duration = p_end - p_start
        dep_ap = pairing.flights[0].departure_airport

        if p_duration > 14 * 60:
            return None  # 单pairing超14h，不可分配

        best_team = None
        best_score = float('inf')
        for team in active_teams:
            if team['last_airport'] != dep_ap:
                continue
            # 时间衔接：必须有至少30min间隙
            if p_start < team['last_arrival_min'] + 30:
                continue
            gap = p_start - team['last_arrival_min']

            # 跨日衔接（gap≥6h）：全新执勤日，仅检查pairing自身≤14h
            if gap >= 6 * 60:
                # 过夜 ✅ → 新一天执勤，14h钟重置
                pass
            else:
                # 同日接续 → 检查累计执勤≤14h
                new_duty_end = max(p_end, team['last_arrival_min'])
                if new_duty_end - team['day_duty_start'] > 14 * 60:
                    continue

            # 资质检查
            for m in team['members']:
                for f in pairing.flights:
                    if f.ac_type not in m.qualifications:
                        break
                else:
                    continue
                break
            else:
                gap = p_start - team['last_arrival_min']
                if gap < best_score:
                    best_score = gap
                    best_team = team
        return best_team

    def _create_fresh_team(pairing):
        """创建全新5人团队"""
        dep_ap = pairing.flights[0].departure_airport
        cap = _pick_fresh(captains)
        off = _pick_fresh(officers)
        pur = _pick_fresh(pursers)
        if not cap or not off or not pur:
            return None
        if dep_ap not in {cap.base, off.base, pur.base}:
            return None
        att_list = []
        for att in attendants:
            if not att.assigned_flights:
                att_list.append(att)
                if len(att_list) >= 2:
                    break
        if len(att_list) < 2:
            return None
        members = [cap, off, pur, att_list[0], att_list[1]]
        return {'members': members, 'last_airport': None, 'last_arrival_min': 0, 'day_duty_start': 0}

    def _assign_pairing_to_team(pairing, team):
        """将pairing的航班加给团队成员，更新团队状态（支持跨日执勤）"""
        for f in pairing.flights:
            dep, arr = f.departure_minutes, f.arrival_minutes
            for m in team['members']:
                m.add_flight(f, dep, arr)
        # 更新团队状态
        last_f = pairing.flights[-1]
        p_start = pairing.flights[0].departure_minutes
        p_end = max(f.arrival_minutes for f in pairing.flights)

        # 跨日执勤处理：若与上一航班的间隔≥6h，算新执勤日
        if team['last_arrival_min'] > 0 and (p_start - team['last_arrival_min']) >= 6 * 60:
            team['day_duty_start'] = p_start  # 新一天执勤开始
        if team['day_duty_start'] == 0:
            team['day_duty_start'] = p_start

        team['last_airport'] = last_f.arrival_airport
        team['last_arrival_min'] = p_end

    for pairing in sorted_pairings:
        if not pairing.flights:
            continue

        # 策略1: 尝试找可接续的活跃团队
        cont_team = _find_continuation_team(pairing)
        if cont_team:
            _assign_pairing_to_team(pairing, cont_team)
            assigned_info.append({
                'pairing_id': getattr(pairing, 'pairing_id', 0),
                'captain': cont_team['members'][0].name,
                'first_officer': cont_team['members'][1].name,
                'purser': cont_team['members'][2].name,
                'attendants': [cont_team['members'][3].name, cont_team['members'][4].name],
            })
            continue

        # 策略2: 从基地出发 → 创建全新团队
        new_team = _create_fresh_team(pairing)
        if new_team:
            _assign_pairing_to_team(pairing, new_team)
            active_teams.append(new_team)
            assigned_info.append({
                'pairing_id': getattr(pairing, 'pairing_id', 0),
                'captain': new_team['members'][0].name,
                'first_officer': new_team['members'][1].name,
                'purser': new_team['members'][2].name,
                'attendants': [new_team['members'][3].name, new_team['members'][4].name],
            })
            continue

        # 策略2失败（无可用人员） → 跳过此pairing

    uncovered = [flight_map[fid] for fid in sorted(all_fids - covered_ids)]
    uncovered.sort(key=lambda f: f.departure_minutes)

    return crew_pool, assigned_info, uncovered


def _coverage_of(pairings):
    s = set()
    for p in pairings:
        s.update(p.flight_ids())
    return len(s)


def _select_disjoint(pairings, key):
    """不相交贪心选择。"""
    sorted_pairs = sorted(pairings, key=key)
    covered = set()
    selected = []
    for p in sorted_pairs:
        p_fids = set(p.flight_ids())
        if p_fids & covered:
            continue
        selected.append(p)
        covered.update(p_fids)
    return selected


def _best_random_disjoint(pairings, rng=None, trials=200):
    """随机排列多次贪心，取覆盖最好的结果。"""
    rng = rng or random
    items = list(pairings)
    best_covered = 0
    best_selection = []
    for _ in range(trials):
        rng.shuffle(items)
        covered = set()
        selected = []
        for p in items:
            p_fids = set(p.flight_ids())
            if p_fids & covered:
                continue
            selected.append(p)
            covered.update(p_fids)
        if len(covered) > best_covered:
            best_covered = len(covered)
            best_selection = list(selected)
    return best_selection


def _build_daily_turnarounds(uncovered_fids, flight_map):
    """从未覆盖航班中构建日级往返链。"""
    from ..models.pairing import Pairing
    from collections import defaultdict
    dep_group = defaultdict(list)

    for fid in uncovered_fids:
        f = flight_map.get(fid)
        if not f:
            continue
        dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
        dep_group[(dk, f.departure_airport)].append(f)

    covered = set()
    chains = []
    pid = 10000

    for (dk, dep_ap), out_flights in dep_group.items():
        for out_f in out_flights:
            if out_f.flight_id in covered:
                continue
            arr_ap = out_f.arrival_airport
            ret_flights = dep_group.get((dk, arr_ap), [])
            for ret_f in ret_flights:
                if ret_f.flight_id in covered:
                    continue
                if ret_f.arrival_airport != dep_ap:
                    continue
                if ret_f.departure_minutes >= out_f.arrival_minutes + 30:
                    chain_flights = sorted([out_f, ret_f], key=lambda x: x.departure_minutes)
                    pairing = Pairing(pid, chain_flights, dep_ap)
                    pid += 1
                    chains.append(pairing)
                    covered.add(out_f.flight_id)
                    covered.add(ret_f.flight_id)
                    break

    return chains, covered


def _pick_fresh(crew_list):
    for c in crew_list:
        if not c.assigned_flights:
            return c
    return None
