"""实验运行编排：后台线程、单并发、阶段进度与状态持久化。"""

import threading
import time
import traceback
from datetime import datetime

from ...models.experiment import (
    STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED, STATUS_INTERRUPTED,
)
from ...utils.city_geo import build_transit_cache_from_flights
from . import store, artifacts, conditions, metrics, weather_program
from .paxflow_builder import build_paxflow_schedule
from .steps import generate, schedule, simulate

_LOCK = threading.Lock()
_RUNS = {}
_STAGE_WEIGHTS = [
    ('校验条件', 1),
    ('生成航班计划', 50),
    ('构建任务链', 4),
    ('飞机排班', 4),
    ('跑道调度', 4),
    ('登机口分配', 5),
    ('机组排班', 10),
    ('编译中断计划', 5),
    ('冻结计划推演', 12),
    ('汇总指标与落盘', 5),
]


class BusyError(RuntimeError):
    pass


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _set_progress(record, pct, stage, message=''):
    record.progress = {'pct': int(pct), 'stage': stage, 'message': message}
    store.save(record)


def active_run():
    for exp_id, state in _RUNS.items():
        if state.get('status') == STATUS_RUNNING:
            return exp_id
    return None


def start(username, exp_id):
    """启动一次运行；已有运行中实验则抛 BusyError。"""
    if not _LOCK.acquire(blocking=False):
        raise BusyError('已有实验在运行，请等待完成')
    try:
        record = store.load(username, exp_id)
        if not record:
            raise ValueError('实验不存在')
        if record.status == STATUS_RUNNING:
            raise BusyError('该实验正在运行')
        record.status = STATUS_RUNNING
        record.started_at = _now()
        record.finished_at = ''
        record.error = None
        record.warnings = []
        record.progress = {'pct': 1, 'stage': '校验条件', 'message': ''}
        store.save(record)
        _RUNS[exp_id] = {'status': STATUS_RUNNING, 'pct': 1,
                         'stage': '校验条件', 'message': '', 'started': time.time()}
    except Exception:
        _LOCK.release()
        raise

    thread = threading.Thread(target=_execute, args=(username, exp_id), daemon=True)
    thread.start()
    return exp_id


def _execute(username, exp_id):
    started = time.time()
    stage = '校验条件'
    record = store.load(username, exp_id)
    durations = {}
    try:
        cond = conditions.normalize(record.conditions)
        _advance(exp_id, record, 1, stage)

        stage = '生成航班计划'
        t0 = time.time()
        gen = generate.run(cond)
        durations[stage] = round(time.time() - t0, 2)
        _advance(exp_id, record, 51, stage)

        stage = '构建任务链'
        t0 = time.time()
        if not gen['flights']:
            raise ValueError('生成结果为空，请检查客流与基地')
        durations[stage] = round(time.time() - t0, 2)
        _advance(exp_id, record, 55, stage)

        schedule_data = schedule.run(gen, cond)
        _advance(exp_id, record, 78, '机组排班')

        stage = '编译中断计划'
        t0 = time.time()
        aircraft_map = {
            f.flight_id: ac.tail_no
            for ac in schedule_data['aircraft'] for f in ac.assigned_flights
        }
        transit_cache = build_transit_cache_from_flights(gen['flights'])
        weather = weather_program.compile_plan(
            cond, gen['flights'], aircraft_map=aircraft_map,
            chains=gen['chains'], transit_cache=transit_cache,
        )
        durations[stage] = round(time.time() - t0, 2)
        _advance(exp_id, record, 83, stage)

        stage = '冻结计划推演'
        t0 = time.time()
        sim = simulate.run(gen, weather['plan'], cond)
        durations[stage] = round(time.time() - t0, 2)
        _advance(exp_id, record, 95, stage)

        stage = '汇总指标与落盘'
        t0 = time.time()
        result = metrics.aggregate(gen, schedule_data, weather, sim)
        paxflow = _build_paxflow(gen, schedule_data, weather, cond)
        replay = {
            'sim_start': sim['sim_start'],
            'sim_end': sim['sim_end'],
            'step_minutes': sim['step_minutes'],
            'airport': cond['hub'],
            'dates': cond['dates'],
            'has_paxflow': bool(paxflow.get('dates')),
        }
        payload = {
            'flights': [artifacts.serialize_flight(f) for f in gen['flights']],
            'schedule': {
                'aircraft': artifacts.serialize_aircraft(schedule_data['aircraft']),
                'aircraft_stats': schedule_data['aircraft_stats'],
                'runway': artifacts.serialize_runway(
                    schedule_data['runway']['items'], schedule_data['runway']['stats']),
                'gates': artifacts.serialize_gates(schedule_data['gates']),
                'crew': artifacts.serialize_crew(schedule_data['crew']),
            },
            'weather': weather,
            'metrics': result,
            'paxflow': paxflow,
            'run': {'stage_seconds': durations, 'warnings': result['warnings']},
        }
        artifacts.write_bundle(username, exp_id, payload)
        durations[stage] = round(time.time() - t0, 2)

        record.status = STATUS_SUCCEEDED
        record.finished_at = _now()
        record.duration_sec = round(time.time() - started, 1)
        record.summary = result['values']
        record.warnings = result['warnings']
        record.replay = replay
        record.progress = {'pct': 100, 'stage': '完成', 'message': ''}
        store.save(record)
        _RUNS[exp_id] = {'status': STATUS_SUCCEEDED, 'pct': 100,
                         'stage': '完成', 'message': '', 'elapsed': record.duration_sec}
    except Exception as exc:
        record.status = STATUS_FAILED
        record.finished_at = _now()
        record.duration_sec = round(time.time() - started, 1)
        record.error = {
            'stage': stage,
            'message': str(exc),
            'traceback': traceback.format_exc()[-2000:],
        }
        record.progress = {'pct': record.progress.get('pct', 0), 'stage': stage,
                           'message': str(exc)}
        store.save(record)
        _RUNS[exp_id] = {'status': STATUS_FAILED, 'pct': record.progress['pct'],
                         'stage': stage, 'message': str(exc)}
    finally:
        _LOCK.release()


def _advance(exp_id, record, pct, stage):
    _set_progress(record, pct, stage)
    _RUNS[exp_id] = {'status': STATUS_RUNNING, 'pct': pct, 'stage': stage,
                     'message': '', 'elapsed': record.duration_sec}


def _build_paxflow(gen, schedule_data, weather, cond):
    gate_map = {}
    for row in schedule_data['gates']:
        for item in row.get('assignments') or []:
            gate_map[item['flight_id']] = {
                'gate': item.get('gate'),
                'runway_group': item.get('runway', 1),
            }
    tail_map = {
        f.flight_id: ac.tail_no
        for ac in schedule_data['aircraft'] for f in ac.assigned_flights
    }
    paxflow = build_paxflow_schedule(
        gen['flights'], airport=cond['hub'],
        runway_schedule=schedule_data['runway']['items'],
        gate_map=gate_map, tail_map=tail_map, plan=weather['plan'],
        dates_filter=cond['dates'],
    )
    paxflow.pop('flights', None)
    return paxflow


def get_progress(record):
    """读取进度；若进程重启导致 running 悬挂，转为 interrupted。"""
    state = _RUNS.get(record.id)
    if state and state.get('status') == STATUS_RUNNING:
        return state
    if record.status == STATUS_RUNNING:
        record.status = STATUS_INTERRUPTED
        record.error = {'stage': record.progress.get('stage', ''),
                        'message': '服务重启，运行中断', 'traceback': ''}
        store.save(record)
        return {'status': STATUS_INTERRUPTED, 'pct': record.progress.get('pct', 0),
                'stage': record.progress.get('stage', ''), 'message': '服务重启，运行中断'}
    return {
        'status': record.status,
        'pct': 100 if record.status == STATUS_SUCCEEDED else record.progress.get('pct', 0),
        'stage': '完成' if record.status == STATUS_SUCCEEDED else record.progress.get('stage', ''),
        'message': '',
        'elapsed': record.duration_sec,
    }


def rerun(username, exp_id):
    old = store.load(username, exp_id)
    if not old:
        raise ValueError('实验不存在')
    record = store.create(username, old.conditions, name=old.name + ' · 重跑',
                          parent_id=old.id)
    start(username, record.id)
    return record
