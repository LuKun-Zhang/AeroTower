"""固定模型的复核状态独立保存，不改权重、不覆盖训练验收结果。"""
from datetime import datetime, timedelta, timezone
from .config import DATA
from .storage import read_json, write_json


def health_path(version):
    return DATA / "health" / f"{version}.json"


def get_health(version):
    return read_json(health_path(version), {})


def scope_enabled(bundle, scope):
    trained = {"delay": bundle.get("delay_enabled", False), "recovery": bundle.get("recovery_enabled", False),
               "routing": bundle.get("routing_report", {}).get("passed", False), "demand": True}
    health = get_health(bundle.get("version", "unversioned"))
    return bool(trained[scope] and health.get("enabled", {}).get(scope, True))


def save_health(version, checks, review_id, mode):
    now = datetime.now(timezone.utc)
    result = {"version": version, "review_id": review_id, "mode": mode,
              "checked_at": now.isoformat(), "next_due": (now+timedelta(days=7)).isoformat(),
              "enabled": {scope: bool(value["passed"]) for scope, value in checks.items()}, "checks": checks}
    write_json(health_path(version), result)
    return result


def review_due(report):
    health = get_health(report["version"])
    due = health.get("next_due")
    if not due:
        due = (datetime.fromisoformat(report["created_at"])+timedelta(days=7)).isoformat()
    return datetime.now(timezone.utc) >= datetime.fromisoformat(due), due
