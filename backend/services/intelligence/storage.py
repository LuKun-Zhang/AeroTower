"""实验记录的原子写入与读取。"""
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
import json
import os
import re
import tempfile
from .config import DATA

LOCK = RLock()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(value, output, ensure_ascii=False, allow_nan=False, indent=2)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def read_json(path, default=None):
    with LOCK:
        if not Path(path).exists():
            return default
        return json.loads(Path(path).read_text(encoding="utf-8"))


def record_path(record_id):
    if not re.fullmatch(r"[a-f0-9]{32}", record_id):
        raise ValueError("实验编号格式错误")
    return DATA / "experiments" / f"{record_id}.json"


def get_record(record_id):
    record = read_json(record_path(record_id))
    if record is None:
        raise FileNotFoundError("实验不存在")
    return record


def list_records():
    folder = DATA / "experiments"
    summaries = []
    for path in folder.glob("*.json"):
        item = read_json(path)
        summaries.append({k: v for k, v in item.items() if k != "result"})
    return sorted(summaries, key=lambda item: item["created_at"], reverse=True)[:100]


def recover_interrupted(folder):
    """单进程服务启动时，让旧作业明确失败，避免页面永久等待。"""
    for path in folder.glob("*.json"):
        record = read_json(path)
        if record.get("status") in ("queued", "running"):
            record.update(status="failed", error="上次服务退出时作业未完成，可按原条件重跑", finished_at=utc_now())
            write_json(path, record)
