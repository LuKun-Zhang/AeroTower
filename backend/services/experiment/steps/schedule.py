"""实验步骤 2：飞机排班、跑道调度、登机口分配、机组排班。

全部使用局部服务实例，不读写 backend.state，也不依赖全局单例。
"""

from ...routing_service import AircraftRoutingService
from ...runway_service import RunwaySchedulingService
from ...gate_service import GateAssignmentService
from ...crew_service import CrewSchedulingService


def _date_at(f, airport):
    t = f.time_arrival if f.arrival_airport == airport else f.time_departure
    return f"{t[0]}-{t[1]:02d}-{t[2]:02d}"


def _airports(flights):
    return sorted({f.departure_airport for f in flights}
                  | {f.arrival_airport for f in flights})


def _route(flights, chains, cond):
    svc = AircraftRoutingService()
    algo = cond['algorithms']['routing']
    size = cond['fleet']['size']
    gap = cond['min_turnaround']
    if algo == 'chain_coverage' and chains:
        aircraft = svc.solve_chain_coverage(chains, size, gap)
    elif algo == 'bipartite':
        aircraft = svc.solve_bipartite(flights, gap)
    elif algo == 'greedy':
        aircraft = svc.solve_greedy_only(flights, size, gap)
    else:
        aircraft = svc.solve_vrp(flights, size, gap)
    stats = svc.get_stats(aircraft, len(flights))
    stats['method'] = algo
    return aircraft, stats


def _runway_stats(items):
    landing = [i for i in items if i.get('type') == 'landing']
    takeoff = [i for i in items if i.get('type') == 'takeoff']
    total_delay = sum(int(i.get('delay', 0)) for i in items)
    return {
        'total_flights': len(items),
        'landing_count': len(landing),
        'takeoff_count': len(takeoff),
        'total_delay': total_delay,
        'avg_delay': round(total_delay / max(len(items), 1), 1),
        'landing_delay': sum(int(i.get('delay', 0)) for i in landing),
        'takeoff_delay': sum(int(i.get('delay', 0)) for i in takeoff),
    }


def _runway(flights, cond):
    svc = RunwaySchedulingService()
    method = cond['algorithms']['runway']
    if method == 'optimized':
        items = svc.solve_optimized(flights, landing=True) + \
                svc.solve_optimized(flights, landing=False)
        # 同一航班可能同时有到达/起飞条目，按 (flight_id, type) 去重
        seen = set()
        dedup = []
        for item in items:
            key = (item.get('flight_id'), item.get('type'))
            if key not in seen:
                seen.add(key)
                dedup.append(item)
        items = dedup
        stats = _runway_stats(items)
        stats['method'] = method
        return {'stats': stats, 'items': items}

    all_items = []
    airports = _airports(flights)
    for ap in airports:
        ap_flights = [f for f in flights
                      if f.departure_airport == ap or f.arrival_airport == ap]
        if not ap_flights:
            continue
        items, _stats = svc.solve_multi_runway(ap_flights, ap)
        all_items.extend(items)
    stats = _runway_stats(all_items)
    stats['method'] = method
    stats['airports'] = len(airports)
    return {'stats': stats, 'items': all_items}


def _gates(flights, runway_items, cond, warnings):
    svc = GateAssignmentService(rng_seed=cond['seed'])
    airport = cond['hub']
    dates = sorted({_date_at(f, airport) for f in flights
                    if f.departure_airport == airport or f.arrival_airport == airport})
    rows = []
    for date in dates:
        day_flights = [f for f in flights
                       if (f.departure_airport == airport or f.arrival_airport == airport)
                       and _date_at(f, airport) == date]
        if not day_flights:
            continue
        try:
            gates = svc.assign_flights_to_gates(
                airport, cond['algorithms']['gate'], date,
                flights=flights, runway_schedule=runway_items,
            )
            stats = svc.get_utilization_stats(gates)
            assignments = []
            for gate in gates:
                for item in gate.assigned_flights:
                    assignments.append({
                        'flight_id': item['flight'].flight_id,
                        'gate': gate.name,
                        'runway': item.get('runway', gate.runway_group),
                    })
            rows.append({'date': date, 'airport': airport,
                         'stats': stats, 'assignments': assignments})
        except Exception as exc:
            warnings.append(f'登机口分配失败({date}): {exc}')
    return rows


def _crew(flights, chains, cond, warnings):
    svc = CrewSchedulingService(rng_seed=cond['seed'])
    airport = cond['hub']
    try:
        if cond['algorithms']['crew'] == 'pairing':
            pool, pairings, assigned, uncovered = svc.schedule_by_pairing(
                target_airport=airport, flights=flights)
        else:
            pool, pairings, assigned, uncovered = svc.schedule_from_aircraft_chains(
                chains, target_airport=airport)
        report = svc.get_compliance_report()
        method = cond['algorithms']['crew']
        if method == 'pairing':
            scope_total = len([f for f in flights
                               if f.departure_airport == airport
                               or f.arrival_airport == airport])
        else:
            scope_total = len(flights)
        covered = max(0, scope_total - len(uncovered or []))
        return {
            'available': report.get('total_crew', 0),
            'assigned': report.get('assigned_crew', 0),
            'coverage': round(covered / max(scope_total, 1) * 100, 1),
            'violations': report.get('total_violations', 0),
            'pairings': len(pairings or []),
            'uncovered': len(uncovered or []),
            'method': method,
        }
    except Exception as exc:
        warnings.append(f'机组排班失败: {exc}')
        return {'available': 0, 'assigned': 0, 'coverage': None,
                'violations': None, 'pairings': 0, 'uncovered': len(flights),
                'method': cond['algorithms']['crew'], 'error': str(exc)}


def run(gen, cond):
    flights = gen['flights']
    chains = gen['chains']
    warnings = []

    aircraft, aircraft_stats = _route(flights, chains, cond)
    runway = _runway(flights, cond)
    gates = _gates(flights, runway['items'], cond, warnings)
    crew = _crew(flights, chains, cond, warnings)

    return {
        'aircraft': aircraft,
        'aircraft_stats': aircraft_stats,
        'runway': runway,
        'gates': gates,
        'crew': crew,
        'warnings': warnings,
    }
