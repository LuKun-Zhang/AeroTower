"""版本固定的模拟日客流与公开月客流，明确区分数据来源。"""
import csv
from datetime import date, timedelta
import hashlib
import math
import random
from ..flight_generator import DEFAULT_TRAFFIC
from .config import AIRPORTS, DEFAULTS, ROOT


def simulated_history(airport, extra_days=0):
    level = sum(row["daily_pax"] for row in DEFAULT_TRAFFIC if row["origin"] == airport) or 500
    end = date.fromisoformat(DEFAULTS["start_date"])-timedelta(days=1)
    start = end-timedelta(days=729)
    rng = random.Random(20261126+AIRPORTS.index(airport))
    rows = []
    for index in range(730+extra_days):
        day = start+timedelta(days=index)
        weekly = [1.00, 0.96, 0.98, 1.03, 1.14, 1.22, 1.12][day.weekday()]
        annual = 1+0.12*math.sin(2*math.pi*day.timetuple().tm_yday/365.25)
        passengers = round(level*(1+index*0.0007)*weekly*annual*(1+rng.gauss(0, 0.012)))
        rows.append({"date": day.isoformat(), "passengers": max(1, passengers)})
    return {"frequency": "day", "rows": rows, "unit": "人次",
            "source": "原平台基准客流构造的模拟历史，含周季节、年季节、趋势及扰动；不是真实航司客流"}


def public_history():
    path = ROOT / ".artifacts" / "downloads" / "air-passengers.csv"
    if not path.exists():
        return None
    expected = "bdb98adbd418a6de6842a742e0602f363c3b841c26677e7e61a1e055e9509bd8"
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("公开客流文件版本与固定评估版本不一致")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = [{"date": date(1949+index//12, index%12+1, 1).isoformat(),
                 "passengers": float(row["value"])*1000} for index, row in enumerate(csv.DictReader(stream))]
    return {"frequency": "month", "rows": rows, "unit": "人次", "sha256": expected,
            "source": "AirPassengers：1949–1960国际航空月客流，原始单位千人，已换算人次",
            "url": "https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/AirPassengers.html"}
