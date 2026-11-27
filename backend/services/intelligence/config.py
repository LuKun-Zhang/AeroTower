"""智能模块的路径和公开场景字段。"""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("AEROTOWER_INTELLIGENCE_DATA", ROOT / "data" / "intelligence"))
MODELS = DATA / "models"
QWEN15 = ROOT / ".artifacts" / "models" / "qwen-1.5b"
QWEN = QWEN15 if (QWEN15 / "verified.json").is_file() else ROOT / ".artifacts" / "models" / "qwen"
AIRPORTS = ["成都", "北京", "上海", "广州", "昆明", "三亚", "重庆", "西安"]
WEATHER = {"clear": "晴朗", "rain": "降雨", "storm": "雷暴", "fog": "大雾", "snow": "降雪"}
STRATEGIES = {"time_shift": "时间平移", "resource_replacement": "资源替换",
              "chain_replanning": "任务链重规划", "merge_flights": "航班合并", "cancel_flights": "航班取消"}
DEFAULTS = {"base_airport": "成都", "flight_count": 48, "weather": "clear", "demand_factor": 1.0,
            "capacity": 2, "previous_delay": 0, "event_type": "airport_closure", "disruption_minutes": 60,
            "backup_aircraft": 2, "seed": 42, "start_hour": 7, "start_date": "2026-11-26", "days": 1,
            "model_enabled": True, "backup_crew": 2, "backup_gates": 2, "spread_minutes": 360}
BOUNDS = {"flight_count": (8, 240), "demand_factor": (0.5, 2.0), "capacity": (1, 4),
          "previous_delay": (0, 180), "disruption_minutes": (0, 480), "backup_aircraft": (0, 12),
          "seed": (0, 2147483647), "start_hour": (0, 18), "days": (1, 7),
          "backup_crew": (0, 12), "backup_gates": (0, 12), "spread_minutes": (60, 720)}
EVENTS = ["airport_closure", "aircraft_failure", "crew_absence", "gate_failure"]


def validate_config(payload):
    if not isinstance(payload, dict):
        raise ValueError("实验条件必须是对象")
    unknown = set(payload) - set(DEFAULTS)
    if unknown:
        raise ValueError("不支持的字段：" + ", ".join(sorted(unknown)))
    values = {**DEFAULTS, **payload}
    if not isinstance(values["model_enabled"], bool):
        raise ValueError("model_enabled 必须是布尔值")
    try:
        date.fromisoformat(values["start_date"])
    except (ValueError, TypeError):
        raise ValueError("开始日期必须是 YYYY-MM-DD") from None
    for field, (low, high) in BOUNDS.items():
        value = values[field]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not low <= value <= high:
            raise ValueError(f"{field} 必须在 {low} 到 {high} 之间")
        if field != "demand_factor" and int(value) != value:
            raise ValueError(f"{field} 必须是整数")
        values[field] = float(value) if field == "demand_factor" else int(value)
    for field, choices in (("base_airport", AIRPORTS), ("weather", WEATHER), ("event_type", EVENTS)):
        if values[field] not in choices:
            raise ValueError(f"{field} 不在支持范围内")
    if values["flight_count"] * values["demand_factor"] * values["days"] > 2000:
        raise ValueError("单个实验的总航班数不能超过 2000，请减少天数或航班数")
    return values
