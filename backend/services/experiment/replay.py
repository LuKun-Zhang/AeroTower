"""回放运行时：从工件懒加载独立引擎，与工作台完全隔离。"""

import threading
from collections import OrderedDict

from ...models.flight import Flight
from ...services.simulation_engine import SimulationEngine
from ...services.weather_service import AirportWeather, WeatherType, WEATHER_CONFIG
from ...utils import city_geo
from . import store, artifacts, weather_program
from .seed import rng_for

MAX_SESSIONS = 2
_CACHE = OrderedDict()
_LOCK = threading.Lock()

_WEATHER_MAP = {
    'sunny': WeatherType.CLEAR,
    'cloudy': WeatherType.CLOUDY,
    'rain_light': WeatherType.RAIN,
    'rain_moderate': WeatherType.RAIN,
    'rain_heavy': WeatherType.RAIN,
    'thunderstorm': WeatherType.THUNDERSTORM,
    'fog': WeatherType.FOG,
}


def _flight(data):
    f = Flight(
        flight_id=data.get('flight_id', 0),
        flight_no=data.get('flight_no', ''),
        ac_type=data.get('ac_type', 'A319'),
        layout=data.get('layout', 'C8Y124'),
        departure_airport=data.get('departure_airport', ''),
        arrival_airport=data.get('arrival_airport', ''),
        time_departure=tuple(data.get('time_departure') or (2020, 11, 30, 0, 0)),
        time_arrival=tuple(data.get('time_arrival') or (2020, 11, 30, 0, 0)),
        timespan=int(data.get('timespan', 0) or 0),
        cost=float(data.get('cost', 0) or 0),
    )
    f._pax_count = int(data.get('pax_count', 0) or 0)
    f._is_ferry = bool(data.get('is_ferry', False))
    return f


class ReplaySession:
    def __init__(self, username, exp_id, record, flights, schedule, weather, paxflow):
        self.username = username
        self.exp_id = exp_id
        self.record = record
        self.schedule = schedule or {}
        self.weather = weather or {}
        self.paxflow = paxflow or {}
        self.plan = (weather or {}).get('plan') or {}
        self.meta = record.replay or {}
        self.sim_start = int(self.meta.get('sim_start', 0))
        self.sim_end = int(self.meta.get('sim_end', self.sim_start))
        self._lock = threading.Lock()

        self.engine = SimulationEngine(rng=rng_for(record.conditions.get('seed', 0), 'replay'))
        self.engine.load_flights(flights)
        self.engine.sync_frozen(self.sim_start, self.plan)

    def _set_airport_weather(self, minutes):
        provinces = weather_program.province_weather_at(self.weather, minutes)
        bad = {p for p, t in (provinces or {}).items() if t in _WEATHER_MAP}
        weather = self.engine.weather
        weather._airport_weather = {}
        for ap in {f.departure_airport for f in self.engine.flights.values()} | \
                  {f.arrival_airport for f in self.engine.flights.values()}:
            prov = city_geo.get_city_province(ap)
            wtype = _WEATHER_MAP.get(provinces.get(prov), WeatherType.CLEAR) if prov in bad \
                else WeatherType.CLEAR
            cfg = WEATHER_CONFIG[wtype]
            weather._airport_weather[ap] = AirportWeather(
                airport=ap, weather=wtype,
                wind_ms=sum(cfg['wind_ms']) / 2,
                visibility_m=cfg['visibility_m'],
                hour=minutes // 60,
            )

    def sync(self, minutes):
        with self._lock:
            target = max(self.sim_start, min(int(minutes), self.sim_end))
            self.engine.sync_frozen(target, self.plan)
            self._set_airport_weather(target)
            return self.snapshot()

    def snapshot(self):
        snap = self.engine.get_snapshot()
        snap['experiment_id'] = self.exp_id
        snap['replay'] = True
        snap['sim_start'] = self.engine._min_to_time(self.sim_start)
        snap['sim_end'] = self.engine._min_to_time(self.sim_end)
        return snap

    def paxflow_payload(self):
        data = dict(self.paxflow or {})
        data.pop('flights', None)
        return data

    def context(self):
        flights = list(self.engine.flights.values())
        airports = sorted({fs.departure_airport for fs in flights}
                          | {fs.arrival_airport for fs in flights})
        aircrafts = [
            {'tail_no': a.get('tail_no'), 'ac_type': a.get('ac_type'), 'base': a.get('base')}
            for a in (self.schedule.get('aircraft') or [])
        ]
        hub = self.meta.get('airport') or ''
        return {
            'airports': airports,
            'aircrafts': aircrafts,
            'airlines': ['四川航空'],
            'bases': {hub: [hub]} if hub else {},
        }

    def weather_disruption(self):
        minutes = self.engine._current_minutes
        provinces = weather_program.province_weather_at(self.weather, minutes)
        # 补齐为全省份（无坏天气则为晴），供省份天气表展示
        for name in city_geo.PROVINCE_BOUNDS.keys():
            provinces.setdefault(name, 'sunny')
        return {
            'province_weather': provinces,
            'plan': self.plan,
            'plan_size': len(self.plan),
            'current_minutes': minutes,
        }


def _load(username, exp_id):
    record = store.load(username, exp_id)
    if not record:
        raise ValueError('实验不存在')
    flights_data = artifacts.read_artifact(username, exp_id, 'flights.json', [])
    if not flights_data:
        raise ValueError('实验尚未产出航班工件')
    session = ReplaySession(
        username, exp_id, record,
        [_flight(d) for d in flights_data],
        artifacts.read_artifact(username, exp_id, 'schedule.json', {}),
        artifacts.read_artifact(username, exp_id, 'weather.json', {}),
        artifacts.read_artifact(username, exp_id, 'paxflow.json', {}),
    )
    return session


def get(username, exp_id):
    key = (username, exp_id)
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        session = _load(username, exp_id)
        _CACHE[key] = session
        while len(_CACHE) > MAX_SESSIONS:
            _CACHE.popitem(last=False)
        return session
