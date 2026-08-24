"""航班管理 API 路由 — 所有响应统一 {code: 0, data/msg} 格式"""

import io
import os
import copy
import json
import re
import datetime
import shutil
import traceback

from flask import Blueprint, jsonify, request, send_file

from ..state import (
    get_uploaded_flights, set_uploaded_flights,
    get_uploaded_airport_map, set_uploaded_airport_map,
    get_active_flights, set_active_flights,
    get_active_chains, set_active_chains,
    get_filtered_mode, set_filtered_mode,
    get_generated_source, set_generated_source,
    get_uploaded_xlsx_bytes, set_uploaded_xlsx_bytes,
    get_last_upload_filename, set_last_upload_filename,
    get_last_upload_count, set_last_upload_count,
    get_processing_progress, set_processing_progress,
    get_processing_stage, set_processing_stage,
    get_current_history_id, set_current_history_id,
    get_transit_cache, set_transit_cache,
    get_flight_aircraft_cache, set_flight_aircraft_cache,
    get_aircraft_chains_cache, set_aircraft_chains_cache,
)
from ..services.data_service import data_service
from ..services import routing_service, runway_service, gate_service, crew_service
from ..services.flight_filter import filter_flights, SICHUAN_BASES
from ..models.flight import Flight
from ..utils.data_loader import _get_default_airport_map as _get_icao_map
from ..utils.city_geo import build_transit_cache_from_flights
from ..auth import USERS, verify_user, get_user_history_list, get_user_history, get_user_history_dir

flight_bp = Blueprint('flight', __name__)

# 持久化目录基础路径
_HISTORY_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'history')
os.makedirs(_HISTORY_BASE, exist_ok=True)


def _get_history_dir():
    """获取当前会话用户的历史记录目录"""
    username = getattr(request, '_username', None)
    if username:
        return os.path.join(_HISTORY_BASE, username)
    return os.path.join(_HISTORY_BASE, '..')  # 无效路径作为降级


# ==================== 辅助函数 ====================

def safe_handler(fn):
    """装饰器：捕获所有异常，永远返回 JSON"""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()
            return jsonify({
                'code': 500,
                'msg': str(e),
            }), 500
    wrapper.__name__ = fn.__name__
    return wrapper


def require_user(fn):
    """装饰器：注入当前用户信息到 request._username"""
    def wrapper(*args, **kwargs):
        username = request.args.get('username') or request.headers.get('X-Username') or ''
        if not username or username not in USERS:
            return jsonify({'code': 401, 'msg': '未登录或会话已过期'}), 401
        request._username = username
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def _parse_time_value(val):
    """解析 Excel 中的时间值 -> (year, month, day, hour, minute)
    支持: datetime对象, Excel浮点序列号, '2020-11-30 06:00', '30/11/2020 08:45:00', '2020,11,30,6,0'
    """
    if val is None:
        return (2020, 11, 30, 0, 0)
    # datetime 对象或 openpyxl 时间对象
    if hasattr(val, 'year'):
        return (val.year, val.month, val.day,
                getattr(val, 'hour', 0), getattr(val, 'minute', 0))
    # Excel 浮点序列号 (天为单位的数字)
    if isinstance(val, (int, float)):
        try:
            from datetime import datetime, timedelta
            base = datetime(1899, 12, 30)
            dt = base + timedelta(days=float(val))
            return (dt.year, dt.month, dt.day, dt.hour, dt.minute)
        except Exception:
            pass
    s = str(val).strip()
    # '2020-11-30 06:00' / '2020-11-30 06:00:00'
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                int(m.group(4)), int(m.group(5)))
    # '30/11/2020 08:45:00' / '30/11/2020 08:45'
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{2}):(\d{2})', s)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)),
                int(m.group(4)), int(m.group(5)))
    # '2020, 11, 30, 6, 0'
    parts = [int(x.strip()) for x in s.replace(' ', '').split(',')]
    if len(parts) >= 5:
        return tuple(parts[:5])
    return (2020, 11, 30, 0, 0)


def _flight_date_key(f):
    y, m, d, *_ = f.time_departure
    return f"{y}-{m:02d}-{d:02d}"


def _get_active_flights():
    """获取当前活跃航班，优先使用筛选后的数据"""
    if get_filtered_mode() and get_active_flights():
        # 防御性规范化：修复遗留的 6 元组时间数据
        _normalize_flight_times(get_active_flights())
        return list(get_active_flights())
    data_service.load_all()
    return list(data_service.flights)


def _get_active_chains():
    """获取当前活跃任务链（Flight对象列表）"""
    if get_filtered_mode() and get_active_chains():
        # 防御性规范化：修复链中航班可能遗留的 6 元组时间
        for chain in get_active_chains():
            _normalize_flight_times(chain)
        return get_active_chains()
    return None


def _normalize_flight_times(flights):
    """将航班列表中所有 6 元组时间规范化为 5 元组"""
    for f in flights:
        for attr in ('time_departure', 'time_arrival'):
            t = getattr(f, attr, None)
            if isinstance(t, (tuple, list)) and len(t) > 5:
                setattr(f, attr, tuple(t[:5]))


def _rebuild_transit_cache():
    """根据当前活跃航班重建航线途经省份缓存"""
    flights = _get_active_flights()
    if not flights:
        set_transit_cache({})
        return
    set_transit_cache(build_transit_cache_from_flights(list(flights)))
    print(f"[TransitCache] 已为 {len(get_transit_cache())} 条航线构建途经缓存")


def _save_cached_flights_at(hist_dir, flights):
    """缓存解析后的航班数据到 JSON（避免 load_history 重复解析 xlsx）"""
    os.makedirs(hist_dir, exist_ok=True)
    cache_path = os.path.join(hist_dir, 'flights_cache.json')
    try:
        cache_data = [_serialize_flight(f) for f in flights]
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False)
        print(f"[Cache] 已缓存 {len(flights)} 个航班到 {cache_path}")
    except Exception as e:
        print(f"[Cache] 缓存失败: {e}")


def _persist_filter_result(history_id):
    """将当前筛选结果持久化到磁盘（按用户分目录）"""
    hist_dir = os.path.join(_get_history_dir(), history_id)
    os.makedirs(hist_dir, exist_ok=True)

    # 保存筛选结果 JSON（航班数据和任务链）
    result_data = {
        'generated': bool(get_generated_source()),
        'uploaded_count': len(get_uploaded_flights()),
        'active_count': len(get_active_flights()),
        'chain_count': len(get_active_chains()),
        'flights': [_serialize_flight(f) for f in get_active_flights()],
        'chains': [[_serialize_flight(f) for f in chain] for chain in get_active_chains()],
    }
    with open(os.path.join(hist_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    # 更新 meta.json
    meta_path = os.path.join(hist_dir, 'meta.json')
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    meta['upload_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    meta['flight_count'] = len(get_uploaded_flights())
    meta['active_count'] = len(get_active_flights())
    meta['chain_count'] = len(get_active_chains())
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _serialize_flight(f):
    """将 Flight 对象或 dict 转为可 JSON 序列化的 dict（时间保留为整数列表）"""
    if isinstance(f, dict):
        return f
    td = tuple(f.time_departure) if isinstance(f.time_departure, (tuple, list)) else f.time_departure
    ta = tuple(f.time_arrival) if isinstance(f.time_arrival, (tuple, list)) else f.time_arrival
    return {
        'flight_id': f.flight_id,
        'flight_no': f.flight_no,
        'ac_type': f.ac_type,
        'layout': f.layout,
        'departure_airport': f.departure_airport,
        'arrival_airport': f.arrival_airport,
        'time_departure': list(td),
        'time_arrival': list(ta),
        'timespan': f.timespan,
        'cost': f.cost,
    }


# ==================== 登录 API ====================

@flight_bp.route('/auth/login', methods=['POST'])
@safe_handler
def login():
    """用户登录"""
    body = request.get_json() or {}
    username = body.get('username', '').strip()
    password = body.get('password', '').strip()
    if not username or not password:
        return jsonify({'code': 1, 'msg': '用户名和密码不能为空'})
    user = verify_user(username, password)
    if not user:
        return jsonify({'code': 1, 'msg': '用户名或密码错误'})
    return jsonify({'code': 0, 'data': {'username': user['username']}})


# ==================== 进度查询 ====================

@flight_bp.route('/flights/progress', methods=['GET'])
def processing_progress():
    """查询当前处理进度"""
    return jsonify({
        'code': 0,
        'data': {
            'progress': get_processing_progress(),
            'stage': get_processing_stage(),
        }
    })


# ==================== 航班上传 ====================

@flight_bp.route('/flights/upload', methods=['POST'])
@safe_handler
def upload_flights():
    """上传航班计划 xlsx 文件，解析并暂存"""
    import openpyxl

    if 'file' not in request.files:
        return jsonify({'code': 400, 'msg': '请上传 xlsx 文件'}), 400

    file = request.files['file']
    history_id = request.form.get('history_id', '').strip()
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'code': 400, 'msg': '仅支持 .xlsx 格式'}), 400

    set_processing_progress(2)
    set_processing_stage('正在读取文件...')

    # 保存原始文件字节（用于导出时保留原格式）
    file.seek(0)
    set_uploaded_xlsx_bytes(file.read())
    file.seek(0)

    # 持久化到磁盘
    if history_id:
        username = request.form.get('username', '').strip()
        if username:
            hist_dir = os.path.join(_HISTORY_BASE, username, history_id)
        else:
            hist_dir = os.path.join(_get_history_dir(), history_id)
        os.makedirs(hist_dir, exist_ok=True)
        xlsx_path = os.path.join(hist_dir, 'upload.xlsx')
        with open(xlsx_path, 'wb') as f:
            f.write(get_uploaded_xlsx_bytes())
        # 保存元信息
        meta = {
            'filename': file.filename,
            'upload_time': None,
            'flight_count': 0,
            'active_count': 0,
            'chain_count': 0,
        }
        with open(os.path.join(hist_dir, 'meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)

    set_processing_progress(5)
    set_processing_stage('正在打开工作簿...')

    wb = openpyxl.load_workbook(file, data_only=True)
    ws = wb.active

    set_processing_progress(8)
    set_processing_stage('正在查找表头...')

    # 查找表头行（包含 FLIGHT_ID 的行）
    header_row_idx = 1
    max_scan = min(ws.max_row + 1, 10)
    for ri in range(1, max_scan):
        row_vals = [str(c.value).strip().upper() if c.value is not None else ''
                     for c in ws[ri]]
        if 'FLIGHT_ID' in row_vals:
            header_row_idx = ri
            break

    set_processing_progress(10)
    set_processing_stage('正在读取列映射...')

    # 读取表头
    headers = []
    for cell in ws[header_row_idx]:
        headers.append(str(cell.value).strip() if cell.value is not None else '')

    # 查找各列索引
    col_map = {}
    for col_name in ['FLIGHT_ID', 'FLIGHT_NO', 'AC_TYPE', 'LAYOUT',
                     'DEPARTURE_AIRPORT', 'ARRIVAL_AIRPORT',
                     'TIME_DEPARTURE', 'TIME_ARRIVAL', 'STD', 'STA', 'TIMESPAN', 'COST']:
        for i, h in enumerate(headers):
            h_upper = h.upper()
            c_upper = col_name.upper()
            if c_upper in h_upper or h_upper == c_upper:
                col_map[col_name] = i
                break

    # 加载 ICAO -> 中文 映射
    icao_map = _get_icao_map()

    flights = []
    airport_set = {}
    parse_errors = 0

    total_data_rows = ws.max_row - header_row_idx
    set_processing_progress(15)
    set_processing_stage(f'正在解析航班数据 (0/{total_data_rows})...')

    for row_idx in range(header_row_idx + 1, ws.max_row + 1):
        # 更新解析进度 (15% ~ 90%)
        current_row = row_idx - header_row_idx
        if current_row % 50 == 0:  # 每50行更新一次进度，避免过于频繁
            pct = 15 + int(75 * current_row / total_data_rows)
            set_processing_progress(pct)
            set_processing_stage(f'正在解析航班数据 ({current_row}/{total_data_rows})...')
        row = [ws.cell(row=row_idx, column=c + 1).value for c in range(len(headers))]

        try:
            fid = col_map.get('FLIGHT_ID')
            flight_id = str(int(row[fid])) if fid is not None and row[fid] is not None else str(row_idx - 1)
        except Exception:
            flight_id = str(row_idx - 1)

        fno = col_map.get('FLIGHT_NO')
        flight_no = str(row[fno]).strip() if fno is not None and row[fno] is not None else ''

        act = col_map.get('AC_TYPE')
        ac_type = str(row[act]).strip() if act is not None and row[act] is not None else 'A319'

        lay = col_map.get('LAYOUT')
        layout = str(row[lay]).strip() if lay is not None and row[lay] is not None else 'C8Y124'

        # 出发/到达机场
        dep_idx = col_map.get('DEPARTURE_AIRPORT')
        arr_idx = col_map.get('ARRIVAL_AIRPORT')
        dep_ap = str(row[dep_idx]).strip() if dep_idx is not None and row[dep_idx] is not None else ''
        arr_ap = str(row[arr_idx]).strip() if arr_idx is not None and row[arr_idx] is not None else ''
        # ICAO 转中文名
        dep_ap = icao_map.get(dep_ap, dep_ap)
        arr_ap = icao_map.get(arr_ap, arr_ap)

        # 时间解析 (优先 STD/STA, 其次 TIME_DEPARTURE/TIME_ARRIVAL)
        td_idx = col_map.get('STD') or col_map.get('TIME_DEPARTURE')
        ta_idx = col_map.get('STA') or col_map.get('TIME_ARRIVAL')
        try:
            td = _parse_time_value(row[td_idx]) if td_idx is not None else (2020, 11, 30, 0, 0)
            ta = _parse_time_value(row[ta_idx]) if ta_idx is not None else (2020, 11, 30, 0, 0)
        except Exception:
            parse_errors += 1
            continue

        # timespan
        ts_idx = col_map.get('TIMESPAN')
        timespan = int(row[ts_idx]) if ts_idx is not None and row[ts_idx] is not None else 0

        # cost
        cost_idx = col_map.get('COST')
        cost = float(row[cost_idx]) if cost_idx is not None and row[cost_idx] is not None else 0

        try:
            flight_id = int(float(flight_id))
        except Exception:
            pass

        f = Flight(
            flight_id=flight_id,
            flight_no=flight_no,
            ac_type=ac_type,
            layout=layout,
            departure_airport=dep_ap,
            arrival_airport=arr_ap,
            time_departure=td,
            time_arrival=ta,
            timespan=int(timespan) if timespan else 0,
            cost=cost,
        )
        # 如果 xlsx 没有 TIMESPAN 列，从时间推算
        if not f.timespan:
            f.timespan = f.arrival_minutes - f.departure_minutes

        flights.append(f)

        if dep_ap:
            airport_set[dep_ap] = dep_ap
        if arr_ap:
            airport_set[arr_ap] = arr_ap

    set_processing_progress(95)
    set_processing_stage('解析完成，正在保存结果...')

    set_uploaded_flights(flights)
    set_uploaded_airport_map(airport_set)
    set_last_upload_filename(file.filename)
    set_last_upload_count(len(flights))
    # 新上传数据集：重置筛选/生成模式，避免沿用旧的任务链池
    set_filtered_mode(False)
    set_generated_source(False)

    # 缓存解析后的航班数据（避免 load_history 重新解析 xlsx）
    if history_id:
        _save_cached_flights_at(hist_dir, flights)

    set_processing_progress(100)
    set_processing_stage('文件解析完成')

    return jsonify({
        'code': 0,
        'data': {
            'flight_count': len(flights),
            'airport_count': len(airport_set),
            'parse_errors': parse_errors,
            'sample': flights[0].to_dict() if flights else None,
        },
    })


# ==================== 数据 API ====================

@flight_bp.route('/flights', methods=['GET'])
@safe_handler
def get_flights():
    """获取所有航班"""
    data_service.load_all()
    return jsonify({
        'code': 0,
        'data': [f.to_dict() for f in data_service.flights],
        'total': len(data_service.flights),
    })


@flight_bp.route('/flights/<int:flight_id>', methods=['GET'])
@safe_handler
def get_flight(flight_id):
    """获取单个航班"""
    data_service.load_all()
    results = data_service.search_flight(flight_id=flight_id)
    if not results:
        return jsonify({'code': 404, 'msg': '航班不存在'}), 404
    return jsonify({'code': 0, 'data': results[0].to_dict()})


# ==================== 航班筛选 API ====================

@flight_bp.route('/flights/filter', methods=['GET'])
@safe_handler
def filter_flights_api():
    """航班计划筛选：从上传数据或默认数据筛选能组成基地闭环的航班
    支持分页: chain_offset/chain_limit, orphan_offset/orphan_limit

    生成模式（客流量 → 航班计划 → 提交）：任务链天然满足，
    任务链池直接使用本次生成的全部任务链，不合格航班为 0。
    """
    chain_offset = request.args.get('chain_offset', 0, type=int)
    chain_limit = request.args.get('chain_limit', 50, type=int)
    orphan_offset = request.args.get('orphan_offset', 0, type=int)
    orphan_limit = request.args.get('orphan_limit', 50, type=int)

    # ===== 生成模式：直接使用活跃任务链作为任务链池 =====
    if get_filtered_mode() and get_generated_source() and get_active_chains():
        active_flights = get_active_flights()
        active_chains = get_active_chains()
        all_chains = [[f.to_dict() for f in chain] for chain in active_chains]
        total_chain_count = len(all_chains)
        paged_chains = all_chains[chain_offset:chain_offset + chain_limit]

        cities = set()
        for f in active_flights:
            cities.add(f.departure_airport)
            cities.add(f.arrival_airport)

        stats = {
            'total_flights': len(active_flights),
            'closed_count': len(active_flights),
            'orphan_count': 0,
            'chain_count': total_chain_count,
            'coverage_pct': 100.0,
            'city_coverage': f"{len(cities)}/{len(cities)}",
            'orphan_reasons': {},
            'timeout': False,
            'elapsed_sec': 0.0,
        }

        return jsonify({
            'code': 0,
            'data': {
                'stats': stats,
                'bases': sorted(SICHUAN_BASES),
                'closed_flights': [f.to_dict() for f in active_flights],
                'orphan_flights': [],
                'orphan_total': 0,
                'chains': paged_chains,
                'chain_total': total_chain_count,
            },
        })

    # 防御性规范化：修复可能存在的 6 元组时间数据
    uploaded = get_uploaded_flights()
    if uploaded:
        _normalize_flight_times(uploaded)

    result = filter_flights(max_chains=300, custom_flights=uploaded if uploaded else None)

    all_chains = [[f.to_dict() for f in chain] for chain in result['chains']]
    total_chain_count = len(all_chains)
    paged_chains = all_chains[chain_offset:chain_offset + chain_limit]

    all_orphans = result['orphan_flights']
    total_orphan_count = len(all_orphans)
    paged_orphans = all_orphans[orphan_offset:orphan_offset + orphan_limit]

    return jsonify({
        'code': 0,
        'data': {
            'stats': result['stats'],
            'bases': sorted(SICHUAN_BASES),
            'closed_flights': [f.to_dict() for f in result['closed_flights']],
            'orphan_flights': paged_orphans,
            'orphan_total': total_orphan_count,
            'chains': paged_chains,
            'chain_total': total_chain_count,
        },
    })


@flight_bp.route('/flights/export', methods=['GET'])
@safe_handler
def export_filtered():
    """导出筛选结果 xlsx — 保留原始上传文件格式，仅保留任务链中的航班"""
    import openpyxl

    # 优先使用已保存的筛选结果
    if get_filtered_mode() and get_active_chains():
        chains = get_active_chains()
        stats = {'合格航班': len(get_active_flights()), '任务链': len(get_active_chains())}
    else:
        uploaded = get_uploaded_flights()
        result = filter_flights(max_chains=300, custom_flights=uploaded if uploaded else None)
        chains = result['chains']
        stats = result['stats']

    # 收集任务链中所有航班的 flight_id
    chain_flight_ids = set()
    for chain in chains:
        for f in chain:
            chain_flight_ids.add(f.flight_id)

    xlsx_bytes = get_uploaded_xlsx_bytes()
    # 用原始上传文件作模板
    if xlsx_bytes:
        template = io.BytesIO(xlsx_bytes)
        wb = openpyxl.load_workbook(template)
    else:
        wb = openpyxl.Workbook()
        ws_tmp = wb.active
        ws_tmp.title = '航班信息'
        ws_tmp.append(['FLIGHT_ID', 'FLIGHT_NO', 'DEPARTURE_AIRPORT', 'ARRIVAL_AIRPORT', 'STD', 'STA'])
        for fid in sorted(chain_flight_ids):
            ws_tmp.append([fid, '', '', '', '', ''])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, download_name='航班筛选结果.xlsx')

    ws = wb.active

    # 查找 FLIGHT_ID 列
    header_row_idx = 1
    max_scan = min(ws.max_row + 1, 10)
    flight_id_col = None
    for ri in range(1, max_scan):
        for ci, cell in enumerate(ws[ri], 1):
            if cell.value is not None and str(cell.value).strip().upper() == 'FLIGHT_ID':
                header_row_idx = ri
                flight_id_col = ci
                break
        if flight_id_col:
            break

    if not flight_id_col:
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True, download_name='航班筛选结果.xlsx')

    # 收集匹配行号（快速方式：先扫描，再按需复制）
    matching_rows = []
    for ri in range(header_row_idx + 1, ws.max_row + 1):
        cell_val = ws.cell(row=ri, column=flight_id_col).value
        if cell_val is None:
            continue
        try:
            fid = int(float(str(cell_val).strip()))
        except (ValueError, TypeError):
            continue
        if fid in chain_flight_ids:
            matching_rows.append(ri)

    # 创建新工作簿，复制表头 + 匹配行（保持原始格式）
    new_wb = openpyxl.Workbook()
    new_ws = new_wb.active
    new_ws.title = ws.title

    # 复制表头行及以上
    for ri in range(1, header_row_idx + 1):
        for ci in range(1, ws.max_column + 1):
            src = ws.cell(row=ri, column=ci)
            dst = new_ws.cell(row=ri, column=ci)
            dst.value = src.value
            if src.has_style:
                dst.font = src.font.copy()
                dst.fill = src.fill.copy()
                dst.border = src.border.copy()
                dst.alignment = src.alignment.copy()

    # 复制匹配数据行
    for di, src_ri in enumerate(matching_rows):
        dst_ri = header_row_idx + 1 + di
        for ci in range(1, ws.max_column + 1):
            src = ws.cell(row=src_ri, column=ci)
            dst = new_ws.cell(row=dst_ri, column=ci)
            dst.value = src.value
            if src.has_style:
                dst.font = src.font.copy()
                dst.fill = src.fill.copy()
                dst.border = src.border.copy()
                dst.alignment = src.alignment.copy()

    # 添加统计 Sheet
    ws_stats = new_wb.create_sheet('筛选统计')
    ws_stats.append(['指标', '值'])
    for k, v in stats.items():
        ws_stats.append([str(k), str(v)])

    output = io.BytesIO()
    new_wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='航班筛选结果.xlsx',
    )


@flight_bp.route('/flights/apply', methods=['POST'])
@safe_handler
def apply_filtered():
    """保存筛选结果作为活跃数据源，触发排班"""
    # 提取用户名（来自 form 或 query 参数）
    username = request.form.get('username', '').strip() or request.args.get('username', '').strip()
    if username:
        request._username = username

    set_processing_progress(0)
    set_processing_stage('正在筛选航班任务链...')

    set_flight_aircraft_cache(None)
    set_aircraft_chains_cache(None)

    # 生成模式：任务链天然满足，直接沿用当前活跃航班/链，不重新筛选
    if get_filtered_mode() and get_generated_source() and get_active_chains():
        active_flights = list(get_active_flights())
        active_chains = list(get_active_chains())
        result = {
            'closed_flights': active_flights,
            'chains': active_chains,
            'stats': {
                'total_flights': len(active_flights),
                'closed_count': len(active_flights),
                'orphan_count': 0,
                'chain_count': len(active_chains),
                'coverage_pct': 100.0,
            },
        }
    else:
        uploaded = get_uploaded_flights()
        result = filter_flights(max_chains=300, custom_flights=uploaded if uploaded else None)

    set_processing_progress(80)
    set_processing_stage('正在保存筛选结果...')

    set_active_flights(list(result['closed_flights']))
    set_active_chains(list(result['chains']))
    set_filtered_mode(True)
    _rebuild_transit_cache()

    set_processing_progress(100)
    set_processing_stage('筛选完成')

    # 持久化筛选结果到磁盘
    history_id = request.form.get('history_id', '').strip() or get_current_history_id()
    if history_id:
        set_current_history_id(history_id)
        _persist_filter_result(history_id)

    stats = result['stats']

    return jsonify({
        'code': 0,
        'msg': f"已保存 {len(get_active_flights())} 条合格航班, {len(get_active_chains())} 条任务链",
        'data': {
            'active_flights': len(get_active_flights()),
            'chains': len(get_active_chains()),
            'stats': stats,
        },
    })


@flight_bp.route('/flights/status', methods=['GET'])
@safe_handler
def filter_status():
    """查询当前筛选状态"""
    return jsonify({
        'code': 0,
        'data': {
            'filtered_mode': get_filtered_mode(),
            'active_flights': len(get_active_flights()),
            'chains': len(get_active_chains()),
            'uploaded_file': get_last_upload_filename(),
            'uploaded_count': get_last_upload_count(),
        },
    })


# ==================== 历史记录持久化 API ====================

@flight_bp.route('/flights/history', methods=['GET'])
@require_user
@safe_handler
def get_history_list():
    """获取当前用户的所有历史分析记录"""
    username = request._username
    items = get_user_history_list(username)
    return jsonify({'code': 0, 'data': items})


@flight_bp.route('/flights/history/<history_id>', methods=['POST'])
@require_user
@safe_handler
def load_history(history_id):
    """加载历史分析记录到内存"""
    username = request._username
    result = get_user_history(username, history_id)
    if result[0] is None:
        return jsonify({'code': 404, 'msg': '历史记录不存在'}), 404
    hist_dir, user_dir = result

    set_flight_aircraft_cache(None)
    set_aircraft_chains_cache(None)

    # 优先从缓存加载航班数据（秒级），回退到解析 xlsx
    cache_path = os.path.join(hist_dir, 'flights_cache.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            flights = []
            for fd in cache_data:
                td = fd.get('time_departure', (2020, 11, 30, 0, 0))
                ta = fd.get('time_arrival', (2020, 11, 30, 0, 0))
                if isinstance(td, list):
                    td = tuple(td)
                if isinstance(ta, list):
                    ta = tuple(ta)
                f = Flight(
                    flight_id=fd.get('flight_id', 0),
                    flight_no=fd.get('flight_no', ''),
                    ac_type=fd.get('ac_type', 'A319'),
                    layout=fd.get('layout', 'C8Y124'),
                    departure_airport=fd.get('departure_airport', ''),
                    arrival_airport=fd.get('arrival_airport', ''),
                    time_departure=td, time_arrival=ta,
                    timespan=fd.get('timespan', 0), cost=fd.get('cost', 0),
                )
                flights.append(f)
            set_uploaded_flights(flights)
            airport_map = {}
            for f in flights:
                if f.departure_airport:
                    airport_map[f.departure_airport] = f.departure_airport
                if f.arrival_airport:
                    airport_map[f.arrival_airport] = f.arrival_airport
            set_uploaded_airport_map(airport_map)
            set_uploaded_xlsx_bytes(None)
            # 加载 xlsx 原始字节（用于导出）
            xlsx_path = os.path.join(hist_dir, 'upload.xlsx')
            if os.path.exists(xlsx_path):
                with open(xlsx_path, 'rb') as xf:
                    set_uploaded_xlsx_bytes(xf.read())
            print(f"[LoadHistory] 从缓存加载: {len(flights)} 个航班")
        except Exception as e:
            print(f"[LoadHistory] 缓存加载失败: {e}, 回退到 xlsx 解析")
            cache_path = ''  # 触发回退

    if not os.path.exists(cache_path):
        # 回退：从 xlsx 解析
        xlsx_path = os.path.join(hist_dir, 'upload.xlsx')
        if os.path.exists(xlsx_path):
            import openpyxl
            with open(xlsx_path, 'rb') as xf:
                set_uploaded_xlsx_bytes(xf.read())
            buf = io.BytesIO(get_uploaded_xlsx_bytes())
            wb = openpyxl.load_workbook(buf, data_only=True)
            ws = wb.active
            header_row_idx = 1
            max_scan = min(ws.max_row + 1, 10)
            for ri in range(1, max_scan):
                row_vals = [str(c.value).strip().upper() if c.value is not None else ''
                             for c in ws[ri]]
                if 'FLIGHT_ID' in row_vals:
                    header_row_idx = ri
                    break
            headers = []
            for cell in ws[header_row_idx]:
                headers.append(str(cell.value).strip() if cell.value is not None else '')
            col_map = {}
            for col_name in ['FLIGHT_ID', 'FLIGHT_NO', 'AC_TYPE', 'LAYOUT',
                             'DEPARTURE_AIRPORT', 'ARRIVAL_AIRPORT',
                             'STD', 'STA', 'TIME_DEPARTURE', 'TIME_ARRIVAL', 'TIMESPAN', 'COST']:
                for i, h in enumerate(headers):
                    h_upper = h.upper()
                    c_upper = col_name.upper()
                    if c_upper in h_upper or h_upper == c_upper:
                        col_map[col_name] = i
                        break
            icao_map = _get_icao_map()
            flights = []
            airport_set = {}
            for row_idx in range(header_row_idx + 1, ws.max_row + 1):
                row = [ws.cell(row=row_idx, column=c + 1).value for c in range(len(headers))]
                try:
                    fid = col_map.get('FLIGHT_ID')
                    flight_id = str(int(row[fid])) if fid is not None and row[fid] is not None else str(row_idx - 1)
                except Exception:
                    flight_id = str(row_idx - 1)
                fno = col_map.get('FLIGHT_NO')
                flight_no = str(row[fno]).strip() if fno is not None and row[fno] is not None else ''
                act = col_map.get('AC_TYPE')
                ac_type = str(row[act]).strip() if act is not None and row[act] is not None else 'A319'
                lay = col_map.get('LAYOUT')
                layout = str(row[lay]).strip() if lay is not None and row[lay] is not None else 'C8Y124'
                dep_idx = col_map.get('DEPARTURE_AIRPORT')
                arr_idx = col_map.get('ARRIVAL_AIRPORT')
                dep_ap = str(row[dep_idx]).strip() if dep_idx is not None and row[dep_idx] is not None else ''
                arr_ap = str(row[arr_idx]).strip() if arr_idx is not None and row[arr_idx] is not None else ''
                dep_ap = icao_map.get(dep_ap, dep_ap)
                arr_ap = icao_map.get(arr_ap, arr_ap)
                td_idx = col_map.get('STD') or col_map.get('TIME_DEPARTURE')
                ta_idx = col_map.get('STA') or col_map.get('TIME_ARRIVAL')
                try:
                    td = _parse_time_value(row[td_idx]) if td_idx is not None else (2020, 11, 30, 0, 0)
                    ta = _parse_time_value(row[ta_idx]) if ta_idx is not None else (2020, 11, 30, 0, 0)
                except Exception:
                    continue
                ts_idx = col_map.get('TIMESPAN')
                timespan = int(row[ts_idx]) if ts_idx is not None and row[ts_idx] is not None else 0
                cost_idx = col_map.get('COST')
                cost = float(row[cost_idx]) if cost_idx is not None and row[cost_idx] is not None else 0
                try:
                    flight_id = int(float(flight_id))
                except Exception:
                    pass
                f = Flight(
                    flight_id=flight_id, flight_no=flight_no,
                    ac_type=ac_type, layout=layout,
                    departure_airport=dep_ap, arrival_airport=arr_ap,
                    time_departure=td, time_arrival=ta,
                    timespan=int(timespan) if timespan else 0, cost=cost,
                )
                if not f.timespan:
                    f.timespan = f.arrival_minutes - f.departure_minutes
                flights.append(f)
                if dep_ap:
                    airport_set[dep_ap] = dep_ap
                if arr_ap:
                    airport_set[arr_ap] = arr_ap
            set_uploaded_flights(flights)
            set_uploaded_airport_map(airport_set)
            # 保存缓存供下次使用
            _save_cached_flights_at(hist_dir, flights)
            print(f"[LoadHistory] 从 xlsx 解析: {len(flights)} 个航班")

    # 读取筛选结果
    result_path = os.path.join(hist_dir, 'result.json')
    if os.path.exists(result_path):
        with open(result_path, 'r', encoding='utf-8') as f:
            result_data = json.load(f)

        # 恢复生成来源标记（生成模式：任务链天然满足）
        set_generated_source(bool(result_data.get('generated', False)))

        # 从 JSON 重建 Flight 对象
        active_flights = []
        for fd in result_data.get('flights', []):
            td = fd.get('time_departure', (2020, 11, 30, 0, 0))
            ta = fd.get('time_arrival', (2020, 11, 30, 0, 0))
            if isinstance(td, list):
                td = tuple(td)
            if isinstance(ta, list):
                ta = tuple(ta)
            if isinstance(td, str) and td:
                td = _parse_time_value(td)
            if isinstance(ta, str) and ta:
                ta = _parse_time_value(ta)
            f = Flight(
                flight_id=fd.get('flight_id', 0),
                flight_no=fd.get('flight_no', ''),
                ac_type=fd.get('ac_type', 'A319'),
                layout=fd.get('layout', 'C8Y124'),
                departure_airport=fd.get('departure_airport', ''),
                arrival_airport=fd.get('arrival_airport', ''),
                time_departure=td,
                time_arrival=ta,
                timespan=fd.get('timespan', 0),
                cost=fd.get('cost', 0),
            )
            active_flights.append(f)
        set_active_flights(active_flights)

        active_chains = []
        for chain_data in result_data.get('chains', []):
            chain = []
            for fd in chain_data:
                td = fd.get('time_departure', (2020, 11, 30, 0, 0))
                ta = fd.get('time_arrival', (2020, 11, 30, 0, 0))
                if isinstance(td, list):
                    td = tuple(td)
                if isinstance(ta, list):
                    ta = tuple(ta)
                f = Flight(
                    flight_id=fd.get('flight_id', 0),
                    flight_no=fd.get('flight_no', ''),
                    ac_type=fd.get('ac_type', 'A319'),
                    layout=fd.get('layout', 'C8Y124'),
                    departure_airport=fd.get('departure_airport', ''),
                    arrival_airport=fd.get('arrival_airport', ''),
                    time_departure=td,
                    time_arrival=ta,
                    timespan=fd.get('timespan', 0),
                    cost=fd.get('cost', 0),
                )
                chain.append(f)
            active_chains.append(chain)
        set_active_chains(active_chains)

        set_filtered_mode(True)
        set_last_upload_count(result_data.get('uploaded_count', 0))

    # 读取 meta
    meta_path = os.path.join(hist_dir, 'meta.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        set_last_upload_filename(meta.get('filename', ''))
    else:
        set_last_upload_filename('')

    set_current_history_id(history_id)

    # 同步异常调度服务的历史记录 ID
    from ..services.anomaly_service import anomaly_service
    from ..services.audit_log_service import audit_log
    anomaly_service.set_history_id(history_id, user_dir)
    audit_log.set_history_id(history_id, user_dir)

    return jsonify({
        'code': 0,
        'msg': f"已加载历史记录: {get_last_upload_filename()}",
        'data': {
            'filtered_mode': get_filtered_mode(),
            'active_flights': len(get_active_flights()),
            'chains': len(get_active_chains()),
            'uploaded_file': get_last_upload_filename(),
            'uploaded_count': len(get_uploaded_flights()),
            'filename': get_last_upload_filename(),
            'flight_count': len(get_uploaded_flights()),
        },
    })


@flight_bp.route('/flights/history/<history_id>', methods=['DELETE'])
@require_user
@safe_handler
def delete_history(history_id):
    """删除历史分析记录"""
    username = request._username
    result = get_user_history(username, history_id)
    hist_dir = result[0] if result[0] else os.path.join(get_user_history_dir(username), history_id)
    if os.path.isdir(hist_dir):
        shutil.rmtree(hist_dir)
    if get_current_history_id() == history_id:
        set_current_history_id(None)
    return jsonify({'code': 0, 'msg': '已删除'})
