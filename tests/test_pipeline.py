"""流水线复现、回放一致性与现场隔离。"""

import json
import shutil
import time
import unittest

from backend import state
from backend.models.flight_state import FlightPhase
from backend.services.experiment import (
    store, conditions, weather_program, metrics, artifacts, replay, runner,
)
from backend.services.experiment.steps import generate, schedule, simulate
from backend.services.experiment.paxflow_builder import build_paxflow_schedule
from backend.utils.city_geo import build_transit_cache_from_flights

USER = '__pipeline__'


def _fingerprint():
    return (
        len(state.get_active_flights()),
        len(state.get_active_chains()),
        state.get_current_history_id(),
        state.get_filtered_mode(),
    )


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(store.user_dir(USER), ignore_errors=True)
        cond = conditions.normalize({
            'name': 'pipe', 'dates': ['2020-11-30'], 'bases': ['成都'],
            'seed': 2026, 'disruption': {'weather': 'sichuan_storm'},
        })
        gen = generate.run(cond)
        sched = schedule.run(gen, cond)
        amap = {f.flight_id: ac.tail_no for ac in sched['aircraft'] for f in ac.assigned_flights}
        weather = weather_program.compile_plan(
            cond, gen['flights'], aircraft_map=amap, chains=gen['chains'],
            transit_cache=build_transit_cache_from_flights(gen['flights']))
        sim = simulate.run(gen, weather['plan'], cond)
        result = metrics.aggregate(gen, sched, weather, sim)
        paxflow = build_paxflow_schedule(
            gen['flights'], cond['hub'], sched['runway']['items'],
            {a['flight_id']: {'gate': a['gate'], 'runway_group': a['runway']}
             for row in sched['gates'] for a in row['assignments']},
            amap, weather['plan'])
        paxflow.pop('flights', None)
        record = store.create(USER, cond, name='pipe')
        record.status = 'succeeded'
        record.replay = {'sim_start': sim['sim_start'], 'sim_end': sim['sim_end'],
                         'step_minutes': sim['step_minutes'], 'airport': cond['hub'],
                         'has_paxflow': True}
        store.save(record)
        artifacts.write_bundle(USER, record.id, {
            'flights': [artifacts.serialize_flight(f) for f in gen['flights']],
            'schedule': {'aircraft': artifacts.serialize_aircraft(sched['aircraft'])},
            'weather': weather, 'metrics': result, 'paxflow': paxflow, 'run': {},
        })
        cls.cond = cond
        cls.gen = gen
        cls.weather = weather
        cls.sim = sim
        cls.record = record

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(store.user_dir(USER), ignore_errors=True)

    def test_reproducible_series(self):
        again = simulate.run(self.gen, self.weather['plan'], self.cond)
        self.assertEqual(json.dumps(again['series'], sort_keys=True),
                         json.dumps(self.sim['series'], sort_keys=True))

    def test_replay_consistency(self):
        before = _fingerprint()
        session = replay.get(USER, self.record.id)
        points = self.sim['series']
        for p in (points[0], points[len(points) // 2], points[-1]):
            session.sync(p['t'])
            counts = {'airborne': 0, 'arrived': 0, 'delayed': 0, 'cancelled': 0}
            for fs in session.engine.flights.values():
                if fs.is_airborne:
                    counts['airborne'] += 1
                if fs.phase == FlightPhase.PARKED:
                    counts['arrived'] += 1
                if fs.phase == FlightPhase.CANCELLED:
                    counts['cancelled'] += 1
                elif fs.delay_minutes > 0:
                    counts['delayed'] += 1
            for key, value in counts.items():
                self.assertEqual(value, p[key], f'{key} @ {p["t"]}')
        self.assertEqual(_fingerprint(), before)

    def test_isolation(self):
        before = _fingerprint()
        record = store.create(USER, self.cond, name='iso')
        runner.start(USER, record.id)
        deadline = time.time() + 60
        while time.time() < deadline:
            current = store.load(USER, record.id)
            if runner.get_progress(current)['status'] != 'running':
                break
            time.sleep(0.3)
        self.assertEqual(store.load(USER, record.id).status, 'succeeded')
        self.assertEqual(_fingerprint(), before)


if __name__ == '__main__':
    unittest.main()
