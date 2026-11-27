"""因素对照必须来自模型重新预测，且不能改变原始数据。"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
import numpy as np
from backend.services.intelligence.config import validate_config
from backend.services.intelligence.explanations import explain_flights
from backend.services.intelligence.features import flight_features


class ExplanationTests(unittest.TestCase):
    def test_reference_preserves_inputs_and_reports_signed_model_changes(self):
        config = validate_config({"weather": "storm", "capacity": 4, "disruption_minutes": 0})
        features = [flight_features({"time_departure": "2026-11-30 09:30"}, config)]
        original = deepcopy(features)
        bundle = {"classifier": SimpleNamespace(predict_proba=lambda rows: np.array([
            [1-row["weather_severity"]/100, row["weather_severity"]/100] for row in rows])),
            "regressor": SimpleNamespace(predict=lambda rows: np.array([row["weather_severity"] for row in rows]))}
        effects = explain_flights(bundle, features, config, np.array([0.7]), np.array([70]))
        self.assertEqual(features, original)
        self.assertEqual(effects[0], [{"factor": "天气", "reference": "晴朗", "probability_delta": 0.7, "minutes_delta": 70.0}])

    def test_empty_references_are_valid(self):
        config = validate_config({"capacity": 4, "disruption_minutes": 0})
        self.assertEqual(explain_flights({}, [{}], config, [0.2], [5]), [[]])
