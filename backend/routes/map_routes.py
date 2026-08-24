"""地图 API 路由 — /api/map/*"""
import traceback
from collections import defaultdict
from flask import Blueprint, jsonify, request

from ..state import (
    get_active_flights,
    get_active_chains,
    get_filtered_mode,
    get_flight_aircraft_cache,
    set_flight_aircraft_cache,
    get_aircraft_chains_cache,
    set_aircraft_chains_cache,
    get_excluded_aircraft,
    set_transit_cache,
)

from ..services.data_service import data_service
from ..services import routing_service
from ..services.map_schedule_store import (
    save_schedule, get_schedule, get_all_dates,
    build_map_timeslices, build_multi_day_timeslices, ICAO_TO_CITY,
)
from ..services.flight_filter import SICHUAN_BASES
from ..utils.city_geo import build_transit_cache_from_flights

map_bp = Blueprint('map', __name__)


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


def _normalize_flight_times(flights):
    """将航班列表中所有 6 元组时间规范化为 5 元组"""
    for f in flights:
        for attr in ('time_departure', 'time_arrival'):
            t = getattr(f, attr, None)
            if isinstance(t, (tuple, list)) and len(t) > 5:
                setattr(f, attr, tuple(t[:5]))


def _get_active_flights():
    """获取当前活跃航班，优先使用筛选后的数据"""
    if get_filtered_mode() and get_active_flights():
        flights = get_active_flights()
        _normalize_flight_times(flights)
        return list(flights)
    data_service.load_all()
    return list(data_service.flights)


def _get_active_chains():
    """获取当前活跃任务链（Flight对象列表）"""
    if get_filtered_mode() and get_active_chains():
        chains = get_active_chains()
        for chain in chains:
            _normalize_flight_times(chain)
        return chains
    return None


def _rebuild_transit_cache():
    """根据当前活跃航班重建航线途经省份缓存"""
    flights = _get_active_flights()
    if not flights:
        set_transit_cache({})
        return
    cache = build_transit_cache_from_flights(list(flights))
    set_transit_cache(cache)
    print(f"[TransitCache] 已为 {len(cache)} 条航线构建途经缓存")


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
        set_aircraft_chains_cache([list(ac.assigned_flights) for ac in result if ac.assigned_flights])
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
        num_ac = max(100 - len(excluded), 5)
        result = routing_service.solve_chain_coverage(
            chains, num_ac, excluded_aircraft=excluded if excluded else None)
        set_aircraft_chains_cache([list(ac.assigned_flights) for ac in result if ac.assigned_flights])
        return get_aircraft_chains_cache()

    # 非筛选模式：二分图
    result = routing_service.solve_bipartite(_get_active_flights(), 60)
    set_aircraft_chains_cache([list(ac.assigned_flights) for ac in result if ac.assigned_flights])
    return get_aircraft_chains_cache()


@map_bp.route('/stats', methods=['GET'])
@safe_handler
def get_map_stats():
    """地图统计页面数据：基于_active_flights生成所有统计图表数据"""
    if not get_filtered_mode() or not get_active_flights():
        return jsonify({'code': 1, 'msg': '请先在航班筛选页上传并保存筛选结果'})

    date = request.args.get('date', '')

    flights = list(get_active_flights())
    if date:
        date_mmdd = date[-5:] if len(date) >= 5 else date
        filtered = []
        for f in flights:
            td = f.time_departure
            fd = f"{td[1]:02d}-{td[2]:02d}"
            if fd == date_mmdd:
                filtered.append(f)
        flights = filtered
        if not flights:
            return jsonify({'code': 1, 'msg': f'{date} 没有航班数据'})

    # 1. 飞机执飞统计
    aircraft_map = {}
    try:
        aircraft_map = _get_flight_aircraft_map()
    except Exception:
        pass
    if aircraft_map:
        ac_counts = {}
        for f in flights:
            tail = aircraft_map.get(f.flight_id, f.flight_no[:3])
            ac_counts[tail] = ac_counts.get(tail, 0) + 1
        aircraft_stats = sorted(
            [{'name': k, 'value': v} for k, v in ac_counts.items()],
            key=lambda x: -x['value']
        )
    else:
        prefix_counts = {}
        for f in flights:
            pf = f.flight_no[:4]
            prefix_counts[pf] = prefix_counts.get(pf, 0) + 1
        aircraft_stats = sorted(
            [{'name': k, 'value': v} for k, v in prefix_counts.items()],
            key=lambda x: -x['value']
        )

    # 2. 24h 热力图
    heatmap_raw = defaultdict(int)
    day_labels_set = set()
    for f in flights:
        parts = f.time_departure
        y, m, d, h, mi = parts[0], parts[1], parts[2], parts[3], parts[4]
        day_label = f"{m:02d}-{d:02d}"
        day_labels_set.add(day_label)
        heatmap_raw[(day_label, h)] += 1

    day_labels = sorted(day_labels_set)
    hours_list = list(range(24))
    heatmap_data = []
    hour_labels = [f"{h}:00" for h in hours_list]
    for di, dl in enumerate(day_labels):
        for hi, h in enumerate(hours_list):
            v = heatmap_raw.get((dl, h), 0)
            heatmap_data.append([hi, di, v])

    # 3. 基地统计
    base_set = set(SICHUAN_BASES)
    base_dep = defaultdict(int)
    base_arr = defaultdict(int)
    for f in flights:
        if f.departure_airport in base_set:
            base_dep[f.departure_airport] += 1
        if f.arrival_airport in base_set:
            base_arr[f.arrival_airport] += 1

    all_bases = set(list(base_dep.keys()) + list(base_arr.keys()))
    base_stats = []
    for b in all_bases:
        name = ICAO_TO_CITY.get(b, b)
        base_stats.append({
            'code': b,
            'name': name,
            'dep': base_dep.get(b, 0),
            'arr': base_arr.get(b, 0),
        })

    return jsonify({
        'code': 0,
        'data': {
            'aircraft_stats': aircraft_stats,
            'heatmap': {
                'day_labels': day_labels,
                'hour_labels': hour_labels,
                'data': heatmap_data,
            },
            'base_stats': base_stats,
            'total_flights': len(flights),
        },
    })
