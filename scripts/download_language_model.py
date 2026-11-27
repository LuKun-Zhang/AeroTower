"""下载已批准的官方1.5B模型，固定修订并逐段核对范围。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".artifacts/models/qwen-1.5b"
TEMP = ROOT / ".artifacts/downloads"
REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
URL = f"https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/resolve/{REVISION}"
CURL = os.environ.get("AEROTOWER_CURL") or shutil.which("curl")


def request(url, path, extra=()):
    # 分段由外层保存已收到的字节并续传；curl内部超时重试会丢弃这一段的进度。
    retries = "0" if "--range" in extra else "2"
    return subprocess.run([CURL, "-fLsS", "--retry", retries, "--connect-timeout", "15", "--max-time", "55",
        *extra, "-D", "-", "-o", str(path), url], capture_output=True, text=True)


def segment(spec):
    start, end, total = spec
    path = TEMP / f"qwen15-{start:010d}.part"
    tail = path.with_suffix(".tail")
    for _ in range(40):
        have = path.stat().st_size if path.exists() else 0
        if have == end-start+1:
            print(f"Segment {start} ready", flush=True)
            return path
        reply = request(f"{URL}/model.safetensors", tail, ("--range", f"{start+have}-{end}"))
        if f"content-range: bytes {start+have}-{end}/{total}" in reply.stdout.lower() and reply.returncode in (0, 18, 28):
            if tail.exists() and 0 < tail.stat().st_size <= end-start+1-have:
                with path.open("ab") as target, tail.open("rb") as source:
                    shutil.copyfileobj(source, target)
    raise RuntimeError(f"下载分段未完成：{start}")


def main():
    if not CURL:
        raise RuntimeError("需要curl，可用AEROTOWER_CURL指定已有可执行文件")
    metadata_file = TEMP / "qwen-1.5b-metadata.json"
    sizes = {"LICENSE": 11343, "config.json": 660, "generation_config.json": 242, "merges.txt": 1671839,
             "tokenizer.json": 7031645, "tokenizer_config.json": 7305, "vocab.json": 2776833}
    # 固定发布元数据，空环境也可复刻，避免无条件追随最新修订。
    metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {
        "sha": REVISION, "siblings": [{"rfilename": name, "size": size} for name, size in sizes.items()]+[
            {"rfilename": "model.safetensors", "size": 3087467144,
             "lfs": {"sha256": "dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee"}}]}
    if metadata["sha"] != REVISION:
        raise ValueError("模型元数据修订不一致")
    DEST.mkdir(parents=True, exist_ok=True)
    for info in metadata["siblings"]:
        name = info["rfilename"]
        if name in ("LICENSE", "config.json", "generation_config.json", "merges.txt", "tokenizer.json", "tokenizer_config.json", "vocab.json"):
            path = DEST / name
            if not path.exists() or path.stat().st_size != info["size"]:
                result = request(f"{URL}/{name}", path)
                if result.returncode or path.stat().st_size != info["size"]:
                    raise RuntimeError(f"模型附件下载失败：{name}")
    weight = next(row for row in metadata["siblings"] if row["rfilename"] == "model.safetensors")
    model = DEST / "model.safetensors"
    if not model.exists():
        chunk, total = 32*1024*1024, weight["size"]
        specs = [(start, min(start+chunk, total)-1, total) for start in range(0, total, chunk)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            paths = list(pool.map(segment, specs))
        assembled = DEST / "model.assembling"
        with assembled.open("wb") as output:
            for path in paths:
                with path.open("rb") as source:
                    shutil.copyfileobj(source, output)
        assembled.rename(model)
    with model.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    expected = weight["lfs"]["sha256"]
    if digest != expected or model.stat().st_size != weight["size"]:
        raise RuntimeError("1.5B模型完整性检查失败")
    (DEST / "verified.json").write_text(json.dumps({"model": "Qwen2.5-1.5B-Instruct", "revision": REVISION,
        "bytes": weight["size"], "sha256": digest}, indent=2), encoding="utf-8")
    print("Model verified", weight["size"], digest, flush=True)


if __name__ == "__main__":
    main()
