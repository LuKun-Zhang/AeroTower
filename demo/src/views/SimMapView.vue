<template>
  <div class="sim-view">
    <!-- 时间轴控制条（内嵌模式下隐藏，统一时钟在 hub 底部） -->
    <SimulationTimeline
      v-if="!embedded"
      :running="engineRunning"
      :paused="enginePaused"
      :speed="simSpeed"
      :progress="simProgress"
      :currentTime="simCurrentTime"
      :simStart="simStart"
      :simEnd="simEnd"
      :events="activeEvents"
      @start="onStart"
      @pause="onPause"
      @resume="onResume"
      @stop="onStop"
      @step="onStep"
      @speedChange="onSpeedChange"
      @jump="onJump"
    />

    <!-- 主体：地图 + 侧面板 -->
    <div class="sim-body">
      <div class="sim-map-area" ref="mapArea">
        <!-- 未启动时的遮罩 -->
        <div class="sim-init-overlay" v-if="!engineRunning && !enginePaused">
          <div class="init-center">
            <div class="init-clock" v-if="initialized">{{ simCurrentTime }}</div>
            <div class="init-clock muted" v-else>-- : -- : --</div>
            <button class="init-big-btn" @click="onBigStart" :disabled="loading">
              {{ loading ? '加载中...' : (initialized ? '▶ 继续仿真' : '🚀 启动仿真') }}
            </button>
            <p class="init-hint" v-if="!initialized">点击加载航班数据并开始模拟</p>
            <p class="init-hint" v-else-if="simProgress > 0">仿真已暂停，进度 {{ simProgress.toFixed(1) }}%</p>
          </div>
        </div>

        <!-- 运行中的轻量信息条 -->
        <div class="sim-running-bar" v-if="engineRunning">
          <span class="rb-clock">{{ simCurrentTime }}</span>
          <span class="rb-dot">● {{ statusText }}</span>
        </div>

        <!-- 3D 航班地图 -->
        <FlightMap3D
          v-if="initialized"
          ref="flightMap"
          :flights="flights"
          :currentTime="simCurrentTime"
          :airportList="airportList"
          @flightClick="onFlightClick"
          @flightHover="onFlightHover"
          @instrumentData="onInstrumentData"
        />
      </div>

      <!-- 右侧面板：省份天气实时表 + 事件注入 + 天气航班调整 -->
      <div class="sim-sidebar">
        <ProvinceWeatherPanel />
        <EventInjectPanel
          v-if="initialized"
          :airports="airportList"
          :aircrafts="aircraftList"
          :crewBases="crewBaseList"
          :activeEvents="activeEvents"
          @injectAirport="onInjectAirport"
          @injectCrew="onInjectCrew"
          @injectAircraft="onInjectAircraft"
          @removeEvent="onRemoveEvent"
        />
        <WeatherFlightPanel v-if="initialized" :flights="flights" />
      </div>
    </div>

    <!-- 航班信息浮窗 -->
    <FlightInfoPopup
      :visible="popupVisible"
      :flight="selectedFlight"
      @close="popupVisible = false"
    />

    <!-- 飞行仪表盘 -->
    <FlightInstruments
      :visible="instrumentVisible"
      :data="instrumentData"
      @close="instrumentVisible = false"
    />

    <!-- 底部状态栏 -->
    <div class="sim-status-bar" v-if="initialized">
      <span>航班: {{ flightCount }} 架</span>
      <span>空中: {{ airborneCount }} 架</span>
      <span>延误: {{ delayedCount }} 架</span>
      <span>取消: {{ cancelledCount }} 架</span>
      <span>准点率: {{ punctuality }}%</span>
      <span class="status-right">{{ simCurrentTime }}</span>
    </div>

  </div>
</template>

<script>
import FlightMap3D from '@/components/FlightMap3D'
import SimulationTimeline from '@/components/SimulationTimeline'
import FlightInfoPopup from '@/components/FlightInfoPopup'
import FlightInstruments from '@/components/FlightInstruments'
import EventInjectPanel from '@/components/EventInjectPanel'
import ProvinceWeatherPanel from '@/components/ProvinceWeatherPanel'
import WeatherFlightPanel from '@/components/WeatherFlightPanel'
import api from '@/api/index'

export default {
  name: 'SimMapView',
  components: { FlightMap3D, SimulationTimeline, FlightInfoPopup, FlightInstruments, EventInjectPanel, ProvinceWeatherPanel, WeatherFlightPanel },
  props: {
    // 作为「模拟大引擎」内嵌 tab 时隐藏自身时间轴（统一由 hub 底部时钟驱动）
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      initialized: false,
      loading: false,
      engineRunning: false,
      enginePaused: false,
      simSpeed: 1,
      simProgress: 0,
      simCurrentTime: '--',
      simStart: '--',
      simEnd: '--',
      mapTimeSlot: 0,

      flights: [],
      selectedFlight: {},
      popupVisible: false,
      instrumentVisible: false,
      instrumentData: { speed: 0, heading: 0, altitude: 0, verticalSpeed: 0, pitch: 0, roll: 0, progress: 0 },
      activeEvents: [],
      weatherAll: {},

      airportList: [],
      aircraftList: [],
      crewBaseList: [],

      flightCount: 0,
      airborneCount: 0,
      delayedCount: 0,
      cancelledCount: 0,
      punctuality: 0,

      _pollTimer: null,
    }
  },
  computed: {
    statusText() {
      if (!this.initialized) return '未初始化'
      if (this.enginePaused) return '已暂停'
      if (this.engineRunning) return '运行中'
      return '已停止'
    },
  },
  mounted() {
    // 作为「模拟大引擎」内嵌 tab 时自动开始仿真，无需手动点击
    if (this.embedded) {
      this.$nextTick(() => this.autoStart())
    }
  },
  methods: {
    async autoStart() {
      this.loading = true
      try {
        if (!this.initialized) {
          await api.initSimulation()
          this.initialized = true
          await this.loadContext()
          this.startPolling()
        }
        if (this.embedded) {
          // 内嵌模式：时间由「模拟大引擎」统一时钟驱动，不启动后端独立线程，
          // 避免后端引擎与底部统一时钟各自推进导致时间漂移。
          this.engineRunning = true
          this.enginePaused = false
        } else {
          await api.startSimulation()
          this.engineRunning = true
          this.enginePaused = false
        }
      } catch (e) {
        console.error('自动启动仿真失败:', e)
      } finally {
        this.loading = false
      }
    },

    async onBigStart() {
      this.loading = true
      try {
        if (!this.initialized) {
          await api.initSimulation()
          this.initialized = true
          await this.loadContext()
          this.startPolling()
        }
        await api.startSimulation()
        this.engineRunning = true
        this.enginePaused = false
      } catch (e) {
        console.error('启动失败:', e)
        alert('启动仿真失败: ' + (e.message || '未知错误'))
      } finally {
        this.loading = false
      }
    },

    async loadContext() {
      try {
        const ctx = await api.getSimContext()
        this.airportList = ctx.airports || []
        this.aircraftList = ctx.aircrafts || []
        const bases = ctx.bases || {}
        this.crewBaseList = Object.keys(bases)
      } catch (e) {}
    },

    async onStart() { await this.onBigStart() },
    async onPause() { await api.pauseSimulation(); this.enginePaused = true },
    async onResume() { await api.resumeSimulation(); this.enginePaused = false },
    async onStop() {
      await api.stopSimulation()
      this.engineRunning = false; this.enginePaused = false
    },
    async onStep() {
      try { const snap = await api.stepSimulation(); this._applySnapshot(snap) } catch (e) {}
    },
    async onSpeedChange(speed) { await api.setSimSpeed(speed); this.simSpeed = speed },
    async onJump(pct) {
      try { const snap = await api.jumpSimulation(pct); this._applySnapshot(snap) } catch (e) {}
    },

    async onInjectAirport(p) {
      try { await api.injectAirportAnomaly(p.airport, p.capacity_ratio, p.duration_min); this.fetchEvents() } catch (e) {}
    },
    async onInjectCrew(p) {
      try { await api.injectCrewAbsence(p.crew_names, p.base); this.fetchEvents() } catch (e) {}
    },
    async onInjectAircraft(p) {
      try { await api.injectAircraftFailure(p.tail_no, p.duration_min); this.fetchEvents() } catch (e) {}
    },
    async onRemoveEvent(i) {
      try { await api.removeSimEvent(i); this.fetchEvents() } catch (e) {}
    },
    async fetchEvents() {
      try { const d = await api.getSimEvents(); this.activeEvents = d.active || [] } catch (e) {}
    },

    startPolling() {
      if (this._pollTimer) clearInterval(this._pollTimer)
      this._pollTimer = setInterval(() => this.pollSnapshot(), 500)
    },
    stopPolling() {
      if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null }
    },

    async pollSnapshot() {
      if (!this.initialized) return
      try { const snap = await api.getSimSnapshot(); this._applySnapshot(snap) } catch (e) {}
    },

    _applySnapshot(snap) {
      if (!snap) return
      // 内嵌模式下显示时间/进度由「模拟大引擎」统一时钟驱动，不从后端快照覆盖，
      // 否则后端引擎会与底部统一时钟各自推进导致显示时间不一致。
      if (!this.embedded) {
        this.engineRunning = snap.status === 'running'
        this.enginePaused = snap.status === 'paused'
        this.simSpeed = snap.speed || 1
        this.simProgress = snap.progress_pct || 0
        this.simCurrentTime = snap.current_time || '--'
        this.simStart = snap.sim_start || '--'
        this.simEnd = snap.sim_end || '--'
      }

      const flights = snap.flights || []
      this.flights = flights
      this.flightCount = flights.length
      this.airborneCount = flights.filter(f => f.is_airborne).length
      this.delayedCount = flights.filter(f => f.is_delayed).length
      this.cancelledCount = flights.filter(f => f.is_cancelled).length
      this.punctuality = (snap.kpi || {}).punctuality || 0
      this.activeEvents = snap.events || []
      this.weatherAll = snap.weather || {}
      this.mapTimeSlot = Math.floor(this.simProgress * 6.57)
    },

    onFlightClick(data) {
      if (!data) return
      // 如果是机场点击
      if (data.airport) return
      // 优先使用原始数据，合并转换后的字段
      var raw = data._raw || data
      this.selectedFlight = Object.assign({}, raw, {
        flight_no: data.flightNo || raw.flight_no || '',
        departure_airport: data.depCity || raw.departure_airport || '',
        arrival_airport: data.arrCity || raw.arrival_airport || '',
        progress: data.progress != null ? Math.round(data.progress * 100) : (raw.progress || 0),
        phase: data.status || raw.phase || 'flying',
      })
      this.popupVisible = true
      this.instrumentVisible = true  // 同时显示仪表盘
    },

    onInstrumentData(data) {
      this.instrumentData = data
    },

    onFlightHover(data) {
      // 悬停时暂不处理，保留扩展接口
    },

    // 统一时钟对齐（由「模拟大引擎」调用：先更新显示时间，再按绝对分钟同步后端引擎）
    setClock(phase, clockText) {
      if (!this.initialized) return
      this.simCurrentTime = clockText
      this.simProgress = phase * 100
    },

    syncToClock(phase, clockText, absoluteMinutes) {
      if (!this.initialized || this.loading) return
      this.setClock(phase, clockText)
      this._syncBackend(absoluteMinutes)
    },

    async _syncBackend(absoluteMinutes) {
      if (absoluteMinutes == null) return
      try {
        const snap = await api.syncSimTime(absoluteMinutes)
        this._applySnapshot(snap)
      } catch (e) {}
    },

    // 供「模拟大引擎」直接注入已同步的快照（避免重复轮询）
    applySnapshot(snap) {
      this._applySnapshot(snap)
    },

    // 从其他 tab 切换回来时重新校正 3D 地图画布尺寸（v-show 下 display:none 会令初始尺寸为 0）
    onTabActivate() {
      this.$nextTick(() => {
        if (this.$refs.flightMap && typeof this.$refs.flightMap._onResize === 'function') {
          this.$refs.flightMap._onResize()
        }
      })
    },
  },

  beforeDestroy() { this.stopPolling() },
}
</script>

<style scoped>
.sim-view {
  display: flex; flex-direction: column; height: 100%; width: 100%; min-height: 100vh;
}
.sim-body {
  flex: 1; display: flex; position: relative; overflow: hidden; min-height: 280px;
}
.sim-map-area { flex: 1; position: relative; min-width: 0; }

/* 未启动遮罩 */
.sim-init-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(10, 10, 26, 0.88); z-index: 100;
}
.init-center { text-align: center; }
.init-clock {
  font-size: 52px; font-weight: 700; color: #409eff; font-family: 'Courier New', monospace;
  margin-bottom: 20px; letter-spacing: 4px;
}
.init-clock.muted { color: #555; }
.init-big-btn {
  padding: 14px 48px; font-size: 20px;
  background: #409eff; color: #fff; border: none; border-radius: 10px;
  cursor: pointer; transition: all 0.2s; font-weight: 600;
}
.init-big-btn:hover { background: #66b1ff; transform: scale(1.03); }
.init-big-btn:disabled { background: #555; cursor: not-allowed; transform: none; }
.init-hint { color: #6a6a8a; margin-top: 12px; font-size: 13px; }

/* 运行中时钟条 */
.sim-running-bar {
  position: absolute; top: 6px; left: 50%; transform: translateX(-50%); z-index: 50;
  background: rgba(0,0,0,0.6); border-radius: 6px; padding: 4px 16px;
  display: flex; align-items: center; gap: 12px;
}
.rb-clock {
  font-size: 18px; font-weight: 700; color: #409eff; font-family: 'Courier New', monospace;
}
.rb-dot { font-size: 12px; color: #4caf50; }

.sim-sidebar {
  width: 250px; position: relative; background: rgba(10, 10, 26, 0.9);
  border-left: 1px solid #313145; overflow-y: auto;
  padding: 8px; box-sizing: border-box;
  display: flex; flex-direction: column; gap: 8px;
}
.sim-status-bar {
  display: flex; gap: 20px; padding: 4px 16px; background: #1a1a2e;
  border-top: 1px solid #313145; font-size: 12px; color: #8a8aaa;
}
.sim-status-bar span { white-space: nowrap; }
.status-right { margin-left: auto; color: #cdd6f4; font-weight: 600; }
</style>
