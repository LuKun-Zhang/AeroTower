"""调度方案存储 - 内存存储排班/跑道调度结果，供地图视图查询"""
import math
from datetime import datetime

# 全局存储：key=date(YYYY-MM-DD), value=schedule dict
_schedule_store = {}

# ICAO代码 -> 中文城市名（补充 Excel 机场表中未映射的机场）
ICAO_TO_CITY = {
    'ZBAA': '北京', 'ZBHH': '呼和浩特', 'ZBTJ': '天津', 'ZGSZ': '深圳',
    'ZHHH': '武汉', 'ZLLL': '兰州', 'ZLIC': '银川', 'ZLXN': '西宁',
    'ZLXY': '西安', 'ZJQH': '琼海', 'ZJSY': '三亚', 'ZGSD': '珠海',
    'ZGNN': '南宁', 'ZGBH': '北海', 'ZGOW': '揭阳', 'ZHSN': '神农架',
    'ZBDS': '鄂尔多斯', 'ZBHD': '邯郸', 'ZBLL': '吕梁', 'ZPSM': '普洱',
    'ZUMY': '绵阳', 'ZUGZ': '广元', 'ZUZH': '攀枝花', 'ZUJZ': '九寨沟',
    'ZUNC': '南充', 'ZUTF': '成都天府', 'ZUUU': '成都', 'ZUXC': '西昌',
    'ZUYI': '宜宾', 'ZWCM': '且末', 'ZYHB': '哈尔滨', 'ZYJM': '佳木斯',
    'ZYJZ': '锦州', 'ZYTX': '铁岭', 'ZSCN': '南昌', 'ZUXC': '西昌',
    'ZSQD': '青岛', 'ZLXH': '夏河',
}

def save_schedule(date, routing_aircrafts, runway_items):
    """保存某天的排班和跑道调度"""
    _schedule_store[date] = {
        'routing_aircrafts': routing_aircrafts,
        'runway_items': runway_items,
    }
    print(f"[MapStore] 保存 {date}: {len(routing_aircrafts)}架飞机排班, {len(runway_items)}条跑道记录")

def get_schedule(date):
    """获取某天的调度"""
    return _schedule_store.get(date, None)

def get_all_dates():
    """获取已保存的所有日期"""
    return sorted(_schedule_store.keys())

def _flight_date(f):
    """从 Flight 对象提取日期字符串 YYYY-MM-DD"""
    td = f.time_departure
    try:
        y, m, d = int(td[0]), int(td[1]), int(td[2])
        return f"{y}-{m:02d}-{d:02d}"
    except (ValueError, TypeError, IndexError):
        return "2020-11-30"

def _minutes_of_day(h, mi):
    """返回一天内的分钟数 0~1439"""
    return h * 60 + mi

def build_map_timeslices(date_str, flights):
    """
    生成一天48个时间切片（每30分钟）。每切片包含该时刻在空中的航班，
    每条记录含 {from, to, progress, flight_no}，progress 0~1 表示
    航班已完成百分比，前端据此在航线上精确摆放飞机图标。
    """
    day_flights = [f for f in flights if _flight_date(f) == date_str]
    if not day_flights:
        return []

    parsed = []
    for f in day_flights:
        _, _, _, h_dep, mi_dep = f.time_departure
        _, _, _, h_arr, mi_arr = f.time_arrival

        dep_min = _minutes_of_day(h_dep, mi_dep)
        arr_min = _minutes_of_day(h_arr, mi_arr)

        dep_name = ICAO_TO_CITY.get(f.departure_airport, f.departure_airport)
        arr_name = ICAO_TO_CITY.get(f.arrival_airport, f.arrival_airport)

        if dep_name and arr_name and dep_min < arr_min and dep_name != arr_name:
            parsed.append({
                'from': dep_name, 'to': arr_name,
                'dep_min': dep_min, 'arr_min': arr_min,
                'flight_no': f.flight_no,
            })

    if not parsed:
        return []

    slice_min = 15
    num_slices = 96  # 15 * 96 = 1440 = 24小时

    result = []
    for s in range(num_slices):
        slice_start = s * slice_min
        slice_end = slice_start + slice_min
        slice_mid = (slice_start + slice_end) / 2.0

        flights_in_slice = []
        for p in parsed:
            dep = p['dep_min']
            arr = p['arr_min']
            if dep >= slice_end or arr <= slice_start:
                continue

            # 进度 = 当前切片中点位于整个飞行中的百分比
            progress = (slice_mid - dep) / (arr - dep)
            progress = max(0.0, min(1.0, progress))

            flights_in_slice.append({
                'from': p['from'],
                'to': p['to'],
                'value': 5,
                'progress': round(progress, 3),
                'flight_no': p['flight_no'],
            })

        result.append(flights_in_slice)

    return result


def build_multi_day_timeslices(flights):
    """
    生成多天的时间切片（每15分钟一个），使用绝对时间轴，自然处理过夜航班。
    返回全部日期的切片列表，可直接被前端按索引访问。

    每条记录含 {from, to, progress, flight_no}，progress 0~1 表示
    航班已完成百分比，前端据此在航线上精确摆放飞机图标。
    """
    if not flights:
        return []

    # 收集所有唯一日期，按出发日期分组
    all_dates_set = set()
    for f in flights:
        all_dates_set.add(_flight_date(f))
    sorted_dates = sorted(all_dates_set)
    if not sorted_dates:
        return []

    # 基准时间：第一天 00:00
    start_dt = datetime.strptime(sorted_dates[0], '%Y-%m-%d')

    # 将所有航班转为绝对分钟数（相对于 start_dt）
    parsed = []
    for f in flights:
        y, m, d, h_dep, mi_dep = f.time_departure
        y2, m2, d2, h_arr, mi_arr = f.time_arrival

        dep_dt = datetime(y, m, d, h_dep, mi_dep)
        arr_dt = datetime(y2, m2, d2, h_arr, mi_arr)

        dep_abs = int((dep_dt - start_dt).total_seconds() / 60)
        arr_abs = int((arr_dt - start_dt).total_seconds() / 60)

        # 保证到达 > 出发（跨天航班 arr_abs 已通过日期正确计算）
        if arr_abs <= dep_abs:
            continue  # 跳过无效数据

        dep_name = ICAO_TO_CITY.get(f.departure_airport, f.departure_airport)
        arr_name = ICAO_TO_CITY.get(f.arrival_airport, f.arrival_airport)

        if not dep_name or not arr_name or dep_name == arr_name:
            continue

        parsed.append({
            'from': dep_name, 'to': arr_name,
            'dep_min': dep_abs, 'arr_min': arr_abs,
            'flight_no': f.flight_no,
        })

    if not parsed:
        return []

    # 每15分钟一个切片，覆盖所有天数
    num_days = len(sorted_dates)
    total_slices = num_days * 96  # 96 = 24小时 * 4

    slice_min = 15
    result = []
    for s in range(total_slices):
        slice_start = s * slice_min
        slice_end = slice_start + slice_min
        slice_mid = (slice_start + slice_end) / 2.0

        flights_in_slice = []
        for p in parsed:
            if p['dep_min'] >= slice_end or p['arr_min'] <= slice_start:
                continue

            progress = (slice_mid - p['dep_min']) / (p['arr_min'] - p['dep_min'])
            progress = max(0.0, min(1.0, progress))

            flights_in_slice.append({
                'from': p['from'],
                'to': p['to'],
                'value': 5,
                'progress': round(progress, 3),
                'flight_no': p['flight_no'],
            })

        result.append(flights_in_slice)

    return result
