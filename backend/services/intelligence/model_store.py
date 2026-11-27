"""本机模型的版本化保存与按需读取。"""
from threading import RLock
import hashlib
from importlib.metadata import version as package_version
import platform
import uuid
import joblib
from .config import MODELS, ROOT
from .storage import read_json, utc_now, write_json

_LOCK = RLock()
_CACHE = {"version": None, "bundle": None}


def save_bundle(bundle, report, samples=None):
    version = uuid.uuid4().hex
    folder = MODELS / version
    folder.mkdir(parents=True, exist_ok=False)
    joblib.dump(bundle, folder / "bundle.joblib", compress=3)
    report = {**report, "version": version, "created_at": utc_now()}
    if samples is not None:
        write_json(folder / "samples.json", samples)
        report["samples_sha256"] = hashlib.sha256((folder / "samples.json").read_bytes()).hexdigest()
    paths = sorted((ROOT / "backend" / "services").rglob("*.py")) + sorted((ROOT / "backend" / "models").glob("*.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    report["source_sha256"] = digest.hexdigest()
    report["runtime"] = {"python": platform.python_version(), **{name: package_version(name) for name in ("numpy", "scikit-learn", "joblib", "ortools")}}
    write_json(folder / "evaluation.json", report)
    # 只有模型和评估文件都落盘后才切换当前版本。
    write_json(MODELS / "current.json", {"version": version})
    return report


def current_report():
    pointer = read_json(MODELS / "current.json")
    return read_json(MODELS / pointer["version"] / "evaluation.json") if pointer else None


def load_bundle():
    with _LOCK:
        pointer = read_json(MODELS / "current.json")
        if not pointer:
            return None
        if pointer["version"] != _CACHE["version"]:
            bundle = joblib.load(MODELS / pointer["version"] / "bundle.joblib")
            bundle["version"] = pointer["version"]
            _CACHE.update(version=pointer["version"], bundle=bundle)
        return _CACHE["bundle"]
