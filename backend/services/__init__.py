"""服务实例共享模块 — 提供全局单例，供 Blueprint 和 app.py 共同使用"""

from .data_service import data_service
from .routing_service import AircraftRoutingService
from .runway_service import RunwaySchedulingService
from .gate_service import GateAssignmentService
from .crew_service import CrewSchedulingService
from .simulation_engine import simulation_engine

# 全局服务单例
routing_service = AircraftRoutingService()
runway_service = RunwaySchedulingService()
gate_service = GateAssignmentService()
crew_service = CrewSchedulingService()
