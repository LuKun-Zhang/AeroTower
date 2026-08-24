"""飞机数据模型"""


class Aircraft:
    """飞机"""
    # 综合指数权重
    _IDX_W_AGE = 0.25
    _IDX_W_HOURS = 0.20
    _IDX_W_COST = 0.20
    _IDX_W_EFFICIENCY = 0.15
    _IDX_W_MAINT = 0.10
    _IDX_W_ON_TIME = 0.10

    # 指数参考值
    _MAX_AGE = 18.0
    _MAX_HOURS = 53000
    _MAX_COST = 25000
    _MIN_COST = 18000

    def __init__(self, ac_id, ac_type, layout, tail_no='', base='',
                 age_years=5.0, total_flight_hours=25000, maintenance_days=0,
                 cost_per_hour=20000, fuel_efficiency=0.90,
                 last_overhaul='', on_time_rate=0.95, cycles=10000):
        self.ac_id = ac_id
        self.ac_type = ac_type       # A319 / A320 / A321
        self.layout = layout          # C8Y124
        self.tail_no = tail_no        # 注册号 B-xxxx
        self.base = base              # 所属基地（成都/重庆/昆明等）

        # 飞机状态指标
        self.age_years = age_years
        self.total_flight_hours_idx = total_flight_hours
        self.maintenance_days = maintenance_days
        self.cost_per_hour = cost_per_hour
        self.fuel_efficiency = fuel_efficiency
        self.last_overhaul = last_overhaul
        self.on_time_rate = on_time_rate
        self.cycles = cycles

        # 运行时数据
        self.assigned_flights = []    # 分配的任务列表

        # 综合质量指数（0~100）
        self.quality_index = self._compute_quality_index()
        # 建议日航班上限：老飞机少飞，新飞机可多飞
        self.max_daily_flights = self._compute_max_flights()

    def _compute_quality_index(self):
        """计算飞机综合质量指数，越高越好（0~100）

        指标权重：
        - 机龄：飞机越新越高（25%）
        - 飞行小时：越低越高（20%）
        - 小时平均成本：越低越高（20%）
        - 燃油效率：越高越高（15%）
        - 维护天数：越少越高（10%）
        - 准点率：越高越高（10%）
        """
        score = 0
        score += max(0, (1 - self.age_years / self._MAX_AGE)) * 100 * self._IDX_W_AGE
        score += max(0, (1 - self.total_flight_hours_idx / self._MAX_HOURS)) * 100 * self._IDX_W_HOURS
        score += max(0, (1 - (self.cost_per_hour - self._MIN_COST) / (self._MAX_COST - self._MIN_COST))) * 100 * self._IDX_W_COST
        score += max(0, min(1, self.fuel_efficiency)) * 100 * self._IDX_W_EFFICIENCY
        score += max(0, (1 - self.maintenance_days / 7.0)) * 100 * self._IDX_W_MAINT
        score += max(0, self.on_time_rate) * 100 * self._IDX_W_ON_TIME
        return round(score, 1)

    def _compute_max_flights(self):
        """根据综合指数比例映射每日最大航班数 (4~14)"""
        return max(4, min(14, round(4 + self.quality_index / 100.0 * 10)))

    def add_flight(self, flight):
        """添加航班到排班列表，按起飞时间排序，自动检查时间冲突"""
        dep = flight.departure_minutes
        arr = flight.arrival_minutes
        for i, f in enumerate(self.assigned_flights):
            _dep = f.departure_minutes
            _arr = f.arrival_minutes
            # 两航班重叠：已存在航班与待加入航班时间交织
            if not (arr <= _dep or dep >= _arr):
                return False  # 时间冲突，拒绝
        self.assigned_flights.append(flight)
        self.assigned_flights.sort(key=lambda f: f.departure_minutes)
        return True

    def can_add_flight(self, flight):
        """仅检查时间是否冲突，不实际添加"""
        dep = flight.departure_minutes
        arr = flight.arrival_minutes
        for f in self.assigned_flights:
            if not (arr <= f.departure_minutes or dep >= f.arrival_minutes):
                return False
        return True

    @property
    def utilization(self):
        """利用率：总飞行时间 / 可用时间"""
        if not self.assigned_flights:
            return 0.0
        total_span = sum(f.timespan for f in self.assigned_flights)
        return round(total_span / (18 * 60) * 100, 1)

    @property
    def idle_time(self):
        """空闲时间（分钟）"""
        if len(self.assigned_flights) < 2:
            return 0
        idle = 0
        for i in range(len(self.assigned_flights) - 1):
            gap = (self.assigned_flights[i + 1].departure_minutes
                   - self.assigned_flights[i].arrival_minutes)
            if gap > 0:
                idle += gap
        return idle

    def to_dict(self):
        return {
            'ac_id': self.ac_id,
            'ac_type': self.ac_type,
            'layout': self.layout,
            'tail_no': self.tail_no,
            'base': self.base,
            'flight_count': len(self.assigned_flights),
            'utilization': self.utilization,
            'idle_time': self.idle_time,
            'quality_index': self.quality_index,
            'max_daily_flights': self.max_daily_flights,
            'age_years': self.age_years,
            'total_flight_hours': self.total_flight_hours_idx,
            'maintenance_days': self.maintenance_days,
            'cost_per_hour': self.cost_per_hour,
            'fuel_efficiency': self.fuel_efficiency,
            'last_overhaul': self.last_overhaul,
            'on_time_rate': self.on_time_rate,
            'cycles': self.cycles,
            'assigned_flights': [f.to_dict() for f in self.assigned_flights],
        }

    def __repr__(self):
        return f"<Aircraft {self.ac_type} {self.tail_no} base={self.base} idx={self.quality_index}>"
