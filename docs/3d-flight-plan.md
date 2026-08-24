# 3D 航班模拟界面开发计划

## 目标

将 `SimMapView.vue` 中的 2D 地图航班模拟替换为 3D 场景，加载 A320 飞机模型，实现立体地形上的机场标记、航线弧和飞机动画。

## 当前状态

| 文件 | 状态 | 说明 |
|------|------|------|
| `demo/src/views/PlaneModelPreview.vue` | 已完成 | A320.glb 模型加载预览，可旋转缩放查看 |
| `demo/src/views/SimMapView.vue` | 现有 | 2D 航班模拟主界面，使用 `<Map>` 组件 |
| `demo/src/components/Map.vue` | 现有 | 2D ECharts 地图，显示航班位置 |
| `demo/src/components/FlightInfoPopup.vue` | 现有 | 航班信息弹窗 |
| `demo/src/components/WeatherMap3D.vue` | 参考 | 3D 气象地图，可复用部分基础设施（底座、坐标转换、OrbitControls） |

## 实施步骤

### 阶段一：创建 FlightMap3D.vue 核心组件

**功能：**
- Three.js 3D 场景初始化（Renderer、Scene、Camera、OrbitControls）
- 中国地图绿色底座（参考 WeatherMap3D 的地面网格）
- 地形高度位移（复用 terrainTex / heightTex 采样逻辑）
- 机场 3D 标记点（发光圆点 + 文字标签）

**依赖：**
- 复用 WeatherMap3D 中的 `lngLatToWorld()`、`CHINA` 地理常量、`MAP_W`/`MAP_H`
- 独立的 Three.js 实例，不共享 Scene

### 阶段二：航线弧绘制

**功能：**
- 根据航班数据（起降机场经纬度）绘制 3D 贝塞尔弧线
- 弧线高度随距离变化（远距离更高）
- 颜色按航班状态区分（飞行中/已降落/延误）
- 弧线材质带透明度渐变

### 阶段三：飞机模型加载与动画

**功能：**
- 加载 `/models/A320.glb`，缩放到合适大小
- 飞机沿航线弧线运动，机头朝向运动方向
- 多航班同时动画，支持播放/暂停/速度调节
- 飞机自带阴影

### 阶段四：交互与信息弹窗

**功能：**
- 点击飞机/弧线弹出 FlightInfoPopup
- 悬停高亮航线
- 相机聚焦航班（双击自动跟随）
- 与 SimMapView 的时间轴（SimulationTimeline）联动

### 阶段五：替换 SimMapView 中的 Map 组件

**步骤：**
1. 在 `SimMapView.vue` 中将 `<Map>` 替换为 `<FlightMap3D>`
2. 传递相同的航班数据和当前时间
3. 确保事件注入面板（EventInjectPanel）正常工作

## 技术要点

| 项目 | 方案 |
|------|------|
| 渲染引擎 | Three.js |
| 飞机模型 | A320.glb（已有） |
| 地形 | china_terrain.jpg 高度图 + ShaderMaterial 位移 |
| 航线弧 | CubicBezierCurve3 / QuadraticBezierCurve3 |
| 动画驱动 | requestAnimationFrame + deltaTime |
| 坐标系统 | 与 WeatherMap3D 一致：lon 73-135, lat 18-54 → 3D 平面 |
| 相机控制 | OrbitControls（可缩放、旋转、平移） |

## 接口设计

```typescript
// FlightMap3D Props
interface Props {
  flights: Flight[]          // 航班数据列表
  currentTime: string        // 当前仿真时间 "HH:MM"
  airportList: Airport[]     // 机场列表（含经纬度）
}

// Flight 数据结构
interface Flight {
  id: string
  flightNo: string           // 航班号 e.g. "CA1234"
  depAirport: string         // 起飞机场代码
  arrAirport: string         // 降落机场代码
  depLng: number, depLat: number
  arrLng: number, arrLat: number
  progress: number           // 0-1 飞行进度
  status: 'flying' | 'landed' | 'delayed'
  altitude: number           // 当前高度
  speed: number              // 当前速度
}
```
