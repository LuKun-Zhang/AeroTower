"""旅客状态机 — 仿真引擎旅客流模型"""

import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


# 各机型典型客座数
AIRCRAFT_CAPACITY = {
    'A319': 160,
    'A320': 180,
    'A321': 220,
    'A330': 280,
    'B737': 170,
    'B738': 180,
    'default': 160,
}


def get_capacity(ac_type: str) -> int:
    return AIRCRAFT_CAPACITY.get(ac_type, AIRCRAFT_CAPACITY['default'])


class PassengerStatus(Enum):
    CHECK_IN = "check_in"       # 值机
    SECURITY = "security"       # 安检
    WAITING = "waiting"         # 候机
    BOARDING = "boarding"       # 登机
    IN_FLIGHT = "in_flight"     # 飞行中
    ARRIVAL = "arrival"         # 到达
    BAGGAGE = "baggage"         # 取行李
    EXIT = "exit"               # 离开
    STRANDED = "stranded"       # 滞留（延误/取消）

    TRANSIT = "transit"         # 中转：等待下一程
    REBOOKED = "rebooked"       # 已改签


@dataclass
class Passenger:
    """单个旅客"""
    pax_id: str
    current_flight: str        # 当前航班 flight_id
    status: PassengerStatus = PassengerStatus.CHECK_IN
    # 如果是中转旅客，记录下一程
    next_flight: Optional[str] = None  # 下一程 flight_id
    is_transit: bool = False
    # 统计
    delay_minutes: int = 0     # 累计延误分钟

    def to_dict(self) -> dict:
        return {
            'pax_id': self.pax_id,
            'current_flight': self.current_flight,
            'status': self.status.value,
            'is_transit': self.is_transit,
            'next_flight': self.next_flight,
            'delay_minutes': self.delay_minutes,
        }


@dataclass
class PassengerFlow:
    """旅客流管理"""

    # flight_id -> list of Passenger
    passengers: dict = field(default_factory=dict)
    # 每个航班旅客已分配标记
    _generated: set = field(default_factory=set)
    # 可选：实验注入的 random.Random 实例；None 时退回模块级 random
    rng: object = field(default=None, repr=False)

    def generate_for_flight(self, flight_id: str, ac_type: str,
                            all_flight_ids: list = None) -> list:
        """为航班生成旅客。返回生成的旅客列表。"""
        if flight_id in self._generated:
            return self.passengers.get(flight_id, [])

        rng = self.rng or random
        capacity = get_capacity(ac_type)
        # 随机客座率 65%~100%
        load_factor = rng.uniform(0.65, 1.0)
        pax_count = max(20, int(capacity * load_factor))

        # 中转旅客比例 5%~20%
        transit_ratio = rng.uniform(0.05, 0.20)
        transit_count = max(0, min(int(pax_count * transit_ratio), pax_count // 3))

        pax_list = []
        for i in range(pax_count):
            is_transit = i < transit_count
            # 随机分配下游航班（从中转旅客中）
            next_f = None
            if is_transit and all_flight_ids and len(all_flight_ids) > 1:
                candidates = [f for f in all_flight_ids if f != flight_id]
                next_f = rng.choice(candidates) if candidates else None

            p = Passenger(
                pax_id=f"{flight_id}_{i}",
                current_flight=flight_id,
                status=PassengerStatus.CHECK_IN,
                is_transit=is_transit,
                next_flight=next_f,
            )
            pax_list.append(p)

        self.passengers[flight_id] = pax_list
        self._generated.add(flight_id)
        return pax_list

    def apply_delay_to_flight(self, flight_id: str, delay_min: int):
        """航班延误：所有旅客标记延迟"""
        for p in self.passengers.get(flight_id, []):
            p.delay_minutes += delay_min
            if p.status not in (PassengerStatus.ARRIVAL, PassengerStatus.EXIT,
                                PassengerStatus.BAGGAGE, PassengerStatus.REBOOKED):
                p.status = PassengerStatus.STRANDED

    def cancel_flight_pax(self, flight_id: str):
        """航班取消：旅客全部滞留"""
        for p in self.passengers.get(flight_id, []):
            p.status = PassengerStatus.STRANDED

    def advance_check_in(self, flight_id: str, departure_min: int, current_min: int):
        """推进旅客值机→安检→候机流程"""
        for p in self.passengers.get(flight_id, []):
            if p.status == PassengerStatus.CHECK_IN:
                # 出发前120min 开始值机
                if departure_min - current_min <= 120:
                    p.status = PassengerStatus.SECURITY
            elif p.status == PassengerStatus.SECURITY:
                # 安检后 30min 进入候机
                if departure_min - current_min <= 90:
                    p.status = PassengerStatus.WAITING
            elif p.status == PassengerStatus.WAITING:
                # 起飞前 30min 登机
                if departure_min - current_min <= 30:
                    p.status = PassengerStatus.BOARDING

    def advance_departed(self, flight_id: str):
        """航班起飞：所有旅客进入 IN_FLIGHT"""
        for p in self.passengers.get(flight_id, []):
            p.status = PassengerStatus.IN_FLIGHT

    def advance_arrived(self, flight_id: str):
        """航班到达：旅客进入到达流程"""
        for p in self.passengers.get(flight_id, []):
            if p.status == PassengerStatus.IN_FLIGHT:
                if p.is_transit and p.next_flight:
                    p.status = PassengerStatus.TRANSIT
                else:
                    p.status = PassengerStatus.BAGGAGE

    def get_airport_stranded(self, airport: str, flight_dep_map: dict) -> int:
        """获取某机场的滞留旅客数"""
        count = 0
        for flight_id, pax_list in self.passengers.items():
            dep_airport = flight_dep_map.get(flight_id, '')
            if dep_airport == airport:
                count += sum(1 for p in pax_list if p.status == PassengerStatus.STRANDED)
        return count

    def get_total_in_flight(self) -> int:
        """在途旅客总数"""
        return sum(
            1 for pax_list in self.passengers.values()
            for p in pax_list if p.status == PassengerStatus.IN_FLIGHT
        )

    def get_total_delayed(self) -> int:
        """延误旅客总数"""
        return sum(
            1 for pax_list in self.passengers.values()
            for p in pax_list if p.delay_minutes > 0
        )

    @property
    def total_passengers(self) -> int:
        return sum(len(pl) for pl in self.passengers.values())
