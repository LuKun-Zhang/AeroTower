"""恢复服务 — 机场异常恢复方案生成与执行

机场异常恢复逻辑：
  1. 分析每个受影响航班的推迟时间
  2. 推迟 >= 5 小时的航班 → 取消（CANCEL）
  3. 推迟 < 5 小时的航班 → 延迟（DELAY）
  4. 生成 RecoveryPlan 包含每个航班的 new_departure / new_arrival
  5. execute_plan: 实际修改调度数据（飞机/机组重新分配）
"""

import copy
import os
import time
from datetime import datetime, timedelta

from ..models.recovery_plan import RecoveryPlan, RecoveryPlanStatus, ChangeType
from ..services.impact_analysis_service import impact_analysis_service, CANCEL_DELAY_THRESHOLD
from ..services.data_service import data_service
from ..utils.city_geo import (get_province_airports, get_affected_flights_by_province,
                               get_city_province, build_transit_cache_from_flights,
                               normalize_city_name)


class RecoveryService:
    """恢复流程编排 + 执行"""

    def __init__(self):
        self._plans = {}
        self._backup_resources = {
            "backup_aircraft": [],
            "backup_crew": [],
            "backup_gates": [],
            "backup_runways": [],
        }
        # 存储执行后的调度快照供前端查询
        self._executed_schedules = {}

    def set_backup_resources(self, aircraft=None, crew=None, gates=None, runways=None):
        if aircraft is not None:
            self._backup_resources["backup_aircraft"] = aircraft
        if crew is not None:
            self._backup_resources["backup_crew"] = crew
        if gates is not None:
            self._backup_resources["backup_gates"] = gates
        if runways is not None:
            self._backup_resources["backup_runways"] = runways

    def generate_recovery_plan(self, event, schedule):
        """生成异常恢复方案"""
        etype = getattr(event, 'event_type', '')
        
        # 入口诊断：print + 文件
        print(f"\n[Recovery/Entry] event_type='{etype}', schedule_keys={list(schedule.keys()) if schedule else 'NONE'}", flush=True)
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'crew_recovery_debug.log')
        try:
            with open(log_path, 'a', encoding='utf-8') as _logf:
                _logf.write(f"\n=== generate_recovery_plan {time.strftime('%H:%M:%S')} ===\n")
                _logf.write(f"event_type: {etype}\n")
                _logf.write(f"schedule keys: {list(schedule.keys()) if schedule else 'NONE'}\n")
        except Exception:
            pass
        
        if etype in ('aircraft_failure', 'aircraft_maintenance', 'aircraft_diversion'):
            print(f"[Recovery/Entry] → aircraft recovery", flush=True)
            return self._generate_aircraft_recovery_plan(event, schedule)
        if etype in ('weather_storm', 'weather_rain', 'weather_snow', 'weather_fog', 'weather_typhoon'):
            print(f"[Recovery/Entry] → weather recovery", flush=True)
            return self._generate_weather_recovery_plan(event, schedule)
        if etype == 'crew_substitution':
            print(f"[Recovery/Entry] → crew_substitution (机组替班)", flush=True)
            return self._generate_crew_substitution_plan(event, schedule)
        print(f"[Recovery/Entry] → 降级 airport recovery (etype='{etype}' 不匹配)", flush=True)
        return self._generate_airport_recovery_plan(event, schedule)

    def _generate_aircraft_recovery_plan(self, event, schedule):
        """飞机异常恢复方案：剔除故障飞机 → 重新分配航班"""
        from ..models.impact_report import ImpactReport
        affected_tails = set(event.affected_aircraft or [])
        flights = schedule.get('flights', [])
        aircraft_map = schedule.get('aircraft_assignments', {})

        print(f"[Recovery/Aircraft] 受影响飞机: {affected_tails}")

        # 找出受影响的航班（当前分配给故障飞机的航班）
        affected_flight_ids = set()
        for fid, tail in aircraft_map.items():
            if tail in affected_tails:
                affected_flight_ids.add(str(fid))

        print(f"[Recovery/Aircraft] 受影响航班: {len(affected_flight_ids)} 个")

        # 构建航班信息
        flight_by_id = {}
        for f in flights:
            fid = str(getattr(f, 'flight_id', ''))
            if fid:
                flight_by_id[fid] = f

        flight_changes = []
        for fid in sorted(affected_flight_ids):
            f = flight_by_id.get(fid)
            flight_changes.append({
                "flight_id": fid,
                "flight_no": getattr(f, 'flight_no', '') if f else '',
                "change_type": ChangeType.REASSIGN_AIRCRAFT,
                "departure_airport": getattr(f, 'departure_airport', '') if f else '',
                "arrival_airport": getattr(f, 'arrival_airport', '') if f else '',
                "origin_dep": self._format_flight_time(f, 'time_departure') if f else '',
                "origin_arr": self._format_flight_time(f, 'time_arrival') if f else '',
                "new_dep": self._format_flight_time(f, 'time_departure') if f else '',
                "new_arr": self._format_flight_time(f, 'time_arrival') if f else '',
                "delay_minutes": 0,
                "reason": f"飞机 {','.join(affected_tails)} 不可用，需重新分配飞机",
                "level": 0,
            })

        # 生成影响报告
        impact = ImpactReport(
            report_id=f"rpt_{event.event_id}",
            event_id=event.event_id,
            direct_impacted_flights=list(affected_flight_ids),
            direct_impacted_aircraft=list(affected_tails),
            cascade_chains=[],
            total_impacted_flights=len(affected_flight_ids),
            total_impacted_aircraft=len(affected_tails),
            total_delay_minutes=0,
            flights_to_cancel=[],
            timeline_changes={},
        )

        plan = RecoveryPlan(
            plan_id=f"plan_{event.event_id}",
            event_id=event.event_id,
            strategy="AircraftExclusionRecovery",
            flight_changes=flight_changes,
            canceled_flights=[],
            coverage_rate=1.0 if affected_flight_ids else 0.0,
            total_delay_minutes=0,
            avg_delay_minutes=0.0,
            status=RecoveryPlanStatus.DRAFT,
            before_metrics={
                "affected_aircraft": len(affected_tails),
                "affected_flights": len(affected_flight_ids),
            },
            after_metrics={
                "reassigned": len(affected_flight_ids),
                "aircraft_to_exclude": list(affected_tails),
            },
        )

        self._plans[plan.plan_id] = plan
        print(f"[Recovery/Aircraft] 方案: 重新分配 {len(affected_flight_ids)} 个航班")

        return impact, plan

    def _generate_weather_recovery_plan(self, event, schedule):
        """天气异常恢复方案：省份→机场→委托机场异常 BFS 级联分析 + 途经航班补充"""
        from copy import deepcopy
        from ..models.impact_report import ImpactReport

        weather_provinces = set(event.affected_airports or [])
        transit_cache = schedule.get('transit_cache', {})
        flights = schedule.get('flights', [])

        print(f"[Recovery/Weather] 受影响省份: {weather_provinces}")

        # 1) 省份 → 机场名列表
        province_airports = get_province_airports(weather_provinces)
        # 收集系统中实际存在的机场名
        actual_airports = set()
        for f in flights:
            actual_airports.add(getattr(f, 'departure_airport', ''))
            actual_airports.add(getattr(f, 'arrival_airport', ''))

        # 模糊匹配：系统中"长沙黄花" → CITY_GEO 中的"长沙"
        fuzzy_map = {}  # actual_airport → CITY_GEO_city
        for ap in actual_airports:
            mapped = normalize_city_name(ap)
            if mapped:
                fuzzy_map[ap] = mapped

        matched_airports = []
        for ap in actual_airports:
            city = fuzzy_map.get(ap)
            if city and city in province_airports:
                matched_airports.append(ap)

        print(f"[Recovery/Weather] 省份→机场: {len(province_airports)} 个城市, "
              f"模糊匹配 {len(matched_airports)} 个: {matched_airports[:10]}...")

        # 2) 途经航班：如果缓存为空，按需重建
        if not transit_cache:
            print("[Recovery/Weather] transit_cache 为空，按需重建...")
            transit_cache = build_transit_cache_from_flights(flights)
            print(f"[Recovery/Weather] 重建 transit_cache: {len(transit_cache)} 条")

        affected = get_affected_flights_by_province(flights, weather_provinces, transit_cache)
        transit_ids = affected['transit']

        print(f"[Recovery/Weather] 直达={len(matched_airports)} 个机场, "
              f"途经={len(transit_ids)} 个航班")

        # 如果既没有直达机场也没有途经航班 → 空方案
        if not matched_airports and not transit_ids:
            print("[Recovery/Weather] 该省无任何受影响航班")
            impact = ImpactReport(
                report_id=f"rpt_{event.event_id}",
                event_id=event.event_id,
                direct_impacted_flights=[],
                total_impacted_flights=0,
            )
            plan = RecoveryPlan(
                plan_id=f"plan_{event.event_id}",
                event_id=event.event_id,
                strategy="WeatherProvinceRecovery",
                flight_changes=[],
                canceled_flights=[],
                coverage_rate=0.0,
                status=RecoveryPlanStatus.DRAFT,
            )
            self._plans[plan.plan_id] = plan
            return impact, plan

        # 3) 直达航班：临时修改 event.affected_airports 为机场名 → 委托机场异常 BFS 级联分析
        if matched_airports:
            saved_airports = event.affected_airports
            event.affected_airports = matched_airports
            try:
                impact, plan = self._generate_airport_recovery_plan(event, schedule)
            finally:
                event.affected_airports = saved_airports
        else:
            # 仅有途经航班，构建基础方案
            impact = ImpactReport(
                report_id=f"rpt_{event.event_id}",
                event_id=event.event_id,
                direct_impacted_flights=list(transit_ids),
                total_impacted_flights=len(transit_ids),
            )
            plan = RecoveryPlan(
                plan_id=f"plan_{event.event_id}",
                event_id=event.event_id,
                strategy="WeatherProvinceRecovery",
                flight_changes=[],
                canceled_flights=[],
                coverage_rate=0.0,
                status=RecoveryPlanStatus.DRAFT,
            )

        # 4) 补充途经航班到方案中
        if transit_ids:
            print(f"[Recovery/Weather] 补充途经航班: {len(transit_ids)} 个")
            flight_by_id = {}
            for f in flights:
                fid = getattr(f, 'flight_id', '')
                if fid:
                    flight_by_id[str(fid)] = f

            # 途经航班：统一加 60 分钟绕飞延迟
            existing_fids = {c['flight_id'] for c in plan.flight_changes}
            for fid in transit_ids:
                sfid = str(fid)
                if sfid in existing_fids:
                    continue  # 已经作为直达航班处理过了
                f = flight_by_id.get(sfid)
                if not f:
                    continue
                new_dep, new_arr = self._compute_delayed_times(f, 60)
                plan.flight_changes.append({
                    "flight_id": sfid,
                    "flight_no": getattr(f, 'flight_no', ''),
                    "change_type": ChangeType.DELAY,
                    "departure_airport": getattr(f, 'departure_airport', ''),
                    "arrival_airport": getattr(f, 'arrival_airport', ''),
                    "origin_dep": self._format_flight_time(f, 'time_departure'),
                    "origin_arr": self._format_flight_time(f, 'time_arrival'),
                    "new_dep": new_dep,
                    "new_arr": new_arr,
                    "delay_minutes": 60,
                    "reason": f"航线途经{'、'.join(weather_provinces)}受天气影响，绕飞+60min",
                    "level": 1,
                })
                plan.total_delay_minutes += 60
                plan.before_metrics['transit_impacted'] = plan.before_metrics.get('transit_impacted', 0) + 1

        # 4) 更新策略标签 + 指标
        plan.strategy = "WeatherProvinceRecovery"
        plan.before_metrics['weather_provinces'] = list(weather_provinces)
        plan.after_metrics['weather_provinces'] = list(weather_provinces)

        # 5) 合并直达 + 途经的受影响航班
        impact.direct_impacted_flights = list(
            set(impact.direct_impacted_flights or []) | transit_ids
        )
        impact.total_impacted_flights = max(
            impact.total_impacted_flights or 0, len(plan.flight_changes)
        )
        impact.total_delay_minutes = plan.total_delay_minutes

        print(f"[Recovery/Weather] 最终: 延迟{len([c for c in plan.flight_changes if c.get('change_type')==ChangeType.DELAY])}班 "
              f"/ 取消{len(plan.canceled_flights)}班 / 总延迟{plan.total_delay_minutes}min")

        return impact, plan

    def _generate_airport_recovery_plan(self, event, schedule):
        """机场异常恢复方案：延迟/取消受影响航班"""
        print(f"[Recovery] 开始影响分析: event={event.event_id}")
        impact = impact_analysis_service.analyze(event, schedule)
        print(f"[Recovery] 直接影响={len(impact.direct_impacted_flights)}, "
              f"级联={len(impact.cascade_chains)}, "
              f"拟取消={len(impact.flights_to_cancel)}, "
              f"总延迟={impact.total_delay_minutes}分钟")

        flights = {f.flight_id: f for f in (schedule.get('flights', []))
                   if hasattr(f, 'flight_id')}
        timeline = impact.timeline_changes or {}

        flight_changes = []
        canceled_flights = []
        delayed_flights = []

        for fid, info in timeline.items():
            delay = info.get('delay_minutes', 0)
            flight = flights.get(fid)

            if delay >= CANCEL_DELAY_THRESHOLD:
                # 取消
                canceled_flights.append({
                    "flight_id": fid,
                    "flight_no": getattr(flight, 'flight_no', '') if flight else '',
                    "departure_airport": getattr(flight, 'departure_airport', '') if flight else '',
                    "arrival_airport": getattr(flight, 'arrival_airport', '') if flight else '',
                    "origin_dep": self._format_flight_time(flight, 'time_departure') if flight else '',
                    "origin_arr": self._format_flight_time(flight, 'time_arrival') if flight else '',
                    "delay_minutes": delay,
                    "reason": f"推迟{delay}分钟(>=5小时)，建议取消",
                    "level": info.get('level', 0),
                    "is_direct": fid in (impact.direct_impacted_flights or []),
                })
                flight_changes.append({
                    "flight_id": fid,
                    "flight_no": getattr(flight, 'flight_no', '') if flight else '',
                    "change_type": ChangeType.CANCEL,
                    "departure_airport": getattr(flight, 'departure_airport', '') if flight else '',
                    "arrival_airport": getattr(flight, 'arrival_airport', '') if flight else '',
                    "origin_dep": self._format_flight_time(flight, 'time_departure') if flight else '',
                    "origin_arr": self._format_flight_time(flight, 'time_arrival') if flight else '',
                    "new_dep": "CANCELED",
                    "new_arr": "CANCELED",
                    "delay_minutes": delay,
                    "reason": f"推迟{delay}分钟(>=5小时)，建议取消",
                    "level": info.get('level', 0),
                })
            else:
                # 延迟：计算新的起飞/降落时间
                new_dep, new_arr = self._compute_delayed_times(flight, delay)
                delayed_flights.append({
                    "flight_id": fid,
                    "flight_no": getattr(flight, 'flight_no', '') if flight else '',
                    "departure_airport": getattr(flight, 'departure_airport', '') if flight else '',
                    "arrival_airport": getattr(flight, 'arrival_airport', '') if flight else '',
                    "origin_dep": self._format_flight_time(flight, 'time_departure') if flight else '',
                    "origin_arr": self._format_flight_time(flight, 'time_arrival') if flight else '',
                    "new_dep": new_dep,
                    "new_arr": new_arr,
                    "delay_minutes": delay,
                    "reason": f"推迟{delay}分钟",
                    "level": info.get('level', 0),
                    "is_direct": fid in (impact.direct_impacted_flights or []),
                })
                flight_changes.append({
                    "flight_id": fid,
                    "flight_no": getattr(flight, 'flight_no', '') if flight else '',
                    "change_type": ChangeType.DELAY,
                    "departure_airport": getattr(flight, 'departure_airport', '') if flight else '',
                    "arrival_airport": getattr(flight, 'arrival_airport', '') if flight else '',
                    "origin_dep": self._format_flight_time(flight, 'time_departure') if flight else '',
                    "origin_arr": self._format_flight_time(flight, 'time_arrival') if flight else '',
                    "new_dep": new_dep,
                    "new_arr": new_arr,
                    "delay_minutes": delay,
                    "reason": f"推迟{delay}分钟",
                    "level": info.get('level', 0),
                })

        # 按 level 排序（直接 > 级联 level1 > level2 ...）
        flight_changes.sort(key=lambda c: (c.get("level", 99), c["flight_id"]))

        affected_set = set(
            [e.get("flight_id") for e in impact.cascade_chains] +
            (impact.direct_impacted_flights or [])
        )
        all_changed = {c["flight_id"] for c in flight_changes}
        coverage = len(affected_set.intersection(all_changed)) / len(affected_set) if affected_set else 1.0

        plan = RecoveryPlan(
            plan_id=f"plan_{event.event_id}",
            event_id=event.event_id,
            strategy="AirportClosureRecovery",
            flight_changes=flight_changes,
            canceled_flights=canceled_flights,
            coverage_rate=coverage,
            total_delay_minutes=impact.total_delay_minutes,
            avg_delay_minutes=(
                impact.total_delay_minutes / len(delayed_flights)
                if delayed_flights else 0
            ),
            status=RecoveryPlanStatus.DRAFT,
            before_metrics={
                "total_delay": impact.total_delay_minutes,
                "impacted_flights": impact.total_impacted_flights,
            },
            after_metrics={
                "total_delay": sum(
                    c["delay_minutes"] for c in flight_changes
                    if c["change_type"] == ChangeType.DELAY
                ),
                "canceled": len(canceled_flights),
                "delayed": len(delayed_flights),
            },
        )

        self._plans[plan.plan_id] = plan
        print(f"[Recovery] 方案: 取消{len(canceled_flights)}班 / 延迟{len(delayed_flights)}班 / 覆盖率{coverage:.0%}")

        return impact, plan

    def execute_plan(self, plan_id, schedule):
        """执行恢复方案，实际修改调度数据

        飞机异常（AircraftExclusionRecovery）：不修改航班，仅标记排除飞机
        机场异常：延迟/取消航班

        将修改后的调度写入 _executed_schedules，供前端查询。
        返回修改后的调度快照。
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        # 飞机异常：不修改航班，仅传递排除信息
        if plan.strategy == 'AircraftExclusionRecovery':
            excluded_tails = plan.after_metrics.get('aircraft_to_exclude', [])
            executed = copy.deepcopy(schedule)
            executed['excluded_aircraft'] = excluded_tails
            plan.status = RecoveryPlanStatus.EXECUTED
            self._executed_schedules[plan_id] = executed
            print(f"[Execute/Aircraft] 排除飞机: {excluded_tails}, 航班不变")
            return executed

        # 机组替班：传递 crew_changes，由 post_execute_handler 重新排班
        if plan.strategy == 'CrewSubstitutionRecovery':
            executed = copy.deepcopy(schedule)
            executed['crew_substitutions'] = plan.crew_changes
            plan.status = RecoveryPlanStatus.EXECUTED
            self._executed_schedules[plan_id] = executed
            print(f"[Execute/Crew] 替班变更: {len(plan.crew_changes)} 项")
            return executed

        # 机场异常：原逻辑
        executed = copy.deepcopy(schedule)
        flights_list = executed.get('flights', [])
        chains = executed.get('chains', [])

        # 构建航班索引
        flight_index = {}
        for f in flights_list:
            fid = getattr(f, 'flight_id', '')
            if fid:
                flight_index[fid] = f

        # 分离取消和延迟的航班
        cancel_ids = set()
        delay_map = {}  # fid -> delay_minutes

        for change in plan.flight_changes:
            fid = change.get('flight_id', '')
            if fid not in flight_index:
                continue
            if change.get('change_type') == ChangeType.CANCEL:
                cancel_ids.add(fid)
            elif change.get('change_type') == ChangeType.DELAY:
                delay_map[fid] = change.get('delay_minutes', 0)

        # 执行取消：从 flights 和 chains 中移除
        if cancel_ids:
            executed['flights'] = [
                f for f in flights_list
                if getattr(f, 'flight_id', '') not in cancel_ids
            ]
            new_chains = []
            for chain in chains:
                new_chain = [
                    f for f in chain
                    if getattr(f, 'flight_id', '') not in cancel_ids
                ]
                if new_chain:
                    new_chains.append(new_chain)
            executed['chains'] = new_chains
            print(f"[Execute] 取消 {len(cancel_ids)} 个航班")

        # 执行延迟：修改 time_departure 和 time_arrival
        delay_count = 0
        for f in executed['flights']:
            fid = getattr(f, 'flight_id', '')
            if fid in delay_map:
                delay = delay_map[fid]
                self._apply_delay(f, delay)
                delay_count += 1
        print(f"[Execute] 延迟 {delay_count} 个航班")

        plan.status = RecoveryPlanStatus.EXECUTED
        self._executed_schedules[plan_id] = executed
        return executed

    def get_executed_schedule(self, plan_id):
        """获取执行后的调度快照"""
        return self._executed_schedules.get(plan_id)

    def get_plan(self, plan_id):
        return self._plans.get(plan_id)

    def _generate_crew_substitution_plan(self, event, schedule):
        """机组替班恢复方案：查找受影响航班 → 同基地同角色替班"""
        from ..models.impact_report import ImpactReport
        from ..services.crew_service import find_crew_substitute

        affected_names = set(event.affected_crew or [])
        start_time = getattr(event, 'start_time', '')
        end_time = getattr(event, 'end_time', '')
        crew_assignments = schedule.get('crew_assignments', {})
        crew_pool = schedule.get('crew_pool', [])
        flights = schedule.get('flights', [])
        chains = schedule.get('chains', [])

        # ========== 全线诊断：输出到 console + 文件 ==========
        import sys, re
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'crew_recovery_debug.log')
        
        def _diag(msg):
            """同时输出到 stdout 和日志文件"""
            print(msg, flush=True)
            try:
                with open(log_path, 'a', encoding='utf-8') as _f:
                    _f.write(msg + '\n')
            except Exception as e:
                print(f"[DIAG] 日志文件写入失败: {e}", flush=True)

        _diag(f"\n{'='*60}")
        _diag(f"=== _generate_crew_substitution_plan {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        _diag(f"affected_names: {affected_names}")
        _diag(f"crew_pool size: {len(crew_pool)}")
        _diag(f"crew_assignments dict size: {len(crew_assignments) if crew_assignments else 0}")
        _diag(f"flights size: {len(flights)}")
        _diag(f"start_time: '{start_time}', end_time: '{end_time}'")

        # 构建索引：name → CrewMember, crew_id → CrewMember
        crew_by_id = {}
        crew_by_name = {}
        for c in crew_pool:
            cid = str(getattr(c, 'crew_id', id(c)))
            crew_by_id[cid] = c
            name = getattr(c, 'name', '')
            if name:
                crew_by_name[name] = c

        _diag(f"crew_by_name 总人数: {len(crew_by_name)}")
        _diag(f"crew_by_name 前30名: {list(crew_by_name.keys())[:30]}")

        # 先解析 name → crew_id，同时确认人员是否存在
        affected_crew_ids = set()
        for name in affected_names:
            cm = crew_by_name.get(name)
            if cm:
                cid = str(getattr(cm, 'crew_id', name))
                affected_crew_ids.add(cid)
                af = getattr(cm, 'assigned_flights', []) or []
                _diag(f"  [找到] {name}: crew_id={cid}, assigned_flights={len(af)}")
            else:
                affected_crew_ids.add(name)
                _diag(f"  [未找到] {name}: NOT in crew_by_name")

        _diag(f"affected_crew_ids: {affected_crew_ids}")

        # 查找受影响航班
        affected_flight_ids = set()
        _diag(f"开始查找受影响航班: crew_assignments非空={bool(crew_assignments)}")
        
        if crew_assignments:
            match_count = 0
            for fid, assigned in crew_assignments.items():
                crew_list = assigned if isinstance(assigned, list) else [assigned]
                for crew_ref in crew_list:
                    cid = str(crew_ref)
                    if cid in affected_crew_ids:
                        affected_flight_ids.add(str(fid))
                        match_count += 1
                        _diag(f"  匹配: fid={fid}, cid={cid}")
                        break
            _diag(f"crew_assignments 匹配: {match_count} 个航班")
        else:
            _diag(f"crew_assignments 为空，从 crew_pool.assigned_flights 查找")
            for cm in crew_pool:
                cm_name = getattr(cm, 'name', '')
                cm_cid = str(getattr(cm, 'crew_id', ''))
                if cm_name in affected_names or cm_cid in affected_crew_ids:
                    assigned = getattr(cm, 'assigned_flights', []) or []
                    _diag(f"  {cm_name}({cm_cid}): {len(assigned)} 个航班")
                    for af in assigned:
                        if isinstance(af, dict):
                            flight_obj = af.get('flight')
                            fid = str(getattr(flight_obj, 'flight_id', '')) if flight_obj else ''
                        elif hasattr(af, 'flight_id'):
                            fid = str(af.flight_id)
                        else:
                            fid = str(af.get('flight_id', '') or af.get('id', ''))
                        if fid:
                            affected_flight_ids.add(fid)
                            _diag(f"    → fid={fid}")

        _diag(f"受影响航班（时间过滤前）: {len(affected_flight_ids)} 个, ids={affected_flight_ids}")

        # 时间过滤
        def _parse_time_to_min(t_str):
            m = re.match(r'(\d{4})-(\d+)-(\d+)\s+(\d+):(\d+)', (t_str or '').strip())
            if not m:
                _diag(f"  [时间解析失败] '{t_str}'")
                return None
            month, day, hour, minute = int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
            result = (month - 11) * 30 * 24 * 60 + day * 24 * 60 + hour * 60 + minute
            return result

        absence_start_min = _parse_time_to_min(start_time)
        absence_end_min = _parse_time_to_min(end_time)
        _diag(f"请假时间: start_min={absence_start_min}, end_min={absence_end_min}")

        if absence_start_min is not None and absence_end_min is not None:
            # 构建 flight_id → (departure_minutes, end_minutes) 映射
            fid_time_map = {}
            for c in crew_pool:
                for af in (getattr(c, 'assigned_flights', []) or []):
                    flight_obj = None
                    ds = 0
                    de = 0
                    if isinstance(af, dict):
                        flight_obj = af.get('flight')
                        ds = af.get('duty_start_min', 0)
                        de = af.get('duty_end_min', 0)
                    elif hasattr(af, 'flight_id'):
                        flight_obj = af
                        ds = getattr(af, 'duty_start_min', 0)
                        de = getattr(af, 'duty_end_min', 0)
                    if flight_obj:
                        fid = str(getattr(flight_obj, 'flight_id', ''))
                        if fid:
                            fid_time_map[fid] = (ds, de)
            # 补充航班时间
            for f_obj in flights:
                fid = str(getattr(f_obj, 'flight_id', ''))
                if fid and fid not in fid_time_map:
                    dm = getattr(f_obj, 'departure_minutes', 0)
                    ts = getattr(f_obj, 'timespan', 60)
                    fid_time_map[fid] = (dm, dm + ts)

            _diag(f"fid_time_map 条目数: {len(fid_time_map)}")

            # 过滤：只有 ds>0 且 de>0 的航班才做时间比对
            # ds=0 或 de=0 表示缺失时间数据，保留该航班（不过滤），避免遗漏
            filtered_ids = set()
            for fid in affected_flight_ids:
                ds, de = fid_time_map.get(fid, (0, 0))
                if ds > 0 and de > 0:
                    if ds < absence_end_min and de > absence_start_min:
                        filtered_ids.add(fid)
                    else:
                        _diag(f"  过滤掉: fid={fid}, ds={ds}, de={de}, 不在时段 [{absence_start_min}, {absence_end_min}]")
                else:
                    # 时间数据缺失：保留航班，不过滤
                    _diag(f"  时间缺失(保留): fid={fid}, ds={ds}, de={de}")
                    filtered_ids.add(fid)
            _diag(f"时间过滤后: {len(filtered_ids)} 个 (过滤掉 {len(affected_flight_ids) - len(filtered_ids)})")
            affected_flight_ids = filtered_ids

        _diag(f"最终受影响航班: {len(affected_flight_ids)} 个, ids={affected_flight_ids}")

        crew_changes = []
        side_effects = []

        # 对每个受影响人员查找替班
        for name in affected_names:
            crew_member = crew_by_name.get(name)
            if not crew_member:
                side_effects.append({"type": "crew_not_found", "detail": f"未找到人员 {name}"})
                _diag(f"  {name}: 未找到 → crew_not_found")
                continue

            base = getattr(crew_member, 'base', '成都')
            role = getattr(crew_member, 'role', 'captain')
            _diag(f"  查替班: {name} base={base} role={role}")

            substitute = find_crew_substitute(
                absent_name=name, base=base, role=role,
                start_time=start_time, end_time=end_time,
                crew_pool=crew_pool, crew_assignments=crew_assignments
            )

            if substitute and affected_flight_ids:
                for fid in affected_flight_ids:
                    crew_changes.append({
                        "flight_id": fid,
                        "change_type": ChangeType.REASSIGN_CREW,
                        "old_value": f"{name}",
                        "new_value": f"{substitute.name}({substitute.crew_id})",
                        "reason": f"{name}({role})请假({start_time}~{end_time})，{substitute.name}替班",
                    })
                _diag(f"  {name} → 替班: {substitute.name}({substitute.crew_id})")
            elif not affected_flight_ids:
                side_effects.append({
                    "type": "no_flights",
                    "affected_crew": name,
                    "detail": f"{name}在{start_time}~{end_time}期间无航班任务",
                })
                _diag(f"  {name}: 无受影响航班 → no_flights")
            else:
                side_effects.append({
                    "type": "crew_shortage",
                    "affected_crew": name,
                    "detail": f"无可用替班替代 {name}({role})，基地{base}",
                })
                _diag(f"  {name}: 无替班 → crew_shortage")

        _diag(f"方案汇总: crew_changes={len(crew_changes)}, side_effects={len(side_effects)}")
        _diag(f"{'='*60}\n")

        # 生成影响报告
        impact = ImpactReport(
            report_id=f"rpt_{event.event_id}",
            event_id=event.event_id,
            direct_impacted_flights=list(affected_flight_ids),
            direct_impacted_crew=list(affected_names),
            cascade_chains=[],
            total_impacted_flights=len(affected_flight_ids),
            total_impacted_aircraft=0,
            total_delay_minutes=0,
            flights_to_cancel=[],
            timeline_changes={},
        )

        plan = RecoveryPlan(
            plan_id=f"plan_{event.event_id}",
            event_id=event.event_id,
            strategy="CrewSubstitutionRecovery",
            flight_changes=[],
            crew_changes=crew_changes,
            canceled_flights=[],
            coverage_rate=1.0 if crew_changes else (0.0 if affected_flight_ids else 1.0),
            total_delay_minutes=0,
            avg_delay_minutes=0.0,
            status=RecoveryPlanStatus.DRAFT,
            before_metrics={
                "affected_crew": len(affected_crew_ids),
                "affected_flights": len(affected_flight_ids),
            },
            after_metrics={
                "substituted": len(crew_changes),
                "shortage": len(side_effects),
            },
            side_effects=side_effects,
        )

        self._plans[plan.plan_id] = plan
        return impact, plan

    def confirm_plan(self, plan_id):
        plan = self._plans.get(plan_id)
        if plan:
            plan.status = RecoveryPlanStatus.CONFIRMED
        return plan

    def reject_plan(self, plan_id):
        plan = self._plans.get(plan_id)
        if plan:
            plan.status = RecoveryPlanStatus.REJECTED
        return plan

    def clear(self):
        self._plans.clear()
        self._executed_schedules.clear()

    # ===== 内部方法 =====

    @staticmethod
    def _format_flight_time(flight, attr_name):
        """格式化航班时间 tuple → 'YYYY-MM-DD HH:MM'"""
        if not flight:
            return ''
        val = getattr(flight, attr_name, None)
        if isinstance(val, (tuple, list)) and len(val) >= 5:
            try:
                return f"{int(val[0])}-{int(val[1]):02d}-{int(val[2]):02d} {int(val[3]):02d}:{int(val[4]):02d}"
            except (ValueError, TypeError):
                return ''
        return str(val) if val else ''

    @staticmethod
    def _compute_delayed_times(flight, delay_minutes):
        """计算延迟后的起飞/降落时间"""
        if not flight or delay_minutes <= 0:
            return '', ''

        dep = getattr(flight, 'time_departure', None)
        arr = getattr(flight, 'time_arrival', None)

        new_dep = RecoveryService._offset_time(dep, delay_minutes)
        new_arr = RecoveryService._offset_time(arr, delay_minutes)
        return new_dep, new_arr

    @staticmethod
    def _offset_time(time_tuple, offset_minutes):
        """时间 tuple + 偏移分钟 → 'YYYY-MM-DD HH:MM' 字符串"""
        if not time_tuple or not isinstance(time_tuple, (tuple, list)) or len(time_tuple) < 5:
            return ''
        try:
            value = datetime(*(int(part) for part in time_tuple[:5])) + timedelta(minutes=offset_minutes)
        except (ValueError, TypeError):
            return ''
        # 用真实日历处理月底和跨年，避免出现12月0日或把年份写回2020。
        return value.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _apply_delay(flight, delay_minutes):
        """直接修改 Flight 对象的 time_departure 和 time_arrival"""
        if delay_minutes <= 0:
            return
        for attr in ('time_departure', 'time_arrival'):
            val = getattr(flight, attr, None)
            if val and isinstance(val, (tuple, list)) and len(val) >= 5:
                try:
                    value = datetime(*(int(part) for part in val[:5])) + timedelta(minutes=delay_minutes)
                except (ValueError, TypeError):
                    continue
                new_val = (value.year, value.month, value.day, value.hour, value.minute)
                setattr(flight, attr, new_val)


# 全局单例
recovery_service = RecoveryService()
