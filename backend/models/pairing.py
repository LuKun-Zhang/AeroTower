"""机组任务链(Pairing)数据模型

Pairing 是连续1~5天的航班链，由同一机组从头执行到尾。
起止必须在同一基地，中间可在外站过夜。
"""
from datetime import datetime, timedelta


class Pairing:
    """任务链"""

    def __init__(self, pairing_id, flights, base):
        self.pairing_id = pairing_id
        self.flights = flights  # Flight 列表, 按时间排序
        self.base = base

    @property
    def num_days(self):
        """跨几天"""
        if not self.flights:
            return 0
        first = self._date_key(self.flights[0])
        last = self._date_key(self.flights[-1])
        d1 = datetime.strptime(first, '%Y-%m-%d')
        d2 = datetime.strptime(last, '%Y-%m-%d')
        return (d2 - d1).days + 1

    @property
    def num_flights(self):
        return len(self.flights)

    @property
    def total_flight_hours(self):
        return round(sum(f.timespan for f in self.flights) / 60, 1)

    @property
    def total_duty_hours(self):
        """总执勤小时数（最早起飞 → 最晚落地）"""
        if not self.flights:
            return 0
        start = min(f.departure_minutes for f in self.flights)
        end = max(f.arrival_minutes for f in self.flights)
        return round((end - start) / 60, 1)

    @property
    def start_date(self):
        if not self.flights:
            return ''
        return self._date_key(self.flights[0])

    @property
    def end_date(self):
        if not self.flights:
            return ''
        return self._date_key(self.flights[-1])

    def daily_flight_hours(self, date_key):
        """某天的飞行小时数"""
        total = 0
        for f in self.flights:
            if self._date_key(f) == date_key:
                total += f.timespan
        return round(total / 60, 1)

    def daily_duty_hours(self, date_key):
        """某天的执勤小时数"""
        day_flights = [f for f in self.flights if self._date_key(f) == date_key]
        if not day_flights:
            return 0
        start = min(f.departure_minutes for f in day_flights)
        end = max(f.arrival_minutes for f in day_flights)
        return round((end - start) / 60, 1)

    def flight_ids(self):
        return [f.flight_id for f in self.flights]

    def is_valid(self, max_daily_flight=8, max_daily_duty=14, min_rest=600):
        """检查整个pairing是否合规（每天的约束）"""
        dates = set()
        for f in self.flights:
            dates.add(self._date_key(f))

        for d in dates:
            # 日飞行上限
            if self.daily_flight_hours(d) > max_daily_flight:
                return False
            # 日执勤上限
            if self.daily_duty_hours(d) > max_daily_duty:
                return False

        # 检查过站时间（同一天相邻航班至少30分钟，隔天之间需≥10小时休息）
        sorted_f = sorted(self.flights, key=lambda f: f.departure_minutes)
        for i in range(len(sorted_f) - 1):
            gap = sorted_f[i+1].departure_minutes - sorted_f[i].arrival_minutes
            if self._date_key(sorted_f[i]) == self._date_key(sorted_f[i+1]):
                if gap < 30:  # 同天过站至少30分钟
                    return False
            else:
                if gap < min_rest:  # 跨天至少10小时休息
                    return False

        return True

    @property
    def num_overnights(self):
        """过夜次数：跨天边界数 = num_days - 1"""
        return max(0, self.num_days - 1)

    @property
    def utilization(self):
        """执勤利用率 = 实际飞行小时 / 总执勤小时（越高越好，理论max 1.0）"""
        duty = self.total_duty_hours
        if duty <= 0:
            return 0.0
        return round(self.total_flight_hours / duty, 3)

    @property
    def cost(self):
        """任务链成本评分（越低越优）。

        成本因素：
        - 过夜: 每次 +100（住宿费+补贴）
        - 执勤利用率惩罚: (1 - utilization) * 80（空闲时间浪费）
        - 航段费率: num_flights * 2（每段基本成本）
        - 跨天惩罚: (num_days - 1) * 5（长期占人）
        """
        overnight_cost = self.num_overnights * 100
        idle_penalty = (1 - self.utilization) * 80
        segment_cost = self.num_flights * 2
        span_penalty = (self.num_days - 1) * 5
        return round(overnight_cost + idle_penalty + segment_cost + span_penalty, 1)

    @property
    def efficiency(self):
        """效率评分 = 覆盖航班数 / 成本（越高越好）"""
        c = self.cost
        if c <= 0:
            return 0.0
        return round(self.num_flights / c, 4)

    def to_dict(self):
        return {
            'pairing_id': self.pairing_id,
            'base': self.base,
            'num_days': self.num_days,
            'num_flights': self.num_flights,
            'num_overnights': self.num_overnights,
            'total_flight_hours': self.total_flight_hours,
            'total_duty_hours': self.total_duty_hours,
            'utilization': self.utilization,
            'cost': self.cost,
            'efficiency': self.efficiency,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'flights': [{
                'flight_id': f.flight_id,
                'flight_no': f.flight_no,
                'departure_airport': f.departure_airport,
                'arrival_airport': f.arrival_airport,
                'date': self._date_key(f),
                'dep_time': f"{f.time_departure[3]:02d}:{f.time_departure[4]:02d}",
                'arr_time': f"{f.time_arrival[3]:02d}:{f.time_arrival[4]:02d}",
                'timespan': f.timespan,
                'ac_type': f.ac_type,
            } for f in self.flights],
        }

    @staticmethod
    def _date_key(f):
        y, m, d, *_ = f.time_departure
        return f"{y}-{m:02d}-{d:02d}"

    def __repr__(self):
        return f"<Pairing {self.pairing_id} {self.start_date}~{self.end_date} {self.num_flights}段 {self.total_flight_hours}h>"
