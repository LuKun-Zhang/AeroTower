"""时间平移策略 — 将受影响航班整体向后平移

适用场景：
  - 机场临时关闭 N 小时后重开
  - 跑道临时关闭后恢复
  - 天气好转后恢复运营
  - 飞机可用性延迟（维修完成后恢复执飞）

原理：
  找出所有受影响航班，按原飞行顺序向后平移 delay_minutes，
  后续航班依次递推。
"""

from .base_strategy import BaseRecoveryStrategy
from ...models.recovery_plan import ChangeType


class TimeShiftStrategy(BaseRecoveryStrategy):
    """时间平移策略"""

    MIN_GAP_MINUTES = 30  # 航班间最小间隔（分钟）

    def can_apply(self):
        """时间平移适用于所有有延迟的场景"""
        return self.impact.total_delay_minutes > 0

    def apply(self):
        """执行时间平移"""
        result = {
            "flight_changes": [],
            "aircraft_changes": [],
            "crew_changes": [],
            "gate_changes": [],
            "runway_changes": [],
            "side_effects": [],
        }

        timeline = self.impact.timeline_changes or {}
        flights = sorted(self.schedule.get("flights", []), key=self._sort_key)
        chains = self.schedule.get("chains", [])

        # 按受影响航班分链处理
        processed = set()
        for chain in chains:
            chain_fids = [
                f.flight_id if hasattr(f, 'flight_id') else str(f)
                for f in chain
            ]
            # 找到链中第一个受影响的航班
            affected_in_chain = [
                (i, fid) for i, fid in enumerate(chain_fids) if fid in timeline
            ]
            if not affected_in_chain:
                continue

            first_idx, first_fid = affected_in_chain[0]
            delay = timeline.get(first_fid, {}).get("delay_minutes", 0)

            # 从第一个受影响航班开始，整个链向后平移
            accumulated_delay = 0
            for i in range(first_idx, len(chain)):
                fid = chain_fids[i]
                if fid in processed:
                    continue
                processed.add(fid)

                # 已经在 timeline 中的延迟
                this_delay = timeline.get(fid, {}).get("delay_minutes", 0)
                effective_delay = max(delay, this_delay)

                if effective_delay > 0:
                    result["flight_changes"].append({
                        "flight_id": fid,
                        "change_type": ChangeType.DELAY,
                        "old_value": "on_time",
                        "new_value": f"+{effective_delay}min",
                        "reason": f"时间平移：前置航班延迟{delay}分钟",
                    })

                # 后续航班累加间隔
                delay = max(0, effective_delay - self.MIN_GAP_MINUTES)

        # 未在链中的受影响航班单独处理
        for fid, info in timeline.items():
            if fid not in processed:
                result["flight_changes"].append({
                    "flight_id": fid,
                    "change_type": ChangeType.DELAY,
                    "old_value": "on_time",
                    "new_value": f"+{info.get('delay_minutes', 0)}min",
                    "reason": f"直接延迟：{info.get('reason', '未知')}",
                })

        return result

    def evaluate(self, result):
        """评估：覆盖的受影响航班比例"""
        total = self.impact.total_impacted_flights
        if total == 0:
            return 1.0
        covered = len(result.get("flight_changes", []))
        return min(1.0, covered / total)

    @staticmethod
    def get_strategy_name():
        return "TimeShiftStrategy"

    def _sort_key(self, f):
        """航班排序键"""
        dep = f.departure_time if hasattr(f, 'departure_time') else ""
        return dep or "9999"
