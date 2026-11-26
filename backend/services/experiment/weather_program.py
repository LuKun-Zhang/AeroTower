"""实验气象情景：把预设情景编译成冻结的中断计划。

现场模式由前端天气页每 2 秒回传省份天气，后端 ``compute_disruption`` 以“当前”
为 t=0 重算。实验是离线批处理，因此这里把情景拆成“省份 × 连续窗口”，
逐窗口调用同一个 ``compute_disruption``，再合并成一份冻结计划。
"""

from datetime import datetime, timedelta

from ..weather_disruption_service import compute_disruption
from ...utils import city_geo

STEP_MIN = 30
TIME_FMT = '%Y-%m-%d %H:%M'

SCENARIOS = {
    'sichuan_storm': {
        'label': '四川盆地雷暴',
        'blocks': [
            {'provinces': ['四川', '重庆'], 'date_index': 0,
             'start': '14:00', 'end': '18:00', 'weather': 'thunderstorm'},
        ],
    },
    'east_rain': {
        'label': '华东强降雨',
        'blocks': [
            {'provinces': ['上海', '江苏', '浙江'], 'date_index': 1,
             'start': '08:00', 'end': '14:00', 'weather': 'rain_heavy'},
        ],
    },
    'south_typhoon': {
        'label': '华南台风',
        'blocks': [
            {'provinces': ['广东', '海南', '福建', '广西'], 'date_index': 1,
             'start': '00:00', 'end': '23:30', 'weather': 'thunderstorm'},
        ],
    },
}


def _parse_dt(text):
    return datetime.strptime(text, TIME_FMT)


def _block_times(cond, block):
    dates = cond.get('dates') or []
    idx = min(block.get('date_index', 0), len(dates) - 1)
    date_str = dates[idx]
    start = _parse_dt(f"{date_str} {block['start']}")
    end = _parse_dt(f"{date_str} {block['end']}")
    return date_str, start, end


def _series(start, end, weather_type, step_min=STEP_MIN):
    points = []
    cur = start
    t = 0
    while cur <= end:
        points.append({'t': t, 'time': cur.strftime(TIME_FMT), 'type': weather_type})
        cur += timedelta(minutes=step_min)
        t += step_min
    return points


def _abs_minutes(dt):
    """与 SimulationEngine._time_to_min 一致的绝对业务分钟。"""
    return (dt.month - 11) * 30 * 1440 + (dt.day - 1) * 1440 + dt.hour * 60 + dt.minute


def _merge_plan(target, source):
    for fid, item in (source or {}).items():
        old = target.get(fid)
        if not old:
            target[fid] = dict(item)
            continue
        if old.get('type') == 'cancel' or item.get('type') == 'cancel':
            target[fid] = dict(item if item.get('type') == 'cancel' else old)
            target[fid]['type'] = 'cancel'
            continue
        if int(item.get('delay_minutes', 0)) > int(old.get('delay_minutes', 0)):
            target[fid] = dict(item)


def _flight_dt(f, arrival=False):
    t = f.time_arrival if arrival else f.time_departure
    try:
        return datetime(int(t[0]), int(t[1]), int(t[2]), int(t[3]), int(t[4]))
    except Exception:
        return None


def _compile_closure(params, flights):
    airport = params.get('airport', '')
    try:
        start = _parse_dt(params.get('start', ''))
        end = _parse_dt(params.get('end', ''))
    except Exception:
        return {}, []
    if not airport or end <= start:
        return {}, []

    plan = {}
    apply_from = _abs_minutes(start)
    for f in flights:
        if f.departure_airport == airport:
            dt = _flight_dt(f)
            if dt and start <= dt <= end:
                plan[str(f.flight_id)] = {
                    'type': 'cancel',
                    'delay_minutes': 0,
                    'reason': f'{airport}临时关闭，航班取消',
                    'affected_by': 'direct',
                    'apply_from': apply_from,
                }
        elif f.arrival_airport == airport:
            dt = _flight_dt(f, arrival=True)
            if dt and start <= dt <= end:
                delay = int((end - dt).total_seconds() // 60) + 30
                plan[str(f.flight_id)] = {
                    'type': 'delay',
                    'delay_minutes': max(30, delay),
                    'reason': f'{airport}临时关闭，航班顺延',
                    'affected_by': 'direct',
                    'apply_from': apply_from,
                }
    block = {
        'kind': 'airport_closure',
        'airport': airport,
        'start': start.strftime(TIME_FMT),
        'end': end.strftime(TIME_FMT),
    }
    return plan, [block]


def compile_plan(cond, flights, aircraft_map=None, chains=None, transit_cache=None):
    """返回 {scenario, anomaly, blocks, timeline, plan, meta}。"""
    disruption = cond.get('disruption') or {}
    weather = disruption.get('weather', 'none')
    anomaly = disruption.get('anomaly', 'none')

    plan = {}
    timeline = {}
    blocks = []
    provinces = set()

    if weather in SCENARIOS:
        for block in SCENARIOS[weather]['blocks']:
            date_str, start, end = _block_times(cond, block)
            series = _series(start, end, block['weather'])
            for prov in block['provinces']:
                timeline[prov] = list(series)
                provinces.add(prov)
            province_weather = {p: block['weather'] for p in block['provinces']}
            sub_timeline = {p: list(series) for p in block['provinces']}
            sub_plan, _meta = compute_disruption(
                province_weather, sub_timeline, flights,
                aircraft_map=aircraft_map or {}, chains=chains or [],
                transit_cache=transit_cache or {},
                clock=start.strftime(TIME_FMT),
            )
            apply_from = _abs_minutes(start)
            for item in sub_plan.values():
                item['apply_from'] = apply_from
            _merge_plan(plan, sub_plan)
            blocks.append({
                'kind': 'weather',
                'date': date_str,
                'start': start.strftime(TIME_FMT),
                'end': end.strftime(TIME_FMT),
                'provinces': list(block['provinces']),
                'weather': block['weather'],
            })

    if anomaly == 'airport_closure':
        closure_plan, closure_blocks = _compile_closure(
            (disruption.get('anomaly_params') or {}), flights)
        _merge_plan(plan, closure_plan)
        blocks.extend(closure_blocks)

    delay_count = sum(1 for v in plan.values() if v.get('type') == 'delay')
    cancel_count = sum(1 for v in plan.values() if v.get('type') == 'cancel')
    meta = {
        'scenario': weather,
        'anomaly': anomaly,
        'affected_provinces': sorted(provinces),
        'delay_count': delay_count,
        'cancel_count': cancel_count,
        'plan_size': len(plan),
        'window': {
            'start': blocks[0]['start'] if blocks else '',
            'end': blocks[-1]['end'] if blocks else '',
        },
    }
    return {
        'scenario': weather,
        'anomaly': anomaly,
        'label': SCENARIOS.get(weather, {}).get('label', '无'),
        'blocks': blocks,
        'timeline': timeline,
        'plan': plan,
        'meta': meta,
    }


def province_weather_at(weather_artifact, abs_minutes):
    """回放用：给定绝对业务分钟（自 2020-11-01 00:00 起算），返回此刻的 {省: 天气类型}。"""
    if not weather_artifact:
        return {}
    target = int(abs_minutes)
    epoch = _parse_dt('2020-11-01 00:00')
    result = {}
    for prov, points in (weather_artifact.get('timeline') or {}).items():
        hit = None
        for p in points:
            try:
                ts = int((_parse_dt(p['time']) - epoch).total_seconds() // 60)
            except Exception:
                continue
            if ts <= target:
                hit = p.get('type')
            else:
                break
        if hit:
            result[prov] = hit
    return result


def airports_for_provinces(provinces):
    """省份 → 机场列表（复用城市地理映射）。"""
    if not provinces:
        return []
    try:
        return city_geo.get_province_airports(set(provinces))
    except Exception:
        return []
