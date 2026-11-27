"""复用原飞机排班器，模型只建议选择框中的算法。"""
from copy import deepcopy
from statistics import mean
from ..routing_service import AircraftRoutingService, SICHUAN_AIRLINES_BASES
from .scenarios import build_scenario, sample_configs
from .health import scope_enabled

NAMES = {"bipartite": "二分图/筛选模式链覆盖", "greedy": "贪心算法", "vrp": "均衡分配"}


def routing_features(schedule, fleet, filtered):
    flights = schedule["flights"]
    return {**{f"count_{name}": sum(f.ac_type == name for f in flights) for name in ("A319", "A320", "A321")},
            "flights": len(flights), "fleet": fleet, "filtered": int(filtered),
            "airports": len({f.departure_airport for f in flights}|{f.arrival_airport for f in flights}),
            "types": len({f.ac_type for f in flights}), "chains": len(schedule.get("chains", [])),
            "days": len({f.time_departure[:3] for f in flights}),
            "departure_span": max(f.departure_minutes for f in flights)-min(f.departure_minutes for f in flights) if flights else 0,
            "mean_duration": mean(f.timespan for f in flights) if flights else 0}


def routing_outcomes(schedule, fleet=100, filtered=True):
    if isinstance(fleet, bool) or not isinstance(fleet, int) or not 1 <= fleet <= 100:
        raise ValueError("可用飞机数须为1到100")
    results = []
    for name in NAMES:
        copied = deepcopy(schedule)
        service = AircraftRoutingService()
        if name == "bipartite":
            aircraft = service.solve_chain_coverage(copied.get("chains", []), fleet, 60) if filtered and copied.get("chains") else service.solve_bipartite(copied["flights"], 60)
        elif name == "greedy":
            aircraft = service.solve_greedy_only(copied["flights"], fleet, 60)
        else:
            aircraft = service.solve_vrp(copied["flights"], fleet, 60)
        ids, violations, idle = [], [], 0
        for plane in aircraft:
            jobs = sorted(plane.assigned_flights, key=lambda f: f.departure_minutes)
            ids.extend(f.flight_id for f in jobs)
            if any(f.ac_type != plane.ac_type for f in jobs):
                violations.append("机型不匹配")
            if jobs and (jobs[0].departure_airport not in SICHUAN_AIRLINES_BASES or jobs[-1].arrival_airport not in SICHUAN_AIRLINES_BASES):
                violations.append("任务链不满足基地起止")
            for first, second in zip(jobs, jobs[1:]):
                if not first.can_connect_to(second, 60):
                    violations.append("时间或机场衔接冲突")
                idle += max(0, second.departure_minutes-first.arrival_minutes)
        if len(ids) != len(set(ids)):
            violations.append("重复分配航班")
        if len(aircraft) > fleet:
            violations.append("超过可用飞机数")
        unassigned = len(schedule["flights"])-len(set(ids))
        # 硬约束不通过的整套计划不能执行，不能因表面覆盖率高而获得低成本。
        cost = (len(schedule["flights"]) if violations else unassigned)*10000+len(aircraft)*100+idle*0.05
        results.append({"algorithm": name, "name": NAMES[name], "cost": round(cost, 2),
            "aircraft": len(aircraft), "unassigned": unassigned, "idle_minutes": idle,
            "feasible": not violations, "violations": sorted(set(violations)),
            "solver": "chain_coverage" if name == "bipartite" and filtered else name})
    return results


def routing_samples(count, seed, holdout=False):
    samples = []
    for index, params in enumerate(sample_configs(count, seed, holdout)):
        # 使用原平台支持的基地，扩大测试场景流量与资源紧张程度。
        params["base_airport"] = ["成都", "重庆", "昆明"][index%3]
        _, schedule, _, _ = build_scenario(params)
        fleet, filtered = 4+params["seed"]%25, True
        samples.append((routing_features(schedule, fleet, filtered), routing_outcomes(schedule, fleet, filtered)))
    return samples


def train_routing(train_count=480, test_count=80, seed=20261126):
    from .training import make_estimator
    training = routing_samples(train_count, seed)
    models = {}
    for name in NAMES:
        model = make_estimator()
        # 学习相对默认方案的差值，避免大量共同的未覆盖成本淹没算法之间的差异。
        model.fit([f for f, _ in training], [next(row["cost"] for row in rows if row["algorithm"] == name)-rows[0]["cost"] for _, rows in training])
        models[name] = model
    # 最终场景种子在这次训练前固定，不再重用已经用于排错的早期测试种子。
    report = evaluate_routing(models, routing_samples(test_count, seed+1000000, True))
    extra = [evaluate_routing(models, routing_samples(max(10, test_count//2), seed+offset, True)) for offset in (1100000, 1200000)]
    report.update(train_scenarios=train_count, test_scenarios=test_count, replications=extra,
                  training_seed=seed, validation_seed=seed+1000000,
                  replication_seeds=[seed+1100000, seed+1200000], target="delta")
    report["passed"] = report["passed"] and all(row["passed"] for row in extra)
    return models, report


def predicted_cost(model, features, row, offset):
    # 小规模场景外推可能把代价差估得过低；已知未分配与飞机成本不能被预测抵消。
    floor = row["unassigned"]*10000+row["aircraft"]*100
    return round(max(floor, offset+float(model.predict([features])[0])), 2)


def evaluate_routing(models, samples):
    selected, baseline, raw_costs, oracle, invalid = [], [], [], [], 0
    for features, rows in samples:
        candidates = [row for row in rows if row["feasible"]]
        chosen = min(candidates, key=lambda row: predicted_cost(models[row["algorithm"]], features, row, rows[0]["cost"])) if candidates else rows[0]
        raw_costs.append(chosen["cost"])
        selected.append(min(chosen["cost"], rows[0]["cost"]) if rows[0]["feasible"] else chosen["cost"])
        baseline.append(rows[0]["cost"])
        oracle.append(min(row["cost"] for row in rows if row["feasible"]) if candidates else rows[0]["cost"])
        invalid += int(not rows[0]["feasible"])
    improvement = (mean(baseline)-mean(selected))/max(1, mean(baseline))
    accuracy = mean(abs(value-best) <= 0.01 for value, best in zip(selected, oracle))
    default_accuracy = mean(abs(value-best) <= 0.01 for value, best in zip(baseline, oracle))
    return {"scenarios": len(selected), "baseline_infeasible": invalid, "oracle_cost": mean(oracle),
        "mean_cost": mean(selected), "baseline_cost": mean(baseline), "improvement": improvement,
        "raw_model_cost": mean(raw_costs), "guard": "已计算计划代价高于原默认可行计划时，保留原算法；不读取执行后的结果",
        "optimal_selection_rate": accuracy, "default_optimal_rate": default_accuracy,
        "passed": accuracy >= 0.85 and mean(selected) <= mean(baseline),
        "acceptance": "选中最低计划代价候选至少85%，平均计划代价不高于原默认；不套用恢复策略的2%门槛",
        "baseline": "原界面默认bipartite；筛选模式实际调用链覆盖",
        "cost_definition": "未分配航班×10000 + 使用飞机×100 + 空闲分钟×0.05；硬约束失败的整套方案视作不可执行"}


def recommend_routing(bundle, schedule, fleet, filtered):
    rows = routing_outcomes(schedule, fleet, filtered)
    models = bundle.get("routing", {}) if bundle else {}
    features = routing_features(schedule, fleet, filtered)
    for row in rows:
        model = models.get(row["algorithm"])
        offset = rows[0]["cost"] if bundle and bundle.get("routing_report", {}).get("target") == "delta" else 0
        row["predicted_cost"] = predicted_cost(model, features, row, offset) if model else None
    eligible = [row for row in rows if row["feasible"] and row["predicted_cost"] is not None and row["unassigned"] < len(schedule["flights"])]
    enabled = bool(eligible and filtered and scope_enabled(bundle, "routing"))
    chosen = min(eligible, key=lambda row: row["predicted_cost"]) if enabled else None
    guarded = bool(chosen and rows[0]["feasible"] and chosen["cost"] > rows[0]["cost"])
    if guarded:
        chosen = rows[0]
    return {"enabled": enabled, "recommended": chosen["algorithm"] if chosen else None, "candidates": rows,
        "version": bundle["version"] if bundle else None,
        "guarded": guarded,
        "reason": f"{len(schedule['flights'])}架航班、{fleet}架可用飞机；已筛选任务链，先检查衔接与机型再比较预测代价" if enabled else "请先筛选任务链并训练通过评估的模型；当前仅并列展示原算法结果",
        "execution": "选用建议只修改算法选择框，仍须点击原一键排班按钮执行"}
