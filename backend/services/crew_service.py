"""机组排班算法服务
支持两种模式：
1. 逐航班贪心 (legacy) - 按航班逐个分配
2. Pairing模式 - 先生成任务链，再指派机组（国内先进算法）

机组人员按基地归属管理：
- 每个航司设有少数几个真正的基地机场（如川航：成都/重庆/昆明/宜宾/绵阳/杭州）
- 非基地机场通过就近映射归到基地（如：浦东→杭州、拉萨→成都）
- 人员名单从 backend/data/crew_roster.json 加载，保证每次一致

性能优化：
- _schedule_day: O(1) 日飞行小时查询 + 二分查找时间冲突 (O(log K))
- 替代原 O(K) 遍历 assigned_flights 和重复计算 daily_flight_hours
"""
import os
import json
import random
import bisect
from ..models.crew import CrewMember
from ..services.data_service import data_service
from ..services.pairing_service import PairingGenerator
from ..services.pairing_assigner import assign_pairings
from .experiment.seed import stable_hash

# ========== 从 roster 文件加载固定人员名单 ==========
_ROSTER_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'crew_roster.json')

def _load_roster():
    try:
        with open(_ROSTER_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

_ROSTER_DATA = _load_roster()

# 中文姓名池（仅当 roster 中人数不足时用作补充）
_SURNAMES = ['李', '王', '张', '刘', '陈', '杨', '赵', '黄', '周', '吴',
             '徐', '孙', '马', '朱', '胡', '郭', '何', '林', '罗', '高']
_GIVEN_M = ['伟', '强', '磊', '洋', '飞', '文', '明', '华', '平', '刚',
            '军', '勇', '杰', '斌', '宇', '志', '建', '国', '辉', '峰']
_GIVEN_F = ['芳', '娜', '敏', '静', '丽', '秀', '英', '娟', '萍', '婷',
            '慧', '洁', '怡', '媛', '思', '欣', '瑶', '蕾', '倩', '柳']


def get_airline_bases():
    """从 roster 数据中获取所有航司及其基地映射。
    返回: {airline_name: [base1, base2, ...]}（仅真正的基地，不含映射机场）
    """
    result = {}
    if _ROSTER_DATA:
        for airline, info in _ROSTER_DATA.get('airlines', {}).items():
            bases = list(info.get('bases', {}).keys())
            if bases:
                result[airline] = sorted(bases)
    return result


def get_airline_list():
    """获取所有可用的航司名称列表"""
    return sorted(get_airline_bases().keys())


def get_crew_by_base(base, airline='四川航空'):
    """获取指定基地的机组人员列表（按角色分组）。
    
    返回: [
        {"crew_id": "captain_0", "name": "张三", "role": "captain", "role_label": "机长"},
        ...
    ]
    """
    result = []
    # captain
    for i, name in enumerate(_get_roster_names(base, 'captains')):
        result.append({"crew_id": f"captain_{i}", "name": name, "role": "captain", "role_label": "机长"})
    # first_officer
    for i, name in enumerate(_get_roster_names(base, 'first_officers')):
        result.append({"crew_id": f"first_officer_{i}", "name": name, "role": "first_officer", "role_label": "副驾驶"})
    # purser
    for i, name in enumerate(_get_roster_names(base, 'pursers')):
        result.append({"crew_id": f"purser_{i}", "name": name, "role": "purser", "role_label": "乘务长"})
    # attendant
    for i, name in enumerate(_get_roster_names(base, 'attendants')):
        result.append({"crew_id": f"attendant_{i}", "name": name, "role": "attendant", "role_label": "乘务员"})
    return result


def find_crew_substitute(absent_name, base, role, start_time, end_time,
                         crew_pool, crew_assignments=None):
    """从同基地同角色中寻找替班人选。
    
    Args:
        absent_name: 请假人员姓名
        base: 基地
        role: 角色 (captain/first_officer/purser/attendant)
        start_time: 请假开始时间 (如 "2020-11-30 08:00")
        end_time: 请假结束时间
        crew_pool: 当前机组池 (list of CrewMember)
        crew_assignments: 已分配机组映射 {flight_id: [crew_id, ...]}
    
    Returns:
        找到的替班 CrewMember，或 None
    """
    from ..models.crew import CrewMember
    
    # 解析时间范围
    def parse_time(t_str):
        parts = t_str.replace(':', '-').replace(' ', '-').split('-')
        return (int(parts[0]), int(parts[1]), int(parts[2]),
                int(parts[3]) if len(parts) > 3 else 0)
    
    try:
        start_parts = parse_time(start_time)
        end_parts = parse_time(end_time)
        start_min = start_parts[0] * 365 * 24 * 60 + start_parts[1] * 30 * 24 * 60 + start_parts[2] * 24 * 60 + start_parts[3] * 60
        end_min = end_parts[0] * 365 * 24 * 60 + end_parts[1] * 30 * 24 * 60 + end_parts[2] * 24 * 60 + end_parts[3] * 60
    except Exception:
        start_min = 0
        end_min = float('inf')
    
    # 从同基地同角色找人
    candidates = [c for c in crew_pool
                  if c.base == base and c.role == role and c.name != absent_name]
    
    for c in candidates:
        # 检查是否在请假时段内有冲突
        has_conflict = False
        for a in c.assigned_flights:
            duty_start = a['duty_start_min']
            duty_end = a['duty_end_min']
            if duty_start < end_min and duty_end > start_min:
                has_conflict = True
                break
        if not has_conflict:
            return c
    return None


# ========== 非基地机场 → 最近基地映射 ==========
# 62个航班机场中只有以下是真正的基地，其余均映射到最近基地
_STATION_TO_BASE = {
    # ---- 成都基地覆盖 (川航主基地) ----
    # 川西
    '西昌': '成都', '康定': '成都', '稻城': '成都', '广元': '成都',
    # 川藏
    '九寨沟': '成都', '林芝': '成都', '拉萨': '成都',
    # 川南
    '泸州': '成都', '攀枝花': '成都',
    # 西北
    '西宁': '成都', '兰州': '成都', '银川': '成都', '中卫': '成都', '夏河': '成都',
    # 华北边缘
    '呼和浩特': '成都', '鄂尔多斯': '成都', '邯郸': '成都', '吕梁': '成都',
    # 东北边缘
    '大连': '成都', '长春': '成都', '铁岭': '成都', '鞍山': '成都',
    # 云南边缘
    '文山': '成都',

    # ---- 北京基地覆盖 (国航/南航/东航/海航/首都航主基地) ----
    '天津': '北京',
    # 东北
    '沈阳': '北京', '大连': '北京', '长春': '北京', '铁岭': '北京', '鞍山': '北京',
    # 华北
    '呼和浩特': '北京', '鄂尔多斯': '北京', '邯郸': '北京', '吕梁': '北京',
    # 山东
    '济南': '北京', '青岛': '北京', '烟台': '北京',
    # 西北
    '西安': '北京', '兰州': '北京', '西宁': '北京', '银川': '北京', '中卫': '北京', '夏河': '北京',
    # 新疆
    '乌鲁木齐': '北京', '喀什': '北京',

    # ---- 上海基地覆盖 (东航主基地) ----
    '浦东': '上海', '南通': '上海', '常州': '上海',
    '宁波': '上海', '舟山': '上海',
    '合肥': '上海', '阜阳': '上海',
    '南京': '上海', '徐州': '上海',

    # ---- 广州/深圳基地覆盖 (南航主基地) ----
    '珠海': '深圳', '南宁': '深圳', '北海': '深圳',
    '揭阳': '深圳', '三亚': '深圳', '琼海': '深圳',
    '海口': '深圳', '武汉': '深圳', '神农架': '深圳',
    '厦门': '深圳', '长沙': '深圳',

    # ---- 昆明基地覆盖 ----
    '丽江': '昆明', '西双版纳': '昆明', '芒市': '昆明', '普洱': '昆明',

    # ---- 杭州基地覆盖 ----
    '浦东': '杭州', '宁波': '杭州', '温州': '杭州', '舟山': '杭州',
    '南通': '杭州', '常州': '杭州', '徐州': '杭州',
    '合肥': '杭州', '阜阳': '杭州',
    '南昌': '杭州', '上饶': '杭州',
    '厦门': '杭州', '福州': '杭州',
    '济南': '杭州', '青岛': '杭州', '烟台': '杭州',
    '南京': '杭州',

    # ---- 西安基地覆盖 ----
    '兰州': '西安', '西宁': '西安', '银川': '西安', '中卫': '西安',

    # ---- 重庆基地覆盖 ----
    '武汉': '重庆', '神农架': '重庆',
    '揭阳': '重庆', '三亚': '重庆', '琼海': '重庆',

    # ---- 海口基地覆盖 ----
    '三亚': '海口', '琼海': '海口', '南宁': '海口', '北海': '海口',
}

# 所有真正的基地机场集合
def _all_real_bases():
    bases = set()
    for airline_bases in get_airline_bases().values():
        bases.update(airline_bases)
    return bases


def _find_nearest_base(airport):
    """将任一机场解析到其对应的基地。
    - 如果自身就是基地，直接返回
    - 否则查找 _STATION_TO_BASE 映射
    - 兜底返回成都
    """
    if airport in _all_real_bases():
        return airport
    return _STATION_TO_BASE.get(airport, '成都')


def _get_roster_names(base, role):
    """从预设名单中取出指定基地+角色的人员姓名列表"""
    if not _ROSTER_DATA:
        return []
    try:
        airlines = _ROSTER_DATA.get('airlines', {})
        for airline_name, info in airlines.items():
            base_data = info.get('bases', {}).get(base)
            if base_data:
                return base_data.get(role, [])
        return []
    except Exception:
        return []


class CrewSchedulingService:
    """机组排班服务

    rng_seed: 可选的实验种子。为 None 时保持现场行为（键相同则结果稳定），
    但不再使用进程相关的内置 hash()，改为跨进程稳定的 crc32。
    """

    def __init__(self, rng_seed=None):
        self._crew_pool = None
        self._base_pools = {}
        self._cache_key = None
        self._pool_id_counter = 0
        self._locked_teams = {}    # team_id → [crew_id, ...]，手工指派的锁定团队
        self._rng_seed = rng_seed
        self._rng = random.Random(0)

    def _reseed(self, key):
        """按业务键 + 实验种子重建实例级 RNG，不触碰全局 random。"""
        seed_val = stable_hash(f"{key}|{self._rng_seed}", 100000) + 2024
        self._rng = random.Random(seed_val)
        return seed_val

    # ========== 机组池生成 ==========

    def generate_crew_pool(self, base='成都', airline='四川航空'):
        """生成指定基地的机组人员池（严格从 roster 预设名单加载，人数固定）"""
        crew = []
        # 从 roster 取预设姓名
        cap_names = _get_roster_names(base, 'captains')
        off_names = _get_roster_names(base, 'first_officers')
        pur_names = _get_roster_names(base, 'pursers')
        att_names = _get_roster_names(base, 'attendants')

        quals = _ROSTER_DATA.get('qualifications', {}) if _ROSTER_DATA else {}
        limits = _ROSTER_DATA.get('limits', {}) if _ROSTER_DATA else {}

        for name in cap_names:
            crew.append(CrewMember(
                crew_id=self._pool_id_counter, name=name, role='captain',
                qualifications=quals.get('captains', ['A319', 'A320']),
                base=base, airline=airline,
                max_daily_hours=limits.get('max_daily_hours', 8),
                max_duty_hours=limits.get('max_duty_hours', 14)))
            self._pool_id_counter += 1
        for name in off_names:
            crew.append(CrewMember(
                crew_id=self._pool_id_counter, name=name, role='first_officer',
                qualifications=quals.get('first_officers', ['A319', 'A320']),
                base=base, airline=airline,
                max_daily_hours=limits.get('max_daily_hours', 8),
                max_duty_hours=limits.get('max_duty_hours', 14)))
            self._pool_id_counter += 1
        for name in pur_names:
            crew.append(CrewMember(
                crew_id=self._pool_id_counter, name=name, role='purser',
                qualifications=quals.get('pursers', ['A319']),
                base=base, airline=airline,
                max_daily_hours=limits.get('max_daily_hours', 8),
                max_duty_hours=limits.get('max_duty_hours', 14)))
            self._pool_id_counter += 1
        for name in att_names:
            crew.append(CrewMember(
                crew_id=self._pool_id_counter, name=name, role='attendant',
                qualifications=quals.get('attendants', ['A319', 'A320']),
                base=base, airline=airline,
                max_daily_hours=limits.get('max_daily_hours', 8),
                max_duty_hours=limits.get('max_duty_hours', 14)))
            self._pool_id_counter += 1
        return crew

    def _ensure_base_pools(self, flights, target_airport=None):
        if not flights:
            return
        if target_airport:
            base = _find_nearest_base(target_airport)
            bases_to_gen = {base}
        else:
            base_flight_count = {}
            for f in flights:
                b = _find_nearest_base(f.departure_airport)
                base_flight_count[b] = base_flight_count.get(b, 0) + 1
            bases_to_gen = set(base_flight_count.keys())

        for base in bases_to_gen:
            if base in self._base_pools:
                continue
            pool = self.generate_crew_pool(base=base, airline='四川航空')
            self._base_pools[base] = pool

    def _assemble_crew_pool(self, target_airport=None):
        if target_airport:
            base = _find_nearest_base(target_airport)
            self._crew_pool = self._base_pools.get(base, [])
        else:
            self._crew_pool = []
            for pool in self._base_pools.values():
                self._crew_pool.extend(pool)

    # ========== 贪心排班 ==========

    def schedule_crew(self, target_airport=None, date=None, flights=None):
        if flights is None:
            data_service.load_all()
            flights = sorted(data_service.flights, key=lambda f: f.departure_minutes)
        else:
            flights = sorted(flights, key=lambda f: f.departure_minutes)

        if target_airport:
            flights = [f for f in flights
                       if f.departure_airport == target_airport
                       or f.arrival_airport == target_airport]
        if date:
            flights = [f for f in flights if self._flight_date_key(f) == date]
        if not flights:
            return []

        new_key = (target_airport or '', date or '')
        self._reseed(new_key)

        if new_key != self._cache_key:
            self._base_pools = {}
            self._crew_pool = None
            self._cache_key = new_key
            self._locked_teams = {}
            if hasattr(self, '_locked_team_dates'):
                self._locked_team_dates = {}
        if not self._crew_pool:
            self._ensure_base_pools(flights, target_airport)
            self._assemble_crew_pool(target_airport)

        # 按日期分组
        flights_by_date = {}
        for f in flights:
            dkey = self._flight_date_key(f)
            flights_by_date.setdefault(dkey, []).append(f)

        # 清空分配
        for m in self._crew_pool:
            m.assigned_flights = []

        # 跨天位置追踪：初始位置 = 各人基地
        crew_positions = {c.crew_id: (c.base if c.base else target_airport) for c in self._crew_pool}

        # 逐日分配（核心优化点）
        for dkey, day_flights in flights_by_date.items():
            self._schedule_day_fast(day_flights, dkey, crew_positions)

        return self._crew_pool

    def _schedule_day_fast(self, flights, date_key, crew_positions=None):
        """优化版日调度。

        运行时状态表：
        - daily_hours/ duty_bounds/ crew_starts/ crew_ends: 日时间追踪
        - crew_chains: 日机场衔接
        - crew_positions: 跨天位置 {crew_id: last_airport}，传入&原地更新
        """
        captains = [c for c in self._crew_pool if c.role == 'captain']
        officers = [c for c in self._crew_pool if c.role == 'first_officer']
        pursers = [c for c in self._crew_pool if c.role == 'purser']
        attendants = [c for c in self._crew_pool if c.role == 'attendant']

        daily_hours = {c.crew_id: {} for c in self._crew_pool}
        duty_bounds = {c.crew_id: {} for c in self._crew_pool}
        crew_starts = {c.crew_id: [] for c in self._crew_pool}
        crew_ends = {c.crew_id: [] for c in self._crew_pool}
        crew_chains = {c.crew_id: {} for c in self._crew_pool}

        for f in flights:
            dep = f.departure_minutes
            arr = f.arrival_minutes
            flight_hours = f.timespan / 60.0
            dep_ap = f.departure_airport
            arr_ap = f.arrival_airport

            cap = _pick_fast(captains, f, dep, arr, flight_hours, date_key,
                             dep_ap, arr_ap,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains, crew_positions)
            off = _pick_fast(officers, f, dep, arr, flight_hours, date_key,
                             dep_ap, arr_ap,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains, crew_positions)
            pur = _pick_fast(pursers, f, dep, arr, flight_hours, date_key,
                             dep_ap, arr_ap,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains, crew_positions)

            if cap and off and pur:
                cap.add_flight(f, dep, arr)
                _assign_fast(cap, f, dep, arr, flight_hours, date_key,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains)
                off.add_flight(f, dep, arr)
                _assign_fast(off, f, dep, arr, flight_hours, date_key,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains)
                pur.add_flight(f, dep, arr)
                _assign_fast(pur, f, dep, arr, flight_hours, date_key,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains)

                # 乘务员也优先位置匹配
                count = 0
                # 先收集可用乘务员，按位置匹配优先
                avail_atts = []
                for att in attendants:
                    if _is_avail_fast(att, dep, arr, flight_hours, date_key,
                                      dep_ap, arr_ap,
                                      daily_hours, duty_bounds, crew_starts, crew_ends,
                                      crew_chains):
                        pos_ok = True
                        if crew_positions is not None:
                            cur_pos = crew_positions.get(att.crew_id)
                            if cur_pos is not None and cur_pos != dep_ap:
                                pos_ok = False
                        avail_atts.append((att, pos_ok))
                # 位置匹配优先
                avail_atts.sort(key=lambda x: (0 if x[1] else 1))
                for att, _ in avail_atts:
                    att.add_flight(f, dep, arr)
                    _assign_fast(att, f, dep, arr, flight_hours, date_key,
                                 daily_hours, duty_bounds, crew_starts, crew_ends,
                                 crew_chains)
                    count += 1
                    if count >= 2:
                        break

        # 日结束：更新跨天位置
        if crew_positions is not None:
            for c in self._crew_pool:
                chain = crew_chains.get(c.crew_id, {}).get(date_key, [])
                if chain:
                    crew_positions[c.crew_id] = chain[-1][1]  # 最后一段的到达机场

    def _flight_date_key(self, f):
        y, m, d, *_ = f.time_departure
        return f"{y}-{m:02d}-{d:02d}"

    # ========== 合规报告 ==========

    def get_compliance_report(self):
        if not self._crew_pool:
            return {'violations': [], 'summary': '无排班数据'}
        all_violations = []
        for c in self._crew_pool:
            vs = c.is_over_limit()
            if vs:
                all_violations.append({
                    'crew_name': c.name, 'role': c.role_label, 'violations': vs})
        total_crew = len(self._crew_pool)
        assigned = sum(1 for c in self._crew_pool if c.assigned_flights)
        return {
            'total_crew': total_crew, 'assigned_crew': assigned,
            'total_violations': len(all_violations), 'violations': all_violations,
            'summary': f'{total_crew} 名机组, {assigned} 人已排班, {len(all_violations)} 项违规'}

    # ========== 机组团队检测 ==========

    def compute_team_groups(self, crew_substitutions=None):
        """根据已分配航班检测机组团队。

        以机长为核心，按航班重叠度匹配队员。
        当有替班变更时，排除替班航班来计算重叠度，
        避免替班机长因替班航班而强行绑定不属于他的队员。

        Args:
            crew_substitutions: 替班变更列表（可选），用于构建替班组
        """
        if not self._crew_pool:
            return [], {}

        for c in self._crew_pool:
            c.team_id = -1

        # 如果有替班变更，提取替班航班ID和替班映射
        substituted_flight_ids = set()
        substitute_map = {}  # absent_name → substitute_name
        if crew_substitutions:
            for sub in crew_substitutions:
                fid = str(sub.get('flight_id', ''))
                if fid:
                    substituted_flight_ids.add(fid)
                old = sub.get('old_value', '')
                new = sub.get('new_value', '')
                if old and new:
                    absent_name = old.split('(')[0].strip()
                    new_name = new.split('(')[0].strip()
                    if absent_name not in substitute_map:
                        substitute_map[absent_name] = new_name

        # 计算每个人的航班集合
        crew_fid_sets = {}
        for c in self._crew_pool:
            fids = set()
            for a in (c.assigned_flights or []):
                fid = str(a['flight'].flight_id if isinstance(a, dict) else getattr(a, 'flight_id', ''))
                if fid:
                    fids.add(fid)
            if fids:
                crew_fid_sets[c] = frozenset(fids)

        # 分离机长和队员
        captains = [c for c in self._crew_pool if c.role == 'captain' and c in crew_fid_sets]
        non_captains = [c for c in self._crew_pool if c.role != 'captain' and c in crew_fid_sets]

        # 为每个机长找最佳匹配队员（按重叠航班数）
        # 关键：每个非机长队员分配给与其重叠度最高的机长，
        # 而不是被航班最多的机长抢先抓走所有队员
        # 有替班时排除替班航班再计算重叠度
        nc_to_best_cap = {}  # nc → (cap, score)
        for nc in non_captains:
            nc_fids = crew_fid_sets[nc]
            nc_match_fids = nc_fids - substituted_flight_ids if substituted_flight_ids else nc_fids
            if not nc_match_fids:
                nc_match_fids = nc_fids

            best_cap = None
            best_score = 0
            for cap in captains:
                cap_fids = crew_fid_sets[cap]
                match_fids = cap_fids - substituted_flight_ids if substituted_flight_ids else cap_fids
                if not match_fids:
                    match_fids = cap_fids
                overlap = len(match_fids & nc_match_fids)
                if overlap > 0:
                    score = overlap / max(len(match_fids), len(nc_match_fids))
                    if score > best_score:
                        best_score = score
                        best_cap = cap
            if best_cap:
                nc_to_best_cap[nc] = (best_cap, best_score)

        captain_teams = {cap: [] for cap in captains}  # captain → [members]
        for nc, (cap, _score) in nc_to_best_cap.items():
            captain_teams[cap].append(nc)

        # 从机长团队中组建标准 5 人组
        team_groups = []
        team_id = 0

        for cap in sorted(captains, key=lambda c: -len(crew_fid_sets[c])):
            members = captain_teams.get(cap, [])
            offs = [m for m in members if m.role == 'first_officer']
            purs = [m for m in members if m.role == 'purser']
            atts = [m for m in members if m.role == 'attendant']

            while offs and purs and len(atts) >= 2:
                off = offs.pop(0)
                pur = purs.pop(0)
                att1 = atts.pop(0)
                att2 = atts.pop(0)

                for m in (cap, off, pur, att1, att2):
                    m.team_id = team_id

                team_groups.append({
                    'team_id': team_id,
                    'shared_flights': len(crew_fid_sets[cap]),
                    'captain': cap.name,
                    'captain_id': cap.crew_id,
                    'officer': off.name,
                    'officer_id': off.crew_id,
                    'purser': pur.name,
                    'purser_id': pur.crew_id,
                    'attendants': [att1.name, att2.name],
                    'attendant_ids': [att1.crew_id, att2.crew_id],
                })
                team_id += 1

        # 构建替班组：替班机长 + 原机长队员
        if crew_substitutions and substitute_map:
            for absent_name, sub_name in substitute_map.items():
                # 从已构建的团队中找到请假机长的原始团队
                absent_team = next((t for t in team_groups
                                    if not t.get('is_substitute') and t.get('captain') == absent_name), None)
                if not absent_team:
                    continue

                # 替班机长
                sub_cap = next((c for c in self._crew_pool
                                if c.name == sub_name and c.role == 'captain'), None)

                team_groups.append({
                    'team_id': team_id,
                    'shared_flights': len(crew_substitutions),
                    'captain': sub_name,
                    'captain_id': sub_cap.crew_id if sub_cap else -1,
                    'officer': absent_team['officer'],
                    'officer_id': absent_team['officer_id'],
                    'purser': absent_team['purser'],
                    'purser_id': absent_team['purser_id'],
                    'attendants': absent_team['attendants'],
                    'attendant_ids': absent_team['attendant_ids'],
                    'is_substitute': True,
                    'substitute_for': absent_name,
                })
                team_id += 1

        return team_groups, {}

    def _reassign_team_ids(self):
        """根据 assigned_flights 重新分配 team_id（调换人员后调用）"""
        from collections import defaultdict
        for c in self._crew_pool:
            c.team_id = -1

        groups = defaultdict(list)
        for c in self._crew_pool:
            fid_set = frozenset(a['flight'].flight_id for a in c.assigned_flights)
            if not fid_set:
                continue
            groups[fid_set].append(c)

        tid = 0
        for fid_set, members in sorted(groups.items(), key=lambda x: -len(x[0])):
            caps   = [m for m in members if m.role == 'captain']
            offs   = [m for m in members if m.role == 'first_officer']
            purs   = [m for m in members if m.role == 'purser']
            atts   = [m for m in members if m.role == 'attendant']

            while caps and offs and purs and len(atts) >= 2:
                for m in (caps.pop(), offs.pop(), purs.pop(), atts.pop(), atts.pop()):
                    m.team_id = tid
                tid += 1

    def _get_dates_for_airport(self, target_airport):
        data_service.load_all()
        dates = set()
        for f in data_service.flights:
            if (not target_airport
                    or f.departure_airport == target_airport
                    or f.arrival_airport == target_airport):
                dates.add(self._flight_date_key(f))
        return sorted(dates)

    def get_available_bases(self, airline=None):
        """获取可用基地列表（可指定航司筛选）"""
        airline_bases = get_airline_bases()
        if airline and airline in airline_bases:
            return airline_bases[airline]

        # 无航司参数 → 返回所有基地
        roster_bases = set()
        for bases in airline_bases.values():
            roster_bases.update(bases)
        return sorted(roster_bases)

    # ========== Pairing模式排班 ==========

    def schedule_by_pairing(self, target_airport=None, date=None, flights=None):
        if flights is None:
            data_service.load_all()
            flights = sorted(data_service.flights, key=lambda f: f.departure_minutes)
        else:
            flights = sorted(flights, key=lambda f: f.departure_minutes)

        if target_airport:
            flights = [f for f in flights
                       if f.departure_airport == target_airport
                       or f.arrival_airport == target_airport]
        if date:
            flights = [f for f in flights if self._flight_date_key(f) == date]
        if not flights:
            return [], [], [], []

        new_key = (target_airport or '', date or '')
        self._reseed(new_key)
        if new_key != self._cache_key:
            self._base_pools = {}
            self._crew_pool = None
            self._cache_key = new_key
        if not self._crew_pool:
            self._ensure_base_pools(flights, target_airport)
            self._assemble_crew_pool(target_airport)

        gen = PairingGenerator(flights, preferred_base=target_airport)
        pairings = gen.generate(max_pairings=3000)

        crew_pool, assigned_info, uncovered = assign_pairings(
            pairings, flights, self._crew_pool, rng=self._rng)
        return self._crew_pool, pairings, assigned_info, uncovered

    # ========== 基于飞机链的机组排班 ==========

    def schedule_from_aircraft_chains(self, aircraft_chains, target_airport=None):
        """
        从飞机排班产出的链切割成机组pairing，再指派给机组。

        飞机链是飞机一整天的完整路线（可能10~16段），
        机组受法规限制（执勤≤14h），需要切割成2~4段的短pairing。

        :param aircraft_chains: [[Flight, ...], ...] 每个子列表是一架飞机的航班链
        :param target_airport: 筛选机场
        :return: (crew_pool, pairings, assigned_info, uncovered)
        """
        from ..models.pairing import Pairing

        if not aircraft_chains:
            return [], [], [], []

        # 收集所有航班
        all_flights = []
        for chain in aircraft_chains:
            all_flights.extend(chain)

        if not all_flights:
            return [], [], [], []

        all_flights = sorted(all_flights, key=lambda f: f.departure_minutes)

        # target_airport 用于确定机组池和覆盖统计的航班范围，
        # 但不截断飞机链（链的完整连续性不能打破）
        airport_flights = all_flights
        if target_airport:
            airport_flights = [f for f in all_flights
                               if f.departure_airport == target_airport
                               or f.arrival_airport == target_airport]
        if not airport_flights:
            return [], [], [], []

        # 初始化机组池（基于 target_airport 的航班）
        self._reseed(target_airport or '')
        self._base_pools = {}
        self._crew_pool = None
        self._cache_key = (target_airport or '', '')
        self._ensure_base_pools(airport_flights, target_airport)
        self._assemble_crew_pool(target_airport)

        # 切割飞机链 → 机组pairing（保留完整链，不按target筛选）
        pairings = []
        pid = 1

        for ac_chain in aircraft_chains:
            if not ac_chain:
                continue

            # 贪心切割：沿飞机链顺序扫描，累计执勤时间 ≤14h 为一组
            segments = []
            current_seg = [ac_chain[0]]
            seg_start_min = ac_chain[0].departure_minutes
            seg_end_min = ac_chain[0].arrival_minutes

            for f in ac_chain[1:]:
                # 下个航班会扩展执勤范围
                new_end = max(seg_end_min, f.arrival_minutes)
                duty_min = new_end - seg_start_min

                # 跨天切换点：如果过夜（间隔>6h），强制切割
                rest_gap = f.departure_minutes - seg_end_min
                if rest_gap >= 6 * 60:
                    segments.append(current_seg)
                    current_seg = [f]
                    seg_start_min = f.departure_minutes
                    seg_end_min = f.arrival_minutes
                    continue

                if duty_min <= 14 * 60:
                    current_seg.append(f)
                    seg_end_min = new_end
                else:
                    # 切割，当前航班开新段
                    segments.append(current_seg)
                    current_seg = [f]
                    seg_start_min = f.departure_minutes
                    seg_end_min = f.arrival_minutes

            if current_seg:
                segments.append(current_seg)

            # 为每个切割段创建 Pairing
            for seg in segments:
                if len(seg) < 2:
                    continue
                p = Pairing(pairing_id=pid, flights=seg, base=seg[0].departure_airport)
                pairings.append(p)
                pid += 1

        print(f"[CrewFromChains] {len(aircraft_chains)}条飞机链 → "
              f"{len(pairings)}个机组pairing")

        # 用assign_pairings指派机组
        crew_pool, assigned_info, uncovered = assign_pairings(
            pairings, all_flights, self._crew_pool, rng=self._rng)
        return self._crew_pool, pairings, assigned_info, uncovered

    # ========== 手动指派 ==========

    def assign_pairing_to_crew(self, pairing, captain_id, officer_id, purser_id, attendant_ids):
        """将指定任务链指派给指定人员组合。

        关键：这 5 人将作为一个固定机组，后续所有剩余航班也优先整组分配。

        :param pairing: Pairing 对象
        :param captain_id: 机长 crew_id
        :param officer_id: 副驾 crew_id
        :param purser_id: 乘务长 crew_id
        :param attendant_ids: 乘务员 crew_id 列表 (2人)
        :return: (success: bool, message: str, assigned_info: dict)
        """
        cap = _find_by_id(self._crew_pool, captain_id)
        off = _find_by_id(self._crew_pool, officer_id)
        pur = _find_by_id(self._crew_pool, purser_id)
        atts = [_find_by_id(self._crew_pool, aid) for aid in attendant_ids]
        atts = [a for a in atts if a is not None]

        if not cap or cap.role != 'captain':
            return False, f'机长 #{captain_id} 无效或角色不匹配', None
        if not off or off.role != 'first_officer':
            return False, f'副驾 #{officer_id} 无效或角色不匹配', None
        if not pur or pur.role != 'purser':
            return False, f'乘务长 #{purser_id} 无效或角色不匹配', None
        if len(atts) < 2:
            return False, '需要至少2名乘务员', None

        # 清除这 5 人原来的排班（他们组成新团队后全部重新分配）
        all_crew = [cap, off, pur] + atts
        for c in all_crew:
            c.assigned_flights = []
            c.team_id = -1

        # 检查时间冲突：用快速调度状态表
        daily_hours = {c.crew_id: {} for c in all_crew}
        duty_bounds = {c.crew_id: {} for c in all_crew}
        crew_starts = {c.crew_id: [] for c in all_crew}
        crew_ends = {c.crew_id: [] for c in all_crew}
        crew_chains = {c.crew_id: {} for c in all_crew}

        for f in pairing.flights:
            dep, arr = f.departure_minutes, f.arrival_minutes
            fh = f.timespan / 60.0
            dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            dep_ap = f.departure_airport
            arr_ap = f.arrival_airport

            for c in all_crew:
                if f.ac_type not in c.qualifications:
                    return False, f'{c.name} 无机型 {f.ac_type} 资质', None
                if not _is_avail_fast(c, dep, arr, fh, dk, dep_ap, arr_ap,
                                      daily_hours, duty_bounds, crew_starts, crew_ends,
                                      crew_chains):
                    return False, f'{c.name} 在 {dk} {f.flight_no} 时段冲突或超限', None

            # 全部通过 → 记录
            for c in all_crew:
                c.add_flight(f, dep, arr)
                _assign_fast(c, f, dep, arr, fh, dk,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains)

        pairing_dates = list(set(
            f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
            for f in pairing.flights
        ))

        info = {
            'pairing_id': pairing.pairing_id,
            'captain': cap.name,
            'first_officer': off.name,
            'purser': pur.name,
            'attendants': [a.name for a in atts],
            'dates': pairing_dates,
        }

        # 全局锁定：这 5 人在所有日期都是同一机组（不再限制于 pairing 的日期）
        locked_ids = [cap.crew_id, off.crew_id, pur.crew_id] + [a.crew_id for a in atts]
        team_key = len(self._locked_teams)
        self._locked_teams[team_key] = locked_ids
        # 空列表表示对所有日期生效（而非仅限定某些日期）
        if not hasattr(self, '_locked_team_dates'):
            self._locked_team_dates = {}
        self._locked_team_dates[team_key] = []   # 空=全局锁定

        # 给 5 个人打上相同的 team_id → 前端搜索任一成员都能看到全队
        for mid in locked_ids:
            for c in self._crew_pool:
                if c.crew_id == mid:
                    c.team_id = team_key
                    break

        return True, '指派成功', info

    def assign_single_flight(self, flight, captain_id, officer_id, purser_id, attendant_ids):
        """手动为单个航班分配完整的5人机组

        :param flight: Flight 对象
        """
        cap = _find_by_id(self._crew_pool, captain_id)
        off = _find_by_id(self._crew_pool, officer_id)
        pur = _find_by_id(self._crew_pool, purser_id)
        atts = [_find_by_id(self._crew_pool, aid) for aid in attendant_ids]
        atts = [a for a in atts if a is not None]

        if not cap or cap.role != 'captain':
            return False, f'机长 #{captain_id} 无效或角色不匹配', None
        if not off or off.role != 'first_officer':
            return False, f'副驾 #{officer_id} 无效或角色不匹配', None
        if not pur or pur.role != 'purser':
            return False, f'乘务长 #{purser_id} 无效或角色不匹配', None
        if len(atts) < 2:
            return False, '需要至少2名乘务员', None

        # 时间冲突检查
        all_crew = [cap, off, pur] + atts
        daily_hours = {c.crew_id: {} for c in all_crew}
        duty_bounds = {c.crew_id: {} for c in all_crew}
        crew_starts = {c.crew_id: [] for c in all_crew}
        crew_ends = {c.crew_id: [] for c in all_crew}
        crew_chains = {c.crew_id: {} for c in all_crew}

        # 载入已有分配的状态（含机场链）
        for c in all_crew:
            for a in c.assigned_flights:
                af = a['flight']
                _assign_fast(c, af, a['duty_start_min'], a['duty_end_min'],
                             af.timespan / 60.0,
                             f"{af.time_departure[0]}-{af.time_departure[1]:02d}-{af.time_departure[2]:02d}",
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains)

        dep, arr = flight.departure_minutes, flight.arrival_minutes
        fh = flight.timespan / 60.0
        dk = f"{flight.time_departure[0]}-{flight.time_departure[1]:02d}-{flight.time_departure[2]:02d}"
        dep_ap = flight.departure_airport
        arr_ap = flight.arrival_airport

        for c in all_crew:
            if flight.ac_type not in c.qualifications:
                return False, f'{c.name} 无机型 {flight.ac_type} 资质', None
            if not _is_avail_fast(c, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                return False, f'{c.name} 在 {dk} {flight.flight_no} 时段冲突或超限', None

        for c in all_crew:
            c.add_flight(flight, dep, arr)
            _assign_fast(c, flight, dep, arr, fh, dk,
                         daily_hours, duty_bounds, crew_starts, crew_ends,
                         crew_chains)

        info = {
            'flight_id': flight.flight_id,
            'flight_no': flight.flight_no,
            'captain': cap.name,
            'first_officer': off.name,
            'purser': pur.name,
            'attendants': [a.name for a in atts],
        }
        return True, '指派成功', info

    def assign_selected_pairings(self, selected_pairing_ids, pairings, flights):
        base = None
        if pairings:
            base = getattr(pairings[0], 'base', None)
        self._base_pools = {}
        self._crew_pool = None
        self._ensure_base_pools(flights, base)
        self._assemble_crew_pool(base)

        selected = [p for p in pairings if p.pairing_id in selected_pairing_ids]
        assigned = []
        captains = [c for c in self._crew_pool if c.role == 'captain']
        officers = [c for c in self._crew_pool if c.role == 'first_officer']
        pursers = [c for c in self._crew_pool if c.role == 'purser']
        attendants = [c for c in self._crew_pool if c.role == 'attendant']

        for pairing in selected:
            pairing_start = pairing.flights[0].departure_airport if pairing.flights else None

            cap = _pick_fresh(captains)
            off = _pick_fresh(officers)
            pur = _pick_fresh(pursers)
            if not cap or not off or not pur:
                break
            # 基地约束：新机组只能从自身基地出发
            if pairing_start and pairing_start not in {cap.base, off.base, pur.base}:
                continue
            for f in pairing.flights:
                dep, arr = f.departure_minutes, f.arrival_minutes
                cap.add_flight(f, dep, arr)
                off.add_flight(f, dep, arr)
                pur.add_flight(f, dep, arr)
                count = 0
                for att in attendants:
                    if _is_avail_legacy(att, dep, arr, f):
                        att.add_flight(f, dep, arr)
                        count += 1
                        if count >= 2:
                            break
            assigned.append({
                'pairing_id': pairing.pairing_id,
                'captain': cap.name, 'first_officer': off.name,
                'purser': pur.name})

        covered = set()
        for p in selected:
            covered.update(p.flight_ids())
        uncovered = [f for f in flights if f.flight_id not in covered]
        return self._crew_pool, assigned, uncovered

    def adjust_schedule(self, selected_pairing_ids, aircraft_chains, target_airport=None):
        """半自动调整：先按用户选择指派，再自动填充剩余。

        1. 从飞机链切割出所有候选 pairing
        2. 用户选择的 pairing 优先指派给机组
        3. 剩余未覆盖航班自动填充
        """
        from ..models.pairing import Pairing

        # 1. 切割飞机链 → pairing
        if not aircraft_chains:
            return [], [], [], []

        all_flights = []
        for chain in aircraft_chains:
            all_flights.extend(chain)
        if not all_flights:
            return [], [], [], []

        all_flights = sorted(all_flights, key=lambda f: f.departure_minutes)

        airport_flights = all_flights
        if target_airport:
            airport_flights = [f for f in all_flights
                               if f.departure_airport == target_airport
                               or f.arrival_airport == target_airport]
        if not airport_flights:
            return [], [], [], []

        # 初始化机组池（复用已有的 base_pools，不清空缓存以免 crew_id 不匹配）
        self._reseed(target_airport or '')
        if not self._base_pools:
            self._ensure_base_pools(airport_flights, target_airport)
        self._assemble_crew_pool(target_airport)

        # 切割
        pairings = []
        pid = 1
        for ac_chain in aircraft_chains:
            if not ac_chain:
                continue
            segments = []
            current_seg = [ac_chain[0]]
            seg_start_min = ac_chain[0].departure_minutes
            seg_end_min = ac_chain[0].arrival_minutes
            for f in ac_chain[1:]:
                new_end = max(seg_end_min, f.arrival_minutes)
                duty_min = new_end - seg_start_min
                rest_gap = f.departure_minutes - seg_end_min
                if rest_gap >= 6 * 60:
                    segments.append(current_seg)
                    current_seg = [f]
                    seg_start_min = f.departure_minutes
                    seg_end_min = f.arrival_minutes
                    continue
                if duty_min <= 14 * 60:
                    current_seg.append(f)
                    seg_end_min = new_end
                else:
                    segments.append(current_seg)
                    current_seg = [f]
                    seg_start_min = f.departure_minutes
                    seg_end_min = f.arrival_minutes
            if current_seg:
                segments.append(current_seg)
            for seg in segments:
                if len(seg) < 2:
                    continue
                p = Pairing(pairing_id=pid, flights=seg, base=seg[0].departure_airport)
                pairings.append(p)
                pid += 1

        # 2. 分离用户选择 vs 剩余
        selected_map = {p.pairing_id: p for p in pairings if p.pairing_id in selected_pairing_ids}
        remaining_pairings = [p for p in pairings if p.pairing_id not in selected_pairing_ids]
        selected = list(selected_map.values())

        # 3. 先指派用户选择的pairing → 形成固定手动机组
        assigned = []
        captains = [c for c in self._crew_pool if c.role == 'captain']
        officers = [c for c in self._crew_pool if c.role == 'first_officer']
        pursers = [c for c in self._crew_pool if c.role == 'purser']
        attendants = [c for c in self._crew_pool if c.role == 'attendant']

        # 清除现有关联
        for c in self._crew_pool:
            c.assigned_flights = []

        covered_ids = set()
        manual_teams = []  # 手动固定团队：[(cap, off, pur, att1, att2), ...]

        for pairing in selected:
            cap = _pick_fresh(captains)
            off = _pick_fresh(officers)
            pur = _pick_fresh(pursers)
            if not cap or not off or not pur:
                break
            att_list = []
            for att in attendants:
                if not att.assigned_flights:
                    att_list.append(att)
                    if len(att_list) >= 2:
                        break
            if len(att_list) < 2:
                continue
            for f in pairing.flights:
                dep, arr = f.departure_minutes, f.arrival_minutes
                cap.add_flight(f, dep, arr)
                off.add_flight(f, dep, arr)
                pur.add_flight(f, dep, arr)
                for att in att_list:
                    att.add_flight(f, dep, arr)
            assigned.append({
                'pairing_id': pairing.pairing_id,
                'captain': cap.name,
                'first_officer': off.name,
                'purser': pur.name,
            })
            covered_ids.update(pairing.flight_ids())
            # 记录固定团队
            manual_teams.append((cap, off, pur, att_list[0], att_list[1]))

        # 4. 自动填充剩余：
        #    - 手动固定团队不参与自动填充（保持不变）
        #    - 剩余未分配的crew随机组成新团队
        remaining_flights = [f for f in all_flights if f.flight_id not in covered_ids]
        if remaining_pairings and remaining_flights:
            remaining_flight_set = set(f.flight_id for f in remaining_flights)

            # 排除手动团队
            manual_team_ids = set()
            for t in manual_teams:
                for m in t:
                    manual_team_ids.add(m.crew_id)

            remaining_captains = [c for c in captains if c.crew_id not in manual_team_ids]
            remaining_officers = [c for c in officers if c.crew_id not in manual_team_ids]
            remaining_pursers = [c for c in pursers if c.crew_id not in manual_team_ids]
            remaining_atts = [c for c in attendants if c.crew_id not in manual_team_ids]
            self._rng.shuffle(remaining_captains)
            self._rng.shuffle(remaining_officers)
            self._rng.shuffle(remaining_pursers)
            self._rng.shuffle(remaining_atts)

            auto_teams = []
            max_t = min(len(remaining_captains), len(remaining_officers),
                       len(remaining_pursers), len(remaining_atts) // 2)
            for i in range(max_t):
                team = (remaining_captains[i], remaining_officers[i],
                        remaining_pursers[i], remaining_atts[i*2], remaining_atts[i*2+1])
                auto_teams.append(team)

            # 构建pairing候选
            cand_pairings = []
            for p in remaining_pairings:
                uncovered_seg = [f for f in p.flights if f.flight_id in remaining_flight_set]
                if len(uncovered_seg) >= 2:
                    new_p = Pairing(pairing_id=p.pairing_id, flights=uncovered_seg,
                                    base=uncovered_seg[0].departure_airport)
                    cand_pairings.append(new_p)

            # 链式接续分配：按出发时间排序，同团队可接续多个pairing（支持跨日）
            cand_pairings.sort(key=lambda p: p.flights[0].departure_minutes if p.flights else 0)
            auto_covered = set()
            # active: [(team_tuple, last_airport, last_arrival, day_duty_start), ...]
            active = []

            for pairing in cand_pairings:
                p_fids = set(f.flight_id for f in pairing.flights)
                if p_fids & auto_covered:
                    continue
                p_start = pairing.flights[0].departure_minutes
                p_end = max(f.arrival_minutes for f in pairing.flights)
                dep_ap = pairing.flights[0].departure_airport

                # 策略1: 找可接续的活跃团队（支持跨日）
                found_team = None
                found_idx = -1
                new_day_duty_start = 0
                for idx, (t, last_ap, last_arr, day_duty_start) in enumerate(active):
                    if last_ap != dep_ap:
                        continue
                    if p_start < last_arr + 30:
                        continue
                    gap = p_start - last_arr

                    # 跨日衔接（gap≥6h）：新执勤日
                    if gap >= 6 * 60:
                        if not _team_can_take(t, pairing.flights):
                            continue
                        found_team = t
                        new_day_duty_start = p_start
                        found_idx = idx
                        break
                    else:
                        # 同日接续：检查累计执勤≤14h
                        if max(p_end, last_arr) - day_duty_start > 14 * 60:
                            continue
                        if not _team_can_take(t, pairing.flights):
                            continue
                        found_team = t
                        new_day_duty_start = day_duty_start
                        found_idx = idx
                        break

                if found_team:
                    cap, off, pur, att1, att2 = found_team
                    for f in pairing.flights:
                        dep, arr = f.departure_minutes, f.arrival_minutes
                        cap.add_flight(f, dep, arr)
                        off.add_flight(f, dep, arr)
                        pur.add_flight(f, dep, arr)
                        att1.add_flight(f, dep, arr)
                        att2.add_flight(f, dep, arr)
                    assigned.append({
                        'pairing_id': pairing.pairing_id,
                        'captain': cap.name, 'first_officer': off.name,
                        'purser': pur.name,
                    })
                    auto_covered.update(p_fids)
                    active[found_idx] = (found_team, pairing.flights[-1].arrival_airport, p_end, new_day_duty_start)
                    continue

                # 策略2: 从基地出发 → 创建新团队
                self._rng.shuffle(auto_teams)
                for team in auto_teams:
                    if not _team_can_take(team, pairing.flights):
                        continue
                    cap, off, pur, att1, att2 = team
                    for f in pairing.flights:
                        dep, arr = f.departure_minutes, f.arrival_minutes
                        cap.add_flight(f, dep, arr)
                        off.add_flight(f, dep, arr)
                        pur.add_flight(f, dep, arr)
                        att1.add_flight(f, dep, arr)
                        att2.add_flight(f, dep, arr)
                    assigned.append({
                        'pairing_id': pairing.pairing_id,
                        'captain': cap.name, 'first_officer': off.name,
                        'purser': pur.name,
                    })
                    auto_covered.update(p_fids)
                    active.append((team, pairing.flights[-1].arrival_airport, p_end, p_start))
                    break

        # 统计最终未覆盖
        all_covered = set()
        for c in self._crew_pool:
            for af in c.assigned_flights:
                if isinstance(af, dict) and 'flight' in af:
                    all_covered.add(af['flight'].flight_id)
        uncovered = [f for f in all_flights if f.flight_id not in all_covered]

        print(f"[AdjustSchedule] 手动{len(selected)}条 + 自动填充 → "
              f"{len([c for c in self._crew_pool if c.assigned_flights])}人排班, "
              f"{len(uncovered)}航班未覆盖")

        return self._crew_pool, pairings, assigned, uncovered

    def adjust_with_manual_team(self, pairing_id, captain_id, officer_id, purser_id,
                                 attendant_ids, aircraft_chains, target_airport=None):
        """手动指定5人团队执行某条pairing，剩余pairing自动填充。

        与 adjust_schedule 的区别：用户可以指定具体哪5个人（而非系统随机选）。

        :return: (crew_pool, pairings, assigned_info, uncovered, manual_team_info)
        """
        from ..models.pairing import Pairing

        if not aircraft_chains:
            return [], [], [], [], {'error': '没有飞机链'}

        # 1. 收集航班 + 切割pairing
        all_flights = []
        for chain in aircraft_chains:
            all_flights.extend(chain)
        if not all_flights:
            return [], [], [], [], {'error': '没有航班'}
        all_flights = sorted(all_flights, key=lambda f: f.departure_minutes)

        airport_flights = all_flights
        if target_airport:
            airport_flights = [f for f in all_flights
                               if f.departure_airport == target_airport
                               or f.arrival_airport == target_airport]
        if not airport_flights:
            return [], [], [], [], {'error': f'没有{target_airport}相关航班'}

        # 初始化机组池
        self._reseed(target_airport or '')
        self._base_pools = {}
        self._crew_pool = None
        self._cache_key = (target_airport or '', '')
        self._ensure_base_pools(airport_flights, target_airport)
        self._assemble_crew_pool(target_airport)

        # 切割
        pairings = []
        pid = 1
        for ac_chain in aircraft_chains:
            if not ac_chain:
                continue
            segments, current_seg = [], [ac_chain[0]]
            seg_start_min, seg_end_min = ac_chain[0].departure_minutes, ac_chain[0].arrival_minutes
            for f in ac_chain[1:]:
                new_end = max(seg_end_min, f.arrival_minutes)
                duty_min = new_end - seg_start_min
                rest_gap = f.departure_minutes - seg_end_min
                if rest_gap >= 6 * 60:
                    segments.append(current_seg)
                    current_seg = [f]
                    seg_start_min, seg_end_min = f.departure_minutes, f.arrival_minutes
                    continue
                if duty_min <= 14 * 60:
                    current_seg.append(f)
                    seg_end_min = new_end
                else:
                    segments.append(current_seg)
                    current_seg = [f]
                    seg_start_min, seg_end_min = f.departure_minutes, f.arrival_minutes
            if current_seg:
                segments.append(current_seg)
            for seg in segments:
                if len(seg) >= 2:
                    p = Pairing(pairing_id=pid, flights=seg, base=seg[0].departure_airport)
                    pairings.append(p)
                    pid += 1

        # 2. 查找目标pairing
        target_pairing = None
        for p in pairings:
            if p.pairing_id == int(pairing_id):
                target_pairing = p
                break
        if not target_pairing:
            return [], [], [], [], {'error': f'未找到任务链 #{pairing_id}'}

        # 3. 查找5个指定成员
        cap = _find_by_id(self._crew_pool, captain_id)
        off = _find_by_id(self._crew_pool, officer_id)
        pur = _find_by_id(self._crew_pool, purser_id)
        att1 = _find_by_id(self._crew_pool, attendant_ids[0]) if len(attendant_ids) > 0 else None
        att2 = _find_by_id(self._crew_pool, attendant_ids[1]) if len(attendant_ids) > 1 else None
        for c, role, rid in [(cap, 'captain', captain_id), (off, 'first_officer', officer_id),
                              (pur, 'purser', purser_id), (att1, 'attendant', attendant_ids[0] if len(attendant_ids) > 0 else None),
                              (att2, 'attendant', attendant_ids[1] if len(attendant_ids) > 1 else None)]:
            if not c:
                return [], [], [], [], {'error': f'{role} #{rid} 不存在'}
        manual_team = (cap, off, pur, att1, att2)

        # 4. 清空所有分配，手动指派
        for c in self._crew_pool:
            c.assigned_flights = []
        for f in target_pairing.flights:
            dep, arr = f.departure_minutes, f.arrival_minutes
            cap.add_flight(f, dep, arr)
            off.add_flight(f, dep, arr)
            pur.add_flight(f, dep, arr)
            att1.add_flight(f, dep, arr)
            att2.add_flight(f, dep, arr)

        assigned = [{
            'pairing_id': target_pairing.pairing_id,
            'captain': cap.name, 'first_officer': off.name,
            'purser': pur.name,
            'attendants': [att1.name, att2.name],
        }]
        covered_ids = set(target_pairing.flight_ids())

        # 5. 自动填充剩余pairing（排除手动机组）
        remaining_pairings = [p for p in pairings if p.pairing_id != target_pairing.pairing_id]
        remaining_flights = [f for f in all_flights if f.flight_id not in covered_ids]

        if remaining_pairings and remaining_flights:
            remaining_flight_set = set(f.flight_id for f in remaining_flights)

            # 排除手动机组
            manual_ids = {cap.crew_id, off.crew_id, pur.crew_id, att1.crew_id, att2.crew_id}
            remaining_captains = [c for c in self._crew_pool if c.role == 'captain' and c.crew_id not in manual_ids]
            remaining_officers = [c for c in self._crew_pool if c.role == 'first_officer' and c.crew_id not in manual_ids]
            remaining_pursers = [c for c in self._crew_pool if c.role == 'purser' and c.crew_id not in manual_ids]
            remaining_atts = [c for c in self._crew_pool if c.role == 'attendant' and c.crew_id not in manual_ids]
            self._rng.shuffle(remaining_captains)
            self._rng.shuffle(remaining_officers)
            self._rng.shuffle(remaining_pursers)
            self._rng.shuffle(remaining_atts)

            auto_teams = []
            max_t = min(len(remaining_captains), len(remaining_officers),
                       len(remaining_pursers), len(remaining_atts) // 2)
            for i in range(max_t):
                auto_teams.append((remaining_captains[i], remaining_officers[i],
                                    remaining_pursers[i], remaining_atts[i*2], remaining_atts[i*2+1]))

            # 构建pairing候选
            cand_pairings = []
            for p in remaining_pairings:
                uncovered_seg = [f for f in p.flights if f.flight_id in remaining_flight_set]
                if len(uncovered_seg) >= 2:
                    new_p = Pairing(pairing_id=p.pairing_id, flights=uncovered_seg,
                                    base=uncovered_seg[0].departure_airport)
                    cand_pairings.append(new_p)

            cand_pairings.sort(key=lambda pp: -len(pp.flights))
            auto_covered = set()
            for pairing in cand_pairings:
                p_fids = set(f.flight_id for f in pairing.flights)
                if p_fids & auto_covered:
                    continue
                self._rng.shuffle(auto_teams)
                for team in auto_teams:
                    if not _team_can_take(team, pairing.flights):
                        continue
                    tcap, toff, tpur, tatt1, tatt2 = team
                    for f in pairing.flights:
                        dep, arr = f.departure_minutes, f.arrival_minutes
                        tcap.add_flight(f, dep, arr)
                        toff.add_flight(f, dep, arr)
                        tpur.add_flight(f, dep, arr)
                        tatt1.add_flight(f, dep, arr)
                        tatt2.add_flight(f, dep, arr)
                    assigned.append({
                        'pairing_id': pairing.pairing_id,
                        'captain': tcap.name, 'first_officer': toff.name,
                        'purser': tpur.name,
                    })
                    auto_covered.update(p_fids)
                    break

        # 统计未覆盖
        all_covered = set()
        for c in self._crew_pool:
            for af in c.assigned_flights:
                if isinstance(af, dict) and 'flight' in af:
                    all_covered.add(af['flight'].flight_id)
        uncovered = [f for f in all_flights if f.flight_id not in all_covered]

        print(f"[AdjustTeam] 手动指派{cap.name}团队→pairing#{target_pairing.pairing_id}, "
              f"{len([c for c in self._crew_pool if c.assigned_flights])}人排班, "
              f"{len(uncovered)}航班未覆盖")

        manual_info = {
            'pairing_id': target_pairing.pairing_id,
            'captain': cap.name, 'first_officer': off.name,
            'purser': pur.name, 'attendants': [att1.name, att2.name],
        }

        return self._crew_pool, pairings, assigned, uncovered, manual_info


# ========== 快速调度辅助函数 ==========

def _find_by_id(crew_pool, crew_id):
    """按 crew_id 查找机组人员"""
    for c in crew_pool:
        if c.crew_id == int(crew_id):
            return c
    return None


# 同人相邻航班最短地面间隔（分钟）
MIN_CREW_GAP = 30


def _is_avail_fast(crew, start, end, flight_hours, date_key,
                   dep_ap, arr_ap,
                   daily_hours, duty_bounds, crew_starts, crew_ends,
                   crew_chains=None):
    """O(log K) 可用性检查

    - 日飞行小时: O(1) 查表
    - 7天滚动飞行小时: O(7) 查表（CCAR-121）
    - 日执勤时间: O(1) 查表（raw 时间，不含缓冲）
    - 时间冲突: 二分查找 O(log K)，含 MIN_CREW_GAP 缓冲
    - 机场衔接: 新航班必须与当天已有航班链条衔接
    """
    # 日飞行小时上限
    cur_flight = daily_hours[crew.crew_id].get(date_key, 0)
    if cur_flight + flight_hours > crew.max_daily_hours:
        return False

    # CCAR-121: 7天滚动飞行小时 ≤ 40h
    _CK = 'CCAR121_7DAY_MAX_HOURS'
    if _CK not in daily_hours:
        daily_hours[_CK] = 40 * 60  # 缓存常量
    try:
        from datetime import datetime
        base_dt = datetime.strptime(date_key, '%Y-%m-%d')
        seven_day_sum = cur_flight + flight_hours  # 包含当前航班
        for offset in range(1, 7):
            prev_dk = (base_dt - __import__('datetime').timedelta(days=offset)).strftime('%Y-%m-%d')
            prev_h = daily_hours[crew.crew_id].get(prev_dk, 0)
            seven_day_sum += prev_h
        if seven_day_sum > daily_hours[_CK]:
            return False
    except Exception:
        pass  # 日期解析失败则跳过7天检查

    # 日执勤时间上限（使用 raw 时间，不加缓冲 — 与 DFS 生成器保持一致）
    duty_max = crew.max_duty_hours * 60
    bd = duty_bounds[crew.crew_id].get(date_key)
    if bd is not None:
        new_min = min(bd[0], start)
        new_max = max(bd[1], end)
        if new_max - new_min > duty_max:
            return False

    # 时间冲突：二分查找（用缓冲去检重叠）
    buf_start = start - MIN_CREW_GAP
    buf_end = end + MIN_CREW_GAP
    starts = crew_starts[crew.crew_id]
    ends = crew_ends[crew.crew_id]
    if starts:
        idx = bisect.bisect_left(starts, buf_start)
        if idx > 0 and buf_start < ends[idx - 1]:
            return False
        if idx < len(starts) and buf_end > starts[idx]:
            return False

    # 机场衔接检查
    if crew_chains is not None:
        chain = crew_chains.get(crew.crew_id, {}).get(date_key, [])
        if chain:
            idx = bisect.bisect_left([c[2] for c in chain], start)
            prev_flight = chain[idx - 1] if idx > 0 else None
            next_flight = chain[idx] if idx < len(chain) else None
            if prev_flight and prev_flight[1] != dep_ap:
                return False
            if next_flight and arr_ap != next_flight[0]:
                return False
        else:
            if not crew.assigned_flights and crew.base and dep_ap != crew.base:
                return False

    return True


def _pick_fast(crew_list, flight, dep, arr, flight_hours, date_key,
               dep_ap, arr_ap,
               daily_hours, duty_bounds, crew_starts, crew_ends,
               crew_chains, crew_positions=None):
    """找可用人员，优先跨天位置匹配和回基地，其次日飞行小时最少。

    评分规则（高分优先）：
    3 = 位置匹配 + 航班回到基地（完美：跨天衔接 + 当日往返）
    2 = 位置匹配（跨天衔接 OK）
    1 = 位置不匹配但回到基地（至少下天从基地出发）
    0 = 位置不匹配且不回基地（最差）

    O(C log K) — 扫描全部人员，每次检查 O(log K)
    """
    best = None
    best_score = -1
    best_hours = float('inf')
    for c in crew_list:
        if flight.ac_type not in c.qualifications:
            continue
        if not _is_avail_fast(c, dep, arr, flight_hours, date_key,
                              dep_ap, arr_ap,
                              daily_hours, duty_bounds, crew_starts, crew_ends,
                              crew_chains):
            continue

        # 评分
        score = 0
        pos_ok = True
        if crew_positions is not None:
            cur_pos = crew_positions.get(c.crew_id)
            if cur_pos is not None and cur_pos != dep_ap:
                pos_ok = False
        if pos_ok:
            score += 2       # 位置匹配 +2
        if arr_ap == c.base:
            score += 1       # 回到基地 +1

        cur = daily_hours[c.crew_id].get(date_key, 0)
        if score > best_score or (score == best_score and cur < best_hours):
            best_score = score
            best_hours = cur
            best = c
    return best


def _assign_fast(crew, flight, dep, arr, flight_hours, date_key,
                 daily_hours, duty_bounds, crew_starts, crew_ends,
                 crew_chains=None):
    """更新运行时状态表。

    - duty_bounds 存 raw 时间 [earliest_dep, latest_arr]（用于日执勤限制检查）
    - crew_starts/crew_ends 存缓冲时间 [dep-30, arr+30]（用于时间冲突检查）
    - crew_chains 存机场衔接信息 [(dep_ap, arr_ap, dep, arr), ...]

    注意：不在此处调用 crew.add_flight()，调用方必须自行管理 assigned_flights。
    """
    # 更新日飞行小时
    hrs = daily_hours[crew.crew_id]
    hrs[date_key] = hrs.get(date_key, 0) + flight_hours

    # 更新日执勤范围（raw 时间，不加缓冲）
    bd = duty_bounds[crew.crew_id].get(date_key)
    if bd is None:
        duty_bounds[crew.crew_id][date_key] = [dep, arr]
    else:
        if dep < bd[0]:
            bd[0] = dep
        if arr > bd[1]:
            bd[1] = arr

    # 缓冲区间（用于时间冲突检查二分插入）
    buf_start = dep - MIN_CREW_GAP
    buf_end = arr + MIN_CREW_GAP
    starts = crew_starts[crew.crew_id]
    ends = crew_ends[crew.crew_id]
    idx_time = bisect.bisect_left(starts, buf_start)
    starts.insert(idx_time, buf_start)
    ends.insert(idx_time, buf_end)

    # 机场衔接：按出发时间插入
    if crew_chains is not None:
        chain = crew_chains[crew.crew_id].setdefault(date_key, [])
        dep_ap = flight.departure_airport
        arr_ap = flight.arrival_airport
        idx = bisect.bisect_left([c[2] for c in chain], dep)
        chain.insert(idx, (dep_ap, arr_ap, dep, arr))


# ========== 通用辅助函数 ==========

def _pick_fresh(crew_list):
    for c in crew_list:
        if not c.assigned_flights:
            return c
    return None


def _team_can_take(team, flights):
    """检查一个5人团队是否能承担一个pairing的所有航班。
    所有5人必须全部满足时间、资质、执勤限制、基地机场约束。

    :param team: (captain, first_officer, purser, attendant1, attendant2)
    :param flights: [Flight, ...]
    :return: bool
    """
    # 0. 基地机场约束
    #    机组只能从自身基地出发。若团队无已分配航班，第一个航班必须从基地起飞。
    #    若团队已有航班，新pairing的第一个航班必须衔接上一个到达机场。
    first_flight = flights[0]
    team_has_flights = False
    team_bases = set()
    last_arrival = None  # 团队上一个航班的到达机场（如果有的话）

    for member in team:
        team_bases.add(member.base)
        if member.assigned_flights:
            team_has_flights = True
            for af in member.assigned_flights:
                if isinstance(af, dict) and 'flight' in af:
                    # 找到最晚到达
                    arr = af['flight'].arrival_minutes
                    if last_arrival is None or arr > last_arrival[0]:
                        last_arrival = (arr, af['flight'].arrival_airport)

    if not team_has_flights:
        # 全新团队：只能在基地机场出发
        common_base = team_bases.pop() if len(team_bases) == 1 else None
        if not common_base:
            return False  # 团队成员不属于同一基地
        if first_flight.departure_airport != common_base:
            return False  # 第一个航班不从基地起飞
    else:
        # 已有航班：必须衔接
        if last_arrival and first_flight.departure_airport != last_arrival[1]:
            return False  # 新航班不与上一个航班衔接

    # 1. 资质+时间冲突检查
    for member in team:
        if not member.assigned_flights:
            continue
        # 已分配航班的时间段
        existing = []
        for af in member.assigned_flights:
            if isinstance(af, dict) and 'flight' in af:
                f = af['flight']
                existing.append((f.departure_minutes, f.arrival_minutes))
        # 检查新航班与已有航班是否有时间冲突
        for f in flights:
            if f.ac_type not in member.qualifications:
                return False
            for e_dep, e_arr in existing:
                if not (f.arrival_minutes + 30 <= e_dep or f.departure_minutes >= e_arr + 30):
                    return False

    # 检查新航班之间的同人衔接（同一人连续航班间不能冲突）
    flights_sorted = sorted(flights, key=lambda f: f.departure_minutes)
    for i in range(len(flights_sorted) - 1):
        f1, f2 = flights_sorted[i], flights_sorted[i + 1]
        if f2.departure_minutes - f1.arrival_minutes < 30:
            return False

    # 检查执勤时长：从第一班出发到最后一班到达 ≤14h
    first_dep = min(f.departure_minutes for f in flights)
    last_arr = max(f.arrival_minutes for f in flights)
    if last_arr - first_dep > 14 * 60:
        return False

    return True


def _is_avail_legacy(crew, start, end, flight):
    """传统 O(K) 检查，供手动指派等非性能敏感路径使用"""
    if flight.ac_type not in crew.qualifications:
        return False
    if crew.daily_flight_hours + flight.timespan / 60 > crew.max_daily_hours:
        return False
    for a in crew.assigned_flights:
        if not (end <= a['duty_start_min'] or start >= a['duty_end_min']):
            return False
    return True


def _pick_fast_excluding(crew_list, flight, dep, arr, flight_hours, date_key,
                         dep_ap, arr_ap,
                         daily_hours, duty_bounds, crew_starts, crew_ends,
                         crew_chains, crew_positions=None, exclude_ids=None):
    """同 _pick_fast，但跳过 exclude_ids 中的人员"""
    if exclude_ids is None:
        exclude_ids = set()
    best = None
    best_score = -1
    best_hours = float('inf')
    for c in crew_list:
        if c.crew_id in exclude_ids:
            continue
        if flight.ac_type not in c.qualifications:
            continue
        if not _is_avail_fast(c, dep, arr, flight_hours, date_key,
                              dep_ap, arr_ap,
                              daily_hours, duty_bounds, crew_starts, crew_ends,
                              crew_chains):
            continue

        score = 0
        pos_ok = True
        if crew_positions is not None:
            cur_pos = crew_positions.get(c.crew_id)
            if cur_pos is not None and cur_pos != dep_ap:
                pos_ok = False
        if pos_ok:
            score += 2
        if arr_ap == c.base:
            score += 1

        cur = daily_hours[c.crew_id].get(date_key, 0)
        if score > best_score or (score == best_score and cur < best_hours):
            best_score = score
            best_hours = cur
            best = c
    return best


# ========== 保留供外部引用的旧接口兼容 ==========

def _schedule_remain(flights, crew_pool, locked_teams=None, locked_team_dates=None):
    """团队优先贪心调度剩余航班。

    locked_teams: {team_id: [cap_id, off_id, pur_id, att1_id, att2_id]}
    锁定团队的 5 人在所有日期都是固定搭配：
    - 每个航班优先尝试分配给锁定团队（5 人全部可用才分配）
    - 锁定团队不可用则从非锁定人员中做单人分配
    """
    # 构建人员索引
    crew_index = {c.crew_id: c for c in crew_pool}

    # 从 locked_teams 构建团队对象列表
    teams = []
    locked_ids = set()
    if locked_teams:
        for tid, member_ids in locked_teams.items():
            if len(member_ids) < 5:
                continue
            cap  = crew_index.get(member_ids[0])
            off  = crew_index.get(member_ids[1])
            pur  = crew_index.get(member_ids[2])
            att1 = crew_index.get(member_ids[3])
            att2 = crew_index.get(member_ids[4])
            if cap and off and pur and att1 and att2:
                teams.append((cap, off, pur, att1, att2))
                locked_ids.update(member_ids)

    captains   = [c for c in crew_pool if c.role == 'captain']
    officers   = [c for c in crew_pool if c.role == 'first_officer']
    pursers    = [c for c in crew_pool if c.role == 'purser']
    attendants = [c for c in crew_pool if c.role == 'attendant']

    daily_hours  = {c.crew_id: {}  for c in crew_pool}
    duty_bounds  = {c.crew_id: {}  for c in crew_pool}
    crew_starts  = {c.crew_id: []  for c in crew_pool}
    crew_ends    = {c.crew_id: []  for c in crew_pool}
    crew_chains  = {c.crew_id: {}  for c in crew_pool}

    # 载入已有分配的状态
    for c in crew_pool:
        for a in c.assigned_flights:
            af = a['flight']
            adep = a['duty_start_min']
            aarr = a['duty_end_min']
            afh = af.timespan / 60.0
            adk = f"{af.time_departure[0]}-{af.time_departure[1]:02d}-{af.time_departure[2]:02d}"
            _assign_fast(c, af, adep, aarr, afh, adk,
                         daily_hours, duty_bounds, crew_starts, crew_ends,
                         crew_chains)

    # 从已有分配中推导跨天位置
    crew_positions = {}
    for c in crew_pool:
        all_chain = []
        for dk_chain in crew_chains.get(c.crew_id, {}).values():
            all_chain.extend(dk_chain)
        all_chain.sort(key=lambda x: x[2])  # 按出发时间排序
        if all_chain:
            crew_positions[c.crew_id] = all_chain[-1][1]
        elif c.base:
            crew_positions[c.crew_id] = c.base

    for f in flights:
        dep, arr = f.departure_minutes, f.arrival_minutes
        fh = f.timespan / 60.0
        dk = f"{f.time_departure[0]}-{f.time_departure[1]:02d}-{f.time_departure[2]:02d}"
        dep_ap = f.departure_airport
        arr_ap = f.arrival_airport

        # === 第 1 优先级：尝试分配给锁定团队（5 人全部可用才分配） ===
        assigned = False
        for cap, off, pur, att1, att2 in teams:
            if not _is_avail_fast(cap, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                continue
            if not _is_avail_fast(off, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                continue
            if not _is_avail_fast(pur, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                continue
            if not _is_avail_fast(att1, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                continue
            if not _is_avail_fast(att2, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                continue
            # 全员可用 → 整组分配
            for c in [cap, off, pur, att1, att2]:
                c.add_flight(f, dep, arr)
                _assign_fast(c, f, dep, arr, fh, dk,
                             daily_hours, duty_bounds, crew_starts, crew_ends,
                             crew_chains)
                crew_positions[c.crew_id] = arr_ap
            assigned = True
            break

        if assigned:
            continue

        # === 第 2 优先级：单人分配（仅从非锁定人员中选，优先位置匹配） ===
        cap = _pick_fast_excluding(captains, f, dep, arr, fh, dk,
                         dep_ap, arr_ap,
                         daily_hours, duty_bounds, crew_starts, crew_ends,
                         crew_chains, crew_positions, locked_ids)
        off = _pick_fast_excluding(officers, f, dep, arr, fh, dk,
                         dep_ap, arr_ap,
                         daily_hours, duty_bounds, crew_starts, crew_ends,
                         crew_chains, crew_positions, locked_ids)
        pur = _pick_fast_excluding(pursers, f, dep, arr, fh, dk,
                         dep_ap, arr_ap,
                         daily_hours, duty_bounds, crew_starts, crew_ends,
                         crew_chains, crew_positions, locked_ids)
        if cap and off and pur:
            cap.add_flight(f, dep, arr)
            _assign_fast(cap, f, dep, arr, fh, dk, daily_hours, duty_bounds, crew_starts, crew_ends, crew_chains)
            crew_positions[cap.crew_id] = arr_ap
            off.add_flight(f, dep, arr)
            _assign_fast(off, f, dep, arr, fh, dk, daily_hours, duty_bounds, crew_starts, crew_ends, crew_chains)
            crew_positions[off.crew_id] = arr_ap
            pur.add_flight(f, dep, arr)
            _assign_fast(pur, f, dep, arr, fh, dk, daily_hours, duty_bounds, crew_starts, crew_ends, crew_chains)
            crew_positions[pur.crew_id] = arr_ap
            count = 0
            for att in attendants:
                if att.crew_id in locked_ids:
                    continue
                if _is_avail_fast(att, dep, arr, fh, dk, dep_ap, arr_ap,
                                  daily_hours, duty_bounds, crew_starts, crew_ends,
                                  crew_chains):
                    att.add_flight(f, dep, arr)
                    _assign_fast(att, f, dep, arr, fh, dk,
                                 daily_hours, duty_bounds, crew_starts, crew_ends,
                                 crew_chains)
                    crew_positions[att.crew_id] = arr_ap
                    count += 1
                    if count >= 2:
                        break


def _pick_avail(crew_list, flight, dep, arr):
    for c in crew_list:
        if _is_avail_legacy(c, dep, arr, flight):
            return c
    return None


def _is_avail(crew, start, end, flight):
    return _is_avail_legacy(crew, start, end, flight)
