"""数据查询 API 路由 — 统一 {code: 0, data/msg} 格式"""
import traceback
from flask import Blueprint, jsonify, request

from ..services.data_service import data_service

data_bp = Blueprint('data', __name__)


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


@data_bp.route('/aircrafts', methods=['GET'])
@safe_handler
def get_aircrafts():
    """获取所有飞机（含综合指标）"""
    data_service.load_all()
    return jsonify({
        'code': 0,
        'data': [a.to_dict() for a in data_service.aircrafts],
        'total': len(data_service.aircrafts),
    })


@data_bp.route('/aircrafts/search', methods=['GET'])
@safe_handler
def search_aircrafts():
    """根据关键词或指标范围搜索飞机"""
    data_service.load_all()
    kw = request.args.get('kw', '').strip()
    min_idx = request.args.get('min_idx', type=float)
    max_idx = request.args.get('max_idx', type=float)
    ac_type = request.args.get('ac_type', '').strip()

    result = list(data_service.aircrafts)
    if kw:
        kw_lower = kw.lower()
        result = [a for a in result
                  if kw_lower in a.tail_no.lower()
                  or kw_lower in a.ac_type.lower()
                  or kw_lower in str(a.ac_id)]
    if min_idx is not None:
        result = [a for a in result if a.quality_index >= min_idx]
    if max_idx is not None:
        result = [a for a in result if a.quality_index <= max_idx]
    if ac_type:
        result = [a for a in result if a.ac_type == ac_type]

    return jsonify({
        'code': 0,
        'data': [a.to_dict() for a in result],
        'total': len(result),
    })


@data_bp.route('/airports/names', methods=['GET'])
@safe_handler
def get_airport_names():
    """获取所有机场中文名称列表（从航班数据中提取）"""
    data_service.load_all()
    names = sorted(set(
        f.departure_airport for f in data_service.flights
    ) | set(
        f.arrival_airport for f in data_service.flights
    ))
    return jsonify({'code': 0, 'data': [n for n in names if n]})


@data_bp.route('/airports', methods=['GET'])
@safe_handler
def get_airports():
    """获取所有机场"""
    data_service.load_all()
    return jsonify({
        'code': 0,
        'data': [a.to_dict() for a in data_service.airports.values()],
        'total': len(data_service.airports),
    })


@data_bp.route('/airport/gate-groups', methods=['GET'])
@safe_handler
def get_airport_gate_groups():
    """获取机场的跑道→登机口组映射

    返回每个机场的跑道分组信息，用于跑道视图展示登机口关联。
    """
    try:
        from ..services.gate_service import _load_gates_config
        cfg = _load_gates_config()
        result = {}
        for airport, data in cfg.items():
            if airport.startswith('_'):
                continue
            groups = []
            for rg in data.get('runway_groups', []):
                g = rg.get('gates', {})
                groups.append({
                    'runway': rg.get('runway'),
                    'name': rg.get('name', ''),
                    'gate_count': g.get('count', 0),
                    'gate_range': f"{g.get('prefix', '')}{g.get('start', 1):02d}~{g.get('prefix', '')}{g.get('start', 1) + g.get('count', 0) - 1:02d}",
                    'taxi_in': rg.get('taxi_in_avg_min', 5),
                    'taxi_out': rg.get('taxi_out_avg_min', 5),
                })
            result[airport] = groups
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)}), 500


@data_bp.route('/airlines', methods=['GET'])
@safe_handler
def get_airlines():
    """获取所有可用的航司列表"""
    from ..services.crew_service import get_airline_list
    return jsonify({'code': 0, 'data': get_airline_list()})
