"""异常事件管理服务 - 异常事件的 CRUD 和持久化"""

import os
import json
import uuid
from datetime import datetime

from ..models.abnormal_event import AbnormalEvent, AnomalyStatus


class AnomalyService:
    """异常事件管理"""

    def __init__(self, history_dir=None):
        self._events = {}
        self._history_dir = history_dir

    def set_history_id(self, history_id, history_dir_base):
        """设置当前历史记录 ID，用于文件持久化"""
        self._current_history_id = history_id
        self._history_dir = os.path.join(history_dir_base, history_id, 'anomalies')
        os.makedirs(self._history_dir, exist_ok=True)
        # 尝试从文件加载已有事件
        self._load_from_dir()

    def create_event(self, event_type, title, description="",
                     priority="P2", affected_airports=None,
                     affected_aircraft=None, affected_crew=None,
                     affected_runways=None, affected_gates=None,
                     affected_flights=None,
                     start_time="", end_time="", duration_minutes=0,
                     delay_minutes=0, capacity_ratio=1.0,
                     extra_flight_time=0, severity=3):
        """创建异常事件"""
        event_id = str(uuid.uuid4())[:8]
        event = AbnormalEvent(
            event_id=event_id,
            event_type=event_type,
            title=title,
            description=description,
            priority=priority,
            affected_airports=affected_airports or [],
            affected_aircraft=affected_aircraft or [],
            affected_crew=affected_crew or [],
            affected_runways=affected_runways or [],
            affected_gates=affected_gates or [],
            affected_flights=affected_flights or [],
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            delay_minutes=delay_minutes,
            capacity_ratio=capacity_ratio,
            extra_flight_time=extra_flight_time,
            severity=severity,
            status=AnomalyStatus.PENDING,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._events[event_id] = event
        self._save_event(event)
        return event

    def get_event(self, event_id):
        """获取单个异常事件"""
        return self._events.get(event_id)

    def list_events(self, status_filter=None):
        """获取异常事件列表"""
        events = list(self._events.values())
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",")]
            events = [e for e in events if e.status in statuses]
        # 按创建时间降序
        events.sort(key=lambda e: e.created_at, reverse=True)
        return events

    def update_event(self, event_id, **updates):
        """更新异常事件"""
        event = self._events.get(event_id)
        if not event:
            return None
        for key, value in updates.items():
            if hasattr(event, key):
                setattr(event, key, value)
        self._save_event(event)
        return event

    def delete_event(self, event_id):
        """删除异常事件"""
        event = self._events.pop(event_id, None)
        if event and self._history_dir:
            filepath = os.path.join(self._history_dir, f"{event_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
        return event

    def set_impact_report(self, event_id, report):
        """为事件附加影响报告"""
        event = self._events.get(event_id)
        if event:
            event.impact_report = report
            self._save_event(event)

    def set_recovery_plan(self, event_id, plan):
        """为事件附加恢复方案"""
        event = self._events.get(event_id)
        if event:
            event.recovery_plan = plan
            self._save_event(event)

    # ===== 内部方法 =====

    def _save_event(self, event):
        """持久化事件到文件"""
        if not self._history_dir:
            return
        filepath = os.path.join(self._history_dir, f"{event.event_id}.json")
        data = event.to_dict()
        if event.impact_report:
            data["impact_report"] = event.impact_report
        if event.recovery_plan:
            data["recovery_plan"] = event.recovery_plan
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_dir(self):
        """从目录加载已有事件"""
        if not self._history_dir or not os.path.exists(self._history_dir):
            return
        for filename in os.listdir(self._history_dir):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(self._history_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                event = AbnormalEvent.from_dict(data)
                self._events[event.event_id] = event
            except Exception:
                pass

    def clear(self):
        """清空所有事件（用于重置）"""
        self._events.clear()


# 全局单例
anomaly_service = AnomalyService()
