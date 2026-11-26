"""航班生成 + 旅客查询 API 路由"""

import os
import re
import json
import datetime

from flask import Blueprint, jsonify, request

from ..services.flight_generator import FlightGenerator, DEFAULT_TRAFFIC
from ..services.passenger_service import passenger_service
from ..services import runway_service, gate_service, routing_service
from ..services.aircraft_types import layout_seats
from ..services.experiment.paxflow_builder import (
    PAXFLOW_LOAD_FACTOR as _PAXFLOW_LOAD_FACTOR,
    build_paxflow_schedule,
    flight_date as _paxflow_date,
)
from ..models.flight import Flight
from ..auth import get_user_history_dir, get_history_dir
from ..state import (
    get_active_flights, set_active_flights,
    get_active_chains, set_active_chains,
    set_current_history_id,
    get_passenger_index, set_passenger_index,
    get_weather_disruption_plan,
)
from .. import state

generate_bp = Blueprint('generate', __name__)


def _parse_generated_time(val):
    """将生成结果中的时间（字符串 '2020-11-30 06:00' 或列表）转为 5 元组"""
    if isinstance(val, (tuple, list)):
        return tuple(int(x) for x in val[:5])
    if isinstance(val, str):
        parts = re.split(r'[-:\s]+', val.strip())
        if len(parts) >= 5:
            try:
                return tuple(int(x) for x in parts[:5])
            except ValueError:
                pass
    return (2020, 11, 30, 0, 0)


def _serialize_flight(f):
    """Flight 对象 -> 可 JSON 序列化 dict（时间保留为整数列表）"""
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


def _dicts_to_flights(flights_data):
    """生成的航班 dict 列表 -> Flight 对象列表（保留空飞/旅客附加字段）"""
    flights = []
    for fd in flights_data:
        f = Flight(
            flight_id=fd.get('flight_id', 0),
            flight_no=fd.get('flight_no', ''),
            ac_type=fd.get('ac_type', 'A319'),
            layout=fd.get('layout', 'C8Y124'),
            departure_airport=fd.get('departure_airport', ''),
            arrival_airport=fd.get('arrival_airport', ''),
            time_departure=_parse_generated_time(fd.get('time_departure')),
            time_arrival=_parse_generated_time(fd.get('time_arrival')),
            timespan=fd.get('timespan', 0),
            cost=fd.get('cost', 0),
        )
        f._is_ferry = bool(fd.get('is_ferry', False))
        f._pax_count = fd.get('pax_count', 0)
        f._passenger_manifest = fd.get('passenger_manifest', {})
        f._pax_list = fd.get('pax_list', [])
        flights.append(f)
    return flights


@generate_bp.route('/api/generate/flights', methods=['POST'])
def generate_flights():
    """POST /api/generate/flights
    输入城市客流量数据，生成航班计划 + 旅客清单 + 任务链。
    结果存储在服务端 state 中，只返回摘要（避免 sessionStorage 溢出）。
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}

    if not data.get('city_traffic'):
        data['city_traffic'] = DEFAULT_TRAFFIC
    if not data.get('dates'):
        data['dates'] = ['2020-11-30', '2020-12-01', '2020-12-02',
                         '2020-12-03', '2020-12-04', '2020-12-05']
    if not data.get('hub'):
        data['hub'] = '成都'

    try:
        generator = FlightGenerator(data)
        result = generator.generate()

        # 存储完整结果到服务端 state
        state.set_generated_data(result)

        # 同时构建旅客索引和座位索引
        pax_index = {p['pax_id']: p for p in result.get('passengers', [])}
        state.set_passenger_index(pax_index)

        manifest_index = {}
        for f in result.get('flights', []):
            if f.get('passenger_manifest'):
                manifest_index[f['flight_id']] = {
                    'flight_no': f['flight_no'],
                    'manifest': f['passenger_manifest'],
                    'pax_count': f.get('pax_count', 0),
                }
        state.set_manifest_index(manifest_index)

        # 只返回摘要，不返回完整旅客数据
        stats = result['stats']
        chains_summary = result['chains']
        return jsonify({
            'code': 0,
            'data': {
                'stats': stats,
                'chains': chains_summary,
                'flights': result['flights'],  # 航班不含庞大的 pax_list
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'生成失败: {str(e)}'}), 500


@generate_bp.route('/api/generate/data', methods=['GET'])
def get_generated_data():
    """GET /api/generate/data
    获取服务端存储的航班生成结果。
    支持 ?type=stats|chains|flights|passengers&limit=N&offset=N&flight_id=X&pax_id=X
    """
    data = state.get_generated_data()
    if not data:
        return jsonify({'code': 1, 'msg': '暂无生成数据，请先生成航班计划'}), 404

    data_type = request.args.get('type', 'stats')
    limit = int(request.args.get('limit') or 50)
    offset = int(request.args.get('offset') or 0)
    flight_id = request.args.get('flight_id', '')
    pax_id = request.args.get('pax_id', '')

    if data_type == 'stats':
        return jsonify({'code': 0, 'data': data['stats']})

    if data_type == 'chains':
        return jsonify({'code': 0, 'data': data['chains']})

    if data_type == 'flights':
        if flight_id:
            flight = next((f for f in data['flights'] if f['flight_id'] == flight_id), None)
            if not flight:
                return jsonify({'code': 1, 'msg': '未找到该航班'}), 404
            return jsonify({'code': 0, 'data': flight})
        total = len(data['flights'])
        subset = data['flights'][offset:offset+limit]
        return jsonify({'code': 0, 'data': subset, 'total': total})

    if data_type == 'passengers':
        if pax_id:
            pax = state.get_passenger_index().get(pax_id)
            if not pax:
                return jsonify({'code': 1, 'msg': '未找到该旅客'}), 404
            return jsonify({'code': 0, 'data': pax})
        total = len(data.get('passengers', []))
        subset = (data.get('passengers', []) or [])[offset:offset+limit]
        return jsonify({'code': 0, 'data': subset, 'total': total})

    return jsonify({'code': 1, 'msg': '无效的 type 参数'}), 400


@generate_bp.route('/api/generate/commit', methods=['POST'])
def commit_flights():
    """POST /api/generate/commit
    将生成的航班/链提交到调度引擎，并创建一条新的历史记录。
    - 任务链池 = 本次生成的全部任务链（天然满足，不合格航班为 0）
    - 每次点击该历史记录项，都会从磁盘恢复本次的全部任务链
    """
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or request.args.get('username') or 'user1').strip()

    data = state.get_generated_data()
    if not data:
        return jsonify({'code': 1, 'msg': '暂无生成数据，请先生成航班计划'}), 400

    flights_data = data.get('flights', [])
    chains_data = data.get('chains', [])

    if not flights_data:
        return jsonify({'code': 1, 'msg': '无航班数据'}), 400

    # 1. dict -> Flight 对象（供调度引擎使用）
    flights = _dicts_to_flights(flights_data)
    flight_map = {f.flight_id: f for f in flights}

    # 2. 链摘要 -> Flight 对象列表（保持链内顺序）
    chains = []
    for cd in chains_data:
        chain = [flight_map[fid] for fid in cd.get('flights', []) if fid in flight_map]
        if chain:
            chains.append(chain)

    total_flights = len(flights)
    total_chains = len(chains)

    # 3. 创建新的历史条目（每次点击该历史记录项都恢复本次全部任务链）
    history_id = 'gen_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    hist_dir = os.path.join(get_user_history_dir(username), history_id)
    os.makedirs(hist_dir, exist_ok=True)

    serialized = [_serialize_flight(f) for f in flights]

    # flights_cache.json：上传航班缓存（load_history 秒级恢复）
    with open(os.path.join(hist_dir, 'flights_cache.json'), 'w', encoding='utf-8') as fh:
        json.dump(serialized, fh, ensure_ascii=False)

    # result.json：筛选结果（全部航班 + 全部任务链），generated 标记来源
    result_data = {
        'generated': True,
        'uploaded_count': total_flights,
        'active_count': total_flights,
        'chain_count': total_chains,
        'flights': serialized,
        'chains': [[_serialize_flight(f) for f in chain] for chain in chains],
    }
    with open(os.path.join(hist_dir, 'result.json'), 'w', encoding='utf-8') as fh:
        json.dump(result_data, fh, ensure_ascii=False, indent=2)

    # meta.json：历史列表展示
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    meta = {
        'filename': f'客流量生成航班计划 {now_str}',
        'upload_time': now_str,
        'flight_count': total_flights,
        'active_count': total_flights,
        'chain_count': total_chains,
    }
    with open(os.path.join(hist_dir, 'meta.json'), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    # 4. 写入内存状态（调度引擎直接使用本次航班/任务链）
    state.set_uploaded_flights(list(flights))
    state.set_uploaded_airport_map({
        f.departure_airport: f.departure_airport for f in flights
    })
    state.set_active_flights(list(flights))
    state.set_active_chains(chains)
    state.set_filtered_mode(True)
    state.set_generated_source(True)
    state.set_current_history_id(history_id)
    state.set_last_upload_filename(meta['filename'])
    state.set_last_upload_count(total_flights)
    state.set_uploaded_xlsx_bytes(None)
    state.set_flight_aircraft_cache(None)
    state.set_aircraft_chains_cache(None)

    return jsonify({
        'code': 0,
        'msg': f'航班计划已提交，共 {total_flights} 个航班，{total_chains} 条链',
        'data': {
            'history_id': history_id,
            'total_flights': total_flights,
            'total_chains': total_chains,
        },
    })


@generate_bp.route('/api/passenger/<pax_id>', methods=['GET'])
def get_passenger(pax_id):
    """GET /api/passenger/<pax_id>
    按旅客 ID 查询旅客完整信息。
    """
    pax = passenger_service.get_by_id(pax_id)
    if not pax:
        return jsonify({'code': 1, 'msg': '未找到该旅客'}), 404
    return jsonify({'code': 0, 'data': pax})


@generate_bp.route('/api/paxflow/manifests', methods=['POST'])
def get_paxflow_manifests():
    """POST /api/paxflow/manifests
    旅客流模拟对接：按航班号批量返回乘客编号清单。
    body: { "date": "2020-11-30", "flights": ["3U8561", ...] }
    从当前生成的旅客池（passenger_index）按 flight_no 匹配，返回每个航班的乘客编号数组。
    匹配不到的航班返回空数组，由前端按规则生成兜底编号。
    """
    body = request.get_json(silent=True) or {}
    flight_nos = body.get('flights') or []
    pax_index = state.get_passenger_index() or {}

    # flight_no -> [pax_id, ...]（保持生成顺序，前端按下标取编号即对应该航班实际乘客）
    by_flight = {}
    for pid, info in pax_index.items():
        fno = info.get('flight_no') if isinstance(info, dict) else None
        if fno:
            by_flight.setdefault(fno, []).append(pid)

    manifests = []
    for fno in flight_nos:
        manifests.append({
            'flight_no': fno,
            'pax_ids': by_flight.get(fno, []),
        })
    return jsonify({
        'code': 0,
        'data': {
            'date': body.get('date', ''),
            'manifests': manifests,
        },
    })


# ==================== 旅客流模拟数据源 ====================
# 矩形登机口映射、跑道窗口、按天组装等纯逻辑已抽到
# backend/services/experiment/paxflow_builder.py，路由与实验流水线共用。


def _ensure_paxflow_flights():
    """旅客流模拟数据源：始终加载最近一条 gen_* 历史记录（用户 user1），
    保证使用最新生成的航班（含首日如 2020-11-29），
    不受其他页面加载历史记录时对全局活跃航班状态的覆盖影响。"""
    user_dir = os.path.join(get_history_dir(), 'user1')
    if not os.path.isdir(user_dir):
        return []
    candidates = sorted(
        (d for d in os.listdir(user_dir)
         if d.startswith('gen_') and os.path.isdir(os.path.join(user_dir, d))),
        reverse=True,
    )
    for hid in candidates:
        result_path = os.path.join(user_dir, hid, 'result.json')
        if not os.path.exists(result_path):
            continue
        try:
            with open(result_path, 'r', encoding='utf-8') as fh:
                result_data = json.load(fh)
        except Exception:
            continue
        flights = []
        for fd in result_data.get('flights', []):
            td = tuple(fd.get('time_departure')) if isinstance(fd.get('time_departure'), (list, tuple)) else (2020, 11, 30, 0, 0)
            ta = tuple(fd.get('time_arrival')) if isinstance(fd.get('time_arrival'), (list, tuple)) else (2020, 11, 30, 0, 0)
            flights.append(Flight(
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
            ))
        if not flights:
            continue
        set_active_flights(flights)
        chains = []
        for chain_data in result_data.get('chains', []):
            chain = []
            for fd in chain_data:
                td = tuple(fd.get('time_departure')) if isinstance(fd.get('time_departure'), (list, tuple)) else (2020, 11, 30, 0, 0)
                ta = tuple(fd.get('time_arrival')) if isinstance(fd.get('time_arrival'), (list, tuple)) else (2020, 11, 30, 0, 0)
                chain.append(Flight(
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
                ))
            if chain:
                chains.append(chain)
        set_active_chains(chains)
        set_current_history_id(hid)
        print(f"[PaxFlow] 自动加载最近历史记录: {hid} ({len(flights)} 航班)")
        return flights
    return []


def _build_paxflow_passengers(ap_flights):
    """按载客量（layout 座位数 × 载客率）为成都场航班生成乘客编号，
    填充 passenger_index，使 /api/paxflow/manifests 返回真实编号。
    """
    pax_index = {}
    counter = 0
    for f in ap_flights:
        seats = layout_seats(f.layout) or 150
        pax_total = max(1, round(seats * _PAXFLOW_LOAD_FACTOR))
        f._pax_count = pax_total
        fd = _paxflow_date(f)
        y, m, d = (int(x) for x in fd.split('-'))
        mmdd = f"{m:02d}{d:02d}"
        for i in range(pax_total):
            counter += 1
            pid = f"Pax-{mmdd}-{counter:05d}"
            row = i // 6 + 1
            col = chr(65 + (i % 6))
            pax_index[pid] = {
                'pax_id': pid,
                'origin': f.departure_airport,
                'destination': f.arrival_airport,
                'date': fd,
                'flight_no': f.flight_no,
                'seat': f"{row}{col}",
                'cabin': 'economy',
                'group_id': None,
                'special': False,
            }
    set_passenger_index(pax_index)
    return len(pax_index)


@generate_bp.route('/api/paxflow/schedule', methods=['GET'])
def get_paxflow_schedule():
    """GET /api/paxflow/schedule
    旅客流模拟数据源：加载最近历史记录（或复用已加载航班），对成都场航班执行
    跑道调度 + 登机口分配，按天组织成前端可用的航班调度数据。
    登机口使用前端布局的"矩形 xx"名称（通过确定性规则映射自后端登机口分配）。
    同时生成乘客编号填充旅客池，供 /api/paxflow/manifests 使用。

    返回:
      { code, data: { history_id, airport, dates: [...], schedule: { date: [航班,...] } } }
    """
    try:
        flights = _ensure_paxflow_flights()
        if not flights:
            return jsonify({'code': 1, 'msg': '没有可用的航班数据（无历史记录）'}), 404

        airport = '成都'
        ap_flights = [
            f for f in flights
            if f.departure_airport == airport or f.arrival_airport == airport
        ]
        if not ap_flights:
            return jsonify({'code': 1, 'msg': '历史记录中无成都场航班'}), 404

        # 天气中断计划：?disrupted=true 时读取共享 state 中的 plan 应用到各 entry
        disrupted = request.args.get('disrupted', '') in ('1', 'true', 'True')
        plan = get_weather_disruption_plan() if disrupted else {}

        # 1) 跑道调度（真实分配）
        runway_schedule, _ = runway_service.solve_multi_runway(ap_flights, airport)

        # 2) 登机口分配（真实分配，返回辰Gxx）
        gates = gate_service.assign_flights_to_gates(
            airport, 'bipartite', flights=flights, runway_schedule=runway_schedule,
        )
        gate_map = {}  # flight_id -> {gate:'辰Gxx', runway_group}
        for g in gates:
            for a in g.assigned_flights:
                gate_map[a['flight'].flight_id] = {
                    'gate': g.name,
                    'runway_group': a.get('runway', g.runway_group),
                }

        # 3) 飞机尾号（链覆盖，与调度页一致）
        try:
            from .schedule_routes import _get_flight_aircraft_map
            tail_map = _get_flight_aircraft_map()
        except Exception:
            tail_map = {}

        # 4) 生成乘客编号（对接 /api/paxflow/manifests）
        pax_count = _build_paxflow_passengers(ap_flights)

        # 5) 按天组装调度数据（纯函数，不写全局状态）
        paxflow = build_paxflow_schedule(
            ap_flights,
            airport=airport,
            runway_schedule=runway_schedule,
            gate_map=gate_map,
            tail_map=tail_map,
            plan=plan,
        )
        dates = paxflow['dates']
        schedule_by_date = paxflow['schedule']

        return jsonify({
            'code': 0,
            'data': {
                'history_id': state.get_current_history_id() or '',
                'airport': airport,
                'pax_count': pax_count,
                'dates': dates,
                'schedule': schedule_by_date,
            },
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': f'获取旅客流调度失败: {str(e)}'}), 500


@generate_bp.route('/api/flight/<flight_id>/passengers', methods=['GET'])
def get_flight_passengers(flight_id):
    """GET /api/flight/<flight_id>/passengers
    按航班 ID 查询该航班所有旅客。
    """
    manifest = passenger_service.get_flight_manifest(flight_id)
    if not manifest:
        return jsonify({'code': 1, 'msg': '未找到该航班旅客信息'}), 404

    pax_list = passenger_service.get_by_flight(flight_id)

    occupied = sum(1 for v in manifest.get('manifest', {}).values() if v)
    business_occupied = sum(
        1 for seat, pid in manifest.get('manifest', {}).items()
        if pid and seat in ['1A', '1C', '1D', '1F', '2A', '2C', '2D', '2F']
    )

    return jsonify({
        'code': 0,
        'data': {
            'flight_id': flight_id,
            'flight_no': manifest.get('flight_no', ''),
            'seats': manifest.get('manifest', {}),
            'pax_list': pax_list,
            'stats': {
                'total': 132,
                'occupied': manifest.get('pax_count', 0),
                'business': business_occupied,
                'economy': manifest.get('pax_count', 0) - business_occupied,
            }
        }
    })
