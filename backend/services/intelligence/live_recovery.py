"""将当前异常页的数据复制适配后交给现有策略，避免改动活动排班。"""
from copy import deepcopy
from ..anomaly_service import anomaly_service
from ..recovery_service import recovery_service
from ..aircraft_types import layout_seats
from ...models.impact_report import ImpactReport
from .config import DEFAULTS
from .predictions import recommend
from .strategy_evaluation import evaluate_strategies
from .original_recovery import original_recovery_outcome


def live_recommendation(event_id):
    from ...routes.anomaly_routes import _get_schedule
    event = anomaly_service.get_event(event_id)
    if not event:
        raise FileNotFoundError("异常事件不存在")
    report = getattr(event, "impact_report", None)
    if not report:
        raise ValueError("请先执行影响分析，再请求智能推荐")
    schedule = deepcopy(_get_schedule())
    for flight in schedule.get("flights", []):
        flight.departure_time = f"{flight.departure_minutes//60:02d}:{flight.departure_minutes%60:02d}"
        flight.arrival_time = f"{flight.arrival_minutes//60:02d}:{flight.arrival_minutes%60:02d}"
        flight.seats = layout_seats(flight.layout)
        flight.pax_count = getattr(flight, "_pax_count", flight.seats)
    normalized = deepcopy(report)
    # 原异常页把编号丰富为显示对象，旧策略仍需要纯编号，不能直接传 dict。
    for field in ("direct_impacted_flights", "flights_to_cancel"):
        normalized[field] = [row["flight_id"] if isinstance(row, dict) else row for row in report.get(field, [])]
    impact = ImpactReport.from_dict(normalized)
    aliases = {"crew_substitution": "crew_absence", "gate_maintenance": "gate_failure"}
    event_type = aliases.get(event.event_type, event.event_type)
    if event_type not in ("aircraft_failure", "crew_absence", "gate_failure"):
        event_type = "airport_closure"
    backups = deepcopy(recovery_service._backup_resources)
    duration = max((v.get("delay_minutes", 0) for v in impact.timeline_changes.values()), default=0)
    config = {**DEFAULTS, "event_type": event_type, "disruption_minutes": duration,
              "flight_count": len(schedule.get("flights", [])), "backup_aircraft": len(backups.get("backup_aircraft", [])),
              "backup_crew": len(backups.get("backup_crew", [])), "backup_gates": len(backups.get("backup_gates", []))}
    baseline = original_recovery_outcome(config, schedule, impact, backups, event)
    result = recommend(config, impact, evaluate_strategies(config, schedule, impact, backups), baseline)
    result["assumptions"] = "此处采用晴朗、2条跑道和基准客流作参考；未接入实时天气。推荐仅供比较，不会替换下方原恢复方案。"
    return result
