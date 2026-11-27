"""校验并恢复从Release下载的正式小模型，默认不覆盖已有不同版本。"""
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version as package_version
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.intelligence.config import DATA


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_package(package):
    package = Path(package).resolve()
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    version = manifest.get("model_version", "")
    if manifest.get("schema_version") != 1 or not re.fullmatch(r"[0-9a-f]{32}", version):
        raise ValueError("正式模型清单版本不支持")
    expected = {"models/current.json", "language-evaluation.json", "THIRD_PARTY_NOTICES.md",
                "licenses/R-GPL-2.txt", "licenses/R-GPL-3.txt"}
    expected.update(f"models/{version}/{name}" for name in ("bundle.joblib", "evaluation.json", "samples.json"))
    if set(manifest["files"]) != expected:
        raise ValueError("正式模型清单的文件集合不匹配")
    for name, info in manifest["files"].items():
        path = package / name
        if not path.resolve().is_relative_to(package) or path.is_symlink() or not path.is_file():
            raise ValueError(f"模型文件不是包内普通文件：{name}")
        if path.stat().st_size != info["bytes"] or digest(path) != info["sha256"]:
            raise ValueError(f"模型文件完整性检查失败：{name}")
    pointer = json.loads((package / "models/current.json").read_text(encoding="utf-8"))
    report = json.loads((package / f"models/{version}/evaluation.json").read_text(encoding="utf-8"))
    if pointer["version"] != version or report["version"] != version:
        raise ValueError("模型指针和评估版本不一致")
    if digest(package / f"models/{version}/samples.json") != report["samples_sha256"]:
        raise ValueError("训练条件快照与原评估指纹不一致")
    return package, manifest


def check_runtime(manifest):
    runtime = manifest["runtime"]
    if platform.python_version_tuple()[:2] != tuple(runtime["python"].split(".")[:2]):
        raise RuntimeError("此模型包按Python 3.12验证，请使用相同主次版本")
    for name in ("numpy", "scikit-learn", "joblib", "ortools"):
        if package_version(name) != runtime[name]:
            raise RuntimeError(f"{name}版本不一致，请先按backend/requirements-windows.lock.txt准备环境")


def copy_atomically(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=target.name+".", suffix=".installing", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def install(package, destination, activate=False):
    package, manifest = checked_package(package)
    check_runtime(manifest)
    destination = Path(destination).resolve()
    conflicts = []
    for name, info in manifest["files"].items():
        target = destination / name
        if not target.resolve().is_relative_to(destination) or target.is_symlink():
            raise ValueError("目标目录含越界路径或链接，未恢复模型")
        if target.exists():
            if not target.is_file():
                raise ValueError(f"目标不是普通文件：{name}")
            if digest(target) != info["sha256"]:
                conflicts.append(name)
    replaceable = {"models/current.json", "language-evaluation.json"}
    if conflicts and (not activate or not set(conflicts) <= replaceable):
        raise ValueError("已有不同模型或评测，未写入；先停止服务，再用--activate明确切换。已存在但内容不同的同版本模型文件不会覆盖")
    backup = None
    if conflicts:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:8]
        backup = destination / "import-backups" / stamp
        for name in conflicts:
            copy_atomically(destination / name, backup / name)
    copied, skipped = [], []
    # 指针最后切换，避免服务看到尚未复制完整的版本。
    names = sorted(manifest["files"], key=lambda name: name == "models/current.json")
    for name in names:
        target = destination / name
        if target.is_file() and digest(target) == manifest["files"][name]["sha256"]:
            skipped.append(name)
            continue
        copy_atomically(package / name, target)
        copied.append(name)
    return {"model_version": manifest["model_version"], "copied": copied, "skipped": skipped,
            "backup": str(backup.relative_to(destination)) if backup else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, default=ROOT / ".artifacts/pretrained/intelligence-81860180")
    parser.add_argument("--destination", type=Path, default=DATA)
    parser.add_argument("--activate", action="store_true", help="备份后更新已有指针/语言评测，不删除旧模型及历史")
    args = parser.parse_args()
    print(json.dumps(install(args.package, args.destination, args.activate), ensure_ascii=False, indent=2))
    print("正式小模型已就绪；Qwen大模型请另运行scripts/download_language_model.py，再重新启动服务。")


if __name__ == "__main__":
    main()
