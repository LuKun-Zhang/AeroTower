<template>
  <div class="replay-panel">
    <div class="rp-tabs">
      <div v-for="t in tabs" :key="t.key" class="rp-tab"
           :class="{ active: activeTab === t.key }" @click="activeTab = t.key">{{ t.label }}</div>
      <div class="rp-weather-note" v-if="weatherMeta.scenario && weatherMeta.scenario !== 'none'"
           :class="{ clickable: !!weatherMeta.window && !!weatherMeta.window.start }"
           :title="weatherMeta.window && weatherMeta.window.start ? '点击跳转到情景开始前 15 分钟' : ''"
           @click="jumpToScenario">
        情景：{{ weatherLabel }}
        <span v-if="weatherMeta.window"> · {{ weatherMeta.window.start }} ~ {{ weatherMeta.window.end }}</span>
      </div>
    </div>

    <div class="rp-body">
      <div v-show="activeTab === 'flight'" class="rp-pane">
        <SimMapView ref="flightPane" :embedded="true" :readonly="true" />
      </div>
      <div v-show="activeTab === 'weather'" class="rp-pane">
        <WeatherMap3D ref="weatherMap" :weatherData="{}" :currentTime="''" />
      </div>
      <div v-show="activeTab === 'paxflow'" class="rp-pane">
        <TerminalFlowView v-if="hasPaxflow" ref="paxPane" :embedded="true" />
        <div v-else class="rp-empty">本实验无成都场航班，旅客流画面不可用</div>
      </div>
    </div>

    <ReplayClock :progress="progress" :clockText="clockText" :playing="playing"
                 :speed="speed" @toggle="toggle" @reset="reset" @speed="setSpeed" @seek="seek" />
  </div>
</template>

<script>
import SimMapView from '@/views/SimMapView'
import WeatherMap3D from '@/components/WeatherMap3D'
import TerminalFlowView from '@/views/TerminalFlowView'
import ReplayClock from './ReplayClock'
import api from '@/api'

const EPOCH_MINUTES = (29 - 1) * 1440
const CYCLE_MINUTES = 7 * 1440
const MINUTES_PER_SECOND = 5

export default {
  name: 'ReplayPanel',
  components: { SimMapView, WeatherMap3D, TerminalFlowView, ReplayClock },
  props: {
    simStart: { type: Number, required: true },
    simEnd: { type: Number, required: true },
    hasPaxflow: { type: Boolean, default: false },
    weatherMeta: { type: Object, default: () => ({}) },
    initialTab: { type: String, default: 'flight' },
    initialMinutes: { type: Number, default: null },
  },
  data() {
    const raw = Number.isFinite(this.initialMinutes) ? this.initialMinutes : this.simStart
    const start = Math.max(this.simStart, Math.min(raw, this.simEnd))
    const tab = ['flight', 'weather', 'paxflow'].includes(this.initialTab) ? this.initialTab : 'flight'
    return {
      activeTab: tab,
      tabs: [
        { key: 'flight', label: '航班模拟' },
        { key: 'weather', label: '天气' },
        { key: 'paxflow', label: '旅客流' },
      ],
      currentMinutes: start,
      playing: true,
      speed: 1,
      clockText: this.format(start),
      _tickTimer: null,
      _weatherTimer: null,
      _lastSync: 0,
      _provinceNames: null,
      _weatherPinned: false,
    }
  },
  computed: {
    progress() {
      const span = this.simEnd - this.simStart
      if (span <= 0) return 0
      return Math.max(0, Math.min(100, (this.currentMinutes - this.simStart) / span * 100))
    },
    weatherLabel() {
      const map = { sichuan_storm: '四川盆地雷暴', east_rain: '华东强降雨', south_typhoon: '华南台风' }
      return map[this.weatherMeta.scenario] || this.weatherMeta.scenario
    },
  },
  watch: {
    activeTab() {
      this.$nextTick(() => {
        this.applyStaticClock()
        window.dispatchEvent(new Event('resize'))
      })
    },
  },
  mounted() {
    this.$nextTick(() => {
      this.applyStaticClock()
      const wm = this.$refs.weatherMap
      if (wm && wm.setClockPaused) wm.setClockPaused(true)
      this._weatherTimer = setInterval(() => this.pushWeather(), 2000)
      this.pushWeather()
    })
    this._tickTimer = setInterval(() => this.tick(), 200)
  },
  beforeDestroy() {
    if (this._tickTimer) clearInterval(this._tickTimer)
    if (this._weatherTimer) clearInterval(this._weatherTimer)
  },
  methods: {
    format(minutes) {
      const totalDays = Math.floor(minutes / 1440)
      const month = 11 + Math.floor(totalDays / 30)
      const day = totalDays % 30 + 1
      const rem = minutes % 1440
      const p2 = n => String(n).padStart(2, '0')
      return `2020-${p2(month)}-${p2(day)} ${p2(Math.floor(rem / 60))}:${p2(rem % 60)}`
    },
    phase() {
      return ((this.currentMinutes - EPOCH_MINUTES) % CYCLE_MINUTES + CYCLE_MINUTES) % CYCLE_MINUTES / CYCLE_MINUTES
    },
    tick() {
      if (this.playing) {
        this.currentMinutes = Math.min(this.simEnd, this.currentMinutes + this.speed)
        this.clockText = this.format(this.currentMinutes)
        this.applyStaticClock()
        this.syncBackend()
        if (this.currentMinutes >= this.simEnd) this.playing = false
      }
    },
    applyStaticClock() {
      const phase = this.phase()
      const wm = this.$refs.weatherMap
      if (wm && wm.setClockPhase) wm.setClockPhase(phase)
      const fp = this.$refs.flightPane
      if (fp && fp.setClock) fp.setClock(phase, this.clockText)
      const pp = this.$refs.paxPane
      if (pp && pp.syncToClock) pp.syncToClock(this.currentMinutes - EPOCH_MINUTES)
    },
    syncBackend() {
      const now = Date.now()
      if (now - this._lastSync < 500) return
      this._lastSync = now
      api.syncSimTime(this.currentMinutes).catch(() => {})
    },
    async pushWeather() {
      const wm = this.$refs.weatherMap
      if (!wm) return
      try {
        const data = await api.getWeatherDisruption()
        if (!this._provinceNames) {
          this._provinceNames = Object.keys(wm.getCurrentProvinceWeather() || {})
        }
        const map = {}
        this._provinceNames.forEach(p => { map[p] = 'sunny' })
        Object.assign(map, data.province_weather || {})
        if (wm.applyProvinceWeather) {
          // 首次强制切到实验天气，之后尊重用户在天气页选的模式
          const force = !this._weatherPinned
          this._weatherPinned = true
          wm.applyProvinceWeather(map, force)
        }
      } catch (e) {}
    },
    toggle() {
      this.playing = !this.playing
    },
    reset() {
      this.playing = false
      this.currentMinutes = this.simStart
      this.clockText = this.format(this.simStart)
      this.applyStaticClock()
      this.syncBackend()
    },
    setSpeed(v) {
      this.speed = v
      const wm = this.$refs.weatherMap
      if (wm && wm.setClockSpeed) wm.setClockSpeed(v)
    },
    jumpToScenario() {
      const w = this.weatherMeta && this.weatherMeta.window
      if (!w || !w.start) return
      const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(w.start)
      if (!m) return
      const target = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5])
      // 业务分钟以 2020-11-01 00:00 为原点（EPOCH_MINUTES = 28 * 1440）
      const minutes = Math.round((target - Date.UTC(2020, 10, 1, 0, 0)) / 60000)
      this.currentMinutes = Math.max(this.simStart, Math.min(this.simEnd, minutes - 15))
      this.clockText = this.format(this.currentMinutes)
      this.applyStaticClock()
      api.syncSimTime(this.currentMinutes).catch(() => {})
    },

    seek(pct) {
      const span = this.simEnd - this.simStart
      this.currentMinutes = this.simStart + Math.round(span * pct)
      this.clockText = this.format(this.currentMinutes)
      this.applyStaticClock()
      this._lastSync = 0
      this.syncBackend()
    },
  },
}
</script>

<style scoped>
.replay-panel { display: flex; flex-direction: column; background: #0a0a1a; border-radius: 8px; overflow: hidden; }
.rp-tabs {
  display: flex; align-items: center; gap: 4px; padding: 6px 10px;
  background: rgba(10,15,30,0.9); border-bottom: 1px solid rgba(255,255,255,0.06);
}
.rp-tab {
  padding: 4px 16px; font-size: 13px; color: #cdd6f4; cursor: pointer;
  border-radius: 4px; background: rgba(255,255,255,0.08);
}
.rp-tab.active { background: rgba(43,196,243,0.35); font-weight: 500; }
.rp-weather-note.clickable { cursor: pointer; text-decoration: underline dotted; }

.rp-weather-note { margin-left: auto; font-size: 11px; color: #8a8aaa; }
.rp-body { position: relative; height: 560px; overflow: hidden; }
.rp-pane { position: absolute; inset: 0; overflow: hidden; }
.rp-pane ::v-deep .sim-view { min-height: 0; height: 100%; }
.rp-empty { display: flex; align-items: center; justify-content: center; height: 100%; color: #6a6a8a; font-size: 13px; }
</style>
