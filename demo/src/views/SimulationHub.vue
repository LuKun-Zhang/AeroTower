<template>
  <div class="sim-hub">
    <!-- 顶部：返回 + 标题 -->
    <div class="hub-header">
      <button class="hub-back" @click="$router.push('/')">← 返回首页</button>
      <h2 class="hub-title">模拟大引擎</h2>
    </div>

    <!-- 模块标签切换 -->
    <div class="hub-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        class="hub-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</div>
    </div>

    <!-- 内容区：三个模拟同时挂载（v-show 保持运行），仅切换可见性 -->
    <div class="hub-body">
      <div v-show="activeTab === 'flight'" class="hub-pane">
        <SimMapView ref="flightPane" :embedded="true" />
      </div>
      <div v-show="activeTab === 'weather'" class="hub-pane">
        <WeatherMap3D ref="weatherMap" :weatherData="{}" :currentTime="''" />
      </div>
      <div v-show="activeTab === 'paxflow'" class="hub-pane">
        <TerminalFlowView ref="paxPane" :embedded="true" />
      </div>
    </div>

    <!-- 底部：统一时钟进度条（始终存在，三页共享同一时间轴） -->
    <div class="hub-clock">
      <div class="hub-clock-controls">
        <button class="cc-btn" @click="togglePlay" :title="playing ? '暂停' : '播放'">
          {{ playing ? '⏸' : '▶' }}
        </button>
        <button class="cc-btn" @click="resetClock" title="重置到起点">⏹</button>
        <span class="cc-label">倍速</span>
        <select class="cc-speed" :value="speed" @change="onSpeedChange">
          <option :value="1">1x</option>
          <option :value="2">2x</option>
          <option :value="5">5x</option>
          <option :value="10">10x</option>
        </select>
        <span class="cc-time">{{ clockText }}</span>
      </div>
      <div class="hub-clock-track" ref="track" @mousedown="onTrackDown">
        <div class="hub-clock-fill" :style="{ width: progress + '%' }"></div>
        <div class="hub-clock-cursor" :style="{ left: progress + '%' }">
          <span class="cursor-time">{{ clockText }}</span>
        </div>
        <div
          v-for="mk in dayMarks" :key="mk.key"
          class="hub-clock-tick" :style="{ left: mk.pct + '%' }"
        ></div>
      </div>
      <div class="hub-clock-scale">
        <div
          v-for="mk in dayMarks" :key="'l' + mk.key"
          class="hub-clock-scale-item" :style="{ left: mk.pct + '%' }"
        >{{ mk.label }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import SimMapView from '@/views/SimMapView'
import WeatherMap3D from '@/components/WeatherMap3D'
import TerminalFlowView from '@/views/TerminalFlowView'
import api from '@/api'

const UNIFIED_MINUTES_PER_SECOND = 5
const CYCLONE_BUSINESS_MINUTES = 7 * 24 * 60   // 10080
const BUSINESS_EPOCH_MINUTES = (29 - 1) * 24 * 60  // 40320 → 2020-11-29 00:00

function formatBusinessTime(absMinutes) {
  const totalDays = Math.floor(absMinutes / 1440)
  const month = 11 + Math.floor(totalDays / 30)
  const day = totalDays % 30 + 1
  const rem = absMinutes % 1440
  const hour = Math.floor(rem / 60)
  const minute = rem % 60
  const p2 = (n) => String(n).padStart(2, '0')
  return `2020-${p2(month)}-${p2(day)} ${p2(hour)}:${p2(minute)}`
}

export default {
  name: 'SimulationHub',
  components: { SimMapView, WeatherMap3D, TerminalFlowView },
  data() {
    return {
      activeTab: 'weather',
      tabs: [
        { key: 'flight', label: '航班模拟' },
        { key: 'weather', label: '天气' },
        { key: 'paxflow', label: '旅客流' },
      ],
      hubPhase: 0,
      playing: true,
      speed: 1,
      clockText: formatBusinessTime(BUSINESS_EPOCH_MINUTES),
      dragging: false,
      _wasPlayingBeforeDrag: false,
      _clockTimer: null,
      _streamTimer: null,
      _lastMoveEmit: 0,
      _lastBackendSync: 0,
    }
  },
  computed: {
    progress() {
      return this.hubPhase * 100
    },
    dayMarks() {
      const marks = []
      for (let d = 0; d <= 7; d++) {
        const abs = BUSINESS_EPOCH_MINUTES + d * 1440
        const totalDays = Math.floor(abs / 1440)
        const month = 11 + Math.floor(totalDays / 30)
        const day = totalDays % 30 + 1
        marks.push({ key: d, pct: (d / 7) * 100, label: `${month}-${day}` })
      }
      return marks
    },
  },
  watch: {
    activeTab() {
      this.$nextTick(() => {
        if (this.activeTab === 'flight' && this.$refs.flightPane && typeof this.$refs.flightPane.onTabActivate === 'function') {
          this.$refs.flightPane.onTabActivate()
        }
        this._broadcastSync()
      })
    },
  },
  mounted() {
    // 统一时钟由天气内部平滑推进，hub 只控制暂停/倍速并读取 phase 展示
    this.$nextTick(() => {
      this._applyPaused()
      this._applySpeed()
    })
    // 天气 stream 自动回传（供后端计算中断，供航班模拟/旅客流消费）
    this._streamTimer = setInterval(() => this._pushStream(), 2000)
    // 统一时钟：定期从天气 phase 读取展示（200ms 刷新进度条）
    this._clockTimer = setInterval(() => this._syncFromWeather(), 200)
    document.addEventListener('mousemove', this.onDocMove)
    document.addEventListener('mouseup', this.onDocUp)
  },
  beforeDestroy() {
    if (this._clockTimer) clearInterval(this._clockTimer)
    if (this._streamTimer) clearInterval(this._streamTimer)
    document.removeEventListener('mousemove', this.onDocMove)
    document.removeEventListener('mouseup', this.onDocUp)
  },
  methods: {
    // 从天气 phase 读取统一时钟显示（天气内部平滑推进气旋运动）
    _syncFromWeather() {
      const wm = this.$refs.weatherMap
      if (!wm || typeof wm.getBusinessClock !== 'function') return
      const clock = wm.getBusinessClock()
      if (clock) {
        this.hubPhase = clock.current_phase || 0
        this.clockText = clock.current_time || this.clockText
        // 航班页显示时间即时跟随统一时钟（轻量，无后端请求）
        this._pushClockToFlightPane()
        // 节流同步后端引擎时间，保证航班起降状态与统一时钟一致
        this._throttledBackendSync()
      }
    },
    _pushClockToFlightPane() {
      const fp = this.$refs.flightPane
      if (fp && typeof fp.setClock === 'function') {
        fp.setClock(this.hubPhase, this.clockText)
      }
    },
    _throttledBackendSync() {
      const now = Date.now()
      if (!this._lastBackendSync || now - this._lastBackendSync > 500) {
        this._lastBackendSync = now
        this._syncBackendTime()
      }
    },
    _syncBackendTime() {
      const fp = this.$refs.flightPane
      if (!fp || !fp.initialized || typeof fp._syncBackend !== 'function') return
      const minutes = BUSINESS_EPOCH_MINUTES + Math.floor(this.hubPhase * CYCLONE_BUSINESS_MINUTES)
      fp._syncBackend(minutes)
    },
    _applyPaused() {
      const wm = this.$refs.weatherMap
      if (wm && typeof wm.setClockPaused === 'function') {
        wm.setClockPaused(!this.playing)
      }
    },
    _applySpeed() {
      const wm = this.$refs.weatherMap
      if (wm && typeof wm.setClockSpeed === 'function') {
        wm.setClockSpeed(this.speed)
      }
    },
    onSpeedChange(e) {
      this.speed = Number(e.target.value)
      this._applySpeed()
    },
    // 时间对齐：把统一时钟广播给航班模拟 / 旅客流（best effort）
    _syncPanes() {
      const relMinutes = Math.floor(this.hubPhase * CYCLONE_BUSINESS_MINUTES)
      const absMinutes = BUSINESS_EPOCH_MINUTES + relMinutes
      if (this.$refs.flightPane && typeof this.$refs.flightPane.syncToClock === 'function') {
        this.$refs.flightPane.syncToClock(this.hubPhase, this.clockText, absMinutes)
      }
      if (this.$refs.paxPane && typeof this.$refs.paxPane.syncToClock === 'function') {
        this.$refs.paxPane.syncToClock(relMinutes)
      }
    },
    // 仅在切换 tab / 拖拽结束 / 重置时对齐一次，避免播放期间高频 jump
    _broadcastSync() {
      this._syncPanes()
    },
    async _pushStream() {
      const wm = this.$refs.weatherMap
      if (!wm) return
      try {
        const clock = wm.getBusinessClock()
        const predicted = wm.predictProvinceTimeline(10080)
        const payload = {
          mode: wm.getMode(),
          province_weather: wm.getCurrentProvinceWeather(),
          clock,
          anchor: predicted.anchor,
          minutes_per_step: predicted.minutes_per_step,
          timeline: predicted.timeline,
        }
        await api.weatherStream(payload)
      } catch (e) {
        // 静默失败
      }
    },
    togglePlay() {
      this.playing = !this.playing
      this._applyPaused()
      this._syncPanesPlayback()
    },
    resetClock() {
      this.playing = false
      this._applyPaused()
      this.hubPhase = 0
      const wm = this.$refs.weatherMap
      if (wm && typeof wm.setClockPhase === 'function') wm.setClockPhase(0)
      this.clockText = formatBusinessTime(BUSINESS_EPOCH_MINUTES)
      this._broadcastSync()
      this._syncPanesPlayback()
    },
    // 播放/暂停 → 同步旅客流运行状态（航班模拟页自身已有起停控制，此处仅旅客流）
    _syncPanesPlayback() {
      if (this.$refs.paxPane && typeof this.$refs.paxPane.setRunning === 'function') {
        this.$refs.paxPane.setRunning(this.playing)
      }
    },
    onTrackDown(e) {
      this.dragging = true
      this._wasPlayingBeforeDrag = this.playing
      // 拖拽期间暂停气旋推进，保证画面停留在拖拽位置供预览
      this.playing = false
      this._applyPaused()
      this._lastMoveEmit = 0
      this.updateFromEvent(e)
      e.preventDefault()
    },
    onDocMove(e) {
      if (!this.dragging) return
      const now = Date.now()
      if (now - this._lastMoveEmit < 60) return
      this._lastMoveEmit = now
      this.updateFromEvent(e)
    },
    onDocUp(e) {
      if (!this.dragging) return
      this.dragging = false
      this.updateFromEvent(e)
      this._broadcastSync()
      // 拖拽结束恢复原播放状态
      if (this._wasPlayingBeforeDrag) {
        this.playing = true
        this._applyPaused()
      }
      this._syncPanesPlayback()
    },
    updateFromEvent(e) {
      const rect = this.$refs.track.getBoundingClientRect()
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
      this.hubPhase = pct
      const wm = this.$refs.weatherMap
      if (wm && typeof wm.setClockPhase === 'function') wm.setClockPhase(pct)
      this.clockText = formatBusinessTime(BUSINESS_EPOCH_MINUTES + Math.floor(pct * CYCLONE_BUSINESS_MINUTES))
    },
  },
}
</script>

<style scoped>
.sim-hub {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: #0a0a1a;
  color: #fff;
}
.hub-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: rgba(10, 15, 30, 0.95);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}
.hub-back {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 4px;
  cursor: pointer;
}
.hub-back:hover { background: rgba(64, 158, 255, 0.2); }
.hub-title { font-size: 16px; font-weight: 700; margin: 0; color: #d0d8f0; }

.hub-tabs {
  display: flex;
  justify-content: center;
  gap: 4px;
  padding: 6px 0;
  flex-shrink: 0;
  background: rgba(10, 15, 30, 0.6);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.hub-tab {
  padding: 5px 22px;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  transition: all 0.2s;
  user-select: none;
}
.hub-tab:hover { background: rgba(255, 255, 255, 0.15); }
.hub-tab.active {
  background: rgba(43, 196, 243, 0.35);
  color: #fff;
  font-weight: bold;
}

.hub-body {
  flex: 1;
  min-height: 0;
  position: relative;
}
.hub-pane {
  position: absolute;
  inset: 0;
}

.hub-clock {
  flex-shrink: 0;
  background: #1e1e2e;
  border-top: 1px solid #313145;
  padding: 26px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hub-clock-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cc-btn {
  background: #2d2d44;
  border: 1px solid #444;
  color: #cdd6f4;
  width: 34px;
  height: 30px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}
.cc-btn:hover { background: #3d3d5c; }
.cc-label { color: #8a8aaa; font-size: 12px; }
.cc-speed {
  background: #2d2d44;
  color: #cdd6f4;
  border: 1px solid #444;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 12px;
}
.cc-time {
  color: #ffd54f;
  font-weight: 700;
  font-size: 14px;
  font-family: 'Courier New', monospace;
  margin-left: auto;
}
.hub-clock-track {
  position: relative;
  height: 10px;
  background: #2d2d44;
  border-radius: 5px;
  cursor: pointer;
}
.hub-clock-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  border-radius: 5px;
  transition: width 0.15s;
}
.hub-clock-cursor {
  position: absolute;
  top: -4px;
  width: 4px;
  height: 18px;
  background: #fff;
  border-radius: 2px;
  margin-left: -2px;
  transition: left 0.15s;
  cursor: ew-resize;
  box-shadow: 0 0 5px rgba(255, 255, 255, 0.6);
}
.hub-clock-cursor .cursor-time {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.85);
  color: #ffd54f;
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 3px;
  white-space: nowrap;
  font-family: 'Courier New', monospace;
  pointer-events: none;
  border: 1px solid rgba(255, 213, 79, 0.35);
}
.hub-clock-tick {
  position: absolute;
  top: 0;
  width: 1px;
  height: 100%;
  background: rgba(255, 255, 255, 0.25);
}
.hub-clock-scale {
  position: relative;
  height: 16px;
}
.hub-clock-scale-item {
  position: absolute;
  transform: translateX(-50%);
  font-size: 11px;
  color: #8a8aaa;
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}
</style>
