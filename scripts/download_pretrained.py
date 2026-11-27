"""下载固定Release小模型包，校验后解压到本地缓存，不改活动模型。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile

from install_pretrained import ROOT, checked_package

TAG = "phase2-models-81860180"
ASSET = "aerotower-intelligence-81860180.zip"
URL = f"https://github.com/LuKun-Zhang/AeroTower/releases/download/{TAG}/{ASSET}"
SHA256 = "fc031465d4f52ea01ee5ec8a85a740814b1fb47f80aa2ed59c20741f490cba4e"
BYTES = 556202
DEFAULT_DEST = ROOT / ".artifacts/pretrained/intelligence-81860180"


def extract_checked(archive, destination):
    archive = Path(archive)
    with archive.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    if archive.stat().st_size != BYTES or actual != SHA256:
        raise ValueError("Release压缩包大小或SHA-256不匹配，未解压")
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != 9 or len(set(names)) != 9 or "manifest.json" not in names:
            raise ValueError("Release压缩包文件集合不匹配")
        if sum(entry.file_size for entry in entries) > 2*1024*1024:
            raise ValueError("Release解压大小超出固定模型包范围")
        for entry in entries:
            target = destination / entry.filename
            mode = entry.external_attr >> 16
            if (entry.is_dir() or stat.S_ISLNK(mode) or "\\" in entry.filename
                    or not target.resolve().is_relative_to(destination.resolve())):
                raise ValueError("Release压缩包包含无效路径或链接")
        manifest = json.loads(package.read("manifest.json"))
        if set(names) != {"manifest.json", *manifest["files"]}:
            raise ValueError("Release文件与清单不一致")
        package.extractall(destination)
    checked_package(destination)


def download(destination=DEFAULT_DEST, archive=None):
    destination = Path(destination).absolute()
    if destination.is_symlink() or destination.resolve() != destination:
        raise ValueError("缓存路径不能经过链接")
    if destination.exists():
        _, manifest = checked_package(destination)
        expected = json.loads((ROOT / "pretrained/intelligence/manifest.json").read_text(encoding="utf-8"))
        if manifest != expected:
            raise ValueError("已有缓存不是本次Release，未覆盖")
        return {"cached": True, "files_verified": len(manifest["files"])}
    destination.parent.mkdir(parents=True, exist_ok=True)
    # 只清理本次创建的临时目录；不删除已有缓存或用户模型。
    with tempfile.TemporaryDirectory(prefix="release-download-", dir=destination.parent) as temporary:
        temporary = Path(temporary).resolve()
        if not temporary.is_relative_to(destination.parent.resolve()):
            raise ValueError("临时目录越界")
        if archive is None:
            curl = os.environ.get("AEROTOWER_CURL") or shutil.which("curl")
            if not curl:
                raise RuntimeError("需要curl，可用AEROTOWER_CURL指定已有可执行文件")
            archive = temporary / ASSET
            subprocess.run([curl, "-fLsS", "--retry", "2", "--connect-timeout", "15",
                            "--max-time", "120", "-o", str(archive), URL], check=True)
        expanded = temporary / "expanded"
        expanded.mkdir()
        extract_checked(archive, expanded)
        os.replace(expanded, destination)
    return {"cached": False, "sha256": SHA256, "bytes": BYTES, "files_verified": 8}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--archive", type=Path, help="使用已下载的本地Release ZIP，仍校验固定哈希")
    args = parser.parse_args()
    print(json.dumps(download(args.destination, args.archive), ensure_ascii=False, indent=2))
    print("小模型包已校验；接着运行scripts/install_pretrained.py恢复模型。")


if __name__ == "__main__":
    main()
