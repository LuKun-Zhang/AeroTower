"""天气模拟服务 — 引擎自动生成天气变化，联动机场容量"""

import random
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class WeatherType(Enum):
    CLEAR = "clear"             # 晴
    CLOUDY = "cloudy"           # 多云
    RAIN = "rain"               # 雨
    THUNDERSTORM = "thunderstorm"  # 雷暴
    FOG = "fog"                 # 雾


# 天气属性配置
WEATHER_CONFIG = {
    WeatherType.CLEAR: {
        "label": "晴", "icon": "☀", "visibility_m": 10000, "capacity_ratio": 1.0,
        "wind_ms": (0, 5),
    },
    WeatherType.CLOUDY: {
        "label": "多云", "icon": "⛅", "visibility_m": 4000, "capacity_ratio": 0.9,
        "wind_ms": (3, 8),
    },
    WeatherType.RAIN: {
        "label": "雨", "icon": "🌧", "visibility_m": 2000, "capacity_ratio": 0.7,
        "wind_ms": (5, 15),
    },
    WeatherType.THUNDERSTORM: {
        "label": "雷暴", "icon": "⛈", "visibility_m": 800, "capacity_ratio": 0.4,
        "wind_ms": (10, 25),
    },
    WeatherType.FOG: {
        "label": "雾", "icon": "🌫", "visibility_m": 300, "capacity_ratio": 0.2,
        "wind_ms": (0, 3),
    },
}


@dataclass
class AirportWeather:
    """单个机场的天气快照"""
    airport: str       # 中文机场名
    weather: WeatherType = WeatherType.CLEAR
    wind_ms: float = 0.0
    visibility_m: float = 10000.0
    hour: int = 0      # 仿真小时

    @property
    def label(self) -> str:
        return WEATHER_CONFIG[self.weather]["label"]

    @property
    def icon(self) -> str:
        return WEATHER_CONFIG[self.weather]["icon"]

    @property
    def capacity_ratio(self) -> float:
        return WEATHER_CONFIG[self.weather]["capacity_ratio"]

    @property
    def is_disrupted(self) -> bool:
        """是否需要触发容量调整（RAIN 及以上）"""
        return self.weather in (WeatherType.RAIN, WeatherType.THUNDERSTORM, WeatherType.FOG)

    def to_dict(self) -> dict:
        cfg = WEATHER_CONFIG[self.weather]
        return {
            "airport": self.airport,
            "weather": self.weather.value,
            "label": cfg["label"],
            "icon": cfg["icon"],
            "wind_ms": round(self.wind_ms, 1),
            "visibility_m": int(self.visibility_m),
            "capacity_ratio": self.capacity_ratio,
            "is_disrupted": self.is_disrupted,
            "hour": self.hour,
        }


# 相邻机场定义（用于区域天气联动）
_REGION_GROUPS = [
    # 成都周边
    ["成都", "重庆", "绵阳", "宜宾", "泸州"],
    # 北京周边
    ["北京", "天津"],
    # 上海周边
    ["上海", "杭州", "南京", "宁波"],
    # 云南
    ["昆明", "丽江", "西双版纳", "大理"],
]


def _get_region(airport: str) -> Optional[List[str]]:
    for region in _REGION_GROUPS:
        if airport in region:
            return region
    return None


class WeatherService:
    """天气模拟服务"""

    def __init__(self):
        self._airport_weather: Dict[str, AirportWeather] = {}
        self._weather_history: Dict[str, List[AirportWeather]] = {}
        self._current_hour: int = -1

    def init_for_airports(self, airports: List[str]):
        """为所有机场初始化天气"""
        for ap in airports:
            # 大部分晴/多云，少量雨
            r = random.random()
            if r < 0.6:
                w = WeatherType.CLEAR
            elif r < 0.85:
                w = WeatherType.CLOUDY
            else:
                w = WeatherType.RAIN
            self._airport_weather[ap] = self._make_weather(ap, w, 0)
            self._weather_history.setdefault(ap, [])

    def tick(self, current_hour: int) -> Dict[str, AirportWeather]:
        """每小时更新一次天气。返回变化了的机场天气字典"""
        self._current_hour = current_hour
        changed = {}

        for ap, current in self._airport_weather.items():
            new = self._evolve_weather(ap, current.weather, current_hour)
            if new != current.weather or self._weather_changed(ap, current):
                changed[ap] = self._make_weather(ap, new, current_hour)
                self._airport_weather[ap] = changed[ap]
                self._weather_history[ap].append(changed[ap])

        return changed

    def get_weather(self, airport: str) -> Optional[AirportWeather]:
        return self._airport_weather.get(airport)

    def get_all_weather(self) -> Dict[str, AirportWeather]:
        return dict(self._airport_weather)

    def get_upcoming(self, airport: str, hours: int = 6) -> List[AirportWeather]:
        """预演未来 N 小时的天气（不实际更新）"""
        current = self._airport_weather.get(airport)
        if not current:
            return []
        result = [current]
        w = current.weather
        for h in range(1, hours + 1):
            w = self._evolve_weather(airport, w, self._current_hour + h)
            result.append(self._make_weather(airport, w, self._current_hour + h))
        return result

    def _make_weather(self, airport: str, wtype: WeatherType, hour: int) -> AirportWeather:
        cfg = WEATHER_CONFIG[wtype]
        lo, hi = cfg["wind_ms"]
        return AirportWeather(
            airport=airport,
            weather=wtype,
            wind_ms=round(random.uniform(lo, hi), 1),
            visibility_m=round(random.uniform(
                cfg["visibility_m"] * 0.7, cfg["visibility_m"] * 1.3
            ), 0),
            hour=hour,
        )

    def _evolve_weather(self, airport: str, current: WeatherType, hour: int) -> WeatherType:
        """马尔可夫链天气转移"""
        region = _get_region(airport)

        # 区域联动：如果同区域其他机场有更差的天气，本机场恶化概率增加
        region_boost = 0.0
        if region:
            for ra in region:
                if ra == airport:
                    continue
                rw = self._airport_weather.get(ra)
                if rw and rw.is_disrupted:
                    region_boost += 0.15

        transitions = {
            WeatherType.CLEAR: [
                (WeatherType.CLEAR, 0.70 - region_boost),
                (WeatherType.CLOUDY, 0.25 + region_boost * 0.5),
                (WeatherType.RAIN, 0.05 + region_boost * 0.5),
            ],
            WeatherType.CLOUDY: [
                (WeatherType.CLOUDY, 0.55 - region_boost),
                (WeatherType.CLEAR, 0.25),
                (WeatherType.RAIN, 0.15 + region_boost * 0.5),
                (WeatherType.FOG, 0.05 + region_boost * 0.5),
            ],
            WeatherType.RAIN: [
                (WeatherType.RAIN, 0.35),
                (WeatherType.CLOUDY, 0.25),
                (WeatherType.CLEAR, 0.20),
                (WeatherType.THUNDERSTORM, 0.10 + region_boost),
                (WeatherType.FOG, 0.10),
            ],
            WeatherType.THUNDERSTORM: [
                (WeatherType.THUNDERSTORM, 0.30),
                (WeatherType.RAIN, 0.40),
                (WeatherType.CLOUDY, 0.30),
            ],
            WeatherType.FOG: [
                (WeatherType.FOG, 0.30),
                (WeatherType.CLOUDY, 0.40),
                (WeatherType.RAIN, 0.30),
            ],
        }

        ts = transitions.get(current, [(WeatherType.CLEAR, 1.0)])
        r = random.random()
        cumulative = 0.0
        for wtype, prob in ts:
            cumulative += prob
            if r <= cumulative:
                return wtype
        return ts[-1][0]

    def _weather_changed(self, airport: str, current: AirportWeather) -> bool:
        """检查是否有显著的风速/能见度变化"""
        cfg = WEATHER_CONFIG[current.weather]
        return abs(current.wind_ms - random.uniform(*cfg["wind_ms"])) > 5
