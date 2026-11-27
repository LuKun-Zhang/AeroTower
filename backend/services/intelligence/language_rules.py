"""用明确文字证据核对语言模型草稿，保留用户未说明的条件。"""
import re
from datetime import datetime, timedelta, timezone
from .config import AIRPORTS, DEFAULTS, validate_config

WEATHER_WORDS = {"雷暴": "storm", "暴雨": "storm", "大雾": "fog", "雾": "fog", "降雪": "snow", "下雪": "snow",
                 "下雨": "rain", "降雨": "rain", "晴天": "clear", "晴朗": "clear"}


def grounded_fields(text):
    fields, evidence, warnings = {}, {}, []
    airports = [name for name in AIRPORTS if name in text]
    if len(airports) == 1:
        fields["base_airport"], evidence["base_airport"] = airports[0], airports[0]
    elif len(airports) > 1:
        warnings.append("提到了多个机场，请在表单中确认基地")
    conditions = []
    for word, value in WEATHER_WORDS.items():
        for match in re.finditer(word, text):
            prefix = text[max(0, match.start()-3):match.start()]
            if not re.search(r"不|没有|不要|取消", prefix):
                conditions.append((value, word))
    if len({value for value, _ in conditions}) == 1:
        fields["weather"], evidence["weather"] = conditions[0]
    elif conditions:
        warnings.append("出现了多种天气，请人工选择")
    change = re.search(r"(?:客流|流量)[^，。；]{0,6}?(涨|增|增加|提高|下降|减少|降)(?:加|长)?\s*(\d+(?:\.\d+)?)\s*[%％]", text)
    chinese = re.search(r"(?:客流|流量)[^，。；]{0,6}?(涨|增|增加|提高|下降|减少|降)([一二两三四五六七八九十])成", text)
    if change or chinese:
        match = change or chinese
        amount = float(match[2])/100 if change else ("一二三四五六七八九十".index(match[2].replace("两", "二"))+1)/10
        sign = -1 if match[1] in ("下降", "减少", "降") else 1
        fields["demand_factor"] = round(1+sign*amount, 3)
        evidence["demand_factor"] = match[0]
    patterns = {"flight_count": r"(\d+)\s*(?:架次|架|个|班)?航班", "capacity": r"(\d+)\s*条(?:可用)?跑道",
                "backup_aircraft": r"(?:备用|备份)(?:飞机)?\s*(\d+)\s*架",
                "backup_crew": r"(?:备用|备份)机组\s*(\d+)\s*组", "backup_gates": r"(?:备用|备份)登机口\s*(\d+)\s*个",
                "disruption_minutes": r"(?:关闭|中断|停场)\s*(\d+)\s*分钟",
                "previous_delay": r"前序(?:航班)?延误\s*(\d+)\s*分钟", "start_hour": r"(?:从|开始于)\s*(\d+)\s*点"}
    for field, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            fields[field], evidence[field] = int(match[1]), match[0]
    event_words = {"飞机故障": "aircraft_failure", "机组请假": "crew_absence", "登机口故障": "gate_failure", "机场关闭": "airport_closure"}
    events = []
    for word, value in event_words.items():
        for match in re.finditer(word, text):
            if not re.search(r"不|没有|不要|取消", text[max(0, match.start()-3):match.start()]):
                events.append((value, word))
    if len({value for value, _ in events}) == 1:
        fields["event_type"], evidence["event_type"] = events[0]
    elif events:
        warnings.append("出现多种异常类型，请人工选择")
    today = datetime.now(timezone(timedelta(hours=8))).date()
    if "下周" in text:
        fields["start_date"] = (today + timedelta(days=7-today.weekday())).isoformat()
        fields["days"] = 7
        evidence.update(start_date="下周（按北京时间解析为下个周一）", days="下周（7天）")
    elif "明天" in text:
        fields["start_date"] = (today+timedelta(days=1)).isoformat()
        fields["days"] = 1
        evidence.update(start_date="明天（按北京时间解析）", days="明天（1天）")
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if date_match:
        fields["start_date"], evidence["start_date"] = date_match[1], date_match[0]
    validate_config(fields)
    return fields, evidence, warnings


def validate_draft(text, proposal):
    fields, evidence, warnings = grounded_fields(text)
    rejected = []
    for key, value in proposal.items():
        if key not in fields or fields[key] != value:
            rejected.append(key)
    if rejected:
        warnings.append("已过滤缺少原文证据或不一致的字段：" + "、".join(rejected))
    return {"fields": fields, "evidence": evidence, "warnings": warnings,
            "unspecified": [key for key in DEFAULTS if key not in fields],
            "requires_confirmation": True, "rejected_fields": rejected}
