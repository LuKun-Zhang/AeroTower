"""实验工件存储：data/experiments/<username>/<exp_id>/ 的读写与列表。"""

import json
import os
import re
import shutil
import threading
import uuid
from datetime import datetime

from ...config import PROJECT_DIR
from ...models.experiment import ExperimentRecord, STATUS_RUNNING

BASE_DIR = os.path.join(PROJECT_DIR, 'data', 'experiments')
_ID_RE = re.compile(r'^exp_[0-9]{8}_[0-9]{6}_[0-9a-f]{4}$')
META = 'meta.json'
_IO_LOCK = threading.RLock()


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _safe_id(exp_id):
    if not _ID_RE.match(str(exp_id or '')):
        raise ValueError('非法实验 ID')
    return exp_id


def user_dir(username):
    if not re.match(r'^[A-Za-z0-9_\-]{1,32}$', str(username or '')):
        raise ValueError('非法用户名')
    return os.path.join(BASE_DIR, username)


def exp_dir(username, exp_id):
    return os.path.join(user_dir(username), _safe_id(exp_id))


def new_id():
    return 'exp_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:4]


def write_json(path, payload):
    with _IO_LOCK:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(',', ':'))
        for attempt in range(6):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 5:
                    # Windows 上目标文件被并发读时 replace 会失败，退化为原地覆盖
                    with open(path, 'w', encoding='utf-8') as fh:
                        json.dump(payload, fh, ensure_ascii=False, separators=(',', ':'))
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                    return
                threading.Event().wait(0.05)


def read_json(path, default=None):
    with _IO_LOCK:
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception:
            return default


def create(username, conditions, name=None, parent_id=None):
    exp_id = new_id()
    record = ExperimentRecord(
        exp_id=exp_id,
        username=username,
        name=name or conditions.get('name', ''),
        conditions=conditions,
        created_at=_now(),
        parent_id=parent_id,
    )
    os.makedirs(exp_dir(username, exp_id), exist_ok=True)
    save(record)
    return record


def save(record):
    write_json(os.path.join(exp_dir(record.username, record.id), META), record.to_dict())


def load(username, exp_id):
    path = os.path.join(exp_dir(username, exp_id), META)
    data = read_json(path)
    if not data:
        return None
    return ExperimentRecord.from_dict(data)


def list_for(username):
    root = user_dir(username)
    if not os.path.isdir(root):
        return []
    records = []
    for name in os.listdir(root):
        if not _ID_RE.match(name):
            continue
        record = load(username, name)
        if record:
            records.append(record)
    records.sort(key=lambda r: r.created_at or '', reverse=True)
    return records


def delete(username, exp_id):
    record = load(username, exp_id)
    if record and record.status == STATUS_RUNNING:
        raise ValueError('运行中的实验不能删除')
    path = exp_dir(username, exp_id)
    if os.path.isdir(path):
        shutil.rmtree(path)
    return True


def disk_usage(username, exp_id):
    path = exp_dir(username, exp_id)
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def artifact_path(username, exp_id, name):
    return os.path.join(exp_dir(username, exp_id), name)
