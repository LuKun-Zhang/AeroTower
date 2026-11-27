"""预测输出与不达标时的明确降级。"""
import math
from .config import validate_config
from .explanations import explain_flights
from .features import flight_features, recovery_features
from .model_store import load_bundle
from .health import scope_enabled


def predict_flights(flights, params):
    if len(flights) > 2000:
        raise ValueError("单次最多预测 2000 架航班")
    config = validate_config(params)
    bundle = load_bundle()
    if not bundle:
        return {"enabled": False, "reason": "尚未训练模型，请在实验中心训练并检查评估结果", "flights": []}
    features = [flight_features(f, config) for f in flights]
    if not features:
        return {"enabled": bundle["delay_enabled"], "flights": []}
    probabilities = bundle["classifier"].predict_proba(features)[:, 1]
    minutes = bundle["regressor"].predict(features)
    enabled = scope_enabled(bundle, "delay") and config["model_enabled"]
    effects = explain_flights(bundle, features, config, probabilities, minutes) if enabled else [[] for _ in flights]
    rows = []
    for flight, probability, delay, explanation in zip(flights, probabilities, minutes, effects):
        reasons = []
        if config["weather"] != "clear":
            reasons.append("当前条件包含恶劣天气")
        if config["previous_delay"]:
            reasons.append(f"已知前序延误 {config['previous_delay']} 分钟")
        if config["capacity"] == 1:
            reasons.append("仅一条可用跑道")
        if config["demand_factor"] > 1:
            reasons.append("当前客流高于基准")
        rows.append({"flight_id": flight.get("flight_id"), "probability": round(float(probability), 4) if enabled else None,
                     "minutes": round(max(0, float(delay)), 1) if enabled else None,
                     "baseline_minutes": round(bundle["baseline_minutes"], 1),
                     "context": reasons or ["当前为表单指定的常规条件"],
                     "effects": explanation,
                     "explanation_type": "单项参考条件的模型敏感性对照，不代表现实因果或资源调整可行性"})
    return {"enabled": enabled, "version": bundle["version"], "flights": rows,
            "scope": "本系统模拟条件；当前未提供的真实天气等信息需在表单确认",
            "reason": None if enabled else ("本次实验关闭模型，展示历史均值作为对照" if not config["model_enabled"] else "离线评估或最近复核未通过，已停用延误模型并显示历史均值")}


def recommend(config, impact, outcomes, baseline=None):
    bundle = load_bundle()
    features = recovery_features(config, impact)
    rows = []
    for outcome in outcomes:
        models = bundle["recovery"].get(outcome["strategy"]) if bundle and scope_enabled(bundle, "recovery") and config.get("model_enabled", True) else None
        # 旧版本只保存总代价模型，仍可读取；新版本分开预测延误和取消数量。
        models = models if isinstance(models, dict) else {"cost": models} if models else {}
        rows.append({key: value for key, value in outcome.items() if key != "changes"})
        for target, field in (("cost", "predicted_cost"), ("delay_minutes", "predicted_delay_minutes"), ("canceled", "predicted_cancellations")):
            score = float(models[target].predict([features])[0]) if models.get(target) else None
            value = max(0, score) if score is not None and math.isfinite(score) else None
            if value is not None and target == "canceled":
                value = min(value, impact.total_impacted_flights)
            rows[-1][field] = round(value, 2) if value is not None else None
    eligible = [row for row in rows if row["feasible"] and row["predicted_cost"] is not None]
    enabled = bool(bundle and scope_enabled(bundle, "recovery") and eligible)
    selected = min(eligible, key=lambda row: row["predicted_cost"]) if enabled else None
    guarded = bool(selected and baseline and baseline["feasible"] and selected["cost"] > baseline["cost"])
    baseline_view = {key: value for key, value in baseline.items() if key != "changes"} if baseline else None
    return {"enabled": enabled, "version": bundle["version"] if bundle else None,
            "recommended": "original_flow" if guarded else selected["strategy"] if selected else None,
            "model_choice": selected["strategy"] if selected else None, "guarded": guarded,
            "original": baseline_view, "candidates": rows,
            "reason": f"{config['event_type']}，受影响 {impact.total_impacted_flights} 架；备份飞机/机组/登机口 {config['backup_aircraft']}/{config['backup_crew']}/{config['backup_gates']}；在通过校验的候选中比较预测代价" if enabled else "模型未启用或留出收益不足，当前只并列展示策略结果",
            "execution": "推荐为辅助信息，执行仍使用原有确认流程"}
