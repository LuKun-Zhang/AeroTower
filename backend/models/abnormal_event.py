"""异常事件数据模型"""


class AnomalyType:
    """异常类型枚举"""
    # 天气类（单机场级别）
    WEATHER_AIRPORT_CLOSURE = "weather_airport_closure"
    WEATHER_ENROUTE = "weather_enroute"
    WEATHER_CAPACITY = "weather_capacity"
    # 天气类（省份级别）
    WEATHER_STORM = "weather_storm"
    WEATHER_RAIN = "weather_rain"
    WEATHER_SNOW = "weather_snow"
    WEATHER_FOG = "weather_fog"
    WEATHER_TYPHOON = "weather_typhoon"
    # 飞机类
    AIRCRAFT_FAILURE = "aircraft_failure"
    AIRCRAFT_DIVERSION = "aircraft_diversion"
    AIRCRAFT_MAINTENANCE = "aircraft_maintenance"
    # 机组类
    CREW_SUBSTITUTION = "crew_substitution"
    CREW_ABSENCE = "crew_absence"
    CREW_OVERTIME = "crew_overtime"
    CREW_QUALIFICATION = "crew_qualification"
    # 跑道类
    RUNWAY_CLOSURE = "runway_closure"
    RUNWAY_DEGRADE = "runway_degrade"
    # 登机口类
    GATE_CLOSURE = "gate_closure"
    GATE_OCCUPIED = "gate_occupied"
    # 空域类
    FLOW_CONTROL = "flow_control"
    AIRSPACE_CLOSURE = "airspace_closure"

    ALL_TYPES = {
        WEATHER_AIRPORT_CLOSURE,
        WEATHER_ENROUTE,
        WEATHER_CAPACITY,
        WEATHER_STORM,
        WEATHER_RAIN,
        WEATHER_SNOW,
        WEATHER_FOG,
        WEATHER_TYPHOON,
        AIRCRAFT_FAILURE,
        AIRCRAFT_DIVERSION,
        AIRCRAFT_MAINTENANCE,
        CREW_SUBSTITUTION,
        CREW_ABSENCE,
        CREW_OVERTIME,
        CREW_QUALIFICATION,
        RUNWAY_CLOSURE,
        RUNWAY_DEGRADE,
        GATE_CLOSURE,
        GATE_OCCUPIED,
        FLOW_CONTROL,
        AIRSPACE_CLOSURE,
    }


class AnomalyPriority:
    """异常优先级"""
    P0_EMERGENCY = "P0"
    P1_CRITICAL = "P1"
    P2_NORMAL = "P2"
    P3_INFO = "P3"

    LABELS = {
        "P0": "紧急",
        "P1": "严重",
        "P2": "一般",
        "P3": "提示",
    }


class AnomalyStatus:
    """异常事件状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ANALYZING = "analyzing"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    RESOLVED = "resolved"


class AbnormalEvent:
    """异常事件"""

    def __init__(self, event_id, event_type, title, description="",
                 priority=AnomalyPriority.P2_NORMAL,
                 affected_airports=None, affected_aircraft=None,
                 affected_crew=None, affected_runways=None,
                 affected_gates=None, affected_flights=None,
                 start_time="", end_time="", duration_minutes=0,
                 delay_minutes=0, capacity_ratio=1.0, extra_flight_time=0,
                 severity=3,
                 status=AnomalyStatus.PENDING, created_at="", resolved_at=None):
        self.event_id = event_id
        self.event_type = event_type
        self.title = title
        self.description = description
        self.priority = priority

        self.affected_airports = affected_airports or []
        self.affected_aircraft = affected_aircraft or []
        self.affected_crew = affected_crew or []
        self.affected_runways = affected_runways or []
        self.affected_gates = affected_gates or []
        self.affected_flights = affected_flights or []

        self.start_time = start_time
        self.end_time = end_time
        self.duration_minutes = duration_minutes

        self.delay_minutes = delay_minutes
        self.capacity_ratio = capacity_ratio
        self.extra_flight_time = extra_flight_time
        self.severity = severity  # 天气严重程度 1-5

        self.status = status
        self.created_at = created_at
        self.resolved_at = resolved_at

        self.impact_report = None
        self.recovery_plan = None

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "affected_airports": self.affected_airports,
            "affected_aircraft": self.affected_aircraft,
            "affected_crew": self.affected_crew,
            "affected_runways": self.affected_runways,
            "affected_gates": self.affected_gates,
            "affected_flights": self.affected_flights,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "delay_minutes": self.delay_minutes,
            "capacity_ratio": self.capacity_ratio,
            "extra_flight_time": self.extra_flight_time,
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @staticmethod
    def from_dict(data):
        event = AbnormalEvent(
            event_id=data.get("event_id", ""),
            event_type=data.get("event_type", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            priority=data.get("priority", AnomalyPriority.P2_NORMAL),
            affected_airports=data.get("affected_airports", []),
            affected_aircraft=data.get("affected_aircraft", []),
            affected_crew=data.get("affected_crew", []),
            affected_runways=data.get("affected_runways", []),
            affected_gates=data.get("affected_gates", []),
            affected_flights=data.get("affected_flights", []),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            duration_minutes=data.get("duration_minutes", 0),
            delay_minutes=data.get("delay_minutes", 0),
            capacity_ratio=data.get("capacity_ratio", 1.0),
            extra_flight_time=data.get("extra_flight_time", 0),
            severity=data.get("severity", 3),
            status=data.get("status", AnomalyStatus.PENDING),
            created_at=data.get("created_at", ""),
            resolved_at=data.get("resolved_at"),
        )
        if data.get("impact_report"):
            event.impact_report = data["impact_report"]
        if data.get("recovery_plan"):
            event.recovery_plan = data["recovery_plan"]
        return event
