"""旅客数据模型"""


class Passenger:
    """单个旅客"""

    def __init__(self, pax_id, origin, destination, date_str,
                 flight_no=None, seat=None, cabin='economy',
                 group_id=None, special=False):
        self.pax_id = pax_id           # 如 Pax-1130-00001
        self.origin = origin            # 出发城市
        self.destination = destination  # 目的城市
        self.date_str = date_str        # 日期字符串 "2020-11-30"
        self.flight_no = flight_no      # 分配的航班号
        self.seat = seat                # 座位号 如 "12A"
        self.cabin = cabin              # business / economy
        self.group_id = group_id        # 预订组 ID（同组旅客视为一起出行，尽量邻座）
        self.special = special          # 特殊旅客（老人/行动不便等，优先前排过道）

    def to_dict(self):
        return {
            'pax_id': self.pax_id,
            'origin': self.origin,
            'destination': self.destination,
            'date': self.date_str,
            'flight_no': self.flight_no,
            'seat': self.seat,
            'cabin': self.cabin,
            'group_id': self.group_id,
            'special': self.special,
        }

    def __repr__(self):
        return f"<Passenger {self.pax_id} {self.origin}->{self.destination}>"
