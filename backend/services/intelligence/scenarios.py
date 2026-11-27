"""把可重跑的实验条件转换为原有调度器输入。"""
from copy import deepcopy
from datetime import datetime, timedelta
import random
from ...models.experiment_flight import ExperimentFlight
from ...models.impact_report import ImpactReport
from ..runway_service import RunwaySchedulingService
from ..aircraft_types import type_layout, type_seats
from .config import AIRPORTS, validate_config

WEATHER_DELAY = {"clear": 0, "rain": 12, "storm": 70, "fog": 38, "snow": 48}


def time_tuple(minutes, start_date):
    value = datetime.fromisoformat(start_date) + timedelta(minutes=minutes)
    return (value.year, value.month, value.day, value.hour, value.minute)


def build_scenario(payload):
    config = validate_config(payload)
    rng = random.Random(config["seed"])
    base = config["base_airport"]
    daily_count = min(480, round(config["flight_count"] * config["demand_factor"]))
    count = daily_count * config["days"]
    flights, chains, assignments = [], [], {}
    start = config["start_hour"] * 60
    pairs_per_day = (daily_count + 1) // 2
    for index in range(config["days"] * pairs_per_day):
        destination = rng.choice([name for name in AIRPORTS if name != base])
        day = index // pairs_per_day
        departure = day * 1440 + start + rng.randrange(max(20, round(config["spread_minutes"] / config["demand_factor"])))
        duration = rng.randrange(45, 135)
        tail = f"LAB-{index:03d}"
        profile = ["A319"]+["A320"]*5+["A321"]*4
        ac_type = profile[(index+config["seed"])%len(profile)]
        chain = []
        for leg in range(2):
            if (index % pairs_per_day) * 2 + leg >= daily_count:
                continue
            minute = departure + leg * (duration + 60)
            flight = ExperimentFlight(f"lab-{len(flights):04d}", f"3U{5000+len(flights):04d}", ac_type, type_layout(ac_type),
                            base if leg == 0 else destination, destination if leg == 0 else base,
                            time_tuple(minute, config["start_date"]), time_tuple(minute + duration, config["start_date"]), duration)
            flight.departure_time = f"{minute//60:02d}:{minute%60:02d}"
            flight.arrival_time = f"{(minute+duration)//60:02d}:{(minute+duration)%60:02d}"
            flight.pax_count, flight.seats = rng.randint(35, 130), type_seats(ac_type)
            flights.append(flight)
            chain.append(flight)
            assignments[flight.flight_id] = tail
        chains.append(chain)
    impacted_tails = sorted(set(assignments.values()))[:max(1, count // 10)]
    impacted = [f.flight_id for f in flights if assignments[f.flight_id] in impacted_tails]
    if config["event_type"] == "airport_closure":
        impacted = [flight.flight_id for flight in flights]
    timeline = {fid: {"delay_minutes": config["disruption_minutes"], "level": 0} for fid in impacted}
    impact = ImpactReport("lab-impact", "lab-event", direct_impacted_flights=impacted,
                          direct_impacted_aircraft=impacted_tails if config["event_type"] == "aircraft_failure" else [],
                          direct_impacted_crew=["LAB-CREW"] if config["event_type"] == "crew_absence" else [],
                          direct_impacted_gates=["LAB-GATE"] if config["event_type"] == "gate_failure" else [],
                          total_impacted_flights=len(impacted), total_impacted_aircraft=len(impacted_tails),
                          total_impacted_crew=int(config["event_type"] == "crew_absence"),
                          total_impacted_gates=int(config["event_type"] == "gate_failure"),
                          total_delay_minutes=len(impacted)*config["disruption_minutes"], timeline_changes=timeline)
    schedule = {"flights": flights, "chains": chains, "aircraft_assignments": assignments,
                "crew_assignments": {fid: ["LAB-CREW"] for fid in impacted},
                "gate_assignments": {fid: "LAB-GATE" for fid in impacted},
                "initial_delays": {fid: value["delay_minutes"] for fid, value in timeline.items()}}
    backups = {"backup_aircraft": [{"tail_no": f"BACK-{i}", "ac_type": "A320", "status": "idle", "base": base}
                                    for i in range(config["backup_aircraft"])],
               "backup_crew": [{"crew_id": f"CREW-{i}", "status": "available", "base": base}
                               for i in range(config["backup_crew"])],
               "backup_gates": [{"gate_id": f"GATE-{i}", "status": "idle"} for i in range(config["backup_gates"])]}
    return config, schedule, impact, backups


def simulate_delays(config, schedule):
    """复用原跑道服务计算排队，并记录未知扰动后的延误标签。"""
    rng = random.Random(config["seed"] + 7919)
    flights = deepcopy(schedule["flights"])
    shifted = {}
    weather = WEATHER_DELAY[config["weather"]]
    for index, flight in enumerate(flights):
        # 微小运行扰动只存在于标签，不能作为预测时已知的输入。
        fluctuation = max(0, rng.gauss(weather * 0.18, 5))
        incident = schedule["initial_delays"].get(flight.flight_id, 0)
        delay = max(incident, round(weather + fluctuation + config["previous_delay"] * (0.8 if index % 2 else 0.4)))
        shifted[flight.flight_id] = delay
        for field in ("time_departure", "time_arrival"):
            current = datetime(*getattr(flight, field)) + timedelta(minutes=delay)
            setattr(flight, field, (current.year, current.month, current.day, current.hour, current.minute))
    solver = RunwaySchedulingService()
    solver._runway_cfg = {config["base_airport"]: config["capacity"]}
    operations, _ = solver.solve_multi_runway(flights, config["base_airport"])
    results = {item["flight_id"]: shifted[item["flight_id"]] + item["delay"] for item in operations}
    return [{**f.to_dict(), "previous_delay": config["previous_delay"],
             "event_affected": f.flight_id in schedule["initial_delays"], "actual_delay": results[f.flight_id],
             "delayed": results[f.flight_id] > 15} for f in schedule["flights"]]


def sample_configs(count, seed, holdout=False):
    rng = random.Random(seed)
    values = []
    airports = AIRPORTS[5:] if holdout else AIRPORTS[:5]
    for _ in range(count):
        values.append(validate_config({"base_airport": rng.choice(airports), "seed": rng.randrange(10000000),
            "flight_count": rng.randint(24, 130 if holdout else 100), "demand_factor": rng.uniform(0.7, 1.8 if holdout else 1.4),
            "weather": rng.choices(list(WEATHER_DELAY), weights=[5, 2, 1, 1, 1])[0], "capacity": rng.randint(1, 3),
            "previous_delay": rng.choice([0, 0, 0, rng.randint(0, 90 if holdout else 65)]), "start_hour": rng.randint(6, 13),
            "event_type": rng.choice(["airport_closure", "aircraft_failure", "crew_absence", "gate_failure"]),
            "disruption_minutes": rng.randint(15, 440 if holdout else 360), "backup_aircraft": rng.randint(0, 7),
            "backup_crew": rng.randint(0, 7), "backup_gates": rng.randint(0, 7)}))
    for config in values:
        config["spread_minutes"] = 120+(config["seed"]%7)*90
    return values
