# 川航航班调度可视化系统 — 开发规范

> 以下简称「本项目」。**每次编码前请务必阅读本文档。**

---

## 一、核心原则

### 1.1 禁止单体文件

- 单个 `.py` 文件不超过 **200 行**
- 单个 `.vue` 文件不超过 **300 行**（含 template + script + style）
- 单个 `.js` 文件不超过 **200 行**

超过上述限制，必须拆分为多个文件或组件。

### 1.2 单一职责

每个文件只做一件事。如果一个文件可以通过“和”来描述它的功能，就应该拆分。

```
❌ flight_service.py  → "航班管理 和 飞机排班 和 跑道调度"
✅ routing_service.py → "飞机排班"
✅ runway_service.py  → "跑道调度"
```

### 1.3 严禁重复代码

同一段逻辑出现**两次**，抽成函数；出现**三次**，抽成独立模块。

---

## 二、目录结构与分包规则

### 2.1 后端 `backend/`

```
backend/
├── app.py                          # Flask 入口（仅注册路由，≤80行）
├── config.py                       # 全局配置（≤50行）
├── requirements.txt
│
├── models/                         # 数据模型层（每个文件≤100行）
│   ├── flight.py                   # 航班模型
│   ├── aircraft.py                 # 飞机模型
│   ├── airport.py                  # 机场模型
│   ├── crew.py                     # 机组模型（Phase 2）
│   └── gate.py                     # 登机口模型（Phase 2）
│
├── services/                       # 业务逻辑+算法（每个文件≤200行）
│   ├── data_service.py             # 数据加载与管理
│   ├── routing_service.py          # 飞机排班算法
│   ├── runway_service.py           # 跑道调度算法
│   ├── gate_service.py             # 登机口分配（Phase 2）
│   ├── crew_service.py             # 机组排班（Phase 2）
│   └── recovery_service.py         # 异常恢复（Phase 3）
│
└── utils/                          # 工具函数（每个文件≤100行）
    ├── data_loader.py              # JSON/Excel 数据读取
    ├── graph_utils.py              # 图论工具
    └── time_utils.py               # 时间格式转换
```

#### 拆分规则

| 层级 | 职责 | 行数上限 |
|------|------|----------|
| `models/` | 纯数据结构，不含算法 | 100 行 |
| `services/` | 一个文件对应一个调度模块 | 200 行 |
| `utils/` | 纯函数工具，无状态 | 100 行 |
| `app.py` | 仅注册路由，不含业务逻辑 | 80 行 |

#### 路由过多时的拆分

当 `app.py` 中路由超过 **6 个**，创建 `routes/` 目录：

```
backend/
└── routes/
    ├── flight_routes.py
    ├── routing_routes.py
    └── runway_routes.py
```

`app.py` 改为：

```python
from .routes import flight_routes, routing_routes, runway_routes
app.register_blueprint(flight_routes.bp)
app.register_blueprint(routing_routes.bp)
app.register_blueprint(runway_routes.bp)
```

---

### 2.2 前端 `demo/src/`

```
demo/src/
├── main.js                        # Vue 入口（≤30行）
├── App.vue                        # 根组件（≤150行）
│
├── api/                           # HTTP 请求封装
│   └── index.js                   # 所有 API 调用（≤200行）
│
├── views/                         # 页面级组件（每个≤300行）
│   ├── MapView.vue                # 地图视图
│   ├── RoutingView.vue            # 飞机排班页面
│   ├── RunwayView.vue             # 跑道调度页面
│   ├── GateView.vue               # 登机口分配（Phase 2）
│   ├── CrewView.vue               # 机组排班（Phase 2）
│   └── RecoveryView.vue           # 异常恢复（Phase 3）
│
├── components/                    # 可复用组件（每个≤200行）
│   ├── layout/                    # 布局组件
│   │   └── TabBar.vue
│   ├── charts/                    # 图表组件
│   │   ├── GanttChart.vue         # 甘特图
│   │   ├── TimelineChart.vue      # 时间线图
│   │   ├── PieChart.vue           # 饼图
│   │   └── HeatmapChart.vue       # 热力图
│   ├── MapView.vue                # 地图组件
│   ├── CtrlPanel.vue              # 时间控制面板
│   └── StatsPanel.vue             # 统计指标面板
│
├── store/                         # Vuex 状态管理
│   └── index.js
│
├── router/                        # 路由
│   └── index.js
│
└── utils/                         # 前端工具
    ├── format.js                  # 时间/数字格式化
    └── chart-helper.js            # ECharts 配置辅助
```

#### 组件拆分规则

| 层级 | 说明 | 行数上限 |
|------|------|----------|
| `views/` | 页面容器，组合 components | 300 行 |
| `components/` | 可复用组件，不含业务逻辑 | 200 行 |
| `components/charts/` | ECharts 图表，只接收 options prop | 150 行 |

#### Vue 组件拆分信号

出现以下情况立即拆分：
1. `<template>` 超过 **100 行** → 拆子组件
2. `<script>` 中 methods 超过 **5 个** → 考虑拆
3. 页面中有两个独立的功能区块 → 各成一个组件

---

## 三、编码规范

### 3.1 Python 后端

```python
# ✅ 正确：小函数、类型清晰
def can_connect(flight_a: Flight, flight_b: Flight, min_gap: int = 60) -> bool:
    """航班 A 结束后能否衔接航班 B"""
    return flight_a.arrival_minutes + min_gap <= flight_b.departure_minutes

# ❌ 错误：大函数、逻辑堆砌
def do_everything(flights):
    # 50行加载数据
    # 50行排班计算
    # 50行跑道调度
    # 50行输出结果
    pass
```

### 3.2 Vue 前端

```vue
<!-- ✅ 正确：组件组合 -->
<template>
  <div class="page">
    <StatsPanel :data="stats" />
    <GanttChart :aircrafts="aircrafts" />
  </div>
</template>

<!-- ❌ 错误：所有东西写在一个组件里 -->
<template>
  <div class="page">
    <!-- 100行统计 -->
    <!-- 100行甘特图 -->
    <!-- 100行控制面板 -->
  </div>
</template>
```

### 3.3 API 请求

```javascript
// ✅ 正确：通过 api/index.js 统一调用
import api from '@/api'
const result = await api.runRouting('bipartite')

// ❌ 错误：在组件里直接 fetch
const res = await fetch('http://localhost:5000/api/schedule/routing', {...})
```

### 3.4 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Python 文件 | 小写下划线 | `routing_service.py` |
| Python 类 | 大驼峰 | `AircraftRoutingService` |
| Python 函数 | 小写下划线 | `solve_bipartite()` |
| Vue 组件 | 大驼峰 | `RoutingView.vue` |
| Vue props | 小驼峰 | `currentTime` |
| Vue methods | 小驼峰 | `runRouting()` |
| JS 文件 | 小写/小写连字符 | `chart-helper.js` |
| API 路由 | 小写复数名词 | `/api/flights` |

---

## 四、Git 提交规范

```
<type>: <简短描述>

类型：
  feat     - 新功能
  fix      - 修bug
  refactor - 重构（不改变功能）
  style    - 格式调整
  docs     - 文档

示例：
  feat: 添加飞机排班二分图匹配算法
  fix: 修复甘特图时间偏移问题
  refactor: 拆分 RunwayView.vue 中时间线组件
```

---

## 五、新增模块检查清单

每次新增一个调度模块前，确认以下内容：

- [ ] 后端 `models/` 中是否已有对应数据模型？没有则新建（≤100行）
- [ ] 后端 `services/` 中是否已有对应服务文件？没有则新建（≤200行）
- [ ] 前端 `views/` 中是否已有对应页面？没有则新建（≤300行）
- [ ] 可复用组件是否抽到 `components/`？（≤200行）
- [ ] API 调用是否通过 `api/index.js`？
- [ ] 新文件行数是否在限制内？

---

## 六、禁止事项

1. **禁止**在 `.vue` 的 `<style scoped>` 中写全局样式（放到 App.vue 的非 scoped 块）
2. **禁止**在 `services/` 中直接操作 Flask request/response（保持纯逻辑）
3. **禁止**在 `models/` 中导入 `services/`（数据模型不依赖业务）
4. **禁止**创建 `common.py`、`helpers.py` 等万能文件（按功能拆分）
5. **禁止**超过行数上限后仍然在同一文件追加代码
