"""事件注入服务 — 手动/自动注入异常事件到模拟引擎"""

from typing import Dict, List, Optional
from ..services.simulation_engine import simulation_engine


class EventInjector:
    """将异常事件注入模拟引擎"""

    @staticmethod
    def inject_airport_anomaly(airport: str, capacity_ratio: float = 0.5,
                               duration_min: int = 60, trigger_min: Optional[int] = None) -> dict:
        """机场异常：降低指定机场起降容量"""
        event = {
            'event_type': 'airport',
            'airport': airport,
            'capacity_ratio': max(0.0, min(1.0, capacity_ratio)),
            'duration_min': duration_min,
            'trigger_min': trigger_min or simulation_engine._current_minutes,
            'label': f"机场异常: {airport} 容量→{capacity_ratio}",
        }
        simulation_engine.inject_event(event)
        simulation_engine.log_event(f"注入机场异常: {airport}, 容量={capacity_ratio}, 持续{duration_min}min")
        return event

    @staticmethod
    def inject_crew_absence(crew_names: List[str], start_time: str, end_time: str,
                            airline: str = "四川航空", base: str = "成都") -> dict:
        """机组请假：创建一个 AnomalyEvent（交由前端调用已有 analyze/execute）"""
        event = {
            'event_type': 'crew_absence',
            'affected_crew': crew_names,
            'start_time': start_time,
            'end_time': end_time,
            'airline': airline,
            'base': base,
            'label': f"机组请假: {', '.join(crew_names)} {start_time}~{end_time}",
        }
        simulation_engine.inject_event(event)
        simulation_engine.log_event(f"注入机组请假: {crew_names}")
        return event

    @staticmethod
    def inject_aircraft_failure(tail_no: str, duration_min: int = 120,
                                trigger_min: Optional[int] = None) -> dict:
        """飞机故障：排除指定飞机"""
        event = {
            'event_type': 'aircraft_failure',
            'aircraft': tail_no,
            'duration_min': duration_min,
            'trigger_min': trigger_min or simulation_engine._current_minutes,
            'label': f"飞机故障: {tail_no}，预计修复 {duration_min}min",
        }
        simulation_engine.inject_event(event)
        simulation_engine.log_event(f"注入飞机故障: {tail_no}")
        return event

    @staticmethod
    def get_active_events() -> List[dict]:
        return simulation_engine._active_events

    @staticmethod
    def get_pending_events() -> List[dict]:
        return simulation_engine._pending_events

    @staticmethod
    def remove_event(index: int):
        """移除指定事件"""
        if 0 <= index < len(simulation_engine._active_events):
            removed = simulation_engine._active_events.pop(index)
            # 如果是机场异常，恢复容量
            if removed.get('event_type') == 'airport':
                ap = removed.get('airport', '')
                if ap:
                    w = simulation_engine.weather.get_weather(ap)
                    if w:
                        simulation_engine._airport_capacity[ap] = w.capacity_ratio
            return removed
        return None


# 单例
event_injector = EventInjector()
