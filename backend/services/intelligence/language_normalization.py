"""只规范化模型给出的字段和值；没有原文参数，不能补提取缺漏。"""
import json
import math
import re
from .config import BOUNDS
from .language_rules import WEATHER_WORDS

ALIASES = {"基地": "base_airport", "天气": "weather", "客流变化": "demand_factor", "航班数": "flight_count",
           "跑道数": "capacity", "备用飞机": "backup_aircraft", "备用机组": "backup_crew", "备用登机口": "backup_gates",
           "前序延误": "previous_delay", "开始时间": "start_hour", "关闭时长": "disruption_minutes", "异常类型": "event_type"}
EVENT_WORDS = {"机场关闭": "airport_closure", "飞机故障": "aircraft_failure", "机组请假": "crew_absence", "登机口故障": "gate_failure"}


def canonical_phrase(value, words):
    if re.search(r"不|没有|不要|取消", value):
        return value
    matches = {code for word, code in words.items() if word in value}
    return next(iter(matches)) if len(matches) == 1 else value


def normalize_value(key, value):
    if not isinstance(value, str):
        return value
    value = value.strip()
    if key == "base_airport":
        return re.sub(r"基地$", "", value)
    if key == "weather":
        return canonical_phrase(value, WEATHER_WORDS)
    if key == "event_type":
        return canonical_phrase(value, EVENT_WORDS)
    if key == "demand_factor":
        change = re.fullmatch(r"(?:客流)?(增加|减少|下降|提高|涨|降|增)\s*(\d+(?:\.\d+)?)\s*[%％]", value)
        chinese = re.fullmatch(r"(?:客流)?(增加|减少|下降|提高|涨|降|增)\s*([一二两三四五六七八九十])成", value)
        if change or chinese:
            match = change or chinese
            amount = float(match[2])/100 if change else ("一二三四五六七八九十".index(match[2].replace("两", "二"))+1)/10
            return round(1+(-amount if match[1] in ("减少", "下降", "降") else amount), 3)
    if key in BOUNDS:
        if key != "demand_factor":
            quantity = re.fullmatch(r"(?:前序航班延误|前序延误|备用飞机|备份飞机|备用机组|备用登机口|机场关闭|关闭|从)?\s*(\d+(?:\.\d+)?)\s*(?:班航班|架次|分钟|小时|条|班|架|组|个|点开始|点)?", value)
            value = quantity[1] if quantity else value
        try:
            number = float(value)
            if math.isfinite(number):
                return number if key == "demand_factor" else int(number) if number.is_integer() else number
        except (ValueError, TypeError):
            pass
    return value


def decoded_fields(raw):
    start, end = raw.find("{"), raw.rfind("}")
    proposal = json.loads(raw[start:end+1])
    if not isinstance(proposal, dict):
        raise ValueError("模型输出不是对象")
    fields = {}
    for original, value in proposal.items():
        if value is None or isinstance(value, bool) or isinstance(value, str) and not value.strip():
            continue
        key = ALIASES.get(original, original)
        value = normalize_value(key, value)
        if key in fields and fields[key] != value:
            raise ValueError("模型同一字段给出冲突值")
        fields[key] = value
    return fields
