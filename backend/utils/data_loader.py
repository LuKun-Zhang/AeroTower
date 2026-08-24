"""数据加载工具 - 读取 Excel / JSON 数据源"""
import json
import os

# 添加 xlrd 支持（可能未安装）
try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False


def load_big_graph_json(filepath):
    """加载 big_graph JSON 文件，返回航班节点和边"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('nodes', {}), data.get('edges', {})


def parse_time(time_str):
    """解析时间字符串 '2020, 11, 30, 6, 0' -> (year, month, day, hour, minute)"""
    parts = [int(x.strip()) for x in time_str.split(',')]
    return tuple(parts)


def load_airport_excel(filepath):
    """读取机场表 Excel，返回 {ICAO代码: 中文名} 映射"""
    airport_map = {}
    if not HAS_XLRD:
        return _get_default_airport_map()

    try:
        workbook = xlrd.open_workbook(filepath)
        sheet = workbook.sheet_by_index(0)
        for i in range(sheet.nrows):
            if i == 0:
                continue
            code = str(sheet.cell(i, 0).value).strip()
            name = str(sheet.cell(i, 3).value).strip() if sheet.ncols > 3 else code
            if code and name:
                airport_map[code] = name
    except Exception as e:
        print(f"[WARN] 读取机场表失败: {e}，使用默认映射")
        airport_map = _get_default_airport_map()

    return airport_map


def _get_default_airport_map():
    """硬编码默认机场映射（当 Excel 不可用时）。

    覆盖数据中全部 62 个 ICAO 机场代码。
    """
    return {
        # 华北
        'ZBAA': '北京', 'ZBTJ': '天津', 'ZBHH': '呼和浩特',
        'ZBDS': '鄂尔多斯', 'ZBHD': '邯郸', 'ZBLL': '吕梁',
        # 东北
        'ZYTL': '大连', 'ZYCC': '长春', 'ZYTX': '铁岭', 'ZYAS': '鞍山',
        # 华东
        'ZSSS': '上海', 'ZSPD': '浦东', 'ZSNB': '宁波', 'ZSWZ': '温州',
        'ZSJN': '济南', 'ZSQD': '青岛', 'ZSYT': '烟台',
        'ZSNT': '南通', 'ZSCG': '常州', 'ZSXZ': '徐州', 'ZSOF': '合肥',
        'ZSFY': '阜阳', 'ZSHC': '杭州', 'ZSAM': '厦门',
        'ZSCN': '南昌', 'ZSSR': '上饶', 'ZSZS': '舟山',
        # 中南
        'ZGGG': '广州', 'ZGSZ': '深圳', 'ZGSD': '珠海',
        'ZGNN': '南宁', 'ZGBH': '北海', 'ZGOW': '揭阳',
        'ZHHH': '武汉', 'ZHSN': '神农架',
        'ZJQH': '琼海', 'ZJSY': '三亚',
        # 西南
        'ZUUU': '成都', 'ZUCK': '重庆', 'ZUTF': '成都天府',
        'ZULS': '拉萨', 'ZUNZ': '林芝', 'ZUXC': '西昌',
        'ZPPP': '昆明', 'ZPMS': '芒市', 'ZPLJ': '丽江', 'ZPJH': '西双版纳',
        'ZUKD': '康定', 'ZUDC': '稻城', 'ZUJZ': '九寨沟',
        'ZUGZ': '广元', 'ZUMY': '绵阳', 'ZUNC': '南充',
        'ZUYI': '宜宾', 'ZUYB': '宜宾', 'ZULZ': '泸州',
        'ZUZH': '攀枝花', 'ZPSM': '普洱', 'ZPWS': '文山',
        # 西北
        'ZLXY': '西安', 'ZLLL': '兰州', 'ZLXN': '西宁', 'ZLIC': '银川',
        'ZLXH': '夏河', 'ZLZW': '中卫',
        # 新疆
        'ZWWW': '乌鲁木齐', 'ZWAK': '阿克苏', 'ZWTN': '和田',
        'ZWCM': '且末', 'ZWSH': '喀什',
    }


def load_flight_dicts(filepath, airport_map):
    """从 big_graph JSON 加载航班字典列表（不创建 Flight 对象，避免循环导入）"""
    nodes, _ = load_big_graph_json(filepath)
    flights = []

    for node_id, node in nodes.items():
        dep_airport = airport_map.get(
            node.get('DEPARTURE_AIRPORT', ''),
            node.get('DEPARTURE_AIRPORT', '')
        )
        arr_airport = airport_map.get(
            node.get('ARRIVAL_AIRPORT', ''),
            node.get('ARRIVAL_AIRPORT', '')
        )

        flights.append({
            'flight_id': node.get('FLIGHT_ID', int(node_id)),
            'flight_no': node.get('FLIGHT_NO', ''),
            'ac_type': node.get('AC_TYPE', ''),
            'layout': node.get('LAYOUT', ''),
            'departure_airport': dep_airport,
            'arrival_airport': arr_airport,
            'time_departure': parse_time(node.get('TIME_DEPARTURE', '2020,11,30,0,0')),
            'time_arrival': parse_time(node.get('TIME_ARRIVAL', '2020,11,30,0,0')),
            'timespan': node.get('TIMESPAN', 0),
            'cost': node.get('COST', 0),
        })

    # 按 departure_minutes 稳定排序，确保每次运行结果一致
    flights.sort(key=lambda f: _departure_minutes(f['time_departure']))
    return flights


def _departure_minutes(t):
    """计算从月初起的分钟数"""
    _, month, day, hour, minute = t
    return (month - 11) * 30 * 24 * 60 + day * 24 * 60 + hour * 60 + minute


def load_schedule_paths(filepath):
    """加载已有的排班路径（output.json）"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
