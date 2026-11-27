"""在新条件上检查已保存模型，不重新拟合，不接触活动排班。"""
from copy import copy
from datetime import datetime, timezone
from statistics import mean
import numpy as np
from .demand import project
from .demand_history import simulated_history
from .routing import evaluate_routing, routing_samples


class DisturbedClassifier:
    def __init__(self, original):
        self.original = original

    def predict_proba(self, rows):
        return self.original.predict_proba(rows)[:, ::-1]


class DisturbedRegressor:
    def __init__(self, original):
        self.original = original

    def predict(self, rows):
        return self.original.predict(rows)+1000


def review_demand(bundle):
    reports = []
    for name, selected in bundle.get("demand", {}).items():
        if selected["history"]["frequency"] != "day":
            continue
        future = simulated_history(name, 28)["rows"][-28:]
        rows = project(selected["model"], selected["history"], 28)
        mae = mean(abs(row["predicted"]-actual["passengers"]) for row, actual in zip(rows, future))
        baseline = mean(abs(row["baseline"]-actual["passengers"]) for row, actual in zip(rows, future))
        reports.append({"source": name, "mae": mae, "baseline_mae": baseline, "passed": mae < baseline*0.98})
    return {"passed": bool(reports and all(row["passed"] for row in reports)), "sources": reports,
            "scope": "模型历史末日之后28天新模拟日客流，固定权重递归预测；公开月数据无新增观测，不作为新增数据复核"}


def review_routing(bundle, seed):
    return evaluate_routing(bundle["routing"], routing_samples(20, seed, True))


def review_bundle(bundle, mode="regular"):
    from .scenarios import sample_configs
    from .training import evaluate_delay, evaluate_recovery, prepare_samples
    seed = datetime.now(timezone.utc).date().toordinal()+50000000
    flights, recovery = prepare_samples(sample_configs(30, seed, True))
    candidate = copy(bundle)
    if mode == "shift-demo":
        candidate.update(classifier=DisturbedClassifier(bundle["classifier"]), regressor=DisturbedRegressor(bundle["regressor"]))
    delay = evaluate_delay(candidate["classifier"], candidate["regressor"], flights,
                           bundle["baseline_probability"], bundle["baseline_minutes"])
    return {"delay": delay, "recovery": evaluate_recovery(bundle["recovery"], recovery),
            "routing": review_routing(bundle, seed+1000), "demand": review_demand(bundle)}, {
            "seed": seed, "mode": mode, "model_version": bundle["version"], "fitted": False,
            "description": "人为反转概率并偏移预测，验证失准回退；未修改保存的模型" if mode == "shift-demo" else "新场景检查固定权重；不重训、不改变已有实验标签"}
