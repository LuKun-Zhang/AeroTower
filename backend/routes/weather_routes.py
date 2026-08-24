"""天气中断联动 API — /api/weather/* 路由"""

from flask import Blueprint, request, jsonify

from ..state import (
    get_province_weather, set_province_weather,
    get_weather_disruption_plan, set_weather_disruption_plan,
    get_active_flights, get_active_chains,
    get_transit_cache, get_flight_aircraft_cache,
    get_generated_data,
)
from ..services.weather_disruption_service import compute_disruption

weather_bp = Blueprint('weather', __name__)


def _ok(data=None, msg="ok"):
    return jsonify({'code': 0, 'data': data, 'msg': msg})


def _err(msg, status=400):
    return jsonify({'code': -1, 'msg': msg}), status


def _gather_flights():
    """获取用于中断计算的航班对象列表（优先当前活跃航班）。"""
    flights = get_active_flights()
    if flights:
        return list(flights)
    # 兜底：数据服务中的航班（保证无坏天气回归时也能有航班上下文）
    from .schedule_routes import _get_active_flights
    try:
        return list(_get_active_flights())
    except Exception:
        return []


def _gather_chains():
    chains = get_active_chains()
    if chains:
        return list(chains)
    from .schedule_routes import _get_aircraft_routing
    try:
        return list(_get_aircraft_routing())
    except Exception:
        return []


def _gather_aircraft_map():
    cache = get_flight_aircraft_cache()
    if cache:
        return dict(cache)
    from .schedule_routes import _get_flight_aircraft_map
    try:
        return dict(_get_flight_aircraft_map())
    except Exception:
        return {}


@weather_bp.route('/weather/stream', methods=['POST'])
def weather_stream():
    """前端天气页每 2s 自动回传各省天气 + 气旋推演时间线。

    后端自动重算中断计划并写回共享 state，供模拟引擎 / 旅客流消费。
    """
    body = request.get_json(silent=True) or {}
    province_weather = body.get('province_weather') or {}
    timeline = body.get('timeline') or {}
    clock = body.get('clock') or ''

    set_province_weather(dict(province_weather))

    flights = _gather_flights()
    if not flights:
        # 没有航班数据也保存空计划，避免残留旧计划
        set_weather_disruption_plan({})
        return _ok({
            'affected_provinces': [],
            'affected_airports': [],
            'direct_count': 0,
            'transit_count': 0,
            'delay_count': 0,
            'cancel_count': 0,
            'plan_size': 0,
            'window': None,
        }, "无航班数据，未计算中断")

    chains = _gather_chains()
    aircraft_map = _gather_aircraft_map()
    transit_cache = dict(get_transit_cache() or {})

    plan, meta = compute_disruption(
        province_weather, timeline, flights,
        aircraft_map=aircraft_map, chains=chains,
        transit_cache=transit_cache, clock=clock,
    )
    set_weather_disruption_plan(plan)

    return _ok(meta, "天气中断计划已更新")


@weather_bp.route('/weather/disruption', methods=['GET'])
def weather_disruption():
    """读取当前天气中断计划（供三页回显 / 调试）。"""
    plan = get_weather_disruption_plan()
    return _ok({
        'province_weather': get_province_weather(),
        'plan': plan,
        'plan_size': len(plan),
    })
