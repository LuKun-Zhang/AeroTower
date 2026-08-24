# 川航调度系统 — 异常调度功能设计文档

> 版本：v2.0 | 2026-07-24 | 按开发阶段组织

---

## 一、背景与目标

### 1.1 为什么需要异常调度

当前系统完成了正常运营下的**计划排班**能力（飞机排班 → 跑道调度 → 登机口分配 → 机组排班），但航空公司每天面临大量突发事件：

- 天气异常：雷暴关闭机场、航路绕飞
- 飞机故障：AOG 停场、备降/迫降
- 机组请假：机长病假、执勤超时
- 跑道关闭：维修/事故导致不可用
- 登机口维修：廊桥故障
- 航班取消/合并/加开/延误传播
- 空域流控

这些事件通过资源依赖关系产生**级联影响**，需要一个**感知 → 分析 → 恢复 → 确认**的闭环调度能力。

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| 异常感知 | 支持 7 大类 20+ 种异常场景的模拟与录入 |
| 影响分析 | 自动计算级联波及范围，生成影响链路 |
| 自动恢复 | 局部搜索 + 重规划，生成多个候选方案 |
| 方案对比 | 恢复前后指标可视化对比 |
| 人机协同 | 审核 → 微调 → 确认 → 执行 |
| 可扩展 | 新增异常类型只需实现接口方法 |

### 1.3 异常优先级

| 优先级 | 级别 | 颜色 | 典型场景 | 响应要求 |
|--------|------|------|----------|----------|
| P0 | 紧急 | 红色 | 飞机事故/迫降、机场完全关闭 | 立即响应 |
| P1 | 严重 | 橙色 | AOG、机组缺失、跑道关闭 | 30分钟 |
| P2 | 一般 | 黄色 | 登机口维修、延误>2h、流控 | 1小时 |
| P3 | 提示 | 蓝色 | 轻微延误、机组请假(有余量) | 2小时 |

### 1.4 核心概念

| 概念 | 英文 | 说明 |
|------|------|------|
| 异常事件 | Abnormal Event | 导致排班偏离计划的突发事件 |
| 影响分析 | Impact Analysis | 计算波及范围和级联链路 |
| 恢复方案 | Recovery Plan | 针对异常的调整建议 |
| 资源替换 | Resource Replacement | 用备份资源替换不可用资源 |
| 时间平移 | Time Shifting | 航班时间顺延吸收延误 |
| 链重规划 | Chain Replanning | 重建受影响的任务链 |
| AOG | Aircraft on Ground | 飞机故障停场无法飞行 |

---

## 二、异常场景分类总览

```
异常调度场景
├── 天气异常
│   ├── 机场天气关闭（雷暴/大雾/暴雪）
│   ├── 航路天气绕飞（飞行时间延长）
│   └── 机场容量下降（起降速率减半）
│
├── 飞机故障
│   ├── 机械故障 AOG（停场维修）
│   ├── 迫降/备降（改降其他机场）
│   └── 定检延期（维修超时）
│
├── 机组异常
│   ├── 病假/事假
│   ├── 执勤超时
│   ├── 资质不匹配
│   └── 备份人员耗尽
│
├── 跑道异常
│   ├── 跑道临时关闭
│   ├── 跑道降级运行
│   └── 跑道容量下降
│
├── 登机口异常
│   ├── 登机口维修关闭
│   ├── 登机口被占用
│   └── 登机口降级
│
├── 航班异常
│   ├── 航班取消
│   ├── 航班合并
│   ├── 航班延误传播
│   └── 航班加开（补班/包机）
│
└── 空域/流控异常
    ├── 流控限制（起飞推迟）
    └── 空域临时关闭
```

---

## 三、开发阶段划分

```
Phase 0: 数据基础         Phase 1: 正向后端链路     Phase 2: 完整恢复引擎
(3天)                      (~7天)                    (~7天)
┌──────────────┐         ┌─────────────────┐       ┌─────────────────────┐
│ 异常事件模型  │   ──▶   │ 影响分析引擎     │ ──▶  │ 资源替换策略          │
│ 影响报告模型  │         │ 资源替换策略     │       │ 时间平移策略          │
│ 恢复方案模型  │         │ 恢复服务主流程    │       │ 链重规划策略          │
│ 场景模板库    │         │ 基础API接口      │       │ 航班合并/取消策略     │
│              │         │ 前端基础页面      │       │ 组合策略              │
└──────────────┘         └─────────────────┘       │ 前端可视化组件        │
                                                    └─────────────────────┘

Phase 3: 多模块联动       Phase 4: 完善与发布
(~7天)                    (~5天)
┌─────────────────────┐   ┌─────────────────────┐
│ 四大模块同步更新      │   │ 批量异常叠加         │
│ 甘特图/跑道/登机口    │   │ 方案回滚             │
│ /机组 异常标记        │   │ 人工微调（拖拽）      │
│ 地图异常可视化        │   │ 调度日志 + 历史回看   │
│ 全局告警横幅          │   │ 单元测试 + 集成测试   │
│ Vuex Store 激活      │   │                      │
└─────────────────────┘   └─────────────────────┘
```

---

## 四、Phase 0：数据基础

> **工期**：约 3 天 | **目标**：建立异常调度的数据骨架和场景模板库，为后续所有开发打好数据根基。

### 4.1 数据模型

#### 4.1.1 异常事件模型 `backend/models/abnormal_event.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class AnomalyType(Enum):
    # 天气
    WEATHER_AIRPORT_CLOSURE = "weather_airport_closure"
    WEATHER_ENROUTE = "weather_enroute"
    WEATHER_CAPACITY = "weather_capacity"
    # 飞机
    AIRCRAFT_FAILURE = "aircraft_failure"
    AIRCRAFT_DIVERSION = "aircraft_diversion"
    AIRCRAFT_MAINTENANCE = "aircraft_maintenance"
    # 机组
    CREW_ABSENCE = "crew_absence"
    CREW_OVERTIME = "crew_overtime"
    CREW_QUALIFICATION = "crew_qualification"
    # 跑道
    RUNWAY_CLOSURE = "runway_closure"
    RUNWAY_DEGRADE = "runway_degrade"
    # 登机口
    GATE_CLOSURE = "gate_closure"
    GATE_OCCUPIED = "gate_occupied"
    # 航班
    FLIGHT_CANCEL = "flight_cancel"
    FLIGHT_MERGE = "flight_merge"
    FLIGHT_ADD = "flight_add"
    FLIGHT_DELAY = "flight_delay"
    # 空域
    FLOW_CONTROL = "flow_control"
    AIRSPACE_CLOSURE = "airspace_closure"

class AnomalyPriority(Enum):
    P0_EMERGENCY = 0
    P1_CRITICAL = 1
    P2_NORMAL = 2
    P3_INFO = 3

@dataclass
class AbnormalEvent:
    event_id: str
    event_type: AnomalyType
    title: str                    # 如"成都双流机场雷暴预警"
    description: str
    priority: AnomalyPriority

    # 影响范围
    affected_airports: list[str]
    affected_aircraft: list[str]
    affected_crew: list[str]
    affected_runways: list[str]
    affected_gates: list[str]
    affected_flights: list[str]

    # 时间窗口
    start_time: str               # "YYYY-MM-DD HH:MM"
    end_time: str
    duration_minutes: int

    # 量化参数
    delay_minutes: int            # 0=完全不可用
    capacity_ratio: float         # 0.0~1.0
    extra_flight_time: int        # 航路绕飞场景

    # 状态
    status: str                   # pending / in_progress / recovered / resolved
    created_at: str
    resolved_at: Optional[str]

    # 关联（计算得出）
    impact_report: Optional[dict] = None
    recovery_plan: Optional[dict] = None
```

#### 4.1.2 影响报告模型 `backend/models/impact_report.py`

```python
@dataclass
class ImpactReport:
    report_id: str
    event_id: str

    # 直接影响
    direct_impacted_flights: list[str]
    direct_impacted_aircraft: list[str]
    direct_impacted_crew: list[str]
    direct_impacted_gates: list[str]
    direct_impacted_runways: list[str]

    # 级联链路 [{flight_id, reason, delay_minutes, level}, ...]
    cascade_chains: list[dict]

    # 汇总指标
    total_impacted_flights: int
    total_impacted_aircraft: int
    total_impacted_crew: int
    total_impacted_gates: int
    total_delay_minutes: int
    flights_to_cancel: list[str]
    crew_shortage_count: int
    gate_conflict_count: int

    # 可视化数据
    timeline_changes: dict
    resource_availability: dict
```

#### 4.1.3 恢复方案模型 `backend/models/recovery_plan.py`

```python
@dataclass
class RecoveryPlan:
    plan_id: str
    event_id: str
    strategy: str                 # 使用的恢复策略名称

    # 变更明细 [{flight_id, change_type, old_value, new_value, reason}]
    # change_type: CANCEL / DELAY / REASSIGN_AIRCRAFT / REASSIGN_CREW /
    #              REASSIGN_GATE / REASSIGN_RUNWAY / MERGE / ADD
    flight_changes: list[dict]
    aircraft_changes: list[dict]
    crew_changes: list[dict]
    gate_changes: list[dict]
    runway_changes: list[dict]

    # 方案指标
    coverage_rate: float          # 航班覆盖率
    total_delay_minutes: int
    avg_delay_minutes: float
    canceled_flights: list[str]
    added_flights: list[str]
    merged_flights: list[dict]

    # 对比
    before_metrics: dict
    after_metrics: dict
    improvement: dict

    # 状态
    status: str                   # draft / confirmed / rejected / executed
```

### 4.2 场景模板库 `backend/services/scenario_templates.py`

预置常用异常场景，前端通过 API 获取，用户可一键创建：

```python
TEMPLATES = [
    {
        "id": "wx_001", "title": "成都双流机场雷暴关闭",
        "type": "weather_airport_closure", "priority": "P1",
        "params": {"airport": "成都", "duration_hours": [1, 2, 3, 4], "capacity_ratio": 0}
    },
    {
        "id": "wx_002", "title": "重庆江北机场大雾低能见度",
        "type": "weather_capacity", "priority": "P2",
        "params": {"airport": "重庆", "duration_hours": [2, 4, 6], "capacity_ratio": 0.5}
    },
    {
        "id": "wx_003", "title": "昆明长水机场暴雪关闭",
        "type": "weather_airport_closure", "priority": "P1",
        "params": {"airport": "昆明", "duration_hours": [2, 4, 8], "capacity_ratio": 0}
    },
    {
        "id": "ac_001", "title": "A319 飞机机械故障（AOG）",
        "type": "aircraft_failure", "priority": "P1",
        "params": {"aircraft_type": "A319", "repair_hours": [2, 4, 8]}
    },
    {
        "id": "ac_002", "title": "飞机备降",
        "type": "aircraft_diversion", "priority": "P1",
        "params": {}
    },
    {
        "id": "cr_001", "title": "机长突发请假",
        "type": "crew_absence", "priority": "P2",
        "params": {"role": "captain", "count": 1}
    },
    {
        "id": "cr_002", "title": "乘务组集体请假",
        "type": "crew_absence", "priority": "P2",
        "params": {"role": "attendant", "count": 2}
    },
    {
        "id": "rw_001", "title": "成都双流 02L 跑道维修关闭",
        "type": "runway_closure", "priority": "P1",
        "params": {"airport": "成都", "duration_hours": [2, 4, 6]}
    },
    {
        "id": "gt_001", "title": "登机口廊桥故障关闭",
        "type": "gate_closure", "priority": "P2",
        "params": {"airport": "成都", "duration_hours": [2, 4, 8]}
    },
    {
        "id": "fl_001", "title": "航班取消",
        "type": "flight_cancel", "priority": "P1",
        "params": {}
    },
    {
        "id": "fl_002", "title": "航班合并（上座率低）",
        "type": "flight_merge", "priority": "P2",
        "params": {}
    },
    {
        "id": "fc_001", "title": "成都双流流控限制",
        "type": "flow_control", "priority": "P2",
        "params": {"airport": "成都", "duration_hours": [1, 2, 4], "rate": 0.5}
    },
]
```

### 4.3 新增目录结构

```
backend/
├── models/
│   ├── abnormal_event.py          # 异常事件模型
│   ├── impact_report.py           # 影响报告模型
│   └── recovery_plan.py           # 恢复方案模型
└── services/
    └── scenario_templates.py      # 场景模板库
```

### 4.4 任务清单

| 编号 | 任务 | 产出 |
|------|------|------|
| P0-1 | 创建 `abnormal_event.py` | 19 种异常类型枚举 + AbnormalEvent 数据类 |
| P0-2 | 创建 `impact_report.py` | ImpactReport 数据类 |
| P0-3 | 创建 `recovery_plan.py` | RecoveryPlan 数据类 |
| P0-4 | 创建 `scenario_templates.py` | 12 个预置场景模板 + 参数 Schema |
| P0-5 | 创建 `data/history/{id}/anomalies/` 目录 | 持久化目录结构 |

### 4.5 验收标准

- [ ] 三个模型可正常实例化、序列化/反序列化
- [ ] `GET /api/anomaly/templates` 返回 12 个模板
- [ ] 场景模板参数 Schema 通过前端动态表单验证

---

## 五、Phase 1：后端正向链路

> **工期**：约 7 天 | **目标**：打通 异常创建 → 影响分析 → 资源替换恢复 → 方案输出的完整后端链路，前端可看到基础结果。

### 5.1 新增服务文件

```
backend/services/
├── anomaly_service.py              # 异常事件 CRUD
├── impact_analysis_service.py      # 影响分析引擎
├── recovery_service.py             # 恢复主流程
├── recovery_strategies/
│   ├── __init__.py
│   ├── base_strategy.py            # 策略基类
│   └── resource_replacement.py     # Phase 1 只实现资源替换策略
└── scenario_templates.py           # Phase 0 已有
```

### 5.2 影响分析引擎 `impact_analysis_service.py`

核心算法：BFS 级联传播

```
propagate_impact(anomaly_event, current_schedule)

步骤：
  1. 直接命中 → 找出时间/空间上直接冲突的航班
  2. 资源锁定 → 标记异常涉及的飞机/机组/登机口/跑道
  3. 级联传播 (BFS) →
     queue = 直接受影响的航班
     while queue:
         flight = queue.pop()
         for next in flight.assigned_aircraft 的后缀航班:
               if next 时间偏移超过阈值:
                   impacted.append(next)
                   queue.append(next)
  4. 级联到其他资源 → 登机口冲突、机组超时、跑道序列变化
  5. 输出 ImpactReport
```

```python
class ImpactAnalysisService:

    def __init__(self, flight_service, routing_service,
                 crew_service, gate_service, runway_service):
        self.flight_service = flight_service
        self.routing_service = routing_service
        self.crew_service = crew_service
        self.gate_service = gate_service
        self.runway_service = runway_service

    def analyze(self, event: AbnormalEvent) -> ImpactReport:
        # Step 1: 直接命中
        direct_flights = self._find_direct_conflicts(event)
        # Step 2: 资源锁定
        locked_resources = self._lock_resources(event)
        # Step 3: BFS 级联传播
        cascade = self._bfs_cascade(direct_flights, locked_resources,
                                     event.duration_minutes)
        # Step 4: 其他资源级联
        gate_conflicts = self._check_gate_conflicts(cascade)
        crew_issues = self._check_crew_issues(cascade)
        runway_changes = self._check_runway_changes(cascade)
        # Step 5: 汇总
        return self._build_report(event, direct_flights, cascade,
                                   gate_conflicts, crew_issues, runway_changes)
```

### 5.3 恢复策略基类 `base_strategy.py`

```python
class BaseRecoveryStrategy:
    """所有恢复策略的基类"""

    def __init__(self, current_schedule: dict, impact: ImpactReport):
        self.schedule = current_schedule
        self.impact = impact

    def can_apply(self) -> bool:
        """策略是否适用当前场景"""
        raise NotImplementedError

    def apply(self) -> dict:
        """执行恢复，返回变更方案"""
        raise NotImplementedError

    def evaluate(self, result: dict) -> float:
        """评估恢复效果，返回 0~1 分数"""
        raise NotImplementedError
```

### 5.4 资源替换策略 `resource_replacement.py`

Phase 1 唯一实现的策略，处理最简单的恢复场景：

```python
class ResourceReplacementStrategy(BaseRecoveryStrategy):
    """
    处理逻辑（按优先级）：
    1. 飞机不可用 → 找同机型、同基地的备份飞机替换
    2. 机组不可用 → 找同资质、同基地的备份人员替换
    3. 登机口不可用 → 找同类型空闲登机口替换
    4. 跑道不可用 → 移到其他可用跑道，重新计算间隔
    """

    def can_apply(self) -> bool:
        return (self._has_backup_aircraft() or
                self._has_backup_crew() or
                self._has_backup_gates() or
                self._has_backup_runways())

    def apply(self) -> dict:
        changes = {
            "aircraft_changes": self._replace_aircraft(),
            "crew_changes": self._replace_crew(),
            "gate_changes": self._replace_gates(),
            "runway_changes": self._replace_runways(),
        }
        changes["side_effects"] = self._check_side_effects(changes)
        return changes

    def evaluate(self, result: dict) -> float:
        score = 1.0
        if result.get("side_effects"):
            score -= 0.1 * len(result["side_effects"])
        return max(0, score)
```

### 5.5 恢复服务主流程 `recovery_service.py`

```python
class RecoveryService:

    def __init__(self):
        self.impact_analyzer = ImpactAnalysisService(...)
        # Phase 1 只注册资源替换策略
        self.strategies = [ResourceReplacementStrategy]

    def recover(self, event: AbnormalEvent,
                current_schedule: dict) -> RecoveryPlan:
        # Step 1: 影响分析
        impact = self.impact_analyzer.analyze(event)

        # Step 2: 尝试各策略，选最优
        best_plan = None
        best_score = 0
        for StrategyClass in self.strategies:
            strategy = StrategyClass(current_schedule, impact)
            if strategy.can_apply():
                result = strategy.apply()
                score = strategy.evaluate(result)
                if score > best_score:
                    best_score = score
                    best_plan = self._build_plan(event, impact,
                                                  result, StrategyClass.__name__)

        return best_plan
```

### 5.6 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/anomaly/templates` | 获取场景模板列表 |
| POST | `/api/anomaly/create` | 创建异常事件 |
| GET | `/api/anomaly/list` | 获取异常事件列表 |
| GET | `/api/anomaly/<event_id>` | 获取异常事件详情 |
| PUT | `/api/anomaly/<event_id>` | 更新异常事件 |
| DELETE | `/api/anomaly/<event_id>` | 删除异常事件 |
| POST | `/api/anomaly/<event_id>/analyze` | 执行影响分析 |
| GET | `/api/anomaly/<event_id>/impact` | 获取影响报告 |
| GET | `/api/anomaly/<event_id>/cascade-tree` | 获取级联影响树数据 |
| POST | `/api/anomaly/<event_id>/recover` | 执行自动恢复 |
| GET | `/api/anomaly/<event_id>/plans` | 获取恢复方案列表 |
| GET | `/api/anomaly/<event_id>/compare` | 恢复前后指标对比 |

### 5.7 前端：RecoveryView 基础页面

```
RecoveryView.vue
├── 左侧：异常场景面板
│   ├── 场景模板列表（从 /api/anomaly/templates 加载）
│   ├── 动态参数表单（机场选择、时间、严重程度等）
│   ├── [创建异常事件] 按钮
│   └── 活跃异常事件列表
│
├── 中间：影响分析结果
│   ├── 级联影响树（ECharts 树图）
│   ├── 受影响航班列表（表格，按严重程度排序）
│   └── [执行影响分析] 按钮
│
└── 右侧：恢复方案
    ├── 恢复方案卡片（策略名称 + 覆盖率 + 延误）
    ├── 变更明细表格
    └── 指标对比图表
```

### 5.8 路由注册

```python
# backend/routes/anomaly_routes.py
# 在 app.py 中注册 blueprint
from .routes import anomaly_routes
app.register_blueprint(anomaly_routes.bp)
```

### 5.9 任务清单

| 编号 | 任务 | 产出 |
|------|------|------|
| P1-1 | 实现 `anomaly_service.py` | 异常事件 CRUD |
| P1-2 | 实现 `impact_analysis_service.py` | BFS 级联传播 + ImpactReport 输出 |
| P1-3 | 实现 `base_strategy.py` | 策略基类 + 接口契约 |
| P1-4 | 实现 `resource_replacement.py` | 资源替换逻辑（飞机/机组/登机口/跑道） |
| P1-5 | 实现 `recovery_service.py` | 主恢复流程编排 |
| P1-6 | 创建 `routes/anomaly_routes.py` | 12 个 API 接口 |
| P1-7 | 前端 `RecoveryView.vue` 基础框架 | 三栏布局 + 模板列表 + API 对接 |
| P1-8 | 前端 `ImpactTree.vue` | ECharts 级联影响树 |

### 5.10 验收标准

- [ ] 创建异常事件 → 影响分析 → 返回 ImpactReport（含 BFS 级联链路）
- [ ] 资源替换策略正确找到备份飞机/机组并生成变更方案
- [ ] `GET /api/anomaly/<id>/cascade-tree` 返回可用于 ECharts 树图的数据
- [ ] 前端页面展示异常事件列表、影响分析结果、恢复方案

---

## 六、Phase 2：完整恢复引擎

> **工期**：约 7 天 | **目标**：实现全部 5 种恢复策略 + 组合策略，前端可视化组件齐备。

### 6.1 新增服务文件

```
backend/services/recovery_strategies/
├── __init__.py
├── base_strategy.py                # Phase 1 已有
├── resource_replacement.py         # Phase 1 已有
├── time_shifting.py                # 新增
├── chain_replanning.py             # 新增
├── flight_merge_strategy.py        # 新增
└── flight_cancel_strategy.py       # 新增
```

### 6.2 新增策略

#### 6.2.1 时间平移策略 `time_shifting.py`

```
TimeShiftingStrategy

适用场景：机场短时关闭（<2h）、单航班延误、流控推迟

逻辑：
  if 延误 < 航班缓冲时间:
      直接吸收（过站时间压缩）
  elif 延误 < 2小时:
      整条飞机链顺延 → 重查衔接/登机口/机组可用性
  else:
      跳过（交给链重规划策略处理）

评分标准：总延误分钟数越少分越高
```

#### 6.2.2 链重规划策略 `chain_replanning.py`

```
ChainReplanningStrategy

适用场景：飞机长期不可用、多航班受影响、天气长时关闭

逻辑：
  1. 释放受影响飞机链上的所有航班
  2. 标记不可用资源（故障飞机、关闭跑道等）
  3. 在现有排班基础上，增量运行链集合覆盖算法
     （复用 routing_service 的 solve_chain_coverage）
  4. 保留未受影响的链，只重建受影响的链
  5. 无法覆盖的航班 → 标记"建议取消"

评分标准：航班覆盖率越高分越高
```

#### 6.2.3 航班合并策略 `flight_merge_strategy.py`

```
FlightMergeStrategy

适用场景：两班同一航线、时间接近、上座率都低

逻辑：
  1. 找出可合并的航班对（同起降机场、时间窗口接近）
  2. 合并后释放一架飞机 + 一组机组
  3. 检查合并后的容量是否满足

前置条件：需要航班有乘客数/座位数数据（当前系统缺失，Phase 2 可先做简版）
```

#### 6.2.4 航班取消策略 `flight_cancel_strategy.py`

```
FlightCancelStrategy

适用场景：无论如何都无法安排、资源严重不足

逻辑：
  1. 从无法覆盖的航班列表中，按优先级排序
     （优先取消客座率低的、有替代航班的）
  2. 取消后释放飞机 → 可能解锁其他航班
  3. 重新运行链重规划，看是否能覆盖更多航班

这是最后手段，只在其他策略都无法满足时使用。
```

### 6.3 组合策略

当单个策略无法满足时，按优先级组合：

```
恢复策略优先级（成本从低到高）：
  1. 资源替换（无连锁影响）
  2. 时间平移（有延误但不取消）
  3. 航班合并（减少资源需求）
  4. 链重排（大规模调整）
  5. 航班取消（最后手段）

组合逻辑：
  recovery_service 依次尝试 1→2→3→4→5
  每个策略评估后，如果分数 < 0.6 则叠加下一个策略
  直到分数 >= 0.6 或策略耗尽
```

### 6.4 恢复服务更新

```python
class RecoveryService:

    def __init__(self):
        # Phase 2 注册全部策略
        self.strategies = [
            ResourceReplacementStrategy,
            TimeShiftingStrategy,
            FlightMergeStrategy,
            ChainReplanningStrategy,
            FlightCancelStrategy,
        ]

    def recover(self, event, schedule) -> RecoveryPlan:
        impact = self.impact_analyzer.analyze(event)

        best_plan = None
        best_score = 0

        # 按优先级依次尝试
        for StrategyClass in self.strategies:
            strategy = StrategyClass(schedule, impact)
            if strategy.can_apply():
                result = strategy.apply()
                score = strategy.evaluate(result)
                if score > best_score:
                    best_score = score
                    best_plan = self._build_plan(...)
                # 如果分数已经够高，停止尝试
                if score >= 0.9:
                    break

        # 如果分数仍不足，启动组合策略
        if best_score < 0.6:
            best_plan = self._apply_combo_strategy(event, schedule, impact)

        # 重新调度关联资源
        if best_plan:
            self._reschedule_gates(best_plan)
            self._reschedule_crew(best_plan)
            self._reschedule_runway(best_plan)

        return best_plan
```

### 6.5 前端可视化组件

| 组件 | 文件路径 | 功能 |
|------|----------|------|
| `AnomalyPanel.vue` | `components/anomaly/AnomalyPanel.vue` | 场景模板选择 + 动态参数表单 |
| `ImpactTree.vue` | `components/anomaly/ImpactTree.vue` | ECharts 树图展示级联链路 |
| `RecoveryCompare.vue` | `components/anomaly/RecoveryCompare.vue` | 恢复前后指标对比（柱状图+表格） |
| `ChangeDetailTable.vue` | `components/anomaly/ChangeDetailTable.vue` | 变更明细表格（航班/飞机/机组/登机口/跑道） |
| `AnomalyTimeline.vue` | `components/anomaly/AnomalyTimeline.vue` | 异常事件时间线 |

### 6.6 API 新增

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/anomaly/simulate` | 模拟异常（不实际修改数据） |
| GET | `/api/anomaly/simulate/preview` | 模拟结果预览 |
| POST | `/api/anomaly/<event_id>/plans/<plan_id>/confirm` | 确认方案 |
| POST | `/api/anomaly/<event_id>/plans/<plan_id>/reject` | 拒绝方案 |

### 6.7 异常参数 Schema（前端动态表单用）

```python
# scenario_templates.py 中
ANOMALY_PARAMS_SCHEMA = {
    "weather_airport_closure": {
        "airport": {"type": "select", "options": "airport_list", "required": True},
        "start_time": {"type": "datetime", "required": True},
        "duration_hours": {"type": "number", "min": 0.5, "max": 24, "step": 0.5},
        "capacity_ratio": {"type": "float", "min": 0, "max": 1, "default": 0},
    },
    "aircraft_failure": {
        "aircraft_id": {"type": "select", "options": "aircraft_list", "required": True},
        "start_time": {"type": "datetime", "required": True},
        "repair_hours": {"type": "number", "min": 1, "max": 72},
    },
    "crew_absence": {
        "crew_id": {"type": "select", "options": "crew_list", "required": True},
        "date": {"type": "date", "required": True},
    },
    "runway_closure": {
        "airport": {"type": "select", "options": "airport_list", "required": True},
        "runway_id": {"type": "select", "options": "runway_list", "required": True},
        "start_time": {"type": "datetime", "required": True},
        "duration_hours": {"type": "number", "min": 0.5, "max": 48},
    },
    "gate_closure": {
        "airport": {"type": "select", "options": "airport_list", "required": True},
        "gate_id": {"type": "select", "options": "gate_list", "required": True},
        "start_time": {"type": "datetime", "required": True},
        "duration_hours": {"type": "number", "min": 0.5, "max": 72},
    },
    "flight_cancel": {
        "flight_id": {"type": "select", "options": "flight_list", "required": True},
        "reason": {"type": "text"},
    },
    "flow_control": {
        "airport": {"type": "select", "options": "airport_list", "required": True},
        "start_time": {"type": "datetime", "required": True},
        "duration_hours": {"type": "number", "min": 0.5, "max": 12},
        "rate": {"type": "float", "min": 0.1, "max": 0.9, "default": 0.5},
    },
}
```

### 6.8 任务清单

| 编号 | 任务 | 产出 |
|------|------|------|
| P2-1 | 实现 `time_shifting.py` | 时间平移逻辑 |
| P2-2 | 实现 `chain_replanning.py` | 链重规划（复用 routing_service） |
| P2-3 | 实现 `flight_merge_strategy.py` | 航班合并逻辑 |
| P2-4 | 实现 `flight_cancel_strategy.py` | 航班取消逻辑 |
| P2-5 | 组合策略编排 | 多策略叠加打分 |
| P2-6 | 实现 `AnomalyPanel.vue` | 场景模板 + 动态表单 |
| P2-7 | 实现 `ImpactTree.vue` | ECharts 级联树 |
| P2-8 | 实现 `RecoveryCompare.vue` | 恢复前后对比 |
| P2-9 | 实现 `ChangeDetailTable.vue` | 变更明细表 |
| P2-10 | 实现 `AnomalyTimeline.vue` | 异常时间线 |
| P2-11 | 模拟 API + 方案确认/拒绝 API | 4 个新接口 |

### 6.9 验收标准

- [ ] 5 种恢复策略均可独立运行
- [ ] 组合策略能处理飞机故障 + 机组请假同时发生的复杂场景
- [ ] 级联影响树正确展示传播链路
- [ ] 恢复前后指标对比面板正确
- [ ] 场景模板一键创建 → 自动填充参数表单

---

## 七、Phase 3：多模块联动与可视化增强

> **工期**：约 7 天 | **目标**：恢复方案确认后自动更新四大模块数据，甘特图/跑道/登机口/机组视图同步显示异常标记，地图增加异常状态渲染，全局告警横幅。

### 7.1 模块联动流程

```
用户确认恢复方案
        │
        ▼
┌───────────────────────────────────────────┐
│  POST /api/anomaly/<id>/plans/<pid>/execute │
└───────────────────┬───────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌────────┐   ┌──────────┐   ┌──────────┐
│飞机排班 │   │登机口重分配│   │机组重排班 │
│数据更新 │   │数据更新   │   │数据更新   │
└───┬────┘   └─────┬────┘   └─────┬────┘
    │              │              │
    ▼              ▼              ▼
 GanttView     GateView      CrewView
 自动刷新       自动刷新       自动刷新
    │              │              │
    └──────────────┼──────────────┘
                   ▼
            RunwayView 自动刷新
```

### 7.2 四大模块异常标记

| 模块 | 标记类型 | 视觉 | 数据来源 |
|------|----------|------|----------|
| **飞机排班** | 受异常影响 | 红色底纹 | `flight_changes` 中该飞机的航班 |
| **飞机排班** | 已恢复调整 | 蓝色底纹 | `aircraft_changes` 中被调整的链 |
| **飞机排班** | 备份飞机启用 | 绿色虚线边框 | `aircraft_changes` 中的替换 |
| **跑道调度** | 顺序变更 | 蓝色 ↑↓ 箭头 | `runway_changes` |
| **跑道调度** | 取消的起降 | 灰色删除线 | `flight_changes` 中的 CANCEL |
| **登机口分配** | 重新分配 | 蓝色背景 | `gate_changes` |
| **登机口分配** | 锁定维护中 | 红色条纹 | 异常事件的 `affected_gates` |
| **机组排班** | 人员替换 | 橙色标记 | `crew_changes` |
| **机组排班** | 超时告警 | 红色闪烁 | 影响报告中的 `crew_issues` |
| **机组排班** | 休息不足 | 黄色警告 | 影响报告中的 `crew_issues` |

### 7.3 地图异常可视化

在现有 `Map.vue` / `Map-a.vue` 中增加异常渲染：

| 状态 | 视觉表达 | 实现方式 |
|------|----------|----------|
| 机场关闭 | 红色闪烁 effectScatter | series 动态切换 |
| 机场容量下降 | 橙色半透明 | itemStyle 修改 |
| 航班延误 | 航线黄色虚线 | lineStyle.type: "dashed" |
| 航班取消 | 航线消失 | 从 series 中移除 |
| 飞机故障 | 飞机图标红色 X | symbol 替换 |
| 登机口/跑道关闭 | Tooltip 中文字标记 | tooltip formatter |

### 7.4 全局告警横幅

```vue
<!-- AnalysisApp.vue 顶部 -->
<div v-if="activeAlerts.length" class="global-alert-bar">
  <span v-for="alert in activeAlerts" :key="alert.id"
        :class="'alert-' + alert.priority">
    {{ alert.priority === 'P0' ? '🔴' : '🟠' }}
    {{ alert.title }} | 影响 {{ alert.impact_count }} 个航班
  </span>
  <el-button size="mini" @click="$router.push('/analysis/xxx?tab=recovery')">
    查看详情
  </el-button>
</div>
```

### 7.5 Vuex Store 激活

```javascript
// store/index.js
export default new Vuex.Store({
  state: {
    activeAnomalies: [],          // 活跃异常事件
    impactReports: {},            // {event_id: report}
    recoveryPlans: {},            // {event_id: [plans]}
    resourceStatus: {             // 备份资源快照
      backupAircraft: [],
      backupCrew: [],
      idleGates: [],
      availableRunways: [],
    },
    scheduleDirty: false,         // 排班是否因恢复而变更
    globalAlerts: [],             // 全局告警列表
  },
  mutations: {
    setActiveAnomalies(state, anomalies) { ... },
    setImpactReport(state, { eventId, report }) { ... },
    setRecoveryPlans(state, { eventId, plans }) { ... },
    setResourceStatus(state, status) { ... },
    setScheduleDirty(state, dirty) { ... },
    addAlert(state, alert) { ... },
    removeAlert(state, eventId) { ... },
  },
  actions: {
    async createAnomaly({ commit }, params) { ... },
    async runImpactAnalysis({ commit }, eventId) { ... },
    async runRecovery({ commit }, eventId) { ... },
    async confirmPlan({ commit }, { eventId, planId }) { ... },
    async executePlan({ commit }, { eventId, planId }) { ... },
  },
})
```

### 7.6 备份资源管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/resource/backup-aircraft` | 查询可用备份飞机 |
| GET | `/api/resource/backup-crew` | 查询可用备份机组 |
| GET | `/api/resource/idle-gates` | 查询空闲登机口 |
| GET | `/api/resource/available-runways` | 查询可用跑道 |

备份资源池配置（基于当前 31 架 A319 的成都基地）：

| 资源类型 | 备份比例 | 备份数量 |
|----------|----------|----------|
| 备份飞机 | 10%~15% | 3~5 架 |
| 备份机长 | 15%~20% | 按需 |
| 备份副驾 | 15%~20% | 按需 |
| 备份乘务长/员 | 20% | 按需 |

备份资源在 `data/` 中配置为标志位字段，平时不参与正常排班。

### 7.7 前端路由扩展

```javascript
// router/index.js — AnalysisApp 中新增 tab：
{
  key: 'recovery',
  label: '异常调度',
  component: RecoveryView
}
```

### 7.8 任务清单

| 编号 | 任务 | 产出 |
|------|------|------|
| P3-1 | 方案执行 → 自动更新四大模块数据 | `execute` API + 数据写入逻辑 |
| P3-2 | 甘特图增加异常标记 | GanttView 红色底纹/蓝色底纹/绿色虚线边框 |
| P3-3 | 跑道时间线增加变更标记 | RunwayView 蓝色箭头/灰色删除线 |
| P3-4 | 登机口视图增加锁定/重新分配标记 | GateView 红色条纹/蓝色背景 |
| P3-5 | 机组视图增加替换/超时/休息不足标记 | CrewView 橙色/红色闪烁/黄色 |
| P3-6 | 地图增加异常状态渲染 | Map.vue/Map-a.vue 动态样式 |
| P3-7 | `GlobalAlertBar.vue` 全局告警横幅 | 顶部告警组件 |
| P3-8 | Vuex Store 完整实现 | state/mutations/actions |
| P3-9 | 备份资源管理 API + 前端展示 | 4 个 API + 资源状态面板 |

### 7.9 验收标准

- [ ] 确认方案后，四大模块视图同步更新
- [ ] 异常标记在甘特图、时间线、登机口、机组中正确显示
- [ ] 地图上机场关闭红色闪烁、航班延误黄色虚线
- [ ] 全局告警横幅实时展示活跃异常
- [ ] 备份资源池可查询
- [ ] Vuex Store 管理全局异常调度状态

---

## 八、Phase 4：完善与发布

> **工期**：约 5 天 | **目标**：多异常叠加、回滚、人工微调、调度日志、历史回看、测试。

### 8.1 批量异常叠加

支持同时创建多个异常事件，模拟真实运营中的复合场景：

```
POST /api/anomaly/batch
Body: [event1_params, event2_params, event3_params]

恢复引擎自动合并影响：
  - 影响分析取并集
  - 恢复策略按优先级联合执行
  - 方案评估考虑叠加效应
```

### 8.2 方案回滚

```
POST /api/anomaly/<event_id>/rollback

实现：
  1. 恢复前快照（Phase 3 的 execute 时自动保存）
  2. 回滚时，用快照覆盖当前排班数据
  3. 四大模块重新加载
```

### 8.3 人工微调

```
POST /api/anomaly/<event_id>/plans/<plan_id>/adjust
Body: { flight_changes: [...], aircraft_changes: [...], ... }

场景：
  - 用户在 RecoveryView 的变更明细表中手动修改
  - 比如：把建议取消的航班改为换备份飞机
  - 提交后重新评估方案指标
```

### 8.4 调度日志

```
data/history/{id}/anomalies/{event_id}_log.json

{
  "event_id": "...",
  "timeline": [
    {"time": "2026-07-24 14:00:00", "action": "created", "detail": "..."},
    {"time": "2026-07-24 14:01:30", "action": "impact_analyzed", "detail": "12 flights affected"},
    {"time": "2026-07-24 14:02:00", "action": "recovery_generated", "detail": "strategy=ResourceReplacement"},
    {"time": "2026-07-24 14:05:00", "action": "confirmed", "detail": "user=admin"},
    {"time": "2026-07-24 14:05:10", "action": "executed", "detail": "4 modules updated"},
  ]
}
```

### 8.5 历史回看

前端在 `RecoveryView.vue` 中增加"历史"标签：

- 异常事件列表（可筛选日期范围、事件类型、状态）
- 点击事件查看完整流程：创建 → 影响分析 → 恢复方案 → 确认 → 执行
- 只读模式，不可修改

### 8.6 测试

| 测试类型 | 覆盖内容 |
|----------|----------|
| 单元测试 | `impact_analysis_service` BFS 传播正确性 |
| 单元测试 | `resource_replacement` 替换逻辑正确性 |
| 单元测试 | `time_shifting` 时间平移计算正确性 |
| 集成测试 | 异常创建 → 分析 → 恢复 → 确认 → 执行 全流程 |
| 集成测试 | 多模块联动：执行后四大模块数据一致 |
| 集成测试 | 多异常叠加场景 |
| 集成测试 | 方案回滚 → 数据恢复到回滚前 |

### 8.7 历史持久化

```
data/history/{history_id}/
├── upload.xlsx
├── result.json
├── meta.json
├── anomalies/                     # Phase 3 新增
│   ├── {event_id}.json            # 异常事件
│   ├── {event_id}_impact.json     # 影响报告
│   ├── {event_id}_plan.json       # 恢复方案
│   └── {event_id}_log.json        # 调度日志
└── schedule_snapshot/
    ├── before_recovery.json        # 恢复前快照
    └── after_recovery.json         # 恢复后快照
```

### 8.8 任务清单

| 编号 | 任务 | 产出 |
|------|------|------|
| P4-1 | 批量异常 API + 合并影响分析 | `batch` + 并集逻辑 |
| P4-2 | 方案回滚 API + 前端按钮 | rollback 端点 |
| P4-3 | 人工微调 API + 变更表格编辑模式 | adjust 端点 + 前端交互 |
| P4-4 | 调度日志模块 | 日志写入 + 查询 API |
| P4-5 | 异常历史回看页面 | RecoveryView 历史标签 |
| P4-6 | 单元测试（6 个） | 策略正确性覆盖 |
| P4-7 | 集成测试（4 个） | 端到端流程覆盖 |

### 8.9 验收标准

- [ ] 可同时创建 3 个异常事件，影响分析取并集
- [ ] 方案回滚后，所有模块数据恢复到执行前状态
- [ ] 人工微调后点击"重新评估"，指标面板更新
- [ ] 调度日志完整记录每条异常的全生命周期
- [ ] 历史页面可回看任意历史异常事件
- [ ] 6 个单元测试 + 4 个集成测试全部通过

---

## 九、扩展接口设计

新增异常类型只需 6 步，无需改动核心引擎：

```
1. AnomalyType 枚举中添加新类型
2. scenario_templates.py 中添加场景模板
3. impact_analysis_service.py 中添加特殊影响分析方法（如需）
4. recovery_strategies/ 目录下新建策略类继承 BaseRecoveryStrategy（如需）
5. AnomalyPanel.vue 动态表单 Schema 中添加参数定义
6. ImpactTree.vue 中添加可视化表达（可选）
```

---

## 十、前端变动清单

> 基于现有 `demo/src/` 目录结构，明确每个文件的增/改内容和所属阶段。

### 10.1 前端目录变动总览

以 `+` 标记新增文件，以 `*` 标记需修改的现有文件：

```
demo/src/
├── main.js                              # * Phase 3 引入 Vuex store
├── App.vue                              # (不变)
│
├── api/
│   └── index.js                         # * Phase 1 新增 12 个异常调度 API 封装
│
├── router/
│   └── index.js                         # * Phase 0 新增异常调度路由（可选）
│
├── store/
│   └── index.js                         # * Phase 3 激活 Vuex，新增 anomaly 模块
│
├── views/
│   ├── Home.vue                         # (不变)
│   ├── AnalysisApp.vue                  # * Phase 2 新增 recovery tab
│   │                                    # * Phase 3 新增全局告警横幅
│   ├── FilterView.vue                   # (不变)
│   ├── DashboardView.vue                # (不变)
│   ├── GanttView.vue                    # * Phase 3 新增异常标记渲染
│   ├── RunwayView.vue                   # * Phase 3 新增变更标记渲染
│   ├── GateView.vue                     # * Phase 3 新增锁定标记渲染
│   ├── CrewView.vue                     # * Phase 3 新增替换/超时标记渲染
│   ├── RecoveryView.vue                 # + Phase 1 创建基础框架
│   │                                    #   Phase 2 集成完整可视化组件
│   │                                    #   Phase 4 新增历史回看标签
│
├── components/
│   ├── Map.vue                          # * Phase 3 新增异常状态渲染
│   ├── Map-a.vue                        # * Phase 3 新增异常状态渲染
│   ├── Ctrl.vue                         # (不变)
│   ├── heatmap.vue                      # (不变)
│   ├── Bar.vue / VerBar.vue             # (不变)
│   ├── Pie2.vue / Pie3.vue / Pie4.vue   # (不变)
│   ├── ECharts.vue                      # (不变)
│   ├── ProgressBar.vue                  # (不变)
│   ├── RoutingView.vue                  # (不变)
│   ├── RunwayView.vue (components/)     # (不变)
│   │
│   └── anomaly/                         # + Phase 1~2 新建目录
│       ├── AnomalyPanel.vue             # + Phase 2 场景模板选择 + 动态参数表单
│       ├── ImpactTree.vue               # + Phase 1 级联影响树可视化
│       ├── RecoveryCompare.vue          # + Phase 2 恢复前后指标对比面板
│       ├── ChangeDetailTable.vue        # + Phase 2 变更明细表格
│       ├── AnomalyTimeline.vue          # + Phase 2 异常事件时间线
│       ├── ResourceStatusBar.vue        # + Phase 3 资源可用性状态条
│       └── GlobalAlertBar.vue           # + Phase 3 全局告警横幅
│
└── utils/
    └── anomaly-helper.js                # + Phase 1 异常状态枚举/颜色映射等工具函数
```

### 10.2 各文件详细变动

#### 10.2.1 `api/index.js`（Phase 1 修改）

新增以下 API 封装函数：

```javascript
// ========== 异常调度 API ==========

/** 获取场景模板列表 */
export function getAnomalyTemplates() {
  return request('/api/anomaly/templates')
}
/** 创建异常事件 */
export function createAnomaly(params) {
  return request('/api/anomaly/create', { method: 'POST', body: JSON.stringify(params) })
}
/** 获取异常事件列表 */
export function getAnomalyList(params) {
  return request('/api/anomaly/list?' + new URLSearchParams(params))
}
/** 获取异常事件详情 */
export function getAnomalyDetail(eventId) {
  return request(`/api/anomaly/${eventId}`)
}
/** 更新异常事件 */
export function updateAnomaly(eventId, params) {
  return request(`/api/anomaly/${eventId}`, { method: 'PUT', body: JSON.stringify(params) })
}
/** 删除异常事件 */
export function deleteAnomaly(eventId) {
  return request(`/api/anomaly/${eventId}`, { method: 'DELETE' })
}
/** 执行影响分析 */
export function runImpactAnalysis(eventId) {
  return request(`/api/anomaly/${eventId}/analyze`, { method: 'POST' })
}
/** 获取影响报告 */
export function getImpactReport(eventId) {
  return request(`/api/anomaly/${eventId}/impact`)
}
/** 获取级联影响树数据 */
export function getCascadeTree(eventId) {
  return request(`/api/anomaly/${eventId}/cascade-tree`)
}
/** 执行自动恢复 */
export function runRecovery(eventId) {
  return request(`/api/anomaly/${eventId}/recover`, { method: 'POST' })
}
/** 获取恢复方案列表 */
export function getRecoveryPlans(eventId) {
  return request(`/api/anomaly/${eventId}/plans`)
}
/** 恢复前后指标对比 */
export function getRecoveryCompare(eventId) {
  return request(`/api/anomaly/${eventId}/compare`)
}
/** 确认方案 */
export function confirmPlan(eventId, planId) {
  return request(`/api/anomaly/${eventId}/plans/${planId}/confirm`, { method: 'POST' })
}
/** 拒绝方案 */
export function rejectPlan(eventId, planId) {
  return request(`/api/anomaly/${eventId}/plans/${planId}/reject`, { method: 'POST' })
}
/** 执行方案 */
export function executePlan(eventId, planId) {
  return request(`/api/anomaly/${eventId}/plans/${planId}/execute`, { method: 'POST' })
}
/** 方案回滚 */
export function rollbackRecovery(eventId) {
  return request(`/api/anomaly/${eventId}/rollback`, { method: 'POST' })
}
/** 人工微调方案 */
export function adjustPlan(eventId, planId, changes) {
  return request(`/api/anomaly/${eventId}/plans/${planId}/adjust`,
    { method: 'POST', body: JSON.stringify(changes) })
}
/** 模拟异常（不修改数据） */
export function simulateAnomaly(params) {
  return request('/api/anomaly/simulate', { method: 'POST', body: JSON.stringify(params) })
}
/** 批量创建异常 */
export function batchCreateAnomaly(events) {
  return request('/api/anomaly/batch', { method: 'POST', body: JSON.stringify(events) })
}
/** 查询备份资源 */
export function getBackupAircraft() {
  return request('/api/resource/backup-aircraft')
}
export function getBackupCrew() {
  return request('/api/resource/backup-crew')
}
export function getIdleGates() {
  return request('/api/resource/idle-gates')
}
export function getAvailableRunways() {
  return request('/api/resource/available-runways')
}
```

#### 10.2.2 `utils/anomaly-helper.js`（Phase 1 新增）

```javascript
/** 异常优先级 → 颜色映射 */
export const PRIORITY_COLORS = {
  P0: '#F56C6C',   // 红色 紧急
  P1: '#E6A23C',   // 橙色 严重
  P2: '#F2D024',   // 黄色 一般
  P3: '#409EFF',   // 蓝色 提示
}

/** 异常类型 → 中文标签 */
export const ANOMALY_TYPE_LABELS = {
  weather_airport_closure: '机场天气关闭',
  weather_enroute: '航路天气绕飞',
  weather_capacity: '机场容量下降',
  aircraft_failure: '飞机机械故障',
  aircraft_diversion: '飞机备降',
  aircraft_maintenance: '定检延期',
  crew_absence: '机组请假',
  crew_overtime: '机组超时',
  crew_qualification: '资质不匹配',
  runway_closure: '跑道关闭',
  runway_degrade: '跑道降级',
  gate_closure: '登机口关闭',
  gate_occupied: '登机口被占',
  flight_cancel: '航班取消',
  flight_merge: '航班合并',
  flight_add: '航班加开',
  flight_delay: '航班延误',
  flow_control: '流控限制',
  airspace_closure: '空域关闭',
}

/** 变更类型 → 中文标签 */
export const CHANGE_TYPE_LABELS = {
  CANCEL: '取消',
  DELAY: '延误',
  REASSIGN_AIRCRAFT: '更换飞机',
  REASSIGN_CREW: '更换机组',
  REASSIGN_GATE: '更换登机口',
  REASSIGN_RUNWAY: '更换跑道',
  MERGE: '合并',
  ADD: '新增',
}

/** 异常状态 → 中文标签 */
export const ANOMALY_STATUS_LABELS = {
  pending: '待处理',
  in_progress: '处理中',
  recovered: '已恢复',
  resolved: '已解决',
}
```

#### 10.2.3 `views/AnalysisApp.vue`（Phase 2 + Phase 3 修改）

```vue
<!-- 现有 tabs 数组追加一项 -->
<script>
import RecoveryView from './RecoveryView.vue'         // Phase 2 新增 import

export default {
  components: {
    // ... 现有组件
    RecoveryView,                                       // Phase 2 新增注册
  },
  data() {
    return {
      tabs: [
        // ... 现有 7 个 tab
        { key: 'recovery', label: '异常调度' },         // Phase 2 新增
      ],
      // Phase 3 新增：活跃告警列表
      activeAlerts: [],
    }
  },
  computed: {
    isMapTab() {
      return this.activeTab === 'map' || this.activeTab === 'recovery'
    },
    isRecoveryTab() {                                   // Phase 2 新增
      return this.activeTab === 'recovery'
    },
  },
}
</script>

<template>
  <div>
    <!-- Phase 3 新增：全局告警横幅 -->
    <GlobalAlertBar
      v-if="activeAlerts.length"
      :alerts="activeAlerts"
      @view-detail="navTo('recovery')"
    />

    <!-- 现有 tab-bar 不变 -->

    <div class="charts" :class="{ 'charts--full': isMapTab }">
      <keep-alive>
        <!-- 现有 6 个 tab 组件不变 -->

        <!-- Phase 2 新增 -->
        <RecoveryView
          v-if="activeTab === 'recovery'"
          key="recovery"
          @schedule-dirty="onScheduleDirty"
        />
      </keep-alive>
    </div>
  </div>
</template>
```

#### 10.2.4 `views/RecoveryView.vue`（Phase 1~4 逐步完善）

```vue
<template>
  <div class="recovery-view">
    <!-- Phase 4 新增：历史/当前 标签切换 -->
    <el-tabs v-model="mode" type="border-card">
      <el-tab-pane label="当前调度" name="current">
        <div class="recovery-layout">
          <!-- 左侧：异常场景面板 -->
          <div class="anomaly-panel">
            <AnomalyPanel
              :templates="templates"
              @create="onCreateAnomaly"
              @select="onSelectAnomaly"
            />
            <div class="active-anomalies">
              <div v-for="a in anomalies" :key="a.event_id"
                   class="anomaly-item" :class="a.priority"
                   @click="onSelectAnomaly(a)">
                {{ a.title }}
              </div>
            </div>
          </div>

          <!-- 中间：影响分析结果 -->
          <div class="impact-area">
            <ImpactTree :data="cascadeData" />
            <ResourceStatusBar :status="resourceStatus" />
            <el-table :data="impactedFlights" />
            <el-button @click="onRunAnalysis">执行影响分析</el-button>
          </div>

          <!-- 右侧：恢复方案 -->
          <div class="recovery-area">
            <div v-for="plan in plans" :key="plan.plan_id" class="plan-card">
              <h4>{{ plan.strategy }} (覆盖率: {{ plan.coverage_rate }}%)</h4>
              <ChangeDetailTable :changes="plan" />
              <RecoveryCompare :before="plan.before_metrics" :after="plan.after_metrics" />
              <div class="plan-actions">
                <el-button @click="onConfirm(plan)">确认方案</el-button>
                <el-button @click="onReject(plan)">拒绝方案</el-button>
                <!-- Phase 4 -->
                <el-button @click="onAdjust(plan)">人工微调</el-button>
                <el-button type="primary" @click="onExecute(plan)">执行方案</el-button>
                <el-button type="danger" @click="onRollback">回滚</el-button>
              </div>
            </div>
            <el-button type="primary" @click="onRunRecovery">生成恢复方案</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- Phase 4 新增：历史回看 -->
      <el-tab-pane label="历史记录" name="history">
        <AnomalyTimeline :events="historyEvents" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
```

#### 10.2.5 `views/GanttView.vue`（Phase 3 修改）

在现有甘特图色块渲染逻辑中新增异常标记：

```javascript
// Phase 3 新增：合并异常影响数据到航空器列表
// 在现有 mounted / watch 中补充：

async fetchAnomalyMarks() {
  // 从 Vuex 读取：当前活跃异常事件对各飞机/航班的影响
  const { affectedAircraft, affectedFlights } = this.$store.state
  this.anomalyMarks = {
    // 红色底纹：受异常影响的航班
    impacted: affectedFlights.map(f => f.flight_id),
    // 蓝色底纹：已被恢复方案调整的航班
    adjusted: affectedFlights.filter(f => f.adjusted).map(f => f.flight_id),
    // 绿色虚线边框：启用的备份飞机
    backupAircraft: affectedAircraft.filter(a => a.is_backup).map(a => a.tail_no),
  }
}

// 甘特图 itemStyle 根据 anomalyMarks 动态设置：
// - 红色底纹 → itemStyle: { color: '#fde2e2', borderColor: '#F56C6C' }
// - 蓝色底纹 → itemStyle: { color: '#ecf5ff', borderColor: '#409EFF' }
// - 绿色虚线边框 → itemStyle: { borderColor: '#67C23A', borderType: 'dashed' }
```

#### 10.2.6 `views/RunwayView.vue`（Phase 3 修改）

```javascript
// Phase 3 新增：在现有跑道时间线渲染中标记顺序变更和取消
// 从 Vuex 获取 runway_changes 数据
computed: {
  runwayChanges() {
    return this.$store.state.currentPlan?.runway_changes || []
  }
},
// 渲染时：
// - 蓝色 ↑↓ 箭头 → 起降顺序被调整的航班旁显示
// - 灰色删除线 → 被取消的航班整条色块变灰 + 文字删除线
```

#### 10.2.7 `views/GateView.vue`（Phase 3 修改）

```javascript
// Phase 3 新增：登机口维护锁定 + 重新分配标记
computed: {
  lockedGates() {
    // 从 Vuex 读取异常事件中的 affected_gates
    return this.$store.state.activeAnomalies
      .filter(a => a.event_type === 'gate_closure')
      .flatMap(a => a.affected_gates)
  },
  reassignedGates() {
    return this.$store.state.currentPlan?.gate_changes?.map(c => c.gate_id) || []
  }
},
// 渲染时：
// - 红色条纹背景 → lockedGates 中的登机口整行标记
// - 蓝色背景 → reassignedGates 中的登机口对应航班色块
```

#### 10.2.8 `views/CrewView.vue`（Phase 3 修改）

```javascript
// Phase 3 新增：在机组甘特图中标记替换、超时、休息不足
// 从 Vuex 读取 crew_changes 和 impact_report.crew_issues
computed: {
  crewMarks() {
    const plan = this.$store.state.currentPlan
    const impact = this.$store.state.currentImpact
    return {
      replaced: plan?.crew_changes?.map(c => c.crew_id) || [],
      overtime: impact?.crew_issues?.filter(i => i.type === 'overtime') || [],
      underRest: impact?.crew_issues?.filter(i => i.type === 'under_rest') || [],
    }
  }
},
// 渲染时：
// - 橙色标记 → 被替换的机组人员行
// - 红色闪烁 → 超时告警的航班色块
// - 黄色警告 → 休息不足时间段的标记
```

#### 10.2.9 `components/Map.vue` + `components/Map-a.vue`（Phase 3 修改）

```javascript
// Phase 3 新增 props / data：
props: {
  // 现有 props 不变
  anomalyStatus: {          // 新增
    type: Object,
    default: () => ({
      closedAirports: [],   // [{name, start, end}]
      degradedAirports: [], // [{name, capacity_ratio}]
      delayedFlights: [],   // [{flight_no, delay_minutes}]
      canceledFlights: [],  // [flight_no, ...]
      faultAircraft: [],    // [tail_no, ...]
      closedGates: [],      // [{airport, gate_id}]
      closedRunways: [],    // [{airport, runway_id}]
    })
  }
},

// watch anomalyStatus → 动态修改 ECharts option：
watch: {
  anomalyStatus: {
    deep: true,
    handler(status) {
      this.updateAnomalyVisual(status)
    }
  }
},

methods: {
  updateAnomalyVisual(status) {
    // 机场关闭 → 对应 effectScatter 改为红色闪烁
    // 机场容量下降 → itemStyle 透明度降低
    // 航班延误 → 对应航线 lineStyle.type = 'dashed', color = '#E6A23C'
    // 航班取消 → 从 series 中移除对应航线 + scatter
    // 飞机故障 → 对应 scatter symbol 改为 'pin', color = '#F56C6C'
    // 登机口/跑道关闭 → tooltip formatter 追加文字
  }
}
```

#### 10.2.10 `store/index.js`（Phase 3 重写）

```javascript
import Vue from 'vue'
import Vuex from 'vuex'
import { getAnomalyList, runImpactAnalysis, runRecovery, executePlan } from '@/api'

export default new Vuex.Store({
  state: {
    // === 异常调度状态 ===
    activeAnomalies: [],           // 当前活跃的异常事件 [{event_id, title, priority, ...}]
    selectedAnomalyId: null,       // 当前选中的异常事件
    currentImpact: null,           // 当前影响报告 ImpactReport
    cascadeTreeData: null,         // 级联影响树（给 ECharts 用）
    currentPlan: null,             // 当前恢复方案 RecoveryPlan
    plans: [],                     // 候选恢复方案列表

    // === 备份资源快照 ===
    resourceStatus: {
      backupAircraft: [],
      backupCrew: [],
      idleGates: [],
      availableRunways: [],
    },

    // === 全局状态 ===
    scheduleDirty: false,          // 排班是否被恢复方案修改
    globalAlerts: [],              // 全局告警 [{id, title, priority, impact_count}]
  },

  getters: {
    hasActiveAnomalies: state => state.activeAnomalies.length > 0,
    currentEvent: state => state.activeAnomalies.find(a => a.event_id === state.selectedAnomalyId),
    impactedModuleData: state => (moduleName) => {
      // 根据 currentPlan 返回对应模块的变更数据
      if (!state.currentPlan) return null
      const map = {
        routing: state.currentPlan.aircraft_changes,
        runway: state.currentPlan.runway_changes,
        gate: state.currentPlan.gate_changes,
        crew: state.currentPlan.crew_changes,
      }
      return map[moduleName] || null
    },
  },

  mutations: {
    SET_ACTIVE_ANOMALIES(state, anomalies) {
      state.activeAnomalies = anomalies
    },
    SELECT_ANOMALY(state, eventId) {
      state.selectedAnomalyId = eventId
    },
    SET_IMPACT(state, impact) {
      state.currentImpact = impact
    },
    SET_CASCADE_TREE(state, treeData) {
      state.cascadeTreeData = treeData
    },
    SET_PLANS(state, plans) {
      state.plans = plans
    },
    SET_CURRENT_PLAN(state, plan) {
      state.currentPlan = plan
    },
    SET_RESOURCE_STATUS(state, status) {
      state.resourceStatus = { ...state.resourceStatus, ...status }
    },
    SET_SCHEDULE_DIRTY(state, dirty) {
      state.scheduleDirty = dirty
    },
    ADD_ALERT(state, alert) {
      const exists = state.globalAlerts.find(a => a.id === alert.id)
      if (!exists) state.globalAlerts.push(alert)
    },
    REMOVE_ALERT(state, eventId) {
      state.globalAlerts = state.globalAlerts.filter(a => a.id !== eventId)
    },
    CLEAR_PLAN(state) {
      state.currentPlan = null
      state.plans = []
    },
  },

  actions: {
    async fetchAnomalies({ commit }) {
      const list = await getAnomalyList({ status: 'pending,in_progress' })
      commit('SET_ACTIVE_ANOMALIES', list)
    },
    async selectAnomaly({ commit }, eventId) {
      commit('SELECT_ANOMALY', eventId)
    },
    async analyzeImpact({ commit, state }) {
      const report = await runImpactAnalysis(state.selectedAnomalyId)
      commit('SET_IMPACT', report)
      // 同步更新各告警
      commit('ADD_ALERT', {
        id: state.selectedAnomalyId,
        title: state.currentEvent?.title,
        priority: state.currentEvent?.priority,
        impact_count: report.total_impacted_flights,
      })
      return report
    },
    async recover({ commit, state }) {
      const plans = await runRecovery(state.selectedAnomalyId)
      commit('SET_PLANS', plans)
      return plans
    },
    async executePlan({ commit }, { eventId, planId }) {
      await executePlan(eventId, planId)
      commit('SET_SCHEDULE_DIRTY', true)
      commit('REMOVE_ALERT', eventId)
    },
  },
})
```

### 10.3 各阶段前端任务细分

#### Phase 0（0 天前端）

无前端任务。

#### Phase 1（约 3 天前端）

| 编号 | 任务 | 文件 |
|------|------|------|
| P1-F1 | `api/index.js` 新增 12 个异常调度 API 函数 | 修改 |
| P1-F2 | 创建 `utils/anomaly-helper.js` | 新增 |
| P1-F3 | 创建 `views/RecoveryView.vue` 基础三栏框架 | 新增 |
| P1-F4 | 创建 `components/anomaly/ImpactTree.vue` | 新增 |
| P1-F5 | `RecoveryView` 中对接场景模板 API、创建事件、影响分析 | 新增 |

#### Phase 2（约 4 天前端）

| 编号 | 任务 | 文件 |
|------|------|------|
| P2-F1 | `AnalysisApp.vue` 新增 recovery tab | 修改 |
| P2-F2 | 创建 `components/anomaly/AnomalyPanel.vue`（模板 + 动态表单） | 新增 |
| P2-F3 | 创建 `components/anomaly/RecoveryCompare.vue` | 新增 |
| P2-F4 | 创建 `components/anomaly/ChangeDetailTable.vue` | 新增 |
| P2-F5 | 创建 `components/anomaly/AnomalyTimeline.vue` | 新增 |
| P2-F6 | `RecoveryView` 集成全部可视化组件 | 修改 |

#### Phase 3（约 4 天前端）

| 编号 | 任务 | 文件 |
|------|------|------|
| P3-F1 | `store/index.js` 重写为完整 Vuex | 重写 |
| P3-F2 | `AnalysisApp.vue` 集成 `GlobalAlertBar` | 修改 |
| P3-F3 | 创建 `components/anomaly/GlobalAlertBar.vue` | 新增 |
| P3-F4 | 创建 `components/anomaly/ResourceStatusBar.vue` | 新增 |
| P3-F5 | `GanttView.vue` 增加异常标记渲染 | 修改 |
| P3-F6 | `RunwayView.vue` 增加变更标记渲染 | 修改 |
| P3-F7 | `GateView.vue` 增加锁定/重新分配标记 | 修改 |
| P3-F8 | `CrewView.vue` 增加替换/超时/休息不足标记 | 修改 |
| P3-F9 | `Map.vue` + `Map-a.vue` 增加异常状态渲染 | 修改 |

#### Phase 4（约 2 天前端）

| 编号 | 任务 | 文件 |
|------|------|------|
| P4-F1 | `RecoveryView` 增加历史 tab + 回看功能 | 修改 |
| P4-F2 | `ChangeDetailTable` 支持行内编辑（人工微调） | 修改 |
| P4-F3 | 方案确认/拒绝/执行/回滚 按钮对接 | 修改 |

### 10.4 前端工作量汇总

| 类型 | 数量 | 涉及阶段 |
|------|------|----------|
| 新增文件 | 9 个 | Phase 1~3 |
| 修改现有文件 | 9 个 | Phase 1~4 |
| 新增 API 封装 | 21 个函数 | Phase 1 |
| 新增 Vuex 模块 | 1 个（约 80 行） | Phase 3 |
| 新增路由 tab | 1 个 | Phase 2 |
| 前端总工作量 | 约 13 天 | Phase 1~4 |

---

## 十一、总任务概览

| 阶段 | 工期 | 后端任务 | 前端任务 | 核心产出 |
|------|------|----------|----------|----------|
| Phase 0 | 3 天 | 3 个模型 + 模板库 | 无 | 数据骨架就绪 |
| Phase 1 | 7 天 | 5 个服务 + 12 个 API | RecoveryView 基础页面 + ImpactTree | 后端正向链路打通 |
| Phase 2 | 7 天 | 4 个策略 + 组合策略 + 4 个 API | 5 个可视化组件 + 动态表单 | 完整恢复引擎 |
| Phase 3 | 7 天 | 模块联动 + 备份资源 + Vuex | 4 模块标记 + 地图增强 + 告警横幅 | 全系统联调 |
| Phase 4 | 5 天 | 回滚/微调/日志/批量 | 历史回看页面 | 发布就绪 |
| **合计** | **29 天** | **17 个服务/模型** | **10 个页面/组件** | - |
