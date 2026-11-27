"""在项目虚拟环境内训练模型，结果保存在本地数据目录。"""
from pathlib import Path
import argparse
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "4")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.intelligence.training import train_models


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-scenarios", type=int, default=180)
    parser.add_argument("--test-scenarios", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20261126)
    args = parser.parse_args()
    report = train_models(args.train_scenarios, args.test_scenarios, args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2))
