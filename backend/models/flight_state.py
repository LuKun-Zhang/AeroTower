"""航班状态机 — 仿真引擎核心模型"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class FlightPhase(Enum):
    """航班运行阶段"""
    SCHEDULED = "scheduled"       # 计划中（尚未出发）
    PUSH_BACK = "push_back"       # 推出
    TAXI_OUT = "taxi_out"         # 滑出
    TAKEOFF = "takeoff"           # 起飞
    CLIMB = "climb"               # 爬升
    CRUISE = "cruise"             # 巡航
    DESCENT = "descent"           # 下降
    APPROACH = "approach"         # 进近
    LANDING = "landing"           # 着陆
    TAXI_IN = "taxi_in"           # 滑入
    PARKED = "parked"             # 靠桥/到达
    DELAYED = "delayed"           # 延误（异常）
    CANCELLED = "cancelled"       # 取消（异常）


# 阶段耗时常量（分钟）
PHASE_DURATION = {
    FlightPhase.PUSH_BACK: (3, 5),
    FlightPhase.TAXI_OUT: (5, 8),
    FlightPhase.CLIMB: (12, 18),
    FlightPhase.DESCENT: (12, 18),
    FlightPhase.APPROACH: (3, 5),
    FlightPhase.LANDING: (2, 3),
    FlightPhase.TAXI_IN: (5, 8),
}

# 正常阶段序列
NORMAL_SEQUENCE = [
    FlightPhase.PUSH_BACK,
    FlightPhase.TAXI_OUT,
    FlightPhase.TAKEOFF,
    FlightPhase.CLIMB,
    FlightPhase.CRUISE,
    FlightPhase.DESCENT,
    FlightPhase.APPROACH,
    FlightPhase.LANDING,
    FlightPhase.TAXI_IN,
    FlightPhase.PARKED,
]


@dataclass
class FlightState:
    """仿真中的航班状态追踪器"""

    flight_id: str
    flight_no: str
    ac_type: str
    departure_airport: str
    arrival_airport: str
    # 原始计划时间
    scheduled_dep: tuple    # (y, m, d, h, min)
    scheduled_arr: tuple    # (y, m, d, h, min)
    # 分钟数（从月初起算）
    dep_minutes: int = 0
    arr_minutes: int = 0
    # 实际时间（初始等于计划，受延误影响）
    actual_dep: tuple = None
    actual_arr: tuple = None
    # 仿真状态
    phase: FlightPhase = FlightPhase.SCHEDULED
    phase_elapsed: int = 0       # 当前阶段已过分钟数
    # 航路
    cruise_duration: int = 0     # 巡航阶段总分钟数
    flight_distance_km: float = 0.0
    # 延误信息
    delay_minutes: int = 0        # 总延误分钟数
    delay_reason: str = ""        # 延误原因
    # 位置（巡航阶段使用）
    dep_lat: float = 0.0
    dep_lng: float = 0.0
    arr_lat: float = 0.0
    arr_lng: float = 0.0
    # 旅客
    passenger_count: int = 0
    transit_count: int = 0
    # 事件日志
    event_log: list = field(default_factory=list)

    # 天气中断可逆记录（用于天气恢复时还原原始状态）
    _weather_disrupted: bool = field(default=False, repr=False)
    _weather_orig_phase: Optional[FlightPhase] = field(default=None, repr=False)
    _weather_orig_delay_minutes: int = field(default=0, repr=False)
    _weather_orig_delay_reason: str = field(default="", repr=False)

    def __post_init__(self):
        if self.actual_dep is None:
            self.actual_dep = self.scheduled_dep
        if self.actual_arr is None:
            self.actual_arr = self.scheduled_arr

    @property
    def is_active(self) -> bool:
        """是否仍活跃（未到达或未取消）"""
        return self.phase not in (FlightPhase.PARKED, FlightPhase.CANCELLED)

    @property
    def is_delayed(self) -> bool:
        return self.delay_minutes > 0 or self.phase == FlightPhase.DELAYED

    @property
    def is_cancelled(self) -> bool:
        return self.phase == FlightPhase.CANCELLED

    @property
    def is_airborne(self) -> bool:
        return self.phase in (
            FlightPhase.TAKEOFF, FlightPhase.CLIMB,
            FlightPhase.CRUISE, FlightPhase.DESCENT,
            FlightPhase.APPROACH,
        )

    @property
    def progress_ratio(self) -> float:
        """整个航班的完成进度 0.0 ~ 1.0"""
        if self.phase == FlightPhase.PARKED:
            return 1.0
        if self.phase in (FlightPhase.CANCELLED, FlightPhase.SCHEDULED):
            return 0.0
        if self.phase == FlightPhase.DELAYED:
            return 0.0

        # 已过的地面阶段
        ground_seq = [
            FlightPhase.PUSH_BACK, FlightPhase.TAXI_OUT,
            FlightPhase.TAXI_IN, FlightPhase.LANDING, FlightPhase.PARKED,
        ]
        ground_minutes = 0
        for ph in ground_seq:
            dur = PHASE_DURATION.get(ph)
            if dur:
                ground_minutes += (dur[0] + dur[1]) / 2
        for ph in (FlightPhase.CLIMB, FlightPhase.DESCENT, FlightPhase.APPROACH):
            dur = PHASE_DURATION.get(ph)
            if dur:
                ground_minutes += (dur[0] + dur[1]) / 2

        total = ground_minutes + self.cruise_duration
        if total == 0:
            return 0.0

        elapsed = self._elapsed_before_phase(self.phase) + self.phase_elapsed
        return min(elapsed / total, 1.0)

    def _elapsed_before_phase(self, phase: FlightPhase) -> int:
        """计算在当前阶段之前已经过去的总分钟数"""
        elapsed = 0
        for ph in NORMAL_SEQUENCE:
            if ph == phase:
                break
            dur = PHASE_DURATION.get(ph)
            if dur:
                elapsed += (dur[0] + dur[1]) / 2
            elif ph == FlightPhase.CRUISE:
                elapsed += self.cruise_duration
        return int(elapsed)

    @property
    def current_position(self) -> Optional[tuple]:
        """当前估计位置 (lat, lng)，仅空中阶段有效"""
        if not self.is_airborne:
            return None
        if self.phase == FlightPhase.TAKEOFF:
            return (self.dep_lat, self.dep_lng)

        cruise_dur = max(self.cruise_duration, 1)
        pre_cruise = 0
        post_cruise = 0
        for ph in (FlightPhase.CLIMB,):
            dur = PHASE_DURATION.get(ph)
            if dur:
                pre_cruise += (dur[0] + dur[1]) / 2
        for ph in (FlightPhase.DESCENT, FlightPhase.APPROACH):
            dur = PHASE_DURATION.get(ph)
            if dur:
                post_cruise += (dur[0] + dur[1]) / 2

        total = pre_cruise + cruise_dur + post_cruise
        if total == 0:
            return (self.dep_lat, self.dep_lng)

        elapsed = self._elapsed_before_phase(self.phase) + self.phase_elapsed
        ratio = min(elapsed / total, 1.0)

        lat = self.dep_lat + (self.arr_lat - self.dep_lat) * ratio
        lng = self.dep_lng + (self.arr_lng - self.dep_lng) * ratio
        return (round(lat, 5), round(lng, 5))

    def log(self, msg: str):
        self.event_log.append(msg)

    def apply_delay(self, minutes: int, reason: str = ""):
        """应用延误"""
        self.delay_minutes += minutes
        self.delay_reason = reason
        self.phase = FlightPhase.DELAYED
        self.log(f"延误 +{minutes}min: {reason}")

    def cancel(self, reason: str = ""):
        """取消航班"""
        self.phase = FlightPhase.CANCELLED
        self.delay_reason = reason
        self.log(f"取消: {reason}")

    def apply_planned_delay(self, minutes: int, reason: str = ""):
        """应用计划性延误（保持 SCHEDULED，由引擎按 dep_minutes + delay_minutes 延后起飞）"""
        self.delay_minutes = minutes
        self.delay_reason = reason

    def apply_weather_cancel(self, reason: str = ""):
        """应用天气取消（可逆）：记录原始状态后置 CANCELLED"""
        self._begin_weather_disruption()
        self.phase = FlightPhase.CANCELLED
        self.delay_reason = reason
        self.log(f"天气取消: {reason}")

    def apply_weather_delay(self, minutes: int, reason: str = ""):
        """应用天气延误（可逆）：记录原始状态后设置延误分钟数"""
        self._begin_weather_disruption()
        self.delay_minutes = minutes
        self.delay_reason = reason

    def clear_weather_disruption(self):
        """清除天气中断，还原到受影响前的状态（天气恢复时调用）"""
        if not self._weather_disrupted:
            return
        if self._weather_orig_phase is not None:
            self.phase = self._weather_orig_phase
        self.delay_minutes = self._weather_orig_delay_minutes
        self.delay_reason = self._weather_orig_delay_reason
        self._weather_disrupted = False
        self._weather_orig_phase = None
        self._weather_orig_delay_minutes = 0
        self._weather_orig_delay_reason = ""

    def _begin_weather_disruption(self):
        if self._weather_disrupted:
            return
        self._weather_orig_phase = self.phase
        self._weather_orig_delay_minutes = self.delay_minutes
        self._weather_orig_delay_reason = self.delay_reason
        self._weather_disrupted = True

    @property
    def weather_disruption(self) -> Optional[str]:
        """当前是否因天气中断：None 表示正常，'delay' 表示天气延误，'cancel' 表示天气取消。

        仅当处于可逆天气中断（_weather_disrupted）时返回有效值；天气恢复后被
        clear_weather_disruption 还原，自动变回 None，供前端实时增删调整面板。
        """
        if not self._weather_disrupted:
            return None
        return 'cancel' if self.phase == FlightPhase.CANCELLED else 'delay'

    def to_dict(self) -> dict:
        pos = self.current_position
        return {
            'flight_id': self.flight_id,
            'flight_no': self.flight_no,
            'ac_type': self.ac_type,
            'departure_airport': self.departure_airport,
            'arrival_airport': self.arrival_airport,
            'scheduled_dep': list(self.scheduled_dep),
            'scheduled_arr': list(self.scheduled_arr),
            'actual_dep': list(self.actual_dep),
            'actual_arr': list(self.actual_arr),
            'phase': self.phase.value,
            'phase_elapsed': self.phase_elapsed,
            'progress': round(self.progress_ratio * 100, 1),
            'delay_minutes': self.delay_minutes,
            'delay_reason': self.delay_reason,
            'is_active': self.is_active,
            'is_delayed': self.is_delayed,
            'is_cancelled': self.is_cancelled,
            'is_airborne': self.is_airborne,
            'weather_disruption': self.weather_disruption,
            'position': list(pos) if pos else None,
            'passenger_count': self.passenger_count,
            'transit_count': self.transit_count,
        }
