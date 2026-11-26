"""实验指标：全程累计口径 + 时间序列。

命名统一加「全程」前缀，避免与现场仪表盘的瞬时 KPI 同名不同数。
"""

DEFINITIONS = {
    'total_flights': '计划航班数（含调机）',
    'ferry_flights': '调机航班数',
    'on_time_rate': '(总数 - 曾延误 - 取消) / 总数 × 100',
    'completion_rate': '已到达 / (总数 - 取消) × 100',
    'cancelled_count': '全程被取消的航班数',
    'delayed_count': '全程曾出现延误的航班数',
    'avg_delay_min': '延误航班的最终延误分钟均值',
    'aircraft_utilization': '平均飞机利用率（飞行分钟 / 18h）',
    'runway_avg_delay_min': '跑道起降条目的平均延误',
    'gate_avg_utilization': '主基地登机口平均利用率',
    'crew_coverage': '机组已覆盖航班比例',
    'crew_violations': '机组违规项数',
    'total_passengers': '生成旅客总数',
}


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def _gate_utilization(gates):
    values = []
    for row in gates or []:
        stats = row.get('stats') or {}
        if stats.get('used_gates'):
            values.append(stats.get('avg_utilization'))
    return _mean(values)


def aggregate(gen, schedule, weather, sim):
    flights = gen['flights']
    total = len(flights)
    cancelled = len(sim['ever_cancelled'])
    delayed = len(sim['ever_delayed'])
    arrived = len(sim['arrived'])
    delays = [v for _fid, v in sim['ever_delayed']]

    effective = max(total - cancelled, 1)
    values = {
        'total_flights': total,
        'ferry_flights': sum(1 for f in flights if getattr(f, '_is_ferry', False)),
        'on_time_rate': round(max(0.0, (total - delayed - cancelled) / max(total, 1) * 100), 1),
        'completion_rate': round(arrived / effective * 100, 1),
        'cancelled_count': cancelled,
        'delayed_count': delayed,
        'avg_delay_min': _mean(delays) or 0,
        'aircraft_utilization': (schedule.get('aircraft_stats') or {}).get('avg_utilization'),
        'runway_avg_delay_min': ((schedule.get('runway') or {}).get('stats') or {}).get('avg_delay'),
        'gate_avg_utilization': _gate_utilization(schedule.get('gates')),
        'crew_coverage': (schedule.get('crew') or {}).get('coverage'),
        'crew_violations': (schedule.get('crew') or {}).get('violations'),
        'total_passengers': sum(int(getattr(f, '_pax_count', 0) or 0) for f in flights),
    }

    return {
        'values': values,
        'definitions': DEFINITIONS,
        'series': {
            'step_minutes': sim['step_minutes'],
            'points': sim['series'],
        },
        'weather': weather.get('meta', {}),
        'warnings': list(schedule.get('warnings') or []),
    }
