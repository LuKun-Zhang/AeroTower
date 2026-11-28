"""实验条件：默认值、校验、规范化与客流解析。"""

import json

from ...models.experiment import ExperimentError
from ..flight_generator import DEFAULT_TRAFFIC
from ..flight_filter import SICHUAN_BASES
from .seed import stable_hash

ALLOWED_DATES = [
    '2020-11-30', '2020-12-01', '2020-12-02',
    '2020-12-03', '2020-12-04', '2020-12-05',
]
ALLOWED_BASES = sorted(SICHUAN_BASES)

ALGORITHM_CHOICES = {
    'routing': ['chain_coverage', 'bipartite', 'greedy', 'vrp'],
    'runway': ['multi_runway', 'optimized'],
    'gate': ['bipartite', 'greedy'],
    'crew': ['chain', 'pairing'],
}
DEFAULT_ALGORITHMS = {
    'routing': 'chain_coverage',
    'runway': 'multi_runway',
    'gate': 'bipartite',
    'crew': 'chain',
}

WEATHER_SCENARIOS = ['none', 'sichuan_storm', 'east_rain', 'south_typhoon']
ANOMALY_CHOICES = ['none', 'airport_closure']
DEFAULT_FLEET_MIX = {'A319': 10, 'A320': 50, 'A321': 40}

MAX_PASTED_FLOWS = 2000


def _as_int(value, field, low, high):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ExperimentError(field, '必须是整数')
    if n < low or n > high:
        raise ExperimentError(field, f'必须在 {low}~{high} 之间')
    return n


def _as_float(value, field, low, high):
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ExperimentError(field, '必须是数字')
    if n < low or n > high:
        raise ExperimentError(field, f'必须在 {low}~{high} 之间')
    return round(n, 4)


def _normalize_dates(raw):
    if not isinstance(raw, list) or not raw:
        raise ExperimentError('dates', '至少选择一个日期')
    dates = []
    for d in raw:
        if d not in ALLOWED_DATES:
            raise ExperimentError('dates', f'不支持的日期: {d}')
        if d not in dates:
            dates.append(d)
    return sorted(dates)


def _normalize_bases(raw):
    if not isinstance(raw, list) or not raw:
        raise ExperimentError('bases', '至少选择一个基地')
    bases = []
    for b in raw:
        if b not in ALLOWED_BASES:
            raise ExperimentError('bases', f'不支持的基地: {b}')
        if b not in bases:
            bases.append(b)
    return sorted(bases)


def _default_mix(size):
    total = sum(DEFAULT_FLEET_MIX.values())
    mix = {k: int(round(size * v / total)) for k, v in DEFAULT_FLEET_MIX.items()}
    diff = size - sum(mix.values())
    mix['A320'] += diff
    return mix


def _normalize_fleet(raw):
    raw = raw or {}
    size = _as_int(raw.get('size', 100), 'fleet.size', 10, 200)
    mix_raw = raw.get('mix')
    if not mix_raw:
        mix = _default_mix(size)
    else:
        mix = {}
        for ac_type in ('A319', 'A320', 'A321'):
            mix[ac_type] = _as_int(mix_raw.get(ac_type, 0), f'fleet.mix.{ac_type}', 0, size)
        if sum(mix.values()) != size:
            raise ExperimentError('fleet.mix', f'机型合计必须等于机队规模 {size}')
    return {'size': size, 'mix': mix}


def _normalize_pasted(raw):
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ExperimentError('traffic.pasted', '必须是城市对列表')
    if len(raw) > MAX_PASTED_FLOWS:
        raise ExperimentError('traffic.pasted', f'最多 {MAX_PASTED_FLOWS} 条')
    flows = []
    for i, item in enumerate(raw):
        origin = str((item or {}).get('origin', '')).strip()
        dest = str((item or {}).get('destination', '')).strip()
        if not origin or not dest or origin == dest:
            raise ExperimentError(f'traffic.pasted[{i}]', '起降城市不能为空且不能相同')
        pax = _as_int((item or {}).get('daily_pax', 0), f'traffic.pasted[{i}].daily_pax', 0, 100000)
        if pax > 0:
            flows.append({'origin': origin, 'destination': dest, 'daily_pax': pax})
    return flows


def resolve_city_traffic(cond):
    """把条件中的客流解析成生成器要的 city_traffic 列表。"""
    traffic = cond.get('traffic', {})
    pasted = traffic.get('city_traffic')
    if pasted:
        return [dict(f) for f in pasted]
    scale = float(traffic.get('scale', 1.0))
    return [
        {
            'origin': f['origin'],
            'destination': f['destination'],
            'daily_pax': max(0, int(round(f['daily_pax'] * scale))),
        }
        for f in DEFAULT_TRAFFIC
        if int(round(f['daily_pax'] * scale)) > 0
    ]


def normalize(raw):
    """校验并返回规范化条件；字段错误抛 ExperimentError。"""
    raw = raw or {}

    name = str(raw.get('name') or '').strip()
    if not name:
        raise ExperimentError('name', '请填写实验名称')
    if len(name) > 60:
        raise ExperimentError('name', '实验名称不超过 60 个字符')

    dates = _normalize_dates(raw.get('dates'))
    bases = _normalize_bases(raw.get('bases'))
    fleet = _normalize_fleet(raw.get('fleet'))

    traffic_raw = raw.get('traffic') or {}
    pasted = _normalize_pasted(traffic_raw.get('pasted'))
    if not pasted and traffic_raw.get('city_traffic'):
        # 已规范化的条件再次进入（运行/重跑）：沿用快照里的客流
        pasted = _normalize_pasted(traffic_raw.get('city_traffic'))
    scale = _as_float(traffic_raw.get('scale', 1.0), 'traffic.scale', 0.1, 3.0)

    algorithms = {}
    for key, choices in ALGORITHM_CHOICES.items():
        value = (raw.get('algorithms') or {}).get(key, DEFAULT_ALGORITHMS[key])
        if value not in choices:
            raise ExperimentError(f'algorithms.{key}', f'不支持的算法: {value}')
        algorithms[key] = value

    disruption_raw = raw.get('disruption') or {}
    weather = disruption_raw.get('weather', 'none')
    if weather not in WEATHER_SCENARIOS:
        raise ExperimentError('disruption.weather', f'不支持的天气情景: {weather}')
    anomaly = disruption_raw.get('anomaly', 'none')
    if anomaly not in ANOMALY_CHOICES:
        raise ExperimentError('disruption.anomaly', f'不支持的异常情景: {anomaly}')
    anomaly_params = disruption_raw.get('anomaly_params') or {}
    if anomaly == 'airport_closure':
        airport = str(anomaly_params.get('airport') or '').strip()
        if not airport:
            raise ExperimentError('disruption.anomaly_params.airport', '请选择关闭机场')
        start = str(anomaly_params.get('start') or '').strip()
        end = str(anomaly_params.get('end') or '').strip()
        if not start or not end or start >= end:
            raise ExperimentError('disruption.anomaly_params', '关闭起止时刻不合法')
        anomaly_params = {'airport': airport, 'start': start, 'end': end}

    load_factor = _as_float(raw.get('load_factor', 0.78), 'load_factor', 0.3, 1.0)
    min_turnaround = _as_int(raw.get('min_turnaround', 60), 'min_turnaround', 20, 180)
    max_segments = _as_int(raw.get('max_segments_per_day', 5), 'max_segments_per_day', 1, 8)
    seed = _as_int(raw.get('seed', 0), 'seed', 0, 999999)

    city_traffic = pasted if pasted else resolve_city_traffic({
        'traffic': {'scale': scale},
    })
    if not city_traffic:
        raise ExperimentError('traffic', '客流为空，请填写或调整缩放')

    hub = '成都' if '成都' in bases else bases[0]

    return {
        'name': name,
        'dates': dates,
        'bases': bases,
        'hub': hub,
        'traffic': {
            'template': traffic_raw.get('template') or ('custom' if pasted else 'demo'),
            'scale': scale,
            'city_traffic': city_traffic,
        },
        'fleet': fleet,
        'load_factor': load_factor,
        'min_turnaround': min_turnaround,
        'max_segments_per_day': max_segments,
        'algorithms': algorithms,
        'disruption': {'weather': weather, 'anomaly': anomaly,
                       'anomaly_params': anomaly_params},
        'seed': seed,
    }


def digest(cond):
    """条件指纹：用于列表展示与复现核对（不含名称与种子）。"""
    payload = {k: v for k, v in cond.items() if k not in ('name', 'seed')}
    return stable_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False), 10 ** 9)


def total_daily_pax(cond):
    return sum(int(f.get('daily_pax', 0)) for f in cond.get('traffic', {}).get('city_traffic', []))
