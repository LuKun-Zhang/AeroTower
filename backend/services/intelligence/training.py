"""按完整场景隔离训练与留出评估，训练轻量预测模型。"""
from statistics import mean
from time import perf_counter
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from .features import flight_features, recovery_features
from .model_store import save_bundle
from .scenarios import build_scenario, sample_configs, simulate_delays
from .strategy_evaluation import evaluate_strategies
from .original_recovery import original_recovery_outcome


def prepare_samples(configs):
    flights, recovery = [], []
    for params in configs:
        config, schedule, impact, backups = build_scenario(params)
        for row in simulate_delays(config, schedule):
            flights.append((flight_features(row, config), row["actual_delay"]))
        outcomes = [value for value in evaluate_strategies(config, schedule, impact, backups) if value["feasible"]]
        baseline = original_recovery_outcome(config, schedule, impact, backups)
        recovery.append((recovery_features(config, impact), outcomes, baseline))
    return flights, recovery


def make_estimator(classification=False):
    cls = HistGradientBoostingClassifier if classification else HistGradientBoostingRegressor
    return make_pipeline(DictVectorizer(sparse=False), cls(max_iter=100, max_leaf_nodes=15,
                          min_samples_leaf=15, l2_regularization=1, early_stopping=False, random_state=42))


def evaluate_delay(classifier, regressor, test, baseline_probability, baseline_minutes):
    x, y = zip(*test)
    truth = np.asarray(y) > 15
    probabilities = classifier.predict_proba(list(x))[:, 1]
    prediction = np.maximum(0, regressor.predict(list(x)))
    auc = float(roc_auc_score(truth, probabilities)) if len(set(truth)) == 2 else None
    mae = float(mean_absolute_error(y, prediction))
    baseline_mae = float(mean_absolute_error(y, [baseline_minutes]*len(y)))
    return {"rows": len(y), "delay_rate": float(np.mean(truth)), "auc": auc,
            "accuracy": float(np.mean((probabilities >= 0.5) == truth)),
            "baseline_accuracy": float(np.mean((baseline_probability >= 0.5) == truth)),
            "baseline_auc": 0.5 if auc is not None else None, "mae_minutes": mae,
            "baseline_mae_minutes": baseline_mae, "brier": float(brier_score_loss(truth, probabilities)),
            "baseline_brier": float(brier_score_loss(truth, [baseline_probability]*len(y))),
            "passed": bool(auc is not None and auc >= 0.53 and mae < baseline_mae * 0.95)}


def train_recovery(samples):
    by_strategy = {}
    for features, outcomes, _ in samples:
        for outcome in outcomes:
            by_strategy.setdefault(outcome["strategy"], []).append((features, outcome))
    models = {}
    for name, values in by_strategy.items():
        if len(values) >= 20:
            models[name] = {}
            for target in ("cost", "delay_minutes", "canceled"):
                estimator = make_estimator()
                estimator.fit([row[0] for row in values], [row[1][target] for row in values])
                models[name][target] = estimator
    return models


def evaluate_recovery(models, samples):
    selected_costs, baseline_costs, oracle_costs, raw_costs = [], [], [], []
    guarded, original_infeasible = 0, 0
    for features, outcomes, baseline in samples:
        eligible = [value for value in outcomes if value["strategy"] in models]
        if not eligible:
            continue
        chosen = min(eligible, key=lambda value: models[value["strategy"]]["cost"].predict([features])[0])
        raw_costs.append(chosen["cost"])
        keep_original = baseline["feasible"] and chosen["cost"] > baseline["cost"]
        guarded += int(keep_original)
        original_infeasible += int(not baseline["feasible"])
        selected_costs.append(baseline["cost"] if keep_original else chosen["cost"])
        baseline_costs.append(baseline["cost"])
        oracle_costs.append(min([value["cost"] for value in outcomes]+[baseline["cost"]]))
    if not selected_costs:
        return {"passed": False, "reason": "留出场景缺少可评估候选"}
    baseline, actual = mean(baseline_costs), mean(selected_costs)
    improvement = (baseline-actual) / max(baseline, 1)
    return {"scenarios": len(selected_costs), "mean_cost": actual, "baseline_cost": baseline,
            "raw_model_cost": mean(raw_costs), "guarded": guarded, "baseline_infeasible": original_infeasible,
            "oracle_cost": mean(oracle_costs), "improvement": improvement,
            "passed": improvement >= 0.02, "cost_definition": "延误分钟 + 240×取消数 + 8×资源变更数",
            "baseline_definition": "同一条件下调用原RecoveryService生成与执行，飞机排除按原链覆盖算法重排",
            "guard": "候选已知计划代价高于原可行计划时保留原方案；不读取未来运行标签"}


def train_models(train_count=180, test_count=60, seed=20261126):
    started = perf_counter()
    train_configs = sample_configs(train_count, seed)
    test_configs = sample_configs(test_count, seed+100000, holdout=True)
    train, recovery_train = prepare_samples(train_configs)
    test, recovery_test = prepare_samples(test_configs)
    x, y = zip(*train)
    classifier, regressor = make_estimator(True), make_estimator()
    classifier.fit(list(x), np.asarray(y) > 15)
    regressor.fit(list(x), y)
    recovery_models = train_recovery(recovery_train)
    delay_report = evaluate_delay(classifier, regressor, test, mean(value > 15 for value in y), mean(y))
    recovery_report = evaluate_recovery(recovery_models, recovery_test)
    replications = []
    extra_configs = []
    # 使用预先固定的另外两组种子检查收益稳定性，不根据结果挑选种子。
    for offset in (200000, 300000):
        params = sample_configs(max(10, test_count//2), seed+offset, holdout=True)
        extra_flights, extra_recovery = prepare_samples(params)
        extra_configs.append(params)
        replications.append({"seed": seed+offset,
            "delay": evaluate_delay(classifier, regressor, extra_flights, mean(value > 15 for value in y), mean(y)),
            "recovery": evaluate_recovery(recovery_models, extra_recovery)})
    delay_report["passed"] = delay_report["passed"] and all(row["delay"]["passed"] for row in replications)
    recovery_report["passed"] = recovery_report["passed"] and all(row["recovery"]["passed"] for row in replications)
    from .demand import train_demand
    from .routing import train_routing
    demand_models, demand_reports = train_demand()
    routing_models, routing_report = train_routing(seed=seed)
    bundle = {"classifier": classifier, "regressor": regressor, "recovery": recovery_models,
              "delay_enabled": delay_report["passed"], "recovery_enabled": recovery_report["passed"],
              "baseline_minutes": mean(y), "baseline_probability": mean(value > 15 for value in y)}
    bundle.update(demand=demand_models, demand_reports=demand_reports, routing=routing_models, routing_report=routing_report)
    report = {"model_schema": 3, "scope": "本系统的模拟条件，真实航班域需独立检查", "seed": seed,
              "train_scenarios": train_count, "test_scenarios": test_count, "train_rows": len(train),
              "split": "按场景隔离；测试基地与训练基地不同，航线目的地可能重合；测试流量及异常强度范围更宽",
              "delay": delay_report, "recovery": recovery_report, "replications": replications,
              "demand": demand_reports, "routing": routing_report,
              "duration_seconds": round(perf_counter()-started, 2),
              "acceptance": {"delay": "AUC≥0.53 且 MAE 比训练均值预测降低至少5%",
                             "recovery": "同场景原恢复服务生成/执行基线，平均代价降低至少2%，两组附加检查也通过",
                             "routing": "最低计划代价选择命中至少85%，保护后平均代价不高于原默认；不宣称必须大幅改善",
                             "demand": "时间尾部留出，误差比同期值对照降低至少2%"}}
    return save_bundle(bundle, report, {"training": train_configs, "holdout": test_configs, "replications": extra_configs})
