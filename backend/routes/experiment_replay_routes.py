"""实验回放 API：独立引擎、只读三画面数据源。"""

from flask import Blueprint, jsonify, request

from ..services.experiment import replay
from .flight_routes import require_user

replay_bp = Blueprint('experiment_replay', __name__)


def _session(exp_id):
    return replay.get(request._username, exp_id)


def _err(message, status=400):
    return jsonify({'code': status, 'msg': message}), status


@replay_bp.route('/experiments/<exp_id>/replay/init', methods=['POST'])
@require_user
def init(exp_id):
    try:
        s = _session(exp_id)
        return jsonify({'code': 0, 'data': {
            'total_flights': len(s.engine.flights),
            'sim_start': s.engine._min_to_time(s.sim_start),
            'sim_end': s.engine._min_to_time(s.sim_end),
            'current_minutes': s.engine._current_minutes,
            'disruption_applied': len(s.plan),
        }})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/sync', methods=['POST'])
@require_user
def sync(exp_id):
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({'code': 0, 'data': _session(exp_id).sync(body.get('current_minutes', 0))})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/snapshot', methods=['GET'])
@require_user
def snapshot(exp_id):
    try:
        return jsonify({'code': 0, 'data': _session(exp_id).snapshot()})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/paxflow', methods=['GET'])
@require_user
def paxflow(exp_id):
    try:
        return jsonify({'code': 0, 'data': _session(exp_id).paxflow_payload()})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/manifests', methods=['POST'])
@require_user
def manifests(exp_id):
    body = request.get_json(silent=True) or {}
    flight_nos = body.get('flights') or []
    return jsonify({'code': 0, 'data': {
        'date': body.get('date', ''),
        'manifests': [{'flight_no': f, 'pax_ids': []} for f in flight_nos],
    }})


@replay_bp.route('/experiments/<exp_id>/replay/context', methods=['GET'])
@require_user
def context(exp_id):
    try:
        return jsonify({'code': 0, 'data': _session(exp_id).context()})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/weather', methods=['GET'])
@require_user
def weather(exp_id):
    try:
        s = _session(exp_id)
        ap = request.args.get('airport', '')
        all_w = {k: w.to_dict() for k, w in s.engine.weather.get_all_weather().items()}
        if ap:
            return jsonify({'code': 0, 'data': {'current': all_w.get(ap), 'upcoming': []}})
        return jsonify({'code': 0, 'data': all_w})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/weather_disruption', methods=['GET'])
@require_user
def weather_disruption(exp_id):
    try:
        return jsonify({'code': 0, 'data': _session(exp_id).weather_disruption()})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/kpi', methods=['GET'])
@require_user
def kpi(exp_id):
    try:
        return jsonify({'code': 0, 'data': _session(exp_id).snapshot().get('kpi', {})})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/flights', methods=['GET'])
@require_user
def flights(exp_id):
    try:
        s = _session(exp_id)
        return jsonify({'code': 0, 'data': {
            'flights': [fs.to_dict() for fs in s.engine.flights.values()]}})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/events', methods=['GET'])
@require_user
def events(exp_id):
    return jsonify({'code': 0, 'data': {'active': [], 'pending': []}})


@replay_bp.route('/experiments/<exp_id>/replay/events/<int:index>', methods=['DELETE'])
@require_user
def remove_event(exp_id, index):
    return _err('回放模式不支持事件注入', 400)


@replay_bp.route('/experiments/<exp_id>/replay/start', methods=['POST'])
@replay_bp.route('/experiments/<exp_id>/replay/pause', methods=['POST'])
@replay_bp.route('/experiments/<exp_id>/replay/resume', methods=['POST'])
@replay_bp.route('/experiments/<exp_id>/replay/stop', methods=['POST'])
@replay_bp.route('/experiments/<exp_id>/replay/speed', methods=['POST'])
@require_user
def noop(exp_id):
    return jsonify({'code': 0, 'data': {'status': 'replay'}})


@replay_bp.route('/experiments/<exp_id>/replay/jump', methods=['POST'])
@require_user
def jump(exp_id):
    body = request.get_json(silent=True) or {}
    try:
        s = _session(exp_id)
        pct = max(0.0, min(1.0, float(body.get('progress_pct', 0)) / 100.0))
        minutes = s.sim_start + (s.sim_end - s.sim_start) * pct
        return jsonify({'code': 0, 'data': s.sync(minutes)})
    except ValueError as exc:
        return _err(str(exc), 404)


@replay_bp.route('/experiments/<exp_id>/replay/step', methods=['POST'])
@require_user
def step(exp_id):
    try:
        s = _session(exp_id)
        return jsonify({'code': 0, 'data': s.sync(s.engine._current_minutes + 1)})
    except ValueError as exc:
        return _err(str(exc), 404)
