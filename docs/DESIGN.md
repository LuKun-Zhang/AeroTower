# 成都双流机场 · 旅客流模拟系统 — 详细设计文档

> 基于 `terminal_layout.json` 和现有 `TerminalLayout.vue` 走廊网络

---

## 一、模拟目标

模拟双流机场一天的真实运营：

```
航班数据输入 → 自动分配登机口 → 按时刻表生成旅客 →
旅客到场 → 候机区等待 → 登机开放 → 经廊桥登机 →
飞机关舱 → 推出 → 滑行 → 跑道起飞/降落
```

---

## 二、物理空间定义

### 2.1 航站楼

| 名称 | 坐标 (x,y) | 尺寸 (w×h) | 中心 |
|------|-----------|------------|------|
| 航站楼1 (T1) | (65, 332) | 178×35 | (154, 349) |
| 航站楼2 (T2) | (372, 298) | 178×35 | (461, 315) |

### 2.2 指廊（Pier 脊柱）

T1 下方伸出 4 根垂直指廊，T2 下方伸出 3 根：

| 指廊 | x 范围 | y 范围 | 归属 |
|------|--------|--------|------|
| 矩形6 | 34 | 355→444 | T1 左一 |
| 矩形7 | 145 | 367→444 | T1 左二 |
| 矩形8 | 261 | 355→444 | T1 右/联通 |
| 矩形11 | 341 | 320→409 | T2 左 |
| 矩形12 | 452 | 332→409 | T2 中 |
| 矩形13 | 568 | 243→409 | T2 右（最长） |
| 矩形40 | 244→341 | 344 | T1↔T2 连廊 |

### 2.3 登机口（rect gate）

| 航站楼 | 数量 | 名称范围 |
|--------|------|----------|
| T1 | 22+ | 矩形16~39（部分被排除为特殊用途） |
| T2 | 26+ | 矩形44~92（部分被排除） |

每个 rect gate 附着在指廊两侧，尺寸约 31×5，有旋转角度。

### 2.4 跑道

| 名称 | 位置 | 尺寸 |
|------|------|------|
| 跑道一 | 底部水平 (34, 523) | 578×24 |
| 跑道二 | 右侧水平 (633, 307) | 578×24 |

### 2.5 入口/出口闸门

| 类别 | T1 | T2 |
|------|----|----|
| 入口 (downArrow) | 下95~下99（5个） | 下87~下91（5个） |
| 出口 (upArrow) | 上100、上101（2个） | 上93、上94（2个） |

---

## 三、区域功能划分

### 3.1 等待区（候机区）

```
┌─────────────────────────────────────────────┐
│  航站楼1 内部区域 (65,332, 178×35)            │
│  ┌─────────────────────────────────────┐    │
│  │  ░░░░ 旅客候机区 ░░░░               │    │
│  │  值机 → 安检 → 候机大厅 → 登机口     │    │
│  └─────────────────────────────────────┘    │
│  乘客在此等待，直到航班开始登机                │
└─────────────────────────────────────────────┘
```

- **T1 候机区**: 航站楼1 矩形内部 (区号: `WAIT_T1`)
- **T2 候机区**: 航站楼2 矩形内部 (区号: `WAIT_T2`)
- 旅客到达后在此随机分布，等待航班登机广播

### 3.2 闸机/检查点

| 检查点类型 | 位置 | 对应 gate |
|------------|------|-----------|
| **入口闸机** | 10个 downArrow gate | 下87~下99 |
| **出口闸机** | 4个 upArrow gate | 上93、上94、上100、上101 |
| **登机闸口** | 每个 rect gate | 登机前15分钟开放 |
| **跑道入口** | 跑道端点 | 起飞/降落调度 |

### 3.3 走廊网络分层

现有 391 条走廊分为以下功能层：

| 层级 | routeType | 数量 | 功能 |
|------|-----------|------|------|
| **到港汇集层** | `t1-trunk`, `t2-trunk` | 10 | 旅客从入口到航站楼主干 |
| **登机分支层** | `t1-in`, `t2-in` | 285 | 航站楼→登机口 |
| **离港疏散层** | `t1-out`, `t2-out` | 57 | 登机口→出口 |
| **跨楼联通层** | `conn`, `link` | 3 | T1↔T2 中转通道 |
| **登机引道层** | `gate-approach` | 28 | 主干→特殊登机口 |
| **出口引道层** | `exit-approach` | 8 | 出口→疏散主干 |

---

## 四、数据模型

### 4.1 航班 (Flight)

```javascript
{
  flightNo: 'CA4501',           // 航班号
  airline: 'CA',                // 航空公司
  type: 'departure',            // departure | arrival
  terminal: 'T1',               // T1 | T2
  gateName: '矩形37',           // 分配的登机口
  scheduledTime: 510,           // 计划时刻 (分钟，08:30 = 510)
  actualTime: 510,              // 实际时刻
  status: 'scheduled',          // scheduled | boarding | taxiing | departed | landed | parked
  passengers: [],               // 关联旅客 ID 列表
  paxTotal: 160,                // 总载客数
  paxBoarded: 0,                // 已登机数
  boardingOpenTime: null,       // 实际开放登机时间
  boardingCloseTime: null,      // 登机关闭时间
  runwayTime: null,             // 进入跑道时间
}
```

### 4.2 旅客 (Passenger)

```javascript
{
  id: 'pax_001',
  flightId: 'CA4501',           // 所属航班
  type: 'departing',            // departing | arriving | transit
  terminal: 'T1',
  status: 'arriving',           // 状态机见第五节
  position: {                   // 当前位置
    zone: 'WAIT_T1',            // 区域代码
    x: 120, y: 345,             // 坐标
  },
  route: {                      // 规划路线
    corridorIdx: 5,
    progress: 0.0,
    laneOffset: 0.3,
  },
  arrivalTime: 430,             // 到达机场时间（出发前1小时±15分钟随机）
  speeds: {                     // 各阶段速度
    walk: 0.008,                // 走廊行走速度
    wait: 0,                    // 等待中
  },
}
```

### 4.3 登机口分配 (Gate Assignment)

```javascript
{
  gateName: '矩形37',
  terminal: 'T1',
  pierRef: '矩形6',             // 所属指廊
  currentFlight: 'CA4501',      // 当前占用航班
  occupiedUntil: 540,           // 占用截止时间
  schedule: [                   // 当日排班
    { flightNo: 'CA4501', start: 480, end: 510 },
    { flightNo: 'MU5401', start: 540, end: 570 },
  ],
}
```

### 4.4 跑道调度队列

```javascript
// 起飞队列
runwayTakeoffQueue: [
  { flightNo: 'CA4501', readyTime: 515, assignedRunway: '跑道一' },
  ...
]
// 降落队列
runwayLandingQueue: [
  { flightNo: '3U8802', eta: 530, assignedRunway: '跑道二' },
  ...
]
```

---

## 五、旅客状态机

```
┌──────────┐    到达机场     ┌──────────┐   安检通过   ┌──────────┐
│  OUTSIDE │ ──────────────→ │ CHECKING │ ──────────→ │ WAITING  │
│  (场外)  │                 │ (值机)   │             │ (候机中) │
└──────────┘                 └──────────┘             └────┬─────┘
                                                           │
                                             登机广播 (起飞前15分钟)
                                                           │
                                                      ┌────▼─────┐
    ┌──────────┐    飞机起飞    ┌──────────┐          │ BOARDING │
    │ DEPARTED │ ←─────────── │ BOARDED  │ ←─────── │ (登机中) │
    │ (已起飞) │              │ (已登机) │          └──────────┘
    └──────────┘              └──────────┘
    
    ┌──────────┐    飞机降落    ┌──────────┐   下机完成   ┌──────────┐
    │  LANDED  │ ────────────→ │ UNLOADING│ ──────────→ │ EXITING  │
    │ (已降落) │              │ (下客中) │             │ (离场中) │
    └──────────┘              └──────────┘             └────┬─────┘
                                                           │
                                                     到达出口
                                                      ┌────▼─────┐
                                                      │   EXIT   │
                                                      │ (已离开) │
                                                      └──────────┘
```

### 5.1 时间线（以出发航班为例）

| 时间 | 航班状态 | 旅客状态 | 可视化 |
|------|----------|----------|--------|
| T-60min | scheduled | 旅客陆续到达机场，进入候机区 | 粒子在航站楼内出现 |
| T-15min | boarding_open | 广播登机，旅客走向登机口 | 粒子沿走廊流向登机口 |
| T-5min | boarding_closing | 最后登机广播 | 走廊上粒子减少 |
| T-0min | taxiing | 所有旅客已登机，飞机关舱 | 候机区清零 |
| T+5min | taking_off | 飞机滑行至跑道起飞 | 飞机图标移向跑道 |

---

## 六、登机口分配算法

### 6.1 约束条件

1. 同一登机口同一时间只能停靠一架飞机
2. 前后航班间隔 ≥ 10 分钟（周转时间）
3. 优先分配同航站楼的登机口
4. 大型航班优先分配长指廊端头登机口
5. 相邻登机口避免同时推出（地面冲突）

### 6.2 贪心分配

```
输入：当日航班列表（按时刻排序）
输出：每个航班的登机口分配

for 每个航班 f:
    1. 筛选 f.terminal 对应航站楼的可用登机口
    2. 按"与航站楼距离"排序（近者优先）
    3. 检查时间冲突：前序航班已离开 ≥ 10min
    4. 分配第一个通过冲突检查的登机口
    5. 如无可用，标记为溢出（延后处理）
```

---

## 七、跑道调度

### 7.1 跑道使用策略

- **跑道一**（底部水平）：主要用于 T1 航班
- **跑道二**（右侧水平）：主要用于 T2 航班
- 单跑道安全间隔：起飞间隔 ≥ 2分钟，降落间隔 ≥ 3分钟
- 起飞/降落交替：同跑道不可同时起降

### 7.2 排序

```
起飞队列：按计划时刻排序，间隔 ≥ 2min
降落队列：按预计到达时间排序，间隔 ≥ 3min
```

---

## 八、可视化设计

### 8.1 飞机显示

- **停靠中**：小飞机图标停在登机口位置
- **推出滑行**：飞机沿指廊间隙缓慢移向跑道
- **跑道上**：飞机在跑道上加速动画
- **空中**：小飞机图标在跑道外侧消失

飞机滑行路线：登机口 → 指廊间通道 → 跑道入口 → 跑道

### 8.2 旅客状态颜色

| 状态 | 颜色 | 说明 |
|------|------|------|
| waiting | 绿色 #4caf50 | 候机中，航站楼内静止 |
| boarding | 黄色 #ff9800 | 走向登机口 |
| exiting | 蓝色 #2196f3 | 走向出口 |
| transit | 粉色 #e91e63 | 中转，跨楼联通走廊 |
| stranded | 红色 #f44336 | 延误滞留 |
| evacuating | 红色闪烁 | 应急疏散 |

### 8.3 信息面板

| 面板 | 内容 |
|------|------|
| 航班牌 | 航班号、登机口、计划时刻、状态、登机进度 |
| KPI 仪表板 | 准点率、在途旅客、候机人数、已起飞数 |
| 登机口占用率 | 热力图：各指廊登机口使用密度 |
| 延误统计 | 延误航班列表、延误原因、受影响旅客数 |

---

## 九、实施阶段

### Phase 1 — 航班数据 + 登机口分配（后端核心）

- 生成当日航班时刻表（基于 realistic 数据）
- 实现登机口贪心分配算法
- 航班状态机：scheduled → boarding → taxiing → taking_off → completed

### Phase 2 — 旅客生成 + 状态机（后端）

- 按航班时刻表生成旅客（出发前 60±15 分钟到场）
- 实现旅客完整状态机
- 登机事件：起飞前 15 分钟广播，旅客从等待区释放到走廊

### Phase 3 — 飞机滑行动画（前端）

- 飞机图标渲染（使用现有 drawPlane 替代品）
- 登机口→跑道滑行路径规划
- 起飞/降落动画

### Phase 4 — 跑道调度（后端）

- 起飞/降落队列管理
- 安全间隔控制
- 跑道占用状态可视化

### Phase 5 — 事件注入 + 应急（前后端）

- 延误、取消、备降等异常事件
- 登机口故障 → 重新分配
- 应急疏散

### Phase 6 — 完善可视化

- 航站楼内候机人数标注
- 走廊实时拥堵热力图
- 登机口占用率仪表板

---

## 十、关键路线划定为等待区

```
等待区分配:
  T1 → 航站楼1 内部区域 (WAIT_T1)
  T2 → 航站楼2 内部区域 (WAIT_T2)

闸机位置:
  入口: 下95~下99 (T1), 下87~下91 (T2)
  出口: 上100~上101 (T1), 上93~上94 (T2)
  登机闸口: 每个 rect gate 在登机前15分钟开启
  跑道入口: 跑道一左端、跑道二顶端

旅客路线:
  出发: 入口 → 航站楼候机区 → 登机口 → 飞机
  到达: 飞机 → 登机口 → 航站楼 → 出口
  中转: 飞机→T1登机口→航站楼1→跨楼走廊→航站楼2→T2登机口→飞机
```

---

## 十一、现有代码改造范围

### 不动（红线）

- `terminal_layout.json` 不动
- 所有 `drawRunways` / `drawPiers` / `drawTerminals` / `drawGates` / `drawSpines` 不动
- `routeCorridors` 的 waypoints 生成不动
- `drawCorridors` 基础渲染不动

### 改动

| 文件 | 改动内容 |
|------|----------|
| 新增 `flight_schedule.json` | 当日航班数据 |
| 新增 `backend/services/flight_scheduler.py` | 航班调度 + 登机口分配 |
| 新增 `backend/services/passenger_generator.py` | 旅客生成 + 状态机 |
| 新增 `backend/services/runway_scheduler.py` | 跑道调度 |
| 改造 `TerminalLayout.vue` | 飞机绘制、旅客状态机改造、时间线重做 |
| 新增 `FlightSchedulePanel.vue` | 航班计划面板 |
| 改造 `FlightBoard.vue` | 接入真实航班数据 |

---

## 十二、飞机 2D 可视化方案

> 决策：不采用 3D（Three.js/Babylon.js）渲染，保持与现有 2D Canvas 机场俯视图一致。
> 飞机模型使用 `A320.glb` 一次性生成俯视快照 PNG，作为 2D 精灵绑定到 Canvas 上。

### 12.1 GLB → PNG 俯视快照

**一次性操作**：用 Node.js 脚本加载 `demo/public/models/A320.glb`，Three.js 相机置顶渲染，导出 PNG。

```
scripts/glb_snapshot.js

流程：
  Three.js 加载 A320.glb
  → 相机位置: (0, 500, 0)，朝向 (0, 0, 0)，正交投影
  → 渲染到 OffscreenCanvas
  → 导出为 A320_topdown.png (建议 128×128 或 256×256)
  → 放入 demo/src/assets/airplane.png
```

**脚本关键代码：**

```javascript
// scripts/glb_snapshot.js
const { createCanvas } = require('canvas')  // node-canvas
const { GLTFLoader } = require('three/examples/jsm/loaders/GLTFLoader')
const THREE = require('three')

async function snapshotGLB(inputPath, outputPath, size = 256) {
  const canvas = createCanvas(size, size)
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true })
  const scene = new THREE.Scene()
  const camera = new THREE.OrthographicCamera(-30, 30, 30, -30, 0.1, 1000)
  camera.position.set(0, 500, 0)
  camera.lookAt(0, 0, 0)

  const loader = new GLTFLoader()
  const gltf = await loader.loadAsync(inputPath)
  scene.add(gltf.scene)

  // 光照
  scene.add(new THREE.AmbientLight(0xffffff, 0.7))
  scene.add(new THREE.DirectionalLight(0xffffff, 0.5))

  renderer.render(scene, camera)

  const fs = require('fs')
  const buffer = canvas.toBuffer('image/png')
  fs.writeFileSync(outputPath, buffer)
  console.log('Snapshot saved to', outputPath)
}

snapshotGLB(
  'demo/public/models/A320.glb',
  'demo/src/assets/airplane_takeoff.png',
  256
)
```

**运行：**
```bash
cd d:\Desktop\job-data-visualization-team-master
node scripts/glb_snapshot.js
```

**输出文件：**
| 文件 | 用途 |
|------|------|
| `demo/src/assets/airplane_takeoff.png` | 起飞角度（机头朝右上） |
| `demo/src/assets/airplane_side.png` | 侧向滑行角度（机头朝右） |

> 只需生成两个角度（纵向/横向），运行时通过 Canvas `rotate()` 实现任意朝向。

### 12.2 飞机精灵数据结构

```javascript
// 在 TerminalLayout.vue data 中添加
airplanes: [
  {
    id: 'plane_CA4501',
    flightNo: 'CA4501',
    flightId: 'CA4501',
    type: 'departure',           // departure | arrival
    status: 'at_gate',           // 状态机见 12.4

    // 当前姿态
    x: 154, y: 349,              // 世界坐标
    angle: 0,                    // 朝向角度（弧度）
    scale: 1.0,                  // 缩放（起降动画用）
    alpha: 1.0,                  // 透明度

    // 滑行路径
    taxiPath: [                  // 预计算的滑行路径点
      { x: 154, y: 370 },       // 登机口推出位置
      { x: 154, y: 440 },       // 指廊末端
      { x: 34,  y: 500 },       // 跑道一入口
      { x: 100, y: 523 },       // 跑道上加速
      { x: 400, y: 523 },       // 跑道中段
    ],
    pathProgress: 0,             // 滑行进度 0~1
    pathSpeed: 0.005,            // 滑行速度

    // 时间相关
    gateReadyTime: 480,          // 登机口就绪时间
    taxiStartTime: 500,          // 开始滑行时间
    takeoffReadyTime: 505,       // 起飞就绪时间

    // 精灵
    img: null,                   // Image 对象，由 loadAssets 预加载
  },
  ...
]
```

### 12.3 滑行路径规划

#### 12.3.1 登机口 → 跑道入口（出发）

基于现有指廊/主干结构，硬编码 4 条滑行通道：

```
通道1 (T1左侧): 矩形6下方间隙
  登机口 → 矩形6底部 (y≈444) → 水平滑行至 x≈34 → 跑道一左端

通道2 (T1右侧): 矩形7/8之间间隙
  登机口 → 矩形7或8底部 → 水平滑行至跑道一

通道3 (T2左侧): 矩形11下方间隙
  登机口 → 矩形11底部 (y≈409) → 向左滑行至 x≈341 → 跑道一右端
  （或向右滑行至跑道二左端）

通道4 (T2右侧): 矩形12/13之间间隙
  登机口 → 矩形12或13底部 → 向右滑行至跑道二
```

**路径数据结构：**

```javascript
// 预定义滑行通道
const TAXI_CHANNELS = {
  // 每个登机口 → 所属通道的映射
  gateToChannel: {
    // T1 登机口
    '矩形16': 't1_left',  '矩形17': 't1_left',  // ...
    '矩形25': 't1_right', '矩形26': 't1_right', // ...
    // T2 登机口
    '矩形53': 't2_left',  '矩形54': 't2_left',  // ...
    '矩形62': 't2_right', '矩形63': 't2_right', // ...
  },

  // 通道终点（跑道入口）
  channelEndpoints: {
    t1_left:  { x: 34,  y: 510, angle: 0,          runway: '跑道一' },
    t1_right: { x: 280, y: 510, angle: 0,          runway: '跑道一' },
    t2_left:  { x: 341, y: 487, angle: 0,          runway: '跑道一' },
    t2_right: { x: 633, y: 380, angle: Math.PI/2,  runway: '跑道二' },
  },
}
```

**路径生成：**

```javascript
generateTaxiPath(gateName, channelName) {
  const gate = this.allGates.find(g => g.name === gateName)
  const end = TAXI_CHANNELS.channelEndpoints[channelName]
  const midY = gate.y + gate.h + 40  // 推出到指廊下方

  // 简单三段式路径
  return [
    { x: gate.x + gate.w/2, y: gate.y + gate.h/2 },  // 当前位置
    { x: gate.x + gate.w/2, y: midY },                // 推出
    { x: end.x,              y: midY },                // 水平滑行
    { x: end.x,              y: end.y },               // 对齐跑道
  ]
}
```

### 12.4 飞机状态机

```
┌──────────┐    加载到登机口    ┌──────────┐   旅客登机完成  
│ SCHEDULED │ ────────────────→ │ AT_GATE  │ ────────────→
│ (计划中)  │                   │ (停机位) │
└──────────┘                   └────┬─────┘
                                    │ 关舱推出
                               ┌────▼─────┐
                               │  TAXIING │ 滑行到跑道入口
                               └────┬─────┘
                                    │ 到达跑道
                               ┌────▼──────┐
                               │ TAKING_OFF│ 跑道上加速，scale: 1.0→0.3
                               └────┬──────┘
                                    │ 动画完成
                               ┌────▼──────┐
                               │ DEPARTED  │ 移除飞机
                               └───────────┘

到达流程：
┌──────────┐    飞机出现       ┌──────────┐   减速到停机位
│ APPROACH │ ────────────────→ │ LANDING  │ ────────────→
│ (进近中) │   跑道远端进入    │ (降落中) │
└──────────┘                   └────┬─────┘
                                    │ 脱离跑道
                               ┌────▼─────┐
                               │  TAXIING │ 滑行到登机口
                               └────┬─────┘
                                    │ 到达
                               ┌────▼──────┐
                               │  AT_GATE  │ 下客
                               └────┬──────┘
                                    │ 下客完成
                               ┌────▼──────┐
                               │ TURNAROUND│ 清洁/加油/准备
                               └───────────┘
```

### 12.5 起降动画实现

**起飞动画（在 `simTick` 中处理）：**

```javascript
updateAirplanes() {
  for (const plane of this.airplanes) {
    switch (plane.status) {

      case 'TAXIING':
        // 沿滑行路径移动
        plane.pathProgress += plane.pathSpeed * this.simState.speed
        if (plane.pathProgress >= 1.0) {
          plane.pathProgress = 0
          plane.status = 'TAKING_OFF'
        } else {
          const pos = interpolatePath(plane.taxiPath, plane.pathProgress)
          plane.x = pos.x
          plane.y = pos.y
          // 朝向跟随路径方向
          plane.angle = getPathAngle(plane.taxiPath, plane.pathProgress)
        }
        break

      case 'TAKING_OFF':
        // 跑道上加速 + 缩小
        plane.x += Math.cos(plane.angle) * 3 * this.simState.speed
        plane.y += Math.sin(plane.angle) * 3 * this.simState.speed
        plane.scale -= 0.005 * this.simState.speed
        if (plane.scale <= 0.1) {
          plane.status = 'DEPARTED'
        }
        break

      case 'LANDING':
        // 跑道上减速 + 放大
        plane.x += Math.cos(plane.angle) * 3 * this.simState.speed * 0.7
        plane.y += Math.sin(plane.angle) * 3 * this.simState.speed * 0.7
        plane.scale += 0.008 * this.simState.speed
        if (plane.scale >= 1.0) {
          plane.scale = 1.0
          plane.status = 'TAXIING'  // 转为滑行到登机口
          plane.pathProgress = 0
          // 反向路径：跑道出口 → 登机口
          plane.taxiPath = this.generateTaxiPath(plane.gateName, plane.channelName).reverse()
        }
        break
    }
  }

  // 清理已出发的飞机
  this.airplanes = this.airplanes.filter(p => p.status !== 'DEPARTED')
}
```

**绘制飞机精灵：**

```javascript
drawAirplanes() {
  const ctx = this.$refs.canvas.getContext('2d')
  for (const plane of this.airplanes) {
    const sx = this.tx(plane.x)
    const sy = this.ty(plane.y)
    const size = 32 * plane.scale

    ctx.save()
    ctx.globalAlpha = plane.alpha
    ctx.translate(sx, sy)
    ctx.rotate(plane.angle)

    // 选择精灵：跑道方向用纵向图，滑行用横向图
    const img = plane.status === 'TAKING_OFF' || plane.status === 'LANDING'
      ? this._spriteTakeoff
      : this._spriteSide

    if (img) {
      ctx.drawImage(img, -size/2, -size/2, size, size)
    } else {
      // 降级：绘制色块
      ctx.fillStyle = '#fff'
      ctx.fillRect(-size/2, -size/2, size, size * 0.3)
    }

    // 航班号标签
    ctx.rotate(-plane.angle)
    ctx.fillStyle = '#fff'
    ctx.font = 'bold 10px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(plane.flightNo, 0, -size/2 - 4)

    ctx.restore()
  }
}
```

**精灵预加载：**

```javascript
// 在 mounted 中调用
loadAssets() {
  this._spriteTakeoff = new Image()
  this._spriteTakeoff.src = require('@/assets/airplane_takeoff.png')
  this._spriteSide = new Image()
  this._spriteSide.src = require('@/assets/airplane_side.png')
}
```

### 12.6 跑道使用分配

| 起降方向 | 跑道 | 使用航站楼 | 滑行通道 |
|----------|------|-----------|----------|
| 起飞 | 跑道一（底部） | T1大部分、T2左半 | t1_left, t1_right, t2_left |
| 起飞 | 跑道二（右侧） | T2右半 | t2_right |
| 降落 | 跑道一 | T1进港航班 | t1_left, t1_right（反向） |
| 降落 | 跑道二 | T2进港航班 | t2_right（反向） |

**简化规则：**
- T1 出发/到达 → 跑道一
- T2 出发/到达 → 跑道二（x>450 用跑道二，否则用跑道一）
- 安全间隔：同跑道起降间隔 ≥ 3 ticks（~15秒真实时间）

### 12.7 绘制层次

在动画循环中，飞机精灵绘制顺序：

```
drawAll()          ← 静态场景（runway/pier/terminal/gate/spine）
drawCorridors()    ← 走廊（不动）
drawHeatmapOverlay() ← 热力图覆盖（可选）
drawAirplanes()    ← ★ 飞机精灵（在跑道/滑行道上）
drawGateOverlays() ← 闸门状态标记
drawWaitingStats() ← 候机人数标注
drawPassengers()   ← 旅客粒子（在飞机之下、走廊之上）
```

> 飞机绘制在旅客之上，这样旅客走走廊时不会被飞机遮挡。
> 飞机绘制在跑道（drawRunways）之后、走廊之前，这样飞机在滑行/起降时覆盖在跑道上。

### 12.8 飞机生命周期完整时间线（出发航班）

```
模拟时间   飞机状态          动画效果
────────────────────────────────────────────
T-20min   SCHEDULED         无显示
T-20min   → AT_GATE        飞机精灵出现在登机口旁
T-15min   登机广播          旅客走向登机口，paxBoarded 增长
T-2min    登机完成          旅客全部登机
T-0min    → TAXIING         飞机推出，沿滑行道→跑道
T+3min    → TAKING_OFF      飞机在跑道上加速，scale 1.0→0.1
T+3.5min  → DEPARTED        飞机 scale 归零，从数组移除
```

### 12.9 飞机生命周期完整时间线（到达航班）

```
模拟时间   飞机状态          动画效果
────────────────────────────────────────────
T-5min    APPROACH          无显示（准备中）
T-0min    → LANDING         飞机精灵出现在跑道远端，scale 0.2
T+1min    减速中            scale 0.2→1.0，减速移动
T+2min    → TAXIING         脱离跑道，反向滑行到登机口
T+5min    → AT_GATE         飞机停在登机口
T+5min    开始下客          旅客从登机口→航站楼→出口（离港流）
T+20min   下客+过站完成     飞机进入 TURNAROUND 或移除
```

### 12.10 跑道冲突检测

每 tick 检查：

```javascript
checkRunwayConflicts() {
  const runway1 = this.airplanes.filter(p =>
    (p.status === 'TAKING_OFF' || p.status === 'LANDING') &&
    p.assignedRunway === '跑道一'
  )
  const runway2 = this.airplanes.filter(p =>
    (p.status === 'TAKING_OFF' || p.status === 'LANDING') &&
    p.assignedRunway === '跑道二'
  )
  // 同跑道同时段只允许一架飞机
  // 如果冲突：后到的等待 3 ticks
}
```
