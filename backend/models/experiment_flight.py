"""实验航班沿用 Flight 接口，以真实日期差计算跨月时间。"""
from datetime import datetime
from .flight import Flight


class ExperimentFlight(Flight):
    @property
    def departure_minutes(self):
        return int((datetime(*self.time_departure) - datetime(2026, 1, 1)).total_seconds() // 60)

    @property
    def arrival_minutes(self):
        return int((datetime(*self.time_arrival) - datetime(2026, 1, 1)).total_seconds() // 60)
