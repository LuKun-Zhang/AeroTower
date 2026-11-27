"""每七天复核固定模型，服务重启后补做已到期检查。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, Thread
import os
import uuid
from .config import DATA
from .health import get_health, review_due, save_health
from .model_store import current_report, load_bundle
from .storage import read_json, recover_interrupted, utc_now, write_json

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="model-review")
LOCK = Lock()
ACTIVE = None
STARTED = False
LAST_ERROR = None
STOP = Event()
recover_interrupted(DATA / "reviews")


def start_review(mode="regular", automatic=False):
    global ACTIVE
    if mode not in ("regular", "shift-demo"):
        raise ValueError("复核类型不支持")
    with LOCK:
        if ACTIVE and not ACTIVE.done():
            if automatic:
                return {"status": "running"}
            raise ValueError("已有模型复核正在运行")
        bundle = load_bundle()
        if not bundle or not bundle.get("demand") or not bundle.get("routing"):
            raise ValueError("请先训练完整版本，再复核")
        record = {"id": uuid.uuid4().hex, "status": "queued", "created_at": utc_now(),
                  "mode": mode, "automatic": automatic, "model_version": bundle["version"]}
        write_json(DATA / "reviews" / f"{record['id']}.json", record)
        ACTIVE = POOL.submit(_run, record.copy(), bundle)
        return record


def _run(record, bundle):
    from .review_processing import review_bundle
    path = DATA / "reviews" / f"{record['id']}.json"
    try:
        record.update(status="running")
        write_json(path, record)
        checks, evidence = review_bundle(bundle, record["mode"])
        state = save_health(bundle["version"], checks, record["id"], record["mode"])
        record.update(status="completed", finished_at=utc_now(), health=state, evidence=evidence)
    except Exception as error:
        record.update(status="failed", error=str(error), finished_at=utc_now())
    write_json(path, record)


def review_status(identifier=None):
    if identifier is not None:
        if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
            raise ValueError("复核编号不正确")
        record = read_json(DATA / "reviews" / f"{identifier}.json")
        if not record:
            raise FileNotFoundError("复核不存在")
        return record
    report = current_report()
    history = [read_json(path) for path in (DATA / "reviews").glob("*.json")]
    history.sort(key=lambda row: row["created_at"], reverse=True)
    return {"health": get_health(report["version"]) if report else {},
            "monitor_error": LAST_ERROR,
            "next_due": review_due(report)[1] if report else None, "history": history[:5],
            "interval_days": 7, "service": "服务运行期间检查到期任务；离线期间不运行，重启后补做"}


def _monitor():
    global LAST_ERROR
    while not STOP.is_set():
        try:
            report = current_report()
            if report and report.get("model_schema", 0) >= 3 and review_due(report)[0]:
                start_review(automatic=True)
                LAST_ERROR = None
        except Exception as error:
            LAST_ERROR = str(error)
            print(f"[ModelReview] 到期复核启动失败：{error}", flush=True)
        STOP.wait(60)


def start_monitor():
    global STARTED
    if not STARTED and os.environ.get("AEROTOWER_DISABLE_MONITOR") != "1":
        STARTED = True
        Thread(target=_monitor, daemon=True, name="model-review-monitor").start()
