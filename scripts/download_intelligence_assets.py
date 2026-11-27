"""从发布方下载公开模型与评估数据，并核对完整性。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".artifacts" / "models" / "qwen"
DOWNLOADS = ROOT / ".artifacts" / "downloads"
CURL = os.environ.get("AEROTOWER_CURL") or shutil.which("curl")
REPO = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/resolve/7ae557604adf67be50417f59c2c2f167def9a775"


def request(url, path, extra=()):
    if not CURL:
        raise RuntimeError("需要 curl，可用 AEROTOWER_CURL 指定可执行文件")
    return subprocess.run(
        [CURL, "-fLsS", "--retry", "2", "--connect-timeout", "15", "--max-time", "50",
         *extra, "-o", str(path), "-D", "-", url], capture_output=True, text=True
    )


def weight_part(spec):
    start, end = spec
    part = DOWNLOADS / f"qwen-{start:010d}.part"
    tail = part.with_suffix(".tail")
    total = 988097824
    for _ in range(24):
        have = part.stat().st_size if part.exists() else 0
        if have == end - start + 1:
            print(f"Qwen segment {start} ready", flush=True)
            return part
        reply = request(f"{REPO}/model.safetensors", tail, ("--range", f"{start+have}-{end}"))
        marker = f"content-range: bytes {start+have}-{end}/{total}"
        if marker in reply.stdout.lower() and reply.returncode in (0, 18, 28):
            if tail.exists() and 0 < tail.stat().st_size <= end-start+1-have:
                with part.open("ab") as output, tail.open("rb") as source:
                    shutil.copyfileobj(source, output)
        else:
            print(f"Segment {start}: retry ({reply.returncode})", flush=True)
    raise RuntimeError(f"模型分段尚未完成 {start}")


def download_model():
    DEST.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    # 附件大小来自同一固定修订的发布元数据，避免依赖本机预先生成的文件。
    sizes = {"LICENSE": 11343, "config.json": 659, "generation_config.json": 242,
             "merges.txt": 1671839, "tokenizer.json": 7031645,
             "tokenizer_config.json": 7305, "vocab.json": 2776833}
    for name, size in sizes.items():
        path = DEST / name
        if not path.exists() or path.stat().st_size != size:
            result = request(f"{REPO}/{name}", path)
            if result.returncode:
                raise RuntimeError(result.stderr)
        if path.stat().st_size != size:
            raise RuntimeError(f"模型附件大小不匹配 {name}")
    model = DEST / "model.safetensors"
    if not model.exists():
        total, chunk = 988097824, 16 * 1024 * 1024
        segments = [(x, min(x+chunk, total)-1) for x in range(0, total, chunk)]
        with ThreadPoolExecutor(max_workers=12) as pool:
            paths = list(pool.map(weight_part, segments))
        assembled = model.with_suffix(".assembling")
        with assembled.open("wb") as output:
            for path in paths:
                with path.open("rb") as source:
                    shutil.copyfileobj(source, output)
        assembled.rename(model)
    with model.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
    expected = "fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe"
    if actual != expected:
        raise RuntimeError("模型 SHA-256 与发布方不匹配")
    print(f"Qwen SHA-256 verified: {model.stat().st_size} bytes", flush=True)


def download_datasets():
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    datasets = [
        ("nyc-flights.csv", "nycflights13/flights.csv", 33206996,
         "b791a2590c9167aa0bd3cb45af3f64101180878cf088c183eae4011e3a654f42"),
        ("air-passengers.csv", "datasets/AirPassengers.csv", None,
         "bdb98adbd418a6de6842a742e0602f363c3b841c26677e7e61a1e055e9509bd8"),
    ]
    for name, relative, size, expected in datasets:
        dataset = DOWNLOADS / name
        if not dataset.exists() or (size is not None and dataset.stat().st_size != size):
            reply = request(f"https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/{relative}", dataset)
            if reply.returncode:
                raise RuntimeError(reply.stderr)
        with dataset.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"{name} 与固定评估版本不一致，不得静默替换数据")
        print(f"{name} SHA-256 verified: {dataset.stat().st_size} bytes", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-model", action="store_true", help="只准备公开数据；1.5B使用独立下载脚本")
    args = parser.parse_args()
    if not args.skip_model:
        download_model()
    download_datasets()


if __name__ == "__main__":
    main()
