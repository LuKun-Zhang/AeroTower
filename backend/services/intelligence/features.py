"""明确区分决策前可用特征和运行后标签。"""
from datetime import datetime
from .scenarios import WEATHER_DELAY


def flight_features(flight, config):
    value = flight.get("time_departure", "2026-11-01 07:00")
    # 原航班接口使用年月日时分数组，实验快照使用 ISO 字符串。
    departure = datetime(*value[:5]) if isinstance(value, (list, tuple)) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return {"hour": departure.hour + departure.minute / 60, "weekday": departure.weekday(),
            "duration": float(flight.get("timespan", 90)), "capacity": config["capacity"],
            "weather_severity": WEATHER_DELAY[config["weather"]], "previous_delay": config["previous_delay"],
            "traffic": config["flight_count"] * config["demand_factor"], "departure_window": config["spread_minutes"],
            "event_type": config["event_type"], "disruption_minutes": config["disruption_minutes"],
            "event_affected": int(flight.get("event_affected", False)),
            "aircraft_type": flight.get("ac_type", "unknown"),
            "origin": flight.get("departure_airport", "unknown"), "destination": flight.get("arrival_airport", "unknown")}


def recovery_features(config, impact):
    return {"event_type": config["event_type"], "affected": impact.total_impacted_flights,
            "aircraft": impact.total_impacted_aircraft, "crew": impact.total_impacted_crew,
            "gates": impact.total_impacted_gates, "duration": config["disruption_minutes"],
            "backup": config["backup_aircraft"], "backup_crew": config["backup_crew"], "backup_gates": config["backup_gates"], "capacity": config["capacity"],
            "traffic": config["flight_count"] * config["demand_factor"], "weather": config["weather"]}
