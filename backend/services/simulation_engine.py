"""模拟引擎 — 仿真时钟 + 航班状态推进 + 异常事件调度"""

import time
import math
import random
import threading
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Tuple

from ..models.flight import Flight
from ..models.flight_state import (
    FlightState, FlightPhase, PHASE_DURATION, NORMAL_SEQUENCE,
)
from ..models.passenger_state import PassengerFlow
from ..services.weather_service import WeatherService, WeatherType, WEATHER_CONFIG


# 巡航速度常量（km/h）
CRUISE_SPEED_KPH = {
    'A319': 830,
    'A320': 840,
    'A321': 840,
    'B737': 830,
    'B738': 840,
}


def haversine(lat1, lng1, lat2, lng2) -> float:
    """Haversine 大圆距离 (km)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_airport_coords() -> Dict[str, Tuple[float, float]]:
    """返回已知机场的中文名 → (lat, lng) 坐标映射"""
    # 主要机场坐标（来自前端 Map.vue geoCoordMap）
    return {
        '上海': (31.2891, 121.4648), '北京': (40.2539, 116.4551),
        '成都': (30.6700, 104.0600), '重庆': (29.5600, 106.5500),
        '昆明': (25.0400, 102.7200), '西安': (34.2600, 108.9400),
        '广州': (23.2196, 113.5107), '深圳': (22.5500, 114.1000),
        '杭州': (30.2500, 120.1600), '南京': (31.9208, 118.8062),
        '三亚': (18.2500, 109.5000), '海口': (20.0200, 110.3300),
        '武汉': (30.5800, 114.2800), '长沙': (28.2200, 112.9300),
        '厦门': (24.6478, 118.1689), '南宁': (23.1152, 108.4790),
        '乌鲁木齐': (43.5883, 87.6236), '兰州': (36.3043, 103.5901),
        '西宁': (36.6200, 101.7700), '银川': (38.4700, 106.2700),
        '呼和浩特': (40.4901, 111.4124), '哈尔滨': (45.3680, 127.9688),
        '长春': (43.8800, 125.3200), '沈阳': (41.8000, 123.4300),
        '大连': (39.4409, 122.2229), '天津': (39.4189, 117.4219),
        '济南': (36.6500, 116.9800), '青岛': (36.0700, 120.3800),
        '石家庄': (38.0400, 114.4800), '郑州': (34.7600, 113.6500),
        '太原': (37.9413, 112.3352), '合肥': (32.0581, 117.2900),
        '南昌': (28.6633, 116.0046), '福州': (26.0700, 119.3000),
        '珠海': (22.2700, 113.5800), '宁波': (29.6466, 121.5967),
        '温州': (28.0000, 120.7000), '拉萨': (29.6500, 91.1300),
        '丽江': (26.8700, 100.2300), '西双版纳': (22.0000, 100.8000),
        '绵阳': (31.4700, 104.7300), '宜宾': (28.7700, 104.6200),
        '泸州': (28.8700, 105.4400), '广元': (32.4300, 105.8400),
        '九寨沟': (33.2500, 103.9000), '康定': (30.0500, 101.9600),
        '稻城': (29.0500, 100.3000), '攀枝花': (26.5800, 101.7200),
        '西昌': (27.9000, 102.2700), '南通': (32.1625, 121.1023),
        '常州': (31.5582, 119.4543), '徐州': (34.2800, 117.1800),
        '揭阳': (23.5500, 116.3700), '北海': (21.6211, 109.3140),
        '琼海': (19.2300, 110.4600), '神农架': (31.7500, 110.6800),
        '鄂尔多斯': (39.8300, 109.7800), '邯郸': (36.6100, 114.4800),
        '吕梁': (37.5200, 111.1300), '林芝': (29.6800, 94.3700),
        '文山': (23.3800, 104.2500), '大理': (25.6100, 100.2300),
        '中卫': (37.5100, 105.1900), '夏河': (35.2000, 102.5200),
        '喀什': (39.4700, 75.9900), '铁岭': (42.2900, 123.8400),
        '鞍山': (41.1100, 123.0100), '烟台': (37.1800, 121.3800),
        '上饶': (28.4500, 117.9700), '阜阳': (32.8900, 115.8100),
        '芒市': (24.4300, 98.5900), '普洱': (22.7800, 100.9700),
    }


class SimulationEngine:
    """航班运营模拟引擎"""

    # 引擎状态
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"

    def __init__(self, rng=None):
        self._rng = rng
        self.status: str = self.IDLE
        self.speed: int = 1          # 倍速 1/2/5/10
        self.tick_minutes: int = 1   # 每 tick 推进的仿真分钟数
        self._current_minutes: int = 0  # 当前仿真时间（从 epoch 开始的分钟数）
        self._simulation_start: int = 0
        self._simulation_end: int = 0
        self._thread: Optional[threading.Thread] = None
        self._stop_flag: bool = False
        # 统一时钟驱动模式：True 时由前端 sync_time 确定性重算状态，
        # 不再独立推进线程，也不在 /snapshot 里重复叠加天气中断。
        self._synced_mode: bool = False

        # 航班状态字典 {flight_id: FlightState}
        self.flights: Dict[str, FlightState] = {}
        # 机场坐标缓存
        self._airport_coords: Dict[str, Tuple[float, float]] = {}

        # 子系统
        self.weather = WeatherService(rng=rng)
        self.passenger_flow = PassengerFlow(rng=rng)

        # 事件（异常事件注入队列）
        self._pending_events: List[dict] = []   # 待处理的注入事件
        self._active_events: List[dict] = []     # 当前生效的事件

        # 容量管理（受天气 + 机场异常影响）
        self._airport_capacity: Dict[str, float] = {}  # airport -> ratio

        # KPI 快照
        self.kpi: dict = self._init_kpi()

        # 回调
        self.on_tick: Optional[Callable] = None   # 每 tick 完成后回调

    # ───────── init / reset ─────────

    def reset(self):
        """重置引擎"""
        self.stop()
        self.status = self.IDLE
        self._current_minutes = 0
        self._synced_mode = False
        self.flights.clear()
        self._airport_coords = {}
        self._pending_events.clear()
        self._active_events.clear()
        self._airport_capacity.clear()
        self.passenger_flow = PassengerFlow(rng=self._rng)
        self.kpi = self._init_kpi()

    def load_flights(self, flights: List[Flight]):
        """从 Flight 列表初始化仿真航班状态"""
        self._airport_coords = load_airport_coords()
        airports = set()

        for f in flights:
            dep_name = f.departure_airport
            arr_name = f.arrival_airport
            airports.add(dep_name)
            airports.add(arr_name)

            dep_coords = self._airport_coords.get(dep_name)
            arr_coords = self._airport_coords.get(arr_name)

            # 航路计算
            cruise_speed = CRUISE_SPEED_KPH.get(f.ac_type, 830)
            distance = 500.0  # 默认
            if dep_coords and arr_coords:
                distance = haversine(dep_coords[0], dep_coords[1],
                                     arr_coords[0], arr_coords[1])
            cruise_duration = int(distance / cruise_speed * 60)

            # 出发时间转分钟
            t = f.time_departure
            try:
                dep_min = self._time_to_min(t)
            except Exception:
                dep_min = 0

            # 到达时间
            total_time = 0
            for ph in (FlightPhase.PUSH_BACK, FlightPhase.TAXI_OUT,
                       FlightPhase.CLIMB, FlightPhase.DESCENT,
                       FlightPhase.APPROACH, FlightPhase.LANDING,
                       FlightPhase.TAXI_IN):
                dur = PHASE_DURATION.get(ph)
                if dur:
                    total_time += (dur[0] + dur[1]) // 2
            total_time += cruise_duration
            arr_min = dep_min + total_time
            arr_time = self._min_to_time(arr_min)

            fs = FlightState(
                flight_id=f.flight_id,
                flight_no=f.flight_no,
                ac_type=f.ac_type,
                departure_airport=dep_name,
                arrival_airport=arr_name,
                scheduled_dep=t,
                scheduled_arr=f.time_arrival,
                dep_minutes=dep_min,
                arr_minutes=arr_min,
                cruise_duration=cruise_duration,
                flight_distance_km=round(distance, 1),
                dep_lat=dep_coords[0] if dep_coords else 0,
                dep_lng=dep_coords[1] if dep_coords else 0,
                arr_lat=arr_coords[0] if arr_coords else 0,
                arr_lng=arr_coords[1] if arr_coords else 0,
            )
            self.flights[f.flight_id] = fs

        # 初始化天气和容量
        self.weather.init_for_airports(list(airports))
        for ap in airports:
            self._airport_capacity[ap] = 1.0

        # 生成旅客
        all_ids = [f.flight_id for f in flights]
        for f in flights:
            pax = self.passenger_flow.generate_for_flight(f.flight_id, f.ac_type, all_ids)
            if f.flight_id in self.flights:
                self.flights[f.flight_id].passenger_count = len(pax)
                self.flights[f.flight_id].transit_count = sum(1 for p in pax if p.is_transit)

        # 设置仿真时间范围（使用分钟数）
        all_dep = [fs.dep_minutes for fs in self.flights.values()]
        all_arr = [fs.arr_minutes for fs in self.flights.values()]
        if all_dep:
            self._simulation_start = min(all_dep)
        if all_arr:
            self._simulation_end = max(all_arr) + 240  # 多跑 4 小时
        self._current_minutes = self._simulation_start

    # ───────── 控制 ─────────

    def start(self):
        if self.status == self.RUNNING:
            return
        self._synced_mode = False
        self.status = self.RUNNING
        self._stop_flag = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def pause(self):
        self.status = self.PAUSED

    def resume(self):
        if self.status == self.PAUSED:
            self.status = self.RUNNING

    def stop(self):
        self._stop_flag = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.status = self.IDLE

    def step(self):
        """单步执行一个 tick"""
        self._do_tick()

    def set_speed(self, speed: int):
        """设置倍速"""
        self.speed = max(1, min(speed, 10))

    def jump_to(self, target_minutes: int):
        """跳转到指定时间"""
        self._current_minutes = target_minutes

    def sync_to(self, minutes: int, plan: Optional[dict] = None):
        """将引擎时钟同步到「绝对业务分钟」，并确定性重算各航班状态。

        供「模拟大引擎」统一时钟驱动：前端天气 phase 映射出的绝对分钟（自
        2020-11-01 00:00 起算，与 _time_to_min 一致）是唯一时间源。引擎不再
        依靠独立线程推进，而是按该时间 + 天气中断计划重算航班是否起飞/到达，
        使航班页显示时间、飞机起降与底部统一时钟完全一致。
        """
        self._synced_mode = True
        self._current_minutes = int(minutes)
        for fs in self.flights.values():
            # 重置为纯计划状态（直接管理，绕过可逆机制避免与 snapshot 冲突）
            fs._weather_disrupted = False
            fs._weather_orig_phase = None
            fs._weather_orig_delay_minutes = 0
            fs._weather_orig_delay_reason = ""
            fs.delay_minutes = 0
            fs.delay_reason = ""

            # 叠加天气中断（取消/延误），仅对尚未起飞的航班生效
            d = None
            if plan:
                d = plan.get(fs.flight_id) or plan.get(str(fs.flight_id))
            if d and minutes < fs.dep_minutes:
                if d.get('type') == 'cancel':
                    fs.phase = FlightPhase.CANCELLED
                    fs.delay_reason = d.get('reason', '天气取消')
                    fs._weather_disrupted = True
                    fs._weather_orig_phase = FlightPhase.SCHEDULED
                else:
                    fs.delay_minutes = int(d.get('delay_minutes', 0) or 0)
                    fs.delay_reason = d.get('reason', '天气延误')
                    fs._weather_disrupted = True
                    fs._weather_orig_phase = FlightPhase.SCHEDULED
                    fs._weather_orig_delay_minutes = 0

            self._recompute_flight_phase(fs, minutes)
        self._update_kpi()

    def sync_frozen(self, minutes: int, plan: Optional[dict] = None, update_kpi: bool = True):
        """冻结计划重算（实验回放专用）。

        与 ``sync_to`` 的区别：计划是一次性冻结的，取消永久生效、延误永久叠加，
        因此可以直接跳到任意时刻而不失真（``sync_to`` 每次会清零延误，且只在
        起飞前应用取消，适合现场“计划随天气演变”的模式）。
        """
        self._synced_mode = True
        self._current_minutes = int(minutes)
        plan = plan or {}
        for fs in self.flights.values():
            d = plan.get(fs.flight_id) or plan.get(str(fs.flight_id))
            apply_from = (d or {}).get('apply_from')
            if d and apply_from is not None and self._current_minutes < int(apply_from):
                d = None
            if d:
                if d.get('type') == 'cancel':
                    fs.phase = FlightPhase.CANCELLED
                    fs.delay_reason = d.get('reason', '计划取消')
                else:
                    fs.delay_minutes = int(d.get('delay_minutes', 0) or 0)
                    fs.delay_reason = d.get('reason', '计划延误')
            else:
                if fs.phase == FlightPhase.CANCELLED:
                    fs.phase = FlightPhase.SCHEDULED
                    fs.phase_elapsed = 0
                fs.delay_minutes = 0
                fs.delay_reason = ''
            self._recompute_flight_phase(fs, self._current_minutes)
        if update_kpi:
            self._update_kpi()

    def _recompute_flight_phase(self, fs: FlightState, minutes: int):
        """按绝对分钟 + 有效延误重算航班阶段（取消/未起飞/空中/已到达）。"""
        if fs.phase == FlightPhase.CANCELLED:
            fs.phase_elapsed = 0
            fs.actual_dep = fs.scheduled_dep
            fs.actual_arr = fs.scheduled_arr
            return

        eff_dep = fs.dep_minutes + fs.delay_minutes
        eff_arr = fs.arr_minutes + fs.delay_minutes
        fs.actual_dep = self._min_to_tuple(eff_dep)
        fs.actual_arr = self._min_to_tuple(eff_arr)

        if minutes < eff_dep:
            fs.phase = FlightPhase.SCHEDULED
            fs.phase_elapsed = 0
        elif minutes >= eff_arr:
            fs.phase = FlightPhase.PARKED
            fs.phase_elapsed = 0
        else:
            # 空中阶段：统一记为 CRUISE，phase_elapsed 表示自起飞后已过分钟
            fs.phase = FlightPhase.CRUISE
            fs.phase_elapsed = max(0, minutes - eff_dep)

    # ───────── 注入事件 ─────────

    def inject_event(self, event_data: dict):
        """注入一个异常事件，立即或定时生效"""
        self._pending_events.append(event_data)

    def apply_disruption(self, plan: dict):
        """应用天气中断计划到航班状态（全量可逆重算）。

        plan 形如 {flight_id: {type: 'cancel'|'delay', delay_minutes, reason, ...}}。
        每次调用先清除上一轮天气中断，再按最新 plan 重新标记，
        保证天气恢复后航班自动还原，不再“一直标黄/取消”。
        只对未起飞的航班生效；已起飞航班不受天气中断影响。
        """
        # 1. 清除上一轮天气中断（可逆还原）
        for fs in self.flights.values():
            fs.clear_weather_disruption()

        if not plan:
            return

        # 2. 建立 flight_id 归一化索引：plan 的键来自 compute_disruption（统一 str），
        #    而引擎键来自原始 Flight.flight_id（可能是 int，如 data_service 加载的
        #    big_graph 数据）。若直接用 str 键去查 int 键字典会永远 miss，导致
        #    天气延误/取消既不生效、也无法清除。
        index = {str(k): fs for k, fs in self.flights.items()}

        for fid, d in plan.items():
            fs = self.flights.get(fid) or index.get(str(fid))
            if not fs or fs.is_airborne:
                continue
            if d.get('type') == 'cancel':
                fs.apply_weather_cancel(d.get('reason', '天气取消'))
            else:
                fs.apply_weather_delay(
                    d.get('delay_minutes', 0), d.get('reason', '天气延误'),
                )

    # ───────── 查询 ─────────

    def get_snapshot(self) -> dict:
        """返回当前完整快照"""
        flights = [fs.to_dict() for fs in self.flights.values()]
        weather = {}
        for k, w in self.weather.get_all_weather().items():
            wd = w.to_dict()
            coords = self._airport_coords.get(k, (0, 0))
            wd['lat'] = coords[0]
            wd['lng'] = coords[1]
            weather[k] = wd
        return {
            'status': self.status,
            'speed': self.speed,
            'current_time': self._min_to_time(self._current_minutes),
            'current_minutes': self._current_minutes,
            'sim_start': self._min_to_time(self._simulation_start),
            'sim_end': self._min_to_time(self._simulation_end),
            'progress_pct': self.progress_pct,
            'flights': flights,
            'weather': weather,
            'kpi': self.kpi,
            'events': self._active_events,
        }

    @property
    def current_time_str(self) -> str:
        return self._min_to_time(self._current_minutes)

    @property
    def current_hour(self) -> int:
        return self._current_minutes // 60

    @property
    def progress_pct(self) -> float:
        span = self._simulation_end - self._simulation_start
        if span <= 0:
            return 0
        return min(round((self._current_minutes - self._simulation_start) / span * 100, 1), 100.0)

    # ───────── 内部 ─────────

    def _run_loop(self):
        """主循环"""
        import traceback
        while not self._stop_flag:
            if self.status == self.RUNNING:
                try:
                    start = time.time()
                    self._do_tick()
                    elapsed_ms = (time.time() - start) * 1000
                    interval_ms = max(50, 200 // self.speed)  # 基础 200ms / tick
                    sleep_ms = max(0, interval_ms - elapsed_ms)
                    time.sleep(sleep_ms / 1000)
                except Exception as e:
                    traceback.print_exc()
                    self.log_event(f"引擎线程异常: {e}")
                    time.sleep(1)
            else:
                time.sleep(0.1)

    def _do_tick(self):
        """执行一个 tick"""

        # 1. 处理待注入事件
        self._process_pending_events()

        # 2. 天气更新（每小时）
        if self.current_hour != self._current_minutes // 60:
            weather_changes = self.weather.tick(self.current_hour)
            for ap, w in weather_changes.items():
                self._airport_capacity[ap] = max(
                    self._airport_capacity.get(ap, 1.0) * 0.5,
                    w.capacity_ratio,
                )
                if w.is_disrupted:
                    self.log_event(f"天气变化: {ap} {w.label} 容量→{w.capacity_ratio}")

        # 3. 推进航班状态
        for fs in self.flights.values():
            if not fs.is_active:
                continue
            self._advance_flight(fs)

        # 4. 过期事件清理
        self._expire_events()

        # 5. 更新 KPI
        self._update_kpi()

        # 6. 推进时间
        self._current_minutes += self.tick_minutes

        # 7. 结束检查
        if self._current_minutes >= self._simulation_end:
            self.status = self.IDLE

        # 8. 回调
        if self.on_tick:
            self.on_tick()

    def _advance_flight(self, fs: FlightState):
        """推进一个航班的状态机"""

        # 处理 DELAYED 状态
        if fs.phase == FlightPhase.DELAYED:
            fs.phase_elapsed += self.tick_minutes
            if fs.phase_elapsed >= fs.delay_minutes:
                fs.phase = FlightPhase.SCHEDULED
                fs.phase_elapsed = 0
                fs.log("延误结束，恢复计划")
            return

        # 处理 SCHEDULED：检查是否到出发时间
        if fs.phase == FlightPhase.SCHEDULED:
            dep_min = fs.dep_minutes + fs.delay_minutes
            if self._current_minutes >= dep_min:
                # 检查机场容量
                cap = self._airport_capacity.get(fs.departure_airport, 1.0)
                if cap < 0.3:
                    fs.apply_delay(60, f"{fs.departure_airport}容量不足")
                else:
                    fs.phase = FlightPhase.PUSH_BACK
                    fs.phase_elapsed = 0
                    fs.log("开始推出")
            return

        # 正常阶段推进
        elif fs.phase == FlightPhase.CRUISE:
            # 巡航：按巡航耗时推进
            fs.phase_elapsed += self.tick_minutes
            if fs.phase_elapsed >= fs.cruise_duration:
                fs.phase = FlightPhase.DESCENT
                fs.phase_elapsed = 0
                fs.log("开始下降")
        else:
            # 固定耗时阶段
            dur_range = PHASE_DURATION.get(fs.phase)
            if dur_range:
                dur = (dur_range[0] + dur_range[1]) / 2
                fs.phase_elapsed += self.tick_minutes
                if fs.phase_elapsed >= dur:
                    # 阶段结束，切换到下一阶段
                    self._transition_to_next(fs)

    def _transition_to_next(self, fs: FlightState):
        current_idx = NORMAL_SEQUENCE.index(fs.phase) if fs.phase in NORMAL_SEQUENCE else -1
        if current_idx >= 0 and current_idx + 1 < len(NORMAL_SEQUENCE):
            next_phase = NORMAL_SEQUENCE[current_idx + 1]
            fs.phase = next_phase
            fs.phase_elapsed = 0

            # CRUISE 阶段：检查是否起飞
            if next_phase == FlightPhase.TAKEOFF:
                dep_airport = fs.departure_airport
                cap = self._airport_capacity.get(dep_airport, 1.0)
                rng = self._rng or random
                if cap < 0.5 and rng.random() > cap:
                    fs.apply_delay(30, f"{dep_airport}起飞受限")
                    return
                fs.log("起飞")
            elif next_phase == FlightPhase.PARKED:
                fs.log("到达靠桥")
        else:
            fs.phase = FlightPhase.PARKED
            fs.log("到达")

    def _process_pending_events(self):
        remaining = []
        for evt in self._pending_events:
            trigger_min = evt.get('trigger_min', self._current_minutes)
            if self._current_minutes >= trigger_min:
                self._apply_event(evt)
            else:
                remaining.append(evt)
        self._pending_events = remaining

    def _apply_event(self, event_data: dict):
        event_type = event_data.get('event_type', '')
        event_data['applied_at'] = self.current_time_str
        event_data['expire_min'] = self._current_minutes + event_data.get('duration_min', 60)

        if event_type == 'airport':
            # 机场异常：降低容量
            ap = event_data.get('airport', '')
            ratio = event_data.get('capacity_ratio', 0.5)
            if ap:
                self._airport_capacity[ap] = min(self._airport_capacity.get(ap, 1.0), ratio)
                self.log_event(f"机场异常: {ap} 容量→{ratio}")
        elif event_type == 'weather_trigger':
            # 天气触发
            ap = event_data.get('airport', '')
            wtype_val = event_data.get('weather', 'rain')
            try:
                wtype = WeatherType(wtype_val)
                self.weather.tick(self.current_hour)  # 强制触发
                self._airport_capacity[ap] = WEATHER_CONFIG[wtype]["capacity_ratio"]
            except Exception:
                pass

        self._active_events.append(event_data)

    def _expire_events(self):
        self._active_events = [
            e for e in self._active_events
            if e.get('expire_min', 0) > self._current_minutes
        ]
        # 过期事件恢复容量
        for ap in list(self._airport_capacity.keys()):
            w = self.weather.get_weather(ap)
            if w:
                self._airport_capacity[ap] = w.capacity_ratio

    def _update_kpi(self):
        total = len(self.flights)
        if total == 0:
            self.kpi = self._init_kpi()
            return

        completed = sum(1 for fs in self.flights.values() if fs.phase == FlightPhase.PARKED)
        delayed = sum(1 for fs in self.flights.values() if fs.is_delayed)
        cancelled = sum(1 for fs in self.flights.values() if fs.is_cancelled)
        airborne = sum(1 for fs in self.flights.values() if fs.is_airborne)

        total_delay = sum(fs.delay_minutes for fs in self.flights.values() if fs.delay_minutes > 0)
        delay_count = sum(1 for fs in self.flights.values() if fs.delay_minutes > 0)

        self.kpi = {
            'punctuality': round((total - delay_count) / total * 100, 1) if total else 100,
            'completion_rate': round(completed / total * 100, 1) if total else 0,
            'airborne_count': airborne,
            'delayed_count': delayed,
            'cancelled_count': cancelled,
            'total_passengers': self.passenger_flow.total_passengers,
            'delayed_passengers': self.passenger_flow.get_total_delayed(),
            'avg_delay': round(total_delay / delay_count, 1) if delay_count else 0,
            'active_events': len(self._active_events),
        }

    def log_event(self, msg: str):
        print(f"[SimEngine] {msg}", flush=True)

    # ───────── 时间工具 ─────────

    @staticmethod
    def _time_to_min(t: tuple) -> int:
        """将 (y, m, d, h, min) 转为从 Nov 1 00:00 起算的分钟数（1-based day）"""
        y, m, d, h, mi = int(t[0]), int(t[1]), int(t[2]), int(t[3]), int(t[4])
        return (m - 11) * 30 * 24 * 60 + (d - 1) * 24 * 60 + h * 60 + mi

    @staticmethod
    def _min_to_tuple(minutes: int) -> tuple:
        """分钟数 → (y, m, d, h, min)（1-based day）"""
        total_days = minutes // (24 * 60)
        month = 11 + total_days // 30
        day = total_days % 30 + 1
        remaining = minutes % (24 * 60)
        hour = remaining // 60
        minute = remaining % 60
        return (2020, month, day, hour, minute)

    @staticmethod
    def _min_to_time(minutes: int) -> str:
        """分钟数 → 日期时间字符串（1-based day）"""
        y, m, d, h, mi = SimulationEngine._min_to_tuple(minutes)
        return f"{y}-{m:02d}-{d:02d} {h:02d}:{mi:02d}"

    @staticmethod
    def _init_kpi() -> dict:
        return {
            'punctuality': 0, 'completion_rate': 0,
            'airborne_count': 0, 'delayed_count': 0, 'cancelled_count': 0,
            'total_passengers': 0, 'delayed_passengers': 0,
            'avg_delay': 0, 'active_events': 0,
        }


# 全局单例
simulation_engine = SimulationEngine()
