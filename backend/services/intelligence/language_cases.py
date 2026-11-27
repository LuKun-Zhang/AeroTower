"""在1.5B运行前固定的开发与留出描述，不将答案放入模型提示。"""
DEVELOPMENT = [
    ("成都基地，客流涨两成，加一场雷暴", {"base_airport": "成都", "demand_factor": 1.2, "weather": "storm"}),
    ("北京基地，客流减少20%，大雾，48班航班", {"base_airport": "北京", "demand_factor": 0.8, "weather": "fog", "flight_count": 48}),
    ("上海基地，晴天，2条可用跑道，备用飞机3架", {"base_airport": "上海", "weather": "clear", "capacity": 2, "backup_aircraft": 3}),
    ("昆明基地，前序延误30分钟，从9点开始", {"base_airport": "昆明", "previous_delay": 30, "start_hour": 9}),
    ("广州基地，不要雷暴", {"base_airport": "广州"}),
    ("三亚基地，机场关闭120分钟", {"base_airport": "三亚", "event_type": "airport_closure", "disruption_minutes": 120}),
    ("重庆基地，客流增加10%，降雨", {"base_airport": "重庆", "demand_factor": 1.1, "weather": "rain"}),
    ("西安基地，40班航班，飞机故障", {"base_airport": "西安", "flight_count": 40, "event_type": "aircraft_failure"})
]
HOLDOUT = [
    ("成都基地，80班航班，客流增加25%，晴天", {"base_airport": "成都", "flight_count": 80, "demand_factor": 1.25, "weather": "clear"}),
    ("昆明基地，备用飞机2架，1条可用跑道", {"base_airport": "昆明", "backup_aircraft": 2, "capacity": 1}),
    ("北京基地，前序航班延误45分钟，大雾", {"base_airport": "北京", "previous_delay": 45, "weather": "fog"}),
    ("重庆基地，登机口故障，前序延误15分钟", {"base_airport": "重庆", "event_type": "gate_failure", "previous_delay": 15}),
    ("三亚基地，客流下降10%，降雪", {"base_airport": "三亚", "demand_factor": 0.9, "weather": "snow"}),
    ("西安基地，3条可用跑道，从8点开始，40班航班", {"base_airport": "西安", "capacity": 3, "start_hour": 8, "flight_count": 40}),
    ("上海基地，不要降雨，24班航班", {"base_airport": "上海", "flight_count": 24}),
    ("北京基地，晴天，备用飞机1架", {"base_airport": "北京", "weather": "clear", "backup_aircraft": 1}),
    ("广州基地，客流涨三成，机组请假", {"base_airport": "广州", "demand_factor": 1.3, "event_type": "crew_absence"}),
    ("成都基地，从6点开始，前序延误20分钟", {"base_airport": "成都", "start_hour": 6, "previous_delay": 20}),
    ("昆明基地，机场关闭150分钟，36班航班", {"base_airport": "昆明", "event_type": "airport_closure", "disruption_minutes": 150, "flight_count": 36}),
    ("重庆基地，备用机组2组，备用登机口3个", {"base_airport": "重庆", "backup_crew": 2, "backup_gates": 3}),
    ("上海基地，64班航班，降雨，客流减少15%", {"base_airport": "上海", "flight_count": 64, "weather": "rain", "demand_factor": 0.85}),
    ("西安基地", {"base_airport": "西安"}),
    ("广州基地，前序延误0分钟，58班航班", {"base_airport": "广州", "previous_delay": 0, "flight_count": 58}),
    ("三亚基地，4条可用跑道，机场关闭30分钟，客流增加5%", {"base_airport": "三亚", "capacity": 4, "event_type": "airport_closure", "disruption_minutes": 30, "demand_factor": 1.05})
]
