"""防止草稿执行、日期和实验重试等真实流程发生回归。"""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
import numpy as np
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory()
os.environ["AEROTOWER_INTELLIGENCE_DATA"] = TEMP.name
os.environ["AEROTOWER_DISABLE_LLM"] = "1"
from backend.app import app
from backend.models.abnormal_event import AbnormalEvent
from backend.services.intelligence.config import validate_config
from backend.services.intelligence.experiments import SLOTS
from backend.services.intelligence.features import flight_features
from backend.services.intelligence.live_recovery import live_recommendation
from backend.services.intelligence.predictions import predict_flights
from backend.services.intelligence.language_rules import validate_draft
from backend.services.intelligence.scenarios import build_scenario, simulate_delays
from backend.services.intelligence.storage import recover_interrupted, write_json


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def completed(self, identifier):
        for _ in range(100):
            value = self.client.get(f"/api/intelligence/experiments/{identifier}").json["data"]
            if value["status"] == "completed":
                return value
            if value["status"] == "failed":
                self.fail(value.get("error"))
            time.sleep(0.03)
        self.fail("实验没有完成")

    def test_draft_is_grounded_and_does_not_run(self):
        before = self.client.get("/api/intelligence/experiments").json["data"]
        reply = self.client.post("/api/intelligence/drafts", json={"text": "成都基地，客流涨两成，加一场雷暴"})
        self.assertEqual(reply.status_code, 200)
        data = reply.json["data"]
        self.assertEqual(data["fields"], {"base_airport": "成都", "demand_factor": 1.2, "weather": "storm"})
        self.assertTrue(data["requires_confirmation"])
        self.assertEqual(self.client.get("/api/intelligence/experiments").json["data"], before)

    def test_hallucinated_fields_and_negation(self):
        result = validate_draft("广州基地，不要雷暴", {"weather": "storm", "backup_aircraft": 8})
        self.assertEqual(result["fields"], {"base_airport": "广州"})
        self.assertEqual(set(result["rejected_fields"]), {"weather", "backup_aircraft"})

    def test_confirmation_and_payload_validation(self):
        for body in ({"config": {}}, {"config": {}, "confirmed": "true"}, ["invalid"]):
            reply = self.client.post("/api/intelligence/experiments", json=body)
            self.assertEqual(reply.status_code, 400)
        for config in ({"flight_count": True}, {"capacity": 0}, {"seed": float("nan")}, {"unknown": 1}):
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_snapshot_retry_rerun_export(self):
        identifier = uuid.uuid4().hex
        body = {"config": {"flight_count": 12}, "confirmed": True, "request_id": identifier}
        first = self.client.post("/api/intelligence/experiments", json=body)
        self.assertEqual(first.status_code, 200)
        original = self.completed(identifier)
        self.assertEqual(self.client.post("/api/intelligence/experiments", json=body).json["data"]["id"], identifier)
        changed = {**body, "config": {"flight_count": 14}}
        self.assertEqual(self.client.post("/api/intelligence/experiments", json=changed).status_code, 400)
        response = self.client.post(f"/api/intelligence/experiments/{identifier}/rerun", json={"confirmed": True})
        repeated = self.completed(response.json["data"]["id"])
        self.assertEqual(original["config"], repeated["config"])
        self.assertEqual(original["result"], repeated["result"])
        self.assertEqual(repeated["parent_id"], identifier)
        exported = self.client.get(f"/api/intelligence/experiments/{identifier}/export")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("actual_delay_minutes", exported.text)

    def test_batch_refuses_without_partial_submission(self):
        acquired = 0
        before = self.client.get("/api/intelligence/experiments").json["data"]
        try:
            for _ in range(15):
                self.assertTrue(SLOTS.acquire(blocking=False))
                acquired += 1
            response = self.client.post("/api/intelligence/experiments/batch", json={"configs": [{}, {}], "confirmed": True})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.get("/api/intelligence/experiments").json["data"], before)
        finally:
            for _ in range(acquired):
                SLOTS.release()

    def test_cross_month_dates_and_odd_daily_count(self):
        config, schedule, _, _ = build_scenario({"flight_count": 9, "days": 7, "start_date": "2026-11-30"})
        rows = simulate_delays(config, schedule)
        self.assertEqual(len(rows), 63)
        self.assertEqual(len({row["time_departure"][:10] for row in rows}), 7)
        self.assertTrue(all(row["actual_delay"] >= 0 for row in rows))
        self.assertEqual(schedule["flights"][0].arrival_minutes-schedule["flights"][0].departure_minutes,
                         schedule["flights"][0].timespan)

    def test_interrupted_job_can_be_identified(self):
        folder = Path(TEMP.name) / "interrupted"
        path = folder / "record.json"
        write_json(path, {"status": "running"})
        recover_interrupted(folder)
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(value["status"], "failed")

    def test_original_flight_array_time_is_supported(self):
        config = validate_config({})
        array = flight_features({"time_departure": [2026, 11, 30, 9, 30]}, config)
        string = flight_features({"time_departure": "2026-11-30 09:30"}, config)
        self.assertEqual(array, string)

    def test_model_switch_preserves_conditions_and_simulated_outcome(self):
        config, schedule, _, _ = build_scenario({"model_enabled": True})
        disabled, same_schedule, _, _ = build_scenario({"model_enabled": False})
        rows = simulate_delays(config, schedule)
        self.assertEqual(rows, simulate_delays(disabled, same_schedule))
        bundle = {"delay_enabled": True, "version": "fixture", "baseline_minutes": 23,
                  "classifier": SimpleNamespace(predict_proba=lambda x: np.array([[0.2, 0.8]]*len(x))),
                  "regressor": SimpleNamespace(predict=lambda x: np.array([57]*len(x)))}
        with patch("backend.services.intelligence.predictions.load_bundle", return_value=bundle):
            enabled = predict_flights(rows, config)
            control = predict_flights(rows, disabled)
        self.assertTrue(enabled["enabled"])
        self.assertEqual(enabled["flights"][0]["minutes"], 57)
        self.assertFalse(control["enabled"])
        self.assertIsNone(control["flights"][0]["minutes"])
        self.assertEqual(control["flights"][0]["baseline_minutes"], 23)

    def test_live_enriched_report_does_not_change_schedule(self):
        _, schedule, impact, _ = build_scenario({"flight_count": 12})
        report = impact.to_dict()
        report["direct_impacted_flights"] = [{"flight_id": fid, "flight_no": "显示用"} for fid in impact.direct_impacted_flights]
        event = AbnormalEvent("fixture", "airport_closure", "接口适配测试", affected_airports=["成都"],
            affected_flights=impact.direct_impacted_flights, delay_minutes=60,
            start_time="2026-11-26 07:00", end_time="2026-11-26 08:00")
        event.impact_report = report
        original = deepcopy([vars(flight) for flight in schedule["flights"]])
        original_report = deepcopy(report)
        with patch("backend.routes.anomaly_routes._get_schedule", return_value=schedule), patch(
            "backend.services.intelligence.live_recovery.anomaly_service.get_event", return_value=event
        ):
            result = live_recommendation("fixture")
        self.assertGreaterEqual(len(result["candidates"]), 2)
        self.assertEqual(original, [vars(flight) for flight in schedule["flights"]])
        self.assertEqual(original_report, report)


if __name__ == "__main__":
    unittest.main()
