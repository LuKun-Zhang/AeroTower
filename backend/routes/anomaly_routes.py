"""异常调度 API 路由 — 所有响应统一 {code: 0, data/msg} 格式"""

import os
import threading
from flask import Blueprint, request, jsonify

from ..services.anomaly_service import anomaly_service
from ..services.recovery_service import recovery_service
from ..utils.city_geo import PROVINCE_BOUNDS
from ..services.scenario_templates import (
    TEMPLATES, ANOMALY_PARAMS_SCHEMA,
    get_template_by_id, get_templates_by_category
)

anomaly_bp = Blueprint('anomaly', __name__)


def _ok(data=None, msg=None):
    """统一成功响应"""
    body = {"code": 0}
    if data is not None:
        body["data"] = data
    if msg is not None:
        body["msg"] = msg
    return jsonify(body)


def _err(msg, status=400):
    """统一错误响应"""
    return jsonify({"code": -1, "msg": msg}), status


# ============================================================
#  场景模板
# ============================================================

@anomaly_bp.route('/templates', methods=['GET'])
def get_templates():
    """获取所有场景模板"""
    category = request.args.get('category')
    if category:
        result = get_templates_by_category(category)
    else:
        result = list(TEMPLATES)
    return _ok({"templates": result, "count": len(result)})


@anomaly_bp.route('/templates/<template_id>', methods=['GET'])
def get_template(template_id):
    """获取单个模板详情"""
    tmpl = get_template_by_id(template_id)
    if not tmpl:
        return _err("模板不存在", 404)
    return _ok({"template": tmpl})


@anomaly_bp.route('/templates/params-schema', methods=['GET'])
def get_params_schema():
    """获取异常参数 Schema"""
    return _ok({"schemas": ANOMALY_PARAMS_SCHEMA})


# ============================================================
#  表单上下文（机场/飞机/日期动态数据）
# ============================================================

@anomaly_bp.route('/context', methods=['GET'])
def get_context():
    """获取创建异常事件表单所需的动态选项数据"""
    schedule = _get_schedule() or {}

    # 预先加载系统数据服务（读系统文件中的机场、飞机）
    from ..services.data_service import data_service
    try:
        data_service.load_all()
    except Exception as e:
        print(f"[AnomalyContext] data_service 加载失败: {e}")

    # 1) 机场：系统数据服务 + 活跃航班合并
    airports = set()
    # 从数据服务加载
    for a in getattr(data_service, 'airports', {}).values():
        name = getattr(a, 'name', '') or getattr(a, 'city_name', '')
        if name:
            airports.add(name)
    # 从活跃/已上传航班补充
    schedule_flights = schedule.get('flights', []) or schedule.get('uploaded_flights', [])
    for f in schedule_flights:
        dep = getattr(f, 'departure_airport', '')
        arr = getattr(f, 'arrival_airport', '')
        if dep:
            airports.add(dep)
        if arr:
            airports.add(arr)
    airports = sorted(airports)
    # 兜底
    if not airports:
        airports = ['成都', '重庆', '昆明', '杭州', '北京', '三亚', '乌鲁木齐', '哈尔滨']

    # 2) 飞机：系统数据服务 + 排班分配合并
    aircrafts = []
    ac_map = schedule.get('aircraft_assignments', {})
    seen = set()
    for tail in ac_map.values():
        if tail and tail not in seen:
            seen.add(tail)
            aircrafts.append({'tail_no': tail, 'ac_type': '', 'base': ''})
    for a in getattr(data_service, 'aircrafts', []):
        if a.tail_no not in seen:
            seen.add(a.tail_no)
            aircrafts.append({
                'tail_no': a.tail_no,
                'ac_type': getattr(a, 'ac_type', ''),
                'base': getattr(a, 'base', ''),
            })
    if not aircrafts:
        for i in range(12):
            aircrafts.append({
                'tail_no': f'B-{6388 + i}',
                'ac_type': 'A320',
                'base': '成都',
            })

    # 3) 日期：从航班数据中直接提取
    all_flights = list(schedule_flights)
    if not all_flights:
        all_flights = list(getattr(data_service, 'flights', []))
    dates = set()
    for f in all_flights:
        td = getattr(f, 'time_departure', None)
        if td and len(td) >= 3:
            try:
                y, m, d = int(td[0]), int(td[1]), int(td[2])
                dates.add(f"{y}-{m:02d}-{d:02d}")
            except (ValueError, TypeError):
                pass
    dates = sorted(dates)
    if not dates:
        # 兜底：系统预设航班日期范围 11-30 ~ 12-06
        dates = [f"2020-11-{d:02d}" for d in range(30, 31)] + \
                [f"2020-12-{d:02d}" for d in range(1, 7)]

    # 4) 航班：简化列表供航班异常表单选择
    flights_list = []
    seen_fids = set()
    for f in all_flights:
        fid = getattr(f, 'flight_id', '')
        if fid and fid not in seen_fids:
            seen_fids.add(fid)
            flights_list.append({
                'flight_id': fid,
                'flight_no': getattr(f, 'flight_no', ''),
                'departure_airport': getattr(f, 'departure_airport', ''),
                'arrival_airport': getattr(f, 'arrival_airport', ''),
            })

    # 5) 机组
    crew_list = []
    crew_map = schedule.get('crew_assignments', {})
    crew_seen = set()
    for cids in crew_map.values():
        if isinstance(cids, (list, tuple)):
            for cid in cids:
                if cid and cid not in crew_seen:
                    crew_seen.add(cid)
                    crew_list.append(cid)
    if not crew_list:
        for c in getattr(data_service, 'crew_members', []):
            cid = getattr(c, 'crew_id', '')
            if cid and cid not in crew_seen:
                crew_seen.add(cid)
                crew_list.append(cid)
    if not crew_list:
        crew_list = ['CA_Zhang', 'FO_Li', 'CA_Wang', 'FO_Chen']

    print(f"[AnomalyContext] 机场={len(airports)}, 飞机={len(aircrafts)}, 航班={len(flights_list)}, 机组={len(crew_list)}, 日期={len(dates)}")
    return _ok({
        'airports': airports,
        'aircrafts': aircrafts,
        'flights': flights_list,
        'crew': crew_list,
        'dates': dates,
        'provinces': list(PROVINCE_BOUNDS.keys()) if PROVINCE_BOUNDS else [],
    })


# ============================================================
#  异常事件
# ============================================================

@anomaly_bp.route('/events', methods=['GET'])
def list_events():
    """获取异常事件列表"""
    status_filter = request.args.get('status')
    events = anomaly_service.list_events(status_filter)
    return _ok({
        "events": [e.to_dict() for e in events],
        "count": len(events),
    })


@anomaly_bp.route('/events/<event_id>', methods=['GET'])
def get_event(event_id):
    """获取异常事件详情"""
    event = anomaly_service.get_event(event_id)
    if not event:
        return _err("事件不存在", 404)
    data = event.to_dict()
    if hasattr(event, 'impact_report') and event.impact_report:
        data["impact_report"] = event.impact_report
    if hasattr(event, 'recovery_plan') and event.recovery_plan:
        data["recovery_plan"] = event.recovery_plan
    return _ok(data)


@anomaly_bp.route('/events', methods=['POST'])
def create_event():
    """创建异常事件"""
    body = request.get_json() or {}
    _clear_crew_cache_func()  # 新事件创建时清除旧的替班缓存
    event = anomaly_service.create_event(
        event_type=body.get('event_type', ''),
        title=body.get('title', ''),
        description=body.get('description', ''),
        priority=body.get('priority', 'P2'),
        affected_airports=body.get('affected_airports', []),
        affected_aircraft=body.get('affected_aircraft', []),
        affected_crew=body.get('affected_crew', []),
        affected_runways=body.get('affected_runways', []),
        affected_gates=body.get('affected_gates', []),
        affected_flights=body.get('affected_flights', []),
        start_time=body.get('start_time', ''),
        end_time=body.get('end_time', ''),
        duration_minutes=body.get('duration_minutes', 0),
        delay_minutes=body.get('delay_minutes', 0),
        capacity_ratio=body.get('capacity_ratio', 1.0),
        extra_flight_time=body.get('extra_flight_time', 0),
        severity=body.get('severity', 3),
    )
    return _ok(event.to_dict()), 201


@anomaly_bp.route('/events/<event_id>', methods=['PUT'])
def update_event(event_id):
    """更新异常事件"""
    body = request.get_json() or {}
    event = anomaly_service.update_event(event_id, **body)
    if not event:
        return _err("事件不存在", 404)
    return _ok(event.to_dict())


@anomaly_bp.route('/events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    """删除异常事件"""
    result = anomaly_service.delete_event(event_id)
    if not result:
        return _err("事件不存在", 404)
    return _ok(None, "已删除")


# ============================================================
#  影响分析 & 恢复方案
# ============================================================

@anomaly_bp.route('/events/<event_id>/analyze', methods=['POST'])
def analyze_event(event_id):
    """分析异常事件影响并生成恢复方案"""
    import traceback, os, time
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'crew_recovery_debug.log')
    
    def _diag(msg):
        print(msg, flush=True)
        try:
            with open(log_path, 'a', encoding='utf-8') as _f:
                _f.write(msg + '\n')
        except Exception:
            pass

    _diag(f"\n>>> analyze_event route {time.strftime('%H:%M:%S')} event_id={event_id}")
    try:
        event = anomaly_service.get_event(event_id)
        if not event:
            _diag("event is None → 404")
            return _err("事件不存在", 404)

        _diag(f"event_type={getattr(event, 'event_type', '')}, affected_crew={getattr(event, 'affected_crew', [])}, start={getattr(event, 'start_time', '')}, end={getattr(event, 'end_time', '')}")

        schedule = _get_schedule()
        if not schedule:
            _diag("schedule is None/Falsy → 400")
            return _err("当前没有排班数据", 400)

        _diag(f"schedule_keys={list(schedule.keys()) if schedule else 'NONE'}")
        _diag(f"schedule.crew_pool size={len(schedule.get('crew_pool', []))}")
        _diag(f"schedule.crew_assignments entries={len(schedule.get('crew_assignments', {}))}")
        _diag(f"schedule.flights size={len(schedule.get('flights', []))}")

        impact, plan = recovery_service.generate_recovery_plan(event, schedule)

        # 构建 flight_id → flight_no 映射
        flight_info = {}
        for f in (schedule.get('flights') or []):
            fid = str(getattr(f, 'flight_id', ''))
            if fid and fid not in flight_info:
                flight_info[fid] = {
                    'flight_no': getattr(f, 'flight_no', ''),
                    'departure_airport': getattr(f, 'departure_airport', ''),
                    'arrival_airport': getattr(f, 'arrival_airport', ''),
                }
        for f in (schedule.get('uploaded_flights') or []):
            fid = str(getattr(f, 'flight_id', ''))
            if fid and fid not in flight_info:
                flight_info[fid] = {
                    'flight_no': getattr(f, 'flight_no', ''),
                    'departure_airport': getattr(f, 'departure_airport', ''),
                    'arrival_airport': getattr(f, 'arrival_airport', ''),
                }

        # 丰富影响报告数据
        impact_dict = impact.to_dict()
        impact_dict['direct_impacted_flights'] = [
            {'flight_id': fid, 'flight_no': flight_info.get(str(fid), {}).get('flight_no', '')}
            for fid in impact_dict.get('direct_impacted_flights', [])
        ]
        impact_dict['flights_to_cancel'] = [
            {'flight_id': fid, 'flight_no': flight_info.get(str(fid), {}).get('flight_no', '')}
            for fid in impact_dict.get('flights_to_cancel', [])
        ]
        for item in impact_dict.get('cascade_chains', []):
            fid = item.get('flight_id', '')
            item['flight_no'] = flight_info.get(str(fid), {}).get('flight_no', '')

        anomaly_service.set_impact_report(event_id, impact_dict)
        anomaly_service.set_recovery_plan(event_id, plan.to_dict())

        _diag(f"<<< analyze_event 完成: impacted={impact_dict.get('total_impacted_flights', 0)}, strategy={plan.to_dict().get('strategy', '?')}")

        return _ok({
            "event": event.to_dict(),
            "impact_report": impact_dict,
            "recovery_plan": plan.to_dict(),
        })
    except Exception as e:
        traceback.print_exc()
        _diag(f"!!! analyze_event 异常: {e}")
        return _err(f"分析失败: {str(e)}", 500)


@anomaly_bp.route('/events/<event_id>/impact', methods=['GET'])
def get_impact(event_id):
    """获取影响分析报告"""
    event = anomaly_service.get_event(event_id)
    if not event:
        return _err("事件不存在", 404)
    if not hasattr(event, 'impact_report') or not event.impact_report:
        return _err("尚未进行影响分析", 404)
    return _ok({"event_id": event_id, "impact_report": event.impact_report})


@anomaly_bp.route('/plans/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    """获取恢复方案"""
    plan = recovery_service.get_plan(plan_id)
    if not plan:
        return _err("方案不存在", 404)
    return _ok(plan.to_dict())


@anomaly_bp.route('/plans/<plan_id>/confirm', methods=['POST'])
def confirm_plan(plan_id):
    """确认恢复方案"""
    plan = recovery_service.confirm_plan(plan_id)
    if not plan:
        return _err("方案不存在", 404)
    event = anomaly_service.get_event(plan.event_id)
    if event:
        from ..models.abnormal_event import AnomalyStatus
        anomaly_service.update_event(plan.event_id, status=AnomalyStatus.RECOVERING)
    return _ok({"plan": plan.to_dict()}, "方案已确认")


@anomaly_bp.route('/plans/<plan_id>/reject', methods=['POST'])
def reject_plan(plan_id):
    """拒绝恢复方案"""
    plan = recovery_service.reject_plan(plan_id)
    if not plan:
        return _err("方案不存在", 404)
    return _ok({"plan": plan.to_dict()}, "方案已拒绝")


@anomaly_bp.route('/plans/<plan_id>/execute', methods=['POST'])
def execute_plan(plan_id):
    """执行恢复方案：启动后台线程，前端轮询 /execute-progress 查看进度"""
    plan = recovery_service.get_plan(plan_id)
    if not plan:
        return _err("方案不存在", 404)
    if plan.status == 'executed':
        return _err("方案已执行过", 400)

    schedule = _get_schedule()
    if not schedule:
        return _err("当前没有排班数据", 400)

    # 重置进度（状态为 idle 表示未被其他请求占用）
    with _progress_lock:
        if _execution_progress["status"] == "running":
            return _err("正在执行中，请等待当前任务完成", 409)
        _execution_progress["progress"] = 0
        _execution_progress["stage"] = "准备执行..."
        _execution_progress["status"] = "running"
        _execution_progress["result"] = None

    # 后台线程执行
    def _run():
        try:
            _set_execute_progress(5, "正在修改航班时间...")

            executed = recovery_service.execute_plan(plan_id, schedule)
            if not executed:
                _set_execute_progress(0, "执行失败", "error", {"msg": "recovery_service 返回空"})
                return

            _set_execute_progress(30, "航班时间已调整，正在更新事件状态...")

            event = anomaly_service.get_event(plan.event_id)
            if event:
                from ..models.abnormal_event import AnomalyStatus
                anomaly_service.update_event(plan.event_id, status=AnomalyStatus.RECOVERED)

            _set_execute_progress(40, "正在回写航班数据...")

            # 重新排班：将修改后的 flights/chains 回写到活跃数据源，并重跑全部调度算法
            if _post_execute_handler:
                try:
                    _post_execute_handler(executed, _set_execute_progress)
                except Exception as e:
                    print(f"[Anomaly] 重排班失败: {e}")
                    _set_execute_progress(100, f"部分完成（重排班出错: {e}）", "partial")
                    return

            is_aircraft = plan.strategy == 'AircraftExclusionRecovery'
            _set_execute_progress(100, "执行完成", "done", {
                "plan": plan.to_dict(),
                "summary": {
                    "total_flights": len(executed.get('flights', [])),
                    "delayed": sum(1 for c in plan.flight_changes if c.get('change_type') == 'DELAY'),
                    "canceled": sum(1 for c in plan.flight_changes if c.get('change_type') == 'CANCEL'),
                    "reassigned": sum(1 for c in plan.flight_changes if c.get('change_type') == 'REASSIGN_AIRCRAFT'),
                    "excluded_aircraft": executed.get('excluded_aircraft', []),
                    "is_aircraft_recovery": is_aircraft,
                }
            })
        except Exception as e:
            print(f"[Anomaly] 执行异常: {e}")
            _set_execute_progress(0, f"执行失败: {e}", "error", {"msg": str(e)})

    threading.Thread(target=_run, daemon=True).start()
    return _ok({"status": "started"}, "开始执行恢复方案")


# ============================================================
#  备份资源
# ============================================================

@anomaly_bp.route('/backup-resources', methods=['GET'])
def get_backup_resources():
    """获取备份资源"""
    return _ok(recovery_service._backup_resources)


@anomaly_bp.route('/backup-resources', methods=['PUT'])
def set_backup_resources():
    """设置备份资源"""
    body = request.get_json() or {}
    recovery_service.set_backup_resources(
        aircraft=body.get('aircraft'),
        crew=body.get('crew'),
        gates=body.get('gates'),
        runways=body.get('runways'),
    )
    return _ok({"resources": recovery_service._backup_resources}, "备份资源已更新")


@anomaly_bp.route('/backup-resources/generate', methods=['POST'])
def generate_backup_resources():
    """从当前排班数据自动生成备份资源池"""
    schedule = _get_schedule()
    if not schedule:
        return _err("当前没有排班数据", 400)

    flights = schedule.get("flights", [])
    aircraft_map = schedule.get("aircraft_assignments", {})
    crew_map = schedule.get("crew_assignments", {})

    used_tails = set(aircraft_map.values())
    used_crew = set()
    for cids in crew_map.values():
        used_crew.update(cids)

    try:
        from ..services.data_service import data_service
        data_service.load_all()
        all_aircraft = data_service.aircrafts
    except Exception:
        all_aircraft = []

    backup_aircraft = []
    for ac in all_aircraft:
        if ac.tail_no not in used_tails:
            backup_aircraft.append({
                "tail_no": ac.tail_no,
                "ac_type": ac.ac_type if hasattr(ac, 'ac_type') else "",
                "base": ac.base if hasattr(ac, 'base') else "",
                "status": "idle",
            })

    airports_in_use = set()
    for f in flights:
        airports_in_use.add(f.departure_airport if hasattr(f, 'departure_airport') else "")
        airports_in_use.add(f.arrival_airport if hasattr(f, 'arrival_airport') else "")

    backup_gates = []
    backup_runways = []
    for ap in sorted(airports_in_use):
        backup_gates.append({"gate_id": f"{ap}_G99", "terminal": "T1", "status": "idle"})
        backup_gates.append({"gate_id": f"{ap}_G98", "terminal": "T2", "status": "idle"})
        backup_runways.append({"runway_id": f"{ap}_RWY_02L", "status": "idle"})
        backup_runways.append({"runway_id": f"{ap}_RWY_02R", "status": "idle"})

    backup_crew = []
    if crew_map:
        all_crew_ids = set()
        for cids in crew_map.values():
            all_crew_ids.update(cids)
        for i in range(1, 11):
            cid = f"BK_CRW_{i:03d}"
            if cid not in all_crew_ids:
                backup_crew.append({
                    "crew_id": cid, "role": "FO" if i % 2 == 0 else "CA",
                    "status": "available", "base": "成都",
                })

    recovery_service.set_backup_resources(
        aircraft=backup_aircraft, crew=backup_crew,
        gates=backup_gates, runways=backup_runways,
    )

    return _ok({"resources": recovery_service._backup_resources}, "备份资源已自动生成")


# ============================================================
#  模块联动 Overlays
# ============================================================

@anomaly_bp.route('/overlays', methods=['GET'])
def get_overlays():
    """获取异常标记覆盖数据"""
    status_filter = request.args.get('status', '')
    events = anomaly_service.list_events(status_filter)

    overlays = {
        "flights": {},
        "aircraft": {},
        "crew": {},
        "gates": {},
        "runways": {},
        "airports": {},
    }

    for event in events:
        impact = getattr(event, 'impact_report', None)
        plan = getattr(event, 'recovery_plan', None)

        for ap in (event.affected_airports or []):
            overlays["airports"][ap] = {
                "status": event.status,
                "priority": event.priority,
                "event_id": event.event_id,
                "reason": event.title,
            }

        for tail in (event.affected_aircraft or []):
            overlays["aircraft"][tail] = {
                "status": event.status,
                "reason": event.title,
                "event_id": event.event_id,
            }

        if impact:
            direct = impact.get("direct_impacted_flights", [])
            cascade = impact.get("cascade_chains", [])
            for item in direct:
                fid = item.get('flight_id', item) if isinstance(item, dict) else item
                overlays["flights"][str(fid)] = {
                    "status": "impacted_direct",
                    "event_id": event.event_id,
                    "reason": "直接影响",
                }
            for entry in cascade:
                fid = entry.get("flight_id")
                if fid:
                    overlays["flights"][fid] = {
                        "status": "impacted_cascade",
                        "delay_minutes": entry.get("delay_minutes", 0),
                        "level": entry.get("level", 1),
                        "event_id": event.event_id,
                        "reason": entry.get("reason", ""),
                    }

        if plan:
            for change in plan.get("aircraft_changes", []):
                fid = change.get("flight_id")
                if fid and fid in overlays["flights"]:
                    overlays["flights"][fid]["recovery_status"] = "reassigned"
                    overlays["flights"][fid]["new_aircraft"] = change.get("new_value")
            for change in plan.get("gate_changes", []):
                fid = change.get("flight_id")
                if fid and fid in overlays["flights"]:
                    overlays["flights"][fid]["recovery_status"] = "gate_changed"
            for change in plan.get("crew_changes", []):
                fid = change.get("flight_id")
                if fid and fid in overlays["flights"]:
                    overlays["flights"][fid]["recovery_status"] = "crew_changed"

        for gid in (event.affected_gates or []):
            overlays["gates"][gid] = {
                "status": event.status,
                "reason": event.title,
                "event_id": event.event_id,
            }

        for rid in (event.affected_runways or []):
            overlays["runways"][rid] = {
                "status": event.status,
                "reason": event.title,
                "event_id": event.event_id,
            }

    return _ok(overlays)


# ============================================================
#  执行 / 回滚 / 人工微调
# ============================================================


@anomaly_bp.route('/plans/<plan_id>/rollback', methods=['POST'])
def rollback_plan(plan_id):
    """回滚恢复方案"""
    plan = recovery_service.get_plan(plan_id)
    if not plan:
        return _err("方案不存在", 404)

    rollback_events = []
    for change in plan.flight_changes:
        rollback_events.append({
            "flight_id": change.get("flight_id"),
            "change_type": change.get("change_type"),
            "rollback_from": change.get("new_value"),
            "rollback_to": change.get("old_value"),
        })

    plan.status = "rolled_back"
    event = anomaly_service.get_event(plan.event_id)
    if event:
        from ..models.abnormal_event import AnomalyStatus
        anomaly_service.update_event(plan.event_id, status=AnomalyStatus.PENDING)

    from ..services.audit_log_service import audit_log
    audit_log.log("rollback", "plan", plan_id,
                  f"回滚 {len(rollback_events)} 项变更")

    return _ok({"rollback_events": rollback_events}, "方案已回滚")


@anomaly_bp.route('/plans/<plan_id>/adjust', methods=['POST'])
def adjust_plan(plan_id):
    """人工微调恢复方案"""
    body = request.get_json() or {}
    plan = recovery_service.get_plan(plan_id)
    if not plan:
        return _err("方案不存在", 404)

    adjustments = body.get("adjustments", [])

    for adj in adjustments:
        change_type = adj.get("change_type", "")
        flight_id = adj.get("flight_id", "")
        new_value = adj.get("new_value", "")
        reason = adj.get("reason", "人工微调")
        entry = {
            "flight_id": flight_id,
            "change_type": change_type,
            "old_value": adj.get("old_value", ""),
            "new_value": new_value,
            "reason": reason,
        }
        ct = change_type.lower()
        if "aircraft" in ct:
            plan.aircraft_changes.append(entry)
        elif "crew" in ct:
            plan.crew_changes.append(entry)
        elif "gate" in ct:
            plan.gate_changes.append(entry)
        elif "runway" in ct:
            plan.runway_changes.append(entry)

    plan.flight_changes = (
        plan.aircraft_changes + plan.crew_changes +
        plan.gate_changes + plan.runway_changes
    )

    from ..services.audit_log_service import audit_log
    audit_log.log("adjust", "plan", plan_id,
                  f"人工微调 {len(adjustments)} 条变更")

    return _ok({"plan": plan.to_dict()}, f"已微调 {len(adjustments)} 项")


# ============================================================
#  审计日志
# ============================================================

@anomaly_bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """获取审计日志"""
    action = request.args.get('action')
    target_type = request.args.get('target_type')
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', type=int, default=0)

    from ..services.audit_log_service import audit_log
    logs = audit_log.get_logs(action=action, target_type=target_type, limit=limit, offset=offset)

    return _ok({"logs": logs, "count": len(logs)})


@anomaly_bp.route('/audit-log/clear', methods=['POST'])
def clear_audit_log():
    """清空审计日志"""
    from ..services.audit_log_service import audit_log
    audit_log.clear()
    return _ok(None, "审计日志已清空")


# ============================================================
#  批量操作
# ============================================================

@anomaly_bp.route('/events/batch-analyze', methods=['POST'])
def batch_analyze():
    """批量分析多个事件（处理叠加异常场景）"""
    body = request.get_json() or {}
    event_ids = body.get("event_ids", [])
    if not event_ids:
        return _err("需要 event_ids", 400)

    schedule = _get_schedule()
    if not schedule:
        return _err("当前没有排班数据", 400)

    results = []
    for event_id in event_ids:
        event = anomaly_service.get_event(event_id)
        if not event:
            results.append({"event_id": event_id, "error": "事件不存在"})
            continue
        impact, plan = recovery_service.generate_recovery_plan(event, schedule)
        anomaly_service.set_impact_report(event_id, impact.to_dict())
        anomaly_service.set_recovery_plan(event_id, plan.to_dict())
        results.append({
            "event_id": event_id,
            "impact": impact.to_dict(),
            "plan": plan.to_dict(),
        })

    return _ok({"results": results, "count": len(results)})


# ============================================================
#  依赖注入
# ============================================================

_schedule_getter = None
_post_execute_handler = None

# 执行进度追踪
_execution_progress = {"progress": 0, "stage": "", "status": "idle", "result": None}
_progress_lock = threading.Lock()


@anomaly_bp.route('/execute-progress', methods=['GET'])
def get_execute_progress():
    """轮询恢复方案执行进度"""
    with _progress_lock:
        return jsonify({
            "code": 0,
            "data": dict(_execution_progress),
        })


def _set_execute_progress(progress, stage, status="running", result=None):
    """更新执行进度（线程安全）"""
    with _progress_lock:
        _execution_progress["progress"] = progress
        _execution_progress["stage"] = stage
        _execution_progress["status"] = status
        if result is not None:
            _execution_progress["result"] = result


def set_schedule_getter(getter):
    """设置排班数据获取函数（由 app.py 注入）"""
    global _schedule_getter
    _schedule_getter = getter


def set_post_execute_handler(handler):
    """设置执行恢复方案后的重排班回调（由 app.py 注入）"""
    global _post_execute_handler
    _post_execute_handler = handler


_clear_crew_cache_func = lambda: None


def set_clear_crew_cache_func(func):
    """设置清除机组替班缓存的回调（由 app.py 注入）"""
    global _clear_crew_cache_func
    _clear_crew_cache_func = func


def _get_schedule():
    """获取当前排班状态"""
    if _schedule_getter:
        return _schedule_getter()
    return None
