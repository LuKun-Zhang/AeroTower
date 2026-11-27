"""固定其他输入，计算单项参考条件对模型输出的影响。"""


def explain_flights(bundle, features, config, probabilities, minutes):
    references = []
    if config["weather"] != "clear":
        references.append(("天气", "晴朗", {"weather_severity": 0}))
    if config["previous_delay"]:
        references.append(("前序延误", "前序不延误", {"previous_delay": 0}))
    if config["capacity"] != 4:
        references.append(("跑道容量", "4条可用跑道", {"capacity": 4}))
    if config["demand_factor"] != 1:
        references.append(("客流", "基准客流", {"traffic": config["flight_count"]}))
    if config["disruption_minutes"]:
        references.append(("已知异常", "没有本次中断", {"disruption_minutes": 0, "event_affected": 0}))
    explanations = [[] for _ in features]
    for name, reference, replacement in references:
        # 不改原始航班、实验条件或已保存特征；对照只供解释，不执行新排班。
        changed = [{**row, **replacement} for row in features]
        reference_probabilities = bundle["classifier"].predict_proba(changed)[:, 1]
        reference_minutes = bundle["regressor"].predict(changed)
        for index, (probability, delay) in enumerate(zip(reference_probabilities, reference_minutes)):
            explanations[index].append({"factor": name, "reference": reference,
                "probability_delta": round(float(probabilities[index]-probability), 4),
                "minutes_delta": round(max(0, float(minutes[index]))-max(0, float(delay)), 1)})
    for values in explanations:
        values.sort(key=lambda row: (row["probability_delta"], row["minutes_delta"]), reverse=True)
    return explanations
