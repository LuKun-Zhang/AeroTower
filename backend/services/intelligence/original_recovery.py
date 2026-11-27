"""在副本中运行原恢复服务，使用相同条件和统一代价作基线。"""
from copy import deepcopy
from datetime import datetime, timedelta
from ...models.abnormal_event import AbnormalEvent
from ..recovery_service import RecoveryService
from ..routing_service import AircraftRoutingService
from .strategy_evaluation import _checked_cost


def original_recovery_outcome(config, schedule, impact, backups, event=None):
    copied = deepcopy(schedule)
    if event is None:
        start = datetime.fromisoformat(config["start_date"])+timedelta(hours=config["start_hour"])
        event = AbnormalEvent("shadow-event", config["event_type"], "原流程隔离对照",
            affected_airports=[config["base_airport"]] if config["event_type"] == "airport_closure" else [],
            affected_aircraft=impact.direct_impacted_aircraft, affected_crew=impact.direct_impacted_crew,
            affected_gates=impact.direct_impacted_gates, affected_flights=impact.direct_impacted_flights,
            start_time=start.strftime("%Y-%m-%d %H:%M"),
            end_time=(start+timedelta(minutes=config["disruption_minutes"])).strftime("%Y-%m-%d %H:%M"),
            duration_minutes=config["disruption_minutes"], delay_minutes=config["disruption_minutes"])
    service = RecoveryService()
    service._backup_resources = deepcopy(backups)
    original_impact, plan = service.generate_recovery_plan(deepcopy(event), copied)
    service.confirm_plan(plan.plan_id)
    executed = service.execute_plan(plan.plan_id, copied)
    proposal = plan.to_dict()
    actual_cancellations = len(plan.canceled_flights)
    unrecovered = []
    for change in proposal["flight_changes"]:
        if change["change_type"] == "DELAY":
            change["new_value"] = f"+{change.get('delay_minutes', 0)}min"
    if executed.get("excluded_aircraft"):
        from ...routes.schedule_routes import DEFAULT_AIRCRAFT_COUNT
        excluded = executed["excluded_aircraft"]
        fleet = max(DEFAULT_AIRCRAFT_COUNT-len(excluded), 5)
        # 与原回调相同的确定性飞机重排；不调用会写活动state的回调函数。
        planes = AircraftRoutingService().solve_chain_coverage(executed.get("chains", []), fleet, 60, excluded_aircraft=excluded)
        assigned = {flight.flight_id: plane.tail_no for plane in planes for flight in plane.assigned_flights}
        proposal["aircraft_changes"] = [{"flight_id": fid, "change_type": "REASSIGN_AIRCRAFT", "new_value": tail}
            for fid, tail in assigned.items() if fid in impact.timeline_changes]
        unrecovered = [f.flight_id for f in copied["flights"] if f.flight_id not in assigned]
        proposal["canceled_flights"] = [{"flight_id": fid} for fid in unrecovered]
    outcome = _checked_cost(proposal, copied, impact, config, "original_flow")
    before = {f.flight_id: f for f in copied["flights"]}
    observed = sum(max(0, (datetime(*f.time_departure)-datetime(*before[f.flight_id].time_departure)).total_seconds()/60)
                   for f in executed["flights"] if f.flight_id in before)
    return {"strategy": "original_flow", "name": "原系统恢复流程", **outcome,
        "canceled": actual_cancellations, "unrecovered": len(unrecovered),
        "original_strategy": plan.strategy, "execution_checked": plan.status == "executed",
        "observed_shift_minutes": observed, "impact_flights": original_impact.total_impacted_flights,
        "scope": "原恢复服务生成和执行；飞机排除采用原回调链覆盖，未恢复架次按取消等价权重240计入但不冒充实际取消；不评价机组执勤法规"}
