"""全局状态管理模块 — 统一 getter/setter，替代 app.py 中的 15+ 全局变量"""

# ==================== 航班上传 & 筛选状态 ====================
_uploaded_flights = []
_uploaded_airport_map = {}
_active_flights = []
_active_chains = []
_filtered_mode = False
_uploaded_xlsx_bytes = None
_last_upload_filename = ''
_last_upload_count = 0
_processing_progress = 0
_processing_stage = ''

# ==================== 历史记录 ====================
_current_history_id = None

# ==================== 故障恢复 ====================
_excluded_aircraft = []

# ==================== 机组替班 ====================
_active_crew_substitutions = []
_cached_crew_schedule = {}
_pre_substitution_crew_pool = None
_analysis_pending = False

# ==================== 生成来源 ====================
_generated_source = False
_passenger_index = {}
_manifest_index = {}
_generated_data = None  # 完整的航班生成结果（flights + passengers + chains）

# ==================== 缓存 ====================
_transit_cache = {}
_flight_aircraft_cache = None
_aircraft_chains_cache = None

# ==================== 天气中断联动 ====================
_province_weather = {}          # 最新省份天气快照 {省: 类型}
_weather_disruption_plan = {}   # flight_id -> {type, delay_minutes, reason, ...}


# ==================== Getter/Setter ====================

# uploaded_flights
def get_uploaded_flights():
    return _uploaded_flights

def set_uploaded_flights(value):
    global _uploaded_flights
    _uploaded_flights = value

# uploaded_airport_map
def get_uploaded_airport_map():
    return _uploaded_airport_map

def set_uploaded_airport_map(value):
    global _uploaded_airport_map
    _uploaded_airport_map = value

# active_flights
def get_active_flights():
    return _active_flights

def set_active_flights(value):
    global _active_flights
    _active_flights = value

# active_chains
def get_active_chains():
    return _active_chains

def set_active_chains(value):
    global _active_chains
    _active_chains = value

# filtered_mode
def get_filtered_mode():
    return _filtered_mode

def set_filtered_mode(value):
    global _filtered_mode
    _filtered_mode = value

# uploaded_xlsx_bytes
def get_uploaded_xlsx_bytes():
    return _uploaded_xlsx_bytes

def set_uploaded_xlsx_bytes(value):
    global _uploaded_xlsx_bytes
    _uploaded_xlsx_bytes = value

# last_upload_filename
def get_last_upload_filename():
    return _last_upload_filename

def set_last_upload_filename(value):
    global _last_upload_filename
    _last_upload_filename = value

# last_upload_count
def get_last_upload_count():
    return _last_upload_count

def set_last_upload_count(value):
    global _last_upload_count
    _last_upload_count = value

# processing_progress
def get_processing_progress():
    return _processing_progress

def set_processing_progress(value):
    global _processing_progress
    _processing_progress = value

# processing_stage
def get_processing_stage():
    return _processing_stage

def set_processing_stage(value):
    global _processing_stage
    _processing_stage = value

# current_history_id
def get_current_history_id():
    return _current_history_id

def set_current_history_id(value):
    global _current_history_id
    _current_history_id = value

# excluded_aircraft
def get_excluded_aircraft():
    return _excluded_aircraft

def set_excluded_aircraft(value):
    global _excluded_aircraft
    _excluded_aircraft = value

# active_crew_substitutions
def get_active_crew_substitutions():
    return _active_crew_substitutions

def set_active_crew_substitutions(value):
    global _active_crew_substitutions
    _active_crew_substitutions = value

# cached_crew_schedule
def get_cached_crew_schedule():
    return _cached_crew_schedule

def set_cached_crew_schedule(value):
    global _cached_crew_schedule
    _cached_crew_schedule = value

# pre_substitution_crew_pool
def get_pre_substitution_crew_pool():
    return _pre_substitution_crew_pool

def set_pre_substitution_crew_pool(value):
    global _pre_substitution_crew_pool
    _pre_substitution_crew_pool = value

# analysis_pending
def get_analysis_pending():
    return _analysis_pending

def set_analysis_pending(value):
    global _analysis_pending
    _analysis_pending = value

# transit_cache
def get_transit_cache():
    return _transit_cache

def set_transit_cache(value):
    global _transit_cache
    _transit_cache = value

# flight_aircraft_cache
def get_flight_aircraft_cache():
    return _flight_aircraft_cache

def set_flight_aircraft_cache(value):
    global _flight_aircraft_cache
    _flight_aircraft_cache = value

# aircraft_chains_cache
def get_aircraft_chains_cache():
    return _aircraft_chains_cache

def set_aircraft_chains_cache(value):
    global _aircraft_chains_cache
    _aircraft_chains_cache = value

# generated_source
def get_generated_source():
    return _generated_source

def set_generated_source(value):
    global _generated_source
    _generated_source = value

# passenger_index
def get_passenger_index():
    return _passenger_index

def set_passenger_index(value):
    global _passenger_index
    _passenger_index = value

# manifest_index
def get_manifest_index():
    return _manifest_index

def set_manifest_index(value):
    global _manifest_index
    _manifest_index = value

# generated_data
def get_generated_data():
    return _generated_data

def set_generated_data(value):
    global _generated_data
    _generated_data = value

# province_weather
def get_province_weather():
    return _province_weather

def set_province_weather(value):
    global _province_weather
    _province_weather = value

# weather_disruption_plan
def get_weather_disruption_plan():
    return _weather_disruption_plan

def set_weather_disruption_plan(value):
    global _weather_disruption_plan
    _weather_disruption_plan = value
