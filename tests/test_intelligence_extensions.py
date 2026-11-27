"""验证新增预测的时间隔离、原流程保护和版本化回退。"""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from backend.services.intelligence.demand import evaluate_history
from backend.services.intelligence.health import review_due, save_health, scope_enabled
from backend.services.intelligence.original_recovery import original_recovery_outcome
from backend.services.intelligence.predictions import recommend
from backend.services.intelligence.review_processing import DisturbedClassifier, DisturbedRegressor
from backend.services.intelligence.scenarios import build_scenario
from backend.services.intelligence.strategy_evaluation import evaluate_strategies
from backend.services.recovery_service import RecoveryService
from backend.services.routing_service import AircraftRoutingService
from backend.models.aircraft import Aircraft
from backend.services.intelligence import reviews


class ExtensionTests(unittest.TestCase):
    def test_due_monitor_dispatches_automatic_review_without_sleeping(self):
        with patch.object(reviews, 'STOP') as stop, patch.object(reviews, 'current_report', return_value={'model_schema': 3}), patch.object(
            reviews, 'review_due', return_value=(True, 'past')
        ), patch.object(reviews, 'start_review') as start:
            stop.is_set.side_effect = [False, True]
            reviews._monitor()
        start.assert_called_once_with(automatic=True)

    def test_chain_coverage_cannot_relax_aircraft_type(self):
        _, schedule, _, _ = build_scenario({"flight_count": 12})
        chain = next(chain for chain in schedule["chains"] if chain[0].ac_type == 'A320')
        wrong_plane = Aircraft(1, 'A319', 'C8Y124', tail_no='B-test')
        with patch('backend.services.routing_service._create_aircraft_with_index', return_value=wrong_plane):
            result = AircraftRoutingService().solve_chain_coverage([chain], 1, 60)
        self.assertEqual(result, [])

    def test_original_recovery_calendar_preserves_year_and_month_end(self):
        self.assertEqual(RecoveryService._offset_time((2026, 11, 30, 23, 30), 60), "2026-12-01 00:30")
        self.assertEqual(RecoveryService._offset_time((2026, 12, 31, 23, 30), 60), "2027-01-01 00:30")
        flight = SimpleNamespace(time_departure=(2024, 2, 28, 23, 30), time_arrival=(2024, 2, 29, 1, 30))
        RecoveryService._apply_delay(flight, 60)
        self.assertEqual(flight.time_departure, (2024, 2, 29, 0, 30))
        self.assertEqual(flight.time_arrival, (2024, 2, 29, 2, 30))

    def test_future_demand_labels_cannot_change_recursive_forecast(self):
        first = date(2024, 1, 1)
        history = {"frequency": "day", "rows": [{"date": (first+timedelta(days=i)).isoformat(),
            "passengers": 1000+i*2+(i%7)*20} for i in range(120)]}
        changed = deepcopy(history)
        for row in changed["rows"][-28:]:
            row["passengers"] += 5000
        before, after = evaluate_history(history), evaluate_history(changed)
        self.assertEqual([r["predicted"] for r in before["comparison"]], [r["predicted"] for r in after["comparison"]])
        self.assertNotEqual(before["mae"], after["mae"])

    def test_original_service_execution_does_not_mutate_input(self):
        config, schedule, impact, backups = build_scenario({"flight_count": 12, "disruption_minutes": 400})
        original = deepcopy([vars(f) for f in schedule["flights"]])
        outcome = original_recovery_outcome(config, schedule, impact, backups)
        self.assertTrue(outcome["execution_checked"])
        self.assertEqual(outcome["canceled"], 12)
        self.assertEqual(outcome["cost"], 12*240)
        self.assertEqual(original, [vars(f) for f in schedule["flights"]])

    def test_higher_cost_candidate_keeps_original_plan(self):
        config, schedule, impact, backups = build_scenario({"flight_count": 12, "disruption_minutes": 400})
        baseline = original_recovery_outcome(config, schedule, impact, backups)
        outcomes = [r for r in evaluate_strategies(config, schedule, impact, backups) if r["strategy"] == "time_shift"]
        predictor = SimpleNamespace(predict=lambda x: np.array([1]*len(x)))
        bundle = {"version": "unit-fixture", "recovery_enabled": True,
                  "recovery": {"time_shift": {"cost": predictor, "delay_minutes": predictor, "canceled": predictor}}}
        with patch("backend.services.intelligence.predictions.load_bundle", return_value=bundle):
            result = recommend(config, impact, outcomes, baseline)
        self.assertTrue(result["guarded"])
        self.assertEqual(result["recommended"], "original_flow")

    def test_failed_review_is_version_specific_and_pass_restores_model(self):
        with tempfile.TemporaryDirectory() as temp, patch("backend.services.intelligence.health.DATA", Path(temp)):
            bundle = {"version": "version-a", "delay_enabled": True}
            save_health("version-a", {"delay": {"passed": False}}, "review", "regular")
            self.assertFalse(scope_enabled(bundle, "delay"))
            self.assertTrue(scope_enabled({**bundle, "version": "version-b"}, "delay"))
            save_health("version-a", {"delay": {"passed": True}}, "review2", "regular")
            self.assertTrue(scope_enabled(bundle, "delay"))
            self.assertTrue(review_due({"version": "old", "created_at": "2020-01-01T00:00:00+00:00"})[0])

    def test_fault_injection_preserves_original_predictor(self):
        classifier = SimpleNamespace(predict_proba=lambda x: np.array([[0.1, 0.9]]*len(x)))
        regressor = SimpleNamespace(predict=lambda x: np.array([30]*len(x)))
        self.assertAlmostEqual(DisturbedClassifier(classifier).predict_proba([{}])[0, 1], 0.1)
        self.assertEqual(DisturbedRegressor(regressor).predict([{}])[0], 1030)
        self.assertEqual(regressor.predict([{}])[0], 30)
