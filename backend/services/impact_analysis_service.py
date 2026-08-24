"""影响分析服务 - BFS 级联传播算法

分析异常事件对排班的级联影响：从直接影响的航班出发，
沿资源依赖链（飞机/机组/登机口/跑道）逐层传播。

机场异常核心逻辑：
  - 找出起飞/降落时间落入异常窗口的航班
  - 计算每个航班需要的推迟时间
  - 推迟 >= 5 小时的航班建议取消
"""

import time

from ..models.impact_report import ImpactReport
from ..models.abnormal_event import AnomalyType

# 航班取消阈值（分钟）：推迟超过此时间则建议取消
CANCEL_DELAY_THRESHOLD = 5 * 60  # 5 小时

# 天气严重度 → 地面延误上限（分钟）。小雨只轻微减容、不长时间停场；
# 大雨/雷暴才允许长延误，从而触及 5 小时取消阈值。非天气事件不适用。
SEVERITY_MAX_DELAY_MIN = {
    1: 60,     # 小雨
    2: 180,    # 中雨
    3: 360,    # 大雨（可超取消阈值）
    4: 480,    # 雷暴
}


class ImpactAnalysisService:
    """影响分析引擎"""

    def analyze(self, event, schedule):
        """执行影响分析"""
        t0 = time.time()
        flights = schedule.get('flights', [])
        aircraft_map = schedule.get('aircraft_assignments', {})
        crew_map = schedule.get('crew_assignments', {})
        gate_map = schedule.get('gate_assignments', {})
        runway_map = schedule.get('runway_assignments', {})
        chains = schedule.get('chains', [])

        print(f"[Impact] 开始分析: flights={len(flights)}, chains={len(chains)}, "
              f"airports={event.affected_airports}, window={event.start_time}~{event.end_time}")

        # 预建索引
        t_idx0 = time.time()
        flights_sorted = sorted(flights, key=lambda f: self._flight_dep_key(f))
        t_idx1 = time.time()

        # 预建航班索引（避免 BFS 中重复遍历）
        flight_by_id = {}
        for f in flights_sorted:
            fid = self._get_flight_id(f)
            if fid:
                flight_by_id[fid] = f

        # 预建任务链后续航班索引（链内 fid → 下一个 fid + 间隔）
        chain_next_map = {}
        for chain in chains:
            fids = [self._get_flight_id(f) for f in chain]
            for i in range(len(fids) - 1):
                curr_fid = fids[i]
                next_fid = fids[i + 1]
                curr = flight_by_id.get(curr_fid)
                nxt = flight_by_id.get(next_fid)
                if curr and nxt:
                    arr = self._get_minutes(curr, 'time_arrival')
                    dep = self._get_minutes(nxt, 'time_departure')
                    if arr is not None and dep is not None:
                        chain_next_map[curr_fid] = (next_fid, dep - arr)
        t_idx2 = time.time()

        # Step 1: 找出直接影响
        direct_flights, direct_aircraft, direct_crew, direct_gates, direct_runways, \
            per_flight_delay = self._find_direct_impacts(
                event, flights_sorted, aircraft_map, crew_map, gate_map, runway_map)
        t_step1 = time.time()

        # Step 2: BFS 级联传播
        all_impacted = set()
        cascade_chain_entries = []
        timeline_changes = {}

        # 初始化 BFS 队列
        queue = []
        for fid in direct_flights:
            delay = per_flight_delay.get(fid, 0)
            queue.append((fid, delay, "direct_impact", 0))
            all_impacted.add(fid)

        queue.sort(key=lambda x: self._flight_order(x[0], flights_sorted))

        while queue:
            current_fid, current_delay, reason, level = queue.pop(0)

            if level > 0:
                cascade_chain_entries.append({
                    "flight_id": current_fid,
                    "reason": reason,
                    "delay_minutes": current_delay,
                    "level": level,
                })

            if current_fid in timeline_changes:
                timeline_changes[current_fid]["delay_minutes"] = max(
                    timeline_changes[current_fid].get("delay_minutes", 0), current_delay
                )
            else:
                timeline_changes[current_fid] = {
                    "delay_minutes": current_delay,
                    "reason": reason,
                    "level": level,
                }

            # 级联：同一飞机的后续航班（链内后续）
            if current_fid in aircraft_map:
                if current_fid in chain_next_map:
                    next_fid, gap_minutes = chain_next_map[current_fid]
                    if next_fid not in all_impacted:
                        cascaded_delay = max(0, current_delay - gap_minutes)
                        if cascaded_delay > 0:
                            all_impacted.add(next_fid)
                            queue.append((next_fid, cascaded_delay,
                                          "aircraft_cascade", level + 1))
        t_bfs = time.time()

        # 汇总
        total_delay = sum(
            tc.get("delay_minutes", 0) for tc in timeline_changes.values()
        )

        flights_to_cancel = [
            fid for fid, tc in timeline_changes.items()
            if tc.get("delay_minutes", 0) >= CANCEL_DELAY_THRESHOLD
        ]

        # 受影响飞机列表
        impacted_aircraft = set()
        for fid in all_impacted:
            if fid in aircraft_map:
                impacted_aircraft.add(aircraft_map[fid])

        report = ImpactReport(
            report_id=f"rpt_{event.event_id}",
            event_id=event.event_id,
            direct_impacted_flights=list(direct_flights),
            direct_impacted_aircraft=list(direct_aircraft),
            direct_impacted_crew=list(direct_crew),
            direct_impacted_gates=list(direct_gates),
            direct_impacted_runways=list(direct_runways),
            cascade_chains=cascade_chain_entries,
            total_impacted_flights=len(all_impacted),
            total_impacted_aircraft=len(impacted_aircraft),
            total_impacted_crew=0,
            total_impacted_gates=0,
            total_delay_minutes=total_delay,
            flights_to_cancel=flights_to_cancel,
            timeline_changes=timeline_changes,
        )

        t_end = time.time()
        print(f"[Impact] 完成: direct={len(direct_flights)}, cascade={len(cascade_chain_entries)}, "
              f"cancel={len(flights_to_cancel)}, total={len(all_impacted)} "
              f"| 耗时: sort={(t_idx1 - t_idx0)*1000:.0f}ms idx={(t_idx2 - t_idx1)*1000:.0f}ms "
              f"direct={(t_step1 - t_idx2)*1000:.0f}ms bfs={(t_bfs - t_step1)*1000:.0f}ms "
              f"total={(t_end - t0)*1000:.0f}ms")

        return report

    # ===== 直接影响分析 =====

    def _find_direct_impacts(self, event, flights, a_map, c_map, g_map, r_map):
        """找出事件直接影响的航班 + 每个航班的延迟分钟数"""
        direct_flights = set()
        direct_aircraft = set()
        direct_crew = set()
        direct_gates = set()
        direct_runways = set()
        per_flight_delay = {}

        affected_airports = set(event.affected_airports or [])
        affected_aircraft_list = set(event.affected_aircraft or [])
        affected_crew_list = set(event.affected_crew or [])
        affected_flights_list = set(event.affected_flights or [])

        start_time = event.start_time or ""
        end_time = event.end_time or ""

        # 预计算异常窗口（分钟表示）
        window_start_min = self._parse_time(start_time) if start_time else 0
        window_end_min = self._parse_time(end_time) if end_time else None

        # 天气事件：按严重度限制地面延误上限（小雨只减容不长时间停场，
        # 大雨/雷暴才允许长延误以触及取消阈值）。非天气事件保持原逻辑。
        is_weather_event = str(getattr(event, 'event_type', '')).startswith('weather')
        max_delay_min = (SEVERITY_MAX_DELAY_MIN.get(getattr(event, 'severity', 3), 360)
                         if is_weather_event else None)

        # 诊断计数器
        diag_matching_airport = 0
        diag_in_window = 0
        diag_minutes_none = 0
        diag_sample = []

        for f in flights:
            fid = self._get_flight_id(f)
            dep_ap = self._get_attr(f, 'departure_airport')
            arr_ap = self._get_attr(f, 'arrival_airport')
            dep_min = self._get_minutes(f, 'time_departure')
            arr_min = self._get_minutes(f, 'time_arrival')

            # 1) 明确指定的航班
            if fid in affected_flights_list:
                direct_flights.add(fid)
                per_flight_delay[fid] = max(
                    per_flight_delay.get(fid, 0),
                    event.delay_minutes or 0
                )

            # 2) 机场异常：起飞/降落机场在受影响列表中 + 时间重叠
            if affected_airports and window_end_min is not None:
                affected = False
                delay_minutes = 0

                # 起飞时间落在异常窗口内
                if dep_ap in affected_airports:
                    diag_matching_airport += 1
                    if dep_min is not None:
                        if window_start_min <= dep_min < window_end_min:
                            delay_minutes = window_end_min - dep_min
                            affected = True
                            diag_in_window += 1
                    else:
                        diag_minutes_none += 1

                # 降落时间落在异常窗口内
                if arr_ap in affected_airports:
                    if dep_ap not in affected_airports:
                        diag_matching_airport += 1
                    if arr_min is not None:
                        if window_start_min <= arr_min < window_end_min:
                            arr_delay = window_end_min - arr_min
                            delay_minutes = max(delay_minutes, arr_delay)
                            affected = True
                            if not affected:
                                diag_in_window += 1
                    else:
                        if dep_ap not in affected_airports:
                            diag_minutes_none += 1

                if affected:
                    if max_delay_min is not None and delay_minutes > max_delay_min:
                        delay_minutes = max_delay_min
                    direct_flights.add(fid)
                    per_flight_delay[fid] = max(
                        per_flight_delay.get(fid, 0), delay_minutes
                    )
                elif dep_ap in affected_airports and len(diag_sample) < 5:
                    diag_sample.append({
                        "fid": fid, "dep_ap": dep_ap, "arr_ap": arr_ap,
                        "dep_min": dep_min, "arr_min": arr_min,
                        "window": f"{window_start_min}~{window_end_min}",
                        "reason": "time_not_in_window" if dep_min is not None else "minutes_none"
                    })

            # 3) 飞机异常
            if fid in a_map and a_map[fid] in affected_aircraft_list:
                direct_flights.add(fid)
                direct_aircraft.add(a_map[fid])

            # 4) 机组异常
            if fid in c_map:
                assigned = set(c_map[fid])
                if assigned.intersection(affected_crew_list):
                    direct_flights.add(fid)
                    direct_crew.update(assigned.intersection(affected_crew_list))

        if affected_airports:
            print(f"[Impact] 诊断: 匹配机场航班={diag_matching_airport}, "
                  f"时间在窗口内={diag_in_window}, "
                  f"时间元组为空={diag_minutes_none}, "
                  f"窗口={window_start_min}~{window_end_min}")
            if diag_sample:
                print(f"[Impact] 诊断样本(未命中): {diag_sample[:3]}")

        return (direct_flights, direct_aircraft, direct_crew,
                direct_gates, direct_runways, per_flight_delay)

    # ===== 时间工具 =====

    @staticmethod
    def _get_minutes(f, attr_name):
        """从 Flight 对象获取时间（以月初起分钟数表示）
        支持 tuple/list 和 'YYYY-MM-DD HH:MM' 字符串两种格式"""
        val = getattr(f, attr_name, None) if not isinstance(f, dict) else f.get(attr_name)
        # tuple/list 格式: (2020, 11, 30, 6, 0)
        if isinstance(val, (tuple, list)) and len(val) >= 5:
            try:
                return ((int(val[1]) - 11) * 30 + int(val[2])) * 24 * 60 + int(val[3]) * 60 + int(val[4])
            except (ValueError, TypeError):
                pass
        # 字符串格式: "2020-11-30 06:00"
        if isinstance(val, str) and val.strip():
            try:
                parts = val.strip().split(' ')
                date_part = parts[0]
                time_part = parts[1] if len(parts) > 1 else '00:00'
                y, m, d = map(int, date_part.split('-'))
                h, mi = map(int, time_part.split(':'))
                return ((m - 11) * 30 + d) * 24 * 60 + h * 60 + mi
            except (ValueError, IndexError):
                pass
        return None

    def _time_window_delay(self, flight_time_str, window_start_str, window_end_str):
        """计算航班时间落在异常窗口内需要的推迟分钟数。
        如果航班时间在窗口之前，返回 0（不受影响）。
        如果航班时间在窗口内，返回 窗口结束 - 航班时间。
        如果航班时间在窗口之后，返回 None（不受影响）。
        """
        if not flight_time_str or not window_end_str:
            return None
        try:
            ft = self._parse_time(flight_time_str)
            ws = self._parse_time(window_start_str) if window_start_str else 0
            we = self._parse_time(window_end_str)
            if ft is None or we is None:
                return None
            if ft < ws:
                return 0  # 在窗口之前，不受影响
            if ft < we:
                return we - ft  # 在窗口内，需推迟到窗口结束
            return None  # 在窗口之后，不受影响
        except Exception:
            return None

    @staticmethod
    def _parse_time(time_str):
        """解析 'YYYY-MM-DD HH:MM' 格式为从月初起的分钟数"""
        if not time_str:
            return None
        try:
            # 支持 "2020-11-30 06:00" 格式
            parts = time_str.strip().split(' ')
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else '00:00'
            y, m, d = map(int, date_part.split('-'))
            h, mi = map(int, time_part.split(':'))
            # 返回从 (2020, 11, 1) 00:00 起的分钟数
            return ((m - 11) * 30 + d) * 24 * 60 + h * 60 + mi
        except Exception:
            return None

    # ===== Flight 对象属性访问 =====

    @staticmethod
    def _get_flight_id(f):
        """获取航班 ID，兼容对象和字典"""
        if isinstance(f, dict):
            return f.get('flight_id', '') or f.get('id', '')
        return getattr(f, 'flight_id', '') or str(getattr(f, 'id', ''))

    @staticmethod
    def _get_attr(f, name):
        """安全获取属性"""
        if isinstance(f, dict):
            return f.get(name, '')
        return getattr(f, name, '')

    @staticmethod
    def _get_time_str(f, attr_name):
        """获取航班时间（格式化为 'YYYY-MM-DD HH:MM' 字符串）"""
        if isinstance(f, dict):
            val = f.get(attr_name, '')
        else:
            val = getattr(f, attr_name, '')

        if isinstance(val, (tuple, list)) and len(val) >= 5:
            return f"{val[0]}-{val[1]:02d}-{val[2]:02d} {val[3]:02d}:{val[4]:02d}"
        if isinstance(val, str) and val:
            return val
        return ''

    @staticmethod
    def _flight_dep_key(f):
        """航班排序键"""
        td = getattr(f, 'time_departure', None)
        if td and isinstance(td, (tuple, list)) and len(td) >= 5:
            return ImpactAnalysisService._time_tuple_to_str(td)
        if isinstance(f, dict):
            return f.get('time_departure', '9999')
        return getattr(f, 'time_departure', '9999') or '9999'

    @staticmethod
    def _time_tuple_to_str(t):
        return f"{t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}"

    def _flight_order(self, fid, flights):
        """返回航班排序索引"""
        for i, f in enumerate(flights):
            if self._get_flight_id(f) == fid:
                return i
        return 99999


# 全局单例
impact_analysis_service = ImpactAnalysisService()
