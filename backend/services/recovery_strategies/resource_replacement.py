"""资源替换策略 — 查找可用的备份资源替代受影响的资源

适用场景：
  - 飞机故障 → 从备份机队中找空闲飞机
  - 机组成员请假/超时 → 从备份机组中找可用人员
  - 登机口维修 → 分配到其他可用登机口
  - 跑道关闭 → 切换到备用跑道
"""

from .base_strategy import BaseRecoveryStrategy
from ...models.recovery_plan import ChangeType


class ResourceReplacementStrategy(BaseRecoveryStrategy):
    """资源替换策略：用备份资源替换受影响资源"""

    def __init__(self, current_schedule, impact_report, backup_resources):
        """
        Args:
            current_schedule: dict 当前排班
            impact_report: ImpactReport
            backup_resources: dict 备份资源
                {
                    'backup_aircraft': [{tail_no, ac_type, status, base}, ...],
                    'backup_crew': [{crew_id, role, status, base}, ...],
                    'backup_gates': [{gate_id, terminal, status}, ...],
                    'backup_runways': [{runway_id, status}, ...],
                }
        """
        super().__init__(current_schedule, impact_report)
        self.backup = backup_resources

    def can_apply(self):
        """只要影响分析报告有直接受影响的资源，就可以尝试资源替换"""
        return bool(
            self.impact.direct_impacted_aircraft or
            self.impact.direct_impacted_crew or
            self.impact.direct_impacted_gates or
            self.impact.direct_impacted_runways or
            self.impact.total_impacted_flights > 0
        )

    def apply(self):
        """执行资源替换"""
        result = {
            "flight_changes": [],
            "aircraft_changes": [],
            "crew_changes": [],
            "gate_changes": [],
            "runway_changes": [],
            "side_effects": [],
        }

        aircraft_map = self.schedule.get("aircraft_assignments", {})
        crew_map = self.schedule.get("crew_assignments", {})
        gate_map = self.schedule.get("gate_assignments", {})
        runway_map = self.schedule.get("runway_assignments", {})

        # 1) 替换受影响飞机
        if self.impact.direct_impacted_aircraft:
            self._replace_aircraft(result, aircraft_map)

        # 2) 替换受影响机组
        if self.impact.direct_impacted_crew:
            self._replace_crew(result, crew_map)

        # 3) 替换受影响登机口
        if self.impact.direct_impacted_gates:
            self._replace_gates(result, gate_map)

        # 4) 替换受影响跑道
        if self.impact.direct_impacted_runways:
            self._replace_runways(result, runway_map)

        # 5) 对级联影响的航班，尝试重新分配资源
        for chain_entry in self.impact.cascade_chains:
            fid = chain_entry.get("flight_id")
            if fid in aircraft_map and aircraft_map[fid] in self.impact.direct_impacted_aircraft:
                backup = self._find_backup_aircraft()
                if backup and fid not in already_replaced(result["aircraft_changes"]):
                    result["aircraft_changes"].append({
                        "flight_id": fid,
                        "change_type": ChangeType.REASSIGN_AIRCRAFT,
                        "old_value": aircraft_map[fid],
                        "new_value": backup["tail_no"],
                        "reason": f"级联影响：原飞机{chain_entry.get('reason', '不可用')}",
                    })

        return result

    def evaluate(self, result):
        """评估恢复效果：覆盖多少受影响航班"""
        total = self.impact.total_impacted_flights
        if total == 0:
            return 1.0
        replaced = len(
            list_affected_fids(result)
        )
        return min(1.0, replaced / total)

    @staticmethod
    def get_strategy_name():
        return "ResourceReplacementStrategy"

    # ===== 内部实现 =====

    def _replace_aircraft(self, result, aircraft_map):
        """替换受影响飞机"""
        backup_list = self.backup.get("backup_aircraft", [])
        available = [a for a in backup_list if a.get("status") == "idle"]

        for tail_no in self.impact.direct_impacted_aircraft:
            # 找出所有使用该飞机的航班
            affected_fids = [
                fid for fid, a in aircraft_map.items() if a == tail_no
            ]
            if not available:
                result["side_effects"].append({
                    "type": "aircraft_shortage",
                    "affected_aircraft": tail_no,
                    "detail": f"无可用备份飞机替代 {tail_no}，共影响 {len(affected_fids)} 个航班",
                })
                continue

            backup = available.pop(0)
            for fid in affected_fids:
                result["aircraft_changes"].append({
                    "flight_id": fid,
                    "change_type": ChangeType.REASSIGN_AIRCRAFT,
                    "old_value": tail_no,
                    "new_value": backup["tail_no"],
                    "reason": f"飞机{tail_no}故障，替换为备份机{backup['tail_no']}",
                })

    def _replace_crew(self, result, crew_map):
        """替换受影响机组成员"""
        backup_list = self.backup.get("backup_crew", [])
        available = [c for c in backup_list if c.get("status") == "available"]

        for crew_id in self.impact.direct_impacted_crew:
            affected_fids = [
                fid for fid, assigned in crew_map.items()
                if crew_id in (assigned if isinstance(assigned, list) else [])
            ]
            if not available:
                result["side_effects"].append({
                    "type": "crew_shortage",
                    "affected_crew": crew_id,
                    "detail": f"无可用备份机组替代 {crew_id}，共影响 {len(affected_fids)} 个航班",
                })
                continue

            backup = available.pop(0)
            for fid in affected_fids:
                result["crew_changes"].append({
                    "flight_id": fid,
                    "change_type": ChangeType.REASSIGN_CREW,
                    "old_value": crew_id,
                    "new_value": backup["crew_id"],
                    "reason": f"机组{crew_id}不可用，替换为备份{backup['crew_id']}",
                })

    def _replace_gates(self, result, gate_map):
        """替换受影响登机口"""
        backup_list = self.backup.get("backup_gates", [])
        available = [g for g in backup_list if g.get("status") == "idle"]

        for gate_id in self.impact.direct_impacted_gates:
            affected_fids = [
                fid for fid, g in gate_map.items() if g == gate_id
            ]
            if not available:
                result["side_effects"].append({
                    "type": "gate_shortage",
                    "affected_gate": gate_id,
                    "detail": f"无可用备份登机口替代 {gate_id}，共影响 {len(affected_fids)} 个航班",
                })
                continue

            backup = available.pop(0)
            for fid in affected_fids:
                result["gate_changes"].append({
                    "flight_id": fid,
                    "change_type": ChangeType.REASSIGN_GATE,
                    "old_value": gate_id,
                    "new_value": backup["gate_id"],
                    "reason": f"登机口{gate_id}维修，替换为{backup['gate_id']}",
                })

    def _replace_runways(self, result, runway_map):
        """替换受影响跑道"""
        backup_list = self.backup.get("backup_runways", [])
        available = [r for r in backup_list if r.get("status") == "idle"]

        for runway_id in self.impact.direct_impacted_runways:
            affected_fids = [
                fid for fid, r in runway_map.items() if r == runway_id
            ]
            if not available:
                result["side_effects"].append({
                    "type": "runway_shortage",
                    "affected_runway": runway_id,
                    "detail": f"无可用备份跑道替代 {runway_id}，共影响 {len(affected_fids)} 个航班",
                })
                continue

            backup = available.pop(0)
            for fid in affected_fids:
                result["runway_changes"].append({
                    "flight_id": fid,
                    "change_type": ChangeType.REASSIGN_RUNWAY,
                    "old_value": runway_id,
                    "new_value": backup["runway_id"],
                    "reason": f"跑道{runway_id}关闭，替换为{backup['runway_id']}",
                })

    def _find_backup_aircraft(self):
        """查找可用备份飞机"""
        backup_list = self.backup.get("backup_aircraft", [])
        for a in backup_list:
            if a.get("status") == "idle":
                return a
        return None


def list_affected_fids(result):
    """从修改结果中收集所有受影响的航班 ID"""
    fids = set()
    for key in ["flight_changes", "aircraft_changes", "crew_changes",
                 "gate_changes", "runway_changes"]:
        for change in result.get(key, []):
            fids.add(change.get("flight_id"))
    return fids


def already_replaced(changes):
    """收集已经被替换的航班 ID"""
    return {c["flight_id"] for c in changes}
