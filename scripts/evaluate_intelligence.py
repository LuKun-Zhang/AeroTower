"""检查公开航班数据及固定24条语言描述，不使用外部推理服务。"""
from pathlib import Path
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "4")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.intelligence.external_evaluation import evaluate_external
from evaluate_language import main as evaluate_language


if __name__ == "__main__":
    external = evaluate_external(ROOT / ".artifacts" / "downloads" / "nyc-flights.csv")
    print(json.dumps({"external": external}, ensure_ascii=False, indent=2), flush=True)
    # 共用正式检查入口，避免旧8条脚本覆盖当前24条评估与启用状态。
    evaluate_language()
