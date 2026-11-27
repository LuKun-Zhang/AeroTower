<template>
  <div ref="container" class="weather3d-container">
    <!-- 右上：模式切换 -->
    <div class="weather-legend">
      <div class="mode-toggle">
        <button
          class="mode-btn" :class="{ active: mode === 'dynamic' }"
          @click="setMode('dynamic')"
        >动态演示</button>
        <button
          class="mode-btn" :class="{ active: mode === 'custom' }"
          @click="setMode('custom')"
        >自定义</button>
        <button
          class="mode-btn" :class="{ active: mode === 'auto' }"
          @click="setMode('auto')"
        >自动模拟</button>
        <button
          class="mode-btn" :class="{ active: mode === 'manual' }"
          @click="setMode('manual')"
        >手动输入</button>
        <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
      </div>
      <div class="legend-title" v-if="mode === 'dynamic'">气旋推演</div>
      <div class="legend-title" v-else-if="mode === 'custom'">自定义气旋</div>
      <div class="legend-title" v-else-if="mode === 'auto'">当前天气</div>
      <div class="legend-title" v-else>手动设定</div>
      <div class="legend-group" v-for="group in weatherGroups" :key="group.type">
        <div class="legend-type" :class="'type-' + group.type">
          <span class="legend-dot"></span>
          <span class="legend-label">{{ group.label }}</span>
          <span class="legend-count">{{ group.count }}</span>
        </div>
        <div class="legend-provinces">{{ group.provinces.join('、') }}</div>
      </div>
    </div>

    <!-- 自定义模式：气旋配置面板 -->
    <div class="cyclone-config-panel" v-if="mode === 'custom'">
      <div class="panel-title">气旋配置</div>
      <div class="cc-row">
        <label>气旋数量</label>
        <select v-model.number="cycloneCount" @change="onCycloneCountChange">
          <option v-for="n in 5" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <div class="cyclone-cards">
        <div class="cyclone-card" v-for="(cfg, idx) in cycloneConfigs" :key="idx">
          <div class="cc-header">气旋 #{{ idx + 1 }}</div>
          <div class="cc-field">
            <label>起点</label>
            <select v-model="cfg.start">
              <option v-for="pc in provinceList" :key="pc.name" :value="pc.name">{{ pc.name }}</option>
            </select>
          </div>
          <div class="cc-field">
            <label>终点</label>
            <select v-model="cfg.end">
              <option v-for="pc in provinceList" :key="pc.name" :value="pc.name">{{ pc.name }}</option>
            </select>
          </div>
          <div class="cc-field">
            <label>强度</label>
            <div class="cc-intensity">
              <input type="range" v-model.number="cfg.level" min="1" max="5" />
              <span class="cc-level-label">{{ levelLabel(cfg.level) }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="cc-actions">
        <button class="cc-btn cc-btn-save" @click="saveCycloneConfig">保存配置</button>
        <button class="cc-btn cc-btn-apply" @click="applyCycloneConfig">应用配置</button>
      </div>
    </div>

    <!-- 手动模式：省份天气选择面板 -->
    <div class="manual-panel" v-if="mode === 'manual'">
      <div class="manual-grid">
        <div
          class="province-row"
          v-for="pc in provinceList" :key="pc.name"
        >
          <span class="prov-name">{{ pc.name }}</span>
          <select
            class="prov-select"
            :value="manualWeather[pc.name]"
            @change="ev => { manualWeather[pc.name] = ev.target.value; onProvinceWeatherChange() }"
          >
            <option
              v-for="wt in weatherTypes" :key="wt.type"
              :value="wt.type"
            >{{ wt.label }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- 动态/自定义模式：天气情况仪表盘（气象卫星 + 省份天气 + 气旋状态） -->
    <div class="weather-dashboard" v-if="mode === 'dynamic' || mode === 'custom'">
      <!-- 左：气象卫星小图 -->
      <div class="dash-panel dash-chart">
        <div class="dash-title">气象卫星</div>
        <canvas ref="dashCanvas" class="dash-canvas"></canvas>
      </div>
      <!-- 中：省份天气 -->
      <div class="dash-panel dash-provinces">
        <div class="dash-title">省份天气</div>
        <div class="province-grid">
          <div
            class="prov-weather-item"
            v-for="pc in provinceList" :key="pc.name"
            :class="'w-' + (dynamicProvinceMap[pc.name] || 'sunny')"
          >
            <span class="pwi-dot"></span>
            <span class="pwi-name">{{ pc.name }}</span>
          </div>
        </div>
        <div class="prov-legend">
          <span class="pl-item"><i class="pl-dot w-sunny-bg"></i>晴</span>
          <span class="pl-item"><i class="pl-dot w-cloudy-bg"></i>多云</span>
          <span class="pl-item"><i class="pl-dot w-rain_light-bg"></i>小雨</span>
          <span class="pl-item"><i class="pl-dot w-rain_moderate-bg"></i>中雨</span>
          <span class="pl-item"><i class="pl-dot w-rain_heavy-bg"></i>大雨</span>
          <span class="pl-item"><i class="pl-dot w-thunderstorm-bg"></i>雷暴</span>
        </div>
      </div>
      <!-- 右：气旋状态 -->
      <div class="dash-panel dash-cyclones" v-if="cycloneStates.length > 0">
        <div class="dash-title">气旋状态</div>
        <div class="cs-cards">
          <div class="cs-card" v-for="cs in cycloneStates" :key="cs.id">
            <div class="cs-header">
              <span class="cs-name">气旋 #{{ cs.id }}</span>
              <span class="cs-stage" :class="'stage-' + cs.stage">{{ cs.stage }}</span>
            </div>
            <div class="cs-bar-row">
              <span class="cs-bar-label">强度</span>
              <div class="cs-bar-track">
                <div class="cs-bar-fill" :style="{ width: Math.round(cs.intensity * 100) + '%' }"
                  :class="cs.intensity > 0.7 ? 'bar-danger' : cs.intensity > 0.4 ? 'bar-warn' : 'bar-ok'"></div>
              </div>
              <span class="cs-bar-val">{{ Math.round(cs.intensity * 100) }}%</span>
            </div>
            <div class="cs-bar-row" v-if="cs.terrainWear > 0.01">
              <span class="cs-bar-label">地形磨损</span>
              <div class="cs-bar-track">
                <div class="cs-bar-fill cs-bar-wear" :style="{ width: Math.min(100, Math.round(cs.terrainWear * 100)) + '%' }"></div>
              </div>
              <span class="cs-bar-val wear-val">-{{ Math.round(cs.terrainWear * 100) }}%</span>
            </div>
            <div class="cs-info-row">
              <span>初始峰值 {{ Math.round(cs.peakIntensity * 100) }}%</span>
              <span v-if="cs.efPeak < cs.peakIntensity">→ 有效 {{ Math.round(cs.efPeak * 100) }}%</span>
            </div>
            <div class="cs-pos">
              位置: {{ cs.lng.toFixed(1) }}°E, {{ cs.lat.toFixed(1) }}°N
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 未来 24 小时天气预报 -->
    <div class="weather-forecast" v-if="(mode === 'dynamic' || mode === 'custom') && forecast">
      <div class="wf-title">天气预报（未来 24 小时）</div>
      <div class="wf-table" v-if="forecast.rows.length">
        <div class="wf-row wf-head">
          <span class="wf-cell wf-prov">省份</span>
          <span class="wf-cell wf-time" v-for="(t, i) in forecast.times" :key="i">{{ t }}</span>
        </div>
        <div class="wf-row" v-for="row in forecast.rows" :key="row.name">
          <span class="wf-cell wf-prov">{{ row.name }}</span>
          <span
            class="wf-cell wf-w"
            :class="'fw-' + c"
            v-for="(c, i) in row.cells"
            :key="i"
            :title="row.name + ' · ' + forecast.times[i] + ' ' + labelOf(c)"
          ></span>
        </div>
      </div>
      <div class="wf-empty" v-else>未来 24 小时全国天气平稳</div>
    </div>

    <ChartOverlay :visible.sync="chartsOpen" :charts="chartList" title="天气推演" />
  </div>
</template>

<script setup>
/**
 * WeatherMap3D — Three.js 3D 气象仿真场景
 * ├── 场景初始化 & 相机控制 (OrbitControls)
 * ├── 中国地图基底 + 地理边界裁剪
 * ├── 5 层云层面片 + GLSL 3D Simplex 噪声
 * ├── 蓝雨粒子系统
 * └── 天气数据 → 纹理驱动云/雨
 */
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import * as echarts from 'echarts'
import '@/utils/china'  // registers echarts map "china"
import ChartOverlay from './ChartOverlay.vue'
import { buildWeatherCharts } from '@/utils/charts/weather'

/* ==================== Props ==================== */
const props = defineProps({
  weatherData: { type: Object, default: () => ({}) },
  currentTime: { type: String, default: '' },
  // /api/weather/stream 自动回传的响应（外层页面每 2s 保存一份后传入；未传时中断联动图显示空态提示）
  streamSummary: { type: Object, default: null },
})

/* ==================== Reactive refs ==================== */
const container = ref(null)
const dashCanvas = ref(null)        // 仪表盘-气象卫星小图 canvas
const mode = ref('dynamic')          // 'dynamic' | 'custom' | 'auto' | 'manual'
const manualWeather = ref({})     // { '广东': 'thunderstorm', '湖南': 'cloudy', ... }

// ——— 自定义气旋配置 ———
const cycloneCount = ref(3)       // 气旋数量 1-5
const intensityLevels = [
  { level: 1, label: '多云', peak: 0.30, type: 'cloudy' },
  { level: 2, label: '小雨', peak: 0.45, type: 'rain_light' },
  { level: 3, label: '中雨', peak: 0.60, type: 'rain_moderate' },
  { level: 4, label: '大雨', peak: 0.80, type: 'rain_heavy' },
  { level: 5, label: '雷暴', peak: 1.00, type: 'thunderstorm' },
]
const cycloneConfigs = ref([
  { start: '新疆',  end: '黑龙江', level: 3 },
  { start: '西藏',  end: '江苏',   level: 4 },
  { start: '青海',  end: '山东',   level: 2 },
])
let customCyclonePaths = []       // [{ pathKey, points, peakIntensity, moveDir }]
let customModeActive = false      // 自定义模式是否已应用

// 所有省份（默认晴朗）
function initManualWeather() {
  const mw = {}
  provinceCenters.forEach(pc => { mw[pc.name] = 'sunny' })
  return mw
}

// 获取当前有效的天气映射
function getEffectiveWeather() {
  if (mode.value === 'manual') return { ...manualWeather.value }
  if (mode.value === 'dynamic') return {} // 动态模式不使用静态映射
  return { ...PROVINCE_WEATHER }
}

const weatherTypes = [
  { type: 'sunny', label: '晴朗' },
  { type: 'cloudy', label: '多云' },
  { type: 'rain_light', label: '小雨' },
  { type: 'rain_moderate', label: '中雨' },
  { type: 'rain_heavy', label: '大雨' },
  { type: 'thunderstorm', label: '雷暴' },
]

const provinceList = ref([])

// ===== 透明浮层图表 =====
const chartsOpen = ref(false)
const chartList = ref([])

/* ==================== State ==================== */
let renderer, scene, camera, controls
let animationId, lastTime = 0
let clockPaused = false   // 统一时钟接管后暂停内部 phase 推进，改由外部 setClockPhase 驱动
let clockSpeed = 1        // 统一时钟倍速（1x=5 业务分钟/秒）
let cloudMeshes = []
let rainSystems = []      // [{ points, type, count }]
let lightningBolts = []   // [{ line, region }]
let provinceSprites = []  // [{ sprite, name }] 省份 3D 悬浮标签
let weatherCanvas, weatherCtx, weatherTex
let chinaMaskTex
let chinaMapTex
let terrainTex         // 地形高度图纹理
let provinceCenters = []
let provincePaths = []     // [{ name, rings: [[x,y], ...] }] 省份多边形路径(2048×2048坐标系)
let provinceWorldPaths = [] // [{ name, polygon: [[worldX,worldZ], ...] }] 世界坐标多边形
let rainRegions = []      // [{ pool, centerWx, centerWz, type }]
let provinceMaskCanvas = null  // 省份 Mask Canvas 引用，用于采样生成点池
let sizeW = 1, sizeH = 1

/* ==================== 动态气旋系统 ==================== */

/* ==================== 统一时钟（三模块对齐）====================
 * 天气动画原先 60s 播完 7 天（约 168 业务分钟/秒），远超模拟引擎
 * （~5~20 业务分钟/秒）和旅客流（~1~6.67 业务分钟/秒）。
 * 现放慢天气动画到 5 业务分钟/秒（对齐模拟引擎默认倍速），并以
 * 气旋 phase 映射出的绝对业务时刻作为三页统一时间锚点 T0。
 */
const BUSINESS_MINUTES_PER_DAY = 24 * 60                       // 1440
const CYCLONE_DAYS = 7                                          // 一个气旋周期覆盖 7 个业务日
const CYCLONE_BUSINESS_MINUTES = CYCLONE_DAYS * BUSINESS_MINUTES_PER_DAY  // 10080 业务分钟
const UNIFIED_MINUTES_PER_SECOND = 1                            // 统一速率：每现实秒推进的业务分钟数（原 5，过快）
const CYCLONE_CYCLE = CYCLONE_BUSINESS_MINUTES / UNIFIED_MINUTES_PER_SECOND  // 2016 秒

// 业务时间锚点：气旋 phase 0 ↔ 2020-11-29 00:00（生成数据首日）
// 后端分钟自 2020-11-01 00:00 起算（见 SimulationEngine._time_to_min）
const BUSINESS_EPOCH_MINUTES = (29 - 1) * BUSINESS_MINUTES_PER_DAY  // 40320
const BUSINESS_EPOCH_STR = '2020-11-29 00:00'

// 三条气旋路径（lng, lat 关键点）
const CYCLONE_PATHS = {
  north: [ // 北线：新疆→内蒙古→东北
    { lng: 76, lat: 44 }, { lng: 88, lat: 43 }, { lng: 100, lat: 43 },
    { lng: 112, lat: 44 }, { lng: 124, lat: 46 }, { lng: 132, lat: 49 },
  ],
  middle: [ // 中线：青海→陕西→河南→山东
    { lng: 80, lat: 37 }, { lng: 92, lat: 36 }, { lng: 104, lat: 35 },
    { lng: 114, lat: 34 }, { lng: 122, lat: 33 }, { lng: 128, lat: 32 },
  ],
  south: [ // 南线：西藏→四川→湖北→安徽→江苏
    { lng: 78, lat: 31 }, { lng: 90, lat: 30 }, { lng: 102, lat: 30 },
    { lng: 112, lat: 31 }, { lng: 118, lat: 30 }, { lng: 124, lat: 29 },
  ],
}

// 气旋实例（efPeak = 受地形消耗后的有效峰值强度）
const cyclones = [
  { pathKey: 'north', phaseOffset: 0.0,  peakIntensity: 0.75, moveDir: 0.15,
    center: { lng: 76, lat: 44 }, phase: 0, intensity: 0, efPeak: 0.75, terrainWear: 0, stage: '' },
  { pathKey: 'south', phaseOffset: 0.30, peakIntensity: 1.0,  moveDir: 0.08,
    center: { lng: 78, lat: 31 }, phase: 0, intensity: 0, efPeak: 1.0, terrainWear: 0, stage: '' },
  { pathKey: 'middle', phaseOffset: 0.55, peakIntensity: 0.85, moveDir: 0.12,
    center: { lng: 80, lat: 37 }, phase: 0, intensity: 0, efPeak: 0.85, terrainWear: 0, stage: '' },
]

// 对流雨细胞（夏季午后局地雷暴，随机位置、有限寿命）
let convectiveCells = []

// 地形高度采样网格（128×128，从 terrainTex 降采样）
let terrainHeightGrid = null
let chinaMaskGrid = null      // 中国边界遮罩（128×128），1=境内 0=境外
let provinceTerrainGrid = null  // 省份地形网格（128×128），0=平原 1=green 2=group 3=snow
let mountainsPlaced = false
let terrainReady = false   // china_terrain.jpg 加载完成标记
let mountainModels = null   // { green, group, snow } → THREE.Group 克隆源
let mountainModelOffsets = {} // { green, group, snow } → 模型底部到 y=0 的 Y 偏移

// 天气计算网格（128×128，用于纹理和粒子生成）
const WEATHER_GRID = 128
let weatherGrid = new Uint8Array(WEATHER_GRID * WEATHER_GRID)
let weatherGridDirty = true
const weatherGridVersion = ref(0)

// 气象小图 Canvas
let weatherChartCanvas = null
let weatherChartCtx = null

// 动态模式省份天气表（响应式）
const dynamicProvinceMap = ref({})   // { '广东': 'thunderstorm', ... }
let provinceMapDirty = true

// 气旋实时状态面板数据
const cycloneStates = ref([])        // [{ id, intensity, stage, peakIntensity, efPeak, terrainWear, lng, lat }]

/* 地理范围 (lon 73-135, lat 18-54) → 3D 平面映射 */
const CHINA = { minLng: 73, maxLng: 135, minLat: 18, maxLat: 54 }
const MAP_W = 60                     // 3D 世界宽度（2.5x，省份级精度）
const MAP_H = MAP_W * (CHINA.maxLat - CHINA.minLat) / (CHINA.maxLng - CHINA.minLng)

/* ==================== 省份天气设定 ==================== */
/**
 * 天气类型 → 纹理参数 & 着色器效果：
 *   sunny:         wx.r=0.12  → wxFac≈0.32 (极薄),  storm=0
 *   cloudy:        wx.r=0.42  → wxFac≈0.83 (中等),  storm=0
 *   rain_light:    wx.r=0.65  → wxFac≈1.21 (厚云),  storm≈0.33
 *   rain_moderate: wx.r=0.80  → wxFac≈1.46 (厚云),  storm≈0.62
 *   rain_heavy:    wx.r=0.90  → wxFac≈1.63 (厚云),  storm≈0.81
 *   thunderstorm:  wx.r=0.97  → wxFac≈1.75 (极厚),  storm≈0.94
 *   default:       wx.r=0     → wxFac=0.12 (几乎无云)
 */
const PROVINCE_WEATHER = {
  // ——— 雷暴 ———
  '广东': 'thunderstorm',

  // ——— 大雨 ———
  '香港': 'rain_heavy',
  '澳门': 'rain_heavy',

  // ——— 中雨 ———
  '海南': 'rain_moderate',

  // ——— 多云省份：中等密度白云 ———
  '福建': 'cloudy',
  '台湾': 'cloudy',
  '江西': 'cloudy',
  '浙江': 'cloudy',
  '广西': 'cloudy',
  '云南': 'cloudy',
  '贵州': 'cloudy',
  '四川': 'cloudy',
  '重庆': 'cloudy',
  '湖南': 'cloudy',
  '湖北': 'cloudy',

  // ——— 晴朗省份：极薄白云 ———
  '北京': 'sunny',
  '天津': 'sunny',
  '河北': 'sunny',
  '山西': 'sunny',
  '内蒙古': 'sunny',
  '辽宁': 'sunny',
  '吉林': 'sunny',
  '黑龙江': 'sunny',
  '上海': 'sunny',
  '江苏': 'sunny',
  '安徽': 'sunny',
  '山东': 'sunny',
  '河南': 'sunny',
  '西藏': 'sunny',
  '陕西': 'sunny',
  '甘肃': 'sunny',
  '青海': 'sunny',
  '宁夏': 'sunny',
  '新疆': 'sunny',
}

const WEATHER_PARAMS = {
  sunny:          { wxR: 0.12, influence: 0.20, radius: 110 },
  cloudy:         { wxR: 0.42, influence: 0.50, radius: 140 },
  rain_light:     { wxR: 0.65, influence: 0.70, radius: 155 },
  rain_moderate:  { wxR: 0.80, influence: 0.80, radius: 165 },
  rain_heavy:     { wxR: 0.90, influence: 0.90, radius: 175 },
  thunderstorm:   { wxR: 0.97, influence: 0.95, radius: 185 },
}

/* ==================== 天气图例数据 ==================== */
const WEATHER_LABELS = {
  sunny: '晴朗', cloudy: '多云',
  rain_light: '小雨', rain_moderate: '中雨', rain_heavy: '大雨',
  thunderstorm: '雷暴',
}
const WEATHER_ORDER = ['thunderstorm', 'rain_heavy', 'rain_moderate', 'rain_light', 'cloudy', 'sunny']

const weatherGroups = computed(() => {
  const groups = {}
  WEATHER_ORDER.forEach(t => { groups[t] = [] })

  if (mode.value === 'dynamic' || mode.value === 'custom') {
    // 动态/自定义模式：从天气网格统计
    // eslint-disable-next-line no-unused-vars
    const _v = weatherGridVersion.value  // 响应式依赖
    rebuildWeatherGrid()
    const counts = {}
    for (let i = 0; i < weatherGrid.length; i++) {
      const type = WEATHER_TYPE_BY_INDEX[weatherGrid[i]]
      if (type !== 'sunny') {
        counts[type] = (counts[type] || 0) + 1
      }
    }
    return WEATHER_ORDER
      .filter(t => counts[t])
      .map(t => ({
        type: t,
        label: WEATHER_LABELS[t],
        count: Math.round(counts[t] / (WEATHER_GRID * WEATHER_GRID) * 100) + '%',
        provinces: [],
      }))
  }

  const effective = getEffectiveWeather()
  for (const [prov, type] of Object.entries(effective)) {
    if (groups[type]) groups[type].push(prov)
  }
  return WEATHER_ORDER
    .filter(t => groups[t] && groups[t].length > 0)
    .map(t => ({
      type: t,
      label: WEATHER_LABELS[t],
      count: groups[t].length,
      provinces: groups[t],
    }))
})

/* ==================== GLSL: 3D Simplex Noise ==================== */
const NOISE_GLSL = /* glsl */ `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1./6.,1./3.);
  const vec4 D=vec4(0.,.5,1.,2.);
  vec3 i=floor(v+dot(v,C.yyy));
  vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz);
  vec3 l=1.-g;
  vec3 i1=min(g.xyz,l.zxy);
  vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx;
  vec3 x2=x0-i2+C.yyy;
  vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
  float n_=.142857142857;
  vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z);
  vec4 y_=floor(j-7.*x_);
  vec4 x=x_*ns.x+ns.yyyy;
  vec4 y=y_*ns.x+ns.yyyy;
  vec4 h=1.-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy);
  vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.+1.;
  vec4 s1=floor(b1)*2.+1.;
  vec4 sh=-step(h,vec4(0.));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
  vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x);
  vec3 p1=vec3(a0.zw,h.y);
  vec3 p2=vec3(a1.xy,h.z);
  vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);
  m=m*m;
  return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
`

/* ==================== GLSL: 云层 Shader（立体位移） ==================== */
const CLOUD_VERT = /* glsl */ `
uniform float uTime;
uniform float uNoiseScale;
uniform float uNoiseAmp;
uniform vec3 uNoiseOffset;
varying vec2 vUv;
varying vec3 vWorldPos;
${NOISE_GLSL}
void main(){
  vec3 pos=position;
  float n=snoise(vec3(pos.x*uNoiseScale+uNoiseOffset.x,
                       pos.y*uNoiseScale+uNoiseOffset.y,
                       uTime*.05+uNoiseOffset.z));
  n+=snoise(vec3(pos.x*uNoiseScale*2.+5.,
                  pos.y*uNoiseScale*2.+3.,
                  uTime*.11+uNoiseOffset.z))*.5;
  n+=snoise(vec3(pos.x*uNoiseScale*4.-3.,
                  pos.y*uNoiseScale*4.+7.,
                  uTime*.18+uNoiseOffset.z))*.2;
  pos.z+=n*uNoiseAmp;
  vec4 worldPos=modelMatrix*vec4(pos,1.);
  vWorldPos=worldPos.xyz;
  vUv=uv;
  gl_Position=projectionMatrix*modelViewMatrix*vec4(pos,1.);
}`

const CLOUD_FRAG = /* glsl */ `
uniform float uTime;
uniform float uAlpha;
uniform vec3 uColorLight;
uniform vec3 uColorHeavy;
uniform vec3 uNoiseOffset;
uniform sampler2D uWeatherTex;
uniform sampler2D uChinaMask;
varying vec2 vUv;
varying vec3 vWorldPos;
${NOISE_GLSL}
void main(){
  vec3 c=vWorldPos*.4;
  float n=snoise(c+vec3(uTime*.03,uTime*.02,0.)+uNoiseOffset);
  n+=snoise(c*2.+vec3(uTime*.05,0.,uTime*.04)+uNoiseOffset)*.5;
  n+=snoise(c*4.+vec3(0.,uTime*.07,uTime*.06)+uNoiseOffset)*.25;
  n=n*.5+.5;
  n=clamp(n,0.,1.);
  vec4 wx=texture2D(uWeatherTex,vUv);
  float wxFac=mix(.12,1.8,wx.r);
  float cloud=smoothstep(.4,.6,n);
  cloud*=smoothstep(0.,.10,n);
  cloud*=wxFac;
  cloud=clamp(cloud,0.,1.);
  float edge=abs(n-.5)*2.;
  cloud*=mix(.75,1.,smoothstep(.3,.7,edge));
  float storm=mix(0.,cloud,smoothstep(.48,1.,wx.r));
  vec3 col=mix(uColorLight,uColorHeavy,storm);
  float mask=texture2D(uChinaMask,vUv).r;
  float alpha=cloud*uAlpha*.85*mask;
  gl_FragColor=vec4(col,alpha);
}`

/* ==================== GLSL: 地形地面 Shader ==================== */
const TERRAIN_VERT = /* glsl */ `
uniform sampler2D uHeightTex;
uniform float uElevationScale;
varying vec2 vUv;
varying float vElevation;

void main(){
  float h=dot(texture2D(uHeightTex,uv).rgb,vec3(0.299,0.587,0.114));
  h=max(h,0.);  // 海平面为基准，只向上增高
  vec3 pos=position;
  pos.z+=h*uElevationScale;
  vElevation=h;
  vUv=uv;
  gl_Position=projectionMatrix*modelViewMatrix*vec4(pos,1.);
}`

const TERRAIN_FRAG = /* glsl */ `
uniform sampler2D uChinaMap;
uniform sampler2D uChinaMask;
varying vec2 vUv;
varying float vElevation;

void main(){
  // 统一绿色平原基底（山脉由 3D 模型表达）
  vec3 elevCol = vec3(0.20, 0.55, 0.20);

  // 叠加干净地图：省份边界/名字作为暗色线条透出
  vec4 mapC=texture2D(uChinaMap,vUv);
  float mapDark=1.-mapC.r;             // 暗色区域=边界/文字
  elevCol=mix(elevCol,elevCol*.7,mapDark*.45); // 边界处压暗

  float mask=texture2D(uChinaMask,vUv).r;
  if(mask<0.4)discard;
  gl_FragColor=vec4(elevCol,1.);
}`

/* ==================== 云层创建 (多层堆叠立体) ==================== */
function createClouds() {
  const strata = [
    { base: 5.0, alpha: 0.32, subH: 0.25, count: 3, seg: 140, scale: 0.36, amp: 0.9 },
    { base: 6.5, alpha: 0.38, subH: 0.30, count: 4, seg: 160, scale: 0.32, amp: 1.1 },
    { base: 8.0, alpha: 0.44, subH: 0.35, count: 4, seg: 180, scale: 0.28, amp: 1.4 },
    { base: 9.5, alpha: 0.38, subH: 0.30, count: 4, seg: 160, scale: 0.32, amp: 1.1 },
    { base: 11.0, alpha: 0.25, subH: 0.20, count: 3, seg: 140, scale: 0.40, amp: 0.75 },
  ]

  strata.forEach((s, si) => {
    const group = new THREE.Group()
    const step = s.subH / (s.count - 1 || 1)
    for (let j = 0; j < s.count; j++) {
      const hOffset = -s.subH / 2 + j * step
      const geo = new THREE.PlaneGeometry(
        MAP_W * 1.08, MAP_H * 1.08, s.seg, s.seg,
      )
      const noiseOff = new THREE.Vector3(
        si * 2.3 + j * 0.7, si * 3.1 + j * 1.1, si * 0.5 + j * 0.3,
      )
      const mat = new THREE.ShaderMaterial({
        vertexShader: CLOUD_VERT,
        fragmentShader: CLOUD_FRAG,
        uniforms: {
          uTime:        { value: 0 },
          uAlpha:       { value: s.alpha / s.count },
          uNoiseScale:  { value: s.scale },
          uNoiseAmp:    { value: s.amp },
          uNoiseOffset: { value: noiseOff },
          uColorLight:  { value: new THREE.Color('#8a8aa0') },
          uColorHeavy:  { value: new THREE.Color('#303040') },
          uWeatherTex:  { value: weatherTex },
          uChinaMask:   { value: chinaMaskTex },
        },
        transparent:  true,
        depthWrite:   false,
        blending:     THREE.NormalBlending,
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.rotation.x = -Math.PI / 2
      mesh.position.y = s.base + hOffset
      mesh.renderOrder = si * 10 + j
      group.add(mesh)
    }
    scene.add(group)
    cloudMeshes.push(group)
  })
}

/* ==================== 降雨 & 雷电系统 ==================== */

/** 降雨强度配置 — 统一粒子大小，仅通过数量/速度/颜色区分强度 */
const RAIN_CONFIGS = {
  rain_light:    { count: 1500, color: 0x88bbee, size: 0.06, opacity: 0.45, speedMul: 0.7 },
  rain_moderate: { count: 3000, color: 0x5599cc, size: 0.06, opacity: 0.55, speedMul: 1.0 },
  rain_heavy:    { count: 5000, color: 0x3366aa, size: 0.06, opacity: 0.68, speedMul: 1.3 },
  thunderstorm:  { count: 7000, color: 0x223366, size: 0.06, opacity: 0.78, speedMul: 1.6 },
}

/** 经纬度 → 3D 世界坐标 */
function lngLatToWorld(lng, lat) {
  const wx = ((lng - CHINA.minLng) / (CHINA.maxLng - CHINA.minLng) - 0.5) * MAP_W
  const wz = (0.5 - (lat - CHINA.minLat) / (CHINA.maxLat - CHINA.minLat)) * MAP_H
  return { x: wx, z: wz }
}

/** 判断点是否在多边形内（射线法） */
function pointInPolygon(px, py, poly) {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1]
    const xj = poly[j][0], yj = poly[j][1]
    if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

/** 从天气映射初始化/重建雨区 */
function rebuildRainRegions(weatherMap) {
  rainRegions = []

  // 构建省份名 → 路径索引映射
  const pathMap = {}
  provincePaths.forEach(p => { pathMap[p.name] = p })

  // 构建省份名 → 省份中心世界坐标
  const centerMap = {}
  provinceCenters.forEach(pc => {
    const w = lngLatToWorld(pc.lng, pc.lat)
    centerMap[pc.name] = { wx: w.x, wz: w.z }
  })

  // ⭐ 从 Mask Canvas 读取 ImageData，用于像素级点池生成
  let maskData = null
  if (provinceMaskCanvas) {
    const ctx = provinceMaskCanvas.getContext('2d')
    try {
      maskData = ctx.getImageData(0, 0, provinceMaskCanvas.width, provinceMaskCanvas.height)
    } catch (_) {
      console.warn('[rebuildRainRegions] 无法读取 mask canvas ImageData')
    }
  }

  const M = provinceMaskCanvas ? provinceMaskCanvas.width : 2048
  // canvas 坐标 → 世界坐标
  const canvasToWorldX = (cx) => (cx / M - 0.5) * MAP_W
  const canvasToWorldZ = (cy) => (cy / M - 0.5) * MAP_H

  // 统计
  let regionCount = 0, poolOkCount = 0, maskHitCount = 0

  for (const pc of provinceCenters) {
    const weatherType = weatherMap[pc.name] || 'sunny'
    if (!RAIN_CONFIGS[weatherType]) continue

    const pathData = pathMap[pc.name]
    const center = centerMap[pc.name]
    if (!center) { console.warn('[rebuildRainRegions] 无 center:', pc.name); continue }

    // 计算覆盖半径（用于雷电定位等）—— 遍历所有 ring 取最远距离
    let radius = 3.0
    if (pathData && pathData.rings && pathData.rings.length > 0) {
      let maxDist = 0
      pathData.rings.forEach(ring => {
        if (!ring || ring.length < 3) return
        ring.forEach(([cx, cy]) => {
          const dx = canvasToWorldX(cx) - center.wx
          const dz = canvasToWorldZ(cy) - center.wz
          const d = Math.sqrt(dx * dx + dz * dz)
          if (d > maxDist) maxDist = d
        })
      })
      radius = Math.max(maxDist * 0.72, 2.0)
    }

    // ⭐ 使用 Mask Canvas 像素采样生成点池
    let pool = []
    if (maskData && pathData && pathData.rings && pathData.rings.length > 0) {
      // 用所有 ring 的并集包围盒（处理 MultiPolygon：部分省份第一个 ring 可能是小岛）
      let minCX = Infinity, minCY = Infinity, maxCX = -Infinity, maxCY = -Infinity
      pathData.rings.forEach(ring => {
        if (!ring || ring.length < 3) return
        ring.forEach(([cx, cy]) => {
          if (cx < minCX) minCX = cx
          if (cx > maxCX) maxCX = cx
          if (cy < minCY) minCY = cy
          if (cy > maxCY) maxCY = cy
        })
      })
      // 扩展包围盒，确保覆盖所有内部
      minCX = Math.floor(Math.max(0, minCX - 2))
      minCY = Math.floor(Math.max(0, minCY - 2))
      maxCX = Math.ceil(Math.min(M - 1, maxCX + 2))
      maxCY = Math.ceil(Math.min(M - 1, maxCY + 2))

      const bw = maxCX - minCX, bh = maxCY - minCY
      const area = bw * bh

      // 采样步长：面积大的省份步长更大（减少采样点但保持足够密度）
      const step = Math.max(1, Math.floor(Math.sqrt(area) / 35))
      const data = maskData.data, w = maskData.width

      for (let py = minCY; py <= maxCY; py += step) {
        for (let px = minCX; px <= maxCX; px += step) {
          const idx = (py * w + px) * 4
          // mask 中白色 (r=255) 表示在省份内
          if (data[idx] > 200) {
            pool.push([canvasToWorldX(px), canvasToWorldZ(py)])
          }
        }
      }

      // 限制池大小（避免过大）
      if (pool.length > 600) {
        // 随机下采样到 600
        const target = 600
        for (let i = pool.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1))
          ;[pool[i], pool[j]] = [pool[j], pool[i]]
        }
        pool = pool.slice(0, target)
      }
      if (pool.length > 0) maskHitCount++
    }

    regionCount++
    if (pool.length > 0) poolOkCount++

    rainRegions.push({
      type: weatherType,
      centerWx: center.wx,
      centerWz: center.wz,
      radius,
      pool,
    })
  }

  console.log(`[rebuildRainRegions] 生成 ${regionCount} 个雨区, pool 有效: ${poolOkCount}/${regionCount}, mask 命中: ${maskHitCount}`)

  // 按 type 统计
  const typeStats = {}
  rainRegions.forEach(r => {
    if (!typeStats[r.type]) typeStats[r.type] = { count: 0, poolOk: 0 }
    typeStats[r.type].count++
    if (r.pool && r.pool.length > 0) typeStats[r.type].poolOk++
  })
  console.log('[rebuildRainRegions] 按类型:', JSON.stringify(typeStats))

  // 更新已有粒子系统的区域引用，并重置粒子位置
  for (const sys of rainSystems) {
    const regions = rainRegions.filter(r => r.type === sys.type)
    const geo = sys.points.geometry
    const geoData = geo.userData
    geoData.regions = regions
    // 重置所有粒子位置使用新点池
    const posArr = geo.attributes.position.array
    const velArr = geoData.vel
    const cfg = RAIN_CONFIGS[sys.type]
    for (let i = 0; i < sys.count; i++) {
      const p = spawnInRegion(regions) || { x: 0, z: 0 }
      posArr[i * 3]     = p.x
      posArr[i * 3 + 1] = Math.random() * 5 + 0.2
      posArr[i * 3 + 2] = p.z
      velArr[i] = (0.02 + Math.random() * 0.06) * (cfg ? cfg.speedMul : 1)
    }
    geo.attributes.position.needsUpdate = true
    sys.points.visible = regions.length > 0
    console.log(`[rebuildRainRegions] 更新系统 ${sys.type}: regions=${regions.length}, visible=${sys.points.visible}`)
  }
  // 按需补建缺失的雨系统（初始时对应类型无 region 可能被跳过）
  for (const type of Object.keys(RAIN_CONFIGS)) {
    const regions = rainRegions.filter(r => r.type === type)
    if (regions.length === 0) continue
    const existing = rainSystems.find(s => s.type === type)
    if (existing) continue
    console.log(`[rebuildRainRegions] 补建系统: ${type}, regions=${regions.length}`)
    const sys = createRainSystem(type)
    if (sys) rainSystems.push(sys)
  }
}

/** 从天气映射重建雷电 */
function rebuildLightning(weatherMap) {
  // 清除旧雷电
  lightningBolts.forEach(b => {
    b.children.forEach(c => { c.geometry.dispose(); c.material.dispose() })
    scene.remove(b)
  })
  lightningBolts = []

  const stormRegions = rainRegions.filter(r => r.type === 'thunderstorm')
  if (stormRegions.length === 0) return

  stormRegions.forEach(reg => {
    const boltCount = 3 + Math.floor(Math.random() * 3)
    for (let i = 0; i < boltCount; i++) {
      const p = spawnInRegion([reg]) || { x: reg.centerWx, z: reg.centerWz }
      const bolt = createLightningBolt(p.x, p.z)
      bolt.userData.region = reg
      lightningBolts.push(bolt)
    }
  })
}

/** 初始化雨区（动态模式跳过，由 updateDynamicRain 接管） */
function initRainRegions() {
  if (mode.value === 'dynamic' || mode.value === 'custom') {
    // 动态模式不需要静态雨区，但需要创建空的 rainRegions 占位
    rainRegions = Object.keys(RAIN_CONFIGS).map(type => ({ type, pool: [], centerWx: 0, centerWz: 0, radius: 10 }))
    return
  }
  rebuildRainRegions(PROVINCE_WEATHER)
}

/** 在多边形雨区内精确生成位置（从预计算池取 + 池小时抖散） */
function spawnInRegion(regions) {
  if (regions.length === 0) return null
  const reg = regions[Math.floor(Math.random() * regions.length)]
  if (reg.pool && reg.pool.length >= 30) {
    // 池充足：随机选一点
    const pt = reg.pool[Math.floor(Math.random() * reg.pool.length)]
    return { x: pt[0], z: pt[1] }
  }
  if (reg.pool && reg.pool.length > 0) {
    // 池偏小：在池中点上加微小随机偏移抖散
    const pt = reg.pool[Math.floor(Math.random() * reg.pool.length)]
    const jitter = 0.3
    return {
      x: pt[0] + (Math.random() - 0.5) * jitter,
      z: pt[1] + (Math.random() - 0.5) * jitter,
    }
  }
  // 空池：用中心 + 大方差抖散
  const jitter = 0.5
  return {
    x: reg.centerWx + (Math.random() - 0.5) * jitter * 4,
    z: reg.centerWz + (Math.random() - 0.5) * jitter * 4,
  }
}

/** 创建单级降雨粒子系统 */
function createRainSystem(type) {
  const cfg = RAIN_CONFIGS[type]
  if (!cfg) return null

  // 筛选该类型的雨区
  const regions = rainRegions.filter(r => r.type === type)
  if (regions.length === 0) { console.warn(`[createRainSystem] ${type}: 无雨区`); return null }

  console.log(`[createRainSystem] ${type}: 区域数=${regions.length}, 粒子数=${cfg.count}, pool大小=${regions.map(r => r.pool?.length || 0).join(',')}`)

  const pos = new Float32Array(cfg.count * 3)
  const vel = new Float32Array(cfg.count)
  for (let i = 0; i < cfg.count; i++) {
    const p = spawnInRegion(regions) || { x: 0, z: 0 }
    pos[i * 3]     = p.x
    pos[i * 3 + 1] = Math.random() * 5 + 0.2
    pos[i * 3 + 2] = p.z
    vel[i] = (0.02 + Math.random() * 0.06) * cfg.speedMul
  }

  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  geo.userData = { pos, vel, regions, cfg }

  const mat = new THREE.PointsMaterial({
    color: cfg.color, size: cfg.size, transparent: true, opacity: cfg.opacity,
    depthWrite: false, blending: THREE.NormalBlending,
  })
  const points = new THREE.Points(geo, mat)
  points.visible = false
  scene.add(points)

  return { points, type, count: cfg.count }
}

function createRain() {
  // 为每种降雨类型创建独立粒子系统
  for (const type of Object.keys(RAIN_CONFIGS)) {
    const sys = createRainSystem(type)
    if (sys) rainSystems.push(sys)
  }
}

function updateRain(dt) {
  for (const sys of rainSystems) {
    if (!sys.points.visible) continue
    const { pos, vel, regions, cfg } = sys.points.geometry.userData
    // 检测是否为动态模式（regions 仅含 type 标记，无 pool/centerWx）
    const isDynamic = regions && regions.length > 0 && !('pool' in regions[0]) && !('centerWx' in regions[0])
    for (let i = 0; i < sys.count; i++) {
      pos[i * 3 + 1] -= vel[i] * dt * 30
      if (pos[i * 3 + 1] < 0.03) {
        let p
        if (isDynamic) {
          // 动态模式：按天气类型从网格随机生成
          const targetTypes = sys.type === 'rain_heavy'
            ? ['rain_heavy', 'thunderstorm']
            : [sys.type]
          p = spawnFromWeatherGrid(targetTypes) || { x: 0, z: 0 }
        } else {
          p = spawnInRegion(regions) || { x: 0, z: 0 }
        }
        pos[i * 3 + 1] = 5 + Math.random() * 3
        pos[i * 3]     = p.x
        pos[i * 3 + 2] = p.z
        vel[i] = (0.03 + Math.random() * 0.08) * (cfg.speedMul || 1)
      }
    }
    sys.points.geometry.attributes.position.needsUpdate = true
  }
}

/* ==================== 雷电系统 ==================== */
let ambientLight = null  // 场景环境光引用，用于闪电闪烁

/** 生成锯齿闪电路径的顶点数组 */
function boltVertices(cx, cz, hTop, hBot, segCount) {
  const verts = []
  for (let i = 0; i <= segCount; i++) {
    const t = i / segCount
    const y = hTop + (hBot - hTop) * t
    const spread = (1 - Math.abs(t - 0.5) * 2) * 1.5
    const offX = (Math.random() - 0.5) * spread
    const offZ = (Math.random() - 0.5) * spread * 0.4
    verts.push(cx + offX, y, cz + offZ)
  }
  return verts
}

function createLightningBolt(cx, cz) {
  const hTop = 12 + Math.random() * 3
  const hBot = 0.05 + Math.random() * 0.5
  const segCount = 12 + Math.floor(Math.random() * 10)

  // 主闪电：大尺寸亮白点
  const verts = boltVertices(cx, cz, hTop, hBot, segCount)
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3))
  const mat = new THREE.PointsMaterial({
    color: 0xffffcc, size: 0.18, transparent: true, opacity: 0.95,
    depthWrite: false, blending: THREE.AdditiveBlending,
  })
  const points = new THREE.Points(geo, mat)
  points.renderOrder = 999
  points.visible = false

  // 辉光线：更大的蓝色光晕
  const glowVerts = boltVertices(cx, cz, hTop, hBot, segCount)
  const glowGeo = new THREE.BufferGeometry()
  glowGeo.setAttribute('position', new THREE.Float32BufferAttribute(glowVerts, 3))
  const glowMat = new THREE.PointsMaterial({
    color: 0x6699ff, size: 0.40, transparent: true, opacity: 0.40,
    depthWrite: false, blending: THREE.AdditiveBlending,
  })
  const glowPoints = new THREE.Points(glowGeo, glowMat)
  glowPoints.renderOrder = 998
  glowPoints.visible = false

  const group = new THREE.Group()
  group.add(points)
  group.add(glowPoints)
  group.userData = {
    get visible() { return points.visible },
    set visible(v) { points.visible = v; glowPoints.visible = v },
    nextFlash: Math.random() * 0.5,   // 前 0.5s 内首次闪烁
    flashDuration: 0.08 + Math.random() * 0.12,
    flashTimer: 0,
    cooldown: 1.5 + Math.random() * 4, // 1.5-5.5s 间隔
    core: points,
    glow: glowPoints,
  }
  scene.add(group)
  return group
}

function createLightning() {
  if (mode.value === 'dynamic' || mode.value === 'custom') return  // 动态模式由 updateDynamicRain 控制可见性
  rebuildLightning(PROVINCE_WEATHER)
}

/* ==================== 省份 3D 悬浮标签 (Sprite) ==================== */
function createProvinceLabels() {
  const labelFilter = new Set(['南海诸岛', '香港', '澳门']) // 太小不显示
  provinceCenters.forEach(pc => {
    if (labelFilter.has(pc.name)) return

    // 创建标签画布
    const labelCanvas = document.createElement('canvas')
    labelCanvas.width = 256
    labelCanvas.height = 80
    const lctx = labelCanvas.getContext('2d')
    lctx.fillStyle = 'rgba(255,255,255,0.88)'
    lctx.font = 'bold 36px "Microsoft YaHei","PingFang SC",sans-serif'
    lctx.textAlign = 'center'
    lctx.textBaseline = 'middle'
    lctx.shadowColor = 'rgba(0,0,0,0.6)'
    lctx.shadowBlur = 6
    lctx.fillText(pc.name, 128, 40)

    const tex = new THREE.CanvasTexture(labelCanvas)
    tex.minFilter = THREE.LinearFilter
    tex.magFilter = THREE.LinearFilter

    const spriteMat = new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    })
    const sprite = new THREE.Sprite(spriteMat)

    // 画布坐标 → 3D 世界坐标
    const wx = (pc.cx / 2048 - 0.5) * MAP_W
    const wz = (pc.cy / 2048 - 0.5) * MAP_H
    sprite.position.set(wx, 3.8, wz)
    sprite.scale.set(5.5, 1.7, 1)

    scene.add(sprite)
    provinceSprites.push({ sprite, name: pc.name })
  })
  updateProvinceLabelScale()
}

/**
 * 省份标签按相机距离换算尺寸，保持恒定屏幕字号（约 12–14px）。
 * 之前用固定世界尺寸 5.5，相机拉近时标签会占满半个屏幕并相互重叠。
 */
function updateProvinceLabelScale() {
  if (!camera || !renderer || !provinceSprites.length) return
  const vh = renderer.domElement.clientHeight || 1
  const halfFov = THREE.MathUtils.degToRad(camera.fov * 0.5)
  for (const item of provinceSprites) {
    const dist = camera.position.distanceTo(item.sprite.position)
    const worldPerPx = (2 * Math.tan(halfFov) * dist) / vh
    const h = 34 * worldPerPx      // 目标屏幕高度约 34px（字形约 15px）
    item.sprite.scale.set(h * 3.2, h, 1)
  }
}

function updateLightning(dt) {
  let anyFlashing = false
  for (const bolt of lightningBolts) {
    const ud = bolt.userData
    ud.flashTimer += dt
    if (bolt.userData.visible) {
      if (ud.flashTimer >= ud.flashDuration) {
        bolt.userData.visible = false
        ud.flashTimer = 0
        ud.nextFlash = ud.cooldown * (0.6 + Math.random() * 0.8)
      } else {
        anyFlashing = true
      }
    } else {
      if (ud.flashTimer >= ud.nextFlash) {
        bolt.userData.visible = true
        ud.flashTimer = 0
        ud.flashDuration = 0.08 + Math.random() * 0.15
        // 更新闪电位置和形状
        const reg = ud.region
        let bx, bz
        if (reg) {
          if (reg._dynamic) {
            // 动态模式：从天气网格随机选取雷暴位置
            const pos = spawnFromWeatherGrid(['thunderstorm'])
            if (pos) { bx = pos.x; bz = pos.z }
          } else if (reg.centerWx !== undefined) {
            bx = reg.centerWx + (Math.random() - 0.5) * reg.radius * 0.6
            bz = reg.centerWz + (Math.random() - 0.5) * reg.radius * 0.6
          }
        }
        if (bx !== undefined) {
          const hTop = 12 + Math.random() * 3
          const hBot = 0.05 + Math.random() * 0.5
          const segCount = 10 + Math.floor(Math.random() * 8)
          const coreVerts = boltVertices(bx, bz, hTop, hBot, segCount)
          const glowVerts = boltVertices(bx, bz, hTop, hBot, segCount)
          const coreArr = ud.core.geometry.attributes.position.array
          const glowArr = ud.glow.geometry.attributes.position.array
          for (let i = 0; i < coreVerts.length; i++) coreArr[i] = coreVerts[i]
          for (let i = 0; i < glowVerts.length; i++) glowArr[i] = glowVerts[i]
          ud.core.geometry.attributes.position.needsUpdate = true
          ud.glow.geometry.attributes.position.needsUpdate = true
        }
        anyFlashing = true
      }
    }
  }

  // 闪电时提高环境光亮度
  if (ambientLight) {
    const target = anyFlashing ? 2.5 : 0.9
    ambientLight.intensity += (target - ambientLight.intensity) * 0.15
  }
}

/** 存储 ambientLight 引用 */
function setAmbientLight(light) {
  ambientLight = light
}

/* ==================== 天气 → 纹理 ==================== */
function createWeatherCanvas() {
  weatherCanvas = document.createElement('canvas')
  weatherCanvas.width  = 2048   // 与 createChinaTextures 的 M 一致
  weatherCanvas.height = 2048
  weatherCtx = weatherCanvas.getContext('2d')
  weatherTex = new THREE.CanvasTexture(weatherCanvas)
  weatherTex.minFilter = THREE.LinearFilter
  weatherTex.magFilter = THREE.LinearFilter
}

function updateWeatherTex() {
  const ctx = weatherCtx
  if (!ctx) return

  // 动态/自定义模式：根据气旋位置实时绘制天气场
  if (mode.value === 'dynamic' || mode.value === 'custom') {
    drawDynamicWeather()
    weatherTex.needsUpdate = true
    updateDynamicRain()
    return
  }

  const w = weatherCanvas.width, h = weatherCanvas.height
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, w, h)

  // 获取当前有效天气（自动模式用 PROVINCE_WEATHER，手动模式用 manualWeather）
  const effectiveWeather = getEffectiveWeather()

  // 构建省份名 → 路径索引映射
  const pathMap = {}
  provincePaths.forEach(p => { pathMap[p.name] = p })

  // 按天气优先级分组：低优先级先画，高优先级叠在上层
  const drawOrder = ['sunny', 'cloudy', 'rain_light', 'rain_moderate', 'rain_heavy', 'thunderstorm']

  // 跟踪哪些降雨类型有数据
  const activeRainTypes = new Set()

  drawOrder.forEach(weatherType => {
    const params = WEATHER_PARAMS[weatherType]
    if (!params) return

    const rVal = Math.round(params.wxR * 255)
    const colorHex = '#' + rVal.toString(16).padStart(2, '0').repeat(3)

    let hasProvince = false

    // 找出该天气类型的所有省份
    provinceCenters.forEach(pc => {
      const pt = effectiveWeather[pc.name] || 'sunny'
      if (pt !== weatherType) return

      hasProvince = true
      const pathData = pathMap[pc.name]
      if (!pathData) return

      // 使用省份多边形精确裁剪
      ctx.save()
      pathData.rings.forEach(ring => {
        ctx.beginPath()
        ring.forEach((pt, i) => {
          i === 0 ? ctx.moveTo(pt[0], pt[1]) : ctx.lineTo(pt[0], pt[1])
        })
        ctx.closePath()
      })
      ctx.clip()

      // 计算省份包围盒 → 自适应渐变半径（保渐变在省份内部衰退）
      // ⚠️ 使用所有 ring 的并集包围盒（MultiPolygon 省份第一个 ring 可能是小岛）
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      pathData.rings.forEach(ring => {
        if (!ring || ring.length < 3) return
        ring.forEach(pt => {
          if (pt[0] < minX) minX = pt[0]
          if (pt[1] < minY) minY = pt[1]
          if (pt[0] > maxX) maxX = pt[0]
          if (pt[1] > maxY) maxY = pt[1]
        })
      })
      const provW = maxX - minX, provH = maxY - minY
      const innerR = Math.min(provW, provH) * 0.35  // 纯色核心半径
      const outerR = Math.min(provW, provH) * 0.55  // 衰退到透明的外边界

      const g = ctx.createRadialGradient(pc.cx, pc.cy, innerR, pc.cx, pc.cy, outerR)
      g.addColorStop(0, colorHex)
      g.addColorStop(0.65, colorHex)
      g.addColorStop(1, 'transparent')
      ctx.fillStyle = g
      ctx.fillRect(minX - 5, minY - 5, provW + 10, provH + 10)

      ctx.restore()
    })

    // 只有真正有省份使用该天气类型时，才标记降雨/雷电为活跃
    if (hasProvince && RAIN_CONFIGS[weatherType]) activeRainTypes.add(weatherType)
  })

  weatherTex.needsUpdate = true

  // 控制各降雨系统 & 雷电可见性
  for (const sys of rainSystems) {
    sys.points.visible = activeRainTypes.has(sys.type)
  }
  const showLightning = activeRainTypes.has('thunderstorm')
  for (const bolt of lightningBolts) {
    if (!showLightning) bolt.userData.visible = false
  }
}

/* ==================== 中国 Mask + 地图 → 纹理 ==================== */

/**
 * 内置 utils/china.js 使用 UTF8 压缩格式（UTF8Encoding + encodeOffsets），
 * echarts.getMap() 返回的 geoJSON 仍是压缩态：coordinates 是字符串。
 * 直接按数组遍历会抛 "c.forEach is not a function"，使地形降级成纯色。
 * 这里按 ECharts 的解码算法就地还原成经纬度数组。
 */
function decodeChinaGeoJSON(json) {
  if (!json || !json.UTF8Encoding) return json
  const scale = json.UTF8Scale || 1024
  const decodeRing = (ring, offsets) => {
    const result = []
    let prevX = offsets[0]
    let prevY = offsets[1]
    for (let i = 0; i < ring.length; i += 2) {
      let x = ring.charCodeAt(i) - 64
      let y = ring.charCodeAt(i + 1) - 64
      // ZigZag 还原 + 差分还原
      x = (x >> 1) ^ (-(x & 1))
      y = (y >> 1) ^ (-(y & 1))
      x += prevX
      y += prevY
      prevX = x
      prevY = y
      result.push([x / scale, y / scale])
    }
    return result
  }

  for (const feature of json.features || []) {
    const geometry = feature && feature.geometry
    if (!geometry || !geometry.coordinates || !geometry.encodeOffsets) continue
    const coords = geometry.coordinates
    const offsets = geometry.encodeOffsets
    if (geometry.type === 'Polygon') {
      for (let i = 0; i < coords.length; i++) {
        if (typeof coords[i] === 'string') coords[i] = decodeRing(coords[i], offsets[i])
      }
    } else if (geometry.type === 'MultiPolygon') {
      for (let i = 0; i < coords.length; i++) {
        const polygon = coords[i]
        if (!Array.isArray(polygon)) continue
        for (let j = 0; j < polygon.length; j++) {
          if (typeof polygon[j] === 'string') {
            polygon[j] = decodeRing(polygon[j], offsets[i][j])
          }
        }
      }
    }
  }
  json.UTF8Encoding = false
  return json
}

function createChinaTextures() {
  const M = 2048  // 纹理分辨率
  const toX = (lng) => (lng - CHINA.minLng) / (CHINA.maxLng - CHINA.minLng) * M
  const toY = (lat) => (1 - (lat - CHINA.minLat) / (CHINA.maxLat - CHINA.minLat)) * M

  // ——— Mask canvas (白底 + 各省填白) ———
  const maskCanvas = document.createElement('canvas')
  maskCanvas.width = M; maskCanvas.height = M
  const mCtx = maskCanvas.getContext('2d')
  mCtx.fillStyle = '#000'; mCtx.fillRect(0, 0, M, M)

  // ——— Map canvas (浅色底图 + 省份分色 + 深色边界) ———
  const mapCanvas = document.createElement('canvas')
  mapCanvas.width = M; mapCanvas.height = M
  const mapCtx = mapCanvas.getContext('2d')
  // 海洋底色：浅色
  mapCtx.fillStyle = '#e8ecf2'; mapCtx.fillRect(0, 0, M, M)

  // 省份配色表（浅色系，微差区分）
  const provinceColors = [
    '#f2f5f8','#eef2f6','#f0f3f7','#ecf0f5','#f3f6f9',
    '#edf1f6','#f1f4f8','#eef1f5','#f2f5f9','#ecf0f4',
    '#f0f3f6','#eef2f5','#f1f4f7','#edf1f4','#f2f4f8',
    '#ecf0f3','#f0f2f6','#eef1f4','#f1f3f7','#edf0f5',
  ]

  provinceCenters = []
  provincePaths = []
  provinceWorldPaths = []
  let colorIdx = 0

  try {
    const geo = echarts.getMap('china')
    if (geo && geo.geoJSON) {
      decodeChinaGeoJSON(geo.geoJSON).features.forEach(feature => {
        const name = feature.properties?.name || ''
        const coords = feature.geometry?.coordinates
        if (!coords || !name) return

        const color = provinceColors[colorIdx % provinceColors.length]
        colorIdx++

        // 收集该省份所有外部环
        const rings = []
        const flatten = (c) => {
          if (!c || !c.length) return
          if (typeof c[0][0] === 'number') {
            rings.push(c)
          } else {
            c.forEach(flatten)
          }
        }
        flatten(coords)

        // 计算省份中心：优先使用 ECharts 预计算的视觉中心 cp=[lng,lat]
        let cx, cy
        const cp = feature.properties?.cp
        if (cp && Array.isArray(cp) && cp.length === 2) {
          cx = toX(cp[0])
          cy = toY(cp[1])
        } else {
          // 降级：边界顶点平均值
          let sumX = 0, sumY = 0, ptCnt = 0
          const mainRing = rings[0] || []
          mainRing.forEach(pt => {
            sumX += toX(pt[0]); sumY += toY(pt[1]); ptCnt++
          })
          cx = ptCnt ? sumX / ptCnt : M / 2
          cy = ptCnt ? sumY / ptCnt : M / 2
        }

        // 反算经纬度
        const clng = cx / M * (CHINA.maxLng - CHINA.minLng) + CHINA.minLng
        const clat = (1 - cy / M) * (CHINA.maxLat - CHINA.minLat) + CHINA.minLat
        provinceCenters.push({ name, cx, cy, lng: clng, lat: clat })
        // 存储省份多边形路径（2048×2048 坐标系，用于天气纹理精确裁剪）
        const canvasRings = rings.map(ring => ring.map(pt => [toX(pt[0]), toY(pt[1])]))
        provincePaths.push({ name, rings: canvasRings })
        // 存储世界坐标多边形（一步到位，用于雨粒子/闪电精确定位）
        const worldPoly = rings[0].map(pt => {
          const w = lngLatToWorld(pt[0], pt[1])
          return [w.x, w.z]
        })
        provinceWorldPaths.push({ name, polygon: worldPoly })

        // ——— 绘制 Mask ———
        mCtx.fillStyle = '#fff'
        rings.forEach(ring => {
          mCtx.beginPath()
          ring.forEach((pt, i) => {
            const x = toX(pt[0]), y = toY(pt[1])
            i === 0 ? mCtx.moveTo(x, y) : mCtx.lineTo(x, y)
          })
          mCtx.closePath(); mCtx.fill()
        })

        // ——— 绘制 Map ———
        mapCtx.fillStyle = color
        mapCtx.strokeStyle = '#4a5070'
        mapCtx.lineWidth = 2.4
        rings.forEach(ring => {
          mapCtx.beginPath()
          ring.forEach((pt, i) => {
            const x = toX(pt[0]), y = toY(pt[1])
            i === 0 ? mapCtx.moveTo(x, y) : mapCtx.lineTo(x, y)
          })
          mapCtx.closePath()
          mapCtx.fill()
          mapCtx.stroke()
        })
      })

      // ——— 省份名称不再绘制到地图上，改用 3D Sprite 悬浮标签 ———
    }
  } catch (_) {
    // 降级
    mCtx.fillStyle = '#fff'; mCtx.fillRect(0, 0, M, M)
    mapCtx.fillStyle = '#131a2a'; mapCtx.fillRect(0, 0, M, M)
  }

  chinaMaskTex = new THREE.CanvasTexture(maskCanvas)
  chinaMaskTex.minFilter = THREE.LinearFilter
  chinaMaskTex.magFilter = THREE.LinearFilter

  chinaMapTex = new THREE.CanvasTexture(mapCanvas)
  chinaMapTex.minFilter = THREE.LinearFilter
  chinaMapTex.magFilter = THREE.LinearFilter

  // 保存 mask canvas 引用，供雨粒子点池采样
  provinceMaskCanvas = maskCanvas

  // 诊断：输出所有省份名称和世界多边形信息
  console.log('[createChinaTextures] === 省份数据诊断 ===')
  console.log('[createChinaTextures] provinceCenters 名称:', provinceCenters.map(p => p.name).join(', '))
  console.log('[createChinaTextures] provinceWorldPaths 名称:', provinceWorldPaths.map(p => p.name).join(', '))
  // 检查哪些省份 worldPath 是空的或顶点不足
  provinceWorldPaths.forEach(p => {
    if (!p.polygon || p.polygon.length < 3) {
      console.warn('[createChinaTextures] 省份多边形顶点不足:', p.name, p.polygon?.length)
    }
  })
  // 与 PROVINCE_WEATHER 做交叉对比
  const pwNames = new Set(provinceWorldPaths.map(p => p.name))
  const pcNames = new Set(provinceCenters.map(pc => pc.name))
  const weatherNames = new Set(Object.keys(PROVINCE_WEATHER))
  const weatherMissingInPW = [...weatherNames].filter(n => !pwNames.has(n))
  const weatherMissingInPC = [...weatherNames].filter(n => !pcNames.has(n))
  if (weatherMissingInPW.length > 0) console.warn('[createChinaTextures] PROVINCE_WEATHER 中有但 worldPaths 缺失:', weatherMissingInPW)
  if (weatherMissingInPC.length > 0) console.warn('[createChinaTextures] PROVINCE_WEATHER 中有但 centers 缺失:', weatherMissingInPC)
  console.log(`[createChinaTextures] 省份: ${provinceCenters.length} 个, 纹理: ${M}x${M}`)

  // ——— 国界线加粗 (从 mask 提取轮廓) ———
  try {
    const maskGeo = echarts.getMap('china')
    if (maskGeo && maskGeo.geoJSON) {
      mapCtx.strokeStyle = '#3a4060'
      mapCtx.lineWidth = 2.0
      maskGeo.geoJSON.features.forEach(feature => {
        const coords = feature.geometry?.coordinates
        if (!coords) return
        const flatten = (c) => {
          if (!c || !c.length) return
          if (typeof c[0][0] === 'number') {
            mapCtx.beginPath()
            c.forEach((pt, i) => {
              const x = toX(pt[0]), y = toY(pt[1])
              i === 0 ? mapCtx.moveTo(x, y) : mapCtx.lineTo(x, y)
            })
            mapCtx.closePath(); mapCtx.stroke()
          } else { c.forEach(flatten) }
        }
        flatten(coords)
      })
    }
  } catch (_) {}

  // 填充响应式 provinceList（用于模板渲染）
  const filter = new Set(['南海诸岛', '香港', '澳门'])
  provinceList.value = provinceCenters.filter(pc => !filter.has(pc.name))
}

/* ==================== 场景初始化 ==================== */
function initScene() {
  if (!container.value) return
  const el = container.value
  sizeW = el.clientWidth; sizeH = el.clientHeight

  // ——— Renderer ———
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(sizeW, sizeH)
  el.appendChild(renderer.domElement)

  // ——— Scene ———
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xe8ecf2)
  scene.fog = new THREE.FogExp2(0xe8ecf2, 0.00012)

  // ——— Camera ———
  camera = new THREE.PerspectiveCamera(50, sizeW / Math.max(sizeH, 1), 0.5, 60)
  camera.position.set(0, 9, 10)
  camera.lookAt(0, 0, 0)

  // ——— OrbitControls ———
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping   = true
  controls.dampingFactor   = 0.08
  controls.minDistance     = 12
  controls.maxDistance     = 100
  controls.maxPolarAngle   = Math.PI * 0.68
  controls.minPolarAngle   = 0.05
  controls.zoomSpeed      = 2.5
  controls.target.set(0, 0, 0)
  controls.update()

  // ——— Lighting ———
  const amb = new THREE.AmbientLight(0xffffff, 0.9)
  scene.add(amb)
  setAmbientLight(amb)
  const dir = new THREE.DirectionalLight(0xffffff, 0.6)
  dir.position.set(5, 12, 5)
  scene.add(dir)

  // ——— Textures ———
  createWeatherCanvas()
  createChinaTextures()
  buildChinaMaskGrid()  // 采样中国边界遮罩网格
  buildProvinceTerrainGrid()  // 构建省份地形网格
  initRainRegions()    // 初始化阴雨区域（必须在 createChinaTextures 之后）

  // ——— Ground (3D 地形：模糊高度图位移 + 海拔着色) ———
  // 512×512 高度图 + 1px 轻模糊：消除文字但保留地形结构
  const heightCanvas = document.createElement('canvas')
  heightCanvas.width = 512
  heightCanvas.height = 512
  const heightCtx = heightCanvas.getContext('2d')
  const heightTex = new THREE.CanvasTexture(heightCanvas)
  terrainTex = heightTex          // 保存引用给 buildTerrainHeightGrid 使用
  heightTex.minFilter = THREE.LinearMipmapLinearFilter
  heightTex.magFilter = THREE.LinearFilter

  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    heightCtx.drawImage(img, 0, 0, 512, 512)
    // 按颜色分类转换为真正的高度图（彩色地势图亮度≠海拔，必须像素分类）
    const imageData = heightCtx.getImageData(0, 0, 512, 512)
    const d = imageData.data
    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i+1], bb = d[i+2]
      let h
      if (r > 235 && g > 235 && bb > 235 && Math.abs(r - g) < 8 && Math.abs(r - bb) < 8) {
        h = 245  // pure white → snow peaks
      } else if (r > 200 && g > 200 && bb > 175 && r + g + bb > 650 && g <= r + 10) {
        h = 245  // white-blue glacier: bright, balanced, not green-tinted
      } else if (r > 140 && r > g + 28 && g > bb + 35 && r + g + bb < 350) {
        h = 170  // true brown: very R dominant, large G-B gap, dark → high mountains
      } else if (r > 155 && r > g + 12 && bb < g - 8 && r > bb + 52) {
        h = 155  // yellow/tan: R dominant, B lowest, warm contrast → plateau
      } else if (g > r || (g + 5 > r && bb < g)) {
        h = 45   // green / greenish → plains (loose, catches coastal pale greens)
      } else {
        h = 10   // water / other → sea level
      }
      d[i] = d[i+1] = d[i+2] = h
    }
    // 手动压低异常隆起区域
    const overrides = [
      { x1: 390, y1: 0,  x2: 435, y2: 60  },   // 黑龙江西北角
      { x1: 445, y1: 15, x2: 500, y2: 85  },   // 黑龙江北边中部
      { x1: 285, y1: 478, x2: 322, y2: 512 },  // 海南岛（强制平原）
    ]
    const FIXED = 45
    for (const rect of overrides) {
      for (let py = rect.y1; py <= rect.y2; py++) {
        for (let px = rect.x1; px <= rect.x2; px++) {
          const idx = (py * 512 + px) * 4
          if (d[idx] > 80) { d[idx] = d[idx+1] = d[idx+2] = FIXED }
        }
      }
    }
    heightCtx.putImageData(imageData, 0, 0)
    heightTex.needsUpdate = true
    terrainReady = true      // 标记地形高度图就绪
  }
  img.src = require('@/assets/china_terrain.jpg')

  const terrainUni = {
    uHeightTex:      { value: heightTex },
    uChinaMap:       { value: chinaMapTex },
    uChinaMask:      { value: chinaMaskTex },
    uElevationScale: { value: 0.3 },
  }

  const gGeo = new THREE.PlaneGeometry(MAP_W, MAP_H, 300, 300)
  const gMat = new THREE.ShaderMaterial({
    vertexShader:   TERRAIN_VERT,
    fragmentShader: TERRAIN_FRAG,
    uniforms:       terrainUni,
    side:           THREE.DoubleSide,
  })
  const ground = new THREE.Mesh(gGeo, gMat)
  ground.rotation.x = -Math.PI / 2
  scene.add(ground)
  createProvinceLabels()
  loadMountainModels()    // 预加载山脉 GLB 模型

  // ——— Clouds & Rain ———
  createClouds()
  createRain()
  createLightning()

  // ——— 初始天气纹理 ———
  updateWeatherTex()

  // ——— 气象小图 ———
  createWeatherChart()

  // ——— Start loop ———
  animate(0)
}

/* ==================== 动态气旋系统 ==================== */

/** 世界坐标 → 经纬度 */
function worldToLngLat(wx, wz) {
  const lng = CHINA.minLng + ((wx / MAP_W) + 0.5) * (CHINA.maxLng - CHINA.minLng)
  const lat = CHINA.minLat + (0.5 - (wz / MAP_H)) * (CHINA.maxLat - CHINA.minLat)
  return { lng, lat }
}

/** 在路径上按 phase(0-1) 插值 */
function interpolateAlongPath(keypoints, phase) {
  const t = phase * (keypoints.length - 1)
  const i = Math.floor(t)
  const f = t - i
  if (i >= keypoints.length - 1) return { ...keypoints[keypoints.length - 1] }
  const a = keypoints[i], b = keypoints[i + 1]
  return { lng: a.lng + (b.lng - a.lng) * f, lat: a.lat + (b.lat - a.lat) * f }
}

/** 气旋强度曲线（四阶段：形成→巅峰→锢囚→消散） */
function calcCycloneIntensity(phase, peak) {
  if (phase < 0.05) return phase / 0.05 * 0.25            // 初生
  if (phase < 0.1)  return 0.25 + ((phase - 0.05) / 0.05) * 0.2
  if (phase < 0.35) return 0.45 + ((phase - 0.1) / 0.25) * (peak - 0.45)  // 增强
  if (phase < 0.45) return peak                            // 巅峰
  if (phase < 0.52) return peak * (1.0 + (phase - 0.45) / 0.07 * 0.06)     // 锢囚（短暂增强~6%）
  if (phase < 0.78) return peak * (1.06 - (phase - 0.52) / 0.26 * 0.86)     // 衰减
  return peak * (0.2 - (phase - 0.78) / 0.22 * 0.2)        // 消散
}

/** 根据 phase 返回气旋生命周期阶段标签 */
function getCycloneStage(phase) {
  if (phase < 0.05) return '初生'
  if (phase < 0.1)  return '发展'
  if (phase < 0.35) return '增强'
  if (phase < 0.45) return '巅峰'
  if (phase < 0.52) return '锢囚'
  if (phase < 0.78) return '衰减'
  return '消散'
}

/** 初始化/重置所有气旋 */
function initCycloneState() {
  for (const cy of cyclones) {
    cy.phase = 0
    cy.intensity = 0
    cy.efPeak = cy.peakIntensity
    cy.terrainWear = 0
    cy.stage = '初生'
    const paths = (mode.value === 'custom')
      ? customCyclonePaths : CYCLONE_PATHS
    const pts = paths[cy.pathKey]
    if (!pts) continue
    Object.assign(cy.center, pts[0])
  }
  convectiveCells = []
  weatherGridDirty = true
}

/** 推进单个气旋：按 phase 增量更新位置/强度（含地形消耗），动画与推演共用 */
function advanceCyclone(cy, dPhase, dtSeconds, paths) {
  cy.phase += dPhase
  if (cy.phase > 1.0) cy.phase -= 1.0
  const pts = paths[cy.pathKey]
  if (!pts) return
  Object.assign(cy.center, interpolateAlongPath(pts, cy.phase))

  // 地形消耗：山地摩擦持续削弱有效峰值强度
  if (cy.intensity > 0.1) {
    const h = sampleTerrainHeight(cy.center.lng, cy.center.lat)
    if (h > 0.12) {
      // 高度越高摩擦越大，强度越高能量损耗越快
      const wearRate = (h - 0.12) * 0.04 * cy.intensity
      cy.terrainWear += wearRate * dtSeconds
      cy.efPeak = Math.max(0.15, cy.peakIntensity - cy.terrainWear)
    }
  }

  cy.intensity = calcCycloneIntensity(cy.phase, cy.efPeak)
  cy.stage = getCycloneStage(cy.phase)
}

/** 每帧更新所有气旋位置（含地形消耗） */
function updateCyclones(dt) {
  if (mode.value !== 'dynamic' && mode.value !== 'custom') return
  if (clockPaused) return   // 统一时钟接管：phase 由外部 setClockPhase 驱动
  const paths = (mode.value === 'custom' && customCyclonePaths)
    ? customCyclonePaths : CYCLONE_PATHS
  const dPhase = (dt / CYCLONE_CYCLE) * clockSpeed
  for (const cy of cyclones) {
    advanceCyclone(cy, dPhase, dt, paths)
  }
  weatherGridDirty = true
  provinceMapDirty = true
}

/** 更新随机对流雨细胞 */
function updateConvectiveCells(dt) {
  // 衰减已有细胞
  convectiveCells = convectiveCells.filter(c => {
    c.life -= dt
    return c.life > 0
  })
  // 概率生成新细胞（偏南方的夏季午后对流）
  // 平均保持 2-5 个活跃细胞
  if (convectiveCells.length < 3 + Math.floor(Math.random() * 3)) {
    const lng = 78 + Math.random() * 46  // 78-124（偏东部）
    const lat = 20 + Math.random() * 22  // 20-42（偏南部）
    convectiveCells.push({
      lng, lat,
      radius: 1 + Math.random() * 3,
      intensity: 0.3 + Math.random() * 0.4,  // 0.3-0.7，不太强
      life: 6 + Math.random() * 15,  // 6-21 秒寿命
      maxLife: 0,
    })
  }
}

/** 省→地形类型映射：0=平原(跳过) 1=green(绿山) 2=group(群山) 3=snow(雪山) */
const PROVINCE_TERRAIN_MAP = {
  // 简称（ECharts 返回的标准名称）      // 全称别名
  '河北':'plain',   '河北省':'plain',
  '山西':'group',   '山西省':'group',
  '内蒙古':'plain',  '内蒙古自治区':'plain',
  '辽宁':'green',   '辽宁省':'green',
  '吉林':'green',   '吉林省':'green',
  '黑龙江':'plain',  '黑龙江省':'plain',
  '江苏':'plain',   '江苏省':'plain',
  '浙江':'green',   '浙江省':'green',
  '安徽':'plain',   '安徽省':'plain',
  '福建':'green',   '福建省':'green',
  '江西':'green',   '江西省':'green',
  '山东':'plain',   '山东省':'plain',
  '河南':'plain',   '河南省':'plain',
  '湖北':'plain',   '湖北省':'plain',
  '湖南':'group',   '湖南省':'group',
  '广东':'green',   '广东省':'green',
  '广西':'group',  '广西壮族自治区':'group',
  '海南':'green',   '海南省':'green',
  '四川':'group',   '四川省':'group',
  '贵州':'group',   '贵州省':'group',
  '云南':'group',   '云南省':'group',
  '西藏':'snow',    '西藏自治区':'snow',
  '陕西':'green',   '陕西省':'green',
  '甘肃':'group',   '甘肃省':'group',
  '青海':'snow',    '青海省':'snow',
  '宁夏':'plain',   '宁夏回族自治区':'plain',
  '新疆':'snow',    '新疆维吾尔自治区':'snow',
  '台湾':'green',   '台湾省':'green',
  '北京':'plain',   '北京市':'plain',
  '天津':'plain',   '天津市':'plain',
  '上海':'plain',   '上海市':'plain',
  '重庆':'group',   '重庆市':'group',
  '香港':'green',   '香港特别行政区':'green',
  '澳门':'plain',   '澳门特别行政区':'plain',
}
const TERRAIN_ID = { plain: 0, green: 1, group: 2, snow: 3 }
const TERRAIN_KEY = { 1: 'green', 2: 'group', 3: 'snow' }

/** 根据省份边界构建地形网格 */
function buildProvinceTerrainGrid() {
  if (provinceTerrainGrid) return
  if (!provincePaths.length) return
  const M = 2048  // provincePaths 坐标基准
  const tmpCanvas = document.createElement('canvas')
  tmpCanvas.width = WEATHER_GRID; tmpCanvas.height = WEATHER_GRID
  const ctx = tmpCanvas.getContext('2d')
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, WEATHER_GRID, WEATHER_GRID)

  provincePaths.forEach(prov => {
    let terrain = PROVINCE_TERRAIN_MAP[prov.name]
    // 尝试去后缀匹配（如 "广西壮族自治区" → "广西"）
    if (!terrain) {
      const short = prov.name.replace(/省|市|自治区|壮族|回族|维吾尔/g, '')
      terrain = PROVINCE_TERRAIN_MAP[short]
    }
    if (!terrain || terrain === 'plain') return
    const id = TERRAIN_ID[terrain]
    if (!id) return
    ctx.fillStyle = `rgb(${id},0,0)`   // R 通道存地形类型
    prov.rings.forEach(ring => {
      ctx.beginPath()
      ctx.moveTo(ring[0][0] / M * WEATHER_GRID, ring[0][1] / M * WEATHER_GRID)
      for (let i = 1; i < ring.length; i++) {
        ctx.lineTo(ring[i][0] / M * WEATHER_GRID, ring[i][1] / M * WEATHER_GRID)
      }
      ctx.closePath(); ctx.fill()
    })
  })

  const imgData = ctx.getImageData(0, 0, WEATHER_GRID, WEATHER_GRID)
  provinceTerrainGrid = new Uint8Array(WEATHER_GRID * WEATHER_GRID)
  // Y 轴翻转：canvas Y=0 是北（maxLat），placeMountains 的 gy=0 是南（minLat）
  for (let gy = 0; gy < WEATHER_GRID; gy++) {
    for (let gx = 0; gx < WEATHER_GRID; gx++) {
      const srcY = WEATHER_GRID - 1 - gy
      provinceTerrainGrid[gy * WEATHER_GRID + gx] = imgData.data[(srcY * WEATHER_GRID + gx) * 4]
    }
  }
  console.log('省份地形网格已构建')
}

/** 构建中国边界遮罩网格（从 mask canvas 降采样，1=境内 0=境外） */
function buildChinaMaskGrid() {
  if (chinaMaskGrid) return
  if (!provinceMaskCanvas) return
  const tmpCanvas = document.createElement('canvas')
  tmpCanvas.width = WEATHER_GRID; tmpCanvas.height = WEATHER_GRID
  const tmpCtx = tmpCanvas.getContext('2d')
  tmpCtx.drawImage(provinceMaskCanvas, 0, 0, WEATHER_GRID, WEATHER_GRID)
  const imgData = tmpCtx.getImageData(0, 0, WEATHER_GRID, WEATHER_GRID)
  chinaMaskGrid = new Uint8Array(WEATHER_GRID * WEATHER_GRID)
  // Y 轴翻转：mask canvas 的 Y=0 是北（maxLat），terrainGrid 的 gy=0 是南（minLat）
  for (let gy = 0; gy < WEATHER_GRID; gy++) {
    for (let gx = 0; gx < WEATHER_GRID; gx++) {
      const srcY = WEATHER_GRID - 1 - gy
      const idx = srcY * WEATHER_GRID + gx
      chinaMaskGrid[gy * WEATHER_GRID + gx] = imgData.data[idx * 4] > 128 ? 1 : 0
    }
  }
}

/** 
 * 构建地形高度采样网格（从 terrainTex 降采样）
 * terrainTex 在 initTerrain() 中已加载
 */
function buildTerrainHeightGrid() {
  if (terrainHeightGrid) return
  if (!terrainReady) return
  if (!terrainTex || !terrainTex.image) return
  const tmpCanvas = document.createElement('canvas')
  tmpCanvas.width = WEATHER_GRID; tmpCanvas.height = WEATHER_GRID
  const tmpCtx = tmpCanvas.getContext('2d')
  tmpCtx.drawImage(terrainTex.image, 0, 0, WEATHER_GRID, WEATHER_GRID)
  const imgData = tmpCtx.getImageData(0, 0, WEATHER_GRID, WEATHER_GRID)
  terrainHeightGrid = new Float32Array(WEATHER_GRID * WEATHER_GRID)
  for (let i = 0; i < terrainHeightGrid.length; i++) {
    // 亮度 → 高度 (0-1)，max 确保只向上
    const r = imgData.data[i * 4], g = imgData.data[i * 4 + 1], b = imgData.data[i * 4 + 2]
    terrainHeightGrid[i] = Math.max(0, (r * 0.299 + g * 0.587 + b * 0.114) / 255)
  }
}

/** 预加载三个山脉 GLB 模型 */
function loadMountainModels() {
  if (mountainModels) return
  const loader = new GLTFLoader()
  const files = {
    green: 'Mountain by Poly by Google - 099f6GxB1bj.glb',
    group: 'Mountains by Quaternius - w9VBrh7Nz0.glb',
    snow:  'Mountain with Snow by Matthew Creighton - 0VBAQNbpNcl.glb',
  }
  mountainModels = {}
  Object.entries(files).forEach(([key, file]) => {
    loader.load(`/models/${file}`, (gltf) => {
      const src = gltf.scene
      // 原地缩放到合适参考尺寸
      const box = new THREE.Box3().setFromObject(src)
      const sy = box.getSize(new THREE.Vector3()).y
      if (sy > 0.001) {
        src.scale.setScalar(1.8 / sy)
        // 强制更新世界矩阵后，遍历所有 mesh 计算真实世界包围盒
        src.updateMatrixWorld(true)
        const worldBox = new THREE.Box3()
        src.traverse(child => {
          if (child.isMesh) {
            child.geometry.computeBoundingBox()
            const gBox = child.geometry.boundingBox.clone()
            gBox.applyMatrix4(child.matrixWorld)
            worldBox.union(gBox)
          }
        })
        // 记录模型底部偏移量（不修改 src.position，由 placeMountains 使用）
        mountainModelOffsets[key] = -worldBox.min.y
        console.log(`山脉 "${key}": height=${worldBox.getSize(new THREE.Vector3()).y.toFixed(2)}, offsetY=${mountainModelOffsets[key].toFixed(3)}, minY=${worldBox.min.y.toFixed(3)}, maxY=${worldBox.max.y.toFixed(3)}`)
      }
      src.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true } })
      mountainModels[key] = src
      console.log(`山脉模型 "${key}" 加载完成`)
      // 三个模型都加载好后立刻触发放置
      if (mountainModels.green && mountainModels.group && mountainModels.snow) {
        placeMountains()
      }
    }, undefined, (err) => console.warn(`山脉模型 "${key}" 加载失败:`, err))
  })
}

/** 根据地形网格放置山脉模型 */
/** 陕西大致经纬度范围 */
const SHAANXI_BOUNDS = { minLng: 105.3, maxLng: 111.3, minLat: 31.5, maxLat: 39.7 }

function isInShaanxi(lng, lat) {
  return lng >= SHAANXI_BOUNDS.minLng && lng <= SHAANXI_BOUNDS.maxLng &&
         lat >= SHAANXI_BOUNDS.minLat && lat <= SHAANXI_BOUNDS.maxLat
}

/** 新疆大致经纬度范围 */
const XINJIANG_BOUNDS = { minLng: 73.5, maxLng: 96.5, minLat: 34.0, maxLat: 49.2 }

function isInXinjiang(lng, lat) {
  return lng >= XINJIANG_BOUNDS.minLng && lng <= XINJIANG_BOUNDS.maxLng &&
         lat >= XINJIANG_BOUNDS.minLat && lat <= XINJIANG_BOUNDS.maxLat
}

/** 云贵广区域范围（云南+贵州+广西），密度 20% */
const YUN_GUI_GUANG_BOUNDS = { minLng: 97.5, maxLng: 112.1, minLat: 20.9, maxLat: 29.3 }

function isInYunGuiGuang(lng, lat) {
  return lng >= YUN_GUI_GUANG_BOUNDS.minLng && lng <= YUN_GUI_GUANG_BOUNDS.maxLng &&
         lat >= YUN_GUI_GUANG_BOUNDS.minLat && lat <= YUN_GUI_GUANG_BOUNDS.maxLat
}

function placeMountains() {
  if (!mountainModels) return
  if (mountainsPlaced) return
  if (!terrainHeightGrid) return
  // 等三个模型都加载好
  if (!mountainModels.green || !mountainModels.group || !mountainModels.snow) return

  mountainsPlaced = true
  const step = 4   // 每 4 格采样一次（128/4 = 32×32 ≈ 1024 个采样点）
  const ELEVATION_SCALE = 0.3
  let count = 0

  for (let gy = 0; gy < WEATHER_GRID; gy += step) {
    for (let gx = 0; gx < WEATHER_GRID; gx += step) {
      // 使用省份地形网格决定模型类型（0=平原跳过）
      if (!provinceTerrainGrid) continue
      const terrainId = provinceTerrainGrid[gy * WEATHER_GRID + gx]
      if (terrainId === 0) continue        // 平原省份，不放置
      if (chinaMaskGrid && !chinaMaskGrid[gy * WEATHER_GRID + gx]) continue

      const srcKey = TERRAIN_KEY[terrainId]
      if (!srcKey) continue

      const h = terrainHeightGrid ? terrainHeightGrid[gy * WEATHER_GRID + gx] : 0.18
      const groundY = h * ELEVATION_SCALE

      const lng = CHINA.minLng + (gx / (WEATHER_GRID - 1)) * (CHINA.maxLng - CHINA.minLng)
      const lat = CHINA.minLat + (gy / (WEATHER_GRID - 1)) * (CHINA.maxLat - CHINA.minLat)

      // 陕西绿山：降低密度，仅 25% 概率放置
      if (srcKey === 'green' && isInShaanxi(lng, lat)) {
        if (Math.random() > 0.25) continue
      }

      // 新疆雪山：大幅降低密度，仅 8% 概率放置
      if (srcKey === 'snow' && isInXinjiang(lng, lat)) {
        if (Math.random() > 0.08) continue
      }

      // 云贵广山峰：密度 20%
      if (srcKey === 'group' && isInYunGuiGuang(lng, lat)) {
        if (Math.random() > 0.2) continue
      }

      const w = lngLatToWorld(lng, lat)

      const jx = (Math.random() - 0.5) * 1.2
      const jz = (Math.random() - 0.5) * 1.2

      const src = mountainModels[srcKey]
      if (!src) continue

      const clone = src.clone(true)
      const baseOffset = mountainModelOffsets[srcKey] || 0
      clone.position.set(w.x + jx, groundY + baseOffset, w.z + jz)
      clone.rotation.y = Math.random() * Math.PI * 2
      // 绿山矮小（0.4-0.7），群山中等（0.85-1.15），雪山最高（1.2-1.6）
      const s = srcKey === 'green'
        ? 0.4 + Math.random() * 0.3
        : srcKey === 'snow'
          ? 1.2 + Math.random() * 0.4
          : 0.85 + Math.random() * 0.3
      clone.scale.multiplyScalar(s)
      scene.add(clone)
      count++
    }
  }
  console.log(`山脉模型已放置: ${count} 个`)
}

/** 查询某点的地形高度（双线性插值，0-1） */
function sampleTerrainHeight(lng, lat) {
  if (!terrainHeightGrid) return 0
  const gx = (lng - CHINA.minLng) / (CHINA.maxLng - CHINA.minLng) * (WEATHER_GRID - 1)
  const gy = (lat - CHINA.minLat) / (CHINA.maxLat - CHINA.minLat) * (WEATHER_GRID - 1)
  const ix = Math.floor(gx), iy = Math.floor(gy)
  const fx = gx - ix, fy = gy - iy
  const clamp = (v) => Math.max(0, Math.min(WEATHER_GRID - 1, v))
  const get = (x, y) => terrainHeightGrid[clamp(y) * WEATHER_GRID + clamp(x)]
  return get(ix, iy) * (1 - fx) * (1 - fy) +
         get(ix + 1, iy) * fx * (1 - fy) +
         get(ix, iy + 1) * (1 - fx) * fy +
         get(ix + 1, iy + 1) * fx * fy
}

/**
 * 计算某点的地形天气影响因子
 * 山体迎风坡（西侧高地形）：抬升 → 云雨增强
 * 背风坡（东侧低地）：下沉 → 干燥
 * 返回 -0.2 ~ +0.3 的调整量
 */
function terrainWeatherModifier(lng, lat) {
  const h = sampleTerrainHeight(lng, lat)
  if (h < 0.15) return 0  // 低地无影响
  // 高原地形：西侧迎风 → 增强，东侧背风 → 减弱
  const hWest = sampleTerrainHeight(lng - 1.5, lat)
  const hEast = sampleTerrainHeight(lng + 1.5, lat)
  if (h > 0.3 && hWest < h - 0.1) {
    // 西侧低、当前高 → 迎风坡，增强
    return 0.05 + (h - 0.3) * 0.35
  }
  if (h > 0.25 && hEast < h - 0.08) {
    // 当前高、东侧低 → 背风坡，略微减弱（雨影）
    return -(h - 0.25) * 0.15
  }
  return 0
}

/**
 * 核心：计算任意经纬度的综合天气
 * = 多个气旋叠加 + 对流雨细胞 + 地形影响
 * 返回 { wxR: 0-1, type: RAIN_CONFIGS key }
 */
const WEATHER_TYPE_INDEX = { sunny: 0, cloudy: 1, rain_light: 2, rain_moderate: 3, rain_heavy: 4, thunderstorm: 5 }
const WEATHER_TYPE_BY_INDEX = ['sunny', 'cloudy', 'rain_light', 'rain_moderate', 'rain_heavy', 'thunderstorm']

function getWeatherAt(lng, lat, cycloneList, cellList) {
  const cycs = cycloneList || cyclones
  const cells = cellList || convectiveCells
  let bestWxR = 0, bestType = 'sunny'

  // 1. 叠加所有气旋（取最强）
  for (const cy of cycs) {
    if (cy.intensity < 0.05) continue
    const dlng = lng - cy.center.lng
    const dlat = lat - cy.center.lat
    const dist = Math.sqrt(dlng * dlng + dlat * dlat)
    const angle = Math.atan2(dlat, dlng)
    const I = cy.intensity
    const moveAngle = cy.moveDir  // 气旋移动方向（弧度）

    // 锋面方向：冷锋 W 侧（西-西南），暖锋 E 侧（东-东南）
    const coldDir = moveAngle + Math.PI        // 西侧冷锋
    const warmDir = moveAngle                   // 东侧暖锋

    // 冷锋角度差和暖锋角度差
    let coldDiff = Math.abs(angle - coldDir)
    if (coldDiff > Math.PI) coldDiff = 2 * Math.PI - coldDiff
    let warmDiff = Math.abs(angle - warmDir)
    if (warmDiff > Math.PI) warmDiff = 2 * Math.PI - warmDiff

    // 中心低压区 (~2°)
    const coreR = 2.0
    if (dist < coreR) {
      const t = 1 - dist / coreR
      const wxR = 0.78 + t * 0.19
      if (wxR > bestWxR) { bestWxR = wxR; bestType = 'thunderstorm' }
      continue
    }

    // 暖区（南侧，冷锋和暖锋之间）：天气相对晴好
    // 暖区范围：南侧（angle 在 -π/2 ~ -π/6 方向，即 SE~SW），距中心 2~5°
    const southAngle = moveAngle - Math.PI * 0.35  // 南侧偏东
    let southDiff = Math.abs(angle - southAngle)
    if (southDiff > Math.PI) southDiff = 2 * Math.PI - southDiff
    if (southDiff < 0.45 && dist > coreR && dist < coreR * 2.5 && I > 0.25) {
      // 暖区：弱化天气（cloudy 或 sunny）
      if (bestWxR < 0.1) { bestWxR = 0.06; bestType = 'sunny' }
      else if (bestWxR < 0.35) { /* 保持原天气 */ }
      else { bestWxR = Math.min(bestWxR, 0.25); bestType = 'cloudy' }
    }

    // 冷锋（W，窄带强降水）
    const cw = 0.3 + I * 0.15; const cl = 5.5 + I * 1.5
    if (coldDiff < cw && dist < cl) {
      const ft = Math.max(0, 1 - Math.max(dist / cl, coldDiff / cw))
      let type, wxR
      if (ft > 0.6) { type = 'rain_heavy'; wxR = 0.72 + ft * 0.18 }
      else if (ft > 0.25) { type = 'rain_moderate'; wxR = 0.52 + ft * 0.3 }
      else { type = 'rain_light'; wxR = 0.28 + ft * 0.4 }
      if (wxR > bestWxR) { bestWxR = wxR; bestType = type }
    }

    // 暖锋（E，宽带连续性降水）
    const ww = 0.7 + I * 0.2; const wl = 8 + I * 1.5
    if (warmDiff < ww && dist < wl) {
      const ft = Math.max(0, 1 - Math.max(dist / wl, warmDiff / ww))
      let type, wxR
      if (ft > 0.55) { type = 'rain_moderate'; wxR = 0.6 + ft * 0.1 }
      else if (ft > 0.2) { type = 'rain_light'; wxR = 0.35 + ft * 0.3 }
      else { type = 'cloudy'; wxR = 0.16 + ft * 0.3 }
      if (wxR > bestWxR) { bestWxR = wxR; bestType = type }
    }

    // 缓冲区（气旋外围多云）
    if (dist < coreR * 3.5 && I > 0.25) {
      const wxR = 0.08 + I * 0.12
      if (wxR > bestWxR) { bestWxR = wxR; bestType = 'cloudy' }
    }
  }

  // 2. 叠加对流雨细胞
  for (const cell of cells) {
    const dlng = lng - cell.lng, dlat = lat - cell.lat
    const dist = Math.sqrt(dlng * dlng + dlat * dlat)
    if (dist < cell.radius) {
      const t = (1 - dist / cell.radius) * cell.intensity * Math.min(1, cell.life / 3)
      if (t > 0.7) {
        const wxR = 0.78 + t * 0.15
        if (wxR > bestWxR) { bestWxR = wxR; bestType = 'thunderstorm' }
      } else if (t > 0.4) {
        const wxR = 0.55 + t * 0.3
        if (wxR > bestWxR) { bestWxR = wxR; bestType = 'rain_heavy' }
      } else if (t > 0.15) {
        const wxR = 0.3 + t * 0.4
        if (wxR > bestWxR) { bestWxR = wxR; bestType = 'rain_moderate' }
      }
    }
  }

  // 3. 地形影响
  const terrainMod = terrainWeatherModifier(lng, lat)
  if (terrainMod !== 0 && bestWxR > 0.1) {
    bestWxR = Math.max(0, Math.min(0.97, bestWxR + terrainMod))
    // 如果原本是小雨但地形大幅增强，升级为中雨
    if (terrainMod > 0.1 && bestType === 'rain_light' && bestWxR > 0.5) bestType = 'rain_moderate'
  }

  return { wxR: Math.min(0.97, Math.max(bestWxR, 0.04)), type: bestType || 'sunny' }
}

/** 重建天气计算网格 */
function rebuildWeatherGrid() {
  if (!weatherGridDirty) return
  if (!terrainReady) return   // 地形高度图未加载完，等下一帧重试
  buildTerrainHeightGrid()
  placeMountains()   // 首次地形网格就绪后放置山脉模型
  for (let gy = 0; gy < WEATHER_GRID; gy++) {
    for (let gx = 0; gx < WEATHER_GRID; gx++) {
      const lng = CHINA.minLng + (gx / (WEATHER_GRID - 1)) * (CHINA.maxLng - CHINA.minLng)
      const lat = CHINA.minLat + (gy / (WEATHER_GRID - 1)) * (CHINA.maxLat - CHINA.minLat)
      const w = getWeatherAt(lng, lat)
      weatherGrid[gy * WEATHER_GRID + gx] = WEATHER_TYPE_INDEX[w.type]
    }
  }
  weatherGridDirty = false
  rebuildWeatherGridIndex()
  weatherGridVersion.value++
}

/** 从天气网格查找指定类型的随机位置 */
// 天气网格按类型建索引：雨滴落地重采样时不用每次扫描整张 128×128 网格
let weatherGridCellsByType = {}

function rebuildWeatherGridIndex() {
  const map = Object.create(null)
  for (let gy = 0; gy < WEATHER_GRID; gy++) {
    for (let gx = 0; gx < WEATHER_GRID; gx++) {
      const type = WEATHER_TYPE_BY_INDEX[weatherGrid[gy * WEATHER_GRID + gx]]
      if (!map[type]) map[type] = []
      map[type].push({ gx, gy })
    }
  }
  weatherGridCellsByType = map
}

function spawnFromWeatherGrid(targetTypes) {
  let total = 0
  for (const t of targetTypes) {
    const list = weatherGridCellsByType[t]
    if (list) total += list.length
  }
  if (total === 0) return null

  // 按各类型格点数量加权随机选一个类型，再随机取格点
  let r = Math.random() * total
  let pickedType = targetTypes[0]
  let pickedList = null
  for (const t of targetTypes) {
    const list = weatherGridCellsByType[t]
    if (!list || !list.length) continue
    if (r < list.length) { pickedType = t; pickedList = list; break }
    r -= list.length
  }
  if (!pickedList) return null

  const m = pickedList[Math.floor(Math.random() * pickedList.length)]
  const lng = CHINA.minLng + (m.gx / (WEATHER_GRID - 1)) * (CHINA.maxLng - CHINA.minLng)
  const lat = CHINA.minLat + ((m.gy + (Math.random() - 0.5) * 0.8) / (WEATHER_GRID - 1)) * (CHINA.maxLat - CHINA.minLat)
  const dLng = (Math.random() - 0.5) * 0.8 * (CHINA.maxLng - CHINA.minLng) / (WEATHER_GRID - 1)
  const w = lngLatToWorld(lng + dLng, lat)
  return { x: w.x, z: w.z, type: pickedType }
}

/** 动态模式：将天气网格绘制到 Canvas 纹理 */
let dynamicGridCanvas = null
function drawDynamicWeather() {
  rebuildWeatherGrid()
  if (!dynamicGridCanvas) {
    dynamicGridCanvas = document.createElement('canvas')
    dynamicGridCanvas.width = WEATHER_GRID; dynamicGridCanvas.height = WEATHER_GRID
  }
  const gCtx = dynamicGridCanvas.getContext('2d')
  if (!dynamicGridImageData) {
    dynamicGridImageData = gCtx.createImageData(WEATHER_GRID, WEATHER_GRID)
  }
  const imgData = dynamicGridImageData
  for (let gy = 0; gy < WEATHER_GRID; gy++) {
    for (let gx = 0; gx < WEATHER_GRID; gx++) {
      const type = WEATHER_TYPE_BY_INDEX[weatherGrid[gy * WEATHER_GRID + gx]]
      const params = WEATHER_PARAMS[type]
      const rVal = params ? Math.round(params.wxR * 255) : 0
      const idx = (gy * WEATHER_GRID + gx) * 4
      imgData.data[idx] = imgData.data[idx + 1] = imgData.data[idx + 2] = rVal
      imgData.data[idx + 3] = 255
    }
  }
  gCtx.putImageData(imgData, 0, 0)
  const ctx = weatherCtx
  // grid 图完全不透明，drawImage 会覆盖整块纹理，无需先 clear/fill
  ctx.drawImage(dynamicGridCanvas, 0, 0, 2048, 2048)
}

/** 动态模式：更新降雨粒子、雷电可见性和动态管理闪电 */
function updateDynamicRain() {
  const activeTypes = new Set()
  // 统计雷暴网格数量用于决定雷电数量
  let stormCellCount = 0
  for (let i = 0; i < weatherGrid.length; i++) {
    const type = WEATHER_TYPE_BY_INDEX[weatherGrid[i]]
    if (type !== 'sunny' && type !== 'cloudy' && RAIN_CONFIGS[type]) activeTypes.add(type)
    if (type === 'thunderstorm') stormCellCount++
  }
  for (const sys of rainSystems) {
    sys.points.visible = activeTypes.has(sys.type)
    if (sys.points.geometry.userData) {
      sys.points.geometry.userData.regions = [{ type: sys.type }]
    }
  }

  // 动态管理闪电：有雷暴时创建/维持 lightningBolts，无雷暴时清除
  const hasThunder = activeTypes.has('thunderstorm') && stormCellCount > 0
  if (hasThunder) {
    // 根据雷暴覆盖面积决定闪电数量
    const targetBoltCount = stormCellCount >= 15 ? 12
      : stormCellCount >= 8 ? 8
      : stormCellCount >= 3 ? 5
      : 2

    // 补齐到目标数量
    while (lightningBolts.length < targetBoltCount) {
      const pos = spawnFromWeatherGrid(['thunderstorm'])
      if (!pos) break
      const bolt = createLightningBolt(pos.x, pos.z)
      bolt.userData.region = { _dynamic: true }  // 标记为动态模式
      bolt.userData.nextFlash = Math.random() * 1.5
      lightningBolts.push(bolt)
    }

    // 过多则移除
    while (lightningBolts.length > targetBoltCount) {
      const old = lightningBolts.pop()
      old.children.forEach(c => { c.geometry.dispose(); c.material.dispose() })
      scene.remove(old)
    }

    for (const bolt of lightningBolts) {
      bolt.visible = true
    }
  } else {
    // 无雷暴：清除所有闪电
    while (lightningBolts.length > 0) {
      const old = lightningBolts.pop()
      old.children.forEach(c => { c.geometry.dispose(); c.material.dispose() })
      scene.remove(old)
    }
  }
}

/** 动态模式：更新省份天气映射表 */
function updateDynamicProvinceMap() {
  if (!provinceMapDirty) return
  const map = {}
  for (const pc of provinceCenters) {
    if (!pc.lng || !pc.lat) continue
    const w = getWeatherAt(pc.lng, pc.lat)
    map[pc.name] = w.type
  }
  dynamicProvinceMap.value = map
  provinceMapDirty = false
}

/* ==================== 统一时钟 & 三页联动接口 ==================== */

/** phase(0~1) → 绝对业务分钟（自 2020-11-01 00:00 起算，与后端一致） */
function phaseToAbsoluteMinutes(phase) {
  const p = ((phase % 1.0) + 1.0) % 1.0
  return BUSINESS_EPOCH_MINUTES + Math.floor(p * CYCLONE_BUSINESS_MINUTES)
}

/** 绝对业务分钟 → "YYYY-MM-DD HH:MM"（复刻后端 _min_to_time 的 30 天/月简化） */
function formatBusinessTime(absMinutes) {
  const totalDays = Math.floor(absMinutes / BUSINESS_MINUTES_PER_DAY)
  const month = 11 + Math.floor(totalDays / 30)
  const day = totalDays % 30 + 1
  const rem = absMinutes % BUSINESS_MINUTES_PER_DAY
  const hour = Math.floor(rem / 60)
  const minute = rem % 60
  const p2 = (n) => String(n).padStart(2, '0')
  return `2020-${p2(month)}-${p2(day)} ${p2(hour)}:${p2(minute)}`
}

/** 读取当前各省天气快照（不重算天气，直接读已随动画更新的表） */
function getCurrentProvinceWeather() {
  if (mode.value === 'manual') return { ...manualWeather.value }
  if (mode.value === 'auto') return { ...PROVINCE_WEATHER }
  const map = { ...(dynamicProvinceMap.value || {}) }
  provinceCenters.forEach(pc => { if (!map[pc.name]) map[pc.name] = 'sunny' })
  return map
}

/** 当前统一时钟信息（以天气 phase 映射为锚点 T0） */
function getBusinessClock() {
  const active = cyclones.length ? cyclones : [{ phase: 0 }]
  const avgPhase = active.reduce((s, c) => s + (c.phase || 0), 0) / active.length
  const abs = phaseToAbsoluteMinutes(avgPhase)
  return {
    anchor: BUSINESS_EPOCH_STR,
    epoch_minutes: BUSINESS_EPOCH_MINUTES,
    cycle_minutes: CYCLONE_BUSINESS_MINUTES,
    minutes_per_second: UNIFIED_MINUTES_PER_SECOND,
    current_phase: Number(avgPhase.toFixed(4)),
    current_time: formatBusinessTime(abs),
  }
}

/** 当前模式（供上层组装 stream 请求） */
function getMode() {
  return mode.value
}

/** 气旋确定性推演：从当前 phase 出发，外推未来 durationMinutes 的各省天气时间线 */
function predictProvinceTimeline(durationMinutes) {
  const timeline = {}
  const validProvinces = provinceCenters.filter(
    pc => pc.name && pc.lng !== undefined && pc.lat !== undefined,
  )
  validProvinces.forEach(pc => { timeline[pc.name] = [] })

  if (!validProvinces.length || !cyclones.length) {
    return {
      anchor: BUSINESS_EPOCH_STR,
      minutes_per_step: 5,
      duration_minutes: durationMinutes,
      timeline,
    }
  }

  // 克隆当前气旋（确定性推演，忽略随机对流细胞）
  const cloned = cyclones.map(cy => ({ ...cy, center: { ...cy.center } }))
  const paths = (mode.value === 'custom' && customCyclonePaths)
    ? customCyclonePaths : CYCLONE_PATHS
  const nowAbs = phaseToAbsoluteMinutes(
    cloned.reduce((s, c) => s + c.phase, 0) / cloned.length,
  )

  const stepMinutes = 30
  const steps = Math.max(1, Math.ceil(durationMinutes / stepMinutes))
  const dPhase = stepMinutes / CYCLONE_BUSINESS_MINUTES
  const dtSeconds = stepMinutes / UNIFIED_MINUTES_PER_SECOND

  for (let i = 0; i <= steps; i++) {
    const t = i * stepMinutes
    if (i > 0) {
      for (const cy of cloned) advanceCyclone(cy, dPhase, dtSeconds, paths)
    }
    const timeStr = formatBusinessTime(nowAbs + t)
    for (const pc of validProvinces) {
      const w = getWeatherAt(pc.lng, pc.lat, cloned, [])
      timeline[pc.name].push({ t, time: timeStr, type: w.type })
    }
  }

  return {
    anchor: BUSINESS_EPOCH_STR,
    minutes_per_step: stepMinutes,
    duration_minutes: durationMinutes,
    timeline,
  }
}

/** 统一时钟：直接设置所有气旋 phase（0~1）并重算位置/强度/天气 */
function setClockPhase(p) {
  const paths = (mode.value === 'custom' && customCyclonePaths)
    ? customCyclonePaths : CYCLONE_PATHS
  const norm = ((p % 1.0) + 1.0) % 1.0
  for (const cy of cyclones) {
    cy.phase = norm
    const pts = paths[cy.pathKey]
    if (pts) Object.assign(cy.center, interpolateAlongPath(pts, cy.phase))
    cy.terrainWear = 0
    cy.efPeak = cy.peakIntensity
    cy.intensity = calcCycloneIntensity(cy.phase, cy.efPeak)
    cy.stage = getCycloneStage(cy.phase)
  }
  convectiveCells = []
  weatherGridDirty = true
  provinceMapDirty = true
}

/** 统一时钟：暂停/恢复天气内部 phase 自动推进 */
function setClockPaused(paused) {
  clockPaused = !!paused
}

/** 统一时钟：设置倍速（1x=5 业务分钟/秒） */
function setClockSpeed(speed) {
  clockSpeed = Number(speed) || 1
}

defineExpose({ getMode, getCurrentProvinceWeather, getBusinessClock, predictProvinceTimeline, setClockPhase, setClockPaused, setClockSpeed, applyProvinceWeather })

/** 打开透明浮层：把图表需要的只读状态/方法打包传给图表模块 */
function openCharts() {
  chartList.value = buildWeatherCharts({
    mode: mode.value,
    weatherGroups: weatherGroups.value,
    cycloneStates: cycloneStates.value,
    forecast: forecast.value,
    streamSummary: props.streamSummary,
    getBusinessClock,
    predictProvinceTimeline,
  })
  chartsOpen.value = true
}

/** 更新气旋实时状态面板数据（节流更新，减少响应式开销） */
let lastCycloneStateUpdate = 0
function updateCycloneStates() {
  const now = performance.now()
  if (now - lastCycloneStateUpdate < 500) return  // 0.5s 刷新一次
  lastCycloneStateUpdate = now

  const states = []
  for (let i = 0; i < cyclones.length; i++) {
    const cy = cyclones[i]
    if (cy.intensity < 0.02) continue
    states.push({
      id: i + 1,
      intensity: cy.intensity,
      stage: cy.stage || getCycloneStage(cy.phase),
      peakIntensity: cy.peakIntensity,
      efPeak: cy.efPeak ?? cy.peakIntensity,
      terrainWear: cy.terrainWear || 0,
      lng: cy.center.lng,
      lat: cy.center.lat,
    })
  }
  cycloneStates.value = states
}

/* ==================== 未来天气预报 ==================== */
const FORECAST_LABELS = {
  sunny: '晴', cloudy: '多云', rain_light: '小雨',
  rain_moderate: '中雨', rain_heavy: '大雨', thunderstorm: '雷暴',
}
// 未来 24 小时采样点（业务分钟，每 3 小时一个）
const FORECAST_SAMPLES = [0, 180, 360, 540, 720, 900, 1080, 1260, 1440]
const BAD_WEATHER_TYPES = new Set(['rain_light', 'rain_moderate', 'rain_heavy', 'thunderstorm'])

const forecast = ref(null)
let forecastTimer = null

function labelOf(type) {
  return FORECAST_LABELS[type] || '晴'
}

/** 用气旋确定性推演未来 24h 天气，聚合成「有坏天气省份」的预报表格 */
function updateForecast() {
  const predicted = predictProvinceTimeline(1440)
  const tl = (predicted && predicted.timeline) || {}
  const times = FORECAST_SAMPLES.map(t => (t === 0 ? '现在' : '+' + (t / 60) + 'h'))

  const rows = []
  for (const name of Object.keys(tl)) {
    const points = tl[name] || []
    const byT = {}
    for (const p of points) byT[p.t] = p.type
    const cells = FORECAST_SAMPLES.map(t => byT[t] || 'sunny')
    if (cells.some(c => BAD_WEATHER_TYPES.has(c))) {
      rows.push({ name, cells })
    }
  }
  // 坏天气格数多的省份排在前面
  rows.sort((a, b) => {
    const ba = a.cells.filter(c => BAD_WEATHER_TYPES.has(c)).length
    const bb = b.cells.filter(c => BAD_WEATHER_TYPES.has(c)).length
    return bb - ba
  })

  forecast.value = { times, rows }
}

/* ==================== 气象小图 ==================== */

/** 创建气象小图 Canvas（挂载到仪表盘 canvas） */
function createWeatherChart() {
  weatherChartCanvas = dashCanvas.value
  if (!weatherChartCanvas) return
  weatherChartCanvas.width = 260; weatherChartCanvas.height = 220
  weatherChartCtx = weatherChartCanvas.getContext('2d')
}

/** 绘制气象小图 */
function drawWeatherChart() {
  if (!weatherChartCtx) return
  const W = 260, H = 220
  const ctx = weatherChartCtx
  ctx.clearRect(0, 0, W, H)

  // ——— 中国地图底座 ———
  const marginL = 14, marginR = 10, marginT = 14, marginB = 30
  const mapW = W - marginL - marginR
  const mapH = H - marginT - marginB
  const toX = (lng) => marginL + (lng - 73) / 62 * mapW
  const toY = (lat) => marginT + (54 - lat) / 36 * mapH  // 与底图 Y 对齐

  // 中国轮廓 + 省界底图：2048² 纹理缩到 232×176 很贵，首次预缩放到小画布后复用
  if (!weatherChartBaseReady && chinaMaskTex && chinaMaskTex.image) {
    if (!weatherChartBase) weatherChartBase = document.createElement('canvas')
    weatherChartBase.width = Math.max(1, Math.round(mapW))
    weatherChartBase.height = Math.max(1, Math.round(mapH))
    const bctx = weatherChartBase.getContext('2d')
    bctx.globalAlpha = 0.25
    bctx.drawImage(chinaMaskTex.image, 0, 0, weatherChartBase.width, weatherChartBase.height)
    if (chinaMapTex && chinaMapTex.image) {
      bctx.globalAlpha = 0.4
      bctx.drawImage(chinaMapTex.image, 0, 0, weatherChartBase.width, weatherChartBase.height)
    }
    bctx.globalAlpha = 1
    weatherChartBaseReady = true
  }
  if (weatherChartBaseReady) {
    ctx.drawImage(weatherChartBase, marginL, marginT)
  } else {
    // fallback: 矩形框
    ctx.strokeStyle = 'rgba(255,255,255,0.2)'; ctx.lineWidth = 0.8
    ctx.strokeRect(marginL, marginT, mapW, mapH)
  }

  // ——— 只显示强度 > 0.6 的对流雨细胞（极弱小圆点） ———
  for (const cell of convectiveCells) {
    if (cell.intensity < 0.6 || cell.life < 1) continue
    const cx = toX(cell.lng), cy2 = toY(cell.lat)
    ctx.fillStyle = 'rgba(180,210,255,0.5)'
    ctx.beginPath(); ctx.arc(cx, cy2, 1.5, 0, Math.PI * 2); ctx.fill()
  }

  // ——— 绘制每个气旋 ———
  for (const cy of cyclones) {
    if (cy.intensity < 0.08) continue
    const cx = toX(cy.center.lng), cy2 = toY(cy.center.lat)

    // 气旋符号：红色 L（低压中心）
    ctx.fillStyle = 'rgba(255,60,40,0.9)'
    ctx.font = 'bold 13px sans-serif'; ctx.textAlign = 'center'
    ctx.fillText('L', cx, cy2 + 5)

    // 气旋圈
    ctx.strokeStyle = 'rgba(255,60,40,0.5)'; ctx.lineWidth = 1
    ctx.beginPath(); ctx.arc(cx, cy2, 15 * cy.intensity, 0, Math.PI * 2); ctx.stroke()

    // 冷锋线（W方向蓝色三角）
    const coldLen = 30 * cy.intensity
    const coldAngle = cy.moveDir + Math.PI
    const coldEndX = cx + Math.cos(coldAngle) * coldLen
    const coldEndY = cy2 + Math.sin(coldAngle) * coldLen
    ctx.strokeStyle = '#4499ff'; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(cx, cy2); ctx.lineTo(coldEndX, coldEndY); ctx.stroke()
    // 冷锋三角
    for (let i = 0; i < 3; i++) {
      const t = 0.25 + i * 0.3
      const tx = cx + Math.cos(coldAngle) * coldLen * t
      const ty = cy2 + Math.sin(coldAngle) * coldLen * t
      const perpX = Math.cos(coldAngle + Math.PI / 2) * 4
      const perpY = Math.sin(coldAngle + Math.PI / 2) * 4
      ctx.fillStyle = '#4499ff'
      ctx.beginPath(); ctx.moveTo(tx, ty)
      ctx.lineTo(tx + perpX, ty + perpY)
      ctx.lineTo(tx - perpX, ty - perpY)
      ctx.closePath(); ctx.fill()
    }

    // 暖锋线（E方向红色半圆）
    const warmLen = 35 * cy.intensity
    const warmAngle = cy.moveDir
    const warmEndX = cx + Math.cos(warmAngle) * warmLen
    const warmEndY = cy2 + Math.sin(warmAngle) * warmLen
    ctx.strokeStyle = '#ff5544'; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(cx, cy2); ctx.lineTo(warmEndX, warmEndY); ctx.stroke()
    // 暖锋半圆
    for (let i = 0; i < 3; i++) {
      const t = 0.25 + i * 0.3
      const tx = cx + Math.cos(warmAngle) * warmLen * t
      const ty = cy2 + Math.sin(warmAngle) * warmLen * t
      ctx.fillStyle = '#ff5544'
      ctx.beginPath(); ctx.arc(tx, ty, 3.5, warmAngle - Math.PI / 2, warmAngle + Math.PI / 2); ctx.fill()
    }

    // 风向箭头
    const windLen = 12
    const arrowX = cx + Math.cos(cy.moveDir) * windLen
    const arrowY = cy2 + Math.sin(cy.moveDir) * windLen
    ctx.strokeStyle = '#ffcc00'; ctx.lineWidth = 1.2
    ctx.beginPath(); ctx.moveTo(cx, cy2); ctx.lineTo(arrowX, arrowY); ctx.stroke()
    const arrowTip = 4
    ctx.beginPath()
    ctx.moveTo(arrowX, arrowY)
    ctx.lineTo(arrowX - Math.cos(cy.moveDir - 0.6) * arrowTip, arrowY - Math.sin(cy.moveDir - 0.6) * arrowTip)
    ctx.lineTo(arrowX - Math.cos(cy.moveDir + 0.6) * arrowTip, arrowY - Math.sin(cy.moveDir + 0.6) * arrowTip)
    ctx.closePath(); ctx.fillStyle = '#ffcc00'; ctx.fill()

    // 风力标签
    const windForce = Math.round(cy.intensity * 8 + 2)
    ctx.fillStyle = '#ffcc00'; ctx.font = '9px sans-serif'; ctx.textAlign = 'left'
    ctx.fillText(windForce + '级', cx + 10, cy2 - 14)
  }

  // 图例
  ctx.fillStyle = '#aaa'; ctx.font = '9px sans-serif'; ctx.textAlign = 'left'
  const legendY = H - marginB / 2 - 6
  ctx.fillText('L 气旋中心', marginL, legendY - 8)
  ctx.fillText('→ 风向风力', marginL, legendY + 8)
  ctx.fillText('· 强对流', marginL + 80, legendY - 8)
  ctx.fillStyle = '#4499ff'; ctx.fillText('━ 冷锋', marginL + 80, legendY + 8)
  ctx.fillStyle = '#ff5544'; ctx.fillText('━ 暖锋', marginL + 150, legendY + 8)
  // 强对流图例圆点
  ctx.fillStyle = 'rgba(180,210,255,0.5)'
  ctx.beginPath(); ctx.arc(marginL + 76, legendY - 12, 2, 0, Math.PI * 2); ctx.fill()
}

/** 切换模式 */
function setMode(m) {
  mode.value = m
  if (m === 'manual') {
    if (Object.keys(manualWeather.value).length === 0) {
      manualWeather.value = initManualWeather()
    }
    rebuildRainRegions(manualWeather.value)
    rebuildLightning(manualWeather.value)
    updateWeatherTex()
  } else if (m === 'dynamic') {
    // 恢复默认气旋路径
    useDefaultCyclones()
    initCycloneState()
    updateWeatherTex()
  } else if (m === 'custom') {
    // 自定义模式：从配置构建路径（如果已有保存的配置则用保存的）
    if (!customModeActive && cycloneConfigs.value.length > 0) {
      buildCustomCyclonePaths()
      initCycloneState()
      customModeActive = true
    }
    updateWeatherTex()
  } else {
    rebuildRainRegions(PROVINCE_WEATHER)
    rebuildLightning(PROVINCE_WEATHER)
    updateWeatherTex()
  }
  // 非动态/自定义模式清除气旋状态面板
  if (m !== 'dynamic' && m !== 'custom') {
    cycloneStates.value = []
  }
}

/** 恢复默认气旋路径 */
function useDefaultCyclones() {
  customModeActive = false
  cyclones.length = 0
  cyclones.push(
    { pathKey: 'north', phaseOffset: 0.0,  peakIntensity: 0.75, moveDir: 0.15,
      center: { lng: 76, lat: 44 }, phase: 0, intensity: 0, efPeak: 0.75, terrainWear: 0, stage: '' },
    { pathKey: 'south', phaseOffset: 0.30, peakIntensity: 1.0,  moveDir: 0.08,
      center: { lng: 78, lat: 31 }, phase: 0, intensity: 0, efPeak: 1.0, terrainWear: 0, stage: '' },
    { pathKey: 'middle', phaseOffset: 0.55, peakIntensity: 0.85, moveDir: 0.12,
      center: { lng: 80, lat: 37 }, phase: 0, intensity: 0, efPeak: 0.85, terrainWear: 0, stage: '' },
  )
}

/** 省份天气变更（手动模式） */
function onProvinceWeatherChange() {
  if (mode.value !== 'manual') return
  rebuildRainRegions(manualWeather.value)
  rebuildLightning(manualWeather.value)
  updateWeatherTex()
}

/** 实验回放：用给定省份天气直接进入手动模式（只喂数据，不改渲染内核） */
function applyProvinceWeather(map) {
  mode.value = 'manual'
  manualWeather.value = { ...(map || {}) }
  rebuildRainRegions(manualWeather.value)
  rebuildLightning(manualWeather.value)
  updateWeatherTex()
  cycloneStates.value = []
}

/* ==================== 自定义气旋 ==================== */

/** 强度 level → 中文标签 */
function levelLabel(level) {
  const item = intensityLevels.find(i => i.level === level)
  return item ? item.label : '多云'
}

/** 气旋数量变更：增减配置项 */
function onCycloneCountChange() {
  const n = cycloneCount.value
  while (cycloneConfigs.value.length < n) {
    cycloneConfigs.value.push({ start: '新疆', end: '黑龙江', level: 3 })
  }
  while (cycloneConfigs.value.length > n) {
    cycloneConfigs.value.pop()
  }
}

/** 根据配置构建 CYCLONE_PATHS 和 cyclones 数组 */
function buildCustomCyclonePaths() {
  const paths = {}
  const cycs = []
  const dirOffset = [0.15, 0.08, 0.12, 0.20, -0.05]  // 移动方向偏移（弧度）
  for (let i = 0; i < cycloneConfigs.value.length; i++) {
    const cfg = cycloneConfigs.value[i]
    const startPC = provinceCenters.find(pc => pc.name === cfg.start)
    const endPC = provinceCenters.find(pc => pc.name === cfg.end)
    if (!startPC || !endPC) continue

    const key = `custom_${i}`
    // 生成路径：起点 → 终点（加一个中点使路径略微弯曲）
    const mid = {
      lng: (startPC.lng + endPC.lng) / 2 + (Math.random() - 0.5) * 8,
      lat: (startPC.lat + endPC.lat) / 2 + (Math.random() - 0.5) * 6,
    }
    paths[key] = [
      { lng: startPC.lng, lat: startPC.lat },
      mid,
      { lng: endPC.lng, lat: endPC.lat },
    ]
    const il = intensityLevels.find(i => i.level === cfg.level) || intensityLevels[0]
    // 计算移动方向角（起点→终点）
    const dx = endPC.lng - startPC.lng, dy = endPC.lat - startPC.lat
    const dir = Math.atan2(dy, dx) + (dirOffset[i % dirOffset.length] || 0)
    cycs.push({
      pathKey: key, phaseOffset: i * (1.0 / cycloneConfigs.value.length),
      peakIntensity: il.peak, moveDir: dir,
      center: { lng: startPC.lng, lat: startPC.lat },
      phase: 0, intensity: 0, efPeak: il.peak, terrainWear: 0, stage: '初生',
    })
  }
  customCyclonePaths = paths
  // 替换全局 cyclones 数组
  cyclones.length = 0
  cyclones.push(...cycs)
}

/** 保存配置到 localStorage */
function saveCycloneConfig() {
  const data = {
    count: cycloneCount.value,
    configs: cycloneConfigs.value.map(c => ({ start: c.start, end: c.end, level: c.level })),
  }
  try {
    localStorage.setItem('weather_cyclone_config', JSON.stringify(data))
    console.log('[自定义气旋] 配置已保存')
  } catch (_) { console.warn('[自定义气旋] 保存失败') }
}

/** 从 localStorage 加载配置 */
function loadCycloneConfig() {
  try {
    const raw = localStorage.getItem('weather_cyclone_config')
    if (!raw) return
    const data = JSON.parse(raw)
    cycloneCount.value = Math.max(1, Math.min(5, data.count || 3))
    cycloneConfigs.value = data.configs || [
      { start: '新疆', end: '黑龙江', level: 3 },
      { start: '西藏', end: '江苏', level: 4 },
      { start: '青海', end: '山东', level: 2 },
    ]
    console.log('[自定义气旋] 配置已加载')
  } catch (_) { console.warn('[自定义气旋] 加载失败') }
}

/** 应用当前配置：构建路径 + 重置气旋 → 开始推演 */
function applyCycloneConfig() {
  buildCustomCyclonePaths()
  initCycloneState()
  customModeActive = true
  weatherGridDirty = true
  provinceMapDirty = true
}

/* ==================== 动画循环 ==================== */
let tickCounter = 0
let lastWeatherTexAt = 0
let dynamicGridImageData = null
let weatherChartBase = null
let weatherChartBaseReady = false
let lastChartDrawAt = 0
function animate(time) {
  animationId = requestAnimationFrame(animate)
  const dt = Math.min((time - lastTime) / 1000, 0.1)
  lastTime = time

  // 作为「模拟大引擎」的非活动 tab 时（display:none）：继续推进时钟与天气场，
  // 但跳过纹理重绘、粒子更新与 render，避免多个 3D 场景同时抢占 GPU。
  const hidden = !!(container.value && container.value.getClientRects().length === 0)

  if (hidden) {
    if (mode.value === 'dynamic' || mode.value === 'custom') {
      updateCyclones(dt)
      updateConvectiveCells(dt)
      updateDynamicProvinceMap()
    }
    return
  }

  controls.update()

  // 动态/自定义模式：更新气旋位置和多气旋系统
  if (mode.value === 'dynamic' || mode.value === 'custom') {
    updateCyclones(dt)
    updateConvectiveCells(dt)
    updateDynamicProvinceMap()
    updateCycloneStates()
    // 小图重绘限 5 FPS（原为每帧）
    if (time - lastChartDrawAt >= 200) {
      drawWeatherChart()
      lastChartDrawAt = time
    }
  }

  // 云层漂移（动态模式：沿平均气旋方向整体漂移，模拟风推云走）
  let windOffsetX = 0, windOffsetY = 0
  if (mode.value === 'dynamic' || mode.value === 'custom') {
    const activeCyclones = cyclones.filter(c => c.intensity > 0.1)
    if (activeCyclones.length > 0) {
      const avgMoveDir = activeCyclones.reduce((s, c) => s + c.moveDir, 0) / activeCyclones.length
      const avgPhase = activeCyclones.reduce((s, c) => s + c.phase, 0) / activeCyclones.length
      windOffsetX = (avgPhase * 0.8 + Math.cos(avgMoveDir) * 0.3) % 10
      windOffsetY = (avgPhase * 0.15 + Math.sin(avgMoveDir) * 0.3) % 10
    }
  }

  // 云层 uniforms 更新（Group 递归）
  cloudMeshes.forEach(g => {
    g.children.forEach(m => {
      m.material.uniforms.uTime.value = time * 0.001
      m.material.uniforms.uWeatherTex.value = weatherTex
      m.material.uniforms.uChinaMask.value = chinaMaskTex
      // 动态模式添加风偏移
      if (mode.value === 'dynamic' && m.material.uniforms.uNoiseOffset) {
        const base = m.material.uniforms.uNoiseOffset.value
        if (base) {
          m.material.uniforms.uNoiseOffset.value = new THREE.Vector3(
            base.x + windOffsetX,
            base.y + windOffsetY,
            base.z
          )
        }
      }
    })
  })

  // 天气纹理刷新：动态模式限 5 FPS（原为每帧 2048² 重绘 + 纹理上传），静态模式 2 FPS
  tickCounter++
  if (mode.value === 'dynamic' || mode.value === 'custom') {
    if (time - lastWeatherTexAt >= 200) {
      updateWeatherTex()
      lastWeatherTexAt = time
    }
  } else if (time - lastWeatherTexAt >= 500) {
    updateWeatherTex()
    lastWeatherTexAt = time
  }

  // 雨 & 雷电
  updateRain(dt)
  updateLightning(dt)

  // 标签随相机距离缩放，保持恒定屏幕字号
  updateProvinceLabelScale()

  renderer.render(scene, camera)
}

function onResize() {
  if (!container.value || !renderer) return
  sizeW = container.value.clientWidth
  sizeH = container.value.clientHeight
  renderer.setSize(sizeW, sizeH)
  camera.aspect = sizeW / Math.max(sizeH, 1)
  camera.updateProjectionMatrix()
}

/* ==================== 生命周期 ==================== */
onMounted(() => {
  loadCycloneConfig()  // 加载已保存的气旋配置
  initScene()
  window.addEventListener('resize', onResize)
  updateForecast()
  forecastTimer = setInterval(updateForecast, 5000)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (forecastTimer) clearInterval(forecastTimer)
  if (animationId) cancelAnimationFrame(animationId)
  cloudMeshes.forEach(g => {
    g.children.forEach(m => { m.geometry.dispose(); m.material.dispose() })
  })
  rainSystems.forEach(s => {
    s.points.geometry.dispose(); s.points.material.dispose()
  })
  lightningBolts.forEach(b => {
    b.children.forEach(c => { c.geometry.dispose(); c.material.dispose() })
  })
  provinceSprites.forEach(s => {
    s.sprite.material.map.dispose()
    s.sprite.material.dispose()
  })
  weatherTex?.dispose()
  chinaMaskTex?.dispose()
  chinaMapTex?.dispose()
  terrainTex?.dispose()
  renderer?.dispose()
  if (container.value && renderer) {
    container.value.removeChild(renderer.domElement)
  }
})

watch(() => props.weatherData, updateWeatherTex, { deep: true })
</script>

<style scoped>
.weather3d-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
}

/* ——— 天气图例 ——— */
.weather-legend {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 10;
  background: rgba(10, 15, 30, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 10px 14px;
  min-width: 180px;
  max-width: 220px;
  font-size: 12px;
  color: #d0d4e0;
  backdrop-filter: blur(6px);
  pointer-events: auto;
}
.mode-toggle {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.mode-btn {
  flex: 1;
  padding: 4px 0;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  background: transparent;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn.active {
  background: rgba(64, 158, 255, 0.25);
  color: #409eff;
  border-color: #409eff;
}
.mode-btn:hover:not(.active) {
  color: #bbb;
  border-color: rgba(255, 255, 255, 0.3);
}

/* ——— 手动模式省份面板 ——— */
.manual-panel {
  position: absolute;
  top: 10px;
  right: 240px;
  bottom: 10px;
  z-index: 10;
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
  overflow-y: auto;
  backdrop-filter: blur(6px);
  pointer-events: auto;
  max-width: 320px;
}
.manual-panel::-webkit-scrollbar {
  width: 4px;
}
.manual-panel::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.12);
  border-radius: 2px;
}
.manual-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 4px 8px;
}
.province-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.prov-name {
  font-size: 11px;
  color: #a0b0d0;
  font-weight: 600;
  white-space: nowrap;
}
.prov-select {
  background: rgba(30, 40, 60, 0.8);
  color: #c0d0e0;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  padding: 2px 4px;
  font-size: 10px;
  cursor: pointer;
  outline: none;
}
.prov-select:focus {
  border-color: #409eff;
}
.legend-title {
  font-weight: 700;
  font-size: 13px;
  color: #a0b0d0;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.legend-group {
  margin-bottom: 6px;
}
.legend-group:last-child {
  margin-bottom: 0;
}
.legend-type {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 12px;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.type-thunderstorm .legend-dot {
  background: #ff5555;
  box-shadow: 0 0 8px rgba(255, 85, 85, 0.7);
}
.type-rain_heavy .legend-dot {
  background: #8855cc;
  box-shadow: 0 0 6px rgba(136, 85, 204, 0.6);
}
.type-rain_moderate .legend-dot {
  background: #5577cc;
  box-shadow: 0 0 5px rgba(85, 119, 204, 0.5);
}
.type-rain_light .legend-dot {
  background: #5599cc;
  box-shadow: 0 0 4px rgba(85, 153, 204, 0.4);
}
.type-cloudy .legend-dot {
  background: #9a9ab0;
  box-shadow: 0 0 4px rgba(154, 154, 176, 0.4);
}
.type-sunny .legend-dot {
  background: #f5d76e;
  box-shadow: 0 0 4px rgba(245, 215, 110, 0.5);
}
.legend-label {
  flex: 1;
}
.legend-count {
  color: #6a8aaa;
  font-size: 11px;
}
.legend-provinces {
  color: #8a8da0;
  font-size: 11px;
  margin-top: 2px;
  margin-left: 16px;
  line-height: 1.5;
}

/* ——— 天气情况仪表盘（底部三栏） ——— */
.weather-dashboard {
  position: absolute;
  bottom: 8px;
  left: 8px;
  right: 8px;
  display: flex;
  gap: 8px;
  z-index: 20;
  pointer-events: none;
}
.dash-panel {
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
  backdrop-filter: blur(6px);
  pointer-events: auto;
  overflow-y: auto;
}
.dash-title {
  font-size: 12px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 6px;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 4px;
  flex-shrink: 0;
}
/* 气象卫星小图 */
.dash-chart {
  flex: 0 0 272px;
  max-height: 260px;
}
.dash-canvas {
  width: 260px;
  height: 220px;
  display: block;
  margin: 0 auto;
  border-radius: 4px;
}
/* 省份天气（中间） */
.dash-provinces {
  flex: 1;
  min-width: 200px;
  max-height: none;
}
/* 气旋状态（右侧） */
.dash-cyclones {
  flex: 0 0 210px;
  max-height: 260px;
}
/* 未来 24 小时天气预报 */
.weather-forecast {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 20;
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
  backdrop-filter: blur(6px);
  pointer-events: auto;
  max-width: 620px;
  max-height: 46vh;
  overflow: auto;
  font-size: 12px;
  color: #d0d4e0;
}
.weather-forecast::-webkit-scrollbar { width: 5px; height: 5px; }
.weather-forecast::-webkit-scrollbar-thumb { background: #444; border-radius: 3px; }
.wf-title {
  font-size: 12px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 6px;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 4px;
}
.wf-table {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.wf-row {
  display: grid;
  grid-template-columns: 56px repeat(9, 1fr);
  gap: 3px;
  align-items: center;
}
.wf-cell { text-align: center; }
.wf-prov { text-align: left; color: #8a8da0; white-space: nowrap; }
.wf-time { color: #6a6a8a; font-size: 10px; }
.wf-w {
  height: 16px;
  border-radius: 3px;
  box-shadow: 0 0 4px rgba(0,0,0,0.4);
}
.fw-sunny          { background: #ffcc44; }
.fw-cloudy         { background: #8f93a8; }
.fw-rain_light     { background: #5fa8dd; }
.fw-rain_moderate  { background: #2f7fd0; }
.fw-rain_heavy     { background: #1b4f9c; }
.fw-thunderstorm   { background: #9b59b6; }
.wf-empty {
  color: #6a6a8a;
  text-align: center;
  padding: 10px 0;
}
.province-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.prov-weather-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 20px;
  font-weight: 700;
  color: #d0d8f0;
  cursor: default;
  background: rgba(255,255,255,0.04);
}
.pwi-dot {
  width: 16px; height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
}
.pwi-name { white-space: nowrap; }

/* 天气类型颜色 */
.w-sunny .pwi-dot          { background: #ffcc44; box-shadow: 0 0 8px #ffcc44; }
.w-cloudy .pwi-dot         { background: #a0a4b8; box-shadow: 0 0 6px #a0a4b8; }
.w-rain_light .pwi-dot     { background: #6aaddd; box-shadow: 0 0 6px #6aaddd; }
.w-rain_moderate .pwi-dot  { background: #4488cc; box-shadow: 0 0 6px #4488cc; }
.w-rain_heavy .pwi-dot     { background: #2255aa; box-shadow: 0 0 6px #2255aa; }
.w-thunderstorm .pwi-dot   { background: #cc3344; box-shadow: 0 0 10px #cc3344; animation: dot-flash 0.5s ease-in-out infinite alternate; }

@keyframes dot-flash {
  from { opacity: 1; }
  to   { opacity: 0.35; }
}

/* 省份表图例 */
.prov-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.1);
}
.pl-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  color: #a0a8c0;
}
.pl-dot {
  display: inline-block;
  width: 12px; height: 12px;
  border-radius: 50%;
}
.w-sunny-bg          { background: #ffcc44; }
.w-cloudy-bg         { background: #a0a4b8; }
.w-rain_light-bg     { background: #6aaddd; }
.w-rain_moderate-bg  { background: #4488cc; }
.w-rain_heavy-bg     { background: #2255aa; }
.w-thunderstorm-bg   { background: #cc3344; }

/* ——— 自定义气旋配置面板 ——— */
.cyclone-config-panel {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 10px 14px;
  min-width: 240px;
  max-width: 260px;
  max-height: calc(100% - 20px);
  overflow-y: auto;
  backdrop-filter: blur(6px);
  pointer-events: auto;
  z-index: 25;
  font-size: 12px;
  color: #d0d4e0;
}
.cyclone-config-panel .panel-title {
  font-size: 13px;
  font-weight: bold;
  color: #409eff;
  margin-bottom: 8px;
  text-align: center;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 5px;
}
.cc-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.cc-row label {
  font-weight: 600;
  color: #a0a8b8;
  white-space: nowrap;
}
.cc-row select {
  background: rgba(255,255,255,0.08);
  color: #d0d4e0;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
  padding: 3px 6px;
  font-size: 12px;
}
.cyclone-cards { display: flex; flex-direction: column; gap: 8px; }
.cyclone-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  padding: 8px 10px;
}
.cc-header {
  font-size: 12px;
  font-weight: 700;
  color: #409eff;
  margin-bottom: 6px;
}
.cc-field {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.cc-field label {
  width: 32px;
  font-weight: 600;
  color: #888ca0;
  font-size: 11px;
  white-space: nowrap;
}
.cc-field select {
  flex: 1;
  background: rgba(255,255,255,0.06);
  color: #d0d4e0;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 4px;
  padding: 3px 5px;
  font-size: 11px;
}
.cc-intensity {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}
.cc-intensity input[type="range"] {
  flex: 1;
  height: 16px;
  accent-color: #409eff;
  cursor: pointer;
}
.cc-level-label {
  min-width: 28px;
  font-size: 11px;
  font-weight: 700;
  color: #f0c040;
  text-align: right;
}
.cc-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.08);
}
.cc-btn {
  flex: 1;
  padding: 6px 0;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.2s;
  background: transparent;
}
.cc-btn-save {
  color: #a0b0c0;
  border-color: rgba(160, 176, 192, 0.3);
}
.cc-btn-save:hover { background: rgba(160, 176, 192, 0.1); }
.cc-btn-apply {
  color: #409eff;
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.1);
}
.cc-btn-apply:hover { background: rgba(64, 158, 255, 0.25); }

.cs-cards { display: flex; flex-direction: column; gap: 6px; }
.cs-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  padding: 6px 8px;
}
.cs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.cs-name { font-weight: 700; color: #e0e4f0; font-size: 11px; }
.cs-stage {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
}
.stage-初生, .stage-发展 { background: rgba(100,180,255,0.2); color: #80ccff; }
.stage-增强 { background: rgba(255,200,60,0.2); color: #ffc830; }
.stage-巅峰 { background: rgba(255,100,60,0.25); color: #ff7040; }
.stage-锢囚 { background: rgba(255,50,50,0.25); color: #ff4444; }
.stage-衰减 { background: rgba(160,120,200,0.2); color: #b090d0; }
.stage-消散 { background: rgba(120,120,140,0.2); color: #8888a0; }

.cs-bar-row {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 3px;
}
.cs-bar-label {
  width: 40px;
  font-size: 10px;
  color: #888ca0;
  white-space: nowrap;
}
.cs-bar-track {
  flex: 1;
  height: 6px;
  background: rgba(255,255,255,0.08);
  border-radius: 3px;
  overflow: hidden;
}
.cs-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.bar-ok     { background: linear-gradient(90deg, #409eff, #66ccff); }
.bar-warn   { background: linear-gradient(90deg, #ffa000, #ffcc00); }
.bar-danger { background: linear-gradient(90deg, #ff4040, #ff6640); }
.cs-bar-wear { background: linear-gradient(90deg, #aa6620, #886622); }
.cs-bar-val {
  width: 28px;
  font-size: 10px;
  font-weight: 600;
  text-align: right;
  color: #c0c8e0;
}
.wear-val { color: #cc8830; }
.cs-info-row {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #7880a0;
  margin-bottom: 2px;
}
.cs-pos {
  font-size: 10px;
  color: #687090;
  margin-top: 2px;
}
</style>
