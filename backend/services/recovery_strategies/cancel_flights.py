"""航班取消策略 — 最后的兜底策略

适用场景：
  - 前序所有策略都无法覆盖的航班
  - 资源严重不足、无法恢复的极端情况
  - 飞机不可用且无可替代资源

原理：
  1. 收集所有其他策略无法覆盖的航空
  2. 按优先级排序后建议取消
  3. 每个取消的航班释放资源供其他策略使用
"""

from .base_strategy import BaseRecoveryStrategy
from ...models.recovery_plan import ChangeType


class CancelFlightsStrategy(BaseRecoveryStrategy):
    """航班取消策略（兜底）"""

    def can_apply(self):
        """总是可以应用（作为兜底策略）"""
        return True

    def apply(self):
        """标记无法恢复的航班为取消"""
        result = {
            "flight_changes": [],
            "aircraft_changes": [],
            "crew_changes": [],
            "gate_changes": [],
            "runway_changes": [],
            "side_effects": [],
            "canceled_flights": [],
        }

        timeline = self.impact.timeline_changes or {}
        flights_to_cancel = list(self.impact.flights_to_cancel or [])

        # 收集所有级联影响中剩余未覆盖的航班
        cascade_fids = {
            c.get("flight_id") for c in (self.impact.cascade_chains or [])
        }
        direct_fids = set(self.impact.direct_impacted_flights or [])
        all_impacted = cascade_fids | direct_fids

        for fid in all_impacted:
            info = timeline.get(fid, {})
            delay = info.get("delay_minutes", 0)
            # 如果延迟超过 6 小时且资源不可用，建议取消
            if delay >= 360 and fid not in flights_to_cancel:
                flights_to_cancel.append(fid)

        # 去重
        flights_to_cancel = list(set(flights_to_cancel))

        # 按影响程度排序（直接影响优先保留，级联影响优先取消）
        for fid in flights_to_cancel:
            is_direct = fid in direct_fids
            level = timeline.get(fid, {}).get("level", 99)
            reason = (
                f"直接受影响航班，不可恢复"
                if is_direct
                else f"级联影响(level={level})，延迟{timeline.get(fid, {}).get('delay_minutes', 0)}分钟，超出可恢复范围"
            )
            result["canceled_flights"].append({
                "flight_id": fid,
                "reason": reason,
                "is_direct": is_direct,
            })
            result["flight_changes"].append({
                "flight_id": fid,
                "change_type": ChangeType.CANCEL,
                "old_value": fid,
                "new_value": "CANCELED",
                "reason": reason,
            })

        return result

    def evaluate(self, result):
        """取消策略的评分：取消越少越好"""
        canceled = len(result.get("canceled_flights", []))
        total = self.impact.total_impacted_flights
        if total == 0:
            return 1.0
        if canceled == 0:
            return 1.0  # 没触发取消
        # 取消越多分越低
        return max(0.0, 1.0 - (canceled / total))

    @staticmethod
    def get_strategy_name():
        return "CancelFlightsStrategy"
