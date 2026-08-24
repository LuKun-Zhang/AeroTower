"""天气中断桥接服务

把「前端天气页回传的各省天气 + 气旋推演时间线」装配成已有的异常调度算法输入，
复用 city_geo（受影响航班判定）和 impact_analysis_service（GDP 延迟 + BFS 级联 + 5h 取消），
产出三页共享的中断计划 disruption_plan。

本文件只做「气象源 → AbnormalEvent → analyze → plan」的桥接装配，不重写调度逻辑。
"""

import time

from ..models.abnormal_event import AbnormalEvent, AnomalyType
from ..services.impact_analysis_service import impact_analysis_service
from ..utils import city_geo


# 前端 6 类天气 → 容量比 / 严重度 / 是否触发中断
FRONT_WEATHER_MAP = {
    'sunny':          {'capacity': 1.0, 'severity': 0, 'disrupted': False},
    'cloudy':         {'capacity': 0.9, 'severity': 0, 'disrupted': False},
    'rain_light':     {'capacity': 0.8, 'severity': 1, 'disrupted': True},
    'rain_moderate':  {'capacity': 0.7, 'severity': 2, 'disrupted': True},
    'rain_heavy':     {'capacity': 0.5, 'severity': 3, 'disrupted': True},
    'thunderstorm':   {'capacity': 0.4, 'severity': 4, 'disrupted': True},
}

# 稳态天气（无气旋推演时间线）时按严重度兜底的持续分钟数
SEVERITY_WINDOW_MIN = {1: 90, 2: 150, 3: 210, 4: 150}


def _is_disrupted(weather_type):
    return FRONT_WEATHER_MAP.get(weather_type, {}).get('disrupted', False)


def _severity(weather_type):
    return FRONT_WEATHER_MAP.get(weather_type, {}).get('severity', 0)


def _capacity(weather_type):
    return FRONT_WEATHER_MAP.get(weather_type, {}).get('capacity', 1.0)


# 前端天气类型 → 中文名称（用于拼出可读的调整原因）
WEATHER_CN = {
    'sunny': '晴',
    'cloudy': '多云',
    'rain_light': '小雨',
    'rain_moderate': '中雨',
    'rain_heavy': '大雨',
    'thunderstorm': '雷暴',
}


def _weather_cn(weather_type):
    return WEATHER_CN.get(weather_type, weather_type or '恶劣天气')


def _build_flight_reason(f, is_cancel, bad_provinces, province_weather, transit_cache):
    """为单个航班拼出可读的天气调整原因，如「因西藏大雨导致机场起降受限，航班延误」。

    优先取起降省份（直接受影响），其次取航线途经省份（绕飞）。
    返回空字符串表示无法定位到具体省份（纯级联航班），由调用方兜底。
    """
    dep_prov = city_geo.get_city_province(getattr(f, 'departure_airport', ''))
    arr_prov = city_geo.get_city_province(getattr(f, 'arrival_airport', ''))

    direct = []
    for prov in (dep_prov, arr_prov):
        if prov and prov in bad_provinces and prov not in direct:
            direct.append(prov)

    if direct:
        desc = '、'.join(
            f"{p}{_weather_cn(province_weather.get(p, ''))}" for p in direct
        )
        if is_cancel:
            return f"因{desc}导致机场起降受限，航班取消"
        return f"因{desc}导致机场起降受限，航班延误"

    route = transit_cache.get(
        (getattr(f, 'departure_airport', ''), getattr(f, 'arrival_airport', '')),
        set(),
    ) or set()
    transits = [p for p in sorted(route) if p in bad_provinces]
    if transits:
        desc = '、'.join(
            f"{p}{_weather_cn(province_weather.get(p, ''))}" for p in transits
        )
        return f"航线途经{desc}，绕飞延误"

    return ""


def _extract_windows(timeline, bad_provinces):
    """从气旋推演时间线提取每省连续坏天气窗口。

    timeline 形如 {省: [{t, type, time}, ...]}，其中 time 为绝对业务时刻
    "YYYY-MM-DD HH:MM"。返回 {省: [(start, end), ...]}。
    """
    windows = {}
    for prov in bad_provinces:
        series = timeline.get(prov) or []
        if not series:
            continue
        try:
            series = sorted(series, key=lambda p: p.get('t', 0))
        except Exception:
            pass

        seg_start = None
        seg_end = None
        segs = []
        for pt in series:
            wtype = pt.get('type', '')
            ts = pt.get('time') or ''
            if _is_disrupted(wtype):
                if seg_start is None:
                    seg_start = ts
                seg_end = ts
            else:
                if seg_start is not None:
                    segs.append((seg_start, seg_end or seg_start))
                    seg_start = None
                    seg_end = None
        if seg_start is not None:
            segs.append((seg_start, seg_end or seg_start))
        if segs:
            windows[prov] = segs
    return windows


def _merge_windows(windows):
    """多省取最早开始 / 最晚结束，作为单个异常事件的统一时间窗口。"""
    starts, ends = [], []
    for segs in windows.values():
        for s, e in segs:
            if s:
                starts.append(s)
            if e:
                ends.append(e)
    if not starts or not ends:
        return '', ''
    return min(starts), max(ends)


def _add_minutes_to_time(time_str, minutes):
    """业务时刻字符串加 N 分钟，用于稳态天气兜底窗口。"""
    try:
        from datetime import datetime, timedelta
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        return (dt + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return time_str


def compute_disruption(province_weather, timeline, flights,
                       aircraft_map=None, chains=None, transit_cache=None,
                       clock=None):
    """核心桥接：省份天气 → 中断计划。

    返回 (plan, meta)：
      plan: {flight_id: {type: 'cancel'|'delay', delay_minutes, reason, affected_by}}
      meta: {affected_provinces, affected_airports, direct_count, transit_count,
             delay_count, cancel_count, plan_size, window}
    """
    province_weather = province_weather or {}
    timeline = timeline or {}
    flights = list(flights or [])
    aircraft_map = aircraft_map or {}
    chains = chains or []
    transit_cache = transit_cache or {}

    # 坏省份判定：优先用确定性推演时间线的「当前时刻(t=0)」，避免随机对流细胞
    # 让航班调整面板随机闪动（随机对流仅作视觉，不参与航班调度）。
    # 无推演时间线（手动/稳态模式）时回退用当前天气快照。
    if timeline:
        bad_provinces = set()
        effective_weather = {}
        for p, series in timeline.items():
            if not series:
                continue
            first = min(series, key=lambda pt: pt.get('t', 0))
            if _is_disrupted(first.get('type', '')):
                bad_provinces.add(p)
                effective_weather[p] = first.get('type', '')
    else:
        bad_provinces = {p for p, t in province_weather.items() if _is_disrupted(t)}
        effective_weather = {p: province_weather[p] for p in bad_provinces}

    if not bad_provinces or not flights:
        return {}, {
            'affected_provinces': [],
            'affected_airports': [],
            'direct_count': 0,
            'transit_count': 0,
            'delay_count': 0,
            'cancel_count': 0,
            'plan_size': 0,
            'window': None,
        }

    # 1) 坏省份 → 机场列表（复用）
    airports = city_geo.get_province_airports(bad_provinces)

    # 2) 受影响航班（direct/transit，复用）
    if not transit_cache:
        try:
            transit_cache = city_geo.build_transit_cache_from_flights(flights)
        except Exception:
            transit_cache = {}
    affected = city_geo.get_affected_flights_by_province(
        flights, bad_provinces, transit_cache,
    )
    direct_ids = {str(fid) for fid in affected.get('direct', set())}
    transit_ids = {str(fid) for fid in affected.get('transit', set())}

    # 3) 影响时间窗口：气旋推演 timeline 提取；无则按 severity 兜底
    windows = _extract_windows(timeline, bad_provinces)
    start_str, end_str = _merge_windows(windows)
    if not start_str or not end_str:
        max_severity = max((_severity(effective_weather.get(p, '')) for p in bad_provinces),
                           default=1)
        dur = SEVERITY_WINDOW_MIN.get(max_severity, 150)
        # clock 可能来自前端 getBusinessClock() 的对象 {current_time, anchor, ...}，
        # 这里统一取其中的业务时刻字符串，避免把 dict 当作时间导致窗口解析失败。
        base = clock or '2020-11-29 00:00'
        if isinstance(base, dict):
            base = base.get('current_time') or base.get('anchor') or '2020-11-29 00:00'
        start_str = base
        end_str = _add_minutes_to_time(base, dur)

    # 4) 复用：构造 AbnormalEvent + schedule，调用 impact_analysis_service
    max_severity = max((_severity(effective_weather.get(p, '')) for p in bad_provinces),
                       default=1)
    min_capacity = min((_capacity(effective_weather.get(p, '')) for p in bad_provinces),
                       default=0.5)

    event = AbnormalEvent(
        event_id=f"weather_{int(time.time() * 1000)}",
        event_type=AnomalyType.WEATHER_CAPACITY,
        title=f"省份天气中断: {'、'.join(sorted(bad_provinces))}",
        description="气旋推演自动生成",
        affected_airports=airports,
        start_time=start_str,
        end_time=end_str,
        capacity_ratio=min_capacity,
        severity=max_severity,
    )

    schedule = {
        'flights': flights,
        'aircraft_assignments': aircraft_map,
        'crew_assignments': {},
        'gate_assignments': {},
        'runway_assignments': {},
        'chains': chains,
    }

    report = impact_analysis_service.analyze(event, schedule)
    cancel_set = {str(fid) for fid in report.flights_to_cancel}

    # 5) 汇总为统一中断计划（reason 带具体省份 + 天气类型，便于前端展示调整原因）
    flight_by_id = {str(getattr(f, 'flight_id', '')): f for f in flights}

    def _reason_for(fid, is_cancel):
        f = flight_by_id.get(str(fid))
        if f is not None:
            r = _build_flight_reason(f, is_cancel, bad_provinces,
                                     effective_weather, transit_cache)
            if r:
                return r
        desc = '、'.join(sorted(bad_provinces))
        if is_cancel:
            return f"因{desc}天气影响，航班取消"
        return f"因{desc}天气影响，航班延误"

    plan = {}
    for fid, tc in (report.timeline_changes or {}).items():
        fid = str(fid)
        is_cancel = fid in cancel_set
        plan[fid] = {
            'type': 'cancel' if is_cancel else 'delay',
            'delay_minutes': int(tc.get('delay_minutes', 0)),
            'reason': _reason_for(fid, is_cancel),
            'affected_by': 'direct' if fid in direct_ids else 'cascade',
        }

    transit_delay = 30 + 10 * max(1, max_severity)
    for fid in transit_ids:
        if fid in plan:
            continue
        plan[fid] = {
            'type': 'delay',
            'delay_minutes': transit_delay,
            'reason': _reason_for(fid, False),
            'affected_by': 'transit',
        }

    # 6) 时间窗口过滤：只保留「起飞时间」落在坏天气持续窗口 [start_str, end_str]
    #    内的航班，避免今天下雨通过级联/直连影响明天及以后的航班。
    try:
        from datetime import datetime
        start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
        end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M')
    except Exception:
        start_dt = end_dt = None

    if start_dt is not None and end_dt is not None:
        def _flight_departure_dt(f):
            td = getattr(f, 'time_departure', None)
            if isinstance(td, (tuple, list)) and len(td) >= 5:
                try:
                    return datetime(int(td[0]), int(td[1]), int(td[2]),
                                    int(td[3]), int(td[4]))
                except Exception:
                    return None
            return None

        dep_map = {}
        for f in flights:
            fid = str(getattr(f, 'flight_id', ''))
            if fid:
                dep_map[fid] = _flight_departure_dt(f)
        plan = {
            fid: d for fid, d in plan.items()
            if dep_map.get(fid) is not None
            and start_dt <= dep_map[fid] <= end_dt
        }

    delay_count = sum(1 for v in plan.values() if v['type'] == 'delay')
    cancel_count = sum(1 for v in plan.values() if v['type'] == 'cancel')

    meta = {
        'affected_provinces': sorted(bad_provinces),
        'affected_airports': airports,
        'direct_count': len(direct_ids),
        'transit_count': len(transit_ids),
        'delay_count': delay_count,
        'cancel_count': cancel_count,
        'plan_size': len(plan),
        'window': {'start': start_str, 'end': end_str},
    }
    return plan, meta
