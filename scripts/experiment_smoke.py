"""实验流水线冒烟与复现检查。

用法：
  python scripts/experiment_smoke.py --days 1
  python scripts/experiment_smoke.py --compare --days 1 --weather sichuan_storm
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.experiment import conditions, weather_program, metrics
from backend.services.experiment.steps import generate, schedule, simulate
from backend.utils.city_geo import build_transit_cache_from_flights

DATES = ['2020-11-30', '2020-12-01', '2020-12-02',
         '2020-12-03', '2020-12-04', '2020-12-05']


def run_once(days, weather, seed):
    cond = conditions.normalize({
        'name': 'smoke',
        'dates': DATES[:days],
        'bases': ['成都'],
        'seed': seed,
        'disruption': {'weather': weather},
    })
    gen = generate.run(cond)
    sched = schedule.run(gen, cond)
    aircraft_map = {f.flight_id: ac.tail_no
                    for ac in sched['aircraft'] for f in ac.assigned_flights}
    weather_plan = weather_program.compile_plan(
        cond, gen['flights'], aircraft_map=aircraft_map,
        chains=gen['chains'],
        transit_cache=build_transit_cache_from_flights(gen['flights']),
    )
    sim = simulate.run(gen, weather_plan['plan'], cond)
    result = metrics.aggregate(gen, sched, weather_plan, sim)
    return {
        'values': result['values'],
        'series': result['series']['points'],
        'crew': sched['crew'],
        'runway': sched['runway']['stats'],
        'plan_size': weather_plan['meta']['plan_size'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=1)
    parser.add_argument('--weather', default='sichuan_storm')
    parser.add_argument('--seed', type=int, default=123456)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--compare', action='store_true')
    args = parser.parse_args()

    if args.compare:
        cmd = [sys.executable, __file__, '--json', '--days', str(args.days),
               '--weather', args.weather, '--seed', str(args.seed)]
        outs = []
        for hash_seed in ('0', '1'):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed)
            raw = subprocess.check_output(cmd, env=env).decode('utf-8', 'replace')
            line = [ln for ln in raw.splitlines() if ln.startswith('__RESULT__')][-1]
            outs.append(json.loads(line[len('__RESULT__'):]))
        same = json.dumps(outs[0], sort_keys=True) == json.dumps(outs[1], sort_keys=True)
        print('cross-process equal:', same)
        if not same:
            print('first :', json.dumps(outs[0]['values'], ensure_ascii=False))
            print('second:', json.dumps(outs[1]['values'], ensure_ascii=False))
        return 0 if same else 1

    result = run_once(args.days, args.weather, args.seed)
    if args.json:
        print('__RESULT__' + json.dumps(result, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(result['values'], indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
