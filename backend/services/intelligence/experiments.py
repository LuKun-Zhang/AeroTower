"""实验提交、独立运行、重跑和结果持久化。"""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
import uuid
from .config import DATA, DEFAULTS, validate_config
from .predictions import predict_flights, recommend
from .scenarios import build_scenario, simulate_delays
from .storage import LOCK, get_record, record_path, recover_interrupted, utc_now, write_json
from .strategy_evaluation import evaluate_strategies
from .original_recovery import original_recovery_outcome

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="aerotower-experiment")
SLOTS = BoundedSemaphore(16)
recover_interrupted(DATA / "experiments")


def execute_experiment(config):
    config, schedule, impact, backups = build_scenario(config)
    rows = simulate_delays(config, schedule)
    predictions = predict_flights(rows, config)
    forecast = {row["flight_id"]: row for row in predictions["flights"]}
    for row in rows:
        row["prediction"] = forecast.get(row["flight_id"])
    paired = [row for row in rows if row["prediction"]]
    predicted = [row for row in paired if row["prediction"]["minutes"] is not None]
    correct = sum((row["prediction"]["probability"] >= 0.5) == row["delayed"] for row in predicted)
    forecast_mae = sum(abs(row["actual_delay"]-row["prediction"]["minutes"]) for row in predicted)/len(predicted) if predicted else None
    baseline_mae = sum(abs(row["actual_delay"]-row["prediction"]["baseline_minutes"]) for row in paired)/len(paired) if paired else None
    outcomes = evaluate_strategies(config, schedule, impact, backups)
    baseline = original_recovery_outcome(config, schedule, impact, backups)
    return {"flights": rows, "prediction": {k: v for k, v in predictions.items() if k != "flights"},
            "recovery": recommend(config, impact, outcomes, baseline),
            "metrics": {"flights": len(rows), "delayed": sum(row["delayed"] for row in rows),
                        "mean_delay": round(sum(row["actual_delay"] for row in rows)/max(len(rows), 1), 2),
                        "prediction_mae": round(forecast_mae, 2) if forecast_mae is not None else None,
                        "baseline_mae": round(baseline_mae, 2) if baseline_mae is not None else None,
                        "prediction_correct": correct, "prediction_total": len(predicted),
                        "prediction_accuracy": correct/len(predicted) if predicted else None},
            "model_version": predictions.get("version"),
            "engine": "原跑道求解器与原五种恢复策略；模拟扰动和代价口径见文档"}


def _run(record):
    try:
        record.update(status="running", started_at=utc_now())
        write_json(record_path(record["id"]), record)
        result = execute_experiment(record["config"])
        record.update(status="completed", finished_at=utc_now(), result=result)
    except Exception as error:
        record.update(status="failed", finished_at=utc_now(), error=str(error))
    finally:
        write_json(record_path(record["id"]), record)
        SLOTS.release()


def submit_experiment(payload, confirmed, request_id=None, parent_id=None):
    if confirmed is not True:
        raise ValueError("请先检查完整表单并明确确认运行")
    config = validate_config(payload)
    identifier = request_id or uuid.uuid4().hex
    path = record_path(identifier)
    with LOCK:
        if path.exists():
            prior = get_record(identifier)
            if prior["config"] != config:
                raise ValueError("重复的请求编号对应了不同条件")
            return prior
        if not SLOTS.acquire(blocking=False):
            raise ValueError("运行队列已满，请等待已有实验结束")
        record = {"id": identifier, "created_at": utc_now(), "status": "queued", "config": config,
                  "config_schema": 2, "parent_id": parent_id, "source": "本系统模拟实验",
                  "defaults_applied": [field for field in DEFAULTS if field not in payload]}
        try:
            write_json(path, record)
            POOL.submit(_run, record.copy())
        except Exception:
            SLOTS.release()
            raise
    return record


def rerun_experiment(identifier):
    previous = get_record(identifier)
    return submit_experiment(previous["config"], True, parent_id=identifier)


def submit_batch(configs):
    validated = [validate_config(value) for value in configs]
    reserved, records = 0, []
    with LOCK:
        try:
            for _ in validated:
                if not SLOTS.acquire(blocking=False):
                    raise ValueError("批量实验所需队列容量不足，请等待已有实验结束")
                reserved += 1
            for config in validated:
                record = {"id": uuid.uuid4().hex, "created_at": utc_now(), "status": "queued",
                          "config": config, "config_schema": 2, "parent_id": None,
                          "source": "本系统模拟实验", "defaults_applied": []}
                write_json(record_path(record["id"]), record)
                records.append(record)
        except Exception:
            for record in records:
                record.update(status="failed", error="批量提交未完成，未运行", finished_at=utc_now())
                write_json(record_path(record["id"]), record)
            for _ in range(reserved):
                SLOTS.release()
            raise
        for record in records:
            POOL.submit(_run, record.copy())
    return records
