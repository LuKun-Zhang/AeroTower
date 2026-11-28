<template>
  <div class="runway-page">
    <!-- ========== 左侧控制面板 (20%) ========== -->
    <div class="left-panel">
      <div class="panel-header">
        <h2>跑道调度</h2>
        <p class="panel-desc">起降混用 · 真实跑道数分配<br/>蓝=降落 绿=起飞 红=延误</p>
      </div>

      <div class="control-group">
        <label class="ctrl-label">选择机场</label>
        <el-select v-model="airport" size="small" filterable @change="onAirportChange" placeholder="选择机场">
          <el-option v-for="ap in airports" :key="ap" :label="ap" :value="ap" />
        </el-select>
      </div>

      <div class="control-group">
        <label class="ctrl-label">选择日期</label>
        <el-select v-model="date" size="small" @change="filterByDate" placeholder="日期">
          <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
        </el-select>
      </div>

      <div class="control-group">
        <label class="ctrl-label">调度算法</label>
        <el-select v-model="runwayMethod" size="small">
          <el-option label="FCFS" value="fcfs" />
          <el-option label="CP-SAT" value="cp_sat" />
          <el-option label="ILS-CPS" value="ils_cps" />
        </el-select>
      </div>

      <div class="control-group btn-row">
        <el-button type="primary" size="small" @click="loadData" :loading="loading" style="width:100%">刷 新</el-button>
      </div>

      <div class="control-group btn-row">
        <el-button type="success" size="small" @click="saveRunway" :disabled="!date" style="width:100%">保存跑道调度</el-button>
      </div>

      <div class="control-group btn-row">
        <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts" style="width:100%">图表</el-button>
      </div>

      <div class="stats-box" v-if="runwayStats">
        <div class="stat-item"><span class="stat-val">{{ runwayCount }}</span>条跑道</div>
        <div class="stat-item"><span class="stat-val">{{ schedule.length }}</span>航班</div>
        <div class="stat-item">延误<span class="stat-val" :class="{warn:runwayStats.total_delay>0}">{{ runwayStats.total_delay || 0 }}min</span></div>
      </div>

      <div class="legend-box">
        <div class="leg-row"><span class="leg-dot land"></span> 降落</div>
        <div class="leg-row"><span class="leg-dot takeoff"></span> 起飞</div>
        <div class="leg-row"><span class="leg-dot delay"></span> 延误</div>
      </div>
    </div>

    <!-- ========== 右侧竖直时间轴 (80%) ========== -->
    <div class="right-panel">
      <div class="empty-hint" v-if="!filteredReady">
        <p>请先在「航班筛选」页面上传文件、执行筛选并点击「保存并执行排班计划」</p>
      </div>

      <template v-else-if="!airport">
        <div class="empty-hint">
          <p>请选择机场查看跑道调度</p>
        </div>
      </template>

      <template v-else-if="schedule.length > 0">
        <div class="vt-title">{{ airport }} — 竖直时间轴（0:00 ~ 次日 6:00）</div>
        <div class="vt-body">
          <!-- 竖直时间标尺 -->
          <div class="vt-ruler">
            <span v-for="tick in hourTicks" :key="tick.hour" class="vt-tick"
                  :style="{top: tick.pct + '%'}">{{ tick.label }}</span>
          </div>
          <!-- 各跑道列 -->
          <div class="vt-lanes">
            <div class="vt-lane" v-for="r in runwayCount" :key="'rwy'+r">
              <div class="vt-lane-header">
                <span class="vt-lane-label">跑道 {{ r }}</span>
                <span class="vt-lane-gates" v-if="gateInfoFor(r)">{{ gateInfoFor(r).gate_range }}</span>
              </div>
              <div class="vt-lane-track">
                <div v-for="item in runwaySchedule(r)" :key="item.flight_id"
                     class="vt-blk" :class="[item.type === 'takeoff' ? 'takeoff' : '', {delayed:item.delay>0}]"
                     :style="vPosStyle(item)"
                     @click="selectedFlight = item">
                  <span class="vt-blk-no">{{ item.flight_no }}</span>
                  <span class="vt-blk-route">{{ item.type === 'landing' ? item.from : item.to }}</span>
                  <span class="vt-blk-ac">{{ item.ac_type || '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="empty-hint">
        <p>{{ airport }} 暂无航班数据</p>
      </div>
    </div>

    <!-- ========== 航班详情弹窗 ========== -->
    <div class="flight-popup-mask" v-if="selectedFlight" @click.self="selectedFlight = null">
      <div class="flight-popup-card">
        <div class="popup-header">
          <strong>{{ selectedFlight.flight_no }}</strong>
          <span class="popup-close" @click="selectedFlight = null">&times;</span>
        </div>
        <div class="popup-body">
          <div class="popup-row"><label>飞机ID</label><span>{{ selectedFlight.flight_id }}</span></div>
          <div class="popup-row"><label>机型</label><span>{{ selectedFlight.ac_type || '-' }} <em class="cat-tag">{{ selectedFlight.category || '' }}</em></span></div>
          <div class="popup-row"><label>跑道</label><span>跑道 {{ selectedFlight.runway }} / {{ selectedFlight.runway_total }}</span></div>
          <div class="popup-row"><label>航线</label><span>{{ selectedFlight.from }} → {{ selectedFlight.to }}</span></div>
          <div class="popup-row"><label>类型</label><span :class="selectedFlight.type === 'landing' ? 'c-land' : 'c-takeoff'">{{ selectedFlight.type === 'landing' ? '降落' : '起飞' }}</span></div>
          <div class="popup-row"><label>日期</label><span>{{ selectedFlight.date }}</span></div>
          <div class="popup-row"><label>飞行时间</label><span>{{ selectedFlight.time_dep }} → {{ selectedFlight.time_arr }}</span></div>
          <div class="popup-row"><label>飞行时长</label><span>{{ selectedFlight.duration }} 分钟</span></div>
          <div class="popup-divider">跑道占用</div>
          <div class="popup-row"><label>开始</label><span>{{ fmtTime(selectedFlight.actual_time) }}</span></div>
          <div class="popup-row"><label>结束</label><span>{{ fmtTime(selectedFlight.end_time) }}</span></div>
          <div class="popup-row"><label>占用</label><span>{{ selectedFlight.runway_duration }} 分钟</span></div>
          <div class="popup-row">
            <label>延误</label>
            <span :class="{ delayed: selectedFlight.delay > 0 }">{{ selectedFlight.delay > 0 ? '+' + selectedFlight.delay + ' min' : '准点' }}</span>
          </div>
        </div>
      </div>
    </div>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="跑道调度" />
  </div>
</template>

<script>
import api from '@/api'
import ChartOverlay from '@/components/ChartOverlay'
import { buildRunwayCharts } from '@/utils/charts/runwayView'

const START_HOUR = 0
const END_HOUR = 30
const TOTAL_MIN = (END_HOUR - START_HOUR) * 60

export default {
  components: { ChartOverlay },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      filteredReady: false,
      airport: '',
      date: '',
      airports: [],
      dates: [],
      allSchedule: [],
      selectedFlight: null,
      runwayMethod: 'fcfs',
      runwayStats: null,
      loading: false,
      gateGroups: {},  // airport → [{runway, gate_range, ...}]
    }
  },
  computed: {
    airportGateGroups() {
      return this.gateGroups[this.airport] || []
    },
    airportSchedule() {
      if (!this.airport) return []
      return this.allSchedule.filter(i => i.airport === this.airport)
    },
    schedule() {
      if (!this.date) return this.airportSchedule
      return this.airportSchedule.filter(i => i.date === this.date)
    },
    runwayCount() {
      if (this.schedule.length === 0) return 1
      return this.schedule[0].runway_total || 1
    },
    hourTicks() {
      const ticks = []
      for (let h = START_HOUR; h <= END_HOUR; h++) {
        ticks.push({
          hour: h,
          label: this.fmtHour(h),
          pct: ((h - START_HOUR) * 60 / TOTAL_MIN) * 100,
        })
      }
      return ticks
    },
  },
  methods: {
    openCharts() {
      this.chartList = buildRunwayCharts(this)
      this.chartsOpen = true
    },
    runwaySchedule(r) {
      return this.schedule.filter(i => i.runway === r)
    },
    _init() {
      this.checkFiltered().then(() => {
        if (this.filteredReady) {
          this.loadAirports()
          this.loadAllSchedules()
          this.loadGateGroups()
        }
      })
    },
    gateInfoFor(r) {
      const groups = this.airportGateGroups
      return groups.find(g => g.runway === r)
    },
    async loadGateGroups() {
      try {
        const resp = await fetch('/api/airport/gate-groups')
        const json = await resp.json()
        if (json.code === 0) {
          this.gateGroups = json.data || {}
        }
      } catch (e) { console.error('加载登机口分组失败', e) }
    },
    fmtHour(h) {
      if (h < 24) return `${h}:00`
      return `次日${h - 24}:00`
    },
    async checkFiltered() {
      try {
        const resp = await fetch('/api/flights/status')
        const json = await resp.json()
        this.filteredReady = json.data && json.data.filtered_mode
      } catch (e) { this.filteredReady = false }
    },
    async loadAirports() {
      try {
        const r = await api.getAirports()
        this.airports = r.map(a => a.name).sort()
      } catch (e) { console.error(e) }
    },
    async loadAllSchedules() {
      try {
        const result = await api.runRunway(this.runwayMethod)
        this.allSchedule = result.schedule || []
        const statsMap = result.stats || {}
        this.runwayStats = statsMap[this.airport] || Object.values(statsMap)[0] || null
        const apSet = new Set(this.airports)
        this.allSchedule.forEach(i => { if (i.airport) apSet.add(i.airport) })
        this.airports = Array.from(apSet).sort()
      } catch (e) { console.error('加载跑道数据失败', e) }
    },
    async loadData() {
      if (!this.airport) return
      this.loading = true
      try {
        await this.loadAllSchedules()
        const ds = new Set()
        this.airportSchedule.forEach(i => { if (i.date) ds.add(i.date) })
        this.dates = Array.from(ds).sort()
        if (!this.date && this.dates.length > 0) this.date = this.dates[0]
      } finally {
        this.loading = false
      }
    },
    onAirportChange() { this.date = ''; this.loadData() },
    filterByDate() {},
    fmtTime(minVal) {
      const m = minVal % 1440
      const h = Math.floor(m / 60)
      const mi = m % 60
      return `${h}:${mi.toString().padStart(2, '0')}`
    },
    vPosStyle(item) {
      const min = item.actual_time % 1440
      const base = min < START_HOUR * 60 ? min + 1440 : min
      const topPct = ((base - START_HOUR * 60) / TOTAL_MIN) * 100
      const runwayDur = item.runway_duration || 2
      const htPct = Math.max(0.3, (runwayDur / TOTAL_MIN) * 100)
      return { top: topPct + '%', height: htPct + '%' }
    },
    async saveRunway() {
      if (!this.date) {
        this.$message.warning('请先选择日期')
        return
      }
      try {
        await api.saveSchedule(this.date, [], this.schedule)
        this.$message.success(`已保存 ${this.date} 跑道调度到地图演示`)
      } catch (e) {
        this.$message.error('保存失败: ' + e.message)
      }
    },
  },
  mounted() { this._init() },
  activated() { this._init() },
}
</script>

<style scoped>
/* ========== 整体布局: 左右分栏 1:4 ========== */
.runway-page {
  width: 100%; height: 100%; display: flex; flex-direction: row;
  background: rgba(0,0,0,0.3); color: #eee; padding: 12px; gap: 12px;
  box-sizing: border-box;
}

/* ========== 左侧控制面板 20% ========== */
.left-panel {
  width: 20%; min-width: 180px; max-width: 240px;
  flex-shrink: 0; display: flex; flex-direction: column;
  padding: 16px 14px; gap: 14px;
  background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px; overflow-y: auto;
}
.panel-header { flex-shrink: 0; }
.panel-header h2 { font-size: 18px; margin: 0 0 4px 0; color: #f5d0a9; }
.panel-desc { font-size: 11px; color: #888; margin: 0; line-height: 1.6; }

.control-group { flex-shrink: 0; }
.ctrl-label { display: block; font-size: 11px; color: #999; margin-bottom: 4px; }
.control-group .el-select { width: 100%; }
.btn-row { margin-top: 2px; }

/* 统计卡片 */
.stats-box {
  flex-shrink: 0; padding: 10px 12px;
  background: rgba(0,0,0,0.3); border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.06);
  display: flex; flex-direction: column; gap: 6px;
}
.stat-item { font-size: 12px; color: #aaa; }
.stat-val { font-weight: bold; font-size: 15px; color: #f5d0a9; margin: 0 3px; }
.stat-val.warn { color: #f56; }

/* 图例 */
.legend-box {
  flex-shrink: 0; padding: 8px 12px;
  background: rgba(0,0,0,0.25); border-radius: 6px;
  display: flex; flex-direction: column; gap: 5px;
}
.leg-row { font-size: 11px; color: #999; display: flex; align-items: center; gap: 6px; }
.leg-dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
}
.leg-dot.land { background: rgba(43,196,243,0.75); }
.leg-dot.takeoff { background: rgba(76,175,80,0.7); }
.leg-dot.delay { background: rgba(220,80,60,0.75); }

/* ========== 右侧时间轴面板 80% ========== */
.right-panel {
  flex: 1; display: flex; flex-direction: column;
  min-width: 0; min-height: 0; overflow-y: auto;
}

.empty-hint {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: #888; font-size: 15px;
}

.vt-title {
  font-size: 13px; color: #888; margin-bottom: 6px; flex-shrink: 0;
}

.vt-body {
  flex: 1; display: flex; min-height: 10800px;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px; background: rgba(0,0,0,0.2);
}

/* 竖直标尺 */
.vt-ruler {
  flex-shrink: 0; width: 52px; position: relative;
  border-right: 1px solid rgba(255,255,255,0.15);
  background: rgba(0,0,0,0.3); overflow: hidden;
}
.vt-tick {
  position: absolute; left: 0; right: 0; text-align: center;
  font-size: 10px; color: #777; transform: translateY(-50%); line-height: 1;
}

/* 跑道列 */
.vt-lanes {
  flex: 1; display: flex; overflow-x: auto; overflow-y: hidden;
}
.vt-lane {
  flex: 1; min-width: 100px; display: flex; flex-direction: column;
  border-right: 1px dashed rgba(255,255,255,0.06); position: relative;
}
.vt-lane:last-child { border-right: none; }
.vt-lane-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  background: rgba(0,0,0,0.4);
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.vt-lane-label {
  height: 26px; line-height: 26px; text-align: center;
  font-size: 11px; color: #aaa;
}
.vt-lane-gates {
  font-size: 9px; color: #fd8; padding-bottom: 2px;
}
.vt-lane-track { flex: 1; position: relative; min-height: 0; }

/* 色块 */
.vt-blk {
  position: absolute; left: 3px; right: 3px; border-radius: 4px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  cursor: pointer; overflow: hidden; min-height: 22px;
  background: rgba(43,196,243,0.55); border: 1px solid rgba(43,196,243,0.75);
}
.vt-blk.takeoff { background: rgba(76,175,80,0.5); border-color: rgba(76,175,80,0.7); }
.vt-blk.delayed { background: rgba(220,80,60,0.6) !important; border-color: rgba(220,80,60,0.8) !important; }
.vt-blk-no { font-size: 9px; font-weight: bold; color: #fff; white-space: nowrap; }
.vt-blk-route { font-size: 7px; color: rgba(255,255,255,0.7); }
.vt-blk-ac { font-size: 7px; color: #8fc5ff; margin-top: 2px; white-space: nowrap; }

/* ========== 弹窗 ========== */
.flight-popup-mask {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
}
.flight-popup-card {
  background: #1e2a35; border: 1px solid rgba(255,255,255,0.15);
  border-radius: 10px; width: 380px; max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.popup-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px 10px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  font-size: 17px; color: #f5d0a9;
}
.popup-close {
  cursor: pointer; font-size: 22px; color: #888; line-height: 1; padding: 0 4px;
}
.popup-close:hover { color: #f56; }
.popup-body { padding: 12px 18px 16px 18px; }
.popup-row {
  display: flex; align-items: center; padding: 5px 0; font-size: 13px; color: #ccc;
}
.popup-row label { color: #888; width: 70px; flex-shrink: 0; font-size: 12px; }
.popup-row .delayed { color: #f56; font-weight: bold; }
.popup-row .c-land { color: #2bc4f3; }
.popup-row .c-takeoff { color: #4caf50; }
.popup-row .cat-tag { font-size: 11px; color: #ffa94d; font-style: normal; margin-left: 4px; }
.popup-divider {
  padding: 8px 0 4px 0; margin-top: 4px;
  border-top: 1px solid rgba(255,255,255,0.08);
  font-size: 11px; color: #888;
}
</style>
