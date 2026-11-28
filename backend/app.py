"""川航航班调度系统 - Flask 后端入口（重构后：Blueprint 架构 + state 状态管理）"""
import os
import json

from flask import Flask, jsonify, request
from flask_cors import CORS

from .config import HOST, PORT, DEBUG
from .services import routing_service, runway_service, gate_service, crew_service
from .services.data_service import data_service
from .auth import USERS, verify_user, migrate_all_to_user1

# ==================== Blueprint 导入 ====================
from .routes.flight_routes import flight_bp
from .routes.aircraft_routes import aircraft_bp
from .routes.data_routes import data_bp
from .routes.schedule_routes import schedule_bp, _build_schedule_state, _on_recovery_executed, _clear_crew_substitution_cache
from .routes.crew_routes import crew_bp
from .routes.map_routes import map_bp
from .routes.anomaly_routes import anomaly_bp, set_schedule_getter, set_post_execute_handler, set_clear_crew_cache_func
from .routes.simulation_routes import simulation_bp
from .routes.generate_routes import generate_bp
from .routes.weather_routes import weather_bp
from .routes.intelligence_routes import intelligence_bp
from .routes.intelligence_extra_routes import intelligence_extra_bp
from .services.intelligence.reviews import start_monitor
from .routes.experiment_routes import experiment_bp
from .routes.experiment_run_routes import run_bp
from .routes.experiment_replay_routes import replay_bp

# ==================== Flask 应用初始化 ====================
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB upload limit
CORS(app)


@app.errorhandler(500)
def handle_500(e):
    import traceback
    tb = traceback.format_exc()
    print(f"[500 ERROR]\n{tb}", flush=True)
    return jsonify({"code": 500, "msg": f"Internal Server Error: {str(e)}"}), 500


# ==================== Blueprint 注册 ====================
app.register_blueprint(anomaly_bp, url_prefix='/api/anomaly')
app.register_blueprint(flight_bp, url_prefix='/api')
app.register_blueprint(aircraft_bp, url_prefix='/api')
app.register_blueprint(data_bp, url_prefix='/api')
app.register_blueprint(schedule_bp, url_prefix='/api')
app.register_blueprint(crew_bp, url_prefix='/api')
app.register_blueprint(map_bp, url_prefix='/api/map')
app.register_blueprint(simulation_bp, url_prefix='/api')
app.register_blueprint(generate_bp)
app.register_blueprint(weather_bp, url_prefix='/api')
app.register_blueprint(intelligence_bp, url_prefix='/api/intelligence')
app.register_blueprint(intelligence_extra_bp, url_prefix='/api/intelligence')
app.register_blueprint(experiment_bp, url_prefix='/api')
app.register_blueprint(run_bp, url_prefix='/api')
app.register_blueprint(replay_bp, url_prefix='/api')
start_monitor()


# ==================== 异常调度集成 ====================
set_schedule_getter(_build_schedule_state)
set_post_execute_handler(_on_recovery_executed)
set_clear_crew_cache_func(_clear_crew_substitution_cache)


# ==================== 持久化目录 ====================
_HISTORY_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'history')
os.makedirs(_HISTORY_BASE, exist_ok=True)

# 启动时迁移现有历史记录到 user1
try:
    migrate_all_to_user1()
except Exception as e:
    print(f"[auth] 迁移失败: {e}")


# ==================== 健康检查 ====================
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'code': 0, 'msg': 'ok'})


# ==================== 启动入口 ====================
if __name__ == '__main__':
    print("=" * 50)
    print("  川航航班调度系统 - 后端服务")
    print(f"  地址: http://{HOST}:{PORT}")
    print("=" * 50)
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
