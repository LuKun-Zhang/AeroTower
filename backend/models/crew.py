"""机组人员数据模型"""

from datetime import datetime, timedelta

# CCAR-121 合规约束
CCAR121_7DAY_MAX_HOURS = 40    # 任意连续7日历日飞行 ≤ 40h
CCAR121_30DAY_MAX_HOURS = 100  # 任意连续30日历日飞行 ≤ 100h
CCAR121_MIN_REST_HOURS = 10    # 执勤间连续休息 ≥ 10h


class CrewMember:
    """机组人员"""

    ROLES = ['captain', 'first_officer', 'purser', 'attendant']
    ROLE_LABELS = {
        'captain': '机长',
        'first_officer': '副驾驶',
        'purser': '乘务长',
        'attendant': '乘务员',
    }

    def __init__(self, crew_id, name, role, qualifications=None,
                 base='成都', airline='四川航空', max_daily_hours=8, max_duty_hours=14):
        self.crew_id = crew_id
        self.name = name
        self.role = role
        self.qualifications = qualifications or []  # 可飞行的机型列表 ['A319','A320']
        self.base = base          # 所属基地机场
        self.airline = airline    # 所属航司
        self.max_daily_hours = max_daily_hours
        self.max_duty_hours = max_duty_hours
        self.assigned_flights = []
        self.team_id = -1         # 所属机组团队 ID

    @property
    def role_label(self):
        return self.ROLE_LABELS.get(self.role, self.role)

    def add_flight(self, flight, duty_start_min, duty_end_min):
        self.assigned_flights.append({
            'flight': flight,
            'duty_start_min': duty_start_min,
            'duty_end_min': duty_end_min,
        })

    @property
    def total_flight_hours(self):
        """全部航班飞行小时总和"""
        if not self.assigned_flights:
            return 0.0
        total = sum(a['flight'].timespan for a in self.assigned_flights)
        return round(total / 60, 1)

    @property
    def daily_flight_hours(self):
        """单日最大飞行小时数（按天分开统计）"""
        if not self.assigned_flights:
            return 0.0
        by_day = {}
        for a in self.assigned_flights:
            f = a['flight']
            dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            by_day[dk] = by_day.get(dk, 0) + f.timespan
        return round(max(by_day.values()) / 60, 1)

    @property
    def duty_hours(self):
        """单日最大执勤小时数（按天分开统计）"""
        if not self.assigned_flights:
            return 0.0
        by_day = {}
        for a in self.assigned_flights:
            f = a['flight']
            dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            smin = a['duty_start_min']
            emin = a['duty_end_min']
            if dk not in by_day:
                by_day[dk] = {'min_start': smin, 'max_end': emin}
            else:
                by_day[dk]['min_start'] = min(by_day[dk]['min_start'], smin)
                by_day[dk]['max_end'] = max(by_day[dk]['max_end'], emin)
        max_duty = 0
        for dk, bounds in by_day.items():
            max_duty = max(max_duty, bounds['max_end'] - bounds['min_start'])
        return round(max_duty / 60, 1)

    @property
    def _daily_hours_map(self):
        """返回 {date_key: total_minutes} 按天分组的飞行分钟数"""
        if not self.assigned_flights:
            return {}
        by_day = {}
        for a in self.assigned_flights:
            f = a['flight']
            dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            by_day[dk] = by_day.get(dk, 0) + f.timespan
        return by_day

    @property
    def _duty_days(self):
        """返回按日期键排序的执勤日期列表及对应 {min_start, max_end}"""
        if not self.assigned_flights:
            return []
        by_day = {}
        for a in self.assigned_flights:
            f = a['flight']
            dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            smin = a['duty_start_min']
            emin = a['duty_end_min']
            if dk not in by_day:
                by_day[dk] = {'min_start': smin, 'max_end': emin}
            else:
                by_day[dk]['min_start'] = min(by_day[dk]['min_start'], smin)
                by_day[dk]['max_end'] = max(by_day[dk]['max_end'], emin)
        return sorted(by_day.items())  # [(dk, {...}), ...]

    @property
    def _date_key_to_ordinal(self):
        """将日期键转换为序数（距离参考日的天数），用于滑动窗口"""
        dates = list(self._daily_hours_map.keys())
        if not dates:
            return {}
        # 按日期排序后计算距最早日期的天数
        sorted_dates = sorted(dates)
        base = datetime.strptime(sorted_dates[0], '%Y-%m-%d')
        return {dk: (datetime.strptime(dk, '%Y-%m-%d') - base).days for dk in dates}

    @property
    def seven_day_flight_hours(self):
        """任意连续7日历日飞行小时最大值（CCAR-121）"""
        dm = self._daily_hours_map
        if not dm:
            return 0.0
        d2o = self._date_key_to_ordinal
        # 按序数排列每日飞行小时
        ordered = sorted([(d2o[dk], dm[dk]) for dk in dm])
        pre = [0] * (ordered[-1][0] + 1)
        for d, mins in ordered:
            pre[d] = mins
        # 滑动窗口：7天
        max_hours = 0.0
        window_sum = 0
        left = 0
        for right, mins in enumerate(pre):
            window_sum += mins
            if right - left >= 7:
                window_sum -= pre[left]
                left += 1
            max_hours = max(max_hours, window_sum)
        return round(max_hours / 60, 1)

    @property
    def thirty_day_flight_hours(self):
        """任意连续30日历日飞行小时最大值（CCAR-121）"""
        dm = self._daily_hours_map
        if not dm:
            return 0.0
        d2o = self._date_key_to_ordinal
        ordered = sorted([(d2o[dk], dm[dk]) for dk in dm])
        pre = [0] * (ordered[-1][0] + 1)
        for d, mins in ordered:
            pre[d] = mins
        max_hours = 0.0
        window_sum = 0
        left = 0
        for right, mins in enumerate(pre):
            window_sum += mins
            if right - left >= 30:
                window_sum -= pre[left]
                left += 1
            max_hours = max(max_hours, window_sum)
        return round(max_hours / 60, 1)

    @property
    def min_rest_hours(self):
        """执勤间最小连续休息时间（CCAR-121: ≥10h）。
        计算连续执勤日之间、以及同日内连续执勤段之间的最小间隔。
        """
        if not self.assigned_flights:
            return -1  # 无排班，不适用

        # 收集所有执勤段：(日期键, 开始分钟, 结束分钟)，按时间排序
        segments = []
        for a in self.assigned_flights:
            f = a['flight']
            dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            segments.append((dk, a['duty_start_min'], a['duty_end_min']))

        # 按日期键+开始时间排序
        segments.sort(key=lambda x: (x[0], x[1]))

        # 合并同一天连续的执勤段
        duty_periods = []  # [(date_key, start_min, end_min)]
        for seg in segments:
            dk, st, ed = seg
            if duty_periods and duty_periods[-1][0] == dk and st <= duty_periods[-1][2] + 30:
                # 同天且间隔≤30分钟，视为连续执勤
                duty_periods[-1] = (dk, duty_periods[-1][1], max(duty_periods[-1][2], ed))
            else:
                duty_periods.append(seg)

        # 计算相邻执勤段之间的最小休息
        min_rest = float('inf')
        for i in range(1, len(duty_periods)):
            prev_end = duty_periods[i-1][2]
            curr_start = duty_periods[i][1]
            # 需要将日期差异转换为分钟
            prev_dk = duty_periods[i-1][0]
            curr_dk = duty_periods[i][0]
            prev_date = datetime.strptime(prev_dk, '%Y-%m-%d')
            curr_date = datetime.strptime(curr_dk, '%Y-%m-%d')
            day_diff = (curr_date - prev_date).days
            # 绝对分钟差 = 当前的开始 - (前一天结束 + day_diff * 1440)
            curr_start_abs = curr_start + day_diff * 1440
            rest = curr_start_abs - prev_end
            min_rest = min(min_rest, rest)

        if min_rest == float('inf'):
            return -1
        return round(min_rest / 60, 1)

    def is_over_limit(self):
        """检查是否超限（含 CCAR-121 约束）"""
        violations = []
        if self.daily_flight_hours > self.max_daily_hours:
            violations.append(f'日飞行{self.daily_flight_hours}h > 上限{self.max_daily_hours}h')
        if self.duty_hours > self.max_duty_hours:
            violations.append(f'日执勤{self.duty_hours}h > 上限{self.max_duty_hours}h')
        if self.seven_day_flight_hours > CCAR121_7DAY_MAX_HOURS:
            violations.append(f'7天飞行{self.seven_day_flight_hours}h > CCAR上限{CCAR121_7DAY_MAX_HOURS}h')
        if self.thirty_day_flight_hours > CCAR121_30DAY_MAX_HOURS:
            violations.append(f'30天飞行{self.thirty_day_flight_hours}h > CCAR上限{CCAR121_30DAY_MAX_HOURS}h')
        if self.min_rest_hours >= 0 and self.min_rest_hours < CCAR121_MIN_REST_HOURS:
            violations.append(f'休息间隔{self.min_rest_hours}h < CCAR下限{CCAR121_MIN_REST_HOURS}h')
        return violations

    def to_dict(self):
        return {
            'crew_id': self.crew_id,
            'name': self.name,
            'role': self.role,
            'role_label': self.ROLE_LABELS.get(self.role, self.role),
            'qualifications': self.qualifications,
            'base': self.base,
            'airline': self.airline,
            'team_id': self.team_id,
            'daily_flight_hours': self.daily_flight_hours,
            'total_flight_hours': self.total_flight_hours,
            'seven_day_flight_hours': self.seven_day_flight_hours,
            'thirty_day_flight_hours': self.thirty_day_flight_hours,
            'duty_hours': self.duty_hours,
            'min_rest_hours': self.min_rest_hours,
            'violations': self.is_over_limit(),
            'flight_count': len(self.assigned_flights),
            'assigned_flights': [
                {
                    'flight_id': a['flight'].flight_id,
                    'flight_no': a['flight'].flight_no,
                    'from': a['flight'].departure_airport,
                    'to': a['flight'].arrival_airport,
                    'date': f"{a['flight'].time_departure[0]}-{a['flight'].time_departure[1]:02d}-{a['flight'].time_departure[2]:02d}",
                    'duty_start_min': a['duty_start_min'],
                    'duty_end_min': a['duty_end_min'],
                }
                for a in self.assigned_flights
            ],
        }

    def __repr__(self):
        return f"<Crew {self.name} [{self.ROLE_LABELS.get(self.role)}]>"
