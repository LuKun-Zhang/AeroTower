"""用户认证模块"""
import os
import json

# 预设用户
USERS = {
    "user1": "user1",
    "user2": "user2",
}

# 历史记录数据目录（相对于 backend 目录）
def get_history_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'history')


def verify_user(username, password):
    """验证用户登录，返回用户信息或 None"""
    if username in USERS and USERS[username] == password:
        return {"username": username}
    return None


def migrate_all_to_user1():
    """将所有历史记录迁移到 user1 目录下"""
    hist_dir = get_history_dir()
    if not os.path.isdir(hist_dir):
        return

    user1_dir = os.path.join(hist_dir, 'user1')
    os.makedirs(user1_dir, exist_ok=True)

    migrated = 0
    # 遍历 history 下的一级目录，每个目录是一条历史记录
    for item in sorted(os.listdir(hist_dir)):
        item_path = os.path.join(hist_dir, item)
        # 跳过 user 目录本身和文件
        if not os.path.isdir(item_path) or item.startswith('user'):
            continue

        # 检查是否已是历史记录目录（包含 upload.xlsx 或 result.json 或 meta.json）
        has_data = any(
            os.path.exists(os.path.join(item_path, f))
            for f in ('upload.xlsx', 'result.json', 'meta.json')
        )
        if not has_data:
            continue

        target = os.path.join(user1_dir, item)
        # 如果已存在则跳过
        if os.path.exists(target):
            continue

        import shutil
        shutil.move(item_path, target)
        migrated += 1

    print(f"[auth] 迁移完成: {migrated} 条历史记录 → user1")
    return migrated


def get_user_history_dir(username):
    """获取用户的数据目录"""
    hist_dir = get_history_dir()
    return os.path.join(hist_dir, username)


def get_user_history_list(username):
    """获取指定用户的历史记录列表"""
    user_dir = get_user_history_dir(username)
    if not os.path.isdir(user_dir):
        return []

    items = []
    for hid in sorted(os.listdir(user_dir), reverse=True):
        hist_path = os.path.join(user_dir, hid)
        if not os.path.isdir(hist_path):
            continue
        meta_path = os.path.join(hist_path, 'meta.json')
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except Exception:
                pass
        items.append({
            'id': hid,
            'filename': meta.get('filename', ''),
            'upload_time': meta.get('upload_time', ''),
            'flight_count': meta.get('flight_count', 0),
            'active_count': meta.get('active_count', 0),
            'chain_count': meta.get('chain_count', 0),
        })
    # 按上传时间倒序（最新在前），无时间的排最后
    items.sort(key=lambda x: x.get('upload_time') or '', reverse=True)
    return items


def get_user_history(username, history_id):
    """获取用户指定历史记录的目录路径，返回 (hist_dir, user_dir)"""
    user_dir = get_user_history_dir(username)
    hist_dir = os.path.join(user_dir, history_id)
    if not os.path.isdir(hist_dir):
        return None, user_dir
    return hist_dir, user_dir
