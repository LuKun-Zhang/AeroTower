"""旅客流调度组装（纯函数）。

从 ``generate_routes.py`` 抽出的组装逻辑：输入航班与排班结果，输出
``/api/paxflow/schedule`` 所需的按天结构，不读写任何全局状态。
路由与实验流水线共用这一份实现，避免复制 180 行。
"""

import re

from ..aircraft_types import layout_seats
from .seed import stable_hash

# 成都双流机场俯视图矩形 → 跑道分组（与前端 TAXI_CHANNELS 对齐）
PAXFLOW_RUNWAY1_RECTS = list(range(16, 72))            # 16~71 → 跑道一
PAXFLOW_RUNWAY2_RECTS = list(range(72, 87)) + [92]     # 72~86, 92 → 跑道二
PAXFLOW_LOAD_FACTOR = 0.78                             # 载客率


def rect_for_gate(gate_name):
    """后端登机口“辰Gxx” → 前端布局“矩形 xx”编号。"""
    m = re.match(r'辰G(\d+)', str(gate_name))
    if not m:
        return None
    num = int(m.group(1))
    if 1 <= num <= 37:
        return PAXFLOW_RUNWAY1_RECTS[(num - 1) % len(PAXFLOW_RUNWAY1_RECTS)]
    return PAXFLOW_RUNWAY2_RECTS[(num - 38) % len(PAXFLOW_RUNWAY2_RECTS)]


def terminal_for_rect(rect_num):
    """矩形编号 → 航站楼（16~43=T1，44 起=T2）。"""
    return 'T1' if rect_num <= 43 else 'T2'


def flight_date(f, airport='成都'):
    """航班在目标机场的操作日期（到达用到达日期，出发用出发日期）。"""
    if f.arrival_airport == airport:
        y, m, d, *_ = f.time_arrival
    else:
        y, m, d, *_ = f.time_departure
    return f"{y}-{m:02d}-{d:02d}"


def fallback_tail_no(flight_id):
    """飞机尾号兜底：由 flight_id 派生唯一编号，避免前端机队合并冲突。"""
    try:
        return 'B-' + str(int(str(flight_id).replace('gen_', ''))).zfill(5)
    except Exception:
        return 'B-' + str(stable_hash(str(flight_id), 100000)).zfill(5)


def apply_disruption_to_entry(entry, plan_item):
    """把冻结的中断计划应用到单个旅客流 entry。"""
    if not plan_item:
        return
    entry['disruptionType'] = plan_item.get('type')
    entry['reason'] = plan_item.get('reason', '天气影响')

    if plan_item.get('type') == 'cancel':
        entry['cancelled'] = True
        return

    delay = int(plan_item.get('delay_minutes', 0) or 0)
    entry['delayMinutes'] = delay
    if delay <= 0:
        return
    for key in ('boardingStart', 'boardingEnd', 'takeoffTime',
                'scheduledArr', 'rwStart', 'rwEnd'):
        if key in entry and entry[key] is not None:
            entry[key] += delay


def _build_runway_windows(runway_schedule):
    """跑道条目 → flight_id 的跑道号与占用窗口（当天分钟）。"""
    runway_map = {}
    rw_window = {}
    for item in runway_schedule or []:
        fid = item.get('flight_id')
        if not fid or fid in runway_map:
            continue
        runway_map[fid] = item.get('runway', 1)
        rw_window[fid] = {
            'start': item.get('actual_time', 0) % 1440,
            'end': item.get('end_time', 0) % 1440,
        }
    return runway_map, rw_window


def build_paxflow_schedule(flights, airport='成都', runway_schedule=None,
                           gate_map=None, tail_map=None, plan=None,
                           load_factor=PAXFLOW_LOAD_FACTOR, dates_filter=None):
    """组装旅客流按天调度。

    :param dates_filter: 仅保留这些日期（实验用；None 表示不过滤）
    """
    gate_map = gate_map or {}
    tail_map = tail_map or {}
    plan = plan or {}
    runway_map, rw_window = _build_runway_windows(runway_schedule)

    ap_flights = [
        f for f in flights
        if f.departure_airport == airport or f.arrival_airport == airport
    ]
    if dates_filter:
        allowed = set(dates_filter)
        ap_flights = [f for f in ap_flights if flight_date(f, airport) in allowed]
    if not ap_flights:
        return {'airport': airport, 'dates': [], 'schedule': {}, 'flights': []}

    dates = sorted({flight_date(f, airport) for f in ap_flights})
    schedule_by_date = {}

    for date_str in dates:
        items = []
        for f in ap_flights:
            if flight_date(f, airport) != date_str:
                continue
            gm = gate_map.get(f.flight_id, {})
            backend_gate = gm.get('gate') or '辰G01'
            rect_num = rect_for_gate(backend_gate)
            if rect_num is None:
                rect_num = 16
            gate_name = f"矩形 {rect_num}"
            runway_no = runway_map.get(f.flight_id, gm.get('runway_group', 1))
            runway = '跑道一' if runway_no == 1 else '跑道二'
            seats = layout_seats(f.layout) or 150
            pax_total = max(1, round(seats * load_factor))
            rw = rw_window.get(f.flight_id, {})

            if f.departure_airport == airport:
                dep_min = f.departure_minutes % 1440
                entry = {
                    'flightId': str(f.flight_id),
                    'flightNo': f.flight_no,
                    'tailNo': tail_map.get(f.flight_id) or fallback_tail_no(f.flight_id),
                    'type': 'departure',
                    'gateName': gate_name,
                    'backendGate': backend_gate,
                    'terminal': terminal_for_rect(rect_num),
                    'boardingStart': dep_min - 35,
                    'boardingEnd': dep_min - 5,
                    'takeoffTime': dep_min,
                    'rwStart': rw.get('start', dep_min - 3),
                    'rwEnd': rw.get('end', dep_min + 2),
                    'runway': runway,
                    'paxTotal': pax_total,
                    'origin': airport,
                    'dest': f.arrival_airport,
                    'nextFlightNo': None,
                }
            else:
                arr_min = f.arrival_minutes % 1440
                entry = {
                    'flightId': str(f.flight_id),
                    'flightNo': f.flight_no,
                    'tailNo': tail_map.get(f.flight_id) or fallback_tail_no(f.flight_id),
                    'type': 'arrival',
                    'gateName': gate_name,
                    'backendGate': backend_gate,
                    'terminal': terminal_for_rect(rect_num),
                    'scheduledArr': arr_min,
                    'rwStart': rw.get('start', arr_min - 2),
                    'rwEnd': rw.get('end', arr_min + 3),
                    'runway': runway,
                    'paxTotal': pax_total,
                    'origin': f.departure_airport,
                    'dest': airport,
                    'nextFlightNo': None,
                }

            apply_disruption_to_entry(entry, plan.get(str(f.flight_id)))
            items.append(entry)

        items.sort(key=lambda e: (
            e.get('takeoffTime') if e.get('type') == 'departure'
            else e.get('scheduledArr', 0)
        ))
        schedule_by_date[date_str] = items

    return {
        'airport': airport,
        'dates': dates,
        'schedule': schedule_by_date,
        'flights': ap_flights,
    }
