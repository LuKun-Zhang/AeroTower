"""实验步骤 3：冻结计划推演与采样。

用独立 SimulationEngine + sync_frozen，按固定步长推进，产出可回放的状态序列。
不启动引擎线程，不依赖前端时钟。
"""

from ....models.flight_state import FlightPhase
from ...simulation_engine import SimulationEngine
from ..seed import rng_for

STEP_MINUTES = 15


def _sample(engine, minutes, cancelled, delayed, arrived):
    """一次遍历同时产出采样点并累计全程状态。"""
    airborne = parked = cancel_now = 0
    delay_now = 0
    total_delay = 0
    for fs in engine.flights.values():
        fid = str(fs.flight_id)
        if fs.phase == FlightPhase.CANCELLED:
            cancel_now += 1
            cancelled.add(fid)
            continue
        if fs.phase == FlightPhase.PARKED:
            parked += 1
            arrived.add(fid)
        if fs.is_airborne:
            airborne += 1
        if fs.delay_minutes > 0:
            delay_now += 1
            total_delay += fs.delay_minutes
            if fs.delay_minutes > delayed.get(fid, 0):
                delayed[fid] = int(fs.delay_minutes)
    return {
        't': int(minutes),
        'time': engine._min_to_time(minutes),
        'airborne': airborne,
        'arrived': parked,
        'delayed': delay_now,
        'cancelled': cancel_now,
        'avg_delay': round(total_delay / delay_now, 1) if delay_now else 0,
    }


def run(gen, plan, cond):
    engine = SimulationEngine(rng=rng_for(cond['seed'], 'sim'))
    engine.load_flights(gen['flights'])
    start = engine._simulation_start
    end = engine._simulation_end

    series = []
    ever_cancelled = set()
    ever_delayed = {}
    arrived = set()

    t = start
    while t <= end:
        engine.sync_frozen(t, plan, update_kpi=False)
        series.append(_sample(engine, t, ever_cancelled, ever_delayed, arrived))
        t += STEP_MINUTES

    if series and series[-1]['t'] != end:
        engine.sync_frozen(end, plan, update_kpi=False)
        series.append(_sample(engine, end, ever_cancelled, ever_delayed, arrived))

    engine._update_kpi()
    return {
        'series': series,
        'sim_start': start,
        'sim_end': end,
        'step_minutes': STEP_MINUTES,
        'ever_cancelled': sorted(ever_cancelled),
        'ever_delayed': sorted(ever_delayed.items()),
        'arrived': sorted(arrived),
        'engine_kpi': dict(engine.kpi),
    }
