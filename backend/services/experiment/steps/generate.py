"""实验步骤 1：客流量 → 航班计划 + 任务链。"""

import re

from ....models.flight import Flight
from ...flight_generator import FlightGenerator


def _parse_time(value):
    if isinstance(value, (tuple, list)):
        return tuple(int(x) for x in value[:5])
    parts = re.split(r'[-:\s]+', str(value).strip())
    if len(parts) >= 5:
        try:
            return tuple(int(x) for x in parts[:5])
        except ValueError:
            pass
    return (2020, 11, 30, 0, 0)


def _to_flight(data):
    f = Flight(
        flight_id=data.get('flight_id', 0),
        flight_no=data.get('flight_no', ''),
        ac_type=data.get('ac_type', 'A319'),
        layout=data.get('layout', 'C8Y124'),
        departure_airport=data.get('departure_airport', ''),
        arrival_airport=data.get('arrival_airport', ''),
        time_departure=_parse_time(data.get('time_departure')),
        time_arrival=_parse_time(data.get('time_arrival')),
        timespan=int(data.get('timespan', 0) or 0),
        cost=float(data.get('cost', 0) or 0),
    )
    f._is_ferry = bool(data.get('is_ferry', False))
    if data.get('pax_count'):
        f._pax_count = int(data['pax_count'])
    elif data.get('passenger_manifest'):
        f._pax_count = sum(1 for v in data['passenger_manifest'].values() if v)
    else:
        f._pax_count = 0
    return f


def run(cond):
    """执行生成；返回航班对象、任务链与统计。"""
    payload = {
        'bases': cond['bases'],
        'dates': cond['dates'],
        'hub': cond.get('hub'),
        'fleet_mix': [(k, v) for k, v in cond['fleet']['mix'].items()],
        'num_aircraft': cond['fleet']['size'],
        'load_factor': cond['load_factor'],
        'min_turnaround': cond['min_turnaround'],
        'max_segments_per_day': cond['max_segments_per_day'],
        'city_traffic': cond['traffic']['city_traffic'],
    }
    result = FlightGenerator(payload).generate()

    flights = []
    for data in result.get('flights', []):
        f = _to_flight(data)
        # 释放生成器里的大字段，避免 10 万级旅客明细常驻内存
        data.pop('pax_list', None)
        data.pop('passenger_manifest', None)
        flights.append(f)

    by_id = {f.flight_id: f for f in flights}
    chains = []
    for chain_data in result.get('chains', []):
        chain = [by_id[fid] for fid in chain_data.get('flights', []) if fid in by_id]
        if chain:
            chains.append(chain)

    stats = dict(result.get('stats', {}))
    stats['built_chains'] = len(chains)
    stats['built_flights'] = len(flights)
    return {
        'flights': flights,
        'chains': chains,
        'stats': stats,
        'skipped_flows': result.get('skipped_flows', []),
    }
