"""机场数据模型"""


class Airport:
    """机场"""

    def __init__(self, code, name, city='', lat=0, lng=0):
        self.code = code          # ICAO 代码 ZUUU
        self.name = name          # 中文名 成都
        self.city = city or name
        self.lat = lat
        self.lng = lng
        self.status = 'normal'    # normal / closed / restricted

    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'city': self.city,
            'lat': self.lat,
            'lng': self.lng,
            'status': self.status,
        }

    def __repr__(self):
        return f"<Airport {self.name} ({self.code})>"
