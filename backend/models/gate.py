"""登机口数据模型

v2: 新增跑道归属（runway_group）、滑行时间、运营阶段（下客/上客/过站保障）
"""


class Gate:
    """登机口

    每个登机口属于某一跑道的"登机口组"，滑行距离影响分配偏好。
    航班占用分三个运营阶段：下客(DEBOARD)、过站保障(TURNAROUND)、上客(BOARDING)。
    """

    GATE_TYPES = {
        'large': {'min_ac': 'A321', 'length': 65},
        'medium': {'min_ac': 'A319', 'length': 50},
        'small': {'min_ac': 'CRJ', 'length': 35},
    }

    # 运营阶段枚举
    OPS_ARRIVAL = 'arrival'       # 仅到达（终到）
    OPS_DEPARTURE = 'departure'   # 仅出发（始发）
    OPS_TURNAROUND = 'turnaround'  # 经停过站

    def __init__(self, gate_id, name, airport, gate_type='medium',
                 position=0, status='available',
                 runway_group=1, taxi_in_min=5, taxi_out_min=5):
        self.gate_id = gate_id
        self.name = name
        self.airport = airport
        self.gate_type = gate_type
        self.position = position
        self.status = status
        self.runway_group = runway_group       # 所属跑道编号(1/2/3)
        self.taxi_in_min = taxi_in_min         # 滑入耗时（分钟）
        self.taxi_out_min = taxi_out_min       # 滑出耗时（分钟）
        self.assigned_flights = []             # [{flight, gate_start, gate_end, ops_type, runway, taxi_in, taxi_out}, ...]

    def add_assignment(self, flight, start_min, end_min,
                       ops_type=None, runway=None, taxi_in=0, taxi_out=0):
        """新增航班分配（支持运营阶段）

        start_min / end_min 是登机口占用时间段（已包含滑行偏移）。
        """
        if ops_type is None:
            # 自动推断
            if flight.departure_airport == self.airport and flight.arrival_airport == self.airport:
                ops_type = self.OPS_TURNAROUND
            elif flight.arrival_airport == self.airport:
                ops_type = self.OPS_ARRIVAL
            else:
                ops_type = self.OPS_DEPARTURE

        self.assigned_flights.append({
            'flight': flight,
            'start_min': start_min,
            'end_min': end_min,
            'ops_type': ops_type,
            'runway': runway or self.runway_group,
            'taxi_in': taxi_in or self.taxi_in_min,
            'taxi_out': taxi_out or self.taxi_out_min,
        })

    @property
    def utilization(self):
        """利用率：占用时间 / 18小时"""
        if not self.assigned_flights:
            return 0.0
        total_occupied = 0
        for a in self.assigned_flights:
            total_occupied += a['end_min'] - a['start_min']
        return round(total_occupied / (18 * 60) * 100, 1)

    def to_dict(self):
        def fmt_min(m):
            h, mi = divmod(m % 1440, 60)
            return f"{h:02d}:{mi:02d}"

        ops_labels = {
            'arrival': '仅到达',
            'departure': '仅出发',
            'turnaround': '过站',
        }

        return {
            'gate_id': self.gate_id,
            'name': self.name,
            'airport': self.airport,
            'gate_type': self.gate_type,
            'position': self.position,
            'status': self.status,
            'runway_group': self.runway_group,
            'taxi_in_min': self.taxi_in_min,
            'taxi_out_min': self.taxi_out_min,
            'utilization': self.utilization,
            'flight_count': len(self.assigned_flights),
            'assigned_flights': [
                {
                    'flight': a['flight'].flight_no,
                    'flight_id': a['flight'].flight_id,
                    'ac_type': a['flight'].ac_type,
                    'direction': 'departure' if a['flight'].departure_airport == self.airport else 'arrival',
                    'from': a['flight'].departure_airport,
                    'to': a['flight'].arrival_airport,
                    'start_min': a['start_min'],
                    'end_min': a['end_min'],
                    'start_time': fmt_min(a['start_min']),
                    'end_time': fmt_min(a['end_min']),
                    'ops_type': a.get('ops_type', 'arrival'),
                    'ops_label': ops_labels.get(a.get('ops_type', 'arrival'), ''),
                    'runway': a.get('runway', self.runway_group),
                    'taxi_in': a.get('taxi_in', self.taxi_in_min),
                    'taxi_out': a.get('taxi_out', self.taxi_out_min),
                }
                for a in self.assigned_flights
            ],
        }

    def __repr__(self):
        return (f"<Gate {self.name} ({self.gate_type}) "
                f"at {self.airport} RWY{self.runway_group}>")
