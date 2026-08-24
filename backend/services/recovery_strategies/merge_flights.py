"""航班合并策略 — 将两个或多个上座率低的航班合并为一个

适用场景：
  - 资源严重不足时，合并临近时间和航线的航班
  - 需求端波动（乘客少，合并后可提高上座率）
  - 作为其他策略的补充，降低整体航班取消率

原理：
  1. 找出时间和航线相近的受影响航班对
  2. 合并为一个大航班（取较早的起飞时间，较大的载客量）
  3. 释放多余的飞机/机组/登机口资源
"""

from .base_strategy import BaseRecoveryStrategy
from ...models.recovery_plan import ChangeType


class MergeFlightsStrategy(BaseRecoveryStrategy):
    """航班合并策略"""

    MAX_DEPARTURE_GAP = 120  # 最大起飞时间差（分钟）
    SAME_AIRPORT_SAME_DEST = True  # 是否要求同机场同目的地

    def can_apply(self):
        """当影响航班数较多且资源不足时启用"""
        return self.impact.total_impacted_flights >= 4

    def apply(self):
        """执行航班合并"""
        result = {
            "flight_changes": [],
            "aircraft_changes": [],
            "crew_changes": [],
            "gate_changes": [],
            "runway_changes": [],
            "side_effects": [],
            "merged_flights": [],
        }

        flights = self.schedule.get("flights", [])
        timeline = self.impact.timeline_changes or {}

        # 找出时间相近的受影响航班
        all_impacted = set(timeline.keys()) | set(self.impact.direct_impacted_flights)

        impacted_list = [
            f for f in flights
            if (f.flight_id if hasattr(f, 'flight_id') else str(f)) in all_impacted
        ]

        # 按起飞时间和航线分组
        merged = set()
        for i, f1 in enumerate(impacted_list):
            f1_id = f1.flight_id if hasattr(f1, 'flight_id') else str(f1)
            if f1_id in merged:
                continue

            dep1 = self._dep_time(f1)
            dep_ap1 = f1.departure_airport if hasattr(f1, 'departure_airport') else ""
            arr_ap1 = f1.arrival_airport if hasattr(f1, 'arrival_airport') else ""

            for j, f2 in enumerate(impacted_list):
                if i == j:
                    continue
                f2_id = f2.flight_id if hasattr(f2, 'flight_id') else str(f2)
                if f2_id in merged:
                    continue

                dep2 = self._dep_time(f2)
                dep_ap2 = f2.departure_airport if hasattr(f2, 'departure_airport') else ""
                arr_ap2 = f2.arrival_airport if hasattr(f2, 'arrival_airport') else ""

                # 检查是否可合并
                if not self._can_merge(dep1, dep2, dep_ap1, dep_ap2, arr_ap1, arr_ap2):
                    continue

                # 执行合并（保留 f1，取消 f2）
                result["flight_changes"].append({
                    "flight_id": f1_id,
                    "change_type": ChangeType.MERGE,
                    "old_value": f1_id,
                    "new_value": f"merged_with_{f2_id}",
                    "reason": f"航班合并：{f1_id} 并入 {f2_id}",
                })
                result["merged_flights"].append({
                    "kept": f1_id,
                    "merged": f2_id,
                    "reason": f"相近航线({dep_ap1}→{arr_ap1} & {dep_ap2}→{arr_ap2})，时间差{self._time_gap(dep1, dep2)}分钟",
                })
                merged.add(f1_id)
                merged.add(f2_id)
                break

        return result

    def evaluate(self, result):
        """评估合并效果"""
        merged = len(result.get("merged_flights", []))
        if merged == 0:
            return 0.0
        # 每合并一对减少2个受影响航班
        reduction = merged * 2 / max(self.impact.total_impacted_flights, 1)
        return min(1.0, reduction)

    @staticmethod
    def get_strategy_name():
        return "MergeFlightsStrategy"

    def _can_merge(self, dep1, dep2, ap1_dep, ap2_dep, ap1_arr, ap2_arr):
        """判断两个航班是否可以合并"""
        if not dep1 or not dep2:
            return False
        gap = self._time_gap(dep1, dep2)
        if gap > self.MAX_DEPARTURE_GAP:
            return False
        if self.SAME_AIRPORT_SAME_DEST:
            return ap1_dep == ap2_dep and ap1_arr == ap2_arr
        return ap1_dep == ap2_dep

    def _dep_time(self, flight):
        """获取航班起飞时间（HH:MM）"""
        return flight.departure_time if hasattr(flight, 'departure_time') else ""

    def _time_gap(self, t1, t2):
        """两个 HH:MM 时间差（分钟）"""
        try:
            parts1 = t1.split(":")
            parts2 = t2.split(":")
            m1 = int(parts1[0]) * 60 + int(parts1[1])
            m2 = int(parts2[0]) * 60 + int(parts2[1])
            return abs(m2 - m1)
        except (ValueError, IndexError):
            return 9999
