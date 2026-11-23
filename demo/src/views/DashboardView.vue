<template>
  <div class="sim-dashboard">
    <div class="dash-header" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
      <h1 style="margin:0">仿真运营仪表盘</h1>
      <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
    </div>

    <!-- KPI 卡片 -->
    <div class="kpi-cards">
      <div class="kpi-card" :class="kpiClass(kpi.punctuality, 70, 85)">
        <div class="kpi-icon">&#9989;</div>
        <div class="kpi-value">{{ kpi.punctuality }}<small>%</small></div>
        <div class="kpi-label">准点率</div>
      </div>
      <div class="kpi-card" :class="kpiClass(kpi.completion_rate, 50, 80)">
        <div class="kpi-icon">&#128640;</div>
        <div class="kpi-value">{{ kpi.completion_rate }}<small>%</small></div>
        <div class="kpi-label">完成率</div>
      </div>
      <div class="kpi-card normal">
        <div class="kpi-icon">&#9992;</div>
        <div class="kpi-value">{{ kpi.airborne_count }}</div>
        <div class="kpi-label">空中航班</div>
      </div>
      <div class="kpi-card" :class="kpiClass(100 - kpi.delayed_count, 50, 20)">
        <div class="kpi-icon">&#9200;</div>
        <div class="kpi-value">{{ kpi.delayed_count }}</div>
        <div class="kpi-label">延误航班</div>
      </div>
      <div class="kpi-card" :class="kpiClass(100 - kpi.cancelled_count, 30, 10)">
        <div class="kpi-icon">&#10060;</div>
        <div class="kpi-value">{{ kpi.cancelled_count }}</div>
        <div class="kpi-label">取消航班</div>
      </div>
      <div class="kpi-card normal">
        <div class="kpi-icon">&#128101;</div>
        <div class="kpi-value">{{ kpi.total_passengers }}</div>
        <div class="kpi-label">在途旅客</div>
      </div>
      <div class="kpi-card warning">
        <div class="kpi-icon">&#9888;</div>
        <div class="kpi-value">{{ kpi.delayed_passengers }}</div>
        <div class="kpi-label">延误旅客</div>
      </div>
      <div class="kpi-card" :class="kpi.active_events > 0 ? 'danger' : 'good'">
        <div class="kpi-icon">&#9889;</div>
        <div class="kpi-value">{{ kpi.active_events }}</div>
        <div class="kpi-label">活跃异常</div>
      </div>
    </div>

    <!-- 延误趋势 + 天气 -->
    <div class="mid-row">
      <div class="panel chart-panel">
        <h3>航班状态趋势</h3>
        <div class="bar-chart-sim">
          <div class="bar-item" v-for="(d, i) in trendData" :key="i">
            <div class="bar-label">{{ i }}</div>
            <div class="bars-stacked">
              <div class="bar-seg seg-normal" :style="barSeg(d.normal)"></div>
              <div class="bar-seg seg-delayed" :style="barOffset(d.normal, d.delayed)"></div>
              <div class="bar-seg seg-cancelled" :style="barOffset(d.normal + d.delayed, d.cancelled)"></div>
            </div>
            <span class="bar-total">{{ d.normal + d.delayed + d.cancelled }}</span>
          </div>
        </div>
        <div class="legend">
          <span class="leg-item"><i class="leg-dot dot-normal"></i> 正常</span>
          <span class="leg-item"><i class="leg-dot dot-delayed"></i> 延误</span>
          <span class="leg-item"><i class="leg-dot dot-cancelled"></i> 取消</span>
        </div>
      </div>

      <div class="panel weather-panel">
        <h3>天气小地图</h3>
        <div class="weather-grid" v-if="weatherList.length">
          <div class="weather-card" v-for="w in weatherList" :key="w.airport"
               :class="{ disrupted: w.is_disrupted }">
            <span class="w-icon">{{ w.icon }}</span>
            <span class="w-ap">{{ w.airport }}</span>
            <span class="w-type">{{ w.label }}</span>
            <span class="w-vis">{{ w.visibility_m }}m</span>
            <span class="w-wind">{{ w.wind_ms }}m/s</span>
          </div>
        </div>
        <div v-else class="no-data">天气数据加载中...</div>
      </div>
    </div>

    <!-- 当前仿真时间 -->
    <div class="sim-time-bar">
      <span class="time-label">仿真时间</span>
      <span class="time-value">{{ simTime }}</span>
      <span class="time-pct">{{ simProgress }}%</span>
    </div>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="总览" />
  </div>
</template>

<script>
import api from '@/api'
import ChartOverlay from '@/components/ChartOverlay'
import { buildDashboardCharts } from '@/utils/charts/dashboardView'

export default {
  name: 'SimDashboard',
  components: { ChartOverlay },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      simTime: '--',
      simProgress: 0,
      kpi: {
        punctuality: 0, completion_rate: 0, airborne_count: 0,
        delayed_count: 0, cancelled_count: 0, total_passengers: 0,
        delayed_passengers: 0, avg_delay: 0, active_events: 0,
      },
      weatherList: [],
      trendData: [], // 每小时的正常/延误/取消
      allFlights: [],
      _pollTimer: null,
    }
  },
  methods: {
    openCharts() {
      this.chartList = buildDashboardCharts(this)
      this.chartsOpen = true
    },
    kpiClass(val, warn, crit) {
      if (val <= crit) return 'danger'
      if (val <= warn) return 'warning'
      return 'good'
    },

    barSeg(val) {
      const max = Math.max(...this.trendData.map(d => d.normal + d.delayed + d.cancelled), 1)
      return { width: (val / max * 100) + '%' }
    },
    barOffset(base, val) {
      const max = Math.max(...this.trendData.map(d => d.normal + d.delayed + d.cancelled), 1)
      return { width: (val / max * 100) + '%', left: (base / max * 100) + '%' }
    },

    async loadSnapshot() {
      try {
        const snap = await api.getSimSnapshot()
        if (snap) {
          this.simTime = snap.current_time || '--'
          this.simProgress = snap.progress_pct || 0
          this.kpi = snap.kpi || this.kpi

          // 天气
          const wObj = snap.weather || {}
          this.weatherList = Object.values(wObj).slice(0, 12)

          // 构建趋势
          this.allFlights = snap.flights || []
          this.buildTrend()
        }
      } catch (e) {
        // 仿真可能未初始化，静默
      }
    },

    buildTrend() {
      const hours = {}
      for (const f of this.allFlights) {
        if (!f.scheduled_dep || !Array.isArray(f.scheduled_dep)) continue
        const h = f.scheduled_dep[3] || 0
        const key = `${String(h).padStart(2, '0')}:00`
        if (!hours[key]) hours[key] = { normal: 0, delayed: 0, cancelled: 0 }
        if (f.is_cancelled) hours[key].cancelled++
        else if (f.is_delayed || f.delay_minutes > 0) hours[key].delayed++
        else hours[key].normal++
      }

      const keys = Object.keys(hours).sort()
      this.trendData = keys.map(k => hours[k])
    },

    startPolling() {
      if (this._pollTimer) clearInterval(this._pollTimer)
      this._pollTimer = setInterval(() => this.loadSnapshot(), 1500)
      this.loadSnapshot()
    },
    stopPolling() {
      if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null }
    },
  },
  mounted() {
    this.startPolling()
  },
  beforeDestroy() {
    this.stopPolling()
  },
}
</script>

<style scoped>
.sim-dashboard {
  padding: 16px 20px;
  color: #ccc;
  flex: 1;
  height: 100%;
  overflow-y: auto;
}
h1 { font-size: 20px; margin: 0 0 14px; color: #f5d0a9; }

/* KPI cards */
.kpi-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.kpi-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  padding: 14px;
  text-align: center;
  transition: border-color 0.3s;
}
.kpi-card.good { border-color: rgba(76, 175, 80, 0.4); }
.kpi-card.warning { border-color: rgba(255, 152, 0, 0.4); }
.kpi-card.danger { border-color: rgba(244, 67, 54, 0.4); }
.kpi-card.normal { border-color: rgba(64, 158, 255, 0.4); }
.kpi-icon { font-size: 20px; margin-bottom: 6px; }
.kpi-value { font-size: 28px; font-weight: bold; color: #f5d0a9; }
.kpi-value small { font-size: 50%; color: #888; }
.kpi-label { font-size: 11px; color: #888; margin-top: 2px; }

/* Mid row */
.mid-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.panel {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 12px 14px;
}
.panel h3 { font-size: 13px; margin: 0 0 10px; color: #aaa; }

/* Stacked bar */
.bar-chart-sim { max-height: 180px; overflow-y: auto; }
.bar-item { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.bar-label { font-size: 10px; color: #777; min-width: 32px; }
.bars-stacked { flex: 1; height: 14px; background: rgba(255,255,255,0.04); border-radius: 2px; position: relative; }
.bar-seg { position: absolute; top: 0; height: 100%; border-radius: 2px; }
.seg-normal { background: #4caf50; }
.seg-delayed { background: #ff9800; }
.seg-cancelled { background: #f44336; }
.bar-total { font-size: 10px; color: #aaa; min-width: 20px; text-align: right; }

.legend { display: flex; gap: 16px; margin-top: 6px; }
.leg-item { font-size: 10px; color: #888; display: flex; align-items: center; gap: 4px; }
.leg-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }
.dot-normal { background: #4caf50; }
.dot-delayed { background: #ff9800; }
.dot-cancelled { background: #f44336; }

/* Weather */
.weather-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 6px; }
.weather-card {
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  padding: 8px 6px;
  text-align: center;
  font-size: 11px;
}
.weather-card.disrupted { border: 1px solid rgba(255,152,0,0.3); }
.w-icon { font-size: 18px; display: block; margin-bottom: 2px; }
.w-ap { color: #cdd6f4; font-weight: 600; display: block; }
.w-type { color: #888; display: block; font-size: 10px; }
.w-vis, .w-wind { color: #666; font-size: 9px; display: inline-block; margin: 0 3px; }

.no-data { color: #666; text-align: center; padding: 20px; }

/* Time bar */
.sim-time-bar {
  display: flex; align-items: center; gap: 12px;
  background: rgba(255,255,255,0.04); border-radius: 6px;
  padding: 8px 14px;
}
.time-label { color: #888; font-size: 12px; }
.time-value { color: #f5d0a9; font-size: 14px; font-weight: 700; }
.time-pct { margin-left: auto; color: #4caf50; font-size: 12px; }
</style>
