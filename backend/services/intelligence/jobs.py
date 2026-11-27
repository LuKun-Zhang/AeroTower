"""训练作业的有界后台执行与状态查询。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import uuid
from .config import DATA, ROOT
from .storage import read_json, recover_interrupted, utc_now, write_json

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aerotower-training")
LOCK = Lock()
ACTIVE = None
recover_interrupted(DATA / "jobs")


def start_training():
    global ACTIVE
    with LOCK:
        if ACTIVE and not ACTIVE.done():
            raise ValueError("已有训练正在运行，请等待完成")
        identifier = uuid.uuid4().hex
        path = DATA / "jobs" / f"{identifier}.json"
        initial = {"id": identifier, "status": "queued", "created_at": utc_now()}
        write_json(path, initial)
        ACTIVE = POOL.submit(_train, path, initial)
        return initial


def _train(path, record):
    from .training import train_models
    try:
        record.update(status="running")
        write_json(path, record)
        report = train_models()
        dataset = ROOT / ".artifacts" / "downloads" / "nyc-flights.csv"
        if dataset.exists():
            from .external_evaluation import evaluate_external
            report["external"] = evaluate_external(dataset)
        record.update(report=report, status="completed", finished_at=utc_now())
    except Exception as error:
        record.update(status="failed", error=str(error), finished_at=utc_now())
    write_json(path, record)


def get_job(identifier):
    if len(identifier) != 32 or any(c not in "0123456789abcdef" for c in identifier):
        raise ValueError("作业编号格式错误")
    result = read_json(DATA / "jobs" / f"{identifier}.json")
    if result is None:
        raise FileNotFoundError("训练作业不存在")
    return result
