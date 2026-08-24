"""任务链重规划策略 — 重新编排受影响飞机的任务序列

适用场景：
  - 一架飞机故障，需要将故障机后续航班分散到其他飞机
  - 多架飞机受影响后，整体重排任务链
  - 机组超时后需要重新分配航班

原理：
  1. 收集受影响的飞机任务链
  2. 找出可接替的飞机（有空闲时段的）
  3. 将受影响航班插入到其他飞机的合适时段
"""

from .base_strategy import BaseRecoveryStrategy
from ...models.recovery_plan import ChangeType


class ChainReplanningStrategy(BaseRecoveryStrategy):
    """任务链重规划策略"""

    MIN_TURNAROUND = 45  # 最小过站时间（分钟）

    def can_apply(self):
        """有多架飞机受影响时需要重规划"""
        return (
            len(self.impact.direct_impacted_aircraft) > 0 or
            self.impact.total_impacted_aircraft > 0
        )

    def apply(self):
        """执行链重规划"""
        result = {
            "flight_changes": [],
            "aircraft_changes": [],
            "crew_changes": [],
            "gate_changes": [],
            "runway_changes": [],
            "side_effects": [],
        }

        flights = self.schedule.get("flights", [])
        chains = self.schedule.get("chains", [])
        aircraft_map = self.schedule.get("aircraft_assignments", {})

        # 构建飞机 → 链索引
        aircraft_chains = {}
        for chain in chains:
            chain_fids = [
                f.flight_id if hasattr(f, 'flight_id') else str(f)
                for f in chain
            ]
            for fid in chain_fids:
                if fid in aircraft_map:
                    tail = aircraft_map[fid]
                    if tail not in aircraft_chains:
                        aircraft_chains[tail] = chain

        # 找出受影响飞机和正常飞机
        affected_tails = set(self.impact.direct_impacted_aircraft)
        all_tails = set(aircraft_map.values())
        healthy_tails = all_tails - affected_tails

        if not healthy_tails:
            result["side_effects"].append({
                "type": "no_healthy_aircraft",
                "detail": "没有可用的健康飞机来接替任务",
            })
            return result

        # 收集受影响飞机上的所有航班
        orphaned_flights = []
        for tail in affected_tails:
            for fid, assigned in aircraft_map.items():
                if assigned == tail:
                    orphaned_flights.append({
                        "flight_id": fid,
                        "from_aircraft": tail,
                    })

        # 按时间排序孤儿航班
        orphaned_flights.sort(key=lambda x: self._flight_time(x["flight_id"], flights))

        # 尝试将孤儿航班插入健康飞机
        healthy_chain_timeslots = {}
        for tail, chain in aircraft_chains.items():
            if tail in healthy_tails:
                healthy_chain_timeslots[tail] = self._get_free_slots(chain, flights)

        for orphan in orphaned_flights:
            fid = orphan["flight_id"]
            assigned = False
            for tail, slots in healthy_chain_timeslots.items():
                if self._can_fit(fid, flights, chain, slots):
                    result["aircraft_changes"].append({
                        "flight_id": fid,
                        "change_type": ChangeType.REASSIGN_AIRCRAFT,
                        "old_value": orphan["from_aircraft"],
                        "new_value": tail,
                        "reason": f"任务链重规划：从{orphan['from_aircraft']}转至{tail}",
                    })
                    # 更新该飞机的空闲时段（标记该时间段已占用）
                    assigned = True
                    break

            if not assigned:
                result["side_effects"].append({
                    "type": "orphaned_flight",
                    "flight_id": fid,
                    "detail": f"航班 {fid} 无法分配到健康飞机",
                })

        return result

    def evaluate(self, result):
        """评估分配成功率"""
        orphaned = sum(
            1 for s in result.get("side_effects", [])
            if s.get("type") == "orphaned_flight"
        )
        total = orphaned + len(result.get("aircraft_changes", []))
        if total == 0:
            return 1.0
        return (total - orphaned) / total

    @staticmethod
    def get_strategy_name():
        return "ChainReplanningStrategy"

    def _flight_time(self, fid, flights):
        """获取航班时间"""
        for f in flights:
            f_id = f.flight_id if hasattr(f, 'flight_id') else str(f)
            if f_id == fid:
                return f.departure_time if hasattr(f, 'departure_time') else "99:99"
        return "99:99"

    def _get_free_slots(self, chain, flights):
        """获取任务链中的空闲时段"""
        if not chain:
            return []
        chain_fids = [
            f.flight_id if hasattr(f, 'flight_id') else str(f)
            for f in chain
        ]
        slots = []
        for i in range(len(chain_fids) - 1):
            fid_a = chain_fids[i]
            fid_b = chain_fids[i + 1]
            time_a = self._arrival_time(fid_a, flights)
            time_b = self._departure_time(fid_b, flights)
            if time_a and time_b:
                gap = self._time_diff_minutes(time_a, time_b)
                if gap > self.MIN_TURNAROUND * 2:
                    slots.append({
                        "before_flight": fid_b,
                        "gap_minutes": gap,
                        "free_from": time_a,
                        "free_to": time_b,
                    })
        return slots

    def _can_fit(self, orphan_fid, flights, chain, slots):
        """判断孤儿航班能否插入某个位置"""
        import datetime
        dep_time = self._departure_time(orphan_fid, flights)
        arr_time = self._arrival_time(orphan_fid, flights)
        if not dep_time or not arr_time:
            return False

        for slot in slots:
            # 需要的前后间隔
            dep_num = self._time_to_minutes(dep_time)
            arr_num = self._time_to_minutes(arr_time)
            free_from = self._time_to_minutes(slot["free_from"])
            free_to = self._time_to_minutes(slot["free_to"])

            need = (arr_num - dep_num) + 2 * self.MIN_TURNAROUND
            if free_to - free_from >= need:
                return True
        return False

    def _departure_time(self, fid, flights):
        for f in flights:
            f_id = f.flight_id if hasattr(f, 'flight_id') else str(f)
            if f_id == fid:
                return f.departure_time if hasattr(f, 'departure_time') else None
        return None

    def _arrival_time(self, fid, flights):
        for f in flights:
            f_id = f.flight_id if hasattr(f, 'flight_id') else str(f)
            if f_id == fid:
                return f.arrival_time if hasattr(f, 'arrival_time') else None
        return None

    def _time_diff_minutes(self, t1, t2):
        """两个 HH:MM 字符串的时间差（分钟）"""
        return self._time_to_minutes(t2) - self._time_to_minutes(t1)

    def _time_to_minutes(self, t):
        """HH:MM 字符串转分钟数"""
        if not t:
            return 0
        try:
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return 0
