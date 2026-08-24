"""排班相关 API Blueprint — /api/schedule/* 路由"""

import io
import os
import copy
import json
import traceback
from collections import defaultdict

from flask import Blueprint, jsonify, request, send_file

from ..state import (
    get_active_flights, set_active_flights,
    get_active_chains, set_active_chains,
    get_filtered_mode, set_filtered_mode,
    get_excluded_aircraft, set_excluded_aircraft,
    get_flight_aircraft_cache, set_flight_aircraft_cache,
    get_aircraft_chains_cache, set_aircraft_chains_cache,
    get_active_crew_substitutions, set_active_crew_substitutions,
    get_cached_crew_schedule, set_cached_crew_schedule,
    get_pre_substitution_crew_pool, set_pre_substitution_crew_pool,
    get_analysis_pending, set_analysis_pending,
    get_transit_cache, set_transit_cache,
    get_uploaded_flights, set_uploaded_flights,
    get_current_history_id, set_current_history_id,
)

from ..services.data_service import data_service
from ..services import routing_service, runway_service, gate_service, crew_service
from ..services.map_schedule_store import (
    save_schedule, get_schedule, get_all_dates,
    build_map_timeslices, build_multi_day_timeslices, ICAO_TO_CITY,
)
from ..services.flight_filter import filter_flights, SICHUAN_BASES
from ..utils.city_geo import build_transit_cache_from_flights

schedule_bp = Blueprint('schedule', __name__)

# 川航机队规模（生成器按此规模生成任务链，飞机排班默认按此数量执行）
DEFAULT_AIRCRAFT_COUNT = 100

_HISTORY_BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'history',
)


# ==================== 辅助函数 ====================

def safe_handler(fn):
    """装饰器：捕获所有异常，永远返回 JSON"""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            return jsonify({
                'code': 500,
                'msg': str(e),
            }), 500
    wrapper.__name__ = fn.__name__
    return wrapper


def _flight_date_key(f):
    y, m, d, *_ = f.time_departure
    return f"{y}-{m:02d}-{d:02d}"


def _filter_crew_with_flights(crew_pool):
    """只返回有航班的机组（严格5人一组，无散兵）"""
    return [c for c in crew_pool if c.assigned_flights]


def _normalize_flight_times(flights):
    """将航班列表中所有 6 元组时间规范化为 5 元组"""
    for f in flights:
        for attr in ('time_departure', 'time_arrival'):
            t = getattr(f, attr, None)
            if isinstance(t, (tuple, list)) and len(t) > 5:
                setattr(f, attr, tuple(t[:5]))


def _get_active_flights():
    """获取当前活跃航班，优先使用筛选后的数据"""
    filtered_mode = get_filtered_mode()
    active_flights = get_active_flights()
    if filtered_mode and active_flights:
        _normalize_flight_times(active_flights)
        return list(active_flights)
    data_service.load_all()
    return list(data_service.flights)


def _get_active_chains():
    """获取当前活跃任务链（Flight对象列表）"""
    filtered_mode = get_filtered_mode()
    active_chains = get_active_chains()
    if filtered_mode and active_chains:
        for chain in active_chains:
            _normalize_flight_times(chain)
        return active_chains
    return None


def _rebuild_transit_cache():
    """根据当前活跃航班重建航线途经省份缓存"""
    flights = _get_active_flights()
    if not flights:
        set_transit_cache({})
        return
    set_transit_cache(build_transit_cache_from_flights(list(flights)))
    print(f"[TransitCache] 已为 {len(get_transit_cache())} 条航线构建途经缓存")


def _get_flight_aircraft_map():
    """运行飞机排班获取 flight_id -> tail_no 映射（带缓存）
    筛选模式下使用链集合覆盖，否则用二分图。
    """
    cache = get_flight_aircraft_cache()
    if cache is not None:
        return cache

    chains = _get_active_chains()
    if chains:
        result = routing_service.solve_chain_coverage(chains)
        set_aircraft_chains_cache(
            [list(ac.assigned_flights) for ac in result if ac.assigned_flights]
        )
    else:
        data_service.load_all()
        result = routing_service.solve_bipartite(_get_active_flights(), 60)

    mapping = {}
    for ac in result:
        for f in ac.assigned_flights:
            mapping[f.flight_id] = ac.tail_no
    set_flight_aircraft_cache(mapping)
    return mapping


def _get_aircraft_routing():
    """获取缓存的飞机排班结果（Flight对象列表的列表）
    筛选模式下从链集合覆盖产出，否则实时计算二分图。
    """
    cache = get_aircraft_chains_cache()
    if cache is not None:
        for chain in cache:
            _normalize_flight_times(chain)
        return cache

    chains = _get_active_chains()
    if chains:
        excluded = list(get_excluded_aircraft()) if get_excluded_aircraft() else []
        num_ac = max(DEFAULT_AIRCRAFT_COUNT - len(excluded), 5)
        result = routing_service.solve_chain_coverage(
            chains, num_ac, excluded_aircraft=excluded if excluded else None)
        set_aircraft_chains_cache(
            [list(ac.assigned_flights) for ac in result if ac.assigned_flights]
        )
        return get_aircraft_chains_cache()

    result = routing_service.solve_bipartite(_get_active_flights(), 60)
    set_aircraft_chains_cache(
        [list(ac.assigned_flights) for ac in result if ac.assigned_flights]
    )
    return get_aircraft_chains_cache()


def _build_schedule_state():
    """构建当前排班状态快照，供异常调度服务使用"""
    flights = _get_active_flights()
    flight_aircraft = _get_flight_aircraft_map() or {}

    aircraft_assignments = dict(flight_aircraft)

    chains = _get_active_chains()
    ac_cache = get_aircraft_chains_cache()
    if not chains and ac_cache:
        chains = ac_cache
    if not chains:
        chains = []

    crew_assignments = {}
    crew_pool_raw = []
    try:
        # ======== 诊断：打印 crew_pool 状态 ========
        pool_exists = bool(crew_service._crew_pool)
        pool_size = len(crew_service._crew_pool) if crew_service._crew_pool else 0
        pool_has_assignments = False
        if crew_service._crew_pool:
            pool_has_assignments = any(
                getattr(c, 'assigned_flights', None)
                for c in crew_service._crew_pool
            )
        print(
            f"[ScheduleState/DIAG] crew_pool exists={pool_exists}, size={pool_size}, "
            f"has_assignments={pool_has_assignments}, flights={len(flights)}, "
            f"chains={len(chains)}", flush=True,
        )

        if crew_service._crew_pool and pool_has_assignments:
            crew_pool_raw = list(crew_service._crew_pool)
            for c in crew_pool_raw:
                for f_obj in (c.assigned_flights or []):
                    flight_obj = f_obj.get('flight') if isinstance(f_obj, dict) else f_obj
                    fid = (
                        getattr(flight_obj, 'flight_id', str(f_obj))
                        if flight_obj else str(f_obj)
                    )
                    if fid not in crew_assignments:
                        crew_assignments[fid] = []
                    crew_assignments[fid].append(c.crew_id)
            print(
                f"[ScheduleState/DIAG] 使用现有机组池: {len(crew_pool_raw)}人, "
                f"{len(crew_assignments)}个航班分配", flush=True,
            )
        else:
            if flights:
                reason = (
                    "pool为空" if not crew_service._crew_pool else "pool无分配"
                )
                print(f"[ScheduleState] {reason}，触发机组排班...", flush=True)
                filtered_active = [
                    f for f in flights
                    if hasattr(f, 'departure_airport') and getattr(f, 'departure_airport', '')
                ]
                if filtered_active:
                    crew_service.schedule_crew(flights=filtered_active)
                    crew_pool_raw = list(crew_service._crew_pool) if crew_service._crew_pool else []
                    for c in crew_pool_raw:
                        for f_obj in (c.assigned_flights or []):
                            flight_obj = f_obj.get('flight') if isinstance(f_obj, dict) else f_obj
                            fid = (
                                getattr(flight_obj, 'flight_id', str(f_obj))
                                if flight_obj else str(f_obj)
                            )
                            if fid not in crew_assignments:
                                crew_assignments[fid] = []
                            crew_assignments[fid].append(c.crew_id)
                    print(
                        f"[ScheduleState] 机组排班完成: {len(crew_pool_raw)} 人, "
                        f"{len(crew_assignments)} 个航班分配", flush=True,
                    )
            else:
                from backend.models.crew import CrewMember
                from backend.services.crew_service import (
                    _get_roster_names, get_airline_bases,
                )
                for airline, bases in get_airline_bases().items():
                    for base in bases:
                        role_configs = [
                            ('captain', 'captains'),
                            ('first_officer', 'first_officers'),
                            ('purser', 'pursers'),
                            ('attendant', 'attendants'),
                        ]
                        for role, role_key in role_configs:
                            for i, name in enumerate(
                                _get_roster_names(base, role_key)
                            ):
                                cm = CrewMember(
                                    crew_id=f"{role}_{i}",
                                    name=name,
                                    role=role,
                                    base=base,
                                    airline=airline,
                                )
                                crew_pool_raw.append(cm)
    except Exception as e:
        print(f"[ScheduleState] 构建 crew_pool 异常: {e}")
        traceback.print_exc()

    crew_with_flights = sum(
        1 for c in crew_pool_raw if getattr(c, 'assigned_flights', None)
    )
    crew_names_sample = [getattr(c, 'name', '?') for c in crew_pool_raw[:10]]
    print(
        f"[ScheduleState/DIAG] 结果: crew_pool={len(crew_pool_raw)}人, "
        f"有航班者={crew_with_flights}人, crew_assignments条目={len(crew_assignments)}",
        flush=True,
    )
    print(f"[ScheduleState/DIAG] 前10名: {crew_names_sample}", flush=True)
    zhang = next(
        (c for c in crew_pool_raw if getattr(c, 'name', '') == '张建国'), None,
    )
    if zhang:
        af = getattr(zhang, 'assigned_flights', None) or []
        print(
            f"[ScheduleState/DIAG] 张建国: crew_id={getattr(zhang, 'crew_id', '?')}, "
            f"assigned_flights={len(af)}", flush=True,
        )
        for a in af[:5]:
            fo = a.get('flight') if isinstance(a, dict) else a
            fid = getattr(fo, 'flight_id', '?') if fo else '?'
            fno = getattr(fo, 'flight_no', '?') if fo else '?'
            print(f"[ScheduleState/DIAG]   flight: {fid} {fno}", flush=True)
    else:
        print(f"[ScheduleState/DIAG] 张建国 NOT in crew_pool!", flush=True)

    gate_assignments = {}
    runway_assignments = {}

    uploaded = list(get_uploaded_flights()) if get_uploaded_flights() else []

    if get_analysis_pending():
        set_analysis_pending(False)
        print(f"[ScheduleState] 分析保护已解除，CrewView 恢复正常排班")

    return {
        "flights": list(flights),
        "aircraft_assignments": aircraft_assignments,
        "crew_assignments": crew_assignments,
        "crew_pool": crew_pool_raw,
        "gate_assignments": gate_assignments,
        "runway_assignments": runway_assignments,
        "chains": list(chains),
        "uploaded_flights": uploaded,
        "transit_cache": dict(get_transit_cache()),
    }


def _apply_crew_substitutions_to_pool(substitutions):
    """将机组替班变更应用到 crew_service._crew_pool"""
    import re
    crew_pool = getattr(crew_service, '_crew_pool', None) or []
    if not crew_pool or not substitutions:
        return

    crew_by_id = {}
    crew_by_name = {}
    for c in crew_pool:
        crew_by_id[str(c.crew_id)] = c
        crew_by_name[c.name] = c

    for sub in substitutions:
        old_val = sub.get('old_value', '')
        new_val = sub.get('new_value', '')
        flight_id = str(sub.get('flight_id', ''))

        absent_name = old_val.split('(')[0].strip()
        sub_name = new_val.split('(')[0].strip()
        sub_match = re.search(r'\((\d+)\)', new_val)
        substitute_cid = sub_match.group(1) if sub_match else None

        absent = crew_by_name.get(absent_name)
        substitute = (
            crew_by_name.get(sub_name)
            or (crew_by_id.get(substitute_cid) if substitute_cid else None)
        )

        if not absent:
            print(f"[Substitution] 未找到请假人员: {absent_name}")
            continue
        if not substitute:
            print(f"[Substitution] 未找到替班人员: crew_id={substitute_cid}")
            continue

        removed = None
        new_assigned = []
        for af in (absent.assigned_flights or []):
            flight_obj = af.get('flight') if isinstance(af, dict) else af
            fid = str(getattr(flight_obj, 'flight_id', '')) if flight_obj else ''
            if fid == flight_id:
                removed = af
            else:
                new_assigned.append(af)
        if removed:
            absent.assigned_flights = new_assigned
            flight_no = (
                getattr(removed.get('flight', None), 'flight_no', '')
                if isinstance(removed, dict) else ''
            )
            print(f"[Substitution] {absent_name} 移除航班 {flight_no}({flight_id})")

        if removed:
            substitute.assigned_flights.append(removed)
            print(f"[Substitution] {substitute.name} 接管航班 {flight_no}({flight_id})")
        else:
            for f_obj in getattr(crew_service, '_all_flights', []) or []:
                if str(getattr(f_obj, 'flight_id', '')) == flight_id:
                    dep = getattr(f_obj, 'departure_minutes', 0)
                    arr = getattr(f_obj, 'arrival_minutes', 0)
                    substitute.assigned_flights.append({
                        'flight': f_obj,
                        'duty_start_min': dep,
                        'duty_end_min': arr,
                    })
                    print(
                        f"[Substitution] {substitute.name} 接管航班 "
                        f"{getattr(f_obj, 'flight_no', '')}({flight_id}) [新建]"
                    )
                    break


def _serialize_flight(f):
    """将 Flight 对象或 dict 转为可 JSON 序列化的 dict（时间保留为整数列表）"""
    if isinstance(f, dict):
        return f
    td = (
        tuple(f.time_departure)
        if isinstance(f.time_departure, (tuple, list))
        else f.time_departure
    )
    ta = (
        tuple(f.time_arrival)
        if isinstance(f.time_arrival, (tuple, list))
        else f.time_arrival
    )
    return {
        'flight_id': f.flight_id,
        'flight_no': f.flight_no,
        'ac_type': f.ac_type,
        'layout': f.layout,
        'departure_airport': f.departure_airport,
        'arrival_airport': f.arrival_airport,
        'time_departure': list(td),
        'time_arrival': list(ta),
        'timespan': f.timespan,
        'cost': f.cost,
    }


def _get_history_dir_static():
    """不依赖 Flask request 的 history 目录获取（供后台线程使用）"""
    return os.path.join(_HISTORY_BASE, 'user1')


def _persist_recovery_result(history_id):
    """持久化恢复方案执行后的航班和任务链数据到磁盘"""
    import datetime
    hist_dir = os.path.join(_get_history_dir_static(), history_id)
    os.makedirs(hist_dir, exist_ok=True)

    uploaded_flights = get_uploaded_flights()
    active_flights = get_active_flights()
    active_chains = get_active_chains()

    result_data = {
        'uploaded_count': len(uploaded_flights),
        'active_count': len(active_flights),
        'chain_count': len(active_chains),
        'flights': [_serialize_flight(f) for f in active_flights],
        'chains': [
            [_serialize_flight(f) for f in chain]
            for chain in active_chains
        ],
        'recovery_applied': True,
        'recovery_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    with open(os.path.join(hist_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    meta_path = os.path.join(hist_dir, 'meta.json')
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    meta['recovery_applied'] = True
    meta['recovery_time'] = result_data['recovery_time']
    meta['active_count'] = len(active_flights)
    meta['chain_count'] = len(active_chains)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(
        f"[RecoveryCallback] 已持久化到 {hist_dir}: "
        f"{len(active_flights)} flights, {len(active_chains)} chains"
    )


def _on_recovery_executed(executed_schedule, set_progress=None):
    """恢复方案执行后的回调：将修改后的航班回写到活跃数据源，重跑全部排班算法"""

    def progress(pct, msg):
        if set_progress:
            set_progress(pct, msg)
        print(f"[RecoveryCallback] {pct}% {msg}")

    flights = executed_schedule.get('flights', [])
    chains = executed_schedule.get('chains', [])
    excluded_aircraft = executed_schedule.get('excluded_aircraft', [])
    crew_substitutions = executed_schedule.get('crew_substitutions', [])

    _normalize_flight_times(flights)
    for chain in chains:
        _normalize_flight_times(chain)

    is_aircraft_recovery = bool(excluded_aircraft)
    is_crew_recovery = bool(crew_substitutions)

    if is_crew_recovery:
        progress(
            30, f"机组替班恢复: {len(crew_substitutions)} 项变更, 跳过航班/飞机重排",
        )
        set_excluded_aircraft([])
        set_active_flights(list(flights))
        set_uploaded_flights(list(flights))
        set_active_chains(list(chains) if chains else list(get_active_chains()))
        set_filtered_mode(True)

        schedule_crew_pool = executed_schedule.get('crew_pool', [])
        if schedule_crew_pool:
            crew_service._crew_pool = list(schedule_crew_pool)
            print(
                f"[RecoveryCallback] 从 schedule 恢复 crew_pool: "
                f"{len(schedule_crew_pool)} 人"
            )
        elif not crew_service._crew_pool:
            print(f"[RecoveryCallback] crew_pool 为空，触发排班")
            crew_service.schedule_crew(flights=get_active_flights())
        progress(50, f"机组池就绪: {len(crew_service._crew_pool or [])} 人")
    elif is_aircraft_recovery:
        set_excluded_aircraft(list(excluded_aircraft))
        progress(
            30,
            f"飞机异常恢复: 排除 {excluded_aircraft}，航班不变 ({len(flights)} 个)",
        )
        set_active_flights(list(flights))
        set_uploaded_flights(list(flights))
        set_active_chains(list(chains) if chains else list(get_active_chains()))
        set_filtered_mode(True)
        progress(50, f"跳过航班筛选，保持 {len(get_active_chains())} 条任务链")
    else:
        set_excluded_aircraft([])
        progress(45, f"接收 {len(flights)} 个航班，准备重跑排班...")
        set_active_flights(list(flights))
        set_uploaded_flights(list(flights))

        progress(50, "正在重新筛选任务链...")
        try:
            active_flights = get_active_flights()
            result = filter_flights(
                max_chains=300, custom_flights=active_flights,
            )
            set_active_chains(list(result['chains']))
            set_filtered_mode(True)
            progress(
                65,
                f"任务链筛选完成: {len(result['closed_flights'])} 合格航班, "
                f"{len(get_active_chains())} 链",
            )
        except Exception as e:
            print(f"[RecoveryCallback] filter_flights 失败: {e}, 使用原始 chains")
            set_active_chains(list(chains))
            set_filtered_mode(True)
            progress(65, "任务链筛选失败，使用原始链")

    if not is_crew_recovery:
        set_flight_aircraft_cache(None)
        set_aircraft_chains_cache(None)

    _rebuild_transit_cache()

    if not is_crew_recovery:
        progress(
            75,
            "正在重新分配飞机..."
            + (f" (排除 {len(excluded_aircraft)} 架)" if excluded_aircraft else ""),
        )
        try:
            num_aircraft = DEFAULT_AIRCRAFT_COUNT
            if excluded_aircraft:
                num_aircraft = max(num_aircraft - len(excluded_aircraft), 5)
                print(
                    f"[RecoveryCallback] 飞机异常: 可用飞机数 {num_aircraft}"
                )
            active_chains = get_active_chains()
            routing_result = routing_service.solve_chain_coverage(
                active_chains, num_aircraft, 60,
                excluded_aircraft=(
                    excluded_aircraft if excluded_aircraft else None
                ),
            )
            set_aircraft_chains_cache([
                list(ac.assigned_flights)
                for ac in routing_result if ac.assigned_flights
            ])
            set_flight_aircraft_cache({
                f.flight_id: ac.tail_no
                for ac in routing_result for f in ac.assigned_flights
            })
            used_tails = [ac.tail_no for ac in routing_result]
            progress(
                85,
                f"飞机分配完成: {len(routing_result)} 架 "
                f"(排除: {excluded_aircraft if excluded_aircraft else '无'}, "
                f"实际使用: {used_tails})",
            )
        except Exception as e:
            print(f"[RecoveryCallback] 飞机排班失败: {e}")
            progress(85, f"飞机排班失败: {e}")

    progress(90, "正在处理机组排班...")
    try:
        if is_crew_recovery:
            print(
                f"[RecoveryCallback] 机组替班：应用 "
                f"{len(crew_substitutions)} 项变更"
            )
            pre_pool = (
                copy.deepcopy(crew_service._crew_pool)
                if crew_service._crew_pool else None
            )
            set_pre_substitution_crew_pool(pre_pool)
            _apply_crew_substitutions_to_pool(crew_substitutions)
            set_active_crew_substitutions(crew_substitutions)
        else:
            crew_service._base_pools = {}
            crew_service._crew_pool = None
            crew_service._cache_key = None
            airports = set()
            for f in get_active_flights():
                ap = (
                    getattr(f, 'departure_airport', '')
                    or getattr(f, 'arrival_airport', '')
                )
                if ap:
                    airports.add(ap)
            if airports:
                crew_service.schedule_crew(flights=get_active_flights())
                progress(
                    92,
                    f"机组排班完成, "
                    f"{len(getattr(crew_service, '_crew_pool', []) or [])} 人",
                )
            set_active_crew_substitutions([])
            set_cached_crew_schedule({})

        if is_crew_recovery:
            new_cache = {}
            crew_pool = crew_service._crew_pool or []
            base_crews = {}
            for c in crew_pool:
                base = getattr(c, 'base', '成都')
                base_crews.setdefault(base, []).append(c)

            team_groups = []
            try:
                team_groups, _ = crew_service.compute_team_groups(
                    crew_substitutions,
                )
            except Exception:
                pass

            all_dates = set()
            for c in crew_pool:
                for af in (c.assigned_flights or []):
                    f_obj = af.get('flight') if isinstance(af, dict) else af
                    if f_obj and hasattr(f_obj, 'time_departure'):
                        y, m, d, *_ = f_obj.time_departure
                        all_dates.add(f"{y}-{m:02d}-{d:02d}")

            for base, base_crew in base_crews.items():
                assigned = [c for c in base_crew if c.assigned_flights]
                dates = sorted(all_dates)

                base_flights = set()
                base_covered = set()
                for c in base_crew:
                    for af in (c.assigned_flights or []):
                        f_obj = af.get('flight') if isinstance(af, dict) else af
                        if f_obj:
                            fid = str(getattr(f_obj, 'flight_id', ''))
                            base_flights.add(fid)
                            base_covered.add(fid)
                total_b = len(base_flights)
                cov_pct = (
                    100.0
                    if total_b == 0
                    else round(len(base_covered) / total_b * 100, 1)
                )

                new_cache[base] = {
                    'crew': [c.to_dict() for c in assigned],
                    'total_crew': len(assigned),
                    'report': {},
                    'dates': dates,
                    'mode': 'chain',
                    'pairings': [],
                    'assigned_pairings': [],
                    'uncovered_flights': [],
                    'uncovered_flights_count': 0,
                    'coverage_pct': cov_pct,
                    'coverage': {
                        'coverage_pct': cov_pct,
                        'covered_flights': len(base_covered),
                        'total_flights': total_b,
                        'uncovered_flights': 0,
                    },
                    'team_groups': team_groups,
                }
                print(
                    f"[RecoveryCallback] 缓存基地 {base}: "
                    f"{len(assigned)} 人, {len(team_groups)} 个机组"
                )
            set_cached_crew_schedule(new_cache)
            progress(
                95,
                f"机组替班已应用并缓存: {len(crew_substitutions)} 项, "
                f"{len(new_cache)} 个基地",
            )
        elif not is_crew_recovery:
            progress(95, "机组排班完成")
    except Exception as e:
        print(f"[RecoveryCallback] 机组排班失败: {e}")
        traceback.print_exc()
        progress(95, f"机组排班失败: {e}")

    progress(
        98,
        f"重排班完成: {len(get_active_flights())} flights, "
        f"{len(get_active_chains())} chains",
    )

    history_id = get_current_history_id()
    if history_id:
        try:
            _persist_recovery_result(history_id)
            progress(100, "执行完成，数据已保存")
        except Exception as e:
            print(f"[RecoveryCallback] 持久化失败: {e}")
            progress(100, "执行完成（持久化失败）")

    # 恢复执行完毕
    # 机组替班恢复：主动设置分析保护，让 /schedule/crew 返回缓存数据
    # 非机组恢复：解除保护，让 CrewView 走正常排班
    if is_crew_recovery:
        set_analysis_pending(True)
        print(f"[RecoveryCallback] 分析保护已开启（机组替班）")
    else:
        set_analysis_pending(False)
        print(f"[RecoveryCallback] 分析保护已解除")


def _clear_crew_substitution_cache():
    set_active_crew_substitutions([])
    set_cached_crew_schedule({})
    pre_pool = get_pre_substitution_crew_pool()
    if pre_pool is not None:
        crew_service._crew_pool = copy.deepcopy(pre_pool)
        set_pre_substitution_crew_pool(None)
        print(
            f"[CacheClear] 已恢复替班前机组池: "
            f"{len(crew_service._crew_pool)} 人"
        )
    set_analysis_pending(True)
    print(f"[CacheClear] 已设置分析保护标记，阻止机组池被覆盖")


def _flight_date_at_airport(flight, airport):
    """获取航班在指定机场的操作日期。
    到达航班用到达日期，出发航班用出发日期。
    """
    if flight.arrival_airport == airport:
        parts = flight.time_arrival
        y, m, d = parts[0], parts[1], parts[2]
    else:
        parts = flight.time_departure
        y, m, d = parts[0], parts[1], parts[2]
    return f"{y}-{m:02d}-{d:02d}"


# ==================== 飞机排班 API ====================

@schedule_bp.route('/schedule/routing', methods=['POST'])
@safe_handler
def run_routing():
    """执行飞机排班算法。
    筛选模式下默认使用链集合覆盖（航司标准做法），
    否则使用二分图/贪心/VRP。
    """
    body = request.get_json() or {}
    algorithm = body.get('algorithm', 'bipartite')
    num_aircraft = body.get('num_aircraft', DEFAULT_AIRCRAFT_COUNT)
    min_gap = body.get('min_gap', 60)

    chains = _get_active_chains()
    use_chain_coverage = get_filtered_mode() and chains

    set_aircraft_chains_cache(None)

    excluded = list(get_excluded_aircraft()) if get_excluded_aircraft() else []
    if excluded:
        num_aircraft = max(num_aircraft - len(excluded), 5)

    if use_chain_coverage and algorithm in ('bipartite', 'chain_coverage'):
        result = routing_service.solve_chain_coverage(
            chains, num_aircraft, min_gap,
            excluded_aircraft=excluded if excluded else None,
        )
    else:
        flights = _get_active_flights()
        if algorithm == 'bipartite':
            result = routing_service.solve_bipartite(flights, min_gap)
        elif algorithm == 'greedy':
            result = routing_service.solve_greedy_only(
                flights, num_aircraft, min_gap,
            )
        elif algorithm == 'vrp':
            result = routing_service.solve_vrp(flights, num_aircraft, min_gap)
        else:
            result = routing_service.solve_bipartite(flights, min_gap)

    set_aircraft_chains_cache([
        list(ac.assigned_flights) for ac in result if ac.assigned_flights
    ])
    set_flight_aircraft_cache({
        f.flight_id: ac.tail_no
        for ac in result for f in ac.assigned_flights
    })

    flights = _get_active_flights()
    stats = routing_service.get_stats(result, len(flights))
    if use_chain_coverage:
        stats['method'] = 'chain_coverage'
        stats['chains_input'] = len(chains)

    return jsonify({
        'code': 0,
        'data': {
            'algorithm': algorithm,
            'aircrafts': [a.to_dict() for a in result],
            'stats': stats,
        },
    })


@schedule_bp.route('/schedule/compare', methods=['GET'])
@safe_handler
def compare_routing():
    """对比不同排班算法（含链集合覆盖）"""
    flights = _get_active_flights()
    chains = _get_active_chains()

    bipartite_result = routing_service.solve_bipartite(flights)
    greedy_result = routing_service.solve_greedy_only(flights, 12)

    result = {
        'bipartite': {
            'aircrafts': [a.to_dict() for a in bipartite_result],
            'stats': routing_service.get_stats(bipartite_result, len(flights)),
        },
        'greedy': {
            'aircrafts': [a.to_dict() for a in greedy_result],
            'stats': routing_service.get_stats(greedy_result, len(flights)),
        },
    }

    if chains:
        excluded = list(get_excluded_aircraft()) if get_excluded_aircraft() else []
        num_ac = max(DEFAULT_AIRCRAFT_COUNT - len(excluded), 5)
        chain_result = routing_service.solve_chain_coverage(
            chains, num_ac,
            excluded_aircraft=excluded if excluded else None,
        )
        result['chain_coverage'] = {
            'aircrafts': [a.to_dict() for a in chain_result],
            'stats': routing_service.get_stats(chain_result, len(flights)),
        }

    return jsonify({'code': 0, 'data': result})


# ==================== 跑道调度 API ====================

@schedule_bp.route('/schedule/runway', methods=['POST'])
@safe_handler
def run_runway():
    """执行跑道调度 API — 按机场分组独立计算，每条跑道互不影响"""
    body = request.get_json() or {}
    method = body.get('method', 'fcfs')

    flights = _get_active_flights()

    arrivals_map = {}
    for f in flights:
        arrivals_map.setdefault(f.arrival_airport, []).append(f)

    departures_map = {}
    for f in flights:
        departures_map.setdefault(f.departure_airport, []).append(f)

    if method == 'cp_sat':
        all_landing = []
        all_takeoff = []
        all_stats = {}
        all_airports = set(arrivals_map.keys()) | set(departures_map.keys())
        for airport in all_airports:
            runway_service._set_airport(airport)
            raw = (
                arrivals_map.get(airport, [])
                + departures_map.get(airport, [])
            )
            seen = {}
            ap_flights = []
            for f in raw:
                if f.flight_id not in seen:
                    seen[f.flight_id] = f
                    ap_flights.append(f)
            if not ap_flights:
                continue
            land_sch, take_sch, stats = runway_service.solve_unified(ap_flights)
            all_landing.extend(land_sch)
            all_takeoff.extend(take_sch)
            all_stats[airport] = stats
        all_items = all_landing + all_takeoff
        return jsonify({
            'code': 0,
            'data': {
                'schedule': all_items,
                'total': len(all_items),
                'method': 'cp_sat',
                'stats': all_stats,
            },
        })

    all_items = []
    all_airports = set(arrivals_map.keys()) | set(departures_map.keys())
    for airport in all_airports:
        runway_service._set_airport(airport)
        raw = (
            arrivals_map.get(airport, [])
            + departures_map.get(airport, [])
        )
        seen = {}
        ap_flights = []
        for f in raw:
            if f.flight_id not in seen:
                seen[f.flight_id] = f
                ap_flights.append(f)
        if not ap_flights:
            continue
        sched, _ = runway_service.solve_multi_runway(ap_flights, airport)
        all_items.extend(sched)

    return jsonify({
        'code': 0,
        'data': {
            'schedule': all_items,
            'total': len(all_items),
            'method': method,
        },
    })


# ==================== 调度概览 API ====================

@schedule_bp.route('/schedule/current', methods=['GET'])
@safe_handler
def get_current_schedule():
    """获取当前排班方案"""
    data_service.load_all()
    return jsonify({
        'code': 0,
        'data': {
            'aircrafts': [a.to_dict() for a in data_service.aircrafts],
            'total_flights': len(data_service.flights),
            'total_aircrafts': len(data_service.aircrafts),
            'total_airports': len(data_service.airports),
        },
    })


@schedule_bp.route('/schedule/dashboard', methods=['GET'])
@safe_handler
def get_dashboard():
    """全局Dashboard数据"""
    data_service.load_all()
    flights = data_service.flights

    by_date = {}
    airport_set = set()
    ac_types = set()
    for f in flights:
        parts = f.time_departure
        y, m, d = parts[0], parts[1], parts[2]
        dk = f"{y}-{m:02d}-{d:02d}"
        by_date[dk] = by_date.get(dk, 0) + 1
        airport_set.add(f.departure_airport)
        airport_set.add(f.arrival_airport)
        ac_types.add(f.ac_type)

    dates_sorted = sorted(by_date.keys())
    total = len(flights)

    type_dist = {}
    for f in flights:
        type_dist[f.ac_type] = type_dist.get(f.ac_type, 0) + 1

    from collections import Counter
    ap_counter = Counter()
    for f in flights:
        ap_counter[f.departure_airport] += 1
        ap_counter[f.arrival_airport] += 1
    top_airports = ap_counter.most_common(10)

    return jsonify({
        'code': 0,
        'data': {
            'total_flights': total,
            'total_airports': len(airport_set),
            'total_aircraft_types': list(ac_types),
            'date_range': (
                f"{dates_sorted[0]} ~ {dates_sorted[-1]}"
                if dates_sorted else ''
            ),
            'daily_flights': [
                {'date': k, 'count': v}
                for k, v in sorted(by_date.items())
            ],
            'type_distribution': [
                {'type': k, 'count': v}
                for k, v in sorted(type_dist.items())
            ],
            'top_airports': [
                {'airport': k, 'flights': v} for k, v in top_airports
            ],
            'avg_per_day': round(total / max(len(by_date), 1), 1),
            'peak_day': (
                max(by_date.items(), key=lambda x: x[1])
                if by_date else ('', 0)
            ),
        },
    })


# ==================== 地图演示数据 API ====================

@schedule_bp.route('/schedule/save', methods=['POST'])
@safe_handler
def save_schedule_api():
    """保存当前排班和跑道调度方案，供地图演示使用"""
    data_service.load_all()

    body = request.get_json() or {}
    date = body.get('date', '')
    routing_aircrafts = body.get('routing_aircrafts', [])
    runway_items = body.get('runway_items', [])

    if not date:
        return jsonify({'code': 1, 'msg': '缺少日期参数'})

    save_schedule(date, routing_aircrafts, runway_items)

    return jsonify({
        'code': 0,
        'data': {'saved_dates': get_all_dates()},
    })


@schedule_bp.route('/schedule/map-data', methods=['GET'])
@safe_handler
def get_map_data():
    """获取指定日期的地图飞行动画数据——仅筛选后可用"""
    data_service.load_all()

    if not get_filtered_mode() or not get_active_flights():
        return jsonify({
            'code': 0,
            'data': {
                'date': '',
                'timeslices': [],
                'total_slices': 0,
                'filtered_mode': False,
            },
        })

    timeslices = build_multi_day_timeslices(list(get_active_flights()))

    first_date = ''
    for f in get_active_flights():
        td = f.time_departure
        first_date = f"{td[0]}-{td[1]:02d}-{td[2]:02d}"
        break

    return jsonify({
        'code': 0,
        'data': {
            'date': first_date,
            'timeslices': timeslices,
            'total_slices': len(timeslices),
            'filtered_mode': True,
        },
    })


@schedule_bp.route('/schedule/saved-dates', methods=['GET'])
@safe_handler
def get_saved_dates():
    """获取可用于演示的日期：已保存调度日期 + 筛选活跃航班日期"""
    saved = get_all_dates()

    if get_filtered_mode() and get_active_flights():
        for f in get_active_flights():
            td = f.time_departure
            d = f"{td[0]}-{td[1]:02d}-{td[2]:02d}"
            if d not in saved:
                saved.append(d)
        saved.sort()

    return jsonify({
        'code': 0,
        'data': saved,
    })


# ==================== 登机口分配 API ====================

@schedule_bp.route('/schedule/gates', methods=['POST'])
@safe_handler
def assign_gates():
    """执行登机口自动分配（含跑道对接）"""
    body = request.get_json() or {}
    airport = body.get('airport', '成都')
    algorithm = body.get('algorithm', 'bipartite')
    date = body.get('date', None)

    flights = _get_active_flights()

    runway_schedule = []
    ap_flights = [
        f for f in flights
        if f.arrival_airport == airport or f.departure_airport == airport
    ]
    if date:
        ap_flights = [
            f for f in ap_flights
            if _flight_date_at_airport(f, airport) == date
        ]
    if ap_flights:
        runway_service._set_airport(airport)
        sched, _ = runway_service.solve_multi_runway(ap_flights, airport)
        runway_schedule = sched

    gates = gate_service.assign_flights_to_gates(
        airport, algorithm, date,
        flights=flights,
        runway_schedule=runway_schedule,
    )
    conflicts = gate_service.detect_conflicts(gates)
    stats = gate_service.get_utilization_stats(gates)
    dates = gate_service._get_dates_for_airport(airport)

    flight_aircraft = _get_flight_aircraft_map()

    gate_dicts = []
    for g in gates:
        gd = g.to_dict()
        for a in gd['assigned_flights']:
            a['tail_no'] = flight_aircraft.get(a['flight_id'], '?')
        gate_dicts.append(gd)

    return jsonify({
        'code': 0,
        'data': {
            'airport': airport,
            'date': date,
            'algorithm': algorithm,
            'gates': gate_dicts,
            'conflicts': conflicts,
            'conflict_count': len(conflicts),
            'stats': stats,
            'dates': dates,
        },
    })


@schedule_bp.route('/schedule/gates/compare', methods=['POST'])
@safe_handler
def compare_gates():
    """对比登机口分配算法（含跑道对接）"""
    body = request.get_json() or {}
    airport = body.get('airport', '成都')
    date = body.get('date', None)

    flights = _get_active_flights()

    runway_schedule = []
    ap_flights = [
        f for f in flights
        if f.arrival_airport == airport or f.departure_airport == airport
    ]
    if ap_flights:
        runway_service._set_airport(airport)
        sched, _ = runway_service.solve_multi_runway(ap_flights, airport)
        runway_schedule = sched

    result = gate_service.compare_algorithms(
        airport, date,
        flights=flights,
        runway_schedule=runway_schedule,
    )

    flight_aircraft = _get_flight_aircraft_map()
    for key in ('greedy', 'bipartite', 'cp_sat'):
        for gd in result[key].get('gates', []):
            for a in gd.get('assigned_flights', []):
                a['tail_no'] = flight_aircraft.get(
                    a.get('flight_id', ''), '?',
                )

    return jsonify({'code': 0, 'data': result})


@schedule_bp.route('/schedule/save-gates', methods=['POST'])
@safe_handler
def save_gates():
    """保存登机口分配方案"""
    body = request.get_json() or {}
    date = body.get('date', '')
    gates = body.get('gates', [])

    if not date:
        return jsonify({'code': 1, 'msg': '缺少日期参数'})

    existing = get_schedule(date) or {}
    existing['gates'] = gates
    save_schedule(
        date,
        existing.get('routing_aircrafts', []),
        existing.get('runway_items', []),
    )

    return jsonify({
        'code': 0,
        'data': {'saved_dates': get_all_dates()},
    })


# ==================== 机组排班 API ====================

@schedule_bp.route('/schedule/crew', methods=['POST'])
@safe_handler
def schedule_crew():
    """
    执行机组自动排班。

    模式：
      - chain: 基于飞机排班链切割（航司标准，筛选后自动启用）
      - pairing: 从航班DFS生成pairing再分配
      - greedy: 逐航班贪心分配
    """
    body = request.get_json() or {}
    airport = body.get('airport', None)
    date = body.get('date', None)
    mode = body.get('mode', 'greedy')
    airline = body.get('airline', None)

    active_flights = _get_active_flights()
    chains = _get_active_chains()

    subs = get_active_crew_substitutions()
    analysis_pending = get_analysis_pending()
    cached_schedule = get_cached_crew_schedule()

    # ===== 替班缓存处理 =====
    # 仅在「分析保护模式 + 缓存命中目标基地」时返回替班缓存
    if analysis_pending and airport and airport in cached_schedule:
        cached = cached_schedule[airport]
        cached['is_cached'] = True
        print(f"[Schedule/Crew] 保护模式缓存命中: {airport}")
        return jsonify({'code': 0, 'data': cached})

    # 其他所有情况：无条件清除替班状态，走正常排班
    if analysis_pending:
        print(f"[Schedule/Crew] 退出保护模式 (airport={airport})")
        set_analysis_pending(False)

    # 核弹级清除：在正常排班模式中彻底删除所有替班相关状态
    if subs:
        print(f"[Schedule/Crew] 清除替班数据 ({len(subs)}条)", flush=True)
    set_active_crew_substitutions([])
    set_cached_crew_schedule({})
    pre_pool = get_pre_substitution_crew_pool()
    if pre_pool is not None:
        import copy
        crew_service._crew_pool = copy.deepcopy(pre_pool)
        set_pre_substitution_crew_pool(None)
        print(f"[Schedule/Crew] 已恢复替班前机组池", flush=True)
    subs = []
    cached_schedule = {}
    analysis_pending = False

    if get_filtered_mode() and chains and mode in ('greedy', 'pairing', 'chain'):
        all_ac_chains = _get_aircraft_routing()
        # 不在此处按首航班过滤链 — schedule_from_aircraft_chains 内部按航班级匹配
        ac_chains = all_ac_chains

        crew_pool, pairings, assigned_info, uncovered = (
            crew_service.schedule_from_aircraft_chains(ac_chains, airport)
        )

        report = crew_service.get_compliance_report()
        team_groups = crew_service.compute_team_groups()[0]
        dates = crew_service._get_dates_for_airport(airport)

        all_ac_flights = set()
        airport_ac_flights = set()
        for chain in ac_chains:
            for f in chain:
                all_ac_flights.add(f.flight_id)
                if (
                    not airport
                    or f.departure_airport == airport
                    or f.arrival_airport == airport
                ):
                    airport_ac_flights.add(f.flight_id)
        total_scheduled = len(all_ac_flights)
        total_airport = len(airport_ac_flights) if airport else total_scheduled
        uncovered_count = len(uncovered)
        coverage_pct = (
            round(
                (total_airport - uncovered_count) / total_airport * 100, 1,
            )
            if total_airport > 0 else 0
        )

        assigned_crew = _filter_crew_with_flights(crew_pool)

        return jsonify({
            'code': 0,
            'data': {
                'crew': [c.to_dict() for c in assigned_crew],
                'total_crew': len(assigned_crew),
                'report': report,
                'dates': dates,
                'mode': 'chain',
                'pairings': [p.to_dict() for p in pairings],
                'assigned_pairings': assigned_info,
                'uncovered_flights': [{
                    'flight_id': f.flight_id,
                    'flight_no': f.flight_no,
                    'departure_airport': f.departure_airport,
                    'arrival_airport': f.arrival_airport,
                    'time_departure': (
                        f._format_time(f.time_departure)
                        if hasattr(f, '_format_time') else ''
                    ),
                    'date': _flight_date_key(f),
                } for f in uncovered],
                'uncovered_flights_count': uncovered_count,
                'coverage_pct': coverage_pct,
                'coverage': {
                    'coverage_pct': coverage_pct,
                    'covered_flights': total_airport - uncovered_count,
                    'total_flights': total_airport,
                    'uncovered_flights': uncovered_count,
                },
                'team_groups': team_groups,
            },
        })

    if mode == 'pairing':
        crew_pool, pairings, assigned_info, uncovered = (
            crew_service.schedule_by_pairing(
                airport, date, flights=active_flights,
            )
        )
        report = crew_service.get_compliance_report()
        team_groups = crew_service.compute_team_groups()[0]
        dates = crew_service._get_dates_for_airport(airport)

        data_service.load_all()
        flights_all = data_service.flights
        if airport:
            flights_all = [
                f for f in flights_all
                if f.departure_airport == airport
                or f.arrival_airport == airport
            ]
        if date:
            flights_all = [
                f for f in flights_all
                if _flight_date_key(f) == date
            ]
        total_flights = len(flights_all)
        uncovered_count = len(uncovered)
        coverage_pct = (
            round(
                (total_flights - uncovered_count) / total_flights * 100, 1,
            )
            if total_flights > 0 else 0
        )

        assigned_crew_p = _filter_crew_with_flights(crew_pool)

        return jsonify({
            'code': 0,
            'data': {
                'crew': [c.to_dict() for c in assigned_crew_p],
                'total_crew': len(assigned_crew_p),
                'report': report,
                'dates': dates,
                'mode': 'pairing',
                'pairings': [p.to_dict() for p in pairings],
                'assigned_pairings': assigned_info,
                'uncovered_flights': [{
                    'flight_id': f.flight_id,
                    'flight_no': f.flight_no,
                    'departure_airport': f.departure_airport,
                    'arrival_airport': f.arrival_airport,
                    'date': _flight_date_key(f),
                    'dep_time': (
                        f"{f.time_departure[3]:02d}:{f.time_departure[4]:02d}"
                    ),
                    'arr_time': (
                        f"{f.time_arrival[3]:02d}:{f.time_arrival[4]:02d}"
                    ),
                    'ac_type': f.ac_type,
                } for f in uncovered],
                'coverage': {
                    'total_flights': total_flights,
                    'covered_flights': total_flights - uncovered_count,
                    'uncovered_flights': uncovered_count,
                    'coverage_pct': coverage_pct,
                },
                'team_groups': team_groups,
            },
        })

    crew_pool = crew_service.schedule_crew(
        airport, date, flights=active_flights,
    )
    report = crew_service.get_compliance_report()
    team_groups = crew_service.compute_team_groups()[0]
    dates = crew_service._get_dates_for_airport(airport)

    assigned_crew_g = _filter_crew_with_flights(crew_pool)

    return jsonify({
        'code': 0,
        'data': {
            'crew': [c.to_dict() for c in assigned_crew_g],
            'total_crew': len(assigned_crew_g),
            'report': report,
            'dates': dates,
            'mode': 'greedy',
            'team_groups': team_groups,
        },
    })


@schedule_bp.route('/schedule/crew/adjust', methods=['POST'])
@safe_handler
def adjust_crew():
    """半自动调整机组排班：用户选择pairing → 自动填充剩余"""
    body = request.get_json() or {}
    airport = body.get('airport', None)
    selected_ids = body.get('selected_ids', [])

    chains = _get_active_chains()
    if not get_filtered_mode() or not chains:
        return jsonify({'code': 1, 'msg': '请先在航班筛选页保存筛选结果'})

    all_ac_chains = _get_aircraft_routing()
    ac_chains = all_ac_chains
    if airport:
        ac_chains = [
            chain for chain in all_ac_chains
            if chain and chain[0].departure_airport == airport
        ]

    crew_pool, pairings, assigned_info, uncovered = (
        crew_service.adjust_schedule(selected_ids, ac_chains, airport)
    )

    report = crew_service.get_compliance_report()
    team_groups = crew_service.compute_team_groups()[0]
    dates = crew_service._get_dates_for_airport(airport)

    all_ac_flights = set()
    airport_ac_flights = set()
    for chain in ac_chains:
        for f in chain:
            all_ac_flights.add(f.flight_id)
            if (
                not airport
                or f.departure_airport == airport
                or f.arrival_airport == airport
            ):
                airport_ac_flights.add(f.flight_id)
    total_airport = len(airport_ac_flights) if airport else len(all_ac_flights)
    uncovered_count = len(uncovered)
    coverage_pct = (
        round(
            (total_airport - uncovered_count) / total_airport * 100, 1,
        )
        if total_airport > 0 else 0
    )

    assigned_crew_adj = _filter_crew_with_flights(crew_pool)

    return jsonify({
        'code': 0,
        'data': {
            'crew': [c.to_dict() for c in assigned_crew_adj],
            'total_crew': len(assigned_crew_adj),
            'report': report,
            'dates': dates,
            'mode': 'chain',
            'pairings': [p.to_dict() for p in pairings],
            'assigned_pairings': assigned_info,
            'uncovered_flights': [{
                'flight_id': f.flight_id,
                'flight_no': f.flight_no,
                'departure_airport': f.departure_airport,
                'arrival_airport': f.arrival_airport,
                'date': _flight_date_key(f),
            } for f in uncovered],
            'uncovered_flights_count': uncovered_count,
            'coverage_pct': coverage_pct,
            'coverage': {
                'coverage_pct': coverage_pct,
                'covered_flights': total_airport - uncovered_count,
                'total_flights': total_airport,
                'uncovered_flights': uncovered_count,
            },
            'team_groups': team_groups,
        },
    })


@schedule_bp.route('/schedule/crew/compare', methods=['POST'])
@safe_handler
def compare_crew():
    """对比机组排班：全机场 vs 单机场"""
    body = request.get_json() or {}
    airport = body.get('airport', None)
    date = body.get('date', None)

    active_flights = _get_active_flights()
    full_pool = crew_service.schedule_crew(flights=active_flights)
    full_report = crew_service.get_compliance_report()

    crew_service._base_pools = {}
    crew_service._crew_pool = None
    crew_service._cache_key = None
    filtered_pool = crew_service.schedule_crew(
        airport, date, flights=active_flights,
    )
    filtered_report = crew_service.get_compliance_report()

    return jsonify({
        'code': 0,
        'data': {
            'airport': airport,
            'date': date,
            'full': {
                'total_crew': len(full_pool),
                'assigned': full_report['assigned_crew'],
                'violations': full_report['total_violations'],
            },
            'filtered': {
                'total_crew': len(filtered_pool),
                'assigned': filtered_report['assigned_crew'],
                'violations': filtered_report['total_violations'],
            },
        },
    })


@schedule_bp.route('/schedule/save-crew', methods=['POST'])
@safe_handler
def save_crew():
    """保存机组排班方案"""
    body = request.get_json() or {}
    date = body.get('date', '')
    crew = body.get('crew', [])

    if not date:
        return jsonify({'code': 1, 'msg': '缺少日期参数'})

    existing = get_schedule(date) or {}
    existing['crew'] = crew
    save_schedule(
        date,
        existing.get('routing_aircrafts', []),
        existing.get('runway_items', []),
    )

    return jsonify({
        'code': 0,
        'data': {'saved_dates': get_all_dates()},
    })


@schedule_bp.route('/schedule/crew/swap', methods=['POST'])
@safe_handler
def swap_crew_members():
    """交换两个团队中同岗位的机组人员（不破坏排班结构）"""
    body = request.get_json() or {}
    team_a = body.get('team_id_a', None)
    team_b = body.get('team_id_b', None)
    role = body.get('role', None)

    if team_a is None or team_b is None or not role:
        return jsonify({'code': 1, 'msg': '参数不完整'})
    if team_a == team_b:
        return jsonify({'code': 1, 'msg': '不能选择同一个团队'})

    if not crew_service._crew_pool:
        return jsonify({'code': 1, 'msg': '请先执行自动排班'})

    teams = crew_service.compute_team_groups()[0]

    def _find_by_role(tid, r, att_idx=0):
        tg = next((t for t in teams if t['team_id'] == tid), None)
        if not tg:
            return None
        if r == 'captain':
            cid = tg.get('captain_id')
        elif r == 'first_officer':
            cid = tg.get('officer_id')
        elif r == 'purser':
            cid = tg.get('purser_id')
        elif r == 'attendant':
            ids = tg.get('attendant_ids', [])
            cid = ids[att_idx] if len(ids) > att_idx else None
        else:
            return None
        if cid is None:
            return None
        return next(
            (c for c in crew_service._crew_pool if c.crew_id == cid), None,
        )

    att_idx = body.get('attendant_index', 0)
    mem_a = _find_by_role(team_a, role, att_idx)
    mem_b = _find_by_role(team_b, role, att_idx)

    if not mem_a or not mem_b:
        return jsonify({'code': 1, 'msg': '未找到对应机组人员'})

    mem_a.assigned_flights, mem_b.assigned_flights = (
        mem_b.assigned_flights, mem_a.assigned_flights,
    )

    crew_service._reassign_team_ids()

    team_groups = crew_service.compute_team_groups()[0]
    assigned_crew = _filter_crew_with_flights(crew_service._crew_pool)

    return jsonify({
        'code': 0,
        'msg': f'{mem_a.name} 与 {mem_b.name} 已互换',
        'data': {
            'msg': f'{mem_a.name} 与 {mem_b.name} 已互换',
            'team_groups': team_groups,
            'crew': [c.to_dict() for c in assigned_crew],
        },
    })