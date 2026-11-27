"""按时间先后留出，离线训练后使用固定版本进行客流预测。"""
from datetime import date, timedelta
import math
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .config import AIRPORTS
from .demand_history import public_history, simulated_history
from .health import scope_enabled


def advance(day, frequency):
    if frequency == "day":
        return day+timedelta(days=1)
    return date(day.year+(day.month == 12), day.month%12+1, 1)


def demand_features(values, day, frequency):
    lags = [1, 7, 14, 28] if frequency == "day" else [1, 12]
    period = 7 if frequency == "day" else 12
    phase = day.weekday() if frequency == "day" else day.month-1
    annual = day.timetuple().tm_yday/365.25
    return [math.log1p(values[-lag]) for lag in lags]+[len(values)/365,
        math.sin(2*math.pi*annual), math.cos(2*math.pi*annual)]+[float(phase == i) for i in range(period)]


def fit_history(history):
    rows, frequency = history["rows"], history["frequency"]
    warmup = 28 if frequency == "day" else 12
    values = [row["passengers"] for row in rows]
    features = [demand_features(values[:index], date.fromisoformat(rows[index]["date"]), frequency)
                for index in range(warmup, len(rows))]
    model = make_pipeline(StandardScaler(), Ridge(alpha=0.1))
    model.fit(features, np.log1p(values[warmup:]))
    return model


def project(model, history, count):
    values = [row["passengers"] for row in history["rows"]]
    frequency = history["frequency"]
    day = date.fromisoformat(history["rows"][-1]["date"])
    period = 7 if frequency == "day" else 12
    repeated = values[-period:]
    rows = []
    for index in range(count):
        day = advance(day, frequency)
        estimate = float(np.expm1(model.predict([demand_features(values, day, frequency)])[0]))
        if not math.isfinite(estimate) or estimate > 100000000:
            raise ValueError("客流预测超出可解释范围，请复核模型")
        estimate = max(0, estimate)
        rows.append({"date": day.isoformat(), "predicted": round(estimate), "baseline": round(repeated[index%period])})
        values.append(estimate)
    return rows


def evaluate_history(history):
    holdout = 28 if history["frequency"] == "day" else 24
    train = {**history, "rows": history["rows"][:-holdout]}
    forecast = project(fit_history(train), train, holdout)
    truth = history["rows"][-holdout:]
    mae = sum(abs(row["predicted"]-actual["passengers"]) for row, actual in zip(forecast, truth))/holdout
    baseline = sum(abs(row["baseline"]-actual["passengers"]) for row, actual in zip(forecast, truth))/holdout
    return {"mae": round(mae, 2), "baseline_mae": round(baseline, 2), "holdout": holdout,
            "passed": mae < baseline*0.98, "split": "时间尾部连续留出，递归预测期间不读取真实未来客流",
            "comparison": [{**row, "actual": actual["passengers"]} for row, actual in zip(forecast, truth)]}


def train_demand():
    models, reports = {}, {}
    sources = {airport: simulated_history(airport) for airport in AIRPORTS}
    public = public_history()
    if public:
        sources["公开月客流"] = public
    for name, history in sources.items():
        report = evaluate_history(history)
        models[name] = {"model": fit_history(history), "history": history, "passed": report["passed"]}
        reports[name] = {**report, "source": history["source"], "rows": len(history["rows"])}
    return models, reports


def forecast_demand(bundle, source, horizon=7, start_date=None):
    if source not in bundle.get("demand", {}):
        raise ValueError("当前模型没有此来源的客流模型，请先训练完整版本")
    selected = bundle["demand"][source]
    history = selected["history"]
    maximum = 28 if history["frequency"] == "day" else 12
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= maximum:
        raise ValueError(f"预测跨度必须为1到{maximum}")
    offset = 0
    if start_date and history["frequency"] == "day":
        first = date.fromisoformat(history["rows"][-1]["date"])+timedelta(days=1)
        offset = (date.fromisoformat(start_date)-first).days
        if not 0 <= offset <= 14:
            raise ValueError("预测开始日须在固定历史末日之后的14天内，超出范围请更新历史并重训")
    rows = project(selected["model"], history, horizon+offset)[offset:]
    enabled = selected["passed"] and scope_enabled(bundle, "demand")
    for row in rows:
        row["used"] = row["predicted"] if enabled else row["baseline"]
    period = 7 if history["frequency"] == "day" else 12
    reference = sum(row["passengers"] for row in history["rows"][-period:])/period
    return {"source": source, "description": history["source"], "frequency": history["frequency"],
            "version": bundle["version"], "enabled": enabled, "forecast": rows,
            "history": history["rows"][-90:], "total": sum(row["used"] for row in rows),
            "factor": round(sum(row["used"] for row in rows)/len(rows)/reference, 3),
            "evaluation": bundle["demand_reports"][source],
            "method": "固定版本客流模型" if enabled else "模型留出未优于对照，使用上周/上年同期值"}
