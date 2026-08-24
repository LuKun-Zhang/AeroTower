"""飞机情况调整 API Blueprint — /api/aircraft/* 路由

提供单机指标调整：更新 aircraft_index.json 中该飞机的各项指标，
用模型口径重新计算综合质量指数，并清除排班缓存使下次排班按新指数重新匹配。
"""

import json
import os

from flask import Blueprint, jsonify, request

from ..models.aircraft import Aircraft
from ..services.aircraft_types import type_layout
from ..state import set_flight_aircraft_cache, set_aircraft_chains_cache

aircraft_bp = Blueprint('aircraft', __name__)

_INDEX_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'aircraft_index.json'
))

# 允许调整的指标字段（与 aircraft_index.json / Aircraft 模型保持一致）
_EDITABLE_FIELDS = [
    'age_years',           # 机龄（年）
    'total_flight_hours',  # 总飞行小时
    'maintenance_days',    # 年维护天数
    'cost_per_hour',       # 小时成本
    'fuel_efficiency',     # 燃油效率 0~1
    'last_overhaul',       # 最近大修日期（字符串）
    'on_time_rate',        # 准点率 0~1
    'cycles',              # 循环次数
]


@aircraft_bp.route('/aircraft/update', methods=['POST'])
def update_aircraft():
    """POST /api/aircraft/update
    请求体: { tail_no, age_years?, total_flight_hours?, ..., on_time_rate? }
    - 更新 aircraft_index.json 中对应飞机的指标
    - 按 Aircraft._compute_quality_index 重算综合指数与日航班上限
    - 清除排班缓存，下次排班按新指数重新匹配
    返回: { code, data: { tail_no, quality_index, max_daily_flights } }
    """
    body = request.get_json(silent=True) or {}
    tail_no = (body.get('tail_no') or '').strip()
    if not tail_no:
        return jsonify({'code': 1, 'msg': '缺少 tail_no 参数'}), 400

    try:
        with open(_INDEX_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'读取机队数据失败: {e}'}), 500

    target = next((item for item in data if item.get('tail_no') == tail_no), None)
    if target is None:
        return jsonify({'code': 1, 'msg': f'未找到飞机 {tail_no}'}), 404

    # 更新传入的指标字段
    changed = []
    for k in _EDITABLE_FIELDS:
        if k in body and body[k] is not None and body[k] != '':
            v = body[k]
            target[k] = str(v) if k == 'last_overhaul' else float(v)
            changed.append(k)
    if not changed:
        return jsonify({'code': 1, 'msg': '没有可更新的指标字段'}), 400

    try:
        with open(_INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'写入机队数据失败: {e}'}), 500

    # 按模型口径重算指数
    ac = Aircraft(
        ac_id=1,
        ac_type=target.get('ac_type', 'A319'),
        layout=type_layout(target.get('ac_type', 'A319')),
        tail_no=tail_no,
        base='',
        age_years=target['age_years'],
        total_flight_hours=target['total_flight_hours'],
        maintenance_days=target['maintenance_days'],
        cost_per_hour=target['cost_per_hour'],
        fuel_efficiency=target['fuel_efficiency'],
        last_overhaul=target['last_overhaul'],
        on_time_rate=target['on_time_rate'],
        cycles=target['cycles'],
    )

    # 清除排班缓存，让下一次排班按新指数重新匹配
    set_flight_aircraft_cache(None)
    set_aircraft_chains_cache(None)

    return jsonify({
        'code': 0,
        'data': {
            'tail_no': tail_no,
            'quality_index': ac.quality_index,
            'max_daily_flights': ac.max_daily_flights,
            'updated_fields': changed,
        },
    })
