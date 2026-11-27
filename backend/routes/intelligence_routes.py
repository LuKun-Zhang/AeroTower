"""实验中心和智能辅助接口。"""
import csv
from functools import wraps
import io
from flask import Blueprint, jsonify, request, Response
from ..services.intelligence.config import AIRPORTS, DEFAULTS, EVENTS, WEATHER, validate_config
from ..services.intelligence.experiments import rerun_experiment, submit_batch, submit_experiment
from ..services.intelligence.jobs import get_job, start_training
from ..services.intelligence.language import language_policy, model_available, parse_description
from ..services.intelligence.live_recovery import live_recommendation
from ..services.intelligence.model_store import current_report
from ..services.intelligence.predictions import predict_flights
from ..services.intelligence.storage import get_record, list_records

intelligence_bp = Blueprint("intelligence", __name__)


def handled(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return jsonify({"code": 0, "data": function(*args, **kwargs)})
        except FileNotFoundError as error:
            return jsonify({"code": -1, "msg": str(error)}), 404
        except (ValueError, TypeError, KeyError) as error:
            return jsonify({"code": -1, "msg": str(error)}), 400
    return wrapper


def body_object():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("请求内容必须是 JSON 对象")
    return body


@intelligence_bp.get("/options")
@handled
def options():
    return {"defaults": DEFAULTS, "airports": AIRPORTS, "weather": WEATHER, "events": EVENTS,
            "language_model_ready": model_available(), "language_policy": language_policy()}


@intelligence_bp.get("/models")
@handled
def model_status():
    return {"report": current_report(), "language_model_ready": model_available(), "language_policy": language_policy()}


@intelligence_bp.post("/training")
@handled
def train():
    body = body_object()
    if body.get("confirmed") is not True:
        raise ValueError("请先确认训练")
    return start_training()


@intelligence_bp.get("/training/<identifier>")
@handled
def training_status(identifier):
    return get_job(identifier)


@intelligence_bp.post("/drafts")
@handled
def draft():
    body = body_object()
    return parse_description(body.get("text"), body.get("use_model"))


@intelligence_bp.get("/experiments")
@handled
def experiments():
    return list_records()


@intelligence_bp.post("/experiments")
@handled
def new_experiment():
    body = body_object()
    return submit_experiment(body.get("config", {}), body.get("confirmed"), body.get("request_id"))


@intelligence_bp.post("/experiments/batch")
@handled
def batch():
    body = body_object()
    configs = body.get("configs")
    if body.get("confirmed") is not True or not isinstance(configs, list) or not 1 <= len(configs) <= 12:
        raise ValueError("请确认 1 到 12 组实验条件")
    return submit_batch(configs)


@intelligence_bp.get("/experiments/<identifier>")
@handled
def experiment(identifier):
    return get_record(identifier)


@intelligence_bp.post("/experiments/<identifier>/rerun")
@handled
def rerun(identifier):
    body = body_object()
    if body.get("confirmed") is not True:
        raise ValueError("请确认重跑")
    return rerun_experiment(identifier)


@intelligence_bp.post("/predictions")
@handled
def predictions():
    body = body_object()
    flights = body.get("flights", [])
    if not isinstance(flights, list) or any(not isinstance(row, dict) for row in flights):
        raise ValueError("航班必须是对象数组")
    return predict_flights(flights, body.get("config", {}))


@intelligence_bp.get("/recovery/<event_id>")
@handled
def recovery(event_id):
    return live_recommendation(event_id)


@intelligence_bp.get("/experiments/<identifier>/export")
def export(identifier):
    try:
        record = get_record(identifier)
        if record["status"] != "completed":
            raise ValueError("实验完成后才能导出")
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["flight_id", "flight_no", "actual_delay_minutes", "predicted_delay_minutes", "delay_probability", "baseline_minutes"])
        for row in record["result"]["flights"]:
            prediction = row.get("prediction") or {}
            writer.writerow([row["flight_id"], row["flight_no"], row["actual_delay"], prediction.get("minutes"), prediction.get("probability"), prediction.get("baseline_minutes")])
        return Response("\ufeff"+buffer.getvalue(), content_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="experiment-{identifier}.csv"'})
    except (ValueError, FileNotFoundError) as error:
        return jsonify({"code": -1, "msg": str(error)}), 400
