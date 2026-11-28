"""实验平台数据模型：实验记录与状态。"""

STATUS_DRAFT = 'draft'
STATUS_RUNNING = 'running'
STATUS_SUCCEEDED = 'succeeded'
STATUS_FAILED = 'failed'
STATUS_INTERRUPTED = 'interrupted'

VALID_STATUSES = (
    STATUS_DRAFT, STATUS_RUNNING, STATUS_SUCCEEDED,
    STATUS_FAILED, STATUS_INTERRUPTED,
)


class ExperimentError(Exception):
    """带字段定位的条件错误。"""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field
        self.message = message

    def to_dict(self):
        return {'field': self.field, 'message': self.message}


class ExperimentRecord:
    """一条实验记录（meta.json 的内存形态）。"""

    def __init__(self, exp_id, username, name, conditions, status=STATUS_DRAFT,
                 created_at='', started_at='', finished_at='', duration_sec=0,
                 summary=None, warnings=None, error=None, parent_id=None,
                 progress=None, replay=None):
        self.id = exp_id
        self.username = username
        self.name = name
        self.conditions = conditions
        self.status = status
        self.created_at = created_at
        self.started_at = started_at
        self.finished_at = finished_at
        self.duration_sec = duration_sec
        self.summary = summary or {}
        self.warnings = warnings or []
        self.error = error
        self.parent_id = parent_id
        self.progress = progress or {'pct': 0, 'stage': '', 'message': ''}
        self.replay = replay or {}

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'conditions': self.conditions,
            'status': self.status,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'duration_sec': self.duration_sec,
            'summary': self.summary,
            'warnings': self.warnings,
            'error': self.error,
            'parent_id': self.parent_id,
            'progress': self.progress,
            'replay': self.replay,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            exp_id=data.get('id', ''),
            username=data.get('username', ''),
            name=data.get('name', ''),
            conditions=data.get('conditions', {}),
            status=data.get('status', STATUS_DRAFT),
            created_at=data.get('created_at', ''),
            started_at=data.get('started_at', ''),
            finished_at=data.get('finished_at', ''),
            duration_sec=data.get('duration_sec', 0),
            summary=data.get('summary', {}),
            warnings=data.get('warnings', []),
            error=data.get('error'),
            parent_id=data.get('parent_id'),
            progress=data.get('progress', {}),
            replay=data.get('replay', {}),
        )

    def is_running(self):
        return self.status == STATUS_RUNNING

    def list_row(self):
        """列表页需要的精简字段。"""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status,
            'created_at': self.created_at,
            'finished_at': self.finished_at,
            'duration_sec': self.duration_sec,
            'conditions': {
                'dates': self.conditions.get('dates', []),
                'bases': self.conditions.get('bases', []),
                'fleet': self.conditions.get('fleet', {}),
                'algorithms': self.conditions.get('algorithms', {}),
                'disruption': self.conditions.get('disruption', {}),
                'seed': self.conditions.get('seed'),
            },
            'summary': self.summary,
            'warnings_count': len(self.warnings),
            'error': (self.error or {}).get('message') if self.error else '',
        }
