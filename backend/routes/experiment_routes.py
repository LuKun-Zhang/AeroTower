"""实验中心 API：创建、列表、详情、删除、导出。"""

import io
import json

from flask import Blueprint, jsonify, request, send_file

from ..services.experiment import store, conditions, artifacts
from ..services.experiment.runner import get_progress
from ..models.experiment import ExperimentError
from .flight_routes import require_user

experiment_bp = Blueprint('experiment', __name__)


def _error(message, status=400, field=None):
    payload = {'code': status, 'msg': message}
    if field:
        payload['field'] = field
    return jsonify(payload), status


@experiment_bp.route('/experiments', methods=['POST'])
@require_user
def create_experiment():
    body = request.get_json(silent=True) or {}
    try:
        cond = conditions.normalize(body.get('conditions') or body)
        record = store.create(request._username, cond,
                              name=body.get('name') or cond.get('name'))
        return jsonify({'code': 0, 'data': record.to_dict()})
    except ExperimentError as exc:
        return _error(exc.message, 400, exc.field)


@experiment_bp.route('/experiments', methods=['GET'])
@require_user
def list_experiments():
    records = store.list_for(request._username)
    rows = []
    for record in records:
        get_progress(record)
        row = record.list_row()
        row['size_bytes'] = store.disk_usage(record.username, record.id)
        rows.append(row)
    return jsonify({'code': 0, 'data': rows})


@experiment_bp.route('/experiments/<exp_id>', methods=['GET'])
@require_user
def get_experiment(exp_id):
    try:
        record = store.load(request._username, exp_id)
    except ValueError as exc:
        return _error(str(exc))
    if not record:
        return _error('实验不存在', 404)
    get_progress(record)
    metrics = artifacts.read_artifact(request._username, exp_id, 'metrics.json', {})
    run = artifacts.read_artifact(request._username, exp_id, 'run.json', {})
    weather = artifacts.read_artifact(request._username, exp_id, 'weather.json', {})
    return jsonify({'code': 0, 'data': {
        'record': record.to_dict(),
        'metrics': metrics,
        'run': run,
        'weather_meta': (weather or {}).get('meta', {}),
        'disk_bytes': store.disk_usage(request._username, exp_id),
    }})


@experiment_bp.route('/experiments/<exp_id>', methods=['DELETE'])
@require_user
def delete_experiment(exp_id):
    try:
        store.delete(request._username, exp_id)
        return jsonify({'code': 0, 'msg': '已删除'})
    except ValueError as exc:
        return _error(str(exc), 409)


@experiment_bp.route('/experiments/<exp_id>/export', methods=['GET'])
@require_user
def export_experiment(exp_id):
    record = store.load(request._username, exp_id)
    if not record:
        return _error('实验不存在', 404)
    metrics = artifacts.read_artifact(request._username, exp_id, 'metrics.json', {})
    if not metrics:
        return _error('实验尚未产出指标', 400)

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '条件'
    ws.append(['字段', '值'])
    for key, value in record.conditions.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        ws.append([key, value])

    ws2 = wb.create_sheet('指标')
    ws2.append(['指标', '值', '口径'])
    definitions = metrics.get('definitions', {})
    for key, value in (metrics.get('values') or {}).items():
        ws2.append([key, value, definitions.get(key, '')])

    ws3 = wb.create_sheet('曲线')
    ws3.append(['分钟', '时间', '在空', '已到达', '延误', '取消', '平均延误'])
    for point in (metrics.get('series') or {}).get('points', []):
        ws3.append([point.get('t'), point.get('time'), point.get('airborne'),
                    point.get('arrived'), point.get('delayed'),
                    point.get('cancelled'), point.get('avg_delay')])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    name = f"experiment_{record.id}.xlsx"
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True, download_name=name,
    )
