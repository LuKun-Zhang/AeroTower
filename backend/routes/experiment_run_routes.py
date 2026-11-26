"""实验运行 API：启动、进度、重跑。"""

from flask import Blueprint, jsonify, request

from ..services.experiment import store
from ..services.experiment.runner import start, rerun, get_progress, BusyError
from .flight_routes import require_user

run_bp = Blueprint('experiment_run', __name__)


@run_bp.route('/experiments/<exp_id>/run', methods=['POST'])
@require_user
def run_experiment(exp_id):
    try:
        start(request._username, exp_id)
        return jsonify({'code': 0, 'msg': '已启动'})
    except BusyError as exc:
        return jsonify({'code': 409, 'msg': str(exc)}), 409
    except ValueError as exc:
        return jsonify({'code': 400, 'msg': str(exc)}), 400


@run_bp.route('/experiments/<exp_id>/progress', methods=['GET'])
@require_user
def progress(exp_id):
    record = store.load(request._username, exp_id)
    if not record:
        return jsonify({'code': 404, 'msg': '实验不存在'}), 404
    return jsonify({'code': 0, 'data': get_progress(record)})


@run_bp.route('/experiments/<exp_id>/rerun', methods=['POST'])
@require_user
def rerun_experiment(exp_id):
    try:
        record = rerun(request._username, exp_id)
        return jsonify({'code': 0, 'data': record.to_dict()})
    except BusyError as exc:
        return jsonify({'code': 409, 'msg': str(exc)}), 409
    except ValueError as exc:
        return jsonify({'code': 400, 'msg': str(exc)}), 400
