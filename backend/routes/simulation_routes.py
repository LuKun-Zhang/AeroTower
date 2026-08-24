"""模拟引擎 API — /api/simulation/* 路由"""

from flask import Blueprint, jsonify, request

from ..services.simulation_engine import simulation_engine
from ..services.event_injector import event_injector
from ..services.data_service import data_service
from ..routes.schedule_routes import safe_handler

simulation_bp = Blueprint('simulation', __name__)


def _ok(data=None, msg="ok"):
    return jsonify({'code': 0, 'data': data, 'msg': msg})


def _err(msg, code=400):
    return jsonify({'code': code, 'msg': msg}), code


# ────────── 引擎控制 ──────────

@simulation_bp.route('/simulation/init', methods=['POST'])
@safe_handler
def init_simulation():
    """初始化仿真：加载当前活跃航班"""
    body = request.get_json() or {}
    airport = body.get('airport', None)

    # 获取活跃航班：优先使用与天气页/旅客流页共享的 state 活跃航班，
    # 保证 flight_id 一致，否则天气中断计划无法匹配到引擎中的航班。
    from ..state import get_active_flights as _state_active_flights
    flights = _state_active_flights()
    if not flights:
        from ..routes.schedule_routes import _get_active_flights
        flights = _get_active_flights()

    if not flights:
        return _err("没有可用的航班数据，请先上传/筛选航班", 400)

    simulation_engine.reset()
    simulation_engine.load_flights(flights)

    # 应用天气中断计划（取消/延误），保证与天气页、旅客流页一致
    from ..state import get_weather_disruption_plan
    plan = get_weather_disruption_plan()
    simulation_engine.apply_disruption(plan)

    cancel_count = sum(
        1 for fs in simulation_engine.flights.values() if fs.is_cancelled
    )
    delay_count = sum(
        1 for fs in simulation_engine.flights.values() if fs.is_delayed
    )

    return _ok({
        'total_flights': len(simulation_engine.flights),
        'sim_start': simulation_engine._min_to_time(simulation_engine._simulation_start),
        'sim_end': simulation_engine._min_to_time(simulation_engine._simulation_end),
        'progress_pct': 0,
        'disruption_applied': len(plan),
        'delay_count': delay_count,
        'cancel_count': cancel_count,
    }, "仿真初始化完成")


@simulation_bp.route('/simulation/start', methods=['POST'])
@safe_handler
def start_simulation():
    """启动仿真"""
    if not simulation_engine.flights:
        return _err("请先初始化仿真", 400)
    if simulation_engine.status == simulation_engine.RUNNING:
        return _ok({'status': simulation_engine.status}, "仿真已在运行")
    simulation_engine.start()
    return _ok({'status': simulation_engine.status}, "仿真已启动")


@simulation_bp.route('/simulation/pause', methods=['POST'])
@safe_handler
def pause_simulation():
    """暂停仿真"""
    simulation_engine.pause()
    return _ok({'status': simulation_engine.status})


@simulation_bp.route('/simulation/resume', methods=['POST'])
@safe_handler
def resume_simulation():
    """恢复仿真"""
    simulation_engine.resume()
    return _ok({'status': simulation_engine.status})


@simulation_bp.route('/simulation/stop', methods=['POST'])
@safe_handler
def stop_simulation():
    """停止仿真"""
    simulation_engine.stop()
    return _ok({'status': simulation_engine.status})


@simulation_bp.route('/simulation/step', methods=['POST'])
@safe_handler
def step_simulation():
    """单步执行"""
    if not simulation_engine.flights:
        return _err("请先初始化仿真", 400)
    simulation_engine.step()
    return _ok(simulation_engine.get_snapshot())


@simulation_bp.route('/simulation/speed', methods=['POST'])
@safe_handler
def set_speed():
    """设置倍速"""
    body = request.get_json() or {}
    speed = body.get('speed', 1)
    simulation_engine.set_speed(speed)
    return _ok({'speed': simulation_engine.speed})


@simulation_bp.route('/simulation/jump', methods=['POST'])
@safe_handler
def jump_to():
    """跳转到指定进度"""
    body = request.get_json() or {}
    pct = body.get('progress_pct', 0)
    span = simulation_engine._simulation_end - simulation_engine._simulation_start
    target = simulation_engine._simulation_start + int(span * pct / 100)
    simulation_engine.jump_to(target)
    return _ok(simulation_engine.get_snapshot())


@simulation_bp.route('/simulation/sync_time', methods=['POST'])
@safe_handler
def sync_time():
    """按「绝对业务分钟」同步引擎时钟（供「模拟大引擎」统一时钟驱动）。

    前端天气 phase 映射出的绝对分钟（自 2020-11-01 00:00 起算）是唯一时间源，
    引擎据此重算航班自然状态，并叠加当前天气中断计划，使航班页显示时间、
    飞机起降状态与底部统一时钟完全一致。
    """
    body = request.get_json() or {}
    minutes = int(body.get('current_minutes', 0))

    from ..state import get_weather_disruption_plan
    plan = get_weather_disruption_plan() or {}

    # 在 sync_to 内部一次性完成「时间 + 天气中断」确定性重算
    simulation_engine.sync_to(minutes, plan)

    return _ok(simulation_engine.get_snapshot())


# ────────── 查询 ──────────

@simulation_bp.route('/simulation/snapshot', methods=['GET'])
@safe_handler
def get_snapshot():
    """获取当前仿真快照

    动态应用最新天气中断计划：天气页每 2s 重算 plan 写回共享 state，
    此处每次快照前重新应用，保证航班随天气演变实时取消/延误（而非仅在 init 时生效一次）。
    """
    from ..state import get_weather_disruption_plan
    plan = get_weather_disruption_plan()
    # 统一时钟驱动模式下，航班状态由 sync_to 确定性重算（含天气中断），
    # 这里不再重复叠加，避免与 sync_to 的可逆记录冲突导致状态抖动。
    if not simulation_engine._synced_mode:
        # 始终应用（含空 plan）：空 plan 时 apply_disruption 会清除上一轮天气中断，
        # 否则天气恢复后航班会一直停留在延误/取消状态。
        simulation_engine.apply_disruption(plan or {})
        simulation_engine._update_kpi()
    return _ok(simulation_engine.get_snapshot())


@simulation_bp.route('/simulation/flights', methods=['GET'])
@safe_handler
def get_flights():
    """获取所有航班状态"""
    flights = [fs.to_dict() for fs in simulation_engine.flights.values()]
    return _ok({'flights': flights})


@simulation_bp.route('/simulation/kpi', methods=['GET'])
@safe_handler
def get_kpi():
    """获取 KPI"""
    return _ok(simulation_engine.kpi)


@simulation_bp.route('/simulation/weather', methods=['GET'])
@safe_handler
def get_weather():
    """获取天气"""
    ap = request.args.get('airport', '')
    if ap:
        w = simulation_engine.weather.get_weather(ap)
        upcoming = simulation_engine.weather.get_upcoming(ap, 6)
        return _ok({
            'current': w.to_dict() if w else None,
            'upcoming': [uw.to_dict() for uw in upcoming],
        })
    all_w = {k: w.to_dict() for k, w in simulation_engine.weather.get_all_weather().items()}
    return _ok(all_w)


# ────────── 事件注入 ──────────

@simulation_bp.route('/simulation/inject/airport', methods=['POST'])
@safe_handler
def inject_airport():
    """手动注入机场异常"""
    body = request.get_json() or {}
    event = event_injector.inject_airport_anomaly(
        airport=body.get('airport', '成都'),
        capacity_ratio=body.get('capacity_ratio', 0.5),
        duration_min=body.get('duration_min', 60),
    )
    return _ok(event, "机场异常已注入")


@simulation_bp.route('/simulation/inject/crew', methods=['POST'])
@safe_handler
def inject_crew():
    """手动注入机组请假"""
    body = request.get_json() or {}
    event = event_injector.inject_crew_absence(
        crew_names=body.get('crew_names', []),
        start_time=body.get('start_time', ''),
        end_time=body.get('end_time', ''),
        airline=body.get('airline', '四川航空'),
        base=body.get('base', '成都'),
    )
    return _ok(event, "机组请假事件已创建")


@simulation_bp.route('/simulation/inject/aircraft', methods=['POST'])
@safe_handler
def inject_aircraft():
    """手动注入飞机故障"""
    body = request.get_json() or {}
    event = event_injector.inject_aircraft_failure(
        tail_no=body.get('tail_no', ''),
        duration_min=body.get('duration_min', 120),
    )
    return _ok(event, "飞机故障已注入")


@simulation_bp.route('/simulation/events', methods=['GET'])
@safe_handler
def get_events():
    """获取活跃事件"""
    return _ok({
        'active': event_injector.get_active_events(),
        'pending': event_injector.get_pending_events(),
    })


@simulation_bp.route('/simulation/events/<int:index>', methods=['DELETE'])
@safe_handler
def remove_event(index):
    """移除事件"""
    result = event_injector.remove_event(index)
    if result:
        return _ok(result, "事件已移除")
    return _err("事件不存在", 404)


# ────────── 上下文数据（供注入面板使用）──

@simulation_bp.route('/simulation/context', methods=['GET'])
@safe_handler
def get_context():
    """获取注入面板需要的上下文数据（机场列表、飞机列表、机组人员）"""
    data_service.load_all()

    # 机场列表
    airports = sorted(set(
        f.departure_airport for f in data_service.flights
    ).union(
        f.arrival_airport for f in data_service.flights
    ))

    # 飞机列表
    aircrafts = sorted(
        [{'tail_no': a.tail_no, 'ac_type': a.ac_type, 'base': a.base}
         for a in data_service.aircrafts],
        key=lambda x: x['tail_no'],
    )

    # 机组基地
    from ..services.crew_service import get_airline_bases
    bases = get_airline_bases()

    return _ok({
        'airports': airports,
        'aircrafts': aircrafts,
        'airlines': list(bases.keys()),
        'bases': bases,
    })
