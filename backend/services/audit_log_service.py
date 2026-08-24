"""调度审计日志服务 — 记录所有调度操作的历史"""

import os
import json
import uuid
from datetime import datetime


class AuditLogService:
    """调度操作审计日志"""

    def __init__(self):
        self._logs = []
        self._log_dir = None

    def set_history_id(self, history_id, history_base):
        """设置历史记录 ID，日志写入对应目录"""
        self._log_dir = os.path.join(history_base, history_id, 'audit_logs')
        os.makedirs(self._log_dir, exist_ok=True)
        self._load_from_dir()

    def log(self, action, target_type, target_id, detail="", operator="system"):
        """记录一条调度日志"""
        entry = {
            "log_id": str(uuid.uuid4())[:8],
            "action": action,           # create_event, analyze, confirm_plan, reject_plan, execute, rollback, adjust
            "target_type": target_type,  # event, plan, flight, aircraft, crew, gate, runway
            "target_id": target_id,
            "detail": detail,
            "operator": operator,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._logs.append(entry)
        self._save_log(entry)
        return entry

    def get_logs(self, action=None, target_type=None, limit=None, offset=0):
        """查询日志"""
        result = list(self._logs)
        if action:
            result = [l for l in result if l.get("action") == action]
        if target_type:
            result = [l for l in result if l.get("target_type") == target_type]
        result.sort(key=lambda l: l.get("timestamp", ""), reverse=True)
        if offset:
            result = result[offset:]
        if limit:
            result = result[:limit]
        return result

    def clear(self):
        """清空日志"""
        self._logs.clear()

    # ===== 内部 =====

    def _save_log(self, entry):
        """持久化日志条目"""
        if not self._log_dir:
            return
        filepath = os.path.join(self._log_dir, f"{entry['log_id']}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)

    def _load_from_dir(self):
        """从目录加载日志"""
        if not self._log_dir or not os.path.exists(self._log_dir):
            return
        for filename in sorted(os.listdir(self._log_dir)):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(self._log_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self._logs.append(json.load(f))
            except Exception:
                pass


audit_log = AuditLogService()
