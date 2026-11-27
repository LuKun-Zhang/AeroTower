"""核对评测数字及模型字段来源，不重新调用模型、不从原文提取字段。"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.intelligence.language import decoded_fields, language_identity, language_policy


def decode(raw):
    try:
        return decoded_fields(raw or "")
    except (TypeError, ValueError):
        return None


def audit():
    folder = ROOT / ".artifacts/verification"
    report = json.loads((folder / "language-evaluation-final.json").read_text(encoding="utf-8"))
    assert report["identity"] == language_identity(), "评估不是当前提示与解析流程"
    rows = report["cases"]
    assert len(rows) == report["count"] == 48
    for row in rows:
        first, revised = decode(row["initial_model_output"]), decode(row["model_output"])
        assert row["raw_model_exact"] == (first == row["expected"])
        assert row["model_exact_after_feedback"] == (row["method"] == "local-qwen" and row["model_fields"] == row["expected"])
        assert row["grounded_exact"] == (row["actual"] == row["expected"])
        for key, value in row["model_fields"].items():
            source = row["model_field_sources"][key]
            supplied = first if source == "initial" else revised if source == "retry" else None
            assert supplied is not None and key in supplied and supplied[key] == value, (row["text"], key, "无模型来源")
        assert (row["method"] == "local-qwen") == row["model_exact_after_feedback"]
    assert report["raw_model_exact"] == sum(row["raw_model_exact"] for row in rows)
    assert report["model_exact_after_feedback"] == sum(row["model_exact_after_feedback"] for row in rows)
    assert report["grounded_exact"] == sum(row["grounded_exact"] for row in rows)
    cohorts = {}
    for name, values in (("old_24", [r for r in rows if r["group"] != "holdout"]),
                         ("fresh_24", [r for r in rows if r["group"] == "holdout"]), ("all_48", rows)):
        cohorts[name] = {"count": len(values), "first": sum(r["raw_model_exact"] for r in values),
                         "merged": sum(r["model_exact_after_feedback"] for r in values),
                         "guarded": sum(r["grounded_exact"] for r in values)}
    assert report["holdout_count"] == cohorts["fresh_24"]["count"] == 24
    assert report["holdout_model_exact"] == cohorts["fresh_24"]["merged"]
    baseline = json.loads((folder / "language-baseline-v1.json").read_text(encoding="utf-8"))
    result = {"passed": True, "identity": report["identity"], "cohorts": cohorts,
              "baseline": {"count": baseline["count"], "first": baseline["raw_model_exact"],
                           "after_feedback": baseline["model_exact_after_feedback"]},
              "all_model_fields_traceable": True, "default_policy": language_policy()}
    (folder / "language-provenance-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    audit()
