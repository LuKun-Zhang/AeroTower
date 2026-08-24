"""异常场景模板库

预置常用的异常场景模板，前端通过 API 获取，用户可一键创建异常事件。
"""

from backend.models.abnormal_event import AnomalyType, AnomalyPriority

# ========== 场景模板 ==========

TEMPLATES = [
    # ---------- 天气类 ----------
    {
        "id": "wx_001",
        "title": "成都双流机场雷暴关闭",
        "type": AnomalyType.WEATHER_AIRPORT_CLOSURE,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "成都双流机场遭遇强雷暴天气，机场临时关闭",
        "params": {
            "airport": {"value": "成都", "type": "select", "options": "airport_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 2, "type": "number", "min": 0.5, "max": 24, "step": 0.5, "options": [1, 2, 3, 4]},
            "capacity_ratio": {"value": 0, "type": "float", "min": 0, "max": 1},
        },
    },
    {
        "id": "wx_002",
        "title": "重庆江北机场大雾低能见度",
        "type": AnomalyType.WEATHER_CAPACITY,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "重庆江北机场大雾导致能见度降低，起降速率减半",
        "params": {
            "airport": {"value": "重庆", "type": "select", "options": "airport_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 4, "type": "number", "min": 1, "max": 12, "step": 1, "options": [2, 4, 6]},
            "capacity_ratio": {"value": 0.5, "type": "float", "min": 0, "max": 1},
        },
    },
    {
        "id": "wx_003",
        "title": "昆明长水机场暴雪关闭",
        "type": AnomalyType.WEATHER_AIRPORT_CLOSURE,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "昆明长水机场遭遇暴雪，机场临时关闭",
        "params": {
            "airport": {"value": "昆明", "type": "select", "options": "airport_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 4, "type": "number", "min": 1, "max": 24, "step": 1, "options": [2, 4, 8]},
            "capacity_ratio": {"value": 0, "type": "float", "min": 0, "max": 1},
        },
    },
    {
        "id": "wx_004",
        "title": "航路雷暴绕飞",
        "type": AnomalyType.WEATHER_ENROUTE,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "航路遭遇雷暴，需绕飞导致飞行时间增加",
        "params": {
            "extra_flight_time": {"value": 30, "type": "number", "min": 15, "max": 120, "step": 15, "options": [30, 45, 60, 90]},
        },
    },

    # ---------- 天气·省份 ----------
    {
        "id": "wp_001",
        "title": "台风影响广东沿海（省份级）",
        "type": AnomalyType.WEATHER_TYPHOON,
        "priority": AnomalyPriority.P0_EMERGENCY,
        "description": "台风登陆广东沿海，全省机场关闭，途经航班均受绕飞影响",
        "params": {
            "affected_provinces": {"value": ["广东", "海南", "福建", "广西"], "type": "multi_select", "options": "province_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 8, "type": "number", "min": 2, "max": 72, "step": 1, "options": [4, 8, 12, 24]},
            "severity": {"value": 5, "type": "select", "options": [{"value": 3, "label": "中度(延误2h)"}, {"value": 4, "label": "重度(延误3h)"}, {"value": 5, "label": "极重(取消)"}], "required": True},
        },
    },
    {
        "id": "wp_002",
        "title": "四川盆地雷暴天气（省份级）",
        "type": AnomalyType.WEATHER_STORM,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "四川盆地大范围雷暴，全省机场降效，途经航班受绕飞影响",
        "params": {
            "affected_provinces": {"value": ["四川"], "type": "multi_select", "options": "province_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 4, "type": "number", "min": 1, "max": 24, "step": 1, "options": [2, 4, 6, 12]},
            "severity": {"value": 4, "type": "select", "options": [{"value": 2, "label": "轻度(延误1h)"}, {"value": 3, "label": "中度(延误2h)"}, {"value": 4, "label": "重度(延误3h)"}], "required": True},
        },
    },
    {
        "id": "wp_003",
        "title": "华中三省暴雨（省份级）",
        "type": AnomalyType.WEATHER_RAIN,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "湖北、湖南、江西三省持续暴雨，航班大面积延误",
        "params": {
            "affected_provinces": {"value": ["湖北", "湖南", "江西"], "type": "multi_select", "options": "province_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 6, "type": "number", "min": 2, "max": 48, "step": 1, "options": [3, 6, 12, 24]},
            "severity": {"value": 3, "type": "select", "options": [{"value": 1, "label": "轻微(延误30min)"}, {"value": 2, "label": "轻度(延误1h)"}, {"value": 3, "label": "中度(延误2h)"}], "required": True},
        },
    },

    # ---------- 飞机类 ----------
    {
        "id": "ac_001",
        "title": "A319 飞机机械故障（AOG）",
        "type": AnomalyType.AIRCRAFT_FAILURE,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "A319 飞机出现机械故障，需停场维修",
        "params": {
            "aircraft_id": {"value": "", "type": "select", "options": "aircraft_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "repair_hours": {"value": 4, "type": "number", "min": 1, "max": 72, "step": 1, "options": [2, 4, 8]},
        },
    },
    {
        "id": "ac_002",
        "title": "飞机备降",
        "type": AnomalyType.AIRCRAFT_DIVERSION,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "飞机因紧急情况备降至非计划机场",
        "params": {
            "flight_id": {"value": "", "type": "select", "options": "flight_list", "required": True},
            "divert_airport": {"value": "", "type": "select", "options": "airport_list", "required": True},
        },
    },
    {
        "id": "ac_003",
        "title": "例行定检延期",
        "type": AnomalyType.AIRCRAFT_MAINTENANCE,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "飞机定检超时，不可用时间延长",
        "params": {
            "aircraft_id": {"value": "", "type": "select", "options": "aircraft_list", "required": True},
            "extend_hours": {"value": 3, "type": "number", "min": 1, "max": 24, "step": 1, "options": [2, 4, 6]},
        },
    },

    # ---------- 机组类 ----------
    {
        "id": "cr_001",
        "title": "机组人员请假替班",
        "type": AnomalyType.CREW_SUBSTITUTION,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "机组成员因突发原因无法执勤，需临时替班",
        "params": {
            "base": {"value": "成都", "type": "select", "options": "base_list", "required": True},
            "role": {"value": "", "type": "select", "options": [{"value": "captain", "label": "机长"}, {"value": "first_officer", "label": "副驾驶"}, {"value": "purser", "label": "乘务长"}, {"value": "attendant", "label": "乘务员"}], "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "end_time": {"value": "", "type": "datetime", "required": True},
        },
    },
    {
        "id": "cr_002",
        "title": "机组执勤超时",
        "type": AnomalyType.CREW_OVERTIME,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "因前序延误导致机组执勤时间超出法规限制",
        "params": {
            "crew_id": {"value": "", "type": "select", "options": "crew_list", "required": True},
        },
    },
    {
        "id": "cr_003",
        "title": "机组资质不匹配",
        "type": AnomalyType.CREW_QUALIFICATION,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "临时更换机型导致原机组无对应资质",
        "params": {
            "flight_id": {"value": "", "type": "select", "options": "flight_list", "required": True},
            "new_ac_type": {"value": "", "type": "select", "options": ["A319", "A320", "A321"], "required": True},
        },
    },

    # ---------- 跑道类 ----------
    {
        "id": "rw_001",
        "title": "成都双流跑道维修关闭",
        "type": AnomalyType.RUNWAY_CLOSURE,
        "priority": AnomalyPriority.P1_CRITICAL,
        "description": "跑道维修施工，临时关闭",
        "params": {
            "airport": {"value": "成都", "type": "select", "options": "airport_list", "required": True},
            "runway_id": {"value": "", "type": "select", "options": "runway_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 3, "type": "number", "min": 0.5, "max": 48, "step": 0.5, "options": [2, 4, 6]},
        },
    },
    {
        "id": "rw_002",
        "title": "跑道灯光故障降级运行",
        "type": AnomalyType.RUNWAY_DEGRADE,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "跑道灯光系统故障，起降标准提高",
        "params": {
            "airport": {"value": "", "type": "select", "options": "airport_list", "required": True},
            "runway_id": {"value": "", "type": "select", "options": "runway_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 4, "type": "number", "min": 1, "max": 24, "step": 1},
        },
    },

    # ---------- 登机口类 ----------
    {
        "id": "gt_001",
        "title": "登机口廊桥故障关闭",
        "type": AnomalyType.GATE_CLOSURE,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "登机口廊桥故障，需维修关闭",
        "params": {
            "airport": {"value": "成都", "type": "select", "options": "airport_list", "required": True},
            "gate_id": {"value": "", "type": "select", "options": "gate_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 4, "type": "number", "min": 0.5, "max": 72, "step": 0.5, "options": [2, 4, 8]},
        },
    },
    {
        "id": "gt_002",
        "title": "登机口被占用未释放",
        "type": AnomalyType.GATE_OCCUPIED,
        "priority": AnomalyPriority.P3_INFO,
        "description": "前序航班延误导致登机口未按时释放",
        "params": {
            "flight_id": {"value": "", "type": "select", "options": "flight_list", "required": True},
            "delay_minutes": {"value": 30, "type": "number", "min": 15, "max": 180, "step": 15},
        },
    },

    # ---------- 空域/流控类 ----------
    {
        "id": "fc_001",
        "title": "成都双流流控限制",
        "type": AnomalyType.FLOW_CONTROL,
        "priority": AnomalyPriority.P2_NORMAL,
        "description": "空管发布成都双流机场流控，起飞速率受限",
        "params": {
            "airport": {"value": "成都", "type": "select", "options": "airport_list", "required": True},
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 2, "type": "number", "min": 0.5, "max": 12, "step": 0.5, "options": [1, 2, 4]},
            "rate": {"value": 0.5, "type": "float", "min": 0.1, "max": 0.9, "step": 0.1},
        },
    },
    {
        "id": "fc_002",
        "title": "空域临时关闭",
        "type": AnomalyType.AIRSPACE_CLOSURE,
        "priority": AnomalyPriority.P0_EMERGENCY,
        "description": "因军事活动等原因空域临时关闭，相关航路不可用",
        "params": {
            "start_time": {"value": "", "type": "datetime", "required": True},
            "duration_hours": {"value": 2, "type": "number", "min": 0.5, "max": 24, "step": 0.5},
        },
    },
]

# ========== 异常参数 Schema（前端动态表单用） ==========

ANOMALY_PARAMS_SCHEMA = {
    AnomalyType.WEATHER_AIRPORT_CLOSURE: {
        "airport": {"type": "select", "options": "airport_list", "label": "机场", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 0.5, "max": 24, "step": 0.5},
        "capacity_ratio": {"type": "float", "label": "容量比例", "min": 0, "max": 1, "default": 0},
    },
    AnomalyType.WEATHER_ENROUTE: {
        "extra_flight_time": {"type": "number", "label": "额外飞行时间(分钟)", "min": 15, "max": 120, "step": 15},
    },
    AnomalyType.WEATHER_CAPACITY: {
        "airport": {"type": "select", "options": "airport_list", "label": "机场", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 1, "max": 12},
        "capacity_ratio": {"type": "float", "label": "容量比例", "min": 0, "max": 1, "default": 0.5},
    },
    AnomalyType.AIRCRAFT_FAILURE: {
        "aircraft_id": {"type": "select", "options": "aircraft_list", "label": "飞机", "required": True},
        "start_time": {"type": "datetime", "label": "故障时间", "required": True},
        "repair_hours": {"type": "number", "label": "维修小时", "min": 1, "max": 72},
    },
    AnomalyType.AIRCRAFT_DIVERSION: {
        "flight_id": {"type": "select", "options": "flight_list", "label": "航班", "required": True},
        "divert_airport": {"type": "select", "options": "airport_list", "label": "备降机场", "required": True},
    },
    AnomalyType.AIRCRAFT_MAINTENANCE: {
        "aircraft_id": {"type": "select", "options": "aircraft_list", "label": "飞机", "required": True},
        "extend_hours": {"type": "number", "label": "延长小时", "min": 1, "max": 24},
    },
    AnomalyType.CREW_SUBSTITUTION: {
        "base": {"type": "select", "options": "base_list", "label": "基地", "required": True},
        "crew_id": {"type": "select", "options": "crew_list", "label": "请假人员", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "end_time": {"type": "datetime", "label": "结束时间", "required": True},
    },
    AnomalyType.CREW_OVERTIME: {
        "crew_id": {"type": "select", "options": "crew_list", "label": "机组人员", "required": True},
    },
    AnomalyType.CREW_QUALIFICATION: {
        "flight_id": {"type": "select", "options": "flight_list", "label": "航班", "required": True},
        "new_ac_type": {"type": "select", "options": ["A319", "A320", "A321"], "label": "新机型", "required": True},
    },
    AnomalyType.RUNWAY_CLOSURE: {
        "airport": {"type": "select", "options": "airport_list", "label": "机场", "required": True},
        "runway_id": {"type": "select", "options": "runway_list", "label": "跑道", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 0.5, "max": 48},
    },
    AnomalyType.RUNWAY_DEGRADE: {
        "airport": {"type": "select", "options": "airport_list", "label": "机场", "required": True},
        "runway_id": {"type": "select", "options": "runway_list", "label": "跑道", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 1, "max": 24},
    },
    AnomalyType.GATE_CLOSURE: {
        "airport": {"type": "select", "options": "airport_list", "label": "机场", "required": True},
        "gate_id": {"type": "select", "options": "gate_list", "label": "登机口", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 0.5, "max": 72},
    },
    AnomalyType.GATE_OCCUPIED: {
        "flight_id": {"type": "select", "options": "flight_list", "label": "航班", "required": True},
        "delay_minutes": {"type": "number", "label": "延误分钟", "min": 15, "max": 180, "step": 15},
    },
    AnomalyType.FLOW_CONTROL: {
        "airport": {"type": "select", "options": "airport_list", "label": "机场", "required": True},
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 0.5, "max": 12},
        "rate": {"type": "float", "label": "放行率", "min": 0.1, "max": 0.9, "default": 0.5},
    },
    AnomalyType.AIRSPACE_CLOSURE: {
        "start_time": {"type": "datetime", "label": "开始时间", "required": True},
        "duration_hours": {"type": "number", "label": "持续小时", "min": 0.5, "max": 24},
    },
}


def get_template_by_id(template_id):
    """根据 ID 查找模板"""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def get_templates_by_category(category):
    """按类别过滤模板"""
    category_prefix_map = {
        "weather": "wx",
        "aircraft": "ac",
        "crew": "cr",
        "runway": "rw",
        "gate": "gt",
        "flight": "fl",
        "airspace": "fc",
    }
    prefix = category_prefix_map.get(category, "")
    return [t for t in TEMPLATES if t["id"].startswith(prefix)]


def get_params_schema(anomaly_type):
    """获取指定异常类型的参数 Schema"""
    return ANOMALY_PARAMS_SCHEMA.get(anomaly_type, {})
