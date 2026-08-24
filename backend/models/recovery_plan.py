"""恢复方案数据模型"""


class RecoveryPlanStatus:
    """恢复方案状态"""
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ChangeType:
    """变更类型"""
    CANCEL = "CANCEL"
    DELAY = "DELAY"
    REASSIGN_AIRCRAFT = "REASSIGN_AIRCRAFT"
    REASSIGN_CREW = "REASSIGN_CREW"
    REASSIGN_GATE = "REASSIGN_GATE"
    REASSIGN_RUNWAY = "REASSIGN_RUNWAY"
    MERGE = "MERGE"
    ADD = "ADD"


class RecoveryPlan:
    """恢复方案"""

    def __init__(self, plan_id, event_id, strategy="",
                 flight_changes=None, aircraft_changes=None,
                 crew_changes=None, gate_changes=None, runway_changes=None,
                 coverage_rate=0.0, total_delay_minutes=0,
                 avg_delay_minutes=0.0,
                 canceled_flights=None, added_flights=None,
                 merged_flights=None,
                 before_metrics=None, after_metrics=None,
                 improvement=None, side_effects=None,
                 status=RecoveryPlanStatus.DRAFT):
        self.plan_id = plan_id
        self.event_id = event_id
        self.strategy = strategy

        # 变更明细
        # flight_changes: [{flight_id, change_type, old_value, new_value, reason}]
        self.flight_changes = flight_changes or []
        self.aircraft_changes = aircraft_changes or []
        self.crew_changes = crew_changes or []
        self.gate_changes = gate_changes or []
        self.runway_changes = runway_changes or []

        # 方案指标
        self.coverage_rate = coverage_rate
        self.total_delay_minutes = total_delay_minutes
        self.avg_delay_minutes = avg_delay_minutes
        self.canceled_flights = canceled_flights or []
        self.added_flights = added_flights or []
        self.merged_flights = merged_flights or []

        # 对比指标
        self.before_metrics = before_metrics or {}
        self.after_metrics = after_metrics or {}
        self.improvement = improvement or {}
        self.side_effects = side_effects or []

        self.status = status

    def to_dict(self):
        return {
            "plan_id": self.plan_id,
            "event_id": self.event_id,
            "strategy": self.strategy,
            "flight_changes": self.flight_changes,
            "aircraft_changes": self.aircraft_changes,
            "crew_changes": self.crew_changes,
            "gate_changes": self.gate_changes,
            "runway_changes": self.runway_changes,
            "coverage_rate": self.coverage_rate,
            "total_delay_minutes": self.total_delay_minutes,
            "avg_delay_minutes": self.avg_delay_minutes,
            "canceled_flights": self.canceled_flights,
            "added_flights": self.added_flights,
            "merged_flights": self.merged_flights,
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "improvement": self.improvement,
            "side_effects": self.side_effects,
            "status": self.status,
        }

    @staticmethod
    def from_dict(data):
        return RecoveryPlan(
            plan_id=data.get("plan_id", ""),
            event_id=data.get("event_id", ""),
            strategy=data.get("strategy", ""),
            flight_changes=data.get("flight_changes", []),
            aircraft_changes=data.get("aircraft_changes", []),
            crew_changes=data.get("crew_changes", []),
            gate_changes=data.get("gate_changes", []),
            runway_changes=data.get("runway_changes", []),
            coverage_rate=data.get("coverage_rate", 0.0),
            total_delay_minutes=data.get("total_delay_minutes", 0),
            avg_delay_minutes=data.get("avg_delay_minutes", 0.0),
            canceled_flights=data.get("canceled_flights", []),
            added_flights=data.get("added_flights", []),
            merged_flights=data.get("merged_flights", []),
            before_metrics=data.get("before_metrics", {}),
            after_metrics=data.get("after_metrics", {}),
            improvement=data.get("improvement", {}),
            side_effects=data.get("side_effects", []),
            status=data.get("status", RecoveryPlanStatus.DRAFT),
        )
