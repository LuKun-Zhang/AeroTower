"""影响报告数据模型"""


class ImpactReport:
    """异常事件影响分析报告"""

    def __init__(self, report_id, event_id,
                 direct_impacted_flights=None, direct_impacted_aircraft=None,
                 direct_impacted_crew=None, direct_impacted_gates=None,
                 direct_impacted_runways=None,
                 cascade_chains=None,
                 total_impacted_flights=0, total_impacted_aircraft=0,
                 total_impacted_crew=0, total_impacted_gates=0,
                 total_delay_minutes=0,
                 flights_to_cancel=None, crew_shortage_count=0,
                 gate_conflict_count=0,
                 timeline_changes=None, resource_availability=None):
        self.report_id = report_id
        self.event_id = event_id

        # 直接影响
        self.direct_impacted_flights = direct_impacted_flights or []
        self.direct_impacted_aircraft = direct_impacted_aircraft or []
        self.direct_impacted_crew = direct_impacted_crew or []
        self.direct_impacted_gates = direct_impacted_gates or []
        self.direct_impacted_runways = direct_impacted_runways or []

        # 级联链路
        # 每个元素: {flight_id, reason, delay_minutes, level}
        self.cascade_chains = cascade_chains or []

        # 汇总指标
        self.total_impacted_flights = total_impacted_flights
        self.total_impacted_aircraft = total_impacted_aircraft
        self.total_impacted_crew = total_impacted_crew
        self.total_impacted_gates = total_impacted_gates
        self.total_delay_minutes = total_delay_minutes

        self.flights_to_cancel = flights_to_cancel or []
        self.crew_shortage_count = crew_shortage_count
        self.gate_conflict_count = gate_conflict_count

        # 可视化数据
        # timeline_changes: {flight_id: {old_dep, new_dep, delay}}
        self.timeline_changes = timeline_changes or {}
        # resource_availability: 资源可用性时间线数据
        self.resource_availability = resource_availability or {}

    def to_dict(self):
        return {
            "report_id": self.report_id,
            "event_id": self.event_id,
            "direct_impacted_flights": self.direct_impacted_flights,
            "direct_impacted_aircraft": self.direct_impacted_aircraft,
            "direct_impacted_crew": self.direct_impacted_crew,
            "direct_impacted_gates": self.direct_impacted_gates,
            "direct_impacted_runways": self.direct_impacted_runways,
            "cascade_chains": self.cascade_chains,
            "total_impacted_flights": self.total_impacted_flights,
            "total_impacted_aircraft": self.total_impacted_aircraft,
            "total_impacted_crew": self.total_impacted_crew,
            "total_impacted_gates": self.total_impacted_gates,
            "total_delay_minutes": self.total_delay_minutes,
            "flights_to_cancel": self.flights_to_cancel,
            "crew_shortage_count": self.crew_shortage_count,
            "gate_conflict_count": self.gate_conflict_count,
            "timeline_changes": self.timeline_changes,
            "resource_availability": self.resource_availability,
        }

    @staticmethod
    def from_dict(data):
        return ImpactReport(
            report_id=data.get("report_id", ""),
            event_id=data.get("event_id", ""),
            direct_impacted_flights=data.get("direct_impacted_flights", []),
            direct_impacted_aircraft=data.get("direct_impacted_aircraft", []),
            direct_impacted_crew=data.get("direct_impacted_crew", []),
            direct_impacted_gates=data.get("direct_impacted_gates", []),
            direct_impacted_runways=data.get("direct_impacted_runways", []),
            cascade_chains=data.get("cascade_chains", []),
            total_impacted_flights=data.get("total_impacted_flights", 0),
            total_impacted_aircraft=data.get("total_impacted_aircraft", 0),
            total_impacted_crew=data.get("total_impacted_crew", 0),
            total_impacted_gates=data.get("total_impacted_gates", 0),
            total_delay_minutes=data.get("total_delay_minutes", 0),
            flights_to_cancel=data.get("flights_to_cancel", []),
            crew_shortage_count=data.get("crew_shortage_count", 0),
            gate_conflict_count=data.get("gate_conflict_count", 0),
            timeline_changes=data.get("timeline_changes", {}),
            resource_availability=data.get("resource_availability", {}),
        )
