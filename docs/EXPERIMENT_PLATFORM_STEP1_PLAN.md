# 民航智能调度与仿真系统 · 实验平台改造（第一步）实施方案

> 对应任务文档：《民航智能调度系统_实验平台改造计划_第一步》v0.1（2026-11-23）
> 本文只覆盖**第一步**：单实验闭环。批量、对比、统计、权限不在本步范围。
> 目标：把现有"演示系统"升级为"可做实验的平台"，且不改动调度算法与现有工作台流程。
> **评审意见见第 11 节**（2026-11-26 代码核对）。其中 6 项必改与 5 项次要问题已并入第 0–10 节正文，第 11 节保留评审原文作为核对记录。

---

## 0. 一页结论

**方案一句话**：在现有系统之上新增一个独立的「实验中心」——后端一个 `experiment` 服务包，前端三个页面；每次实验用**局部服务实例**跑完整流水线，产出一份**工件包**（条件快照 + 排班结果 + 中断计划 + 指标序列 + 回放元数据）；回放由同一套仿真引擎按同一份计划重算，三个画面直接复用。

**三个关键判断**：

1. 现有系统"算得出来、画得出来"，缺的是"把一次运行变成一次实验"。因此本方案不重写任何算法，只做**编排、快照、隔离、回放**四件事。
2. 实验化有三个硬约束，全部来自现状：**全局单例状态**、**全局随机源**、**前端驱动的天气/旅客流**。方案用"局部实例 + 种子注入 + 后端气象情景程序"逐条化解。
3. 回放不做逐帧录制，而是"**同一引擎 + 同一冻结计划 + 同一时刻**"重算。存储从几十 MB/实验降到 2–3 MB/实验，且跳转到任意时刻都不会失真。

**实测基线**（本机，2026-11-26）：

| 环节 | 规模 | 耗时 |
|------|------|------|
| 6 日航班生成 | 1,196 航班 / 100 链 / 107,880 旅客 | 11.5 s |
| 飞机排班（链覆盖） | 100 链 → 100 架 | 0.07 s |
| 跑道调度 | 26 机场 / 556 起降条目/日 | 0.01 s/日 |
| 登机口分配（成都） | 74 机位 | 0.03 s/日 |
| 机组排班（成都） | 40 人 / 91 pairing | 0.11 s/日 |
| **单次实验（实测）** | 6 日全链路 | **18.6 s**（生成 12.0 s，推演 5.4 s） |

结论：第一步可以"后台线程跑 + 前端轮询进度"，不需要任务队列。

---

## 1. 现状评估

### 1.1 系统分层

| 层 | 位置 | 现状 |
|----|------|------|
| 前端 | `demo/`（Vue 2 + Element UI + ECharts + Three.js） | 21 个页面、34 个组件；路由见 `demo/src/router/index.js` |
| 后端 | `backend/`（Flask 3 + OR-Tools） | 9 个 Blueprint，18,850 行 Python |
| 状态 | `backend/state/__init__.py` | **一组模块级全局变量 + getter/setter**（活跃航班、任务链、缓存、天气计划等 30 项） |
| 服务单例 | `backend/services/__init__.py:11-14` | `routing_service / runway_service / gate_service / crew_service` 四个全局实例 |
| 数据 | `dataProcess/`（Excel/JSON 源）+ `data/`（运行时产物，已 gitignore） | 历史记录按用户存放：`data/history/<user>/<history_id>/` |

### 1.2 现有主链路（本步要复用的部分）

```
客流量输入页 (TrafficInput.vue)
  → POST /api/generate/flights            FlightGenerator：客流→航班+旅客+任务链
  → POST /api/generate/commit             写入全局 state + 创建 gen_* 历史
  → /api/flights/filter                   生成模式下直接沿用全部任务链
  → /api/schedule/routing                 飞机排班（chain_coverage / bipartite / greedy / vrp）
  → /api/schedule/runway                  跑道调度（FCFS / 多跑道贪心）
  → /api/schedule/gates                   登机口（greedy / bipartite / cp_sat）
  → /api/schedule/crew                    机组（chain / pairing / greedy）
  → /simulation-hub                       三画面 + 统一时钟（前端驱动）
  → 仪表盘 DashboardView                  取 /api/simulation/kpi 轮询
```

### 1.3 三个硬约束（方案必须正面处理）

**约束 A：全局单例状态**

- `state` 里的活跃航班/任务链/缓存是"当前这一局"的唯一真相；`/api/flights/history/<id>`、`/api/flights/apply`、`/api/anomaly/plans/<id>/execute` 都会直接改写它。
- `crew_service._crew_pool` 是模块级实例属性（`backend/services/crew_service.py:243-247`），`gate_service._gates_by_airport` 同理。
- 若实验运行直接调用这些路由或全局实例，实验数据会**覆盖工作台**，直接违反"实验与现场隔离"。

**约束 B：全局随机源**

| 位置 | 现状 | 后果 |
|------|------|------|
| `crew_service.py:344,696,751,1060,1319` | `random.seed(hash(key) % 100000 + 2024)` | `hash()` 对字符串按进程随机化（PYTHONHASHSEED），**重启后同条件结果不同** |
| `crew_service.py` 多处 | `random.shuffle(...)` 用全局 RNG | 与并发请求互相污染 |
| `gate_service.py:86,127` | `random.seed(hash(airport_name) % 10000 + self._seed)` | 同上；登机口兼容矩阵每次重启可能不同 |
| `gate_service.py:362` | CP-SAT 局部搜索 `time_limit = 25.0` | 结果与机器负载相关，**不可复现** |
| `simulation_engine.py:520` | `random.random() > cap` 决定是否起飞延误 | 仿真指标随机 |
| `models/passenger_state.py:80-94` | `random.uniform / random.choice` 生成旅客 | 旅客数/中转比例随机 |
| `weather_service.py:116,217` | 马尔可夫链 + 随机风/能见度 | 天气随机 |

**约束 C：天气与旅客流由前端驱动**

- 天气页 `WeatherMap3D.vue` 内部维护气旋 phase，`SimulationHub.vue:146` 每 2 秒把省份天气 + 时间线 POST 给 `/api/weather/stream`，后端 `compute_disruption` 才产出中断计划。
- 实验是无人在前端操作的批处理，**不能依赖这条链路**；否则"实验天气"无法自动化、无法复现。
- 旅客流页 `/api/paxflow/schedule` 固定读取"最近一条 `gen_*` 历史"（`generate_routes.py:400-464`），并不认实验上下文。

### 1.4 与任务文档的逐条对照

| 任务文档的判断 | 代码现状 | 结论 |
|----------------|----------|------|
| 客流→航班→四类调度→仿真→看板都已具备 | 成立，见 1.2 | 复用 |
| 参数散在各表单、跑完即弃 | 成立：参数由各页面请求体临时携带 | 需快照 |
| 没有统一种子 | 成立：见约束 B | 需治理 |
| 历史存航班不存指标 | 成立：`result.json` 只有 flights/chains | 需新存储 |
| 一次只能跑一组条件 | 成立 | 第一步仍单组 |
| 只有当前看板、无实验列表/详情 | 成立 | 需新页面 |

### 1.5 现有代码中与本方案直接相关的"接口"

| 能力 | 入口 | 是否纯函数/可复用 |
|------|------|------------------|
| 航班生成 | `FlightGenerator(data).generate()`（`flight_generator.py:288`） | 是（无随机） |
| 飞机排班 | `routing_service.solve_chain_coverage(chains, n, gap)` | 逻辑是纯函数；实验仍用新实例，避免实例状态串台 |
| 跑道调度 | `runway_service.solve_multi_runway(flights, airport)` | 逻辑是纯函数；`_set_airport` 会写实例状态，实验用新实例 |
| 登机口 | `gate_service.assign_flights_to_gates(airport, algo, date, flights=..., runway_schedule=...)` | 需新实例（内部重置 `_gates_by_airport`） |
| 机组 | `CrewSchedulingService().schedule_from_aircraft_chains(chains, base)` | 需新实例 + 种子 |
| 中断计划 | `compute_disruption(province_weather, timeline, flights, ...)`（`weather_disruption_service.py:156`） | 是，只做装配 |
| 仿真 | `SimulationEngine().load_flights()` / `sync_to()` | 需新实例 + 冻结计划 |

---

## 2. 第一步范围

### 2.1 做（对应任务文档 4.2 的五件事）

1. **新建实验**：条件表单 + 保存草稿 + 实验列表可见。
2. **运行**：启动一次完整运行，后台执行，前端按阶段显示进度；成功/失败都有明确起止与原因。
3. **看过程**：实验详情内嵌三个既有画面（航班 / 天气 / 旅客流）+ 统一时钟，可播放、暂停、拖拽、倍速。
4. **看结果**：6 项主指标 + 4 项辅指标 + 2 条时间序列曲线（见 3.10）。
5. **回看与复用**：实验列表、打开历史实验、一键重跑（同条件同种子，生成新实验）、一键导出 xlsx。

### 2.2 明确不做（与任务文档一致）

- 不做批量网格扫描、多组条件自动跑。
- 不做多人并发、权限体系；沿用 `user1/user2`。
- 不改任何调度算法逻辑（只做随机源与参数的"接口化"，见 3.8）。
- 不改现有分析工作台的页面结构与操作流程。
- 不做逐帧录制；不做旅客级追溯（回放只保证旅客数量与流动形态）。
- 不做实验数据的保留策略（先全部保留，列表页显示占用）。

### 2.3 与现有功能的边界

| 现有功能 | 本步影响 |
|----------|----------|
| 首页上传 → 分析工作台 | 不变；仅在首页加"实验中心"入口 |
| 客流量输入 → 生成 → 分析 | 不变；实验不写 `gen_*` 历史、不改全局 state |
| 四类调度页面 | 不变；实验用独立的局部服务实例 |
| 模拟大引擎 | 不变；实验回放是独立路由与独立引擎 |
| 天气三页联动 | 不变；实验天气走独立的"后端情景程序"，不回传、不共享 state |

---

## 3. 总体设计

### 3.1 架构图

```
┌────────────────────────── 实验中心（新增） ──────────────────────────┐
│  ExperimentListView   ExperimentCreateView   ExperimentDetailView    │
│                                         ├─ ReplayPanel（时钟 + 三画面）│
│                                         └─ MetricCards / MetricChart  │
└───────────────┬──────────────────────────────────────┬───────────────┘
                │ REST /api/experiments/*              │ 回放 /api/experiments/:id/replay/*
┌───────────────▼──────────────────┐   ┌───────────────▼───────────────┐
│ experiment 服务包（新增）          │   │ ReplayRegistry（新增）         │
│  conditions / runner / pipeline   │   │  懒加载工件 → 独立 SimulationEngine│
│  weather_program / metrics        │   │  与工作台引擎完全隔离           │
│  store / artifacts                │   └───────────────┬───────────────┘
└───────┬───────────────┬───────────┘                   │
        │ 只读调用       │ 写工件                         │ 同一份冻结计划重算
┌───────▼───────┐ ┌─────▼──────────┐            ┌────────▼────────┐
│ 现有算法服务   │ │ data/experiments│            │ SimulationEngine │
│ （局部新实例） │ │  /<user>/<id>/  │            │ （新实例）       │
└───────────────┘ └────────────────┘            └─────────────────┘
        ▲                                                    
        │ 默认路径完全不变                                     
┌───────┴────────────────── 现有工作台（不改） ──────────────────────┐
│ 全局 state + 四个全局服务单例 + 前端驱动的天气/旅客流 + 模拟大引擎    │
└────────────────────────────────────────────────────────────────────┘
```

**核心原则**：实验链路只"读"现有算法与数据，不写全局 state；工作台链路完全不知道实验的存在。两条链路唯一的交点是 `data/experiments/` 下的文件。

### 3.2 四个核心概念

| 概念 | 定义 | 载体 |
|------|------|------|
| **实验 Experiment** | 一份运行条件 + 一条结果记录 | `meta.json` |
| **运行 Run** | 从 `running` 到 `succeeded/failed` 的一次完整执行 | `run.json` + 内存进度 |
| **工件 Artifact** | 运行产出的可复用数据（航班/排班/中断/指标/回放元数据） | 分片 JSON |
| **回放 Replay** | 用工件重建的、只读的、可拖拽时间轴的三画面 | `ReplayRegistry` |

### 3.3 目录与文件清单

#### 后端新增（新文件尽量遵守 `DEVELOPMENT_STANDARDS.md` 的行数上限，超限处注明原因）

> 说明：`models/experiment.py` 约 160 行，超出 models 层的 100 行上限。原因是条件/记录/摘要三个数据类放在同一文件更内聚，拆开会产生互相 import；若评审坚持，可拆为 `experiment_conditions.py` 与 `experiment_record.py`。
> 实际落地时 `conditions.py`（约 227 行）、`weather_program.py`（约 235 行）、`runner.py`（约 239 行）略超 200 行：三者分别是"条件校验/情景编译/运行编排"的单一职责，继续拆分会产生循环依赖或把一次流程切碎，故保留并在文件头注明。
> 前端 `api/index.js` 现有 572 行，本就超出 200 行上限；本步只在其上增加作用域转发，不继续堆业务封装，实验相关请求全部放新文件 `api/experiment.js`。

```
backend/models/experiment.py                     条件/记录的数据类与序列化          ~160 行（超限已说明）
backend/services/experiment/__init__.py          导出入口                          ~10 行
backend/services/experiment/seed.py              稳定哈希 + RNG 工厂               ~70 行
backend/services/experiment/conditions.py        默认值/校验/规范化/条件摘要        ~180 行
backend/services/experiment/weather_program.py   气象情景 → 省份时间线 → 中断计划   ~200 行
backend/services/experiment/paxflow_builder.py   航班+排班 → 旅客流调度（纯函数）    ~180 行
backend/services/experiment/steps/generate.py    生成航班 + 任务链                 ~120 行
backend/services/experiment/steps/schedule.py    四类调度                          ~200 行
backend/services/experiment/steps/simulate.py    冻结计划推演 + 采样               ~140 行
backend/services/experiment/metrics.py           指标聚合与序列                    ~180 行
backend/services/experiment/artifacts.py         分片读写/压缩字段                 ~170 行
backend/services/experiment/store.py             目录/列表/删除/占用统计            ~190 行
backend/services/experiment/runner.py            线程/单并发锁/进度/状态机          ~170 行
backend/services/experiment/replay.py            回放引擎注册表（LRU=2）            ~180 行
backend/routes/experiment_routes.py              创建/列表/详情/删除/导出           ~200 行
backend/routes/experiment_run_routes.py          启动/进度/重跑                     ~120 行
backend/routes/experiment_replay_routes.py       回放 8 个端点                      ~180 行
scripts/experiment_smoke.py                      M1.5 冒烟：进程内 + 子进程复现      ~160 行
```

#### 后端小改造（行为保持）

| 文件 | 改动 | 目的 |
|------|------|------|
| `services/crew_service.py` | 用实例级 `self._rng` 替代 `random.seed/shuffle`；`hash()` → `stable_hash()` | 可复现，且不污染全局 RNG |
| `services/pairing_assigner.py` | `assign_pairings(..., rng=None)`；`_best_random_disjoint(pairings, rng, trials)`；集合遍历改 `sorted(...)` | 机组 `chain` 路径默认会走到这里，不改则失去可复现 |
| `services/gate_service.py` | 同上；`cp_sat` 不进实验算法白名单 | 可复现 |
| `models/passenger_state.py` | `PassengerFlow(rng=None)` | 旅客生成可种子化 |
| `services/simulation_engine.py` | 新增 `sync_frozen(minutes, plan)`；`SimulationEngine(rng=None)` 可延到 M5 | 回放跳转不失真 |
| `services/aircraft_types.py` | 新增 `fleet_sequence(fleet_mix)` | 让"机型配比"真正生效 |
| `services/flight_generator.py` | `self._fleet_seq = fleet_sequence(self.fleet_mix)` | 同上（默认值输出不变） |
| `routes/generate_routes.py` | 把 `:500-679` 的旅客流组装抽到 `paxflow_builder.py`，路由改为调用纯函数 | 实验与现场共用，避免复制 180 行 |
| `backend/app_main.py` 或启动脚本 | 入口处 `os.environ.setdefault('PYTHONHASHSEED','0')` 并提示需在进程启动前设置 | 集合/哈希顺序兜底 |
| `requirements.txt` | 增加 `openpyxl==3.1.5` | 导出 xlsx；现上传已在用但未声明 |

#### 前端新增

```
demo/src/api/experiment.js                       实验 REST 封装                     ~120 行
demo/src/api/scope.js                            数据作用域（live/replay）           ~50 行
demo/src/views/ExperimentListView.vue            实验列表                           ~200 行
demo/src/views/ExperimentCreateView.vue          新建实验                           ~220 行
demo/src/views/ExperimentDetailView.vue          详情（回放 + 结果）                 ~260 行
demo/src/components/experiment/ConditionForm.vue 条件表单                           ~200 行
demo/src/components/experiment/ConditionSummary.vue 条件快照只读展示                 ~110 行
demo/src/components/experiment/ExperimentTable.vue  列表表格                         ~140 行
demo/src/components/experiment/RunProgress.vue   阶段进度                           ~120 行
demo/src/components/experiment/MetricCards.vue   指标卡片                           ~110 行
demo/src/components/experiment/MetricChart.vue   指标曲线（ECharts）                 ~120 行
demo/src/components/experiment/ReplayPanel.vue   回放容器（时钟 + 三 tab）           ~200 行
```

#### 前端小改造（默认行为不变）

| 文件 | 改动 | 目的 |
|------|------|------|
| `views/Home.vue` | 加"实验中心"入口按钮 | 入口 |
| `router/index.js` | 加 3 条路由 | 页面 |
| `api/index.js` | 增加 `setApiScope()`；仿真/旅客流请求按作用域改写 | 回放复用 |
| `views/SimMapView.vue` | 加 `readonly` prop（隐藏事件注入面板） | 回放只读 |
| `components/TerminalLayout.vue` | 2 处 `fetch` 改为 `api.*` | 回放复用 |
| `components/WeatherMap3D.vue` | 暴露 `applyProvinceWeather(map)`（进入既有 manual 模式） | 回放天气一致 |

### 3.4 存储布局

```
data/experiments/<username>/<exp_id>/
├── meta.json        条件快照 + 状态 + 时间戳 + 摘要指标 + warnings/error
├── flights.json     航班（调度字段 + pax_count，**不含** pax_list/manifest）
├── schedule.json    飞机链 + 跑道条目 + 登机口分配 + 机组摘要
├── weather.json     气象情景 + 省份时间线 + 冻结中断计划 + 计划元信息
├── metrics.json     指标定义 + 指标值 + 时间序列
├── paxflow.json     回放用旅客流调度（既有 /api/paxflow/schedule 同构）
└── run.json         阶段耗时 + 日志尾部 + 失败阶段
```

**体积估算**（6 日 / 1,196 航班）：`flights.json` ≈ 0.4 MB，`schedule.json` ≈ 1.2 MB，`paxflow.json` ≈ 0.6 MB，其余 < 0.2 MB → **约 2.5 MB/实验**。不存 `pax_list`（107,880 条），否则会膨胀到数十 MB。

### 3.5 API 契约

统一响应 `{code: 0, data|msg}`，与现有后端一致；用户通过 `?username=` 传入（沿用现有 `require_user` 方式）。

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/api/experiments` | 创建草稿，返回 `id` |
| GET | `/api/experiments` | 列表（按创建时间倒序，含状态与摘要指标） |
| GET | `/api/experiments/<id>` | 详情（条件 + 指标 + 曲线 + 警告 + 错误） |
| DELETE | `/api/experiments/<id>` | 删除目录（运行中拒绝） |
| POST | `/api/experiments/<id>/run` | 启动后台运行；已有运行中实验则 409 |
| GET | `/api/experiments/<id>/progress` | `{status, pct, stage, message, elapsed_sec}` |
| POST | `/api/experiments/<id>/rerun` | 同条件同种子新建一条实验并启动，记录 `parent_id` |
| GET | `/api/experiments/<id>/export` | xlsx（条件/指标/曲线三张表） |
| POST | `/api/experiments/<id>/replay/init` | 懒加载工件，返回 `{total_flights, sim_start, sim_end}` |
| POST | `/api/experiments/<id>/replay/sync` | `{current_minutes}` → 冻结计划重算，返回快照 |
| GET | `/api/experiments/<id>/replay/snapshot` | 当前快照（供 500ms 轮询） |
| POST | `/api/experiments/<id>/replay/start\|pause\|resume\|stop\|speed\|step\|jump` | 兼容 `SimMapView` 的既有调用（回放引擎为空实现/直接重算） |
| GET | `/api/experiments/<id>/replay/paxflow` | 回放旅客流调度（读 `paxflow.json`） |
| POST | `/api/experiments/<id>/replay/manifests` | 返回空清单，前端用兜底编号 |
| GET | `/api/experiments/<id>/replay/context` | 机场/机型/基地（供注入面板，只读时隐藏） |
| GET | `/api/experiments/<id>/replay/weather` | 当前时刻的机场天气（由省份情景映射，供航班地图徽标） |

### 3.6 运行流水线

**阶段与进度权重**（依据 1.0 实测）：

| # | 阶段 | 权重 | 主要动作 | 失败处理 |
|---|------|------|----------|----------|
| 1 | 校验条件 | 1% | 字段校验、日期/基地/机型归一化 | 直接失败，返回字段错误 |
| 2 | 生成航班计划 | 50% | `FlightGenerator.generate()` | 失败即终止 |
| 3 | 构建任务链 | 4% | dict→Flight、链重建、完整性校验 | 失败即终止 |
| 4 | 飞机排班 | 4% | `solve_chain_coverage` / 其它 | 失败即终止 |
| 5 | 跑道调度 | 4% | 逐机场 `solve_multi_runway` | 单机场失败记 warning，继续 |
| 6 | 登机口分配 | 5% | 逐日期 × 主基地 | 单日失败记 warning，继续 |
| 7 | 机组排班 | 10% | `schedule_from_aircraft_chains` | 失败记 warning，指标置 null |
| 8 | 编译中断计划 | 5% | 气象情景 → 省份时间线 → `compute_disruption` | 失败即终止 |
| 9 | 冻结计划推演 | 12% | `sync_frozen()` 逐步采样，15 分钟步长 | 失败即终止 |
| 10 | 汇总指标与落盘 | 5% | 指标聚合、工件写入、meta 更新 | 失败即终止 |

**伪代码**（`runner.py`）：

```python
def run(exp_id):
    meta = store.load_meta(exp_id)
    try:
        with RUN_LOCK:                       # 单并发
            set_status(exp_id, 'running', pct=1, stage='校验条件')
            cond = conditions.normalize(meta['conditions'])
            seed = cond['seed']

            gen  = steps.generate.run(cond, progress)          # 生成
            sch  = steps.schedule.run(gen, cond, progress)     # 四类调度
            wth  = weather_program.compile(cond, gen, sch, seed)
            sim  = steps.simulate.run(gen, wth['plan'], progress)

            metrics = metrics.aggregate(gen, sch, wth, sim)
            artifacts.write_all(exp_id, gen, sch, wth, metrics, sim)
            set_status(exp_id, 'succeeded', summary=metrics['values'],
                       warnings=sch['warnings'], pct=100)
    except Exception as e:
        set_status(exp_id, 'failed', error=capture(e))          # 阶段 + 消息 + 栈尾
```

**关键实现约定**：

- 运行在 `threading.Thread(daemon=True)` 中执行；Flask 以 `threaded=True` 运行，轮询不受阻。
- 进度写内存 + 每次阶段切换落 `meta.json`（重启后 `running` 且无活线程 → 标记 `interrupted`）。
- 单并发：模块级 `Lock`；第二个运行请求返回 409 并说明"已有实验在运行"。
- 失败信息包含 `stage`、`message`、`traceback` 最后 20 行，前端详情页原样展示。
- 成功但存在子模块失败 → `status=succeeded` + `warnings[]`，指标里对应项为 `null`，不伪造数字。

### 3.7 隔离设计（对应"不打扰现场"）

| 风险点 | 现状 | 本方案 |
|--------|------|--------|
| 活跃航班/任务链被覆盖 | 全局 `state` | 实验流水线**完全不写** state；生成结果只存在局部变量 |
| 机组池被覆盖 | `crew_service._crew_pool` 全局实例 | 每次运行 `CrewSchedulingService()` **新实例** |
| 登机口机位表被重置 | `gate_service._gates_by_airport` | 每次运行 `GateAssignmentService()` 新实例 |
| 跑道机场配置串台 | `runway_service._current_airport_cfg` | 新实例 + 直接传 `airport_name` 参数 |
| 随机数污染 | 全局 `random` | 注入实例级 `Random(seed)`，不调用 `random.seed`；`pairing_assigner` 也必须接收 rng |
| 仿真引擎被改写 | `simulation_engine` 单例 | 回放用独立 `SimulationEngine()`，注册在 `ReplayRegistry` |
| 旅客流抢"最近 gen_*" | `_ensure_paxflow_flights()`（`generate_routes.py:439-461` 会写全局活跃航班/链/历史 ID） | 回放只读 `paxflow.json`；前端三处请求（`TerminalLayout` 2 处 + `TerminalFlowView.loadBackendDates` 1 处）全部走作用域，不调线上接口 |
| 回放作用域泄漏 | `scope.js` 是全局可变状态 | `ExperimentDetailView` 进入时设 `replay`，`beforeDestroy` 复位 `live`；路由守卫兜底 |
| 历史记录被写入 | `/api/generate/commit` 写 `data/history` | 实验流水线不调用 commit，不创建 history |

**验证方式**：运行前后各取一次"现场指纹"（`flights/status` + `schedule/current` 的航班数、链数、current_history_id），断言完全一致；运行期间并发调用工作台接口，断言不报错、结果不变（**不对耗时做断言**：生成阶段约 10 s 的纯 Python 计算占 GIL，工作台会变慢但不会阻塞）。额外用例：打开回放的三个 tab 后，再取一次指纹，仍须一致。

### 3.8 复现设计（对应"可复现"）

**种子治理**

- 实验条件必须带 `seed`（6 位整数）；表单默认随机生成，允许手填。
- 所有随机行为从 `Random(seed + salt)` 派生，salt 按用途区分（`crew` / `gate` / `passenger` / `sim`），互不干扰。
- 禁止使用 Python 内置 `hash()` 派生种子；统一 `zlib.crc32(text.encode())`。
- **只替换 hash 不够**：集合迭代顺序同样随 `PYTHONHASHSEED` 变化。启动脚本固定 `PYTHONHASHSEED=0` 作为兜底；同时把会影响输出的集合遍历改为 `sorted(...)`，至少包括：
  - `pairing_assigner.py:55,196` 的未覆盖航班集合；
  - `pairing_assigner._build_daily_turnarounds` 的 `for fid in uncovered_fids`；
  - `weather_disruption_service.compute_disruption` 的 `bad_provinces` 遍历与 `transit_ids` 遍历。
- 实验算法白名单排除 `gate.cp_sat`（25s 时间上限，不可复现）；UI 中该项置灰并注明"实验模式不支持"。

**参数化（不是算法改造）**

| 参数 | 现状 | 改动 |
|------|------|------|
| 机队规模 | `num_aircraft` 已支持 | 直接用 |
| 机型配比 | 生成器接受 `fleet_mix` 但忽略，实际用固定 `fleet_ratio_list()` | 新增 `fleet_sequence(mix)` 并接入；默认 10/50/40 输出与现在**完全一致** |
| 客座率/过站/单日段数 | 已支持 | 直接用 |

**复现判据（写进验收）**

- 同一条件 + 同一 seed，在同一进程内连跑两次：`metrics.json` 去掉时间戳/耗时字段后**逐字节相等**。
- 跨进程（重启后端）再跑一次：仍逐字节相等 → 专门抓 `hash()` 类问题。
- 容差（为未来随机模式预留）：计数类必须完全相等；百分比 ±0.1pp；平均延误 ±0.5 min。第一步实测应为 0 偏差。

### 3.9 回放设计（对应"可回放"）

**为什么不用逐帧录制**

- 现有三画面本身就是"时间 → 状态"的确定性渲染：航班位置由 `(计划时刻, 当前分钟)` 决定，天气由气旋 phase 决定，旅客流由航班调度决定。
- 只要冻结"计划 + 中断 + 时间轴"，同一时刻重算即可得到同一画面；录制反而会引入渲染噪声（粒子随机）且存储爆炸。

**三个画面如何复用**

| 画面 | 复用组件 | 数据来源 | 需要的改动 |
|------|----------|----------|-----------|
| 航班 | `SimMapView`（`embedded=true`, `readonly=true`） | `/replay/init` + `/replay/snapshot` + `/replay/sync` | `readonly` prop 隐藏注入面板 |
| 天气 | `WeatherMap3D` | `weather.json` 的省份时间线 → `applyProvinceWeather()` | 暴露一个进入 manual 模式的方法 |
| 旅客流 | `TerminalFlowView` → `TerminalLayout` | `/replay/paxflow`（`paxflow.json`） | 三处请求走作用域：`TerminalLayout` 的 schedule/manifests + `TerminalFlowView.loadBackendDates` 的 dates |

> 旅客流限制：现有旅客流画面绑定成都双流机场（`generate_routes.py:516` 硬编码 `airport='成都'`）。实验基地若不含成都，该 tab 显示"本实验无成都场航班"，不伪造数据。

**气象情景如何编译（一次性编译的语义）**

现有 `compute_disruption` 是给"现场每 2 秒重算"设计的：它用每条时间线 `t=0` 的点判定坏省份（`weather_disruption_service.py:176-185`），再把多省窗口并成一个（`:218`）。实验只编译一次，必须自己保证语义正确：

1. **逐省、逐窗口编译**：把一个情景拆成"省份 × 连续坏天气窗口"，每个窗口单独调用 `compute_disruption`，并把它自己的起始时刻对齐为 `t=0`（否则该省会因首个采样点不是坏天气而被整体忽略）。
2. **合并计划**：同一航班命中多个窗口时，`cancel` 优先于 `delay`；同为 `delay` 取最大值；`reason` 取首个生效窗口的原因。
3. **机场临时关闭**不是省份天气，单独编译：
   - 从该机场出发、且起飞时刻落在 `[start, end)` 的航班 → `{type: 'cancel'}`；
   - 到达该机场、且到达时刻落在 `[start, end)` 的航班 → `{type: 'delay', delay_minutes: end - 到达时刻 + 30}`。
4. **单元测试**：多省错峰、窗口不从 0 开始、机场关闭三个用例，断言计划条数与类型。

**时钟映射**

- 业务分钟基准与后端一致：`(month-11)*30*1440 + day*1440 + hour*60 + minute`。
- 回放时钟范围 = `sim_start_minutes ~ sim_end_minutes`（存在 `meta.replay`）。
- 天气 phase = `(minutes - 11-29 00:00) / 10080`，实验日期池限制在 11-30 ~ 12-05，phase 落在 1/7 ~ 1 之间，不会越界。
- 时钟 UI 新建 `ReplayPanel`（不改造 `SimulationHub`），支持播放/暂停/倍速/拖拽；拖动时用 `sync_frozen` 直接重算，**任意跳转都正确**。

**为什么必须新增 `sync_frozen`**

现有 `sync_to(minutes, plan)` 每次调用会先把 `delay_minutes` 归零，并且只在 `minutes < 起飞时刻` 时应用取消/延误。它适合"计划随天气实时演变"的现场模式，但不适合"冻结计划 + 任意跳转"的回放：

- 直接跳到某航班起飞后，取消会丢失；
- 延误在起飞后被清零，航班会"提前到达"。

`sync_frozen` 的语义是：计划冻结，取消永久生效，延误永久叠加，然后按分钟重算阶段。它只在回放/实验采样中使用，现有 `sync_to` 与现场行为不变。

**回放一致性判据**

- 在 `metrics.series` 的每个采样点 `t`，用回放引擎 `sync_frozen(t)` 得到的"在空/已到达/延误/取消"计数，必须与 `metrics.series` 中该点完全一致（自动化测试）。
- 用户在回放页拖动到任意时刻，页面底部读数与曲线在同一时刻的值一致。

**已知取舍**（需在评审时确认）

- 回放的"天气"使用实验情景（manual 省份天气），不是运行当天前端气旋的原始画面。原因：实验是后端批处理，没有前端气旋现场。这样"天气—中断—航班"三者语义一致。
- 回放的旅客编号由前端按 `Pax-MMDD-XXXXX` 兜底生成（数量与登机/到达时序准确），不保证与运行当时的个体 ID 一一对应。

### 3.10 指标口径

**主指标（6 项，结果区首屏）**

| 指标 | 公式 | 来源 |
|------|------|------|
| 计划航班数 | 生成航班总数（含调机） | `generate` |
| 全程准点率 | `(总数 - 曾延误 - 取消) / 总数 × 100` | 推演采样 |
| 完成率 | `已到达 / (总数 - 取消) × 100` | 推演采样 |
| 取消航班数 | 计划中 `type=cancel` 的航班数 | 中断计划 |
| 延误航班数 | 曾出现 `delay_minutes > 0` 的航班数 | 推演采样 |
| 平均延误 | 延误航班的 `max(delay_minutes)` 均值 | 推演采样 |

**辅指标（4 项，结果区第二行）**

| 指标 | 公式 | 来源 |
|------|------|------|
| 飞机利用率 | `mean(飞行分钟 / (18×60)) × 100` | 排班统计（`routing_service.get_stats`） |
| 跑道平均延误 | `sum(delay) / 起降条目数`（全机场） | 跑道统计 |
| 登机口平均利用率 | 主基地各日 `avg_utilization` 的加权均值 | 登机口统计 |
| 机组覆盖率 | `已排班航班 / 总航班 × 100`；违规项另列 | 机组统计 |

**时间序列（2 条曲线）**

- 曲线 A（每 15 分钟）：在空 / 已到达 / 延误 / 取消 四个计数（堆叠面积或折线）。
- 曲线 B（每 15 分钟）：当刻延误航班的平均延误（分钟）。

**口径说明（避免"同名不同数"）**

- 现有 `DashboardView` 的 KPI 是"当前仿真时刻的瞬时值"；实验指标是"全程累计值"。两者同名但语义不同。
- 实验页统一加"全程"前缀（如"全程准点率"），并在指标卡 tooltip 与导出表头写明公式；`metrics.json` 内嵌 `definitions`。
- 同一实验内，卡片、曲线、导出三处数值来自同一份 `metrics.json`，不重复计算。

### 3.11 前端页面与交互

**实验列表 `/experiments`**

- 表格列：名称 / 创建时间 / 条件摘要（日期·基地·机队·算法·天气·种子）/ 状态 / 全程准点率 / 完成率 / 操作（打开·重跑·导出·删除）。
- 状态色：`draft` 灰、`running` 蓝（带进度）、`succeeded` 绿、`failed` 红、`interrupted` 橙。
- 空态：引导"新建实验"。

**新建实验 `/experiments/new`**

分区表单：

1. 基本信息：名称（默认 `实验 YYYY-MM-DD HH:mm`）。
2. 客流与日期：日期多选（11-30 ~ 12-05）；基地多选（成都/重庆/昆明/宜宾/绵阳/杭州）；客流模板（演示客流）+ 全局缩放（0.5–2.0，默认 1.0）+ **粘贴城市对客流**（每行 `城市,城市,人数`，留空则用模板）；实时显示"日均总客流 / 方向流条数"。粘贴内容直接作为 `city_traffic` 输入，补上"输入自己的客流量"这一诉求；完整矩阵编辑仍留在原页面。
3. 机队：规模（20–150，默认 100）；机型配比（A319/A320/A321 三输入，自动校验合计 = 规模，默认 10/50/40）。
4. 算法：飞机排班 / 跑道 / 登机口 / 机组 四组单选，默认 `chain_coverage / multi_runway / bipartite / chain`；`gate.cp_sat` 置灰。
5. 中断情景：天气（无 / 四川盆地雷暴 / 华东强降雨 / 华南台风）；异常（无 / 机场临时关闭：机场 + 起止时刻）。
6. 运行参数（高级，折叠）：客座率、过站时间、单日最大段数。
7. 种子：默认随机 6 位，可手填；旁注"同条件同种子才能复现"。
8. 底部：保存草稿 / 保存并运行。

**详情 `/experiments/:id`**

- 顶部：名称、状态徽标、条件 chips、按钮（重跑 / 导出 / 删除）。
- 运行中：`RunProgress` 阶段列表 + 百分比 + 已耗时；可离开页面，回来继续看。
- 完成后：
  - 上：`ReplayPanel`（三个 tab + 统一时钟 + 底部读数）。
  - 下：`MetricCards`（6 主 + 4 辅）+ `MetricChart`（曲线 A/B 切换）。
  - 右/下：`ConditionSummary`（完整条件快照、种子、起止时间、阶段耗时、warnings）。
- 失败：红色提示条 + 失败阶段 + 错误消息 + 栈尾（折叠）。

**入口**

- `Home.vue` 在"全链路模式"区域增加第三个按钮「实验中心」。

---

## 4. 验收对照（任务文档第 7 节逐条落地）

| 任务文档验收项 | 可测判据 | 验证方式 |
|----------------|----------|----------|
| 能建实验 | `POST /api/experiments` 返回 id；列表可见；刷新/重启后仍在 | 手工 + `test_store` |
| 能跑完 | 状态从 `running` 到 `succeeded/failed`；有 `started_at/finished_at`；失败有 `stage+message` | 手工 + `test_runner` |
| 能回放 | 三个 tab 均可播放；拖动到任意时刻画面正确；采样点计数与曲线一致 | `test_replay_consistency` + 手工 |
| 结果可读 | 6 主 + 4 辅指标；2 条曲线；空值标注原因 | 手工 + 指标单测 |
| 可复现 | 同条件同种子两次运行，指标逐字节一致（跨进程亦然） | `test_repro`（同进程 + 子进程） |
| 可导出 | 一键下载 xlsx，含条件/指标/曲线三张表，数值与页面一致 | 手工 + 文件校验 |
| 不打扰现场 | 运行前后现场指纹一致；运行期间工作台接口可用；**打开回放三个 tab 后指纹仍一致** | `test_isolation`（含回放用例）+ 并发手工验证 |

---

## 5. 任务拆分（按依赖顺序）

### M0 环境与基线（前置）

- 用 **Python 3.13** 建虚拟环境（本机默认 PATH 是 3.14，`ortools 9.12.4544` 没有 cp314 wheel；3.13 可解析到 cp313 wheel）。安装 `flask / flask-cors / ortools / xlrd / openpyxl`；`npm install`。
- 启动脚本固定 `PYTHONHASHSEED=0`（写进启动命令/文档，进程内设置无效）。
- 启动前后端，手工跑通"客流→生成→四类调度→模拟大引擎"。
- 记录 6 日基线的航班数/链数/旅客数/耗时；**另记一份"改造前机组/登机口跨重启不一致"的证据**（两次进程、同条件、对比机组覆盖率/违规数），作为复现改造的对照。
- **产出**：可运行环境 + 基线记录。
- **验收**：`/api/health` 正常；登录、生成、四类调度页面均可用。

### M1 复现性地基（后端）

- `seed.py`：`stable_hash` + `rng_for(seed, salt)`。
- 改造 `crew_service` / `gate_service` / `pairing_assigner`：实例级 RNG、稳定哈希、去掉 `random.seed`。
- 集合遍历改 `sorted(...)`（`pairing_assigner` 两处、`compute_disruption` 两处）。
- `PassengerFlow(rng)`；`SimulationEngine(rng)` 可延到 M5（冻结重算不走随机路径）。
- `fleet_sequence(mix)` + 生成器接入。
- 抽取 `paxflow_builder.py`：把 `generate_routes.py:500-679` 的组装逻辑变成纯函数，路由改为调用它。
- **产出**：可注入种子的算法层 + 可复用的旅客流组装函数。
- **验收**：航班生成输出与改造前一致（航班数/链数/旅客数）；机组、登机口、旅客生成在**固定种子**下同进程与跨进程均稳定；改造前"跨重启不一致"的证据已记录。

### M1.5 冒烟脚本（写接口之前）

- `scripts/experiment_smoke.py`：单进程跑完"生成 → 四类调度 → 气象编译 → 冻结采样 → 指标汇总"，打印关键计数。
- 同一命令再跑两次（其中一次在子进程、换 `PYTHONHASHSEED`），比较归一化结果。
- **验收**：三次结果一致；不一致时能定位到具体阶段。这一步用于提前暴露 11.2 第 1、2、5 项风险。

### M2 实验存储与 API 骨架

- `models/experiment.py`、`conditions.py`、`store.py`、`artifacts.py`。
- 创建/列表/详情/删除四个接口。
- **产出**：可建草稿、可列表、可读详情、可删除。
- **验收**：重启后数据仍在；非法条件返回明确字段错误。

### M3 运行编排与工件

- `steps/generate.py`、`steps/schedule.py`、`steps/simulate.py`、`runner.py`、`weather_program.py`。
- 进度、单并发锁、失败原因、状态持久化。
- **产出**：一次 6 日实验可跑完，工件落盘。
- **验收**：20 s 内完成（实测 18.6 s）；进度阶段可见；人为制造失败（非法基地）能显示阶段与原因。

### M4 指标与导出

- `metrics.py`：10 项指标 + 2 条序列；口径写入 `definitions`。
- 导出 xlsx（条件/指标/曲线）。
- **产出**：结果区数据完整、可导出。
- **验收**：指标齐全；导出文件可打开且与页面一致；同条件同种子指标一致。

### M5 回放（后端 + 前端容器）

- `SimulationEngine.sync_frozen()`。
- `replay.py` + 三个回放路由。
- `ReplayPanel.vue` + `api/scope.js` + `api/index.js` 作用域改造。
- `SimMapView.readonly`、`TerminalLayout` 两处 fetch、`TerminalFlowView.loadBackendDates`、`WeatherMap3D.applyProvinceWeather`。
- 作用域复位：`ExperimentDetailView.beforeDestroy` → `live`。
- **产出**：详情页三画面可回放。
- **验收**：三 tab 可播；拖拽/跳转正确；采样点一致性测试通过；打开三 tab 后现场指纹不变。

### M6 实验中心 UI

- 列表、创建、详情三页 + 首页入口 + 路由。
- 空态、错误态、状态色、删除确认。
- **产出**：五件事全部可在界面上完成。
- **验收**：手工走查任务文档 4.2 的五个动作；页面不超出 300 行限制。

### M7 回归与验收

- 补齐 `tests/`：`test_metrics / test_repro / test_isolation / test_artifacts / test_replay_consistency`。
- 回归现有工作台：上传→筛选→四类调度→仿真→看板全部照旧。
- 更新 `README.md` 增加"实验中心"一节（启动方式、字段说明、口径说明）。
- **验收**：第 4 节 7 条全部通过；现有页面无回归。

---

## 6. 测试计划

| 测试 | 内容 | 命令/方式 |
|------|------|-----------|
| 单元：指标 | 给定构造的计划/计划表，校验 10 项指标与序列 | `python -m unittest tests.test_metrics` |
| 单元：条件 | 默认值、校验、机型配比合计、非法日期/基地 | `python -m unittest tests.test_conditions` |
| 复现 | 同进程两次 + 子进程一次，比较归一化 `metrics.json`；条件**必须带天气 + 机组算法**，不能只测航班生成 | `python -m unittest tests.test_repro` |
| 隔离 | 运行前后现场指纹；运行中并发调工作台接口；打开回放三 tab 后指纹仍不变 | `python -m unittest tests.test_isolation` |
| 工件 | 写入→读取→列表→删除；损坏文件降级 | `python -m unittest tests.test_artifacts` |
| 回放一致性 | 每个采样点 `sync_frozen` 聚合值 == 存储序列 | `python -m unittest tests.test_replay_consistency` |
| 手工：主流程 | 建→跑→看过程→看结果→重跑→导出 | 按第 4 节清单 |
| 手工：回归 | 首页上传、客流量生成、四类调度、模拟大引擎、天气页 | 对照 M0 基线 |

---

## 7. 风险与对策

| 风险 | 评估（基于实测/代码） | 对策 |
|------|----------------------|------|
| 单次运行耗时 | 6 日实测 18.6 s（生成 12.0 s，推演 5.4 s） | 后台线程 + 阶段进度；默认日期选 1 天（约 3–4 s） |
| 随机性 | `hash()` 与集合迭代顺序跨进程不稳定；全局 RNG 会被并发污染 | M1 统一治理 + `PYTHONHASHSEED=0` + 集合排序；复现测试跨进程且覆盖天气/机组 |
| 隔离 | 全局 state + 全局服务实例 + 线上 paxflow 接口会写状态 | 局部实例 + 不写 state + 三处旅客流请求走作用域；隔离测试含回放 |
| 存储增长 | 约 2.5 MB/实验，不含 `pax_list` | 列表页显示占用；保留策略下一步 |
| 指标口径 | 旧看板是瞬时值，实验是累计值 | 加"全程"前缀 + tooltip + `definitions` |
| 机组质量 | 现有 6 日数据覆盖率约 86%、违规 40 项 | 如实展示 + `warnings`；明确算法质量不在本步 |
| 天气一致性 | 前端气旋与实验情景是两套语义 | 逐省逐窗口编译；回放用情景 manual 天气；详情页同时展示情景窗口 |
| 时间模型 | 生成器按"每月 30 天"简化，仅支持 11–12 月 | 实验日期限制在 11-30 ~ 12-05；文档注明 |
| 内存峰值 | 6 日 107,880 旅客对象 | 生成后立即抽取航班/链并释放 `pax_list`；不落盘 |
| CP-SAT | 25 s 时间上限，不可复现 | 实验白名单排除；UI 置灰 |
| 依赖与环境 | PATH 默认 Python 3.14 无 ortools；无 frontend node_modules | M0 用 3.13 建 venv；`requirements.txt` 补 `openpyxl` |
| `data_service` 懒加载竞态 | 多线程首次 `load_all()` 可能重复加载 | M3 运行前预热；可选给 `load_all` 加锁 |
| GIL 争用 | 生成约 10 s 的纯 Python 计算占 GIL，工作台会变慢 | 隔离测试只断言结果，不对耗时做断言；必要时把运行进程与 Web 进程分开（下一步） |

---

## 8. 待拍板事项（评审时确认）

| # | 事项 | 选项 | 推荐 | 影响 |
|---|------|------|------|------|
| 1 | 客流输入粒度 | A. 模板 + 全局缩放 + 粘贴城市对（第一步）<br>B. 在实验表单重建完整 1056 行矩阵 | **A** | 选 A 已能覆盖"输入自己的客流"；选 B 会让创建页复杂度翻倍，且与现有页面重复 |
| 2 | 天气/异常口径 | A. 后端情景程序（3 预设天气 + 机场关闭），复用 `compute_disruption`<br>B. 复刻前端气旋实时联动 | **A** | 选 B 无法离线复现，违背"可复现"验收 |
| 3 | 回放实现 | A. 工件 + 同引擎冻结计划重算（约 2.5 MB/实验）<br>B. 逐帧录制（数十 MB/实验） | **A** | 选 B 存储与渲染一致性都更难 |
| 4 | 随机源改造 | A. 允许对 crew/gate/passenger/sim 做 RNG 注入 + 稳定哈希（不改算法逻辑）<br>B. 不改，接受指标不可复现 | **A** | 选 B 则"可复现"验收无法通过 |
| 5 | 实验日期默认值 | A. 默认 1 天（11-30）<br>B. 默认 6 天 | **A** | 首次体验快；6 天可手动勾选 |

> 以上 5 项建议在开工前一次性确认；确认后 M0–M7 按顺序执行，中途不再改范围。

---

## 9. 与任务文档的差异/冲突（显式提示）

1. **"是否注入异常与天气" vs 现有前端驱动天气**：任务文档假设天气/异常可作为实验条件。现有系统的天气是"前端气旋 + 每 2s 回传"，实验无人操作，无法直接复用。方案改为"后端气象情景程序"，复用同一条 `compute_disruption` 装配链，保证结果口径一致；代价是实验天气不是"当天那场气旋"的逐帧复刻。
2. **"输入自己的客流量" vs 1056 行矩阵**：现有客流量输入页是全量城市对矩阵。第一步实验表单做"模板 + 缩放 + 粘贴城市对"，已能覆盖自定义客流；完整矩阵编辑仍在原页面。若评审要求实验表单也支持逐条表格编辑，需要额外 1 个页面级组件与校验。
3. **"不改动现有分析工作台页面与流程" vs 回放复用**：为让三个画面接受实验数据，需要给 `SimMapView` 加 `readonly`、`TerminalLayout` 两处 fetch 与 `TerminalFlowView` 一处 fetch 改走 `api`、`WeatherMap3D` 暴露 manual 入口。这些都是"只读开关/数据入口"，不改变默认行为，也不改变工作台流程；但严格说属于对现有组件的改动。
4. **"不改动任何调度算法本身" vs 随机源治理**：`hash()` → `stable_hash()`、全局 `random` → 实例 RNG 属于随机源改造，不改变算法策略与逻辑；但会改变机组/登机口的打散顺序（同一种子下稳定）。需评审确认可接受。
5. **"指标与现有看板对齐" vs 瞬时/累计差异**：现有 `DashboardView` 是仿真当前时刻的瞬时 KPI；实验是全程累计。方案保留同名公式但加"全程"前缀，避免用户把两个数直接对比。若要求完全同名同数，需要把看板也改成累计口径（会改动现有页面，不建议）。
6. **机组排班质量**：现有演示数据上机组覆盖率约 86%、违规 40 项。实验会如实展示这些数字；这不是本步改造失败，而是既有算法在 100 架机队/40 人机组池下的真实结果。建议在结果页固定显示一条说明，避免误读。

---

## 10. 附录：现状代码索引

| 事项 | 位置 |
|------|------|
| 全局状态 | `backend/state/__init__.py:1-243` |
| 服务单例 | `backend/services/__init__.py:11-14` |
| 机组种子/全局 RNG | `backend/services/crew_service.py:344,696,751,1060,1319` |
| 机组指派随机 | `backend/services/pairing_assigner.py:38,229` |
| 集合迭代（顺序敏感） | `backend/services/pairing_assigner.py:55,196,250`；`weather_disruption_service.py:180,289` |
| 登机口种子/CP-SAT 时限 | `backend/services/gate_service.py:86,127,362` |
| 仿真随机起飞门限 | `backend/services/simulation_engine.py:520` |
| 仿真天气同步 | `backend/services/simulation_engine.py:262-299` |
| 旅客生成随机 | `backend/models/passenger_state.py:80-94` |
| 航班生成器参数 | `backend/services/flight_generator.py:288-334` |
| 机队比例（固定） | `backend/services/aircraft_types.py:44-52` |
| 生成接口 | `backend/routes/generate_routes.py:84-138` |
| 提交历史（写全局） | `backend/routes/generate_routes.py:186-279` |
| 旅客流固定读最近 gen_* | `backend/routes/generate_routes.py:400-464` |
| 飞机排班路由 | `backend/routes/schedule_routes.py:764-824` |
| 跑道调度路由 | `backend/routes/schedule_routes.py:865-942` |
| 登机口路由 | `backend/routes/schedule_routes.py:1108-1164` |
| 机组路由 | `backend/routes/schedule_routes.py:1231-1439` |
| 天气中断桥接 | `backend/services/weather_disruption_service.py:156-343` |
| 前端路由 | `demo/src/router/index.js` |
| 前端 API 封装 | `demo/src/api/index.js:441-556` |
| 三画面容器 | `demo/src/views/SimulationHub.vue:146-191` |
| 天气统一时钟 | `demo/src/components/WeatherMap3D.vue:2261-2389` |
| 旅客流取数 | `demo/src/components/TerminalLayout.vue:1234-1300` |
| 首页入口 | `demo/src/views/Home.vue:67-78` |

---

**下一步**：评审确认第 8 节 5 项事项后，按 M0 → M7 顺序开工；M1 完成时先跑一次"跨进程复现"测试，作为后续所有工作的可信基线。

---

## 11. 评审意见（2026-11-26）

**结论**：方向正确，现状诊断基本准确，可作为开工依据。以下 6 项须在开工前修订，其中第 1、2、5 项不修则"可复现"验收无法通过，第 3 项不修则"不打扰现场"验收无法通过。另有 5 项次要问题和 1 条流程建议。

### 11.1 已核实成立的部分

| 方案中的判断 | 核对结果 |
|--------------|----------|
| 耗时基线 | 复测 6 日生成 9.8 s，1,196 航班 / 100 链 / 107,880 旅客，与 11.5 s 同量级；"后台线程 + 轮询、不上任务队列"成立 |
| 航班生成确定性 | `FlightGenerator` 无随机源，更换 `PYTHONHASHSEED` 两次运行输出一致 |
| `sync_to` 缺陷 | `simulation_engine.py:278` 每次清零延误、`:286` 只在起飞前应用取消，新增 `sync_frozen` 有必要 |
| 局部实例可行 | `services/` 层不引用全局 `state`（`passenger_service.py` 除外） |
| `fleet_mix` 被忽略 | `flight_generator.py:319` 实际使用固定序列 |
| 第 9 节差异提示 | 任务文档与代码的冲突均已如实列出 |

### 11.2 开工前必须修订（6 项）

**1. 随机源治理漏了 `pairing_assigner.py`**

- `_best_random_disjoint`（`pairing_assigner.py:229`）用全局 `random.shuffle` 做 200 次试探。
- 实验默认的机组算法 `chain` 会经 `crew_service.py:811` 调到 `assign_pairings`。
- 方案只把 `crew_service` 改为实例 RNG。改完后，机组结果会从"进程内稳定"变成"每次都不同"（原本被 `random.seed` 意外固定，改后失去固定）。
- **修订**：把 RNG 作为参数传入 `assign_pairings(pairings, flights, crew_pool, rng=None)`，并补进 3.3 节"后端小改造"表。

**2. 只替换 `hash()` 不足以保证跨进程一致**

- 集合的迭代顺序同样随 `PYTHONHASHSEED` 变化。例如 `pairing_assigner.py:250` 直接遍历集合 `uncovered_by_id`，`compute_disruption` 的 `bad_provinces` 也是集合。
- **修订**：
  - 启动脚本固定 `PYTHONHASHSEED=0`，作为兜底；
  - 上述两处遍历改为 `sorted(...)`；
  - `test_repro` 的子进程用例必须覆盖"带天气 + 带机组"的条件，不能只测航班生成。

**3. 回放会调到一个改写现场的接口**

- `TerminalFlowView.vue:219` 的 `loadBackendDates()` 直接请求线上 `/api/paxflow/schedule`，方案只改了 `TerminalLayout` 的两处。
- 该接口内部会改写全局活跃航班、任务链和当前历史 ID（`generate_routes.py:439-461`）。只要打开回放的旅客流 tab，就会违反"实验不写全局 state"。
- 前端"作用域"（`scope.js`）是全局可变状态，离开回放页不复位的话，工作台会继续请求回放接口。方案未提及。
- **修订**：`TerminalFlowView` 的这处请求也走 `api.*`；`ExperimentDetailView` 在 `beforeDestroy` 中复位作用域为 `live`；`test_isolation` 增加"打开三画面回放后现场指纹不变"的用例。

**4. 旅客流调度的组装逻辑不可复用**

- 约 180 行组装代码写在路由函数里（`generate_routes.py:500-679`），机场硬编码为成都（`:516`）。
- 实验要产出 `paxflow.json` 只能复制这段代码，或者调用这个会写全局 state 的路由。
- **修订**：先把组装部分抽成纯函数（输入航班与排班，输出调度字典，不碰 `state`），路由与实验共同调用；这一步列入 M1 或 M2。同时写明：旅客流画面只在主基地包含成都时有数据，否则该 tab 显示"本实验无成都场航班"。

**5. 天气"一次性编译"的语义未定义**

- `compute_disruption` 用每条时间线 t=0 的点判定坏省份（`weather_disruption_service.py:176-185`），再把所有窗口并成一个（`:218`）。
- 现场模式每 2 秒以"当前"为 t=0 重算，所以这个逻辑在线上没有问题。实验一次算完则有两个后果：
  - 情景不以首个受影响时刻作为 t=0 时，该省被整体忽略，情景静默失效，不报错；
  - 多省起止不同会被并成一个大窗口，与逐省时间线不符。
- "机场临时关闭"不是省份天气，如何编译成计划也未说明。
- **修订**：在 `weather_program.py` 中明确编译规则：每个省份时间线从其首个坏天气点开始（t=0 对齐）；逐省输出窗口；机场关闭单独生成 `{type: 'cancel', ...}` 计划项并合并。为编译器补单元测试：多省错峰、延迟起始、机场关闭三个用例。

**6. M1 验收措辞不成立**

- "默认参数下输出与改造前一致"对机组和登机口做不到：改造前它们每次重启本来就不同（依赖 `hash()`）。
- **修订**：M1 产出改为"航班生成输出与改造前一致；机组、登机口、旅客生成在固定种子下同进程与跨进程均稳定"，并补记改造前机组/登机口跨重启不一致的证据作为对照。

### 11.3 次要问题（5 项）

| # | 问题 | 修订 |
|---|------|------|
| 1 | 实例口径不一：1.5 节写飞机排班、跑道用全局实例，3.7 节写新实例 | 统一为全部新实例。`runway_service.py:333` 的 `_set_airport` 会改实例状态 |
| 2 | M0 未指定 Python 版本 | 写明用 3.13：本机默认即 3.13，`ortools 9.12.4544` 可解析到 cp313 wheel；PATH 中的 3.14 没有 ortools |
| 3 | "遵守行数上限"的表述与清单矛盾 | `models/experiment.py` 约 160 行，超出 100 行上限；`api/index.js` 已 572 行还要再加。改为"新文件尽量遵守，超限处在清单中注明原因" |
| 4 | `SimulationEngine(rng)` 优先级 | `simulation_engine.py:520` 的随机只在线程推进路径上，冻结重算不经过。可降到 M5 之后再做 |
| 5 | 并发时延 | 生成阶段约 10 s 的纯 Python 计算会占用 GIL，运行期间工作台请求变慢但不会阻塞。隔离测试不对耗时做断言，只断言结果 |

### 11.4 对第 8 节 5 项待拍板的意见

五项均同意方案的推荐（1-A、2-A、3-A、4-A、5-A）。

仅第 1 项建议加一个折中：任务文档的标题目标是"输入自己的客流量"，而模板 + 缩放做不到这一点；后端 `city_traffic` 本身只是一个城市对列表。在表单"客流模板"旁加一个"粘贴城市对客流"文本框（每行 `城市,城市,人数`），直接作为生成器输入。成本低，能补上任务文档的核心诉求；完整矩阵编辑仍留在原页面。

### 11.5 流程建议

在 M1 与 M2 之间增加一个冒烟脚本：用一个进程内脚本跑完生成、四类调度、天气编译、冻结采样、指标落盘；再在子进程中跑两次并对比。第 11.2 节第 1、2、5 项的风险可以在写任何接口和页面之前暴露出来。
