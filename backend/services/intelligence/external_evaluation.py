"""用公开真实航班检查同一已保存模型的跨域表现。"""
import csv
from datetime import datetime
import hashlib
import math
from sklearn.metrics import mean_absolute_error, roc_auc_score
from .config import DEFAULTS, MODELS
from .features import flight_features
from .model_store import load_bundle
from .storage import read_json, write_json


def evaluate_external(path, stride=17):
    bundle = load_bundle()
    if not bundle:
        raise ValueError("先训练本系统模型，再进行独立检查")
    report = read_json(MODELS / bundle["version"] / "evaluation.json")
    features, targets, historical = [], [], []
    missing = 0
    with path.open(encoding="utf-8", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream)):
            try:
                delay = float(row["dep_delay"])
                hour, minute = int(row["hour"]), int(row["minute"])
                if not math.isfinite(delay):
                    raise ValueError("缺少实际延误")
            except (ValueError, TypeError):
                missing += 1
                continue
            if int(row["month"]) <= 9:
                historical.append(max(0, delay))
                continue
            if index % stride:
                continue
            value = {"time_departure": datetime(int(row["year"]), int(row["month"]), int(row["day"]), hour, minute).isoformat(),
                     "timespan": float(row["distance"])/8+30,
                     "departure_airport": row["origin"], "arrival_airport": row["dest"]}
            params = {**DEFAULTS, "disruption_minutes": 0}
            features.append(flight_features(value, params))
            targets.append(max(0, delay))
    probabilities = bundle["classifier"].predict_proba(features)[:, 1]
    prediction = bundle["regressor"].predict(features).clip(min=0)
    truth = [value > 15 for value in targets]
    auc = float(roc_auc_score(truth, probabilities))
    mae = float(mean_absolute_error(targets, prediction))
    historical_mean = sum(historical)/len(historical)
    baseline_mae = float(mean_absolute_error(targets, [historical_mean]*len(targets)))
    passed = auc >= 0.53 and mae < baseline_mae * 0.95
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    result = {"dataset": "nycflights13 / NYC 2013，原始来源 BTS", "rows": len(targets),
              "missing_rows_skipped": missing, "sampling": f"10–12月按原始顺序每 {stride} 条取一条，所有真实数据均不参与模拟模型训练",
              "baseline_definition": "用1–9月非负延误的均值预测10–12月，历史与测试按月份分开",
              "baseline_minutes": historical_mean,
              "auc": auc, "mae_minutes": mae, "baseline_mae_minutes": baseline_mae, "passed": passed,
              "model_version": report["version"], "sha256": digest,
              "source": "https://nycflights13.tidyverse.org/reference/flights.html",
              "csv_source": "https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/nycflights13/flights.csv",
              "mapping": "使用计划起飞时间、机场和已知距离；航程按距离粗估。缺失天气/容量/前序状态等用明确的常规参考条件，未使用实际到达时间或实际飞行时长",
              "conclusion": "仅能说明当前映射下的跨域检查，真实天气等字段缺失，实际部署效果尚不能确认" if passed else "真实域检查未达通过线，当前模型仅用于本系统模拟实验，禁止宣称真实航班预测有效"}
    report["external"] = result
    write_json(MODELS / report["version"] / "evaluation.json", report)
    return result
