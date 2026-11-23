<template>
  <div class="paxflow-page">
    <div class="paxflow-header">
      <button class="back-btn" @click="$router.push('/')">← 返回首页</button>
      <h2 class="page-title">成都双流机场 · 旅客流模拟</h2>
      <div class="date-picker">
        <button class="date-btn" @click="onPrevDay" :disabled="dateIndex <= 0">◀</button>
        <select class="date-select" :value="currentDate" @change="onDateChange($event.target.value)">
          <option v-for="d in dates" :key="d" :value="d">{{ formatDate(d) }}</option>
        </select>
        <button class="date-btn" @click="onNextDay" :disabled="dateIndex >= dates.length - 1">▶</button>
      </div>
      <div class="header-right">
        <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
        <button class="taxi-toggle" @click="toggleTaxiPaths">
          {{ showTaxiPaths ? '🔴 隐藏路径' : '⚪ 显示路径' }}
        </button>
        <span class="header-stat" v-if="paxCount > 0">旅客: {{ paxCount }}</span>
        <span class="header-stat" v-if="planeCount > 0">飞机: {{ planeCount }}</span>
        <span class="header-stat" v-if="simTime > 0">{{ formatTime(simTime) }}</span>
        <span class="header-hint">绿色: 入港 · 橙色: 离港 · 红色: 中转</span>
      </div>
    </div>

    <div class="paxflow-body">
      <div class="layout-area">
        <TerminalLayout ref="layout" @day-complete="onDayComplete" />
      </div>

      <div class="side-panels">
        <ProvinceWeatherPanel />
        <PassengerControlPanel
          :paxParams="paxParams"
          @update="onPaxUpdate"
          @reset="onPaxReset"
        />
        <PaxStatusQuery
          :query-fn="queryPaxStatus"
          :flights="simFlights"
        />
        <FlightBoard
          :flights="simFlights"
          :simTime="simTime"
          @selectFlight="onSelectFlight"
        />
        <GateControlPanel
          :entryGates="entryGates"
          :exitGates="exitGates"
          :boardingGates="boardingGates"
          :gateStates="gateStates"
          :corridorList="corridorControlList"
          @toggleGate="onToggleGate"
          @toggleCorridor="onToggleCorridor"
          @setAllGates="onSetAllGates"
        />
        <CongestionHeatmap
          :enabled="heatmapEnabled"
          :levels="congestionLevels"
          @toggle="onToggleHeatmap"
        />
        <EvacuationPanel
          :active="evacuationActive"
          :totalEvacuating="evacuationTotal"
          :totalArrived="evacuationArrived"
          :exitGates="exitGateNames"
          :availableExits="availableExits"
          @start="onStartEvacuation"
          @stop="onStopEvacuation"
        />
      </div>
    </div>

    <div class="bottom-bar" v-if="!embedded">
      <SimulationTimeline
        :running="simRunning"
        :paused="simPaused"
        :speed="simSpeed"
        :progress="simProgress"
        :currentTime="formatTime(simTime)"
        :simStart="'00:00'"
        :simEnd="'24:00'"
        :totalMinutes="1440"
        :events="timelineEvents"
        @start="onStart"
        @pause="onPause"
        @resume="onResume"
        @stop="onStop"
        @speedChange="onSpeedChange"
        @step="onStep"
        @jump="onJump"
      />
    </div>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="旅客流模拟" />
  </div>
</template>

<script>
import TerminalLayout from '@/components/TerminalLayout'
import SimulationTimeline from '@/components/SimulationTimeline'
import PassengerControlPanel from '@/components/PassengerControlPanel'
import PaxStatusQuery from '@/components/PaxStatusQuery'
import FlightBoard from '@/components/FlightBoard'
import GateControlPanel from '@/components/GateControlPanel'
import CongestionHeatmap from '@/components/CongestionHeatmap'
import EvacuationPanel from '@/components/EvacuationPanel'
import ProvinceWeatherPanel from '@/components/ProvinceWeatherPanel'
import ChartOverlay from '@/components/ChartOverlay'
import { buildTerminalFlowCharts } from '@/utils/charts/terminalFlow'
import { SCHEDULE_DATES } from '@/data/multiDaySchedule'

const DEFAULT_PAX_PARAMS = {
  inboundRate: 10,
  outboundRate: 6,
  transitRatio: 0.05,
  loadFactor: 0.78,
}

export default {
  name: 'TerminalFlowView',
  components: {
    TerminalLayout,
    SimulationTimeline,
    PassengerControlPanel,
    PaxStatusQuery,
    FlightBoard,
    GateControlPanel,
    CongestionHeatmap,
    EvacuationPanel,
    ProvinceWeatherPanel,
    ChartOverlay,
  },
  props: {
    // 作为「模拟大引擎」内嵌 tab 时隐藏自身底部时间轴（统一由 hub 底部时钟驱动）
    embedded: { type: Boolean, default: false },
  },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      paxParams: { ...DEFAULT_PAX_PARAMS },
      heatmapEnabled: false,
      // 从 TerminalLayout 轮询同步的数据（$refs 不响应式，必须轮询）
      simRunning: false,
      simPaused: false,
      simSpeed: 1,
      simTime: 0,
      simFlights: [],
      paxCount: 0,
      planeCount: 0,
      gateStates: {},
      entryGates: [],
      exitGates: [],
      boardingGates: [],
      exitGateNames: [],
      congestionLevels: [],
      evacuationActive: false,
      evacuationTotal: 0,
      evacuationArrived: 0,
      availableExits: [],
      corridorControlList: [],
      showTaxiPaths: true,
      currentDate: SCHEDULE_DATES[0] || '2020-11-30',
      // 后端 /api/paxflow/schedule 返回的真实航班日期（TerminalLayout 加载后轮询同步）
      paxflowDates: [],
      _pollTimer: null,
      _speedSynced: false,
    }
  },
  mounted() {
    // 轮询同步 TerminalLayout 状态到本地 data（Vue 2 $refs 不是响应式的）
    this._pollTimer = setInterval(() => this.pollLayout(), 200)
    // 主动拉取后端真实航班日期（保证下拉框始终含最早日期如 11-29，
    // 不依赖 TerminalLayout 的异步加载/HMR 状态，后端日期不可用时回退静态快照）
    this.loadBackendDates()
  },
  beforeDestroy() {
    if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null }
  },
  computed: {
    // 日期列表：优先用后端真实航班日期（如 11-29 起），后端未加载时回退静态快照
    dates() {
      const ds = this.paxflowDates || []
      return ds.length ? ds : SCHEDULE_DATES
    },
    dateIndex() {
      const ds = this.dates
      const i = ds.indexOf(this.currentDate)
      return i < 0 ? 0 : i
    },
    // 模拟总时长：一天 24h = 1440 分钟（末班航班可能延后到下客完成，进度条封顶 100%）
    simProgress() {
      const L = this.$refs.layout
      const total = (L && L.simTotalMinutes) || 1440
      return Math.min((this.simTime / total) * 100, 100)
    },
    // 底部进度栏上的航班事件（起飞/降落），按真实调度时刻定位到进度条
    timelineEvents() {
      const L = this.$refs.layout
      const total = (L && L.simTotalMinutes) || 1440
      return this.simFlights
        .map(f => {
          if (f.type === 'departure') {
            const t = f.takeoffTime || f.boardingEnd || 0
            return {
              label: `${f.flightNo} 起飞 ${this.formatTime(t)} · ${f.runway || '跑道'}`,
              pct: (t / total) * 100,
              type: 'takeoff',
            }
          }
          const t = f.scheduledArr || 0
          return {
            label: `${f.flightNo} 降落 ${this.formatTime(t)} · ${f.runway || '跑道'}`,
            pct: (t / total) * 100,
            type: 'landing',
          }
        })
        .filter(e => e.pct > 0)
        .sort((a, b) => a.pct - b.pct)
    },
  },
  methods: {
    openCharts() {
      this.chartList = buildTerminalFlowCharts(this)
      this.chartsOpen = true
    },

    // 直接拉取后端 /api/paxflow/schedule 的日期列表（仅用 dates 字段），
    // 使日期下拉框确定性展示最近历史记录的真实航班日期（含 11-29）。
    async loadBackendDates() {
      try {
        const res = await fetch('/api/paxflow/schedule')
        const json = await res.json()
        if (json.code === 0 && json.data && json.data.dates && json.data.dates.length) {
          this.paxflowDates = json.data.dates
          console.log('[PaxFlow] 日期列表已加载(独立拉取): ' + this.paxflowDates.join(', '))
        } else {
          console.warn('[PaxFlow] 后端日期为空，使用静态快照', json)
        }
      } catch (e) {
        console.warn('[PaxFlow] 后端日期拉取失败，使用静态快照:', e.message)
      }
    },

    pollLayout() {
      const L = this.$refs.layout
      if (!L) return
      // 嵌入模式：后端调度加载完成后，一次性把旅客流速度对齐到统一时钟
      // （5 业务分钟/秒 ≈ speed 5），保证日常播放与天气/航班模拟速度一致
      if (this.embedded && !this._speedSynced && L.paxflowDates && L.paxflowDates.length) {
        this._speedSynced = true
        if (typeof L.setSpeed === 'function') L.setSpeed(5)
      }
      this.simRunning = L.simState.running
      this.simPaused = L.simState.paused
      this.simSpeed = L.simState.speed
      this.simTime = L.simState.currentTime
      this.simFlights = L.simFlights ? [...L.simFlights] : []
      this.paxCount = L.passengers ? L.passengers.length : 0
      this.planeCount = L.airplanes ? L.airplanes.length : 0
      this.gateStates = { ...L.gateStates }
      this.entryGates = L.entryGates ? [...L.entryGates] : []
      this.exitGates = L.exitGates ? [...L.exitGates] : []
      this.boardingGates = L.boardingGates ? [...L.boardingGates] : []
      this.exitGateNames = L.exitGates ? L.exitGates.map(g => g.name) : []
      this.congestionLevels = L.congestion && L.congestion.levels ? [...L.congestion.levels] : []
      this.evacuationActive = L.evacuation ? L.evacuation.active : false
      this.evacuationTotal = L.evacuation ? L.evacuation.totalEvacuating : 0
      this.evacuationArrived = L.evacuation ? L.evacuation.totalArrived : 0
      this.availableExits = L.evacuation ? [...L.evacuation.availableExits] : []

      // 走廊列表
      const rc = L.routeCorridors || []
      const list = []
      const seen = new Set()
      for (let i = 0; i < rc.length; i++) {
        const r = rc[i]
        let label = r.label || r.routeType || ('走廊#' + i)
        if (seen.has(label)) label = label + ' #' + i
        seen.add(label)
        list.push({ idx: i, label, blocked: false })
      }
      this.corridorControlList = list
      this.currentDate = L.currentDate || this.currentDate
      // 同步后端航班日期列表（有真实数据时优先展示，静态快照作为兜底）
      if (L.paxflowDates && L.paxflowDates.length) {
        this.paxflowDates = L.paxflowDates
      }
    },

    formatTime(min) {
      const h = Math.floor(min / 60) % 24
      const m = Math.floor(min % 60)
      return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0')
    },

    // 日期显示："2020-11-30" → "11-30 周日"
    formatDate(d) {
      const [, m, day] = d.split('-')
      const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][new Date(d + 'T00:00:00').getDay()]
      return `${m}-${day} ${week}`
    },

    onDateChange(date) {
      if (!this.$refs.layout || date === this.currentDate) return
      this.$refs.layout.setDate(date)
    },
    onPrevDay() {
      const i = this.dateIndex
      if (i > 0) this.onDateChange(this.dates[i - 1])
    },
    onNextDay() {
      const i = this.dateIndex
      if (i >= 0 && i < this.dates.length - 1) this.onDateChange(this.dates[i + 1])
    },

    // 当天播放完成 → 自动切换到下一天继续播放
    onDayComplete() {
      const i = this.dateIndex
      const next = this.dates[i + 1]
      if (next && this.$refs.layout) {
        this.$refs.layout.setDate(next)
      } else {
        this.onStop()
      }
    },

    onStart() { if (this.$refs.layout) this.$refs.layout.startSimulation() },
    onPause() { if (this.$refs.layout) this.$refs.layout.pauseSimulation() },
    onResume() { if (this.$refs.layout) this.$refs.layout.resumeSimulation() },
    onStop() { if (this.$refs.layout) this.$refs.layout.stopSimulation() },
    // 统一时钟播放/暂停 → 同步旅客流运行状态（嵌入模式）
    setRunning(running) {
      if (this.$refs.layout) this.$refs.layout.setRunning(running)
    },
    onStep() { if (this.$refs.layout) this.$refs.layout.simTick() },
    onSpeedChange(speed) { if (this.$refs.layout) this.$refs.layout.setSpeed(speed) },
    // 拖动进度条：换算成目标分钟数后异步逐 tick 快进到该时刻
    // 异步分批快进避免阻塞渲染（飞机画面不会冻结），await 等待完成后再同步进度
    async onJump(pct) {
      console.log('[PaxFlow] onJump pct=' + pct + ' layout=' + !!this.$refs.layout)
      if (!this.$refs.layout) {
        console.warn('[PaxFlow] layout ref 为空，无法调用 jumpToTime')
        return
      }
      // 防止快速连续拖拽时多次 jumpToTime 并发运行（上一次未结束则直接覆盖目标）
      const total = this.$refs.layout.simTotalMinutes || 1020
      const target = Math.round((pct / 100) * total)
      this._jumpTarget = target
      if (this._jumping) {
        console.log('[PaxFlow] 上次跳转未完成，更新目标=' + target + '，本次调用将忽略')
        return
      }
      this._jumping = true
      try {
        // 用局部变量跟踪最新目标，跳转过程中持续拖拽时 @jump 会更新 _jumpTarget
        while (this._jumpTarget !== undefined) {
          const tgt = this._jumpTarget
          this._jumpTarget = undefined
          try {
            await this.$refs.layout.jumpToTime(tgt)
          } catch (e) {
            console.error('[PaxFlow] jumpToTime 异常:', e)
          }
        }
      } finally {
        this._jumping = false
        this.pollLayout()
        this.$nextTick(() => {
          if (this.$refs.layout) {
            this.simTime = this.$refs.layout.simState.currentTime
          }
        })
      }
    },

    onPaxUpdate(params) {
      this.paxParams = params
      if (this.$refs.layout) Object.assign(this.$refs.layout.paxParams, params)
    },
    onPaxReset() {
      this.paxParams = { ...DEFAULT_PAX_PARAMS }
      if (this.$refs.layout) Object.assign(this.$refs.layout.paxParams, DEFAULT_PAX_PARAMS)
    },

    onSelectFlight(flight) {
      console.log('Selected flight:', flight.flightNo, 'at gate:', flight.gateName)
    },

    // 查询乘客粒子状态（透传给 PaxStatusQuery 组件）
    queryPaxStatus(flightNo, paxNo) {
      const L = this.$refs.layout
      return L && typeof L.getPaxStatus === 'function'
        ? L.getPaxStatus(flightNo, paxNo)
        : { status: 'unknown', statusText: '模拟未就绪' }
    },

    onToggleGate(gateName) {
      if (!this.$refs.layout) return
      const gs = this.$refs.layout.gateStates[gateName]
      this.$refs.layout.setGateStatus(gateName, (gs && gs.status === 'open') ? 'closed' : 'open')
    },
    onToggleCorridor(idx, blocked) {
      if (this.$refs.layout) this.$refs.layout.setCorridorBlocked(idx, blocked)
    },
    onSetAllGates(status) {
      if (this.$refs.layout) this.$refs.layout.setAllGatesStatus(status)
    },

    toggleTaxiPaths() {
      this.showTaxiPaths = !this.showTaxiPaths
      if (this.$refs.layout) this.$refs.layout.showTaxiPaths = this.showTaxiPaths
    },

    onToggleHeatmap() {
      this.heatmapEnabled = !this.heatmapEnabled
      if (this.$refs.layout) {
        this.$refs.layout.congestion.enabled = this.heatmapEnabled
        if (!this.heatmapEnabled) this.$refs.layout.congestion.levels = []
      }
    },

    onStartEvacuation(targetArea) {
      if (this.$refs.layout) this.$refs.layout.startEvacuation(targetArea)
    },
    onStopEvacuation() {
      if (this.$refs.layout) this.$refs.layout.stopEvacuation()
    },

    // 统一时钟对齐（由「模拟大引擎」在切换 tab / 拖拽结束时调用一次）
    // minutes = 统一时钟业务分钟（自 2020-11-29 00:00 起，0~10080）
    syncToClock(minutes) {
      const ds = this.dates
      if (!ds.length || !this.$refs.layout) return
      const dayIndex = Math.min(Math.floor(minutes / 1440), ds.length - 1)
      const date = ds[dayIndex]
      const minuteInDay = Math.min(minutes % 1440, 1439)
      const L = this.$refs.layout
      if (this.embedded) {
        // 嵌入模式：旅客流时间速度与统一时钟保持一致（5 业务分钟/秒 ≈ speed 5），
        // 并保持播放状态，避免跳转后 running=false 导致飞机“到点不动”
        L.setSpeed(5)
        L.setRunning(true)
      }
      if (date && date !== this.currentDate) {
        L.setDate(date)
        this.currentDate = date
      }
      L.jumpToTime(minuteInDay)
    },
  },
}
</script>

<style scoped>
.paxflow-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: #1a1a2e;
}

.paxflow-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: rgba(10, 15, 30, 0.92);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  z-index: 100;
  flex-shrink: 0;
}

.back-btn {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
.back-btn:hover { background: rgba(64, 158, 255, 0.2); }

.page-title {
  color: #fff;
  font-size: 16px;
  margin: 0;
  font-weight: 600;
}

.date-picker {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 8px;
}
.date-btn {
  padding: 4px 10px;
  font-size: 13px;
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
}
.date-btn:disabled {
  color: #555;
  background: rgba(255, 255, 255, 0.03);
  border-color: #333;
  cursor: not-allowed;
}
.date-select {
  padding: 4px 6px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: rgba(20, 28, 48, 0.95);
  border: 1px solid rgba(64, 158, 255, 0.4);
  border-radius: 4px;
  cursor: pointer;
  outline: none;
}
.date-select option { background: #141c30; color: #fff; }

.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}
.header-stat {
  color: #409eff;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
}
.header-hint { color: #8a8aaa; font-size: 12px; }

.paxflow-body { flex: 1; display: flex; min-height: 0; }
.layout-area { flex: 1; min-width: 0; position: relative; }

.side-panels {
  width: 260px;
  flex-shrink: 0;
  overflow-y: auto;
  padding: 6px;
  background: rgba(10, 15, 30, 0.6);
  border-left: 1px solid #313145;
}
.side-panels::-webkit-scrollbar { width: 4px; }
.side-panels::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }

.bottom-bar { flex-shrink: 0; border-top: 1px solid #313145; }
</style>
