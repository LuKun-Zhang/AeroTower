"""8条开发、16条旧回归及24条新留出，分别记录模型提取与模板回退。"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("OMP_NUM_THREADS", "4")
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-for-1-5b", action="store_true")
    parser.add_argument("--resume", action="store_true", help="仅在模型、提示和固定样例完全一致时续跑中断检查")
    parser.add_argument("--development-only", action="store_true", help="只检查8条开发描述，保留进度但不发布正式成绩")
    args = parser.parse_args()
    if args.wait_for_1_5b:
        proof = ROOT / ".artifacts/models/qwen-1.5b/verified.json"
        deadline = time.monotonic()+3600
        while not proof.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("1.5B模型仍未校验完成，本次未开始模型评测")
            time.sleep(5)
    # 等待后再导入，保证路径选择的是已完整校验的1.5B，而不是旧模型。
    from backend.services.intelligence.language import decoded_fields, language_identity, parse_description
    from backend.services.intelligence.language_cases import DEVELOPMENT, HOLDOUT
    from backend.services.intelligence.config import DATA
    from backend.services.intelligence.storage import read_json, write_json
    identity = language_identity()
    fresh_path = ROOT / "tests/fixtures/language_holdout_v2.json"
    fresh_sha = hashlib.sha256(fresh_path.read_bytes()).hexdigest()
    if fresh_sha != "6509a92be98d38a32754e46155155d6b4ef3b78b6b431b2011d57c43f915c724":
        raise ValueError("固定新留出样例已变化，不能继续使用原协议")
    groups = (("development", DEVELOPMENT), ("regression", HOLDOUT), ("holdout", read_json(fresh_path)))
    if args.wait_for_1_5b and identity["name"] != "Qwen2.5-1.5B-Instruct":
        raise ValueError("本次没有加载批准的1.5B模型，停止以免误报")
    print("MODEL", json.dumps(identity, ensure_ascii=False), flush=True)
    results = []
    if args.resume:
        prior = read_json(ROOT / ".artifacts/verification/language-evaluation-progress.json", {})
        if prior.get("identity") != identity:
            raise ValueError("已存评测的模型或提示不同，不能合并结果")
        results = prior.get("cases", [])
        frozen = [(group, text, expected) for group, cases in groups for text, expected in cases]
        if len(results) > len(frozen) or any((row["group"], row["text"], row["expected"]) != frozen[index] for index, row in enumerate(results)):
            raise ValueError("已存评测不是当前固定样例的连续前缀，不能跳过或挑选样例")
        print("RESUME", len(results), "completed cases", flush=True)
    completed = len(results)
    index = 0
    for group, cases in groups:
        if args.development_only and group != "development":
            break
        for text, expected in cases:
            index += 1
            if index <= completed:
                continue
            started = time.monotonic()
            result = parse_description(text, use_model=True)
            try:
                initial = decoded_fields(result.get("initial_model_output") or "")
            except (ValueError, TypeError):
                initial = None
            row = {"group": group, "text": text, "expected": expected, "actual": result["fields"],
                   "raw_model_exact": initial == expected,
                   "model_exact_after_feedback": result["method"] == "local-qwen" and result["model_fields"] == expected,
                   "grounded_exact": result["fields"] == expected, "method": result["method"],
                   "initial_model_output": result.get("initial_model_output"), "model_output": result.get("model_output"),
                   "retry_used": result["retry_used"], "seconds": round(time.monotonic()-started, 2),
                   "model_fields": result["model_fields"], "model_field_sources": result["model_field_sources"],
                   "warnings": result["warnings"]}
            results.append(row)
            write_json(ROOT / ".artifacts/verification/language-evaluation-progress.json", {"identity": identity, "cases": results})
            print(group, text, "raw", row["raw_model_exact"], "after_feedback", row["model_exact_after_feedback"], result["method"], row["seconds"], flush=True)
    if args.development_only:
        print("DEVELOPMENT", len(results), "first", sum(row["raw_model_exact"] for row in results),
              "merged", sum(row["model_exact_after_feedback"] for row in results), "not published", flush=True)
        return
    holdout = [row for row in results if row["group"] == "holdout"]
    evaluation = {"identity": identity, "cases": results, "count": len(results), "holdout_count": len(holdout),
        "raw_model_exact": sum(row["raw_model_exact"] for row in results),
        "model_exact_after_feedback": sum(row["model_exact_after_feedback"] for row in results),
        "grounded_exact": sum(row["grounded_exact"] for row in results),
        "holdout_model_exact": sum(row["model_exact_after_feedback"] for row in holdout),
        "protocol_version": 2, "fresh_cases_sha256": fresh_sha,
        "acceptance": "8开发+16旧回归+24新留出；总体及新留出两轮模型提取合并正确率均至少90%，带回退草稿100%正确；失败明确模板回退",
        "raw_definition": "首轮模型字段经中文名称、单位、枚举与空值规范化；只读取模型输出，不从原文补值",
        "feedback_definition": "最多一次只含字段名的反馈；保留已核对正确的首轮模型值，再合并第二轮模型补丁，逐字段记录来源；不把模板补漏算模型成功",
        "scope": "固定支持描述，不能保证任意自由表达；只生成草稿，必须人工确认"}
    prior = read_json(DATA / "language-evaluation.json")
    if prior:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        write_json(DATA / "language-evaluation-history" / f"{stamp}.json", prior)
    write_json(DATA / "language-evaluation.json", evaluation)
    write_json(ROOT / ".artifacts/verification/language-evaluation-final.json", evaluation)
    print("FINAL", {key: value for key, value in evaluation.items() if key not in ("cases",)}, flush=True)


if __name__ == "__main__":
    main()
