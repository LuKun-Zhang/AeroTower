"""机组排班 API 路由 — 所有响应统一 {code: 0, data/msg} 格式"""

import io
import random
import traceback
from flask import Blueprint, jsonify, request, send_file

from ..state import (
    get_active_flights,
    get_active_chains,
    get_filtered_mode,
    get_active_crew_substitutions,
    get_aircraft_chains_cache,
    get_flight_aircraft_cache,
    get_excluded_aircraft,
    set_aircraft_chains_cache,
)

from ..services.data_service import data_service
from ..services import crew_service, routing_service

crew_bp = Blueprint('crew', __name__)


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


def _normalize_flight_times(flights):
    """将航班列表中所有 6 元组时间规范化为 5 元组"""
    for f in flights:
        for attr in ('time_departure', 'time_arrival'):
            t = getattr(f, attr, None)
            if isinstance(t, (tuple, list)) and len(t) > 5:
                setattr(f, attr, tuple(t[:5]))


def _get_active_flights_impl():
    """获取当前活跃航班，优先使用筛选后的数据"""
    _filtered_mode = get_filtered_mode()
    _active_flights = get_active_flights()
    if _filtered_mode and _active_flights:
        _normalize_flight_times(_active_flights)
        return list(_active_flights)
    data_service.load_all()
    return list(data_service.flights)


def _get_active_chains_impl():
    """获取当前活跃任务链（Flight对象列表）"""
    _filtered_mode = get_filtered_mode()
    _active_chains = get_active_chains()
    if _filtered_mode and _active_chains:
        for chain in _active_chains:
            _normalize_flight_times(chain)
        return _active_chains
    return None


def _get_aircraft_routing():
    """获取缓存的飞机排班结果（Flight对象列表的列表）
    筛选模式下从链集合覆盖产出，否则实时计算二分图。
    """
    _aircraft_chains_cache = get_aircraft_chains_cache()
    if _aircraft_chains_cache is not None:
        for chain in _aircraft_chains_cache:
            _normalize_flight_times(chain)
        return _aircraft_chains_cache

    chains = _get_active_chains_impl()
    if chains:
        _excluded_aircraft = get_excluded_aircraft()
        excluded = list(_excluded_aircraft) if _excluded_aircraft else []
        num_ac = max(100 - len(excluded), 5)
        result = routing_service.solve_chain_coverage(
            chains, num_ac, excluded_aircraft=excluded if excluded else None)
        _aircraft_chains_cache = [list(ac.assigned_flights) for ac in result if ac.assigned_flights]
        set_aircraft_chains_cache(_aircraft_chains_cache)
        return _aircraft_chains_cache

    result = routing_service.solve_bipartite(_get_active_flights_impl(), 60)
    _aircraft_chains_cache = [list(ac.assigned_flights) for ac in result if ac.assigned_flights]
    set_aircraft_chains_cache(_aircraft_chains_cache)
    return _aircraft_chains_cache


def _filter_crew_with_flights(crew_pool):
    """只返回有航班的机组（严格5人一组，无散兵）"""
    return [c for c in crew_pool if c.assigned_flights]


# ==================== 机组排班 API ====================

@crew_bp.route('/crew/manual-assign-flight', methods=['POST'])
@safe_handler
def manual_assign_flight():
    """手动为单个航班分配5人机组"""
    body = request.get_json() or {}
    flight_id = body.get('flight_id')
    captain_id = body.get('captain_id')
    officer_id = body.get('officer_id')
    purser_id = body.get('purser_id')
    attendant_ids = body.get('attendant_ids', [])
    airport = body.get('airport', None)

    if flight_id is None or flight_id == '':
        return jsonify({'code': 1, 'msg': '缺少航班ID'})
    if captain_id is None or officer_id is None or purser_id is None or captain_id == '' or officer_id == '' or purser_id == '':
        return jsonify({'code': 1, 'msg': '机长、副驾、乘务长缺一不可'})
    if len(attendant_ids) < 2:
        return jsonify({'code': 1, 'msg': '需要至少2名乘务员'})

    data_service.load_all()
    flights = _get_active_flights_impl()
    if airport:
        flights = [f for f in flights
                   if f.departure_airport == airport or f.arrival_airport == airport]

    target = None
    for f in flights:
        if f.flight_id == int(flight_id):
            target = f
            break
    if not target:
        return jsonify({'code': 1, 'msg': f'未找到航班 #{flight_id}'})

    crew_pool = crew_service.schedule_crew(airport, flights=_get_active_flights_impl())
    for c in crew_pool:
        c.assigned_flights = []

    success, msg, info = crew_service.assign_single_flight(
        target, captain_id, officer_id, purser_id, attendant_ids)

    if not success:
        return jsonify({'code': 1, 'msg': msg})

    covered_ids = {target.flight_id}
    remaining = [f for f in flights if f.flight_id not in covered_ids]
    if remaining:
        from ..services.crew_service import _schedule_remain
        _schedule_remain(remaining, crew_pool)

    report = crew_service.get_compliance_report()
    team_groups = crew_service.compute_team_groups()[0]
    assigned_crew_adj = _filter_crew_with_flights(crew_pool)

    return jsonify({
        'code': 0,
        'data': {
            'crew': [c.to_dict() for c in assigned_crew_adj],
            'total_crew': len(assigned_crew_adj),
            'report': report,
            'assigned_team': info,
            'team_groups': team_groups,
        },
    })


@crew_bp.route('/crew/available-for-flight', methods=['POST'])
@safe_handler
def available_for_flight():
    """查询某个航班当前可用的机组人员"""
    body = request.get_json() or {}
    flight_id = body.get('flight_id')
    airport = body.get('airport', None)

    if not flight_id:
        return jsonify({'code': 1, 'msg': '缺少航班ID'})

    data_service.load_all()
    flights = data_service.flights
    if airport:
        flights = [f for f in flights
                   if f.departure_airport == airport or f.arrival_airport == airport]

    target = None
    for f in flights:
        if f.flight_id == int(flight_id):
            target = f
            break
    if not target:
        return jsonify({'code': 1, 'msg': f'未找到航班 #{flight_id}'})

    crew_pool = crew_service.schedule_crew(airport, flights=_get_active_flights_impl())
    dep = target.departure_minutes
    arr = target.arrival_minutes
    fh = target.timespan / 60.0
    dk = _flight_date_key(target)

    from ..services.crew_service import _is_avail_fast, _assign_fast as _af

    # 构建当前人员的忙闲状态
    daily_hours = {c.crew_id: {} for c in crew_pool}
    duty_bounds = {c.crew_id: {} for c in crew_pool}
    crew_starts = {c.crew_id: [] for c in crew_pool}
    crew_ends = {c.crew_id: [] for c in crew_pool}

    for c in crew_pool:
        for a in c.assigned_flights:
            af = a['flight']
            if af.flight_id == target.flight_id:
                continue
            adep = a['duty_start_min']
            aarr = a['duty_end_min']
            afh = af.timespan / 60.0
            adk = _flight_date_key(af)
            _af(c, af, adep, aarr, afh, adk,
                daily_hours, duty_bounds, crew_starts, crew_ends)

    result = {'captains': [], 'officers': [], 'pursers': [], 'attendants': []}
    role_map = {'captain': 'captains', 'first_officer': 'officers',
                'purser': 'pursers', 'attendant': 'attendants'}

    for c in crew_pool:
        if target.ac_type not in c.qualifications:
            continue
        if _is_avail_fast(c, dep, arr, fh, dk, daily_hours, duty_bounds, crew_starts, crew_ends):
            key = role_map.get(c.role)
            if key:
                result[key].append({
                    'crew_id': c.crew_id, 'name': c.name,
                    'role_label': c.role_label, 'base': c.base,
                    'today_hours': round(daily_hours[c.crew_id].get(dk, 0), 1),
                })

    return jsonify({
        'code': 0,
        'data': {
            'flight': {
                'flight_id': target.flight_id, 'flight_no': target.flight_no,
                'dep_airport': target.departure_airport, 'arr_airport': target.arrival_airport,
                'date': dk,
            },
            'available': result,
        },
    })


@crew_bp.route('/crew/bases', methods=['GET'])
@safe_handler
def get_crew_bases():
    """获取机组可用基地列表（可指定航司）"""
    airline = request.args.get('airline', None)
    bases = crew_service.get_available_bases(airline=airline)
    return jsonify({'code': 0, 'data': bases})


@crew_bp.route('/crew/by-base', methods=['GET'])
@safe_handler
def get_crew_by_base():
    """获取指定基地的机组人员列表（按角色分组）"""
    from ..services.crew_service import get_crew_by_base as get_crew_by_base_svc
    base = request.args.get('base', '成都')
    airline = request.args.get('airline', '四川航空')
    crew_list = get_crew_by_base_svc(base, airline)
    # 按角色分组
    grouped = {}
    for c in crew_list:
        role = c['role']
        if role not in grouped:
            grouped[role] = []
        grouped[role].append(c)
    return jsonify({
        'code': 0,
        'data': {
            'base': base,
            'airline': airline,
            'crew': crew_list,
            'by_role': grouped,
        }
    })


@crew_bp.route('/crew/assign-pairings', methods=['POST'])
@safe_handler
def assign_crew_pairings():
    """用户手动选链指派机组"""
    body = request.get_json() or {}
    airport = body.get('airport', None)
    date = body.get('date', None)
    selected_ids = body.get('selected_ids', [])

    data_service.load_all()
    flights = _get_active_flights_impl()
    if airport:
        flights = [f for f in flights
                   if f.departure_airport == airport or f.arrival_airport == airport]
    if date:
        flights = [f for f in flights if _flight_date_key(f) == date]

    # 生成配对池
    from ..services.pairing_service import PairingGenerator
    gen = PairingGenerator(flights, preferred_base=airport)
    pairings = gen.generate(max_pairings=3000)

    crew_pool, assigned, uncovered = crew_service.assign_selected_pairings(
        selected_ids, pairings, flights)
    report = crew_service.get_compliance_report()
    team_groups = crew_service.compute_team_groups()[0]

    assigned_crew_ap = _filter_crew_with_flights(crew_pool)

    return jsonify({
        'code': 0,
        'data': {
            'crew': [c.to_dict() for c in assigned_crew_ap],
            'total_crew': len(assigned_crew_ap),
            'report': report,
            'pairings': [p.to_dict() for p in pairings],
            'assigned_pairings': assigned,
            'uncovered_flights': [f.flight_id for f in uncovered],
            'team_groups': team_groups,
        },
    })


@crew_bp.route('/pairings/list', methods=['POST'])
@safe_handler
def list_pairings():
    """获取任务链列表（仅生成配对，不执行排班）"""
    body = request.get_json() or {}
    airport = body.get('airport', None)

    data_service.load_all()
    flights = data_service.flights
    if airport:
        flights = [f for f in flights
                   if f.departure_airport == airport or f.arrival_airport == airport]

    base = airport or flights[0].departure_airport
    from ..services.pairing_service import PairingGenerator
    gen = PairingGenerator(flights, preferred_base=airport)
    pairings = gen.generate(max_pairings=3000)

    return jsonify({
        'code': 0,
        'data': {
            'pairings': [p.to_dict() for p in pairings],
            'base': base,
        },
    })


@crew_bp.route('/crew/assign-pairing-to-team', methods=['POST'])
@safe_handler
def assign_pairing_to_team():
    """手动组建机组 & 分配任务链 → 剩余自动填充（团队模式）"""
    body = request.get_json() or {}
    pairing_id = body.get('pairing_id')
    captain_id = body.get('captain_id')  # crew_id
    officer_id = body.get('officer_id')
    purser_id = body.get('purser_id')
    attendant_ids = body.get('attendant_ids', [])
    captain_name = body.get('captain_name', '')
    officer_name = body.get('officer_name', '')
    purser_name = body.get('purser_name', '')
    attendant_names = body.get('attendant_names', [])
    airport = body.get('airport', None)

    if pairing_id is None or pairing_id == '':
        return jsonify({'code': 1, 'msg': '缺少任务链ID'})
    if captain_id is None or officer_id is None or purser_id is None or captain_id == '' or officer_id == '' or purser_id == '':
        return jsonify({'code': 1, 'msg': '机长、副驾、乘务长缺一不可'})
    if len(attendant_ids) < 2:
        return jsonify({'code': 1, 'msg': '需要至少2名乘务员'})

    chains = _get_active_chains_impl()
    if not get_filtered_mode() or not chains:
        return jsonify({'code': 1, 'msg': '请先在航班筛选页保存筛选结果'})

    all_ac_chains = _get_aircraft_routing()
    ac_chains = all_ac_chains
    if airport:
        ac_chains = [chain for chain in all_ac_chains
                     if chain and chain[0].departure_airport == airport]

    # 先用自动排班初始化机组池（保证 crew_id 一致）
    from ..services.crew_service import _find_by_id, _team_can_take
    from ..models.pairing import Pairing

    crew_pool, all_pairings, _, _ = crew_service.schedule_from_aircraft_chains(ac_chains, airport)

    # 查找目标 pairing
    target_pairing = None
    for p in all_pairings:
        if p.pairing_id == int(pairing_id):
            target_pairing = p
            break
    if not target_pairing:
        return jsonify({'code': 1, 'msg': f'未找到任务链 #{pairing_id}'})

    # 查找5个指定成员（优先ID，后备名字）
    cap = _find_by_id(crew_pool, captain_id)
    if not cap and captain_name:
        cap = next((c for c in crew_pool if c.name == captain_name and c.role == 'captain'), None)
    off = _find_by_id(crew_pool, officer_id)
    if not off and officer_name:
        off = next((c for c in crew_pool if c.name == officer_name and c.role == 'first_officer'), None)
    pur = _find_by_id(crew_pool, purser_id)
    if not pur and purser_name:
        pur = next((c for c in crew_pool if c.name == purser_name and c.role == 'purser'), None)
    att1 = _find_by_id(crew_pool, attendant_ids[0]) if len(attendant_ids) > 0 else None
    att1_name_val = attendant_names[0] if len(attendant_names) > 0 else ''
    if not att1 and att1_name_val:
        att1 = next((c for c in crew_pool if c.name == att1_name_val and c.role == 'attendant'), None)
    att2 = _find_by_id(crew_pool, attendant_ids[1]) if len(attendant_ids) > 1 else None
    att2_name_val = attendant_names[1] if len(attendant_names) > 1 else ''
    if not att2 and att2_name_val:
        att2 = next((c for c in crew_pool if c.name == att2_name_val and c.role == 'attendant'), None)
    if not cap:
        return jsonify({'code': 1, 'msg': f'机长 #{captain_id} 不存在'})
    if not off:
        return jsonify({'code': 1, 'msg': f'副驾 #{officer_id} 不存在'})
    if not pur:
        return jsonify({'code': 1, 'msg': f'乘务长 #{purser_id} 不存在'})
    if not att1 or not att2:
        return jsonify({'code': 1, 'msg': '乘务员不足'})

    # 清空所有分配，手动指派手动机组到目标pairing
    for c in crew_pool:
        c.assigned_flights = []
    for f in target_pairing.flights:
        dep, arr = f.departure_minutes, f.arrival_minutes
        cap.add_flight(f, dep, arr)
        off.add_flight(f, dep, arr)
        pur.add_flight(f, dep, arr)
        att1.add_flight(f, dep, arr)
        att2.add_flight(f, dep, arr)

    manual_info = {
        'pairing_id': target_pairing.pairing_id,
        'captain': cap.name, 'first_officer': off.name,
        'purser': pur.name, 'attendants': [att1.name, att2.name],
    }
    assigned_info = [manual_info]
    covered_ids = set(target_pairing.flight_ids())

    # 自动填充剩余pairing（排除手动机组，团队模式）
    all_flights = []
    for chain in ac_chains:
        all_flights.extend(chain)
    all_flights = sorted(all_flights, key=lambda f: f.departure_minutes)

    remaining_pairings = [p for p in all_pairings if p.pairing_id != target_pairing.pairing_id]
    remaining_flights = [f for f in all_flights if f.flight_id not in covered_ids]

    if remaining_pairings and remaining_flights:
        remaining_flight_set = set(f.flight_id for f in remaining_flights)
        manual_ids = {cap.crew_id, off.crew_id, pur.crew_id, att1.crew_id, att2.crew_id}

        remaining_captains = [c for c in crew_pool if c.role == 'captain' and c.crew_id not in manual_ids]
        remaining_officers = [c for c in crew_pool if c.role == 'first_officer' and c.crew_id not in manual_ids]
        remaining_pursers = [c for c in crew_pool if c.role == 'purser' and c.crew_id not in manual_ids]
        remaining_atts = [c for c in crew_pool if c.role == 'attendant' and c.crew_id not in manual_ids]
        random.shuffle(remaining_captains)
        random.shuffle(remaining_officers)
        random.shuffle(remaining_pursers)
        random.shuffle(remaining_atts)

        auto_teams = []
        max_t = min(len(remaining_captains), len(remaining_officers),
                   len(remaining_pursers), len(remaining_atts) // 2)
        for i in range(max_t):
            auto_teams.append((remaining_captains[i], remaining_officers[i],
                               remaining_pursers[i], remaining_atts[i*2], remaining_atts[i*2+1]))

        cand_pairings = []
        for p in remaining_pairings:
            uncovered_seg = [f for f in p.flights if f.flight_id in remaining_flight_set]
            if len(uncovered_seg) >= 2:
                cand_pairings.append(Pairing(pairing_id=p.pairing_id, flights=uncovered_seg,
                                              base=uncovered_seg[0].departure_airport))

        cand_pairings.sort(key=lambda pp: pp.flights[0].departure_minutes if pp.flights else 0)
        auto_covered = set()
        # 手动团队也加入活跃列表（他们完成pairing后到达某机场，可以接后续，支持跨日）
        manual_last_ap = target_pairing.flights[-1].arrival_airport
        manual_last_arr = max(f.arrival_minutes for f in target_pairing.flights)
        manual_day_duty_start = target_pairing.flights[0].departure_minutes
        active_teams = []  # [(team, last_airport, last_arrival, day_duty_start), ...]
        manual_team_tuple = (cap, off, pur, att1, att2)
        active_teams.append((manual_team_tuple, manual_last_ap, manual_last_arr, manual_day_duty_start))

        for pairing in cand_pairings:
            p_fids = set(f.flight_id for f in pairing.flights)
            if p_fids & auto_covered:
                continue
            p_start = pairing.flights[0].departure_minutes
            p_end = max(f.arrival_minutes for f in pairing.flights)
            dep_ap = pairing.flights[0].departure_airport

            # 策略1: 找可接续的活跃团队（支持跨日）
            found = None
            found_idx = -1
            new_day_start = 0
            for idx, (t, last_ap, last_arr, day_duty_start) in enumerate(active_teams):
                if last_ap != dep_ap:
                    continue
                if p_start < last_arr + 30:
                    continue
                gap = p_start - last_arr

                # 跨日衔接（gap≥6h）：新执勤日
                if gap >= 6 * 60:
                    if not _team_can_take(t, pairing.flights):
                        continue
                    found = (t, p_start)
                    new_day_start = p_start
                    found_idx = idx
                    break
                else:
                    # 同日接续
                    if max(p_end, last_arr) - day_duty_start > 14 * 60:
                        continue
                    if not _team_can_take(t, pairing.flights):
                        continue
                    found = (t, day_duty_start)
                    new_day_start = day_duty_start
                    found_idx = idx
                    break

            if found:
                t, _ = found
                tcap2, toff2, tpur2, tatt1_2, tatt2_2 = t
                for f in pairing.flights:
                    dep, arr = f.departure_minutes, f.arrival_minutes
                    tcap2.add_flight(f, dep, arr)
                    toff2.add_flight(f, dep, arr)
                    tpur2.add_flight(f, dep, arr)
                    tatt1_2.add_flight(f, dep, arr)
                    tatt2_2.add_flight(f, dep, arr)
                assigned_info.append({
                    'pairing_id': pairing.pairing_id,
                    'captain': tcap2.name, 'first_officer': toff2.name,
                    'purser': tpur2.name,
                })
                auto_covered.update(p_fids)
                active_teams[found_idx] = (t, pairing.flights[-1].arrival_airport, p_end, new_day_start)
                continue

            # 策略2: 从基地出发 → 创建新团队
            random.shuffle(auto_teams)
            for team in auto_teams:
                if not _team_can_take(team, pairing.flights):
                    continue
                tcap, toff, tpur, tatt1, tatt2 = team
                for f in pairing.flights:
                    dep, arr = f.departure_minutes, f.arrival_minutes
                    tcap.add_flight(f, dep, arr)
                    toff.add_flight(f, dep, arr)
                    tpur.add_flight(f, dep, arr)
                    tatt1.add_flight(f, dep, arr)
                    tatt2.add_flight(f, dep, arr)
                assigned_info.append({
                    'pairing_id': pairing.pairing_id,
                    'captain': tcap.name, 'first_officer': toff.name,
                    'purser': tpur.name,
                })
                auto_covered.update(p_fids)
                active_teams.append((team, pairing.flights[-1].arrival_airport, p_end, p_start))
                break

    # 统计未覆盖
    all_covered = set()
    for c in crew_pool:
        for af in c.assigned_flights:
            if isinstance(af, dict) and 'flight' in af:
                all_covered.add(af['flight'].flight_id)
    uncovered = [f for f in all_flights if f.flight_id not in all_covered]

    report = crew_service.get_compliance_report()
    team_groups = crew_service.compute_team_groups()[0]
    dates = crew_service._get_dates_for_airport(airport)

    all_ac_flights = set()
    airport_ac_flights = set()
    for chain in ac_chains:
        for f in chain:
            all_ac_flights.add(f.flight_id)
            if not airport or f.departure_airport == airport or f.arrival_airport == airport:
                airport_ac_flights.add(f.flight_id)
    total_airport = len(airport_ac_flights) if airport else len(all_ac_flights)
    uncovered_count = len(uncovered)
    coverage_pct = round((total_airport - uncovered_count) / total_airport * 100, 1) if total_airport > 0 else 0

    assigned_crew = _filter_crew_with_flights(crew_pool)
    return jsonify({
        'code': 0,
        'data': {
            'crew': [c.to_dict() for c in assigned_crew],
            'total_crew': len(assigned_crew),
            'report': report,
            'dates': dates,
            'mode': 'chain',
            'pairings': [p.to_dict() for p in all_pairings],
            'assigned_pairings': assigned_info,
            'assigned_team': manual_info,
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


@crew_bp.route('/crew/export', methods=['POST'])
@safe_handler
def export_crew_schedule():
    """导出机组排班表为 xlsx 文件（与前端显示一致，支持调换后数据）"""
    body = request.get_json(silent=True) or {}
    airport = body.get('airport', None)
    date = body.get('date', None)
    airline = body.get('airline', None)

    base = airport or '全部基地'
    airline_name = airline or '全部航司'

    def _minutes_to_time_str(minutes):
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    def _flight_time_str(flight):
        """从 flight 对象提取 HH:MM 格式的出发/到达时间"""
        td = flight.time_departure
        ta = flight.time_arrival
        return f"{td[3]:02d}:{td[4]:02d}", f"{ta[3]:02d}:{ta[4]:02d}"

    # 优先使用已调度的机组池（保留手动指派和人员调换结果）
    pool = crew_service._crew_pool
    if not pool or not any(c.assigned_flights for c in pool):
        # 尚未排班，自动执行一次
        data_service.load_all()
        flights = data_service.flights
        if airport:
            flights = [f for f in flights
                       if f.departure_airport == airport or f.arrival_airport == airport]
        if date:
            flights = [f for f in flights if _flight_date_key(f) == date]
        pool, _, _, _ = crew_service.schedule_by_pairing(airport, date, flights=flights)

    team_groups, _ = crew_service.compute_team_groups()

    # team_id → 展示序号
    team_order_map = {g['team_id']: i + 1 for i, g in enumerate(team_groups)}
    role_order = {'captain': 0, 'first_officer': 1, 'purser': 2, 'attendant': 3}

    # 收集所有有航班的日期
    all_dates = set()
    for c in pool:
        for a in c.assigned_flights:
            all_dates.add(a.get('date', _flight_date_key(a['flight'])))
    date_order = sorted(all_dates)

    import openpyxl
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    wb = openpyxl.Workbook()

    # 公共样式
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(bold=True, size=11, color='FFFFFF')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin'))
    team_fill = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
    alt_fill = PatternFill(start_color='F2F7FB', end_color='F2F7FB', fill_type='solid')

    # ========== Sheet 1: 机组排班明细（按团队集中） ==========
    ws = wb.active
    ws.title = '机组排班明细'

    ws.merge_cells('A1:I1')
    ws['A1'] = f'{airline_name}机组排班表 — {base}基地'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = center

    headers = ['日期', '姓名', '职务', '航班号', '出发', '到达', '飞行时间', '执勤开始', '执勤结束']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=3, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = thin_border

    row = 4
    for tg in team_groups:
        tid = tg['team_id']
        tno = team_order_map.get(tid, '?')
        # 团队成员：按角色排序
        team_members = [c for c in pool if c.team_id == tid]
        team_members.sort(key=lambda c: role_order.get(c.role, 4))

        if not team_members:
            continue

        # 团队头行（合并单元格）
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
        attends_str = '、'.join(tg['attendants'])
        team_header = (f'机组{tno} — 机长:{tg["captain"]}  副驾:{tg["officer"]}  '
                       f'乘务长:{tg["purser"]}  乘务员:{attends_str} — 共飞{tg["shared_flights"]}班')
        th_cell = ws.cell(row=row, column=1, value=team_header)
        th_cell.font = Font(bold=True, size=11, color='2F5496')
        th_cell.fill = team_fill
        th_cell.alignment = left_align
        th_cell.border = thin_border
        for cc in range(2, 10):
            c = ws.cell(row=row, column=cc)
            c.fill = team_fill
            c.border = thin_border
        row += 1

        # 成员行
        for mi, m in enumerate(team_members):
            m_flights = sorted(m.assigned_flights, key=lambda a: (a.get('date', ''), a['duty_start_min']))
            start_row_member = row
            for fi, af in enumerate(m_flights):
                fobj = af['flight']
                dep_time, arr_time = _flight_time_str(fobj)
                values = [
                    af.get('date', _flight_date_key(fobj)),
                    m.name, m.role_label,
                    fobj.flight_no, fobj.departure_airport, fobj.arrival_airport,
                    f"{fobj.timespan / 60:.1f}h", dep_time, arr_time,
                ]
                for col, val in enumerate(values, 1):
                    cell = ws.cell(row=row, column=col, value=val)
                    cell.alignment = center
                    cell.border = thin_border
                    if mi % 2 == 0:
                        cell.fill = alt_fill
                row += 1

            # 如果该成员有多行，合并姓名和职务列
            if len(m_flights) > 1:
                ws.merge_cells(start_row=start_row_member, start_column=2,
                               end_row=start_row_member + len(m_flights) - 1, end_column=2)
                ws.merge_cells(start_row=start_row_member, start_column=3,
                               end_row=start_row_member + len(m_flights) - 1, end_column=3)

        row += 1  # 团队间空行

    widths1 = [14, 10, 10, 12, 10, 10, 10, 10, 10]
    for i, w in enumerate(widths1, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # ========== Sheet 2: 机组人员汇总 ==========
    ws2 = wb.create_sheet('机组人员汇总')
    ws2.merge_cells('A1:J1')
    ws2['A1'] = f'机组人员汇总 — {base}基地'
    ws2['A1'].font = Font(bold=True, size=14)
    ws2['A1'].alignment = center

    sum_headers = ['机组', '姓名', '职务', '基地', '航司', '总班次', '总飞行(h)', '日最大飞行(h)', '日最大执勤(h)', '是否违规']
    for col, h in enumerate(sum_headers, 1):
        c = ws2.cell(row=3, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = thin_border

    row2 = 4
    current_team = None
    sorted_pool = sorted(
        [c for c in pool if c.assigned_flights],
        key=lambda c: (team_order_map.get(c.team_id, 999), role_order.get(c.role, 4), c.name))

    for c in sorted_pool:
        v = c.is_over_limit()
        tno = team_order_map.get(c.team_id, 999)
        team_label = f'机组{tno}' if c.team_id >= 0 else '-'
        if current_team is not None and tno != current_team:
            row2 += 1
        current_team = tno
        values = [team_label, c.name, c.role_label, c.base, c.airline,
                  len(c.assigned_flights), f'{c.total_flight_hours:.1f}',
                  f'{c.daily_flight_hours:.1f}', f'{c.duty_hours:.1f}',
                  '违规' if v else '合规']
        for col, val in enumerate(values, 1):
            cell = ws2.cell(row=row2, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
            if col == 10 and val == '违规':
                cell.font = Font(color='FF0000', bold=True)
        row2 += 1

    sum_widths = [10, 10, 10, 8, 10, 8, 12, 14, 14, 10]
    for i, w in enumerate(sum_widths, 1):
        ws2.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # ========== Sheet 3: 机组概览 ==========
    ws3 = wb.create_sheet('机组概览')
    ws3.merge_cells('A1:G1')
    ws3['A1'] = f'机组概览 — {base}基地'
    ws3['A1'].font = Font(bold=True, size=14)
    ws3['A1'].alignment = center

    overview_headers = ['机组', '机长', '副驾', '乘务长', '乘务员', '共飞航班数', '涉及日期']
    for col, h in enumerate(overview_headers, 1):
        c = ws3.cell(row=3, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = thin_border

    row3 = 4
    for g in team_groups:
        # 获取该团队覆盖的日期
        tm = [c for c in pool if c.team_id == g['team_id']]
        team_dates = set()
        for m in tm:
            for a in m.assigned_flights:
                team_dates.add(a.get('date', _flight_date_key(a['flight'])))

        values = [
            f'机组{g["team_id"] + 1}',
            g['captain'], g['officer'], g['purser'],
            '、'.join(g['attendants']),
            g['shared_flights'],
            '、'.join(sorted(team_dates)),
        ]
        for col, val in enumerate(values, 1):
            cell = ws3.cell(row=row3, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
        row3 += 1

    ov_widths = [10, 10, 10, 10, 18, 12, 20]
    for i, w in enumerate(ov_widths, 1):
        ws3.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # 构建文件名：川航{基地}基地——{开始日期}至{结束日期}机组排班表
    date_str = date if date else '全日期'
    if not date and date_order:
        date_str = f'{date_order[0]}至{date_order[-1]}'
    base_display = base if base != '全部基地' else '全基地'
    filename = f'川航{base_display}基地——{date_str}机组排班表.xlsx'
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@crew_bp.route('/crew/substitutions', methods=['GET'])
@safe_handler
def get_crew_substitutions():
    """获取当前的机组替班变更列表"""
    substitutions = get_active_crew_substitutions()
    return jsonify({
        'code': 0,
        'data': {
            'substitutions': substitutions,
            'count': len(substitutions),
        }
    })
