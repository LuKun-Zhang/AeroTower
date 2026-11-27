"""执行已有恢复策略，并使用统一的代价与约束检查评估结果。"""
from copy import deepcopy
import re
from ..recovery_strategies.time_shift import TimeShiftStrategy
from ..recovery_strategies.resource_replacement import ResourceReplacementStrategy
from ..recovery_strategies.chain_replanning import ChainReplanningStrategy
from ..recovery_strategies.merge_flights import MergeFlightsStrategy
from ..recovery_strategies.cancel_flights import CancelFlightsStrategy
from .config import STRATEGIES


def _checked_cost(result, schedule, impact, config, strategy):
    flights = {f.flight_id: f for f in schedule["flights"]}
    delays = {fid: info.get("delay_minutes", 0) for fid, info in impact.timeline_changes.items()}
    cancellations = {v["flight_id"] for v in result.get("canceled_flights", [])}
    replacements = result.get("aircraft_changes", []) + result.get("crew_changes", []) + result.get("gate_changes", [])
    violations = []
    for change in result.get("flight_changes", []):
        fid = change.get("flight_id")
        if fid not in flights:
            violations.append("方案包含未知航班")
            continue
        if change.get("change_type") == "DELAY":
            match = re.fullmatch(r"\+(\d+)min", str(change.get("new_value", "")))
            if match:
                delays[fid] = max(int(match.group(1)), delays.get(fid, 0))
    for change in replacements:
        # 机场关闭不能用换飞机解除，只有相应资源事件才允许清除等待。
        expected = {"aircraft_failure": "REASSIGN_AIRCRAFT", "crew_absence": "REASSIGN_CREW", "gate_failure": "REASSIGN_GATE"}
        if change.get("change_type") == expected.get(config["event_type"]):
            delays[change["flight_id"]] = 0
    for merged in result.get("merged_flights", []):
        first, second = flights.get(merged["kept"]), flights.get(merged["merged"])
        if not first or not second:
            violations.append("合并航班缺少原始数据")
        elif first.pax_count + second.pax_count > first.seats:
            violations.append("合并后旅客超过座位数")
        else:
            cancellations.add(second.flight_id)
    changed_aircraft = {v["flight_id"]: v["new_value"] for v in result.get("aircraft_changes", [])}
    for fid, tail in changed_aircraft.items():
        known_type = schedule.get("aircraft_types", {}).get(tail)
        if known_type and fid in flights and known_type != flights[fid].ac_type:
            violations.append("备份飞机机型不匹配")
    reservations = {}
    for flight in flights.values():
        fid = flight.flight_id
        if fid in cancellations:
            continue
        tail = changed_aircraft.get(fid, schedule.get("aircraft_assignments", {}).get(fid))
        if tail:
            reservations.setdefault(tail, []).append((flight.departure_minutes + delays.get(fid, 0),
                                                      flight.arrival_minutes + delays.get(fid, 0), flight))
    for jobs in reservations.values():
        jobs.sort(key=lambda value: value[0])
        for first, second in zip(jobs, jobs[1:]):
            if first[1] + 30 > second[0] or first[2].arrival_airport != second[2].departure_airport:
                violations.append("飞机任务存在时间或空间冲突")
    if strategy == "chain_replanning" and not changed_aircraft:
        violations.append("任务链重规划未找到可用接替")
    if strategy == "resource_replacement" and not replacements:
        violations.append("缺少可用备份资源")
    if strategy == "merge_flights" and not result.get("merged_flights"):
        violations.append("没有可合并的航班")
    delay_total = sum(delay for fid, delay in delays.items() if fid not in cancellations)
    # 单位为等价延误分钟。取消权重在训练和评估中保持一致，页面同时展示原始指标。
    cost = delay_total + len(cancellations) * 240 + len(replacements) * 8
    return {"cost": round(cost, 2), "delay_minutes": delay_total, "canceled": len(cancellations),
            "resource_changes": len(replacements), "feasible": not violations,
            "violations": sorted(set(violations)), "changes": result}


def evaluate_strategies(config, schedule, impact, backups):
    classes = {"time_shift": TimeShiftStrategy, "chain_replanning": ChainReplanningStrategy,
               "merge_flights": MergeFlightsStrategy, "cancel_flights": CancelFlightsStrategy}
    results = []
    for name in STRATEGIES:
        copied, copied_impact = deepcopy(schedule), deepcopy(impact)
        copied["aircraft_types"] = {row["tail_no"]: row["ac_type"] for row in backups.get("backup_aircraft", []) if row.get("ac_type")}
        if name == "resource_replacement":
            instance = ResourceReplacementStrategy(copied, copied_impact, deepcopy(backups))
        else:
            instance = classes[name](copied, copied_impact)
        if not instance.can_apply():
            continue
        proposal = instance.apply()
        outcome = _checked_cost(proposal, copied, copied_impact, config, name)
        results.append({"strategy": name, "name": STRATEGIES[name], **outcome})
    return results
