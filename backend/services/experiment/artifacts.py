"""实验工件序列化：航班、排班、旅客流、指标与运行日志。"""

import os

from .store import write_json, read_json, artifact_path


def serialize_flight(f):
    return {
        'flight_id': f.flight_id,
        'flight_no': f.flight_no,
        'ac_type': f.ac_type,
        'layout': f.layout,
        'departure_airport': f.departure_airport,
        'arrival_airport': f.arrival_airport,
        'time_departure': list(f.time_departure),
        'time_arrival': list(f.time_arrival),
        'timespan': int(getattr(f, 'timespan', 0) or 0),
        'cost': float(getattr(f, 'cost', 0) or 0),
        'pax_count': int(getattr(f, '_pax_count', 0) or 0),
        'is_ferry': bool(getattr(f, '_is_ferry', False)),
    }


def serialize_aircraft(aircrafts):
    rows = []
    for ac in aircrafts or []:
        rows.append({
            'tail_no': getattr(ac, 'tail_no', ''),
            'ac_type': getattr(ac, 'ac_type', ''),
            'base': getattr(ac, 'base', ''),
            'flights': [f.flight_id for f in getattr(ac, 'assigned_flights', [])],
        })
    return rows


def serialize_runway(items, stats):
    compact = []
    for item in items or []:
        compact.append({
            'flight_id': item.get('flight_id'),
            'flight_no': item.get('flight_no', ''),
            'airport': item.get('airport', ''),
            'date': item.get('date', ''),
            'type': item.get('type', ''),
            'runway': item.get('runway', 1),
            'target_time': item.get('target_time', 0),
            'actual_time': item.get('actual_time', 0),
            'end_time': item.get('end_time', 0),
            'delay': item.get('delay', 0),
        })
    return {'stats': stats or {}, 'items': compact}


def serialize_gates(per_day):
    return per_day or []


def serialize_crew(report):
    return report or {}


def write_bundle(username, exp_id, payload):
    """按分片写入工件，单文件失败不影响其它分片。"""
    mapping = {
        'flights.json': payload.get('flights', []),
        'schedule.json': payload.get('schedule', {}),
        'weather.json': payload.get('weather', {}),
        'metrics.json': payload.get('metrics', {}),
        'paxflow.json': payload.get('paxflow', {}),
        'run.json': payload.get('run', {}),
    }
    written = {}
    for name, data in mapping.items():
        path = artifact_path(username, exp_id, name)
        write_json(path, data)
        written[name] = os.path.getsize(path)
    return written


def read_artifact(username, exp_id, name, default=None):
    return read_json(artifact_path(username, exp_id, name), default)
