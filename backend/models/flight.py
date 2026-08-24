"""航班数据模型"""


class Flight:
    """单个航班实例"""

    def __init__(self, flight_id, flight_no, ac_type, layout,
                 departure_airport, arrival_airport,
                 time_departure, time_arrival, timespan, cost=0):
        self.flight_id = flight_id
        self.flight_no = flight_no
        self.ac_type = ac_type
        self.layout = layout
        self.departure_airport = departure_airport
        self.arrival_airport = arrival_airport
        self.time_departure = time_departure  # (year, month, day, hour, minute)
        self.time_arrival = time_arrival
        self.timespan = timespan  # 分钟
        self.cost = cost

    @property
    def departure_minutes(self):
        """返回起飞时间（从月初算起的分钟数）"""
        t = self.time_departure
        try:
            month, day, hour, minute = int(t[1]), int(t[2]), int(t[3]), int(t[4])
            return (month - 11) * 30 * 24 * 60 + day * 24 * 60 + hour * 60 + minute
        except (ValueError, TypeError, IndexError):
            return 0

    @property
    def arrival_minutes(self):
        """返回到达时间（从月初算起的分钟数）"""
        t = self.time_arrival
        try:
            month, day, hour, minute = int(t[1]), int(t[2]), int(t[3]), int(t[4])
            return (month - 11) * 30 * 24 * 60 + day * 24 * 60 + hour * 60 + minute
        except (ValueError, TypeError, IndexError):
            return 0

    def can_connect_to(self, other, min_gap=60):
        """判断本航班结束后能否衔接下一个航班（默认最少间隔60分钟）
        必须同时满足：
        1. 时间衔接：到达时间 + 最小间隔 <= 下一班出发时间
        2. 空间衔接：到达机场 == 下一班出发机场（飞机不能瞬移）
        """
        return (self.arrival_minutes + min_gap <= other.departure_minutes
                and self.arrival_airport == other.departure_airport)

    def to_dict(self):
        return {
            'flight_id': self.flight_id,
            'flight_no': self.flight_no,
            'ac_type': self.ac_type,
            'layout': self.layout,
            'departure_airport': self.departure_airport,
            'arrival_airport': self.arrival_airport,
            'time_departure': self._format_time(self.time_departure),
            'time_arrival': self._format_time(self.time_arrival),
            'timespan': self.timespan,
            'cost': self.cost,
        }

    @staticmethod
    def _format_time(t):
        y, m, d, h, mi = t[0], t[1], t[2], t[3], t[4]
        return f"{y}-{m:02d}-{d:02d} {h:02d}:{mi:02d}"

    def __repr__(self):
        return f"<Flight {self.flight_no} {self.departure_airport}->{self.arrival_airport}>"
