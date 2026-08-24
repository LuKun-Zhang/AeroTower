"""数据服务 - 统一的数据加载和管理"""
import json
import os

from ..config import GRAPH_DIR, EXCEL_DIR, DEFAULT_AC_TYPE, DEFAULT_LAYOUT
from ..services.aircraft_types import type_layout
from ..models.flight import Flight
from ..models.airport import Airport
from ..models.aircraft import Aircraft
from ..utils.data_loader import (
    load_flight_dicts, load_airport_excel, load_schedule_paths
)

# 飞机指标预设文件路径
_AIRCRAFT_INDEX_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'aircraft_index.json'
))

def _load_aircraft_index():
    """加载飞机指标预设文件，返回 {tail_no: {metrics}} 映射"""
    try:
        print(f"[DataService] 加载飞机指标: {_AIRCRAFT_INDEX_PATH}")
        with open(_AIRCRAFT_INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"[DataService] 飞机指标加载成功: {len(data)} 架")
        return {item['tail_no']: item for item in data}
    except Exception as e:
        print(f"[DataService] 飞机指标加载失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


class DataService:
    """数据服务 - 单例模式，避免重复读取文件"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._flights_loaded = False
        return cls._instance

    def load_all(self):
        """加载所有数据。航班/机场只加载一次，飞机每次重建以保证指标文件最新。"""
        if not self._flights_loaded:
            self._load_flights_and_airports()
            self._flights_loaded = True
        self._rebuild_aircrafts()

    def _load_flights_and_airports(self):
        """加载航班和机场数据（只需一次）"""
        # 1. 加载机场映射
        airport_excel = os.path.join(EXCEL_DIR, '（机场表）.xlsx')
        self.airport_map = load_airport_excel(airport_excel)

        # 2. 加载航班
        graph_file = os.path.join(
            GRAPH_DIR,
            f"{DEFAULT_AC_TYPE}_{DEFAULT_LAYOUT}_big.json"
        )
        flight_dicts = load_flight_dicts(graph_file, self.airport_map)
        self.flights = [
            Flight(
                flight_id=d['flight_id'],
                flight_no=d['flight_no'],
                ac_type=d['ac_type'],
                layout=d['layout'],
                departure_airport=d['departure_airport'],
                arrival_airport=d['arrival_airport'],
                time_departure=d['time_departure'],
                time_arrival=d['time_arrival'],
                timespan=d['timespan'],
                cost=d['cost'],
            )
            for d in flight_dicts
        ]

        # 3. 构建机场列表
        self.airports = {}
        self._build_airports()

        # 4. 加载已有排班路径
        output_file = os.path.join(os.path.dirname(GRAPH_DIR), 'output.json')
        self.schedule_paths = load_schedule_paths(output_file)

        print(f"[DataService] 航班/机场加载完成: {len(self.flights)} 航班, "
              f"{len(self.airports)} 机场")

    def _rebuild_aircrafts(self):
        """重新创建飞机列表，每次调用都会重新加载指标文件"""
        num_aircraft = (
            len(self.schedule_paths) if self.schedule_paths
            else max(12, len(self.flights) // 8)
        )
        self.aircrafts = self._build_aircrafts(num_aircraft)

    def _build_airports(self):
        """构建机场列表"""
        seen = set()
        for f in self.flights:
            for name in [f.departure_airport, f.arrival_airport]:
                if name and name not in seen:
                    seen.add(name)
                    self.airports[name] = Airport(
                        code='', name=name, city=name
                    )

    def _build_aircrafts(self, num):
        """创建飞机列表 — 从 aircraft_index.json 加载指标"""
        index_map = _load_aircraft_index()
        aircrafts = []
        for i in range(num):
            tail = f"B-{6388 + i}"
            # 查找预设指标
            metrics = index_map.get(tail, {})
            ac_type = metrics.get('ac_type', DEFAULT_AC_TYPE)
            aircrafts.append(Aircraft(
                ac_id=i + 1,
                ac_type=ac_type,
                layout=type_layout(ac_type),
                tail_no=tail,
                age_years=metrics.get('age_years', 5.0),
                total_flight_hours=metrics.get('total_flight_hours', 25000),
                maintenance_days=metrics.get('maintenance_days', 0),
                cost_per_hour=metrics.get('cost_per_hour', 20000),
                fuel_efficiency=metrics.get('fuel_efficiency', 0.90),
                last_overhaul=metrics.get('last_overhaul', ''),
                on_time_rate=metrics.get('on_time_rate', 0.95),
                cycles=metrics.get('cycles', 10000),
            ))
        return aircrafts

    def search_flight(self, flight_id=None, flight_no=None):
        """搜索航班"""
        results = []
        for f in self.flights:
            if flight_id and f.flight_id != flight_id:
                continue
            if flight_no and f.flight_no != flight_no:
                continue
            results.append(f)
        return results

    def get_aircraft_by_id(self, ac_id):
        for a in self.aircrafts:
            if a.ac_id == ac_id:
                return a
        return None


# 全局数据服务实例
data_service = DataService()
