<template>
  <div class="gantt-page">
    <div class="page-header">
      <h2>飞机排班甘特图</h2>
      <p class="page-desc">
        每一行=一架飞机，每个色块=一个航班。色块左缘=起飞时间，右缘=到达时间。
        行左侧标注该飞机每天执勤（飞行）时长，超过 8 小时(480分钟)标红 ——
        对应 CCAR-121 两人制机组每日飞行时间上限。
      </p>
      <div class="toolbar">
        <el-select v-model="algorithm" size="small" style="width:120px">
          <el-option label="二分图匹配" value="bipartite" />
          <el-option label="贪心算法" value="greedy" />
          <el-option label="均衡分配" value="vrp" />
        </el-select>
        <el-button type="primary" size="small" @click="runRouting">一键排班</el-button>
        <el-button size="small" @click="compareRouting">算法对比</el-button>
        <el-button type="success" size="small" @click="saveRouting" :disabled="!filterDate">保存排班</el-button>
        <el-input-number v-model="aircraftLimit" :min="1" :max="100" size="small" style="width:90px" />
        <span class="sep">|</span>
        <el-select v-model="filterAirport" size="small" filterable clearable style="width:150px" @change="onFilterChange" placeholder="按机场筛选">
          <el-option v-for="ap in airports" :key="ap" :label="ap" :value="ap" />
        </el-select>
        <el-select v-model="filterDate" size="small" style="width:120px" @change="onFilterChange" placeholder="按日期筛选">
          <el-option v-for="d in filterDates" :key="d" :label="d" :value="d" />
        </el-select>
        <span v-if="stats" class="info">飞机: {{ stats.aircraft_count }} 架 | 覆盖: {{ stats.coverage }}%</span>
        <span class="sep" v-if="stats">|</span>
        <el-input v-model="acSearch" size="small" placeholder="搜索飞机(编号/机型/注册号)" clearable style="width:200px" />
      </div>
    </div>

    <RoutingRecommendation :aircraft-limit="aircraftLimit" @select="algorithm = $event" />
    <!-- 未筛选提示 -->
    <div class="empty-hint" v-if="!filteredReady && aircrafts.length === 0">
      <p>请先在「航班筛选」页面上传文件、执行筛选并点击「保存并执行排班计划」</p>
    </div>
    <!-- 未排班 -->
    <div class="empty-hint" v-if="filteredReady && aircrafts.length === 0">
      <p>请点击「一键排班」开始飞机排班</p>
    </div>
    <!-- 甘特图 -->
    <div class="gantt-main" v-if="aircrafts.length > 0">
      <div class="gantt-header">
        <div class="row-label">飞机</div>
        <div class="time-header">
          <div v-for="d in dayMarks" :key="d.label" class="day-mark" :style="{left: d.px + 'px'}">{{ d.label }}</div>
        </div>
      </div>

      <div class="gantt-body">
        <div class="gantt-row" v-for="ac in displayAircrafts" :key="ac.ac_id">
          <div class="row-label">
            <span class="tail-no">{{ ac.tail_no }}</span>
            <span class="type-tag">{{ ac.ac_type }}</span>
            <div class="idx-row">
              <span class="idx-tag" :class="idxClass(ac.quality_index)">{{ ac.quality_index || '?' }}</span>
              <el-button size="mini" type="warning" plain class="adj-btn" @click="openAircraftDlg(ac)">调整</el-button>
            </div>
            <div class="duty-list" v-if="ac.dailyDuty && ac.dailyDuty.length">
              <div v-for="dd in ac.dailyDuty" :key="dd.date"
                   class="duty-item" :class="{ over: dd.minutes > 480 }"
                   :title="dd.date + ' 执勤 ' + fmtMin(dd.minutes) + '（上限 8h）'">
                <span class="duty-date">{{ dayShort(dd.date) }}</span>
                <span class="duty-h">{{ fmtMin(dd.minutes) }}</span>
              </div>
            </div>
          </div>
          <div class="row-timeline" :style="{minWidth: timelinePx + 'px'}">
            <div v-for="(f, fi) in ac.displayFlights" :key="fi"
                 class="flight-block" :style="blockStyle(f)"
                 :title="blockTooltip(f)"
                 @click="selectedFlight = f">
              <span class="block-label">{{ f.flight_no }}</span>
              <span class="block-route">{{ f.departure_airport }}→{{ f.arrival_airport }}</span>
            </div>
            <div v-for="d in dayDividers" :key="'dv'+d.px" class="day-divider" :style="{left: d.px + 'px'}"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!stats" class="empty-hint"><p>点击「一键排班」开始</p></div>

    <!-- 航班详情悬浮弹窗 -->
    <div class="flight-popup-mask" v-if="selectedFlight" @click.self="selectedFlight = null">
      <div class="flight-popup-card">
        <div class="popup-header">
          <strong>{{ selectedFlight.flight_no }}</strong>
          <span class="popup-close" @click="selectedFlight = null">&times;</span>
        </div>
        <div class="popup-body">
          <div class="popup-row"><span class="popup-label">航线</span><span>{{ selectedFlight.departure_airport }} → {{ selectedFlight.arrival_airport }}</span></div>
          <div class="popup-row"><span class="popup-label">起飞</span><span>{{ selectedFlight.time_departure }}</span></div>
          <div class="popup-row"><span class="popup-label">到达</span><span>{{ selectedFlight.time_arrival }}</span></div>
          <div class="popup-row"><span class="popup-label">时长</span><span>{{ selectedFlight.timespan }} 分钟</span></div>
          <div class="popup-row"><span class="popup-label">航班ID</span><span>{{ selectedFlight.flight_id }}</span></div>
          <div class="popup-row"><span class="popup-label">机型</span><span>{{ selectedFlight.ac_type }}</span></div>
        </div>
      </div>
    </div>

    <!-- 算法对比 -->
    <div class="compare-panel" v-if="compareData">
      <h3>算法对比（绿=更优, 红=劣势）</h3>
      <table>
        <tr><th>指标</th><th>二分图匹配</th><th>贪心算法</th></tr>
        <tr>
          <td>飞机数</td>
          <td :class="better('aircraft_count','min')">{{ compareData.bipartite.stats.aircraft_count }}</td>
          <td :class="better('aircraft_count','min')">{{ compareData.greedy.stats.aircraft_count }}</td>
        </tr>
        <tr>
          <td>利用率</td>
          <td :class="better('avg_utilization','max')">{{ compareData.bipartite.stats.avg_utilization }}%</td>
          <td :class="better('avg_utilization','max')">{{ compareData.greedy.stats.avg_utilization }}%</td>
        </tr>
        <tr>
          <td>空闲(min)</td>
          <td :class="better('total_idle_time_minutes','min')">{{ compareData.bipartite.stats.total_idle_time_minutes }}</td>
          <td :class="better('total_idle_time_minutes','min')">{{ compareData.greedy.stats.total_idle_time_minutes }}</td>
        </tr>
      </table>
    </div>

    <!-- 飞机情况调整对话框 -->
    <el-dialog title="飞机情况调整" :visible.sync="aircraftDlgVisible" width="480px">
      <div v-if="editingAircraft">
        <p class="dlg-head">
          飞机 <b>{{ editingAircraft.tail_no }}</b>（{{ editingAircraft.ac_type }}）
          <el-tag size="small" :type="editIdxTag" class="dlg-idx">当前指数 {{ editingAircraft.quality_index }}</el-tag>
          <span class="dlg-new" v-if="newIdx !== null">→ 调整后 <b>{{ newIdx }}</b></span>
        </p>
        <el-form label-width="130px" size="small">
          <el-form-item label="机龄（年）">
            <el-input-number v-model="editForm.age_years" :min="0" :max="30" :step="0.5" :precision="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="总飞行小时">
            <el-input-number v-model="editForm.total_flight_hours" :min="0" :step="500" :precision="0" controls-position="right" />
          </el-form-item>
          <el-form-item label="年维护天数">
            <el-input-number v-model="editForm.maintenance_days" :min="0" :max="30" :precision="0" controls-position="right" />
          </el-form-item>
          <el-form-item label="小时成本">
            <el-input-number v-model="editForm.cost_per_hour" :min="10000" :step="500" :precision="0" controls-position="right" />
          </el-form-item>
          <el-form-item label="燃油效率">
            <el-input-number v-model="editForm.fuel_efficiency" :min="0.5" :max="1" :step="0.01" :precision="2" controls-position="right" />
          </el-form-item>
          <el-form-item label="准点率">
            <el-input-number v-model="editForm.on_time_rate" :min="0.5" :max="1" :step="0.01" :precision="2" controls-position="right" />
          </el-form-item>
          <el-form-item label="最近大修日期">
            <el-input v-model="editForm.last_overhaul" placeholder="如 2025-01-22" />
          </el-form-item>
          <el-form-item label="循环次数">
            <el-input-number v-model="editForm.cycles" :min="0" :step="500" :precision="0" controls-position="right" />
          </el-form-item>
        </el-form>
        <p class="dlg-tip">保存后重新计算指数，并按新指数重新生成排班计划。</p>
      </div>
      <div slot="footer">
        <el-button size="small" @click="aircraftDlgVisible = false">取消</el-button>
        <el-button type="primary" size="small" :loading="savingAircraft" @click="saveAircraft">保存并重新排班</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/api'
import RoutingRecommendation from '@/components/intelligence/RoutingRecommendation'

export default {
  components: { RoutingRecommendation },
  data() {
    return {
      filteredReady: false,
      algorithm: 'bipartite',
      aircraftLimit: 100,
      aircrafts: [],         // 原始排班结果（全部航班）
      stats: null,
      filterAirport: '',
      filterDate: '',
      airports: [],
      filterDates: [],
      compareData: null,
      selectedFlight: null,
      pxPerMin: 1.2,
      acSearch: '',
      // 飞机情况调整对话框
      aircraftDlgVisible: false,
      editingAircraft: null,
      editForm: {},
      newIdx: null,
      savingAircraft: false,
    }
  },
  computed: {
    // 每架飞机的原始航班 + 筛选后航班
    enrichedAircrafts() {
      return this.aircrafts.map(ac => {
        let flights = ac.assigned_flights || []
        // 每日执勤时长：基于完整任务链（不受机场/日期筛选影响）按天聚合飞行分钟
        const duty = {}
        for (const f of flights) {
          const d = this.flightDate(f)
          if (d) duty[d] = (duty[d] || 0) + (f.timespan || 0)
        }
        const dailyDuty = Object.keys(duty).sort().map(d => ({ date: d, minutes: duty[d] }))
        // 机场+日期筛选
        if (this.filterAirport) {
          flights = flights.filter(f => f.departure_airport === this.filterAirport || f.arrival_airport === this.filterAirport)
        }
        if (this.filterDate) {
          flights = flights.filter(f => this.flightDate(f) === this.filterDate)
        }
        return { ...ac, displayFlights: flights, dailyDuty }
      })
    },
    displayAircrafts() {
      let list = this.enrichedAircrafts
        .filter(ac => ac.displayFlights.length > 0)
      if (this.acSearch) {
        const kw = this.acSearch.toLowerCase()
        list = list.filter(ac =>
          ac.tail_no.toLowerCase().includes(kw) ||
          ac.ac_type.toLowerCase().includes(kw) ||
          String(ac.ac_id).includes(kw) ||
          String(ac.quality_index || '').includes(kw)
        )
      }
      return list
    },
    timeRange() {
      let min = Infinity, max = -Infinity
      for (const ac of this.displayAircrafts) {
        for (const f of ac.displayFlights) {
          const d = this.absMin(f.time_departure)
          const a = this.absMin(f.time_arrival)
          if (d < min) min = d
          if (a > max) max = a
        }
      }
      if (!isFinite(min)) min = 0
      if (!isFinite(max)) max = 1440
      return { min, max }
    },
    timelinePx() {
      return Math.max(800, (this.timeRange.max - this.timeRange.min) * this.pxPerMin + 200)
    },
    dayMarks() {
      const marks = []
      const startDay = this.absDay(this.timeRange.min)
      const endDay = this.absDay(this.timeRange.max)
      for (let d = startDay; d <= endDay; d++) {
        marks.push({ label: this.dayLabel(d), px: (d * 1440 - this.timeRange.min) * this.pxPerMin })
      }
      return marks
    },
    dayDividers() { return this.dayMarks.map(d => ({ px: d.px })) },
    editIdxTag() {
      if (!this.editingAircraft) return 'info'
      if (this.editingAircraft.quality_index >= 80) return 'success'
      if (this.editingAircraft.quality_index >= 60) return 'warning'
      return 'danger'
    },
  },
  watch: {
    'editForm': {
      deep: true,
      handler() { this.newIdx = this.previewIdx() },
    },
  },
  methods: {
    idxClass(val) {
      if (val == null || val === '?') return ''
      if (val >= 80) return 'idx-good'
      if (val >= 60) return 'idx-ok'
      return 'idx-low'
    },
    // 打开飞机情况调整对话框（初始值 = 系统预设指标）
    openAircraftDlg(ac) {
      this.editingAircraft = ac
      this.editForm = {
        age_years: ac.age_years,
        total_flight_hours: ac.total_flight_hours,
        maintenance_days: ac.maintenance_days,
        cost_per_hour: ac.cost_per_hour,
        fuel_efficiency: ac.fuel_efficiency,
        last_overhaul: ac.last_overhaul,
        on_time_rate: ac.on_time_rate,
        cycles: ac.cycles,
      }
      this.newIdx = this.previewIdx()
      this.aircraftDlgVisible = true
    },
    // 前端实时预览指数（与后端 Aircraft._compute_quality_index 同口径）
    previewIdx() {
      const f = this.editForm || {}
      const num = (v, d) => (typeof v === 'number' && isFinite(v) ? v : d)
      const age = num(f.age_years, 5)
      const hours = num(f.total_flight_hours, 25000)
      const cost = num(f.cost_per_hour, 20000)
      const eff = num(f.fuel_efficiency, 0.9)
      const maint = num(f.maintenance_days, 0)
      const ontime = num(f.on_time_rate, 0.95)
      let s = 0
      s += Math.max(0, 1 - age / 18) * 25
      s += Math.max(0, 1 - hours / 53000) * 20
      s += Math.max(0, 1 - (cost - 18000) / 7000) * 20
      s += Math.max(0, Math.min(1, eff)) * 15
      s += Math.max(0, 1 - maint / 7) * 10
      s += Math.max(0, ontime) * 10
      return Math.round(s * 10) / 10
    },
    // 保存：后端更新指标并重算指数 → 重新排班
    async saveAircraft() {
      this.savingAircraft = true
      try {
        const res = await api.updateAircraft({ tail_no: this.editingAircraft.tail_no, ...this.editForm })
        this.$message.success(`已更新 ${res.tail_no}：指数 ${this.editingAircraft.quality_index} → ${res.quality_index}，正在重新排班...`)
        this.aircraftDlgVisible = false
        this.editingAircraft = null
        this.newIdx = null
        await this.runRouting()
      } catch (e) {
        this.$message.error('保存失败: ' + e.message)
      } finally {
        this.savingAircraft = false
      }
    },
    _init() {
      this.checkFiltered().then(() => {
        if (this.filteredReady) {
          this.loadAirports()
          this.runRouting()
        }
      })
    },
    absMin(timeStr) {
      const m = timeStr.match(/(\d+)-(\d+)-(\d+)\s+(\d+):(\d+)/)
      if (!m) return 0
      // 以11月1日为基准：month=11 → dayOffset=0, month=12 → dayOffset=30
      const month = parseInt(m[2])
      const day = parseInt(m[3])
      const dayOffset = month === 11 ? day : 30 + day
      return dayOffset * 1440 + parseInt(m[4]) * 60 + parseInt(m[5])
    },
    absDay(minVal) { return Math.floor(minVal / 1440) },
    dayLabel(day) { return day <= 30 ? `11/${day}` : `12/${day - 30}` },
    flightDate(f) {
      const m = (f.time_departure || '').match(/(\d+-\d+-\d+)/)
      return m ? m[1] : ''
    },
    // '2020-11-30' -> '11/30'
    dayShort(dateStr) {
      const m = (dateStr || '').match(/(\d+)-(\d+)-(\d+)/)
      return m ? `${Number(m[2])}/${Number(m[3])}` : dateStr
    },
    fmtMin(min) {
      const h = Math.floor(min / 60)
      const mm = Math.round(min % 60)
      return mm > 0 ? `${h}h${mm}m` : `${h}h`
    },

    blockStyle(f) {
      const dep = this.absMin(f.time_departure)
      const arr = this.absMin(f.time_arrival)
      const left = (dep - this.timeRange.min) * this.pxPerMin
      const width = Math.max(30, (arr - dep) * this.pxPerMin)
      const hash = f.flight_no.split('').reduce((s, c) => s + c.charCodeAt(0), 0)
      const hue = hash % 360
      return {
        left: left + 'px', width: width + 'px',
        background: `linear-gradient(135deg, hsl(${hue},65%,55%), hsl(${hue + 20},60%,45%))`,
      }
    },
    blockTooltip(f) {
      return `航班: ${f.flight_no}\n航线: ${f.departure_airport} → ${f.arrival_airport}\n起飞: ${f.time_departure}\n到达: ${f.time_arrival}\n时长: ${f.timespan} 分钟`
    },
    better(key, dir) {
      if (!this.compareData) return ''
      const b = this.compareData.bipartite.stats[key]
      const g = this.compareData.greedy.stats[key]
      if (b === g) return ''
      return (dir === 'min' ? b < g : b > g) ? 'better' : 'worse'
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
    async runRouting() {
      this.selectedFlight = null
      try {
        const result = await api.runRouting(this.algorithm, this.aircraftLimit)
        this.aircrafts = result.aircrafts || []
        this.stats = result.stats || null
        this.compareData = null
        // 提取日期列表
        const ds = new Set()
        for (const ac of this.aircrafts) {
          for (const f of ac.assigned_flights || []) {
            const d = this.flightDate(f)
            if (d) ds.add(d)
          }
        }
        this.filterDates = Array.from(ds).sort()
        this.$message.success(`排班完成: ${this.stats.aircraft_count} 架`)
      } catch (e) {
        this.$message.error('排班失败: ' + e.message)
      }
    },
    async compareRouting() {
      try {
        const result = await api.compareRouting()
        this.compareData = result
      } catch (e) {
        this.$message.error('对比失败: ' + e.message)
      }
    },
    onFilterChange() { /* computed 自动重新过滤 */ },
    async saveRouting() {
      if (!this.filterDate) {
        this.$message.warning('请先选择日期')
        return
      }
      try {
        // 发送当前筛选后的飞机排班
        const routingData = this.displayAircrafts.map(ac => ({
          ...ac,
          assigned_flights: ac.displayFlights,
        }))
        const result = await api.saveSchedule(this.filterDate, routingData, [])
        this.$message.success(`已保存 ${this.filterDate} 排班到地图演示`)
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
.gantt-page {
  width: 100%; flex: 1; min-height: 0; display: flex; flex-direction: column;
  padding: 16px; background: rgba(0,0,0,0.3); color: #eee; overflow-y: auto;
}
.page-header { flex-shrink: 0; margin-bottom: 12px; }
.page-header h2 { font-size: 20px; margin: 0 0 4px 0; }
.page-desc { font-size: 13px; color: #aaa; margin: 0 0 10px 0; line-height: 1.5; }
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sep { color: #555; }
.info { font-size: 12px; color: #999; margin-left: auto; }

.empty-hint { flex: 1; display: flex; align-items: center; justify-content: center; color: #888; font-size: 15px; }

.gantt-main { flex: 1 0 auto; min-height: 300px; display: flex; flex-direction: column; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; }
.gantt-header { display: flex; flex-shrink: 0; border-bottom: 1px solid rgba(255,255,255,0.2); background: rgba(0,0,0,0.4); }
.row-label {
  width: 132px; min-width: 132px; padding: 8px; font-size: 13px; font-weight: bold;
  text-align: center; border-right: 1px solid rgba(255,255,255,0.15);
  display: flex; flex-direction: column; justify-content: flex-start; align-items: center;
  overflow: hidden;
}
.time-header { flex: 1; position: relative; height: 24px; overflow: hidden; }
.day-mark { position: absolute; font-size: 11px; color: #999; top: 4px; white-space: nowrap; transform: translateX(-50%); }

.gantt-body { flex: 1; overflow: auto; }
.gantt-row { display: flex; border-bottom: 1px solid rgba(255,255,255,0.06); min-height: 52px; }
.gantt-row:hover { background: rgba(255,255,255,0.04); }
.tail-no { font-size: 12px; color: #fff; }
.type-tag { font-size: 10px; color: #aaa; margin-top: 2px; }
.idx-row { display: flex; align-items: center; gap: 5px; margin-top: 3px; }
.idx-tag {
  font-size: 10px; padding: 1px 5px; border-radius: 8px;
  background: rgba(255,255,255,0.1); color: #aaa;
}
.adj-btn { padding: 1px 6px; font-size: 11px; line-height: 1.6; }
.idx-tag.idx-good { background: rgba(76,175,80,0.3); color: #4caf50; }
.idx-tag.idx-ok { background: rgba(255,193,7,0.3); color: #ffc107; }
.idx-tag.idx-low { background: rgba(244,67,54,0.3); color: #f44336; }

.dlg-head { margin: 0 0 12px 0; color: #ddd; font-size: 14px; }
.dlg-head b { color: #fff; }
.dlg-idx { margin-left: 6px; }
.dlg-new { margin-left: 8px; color: #e6a23c; }
.dlg-tip { color: #888; font-size: 12px; margin: 10px 0 0 0; }

.duty-list { margin-top: 6px; width: 100%; display: flex; flex-direction: column; gap: 3px; }
.duty-item {
  font-size: 10px; display: flex; justify-content: space-between; align-items: center;
  padding: 2px 7px; border-radius: 4px; background: rgba(255,255,255,0.06);
  color: #9ccc65; white-space: nowrap; cursor: default;
}
.duty-item .duty-date { color: #bbb; }
.duty-item.over { background: rgba(244,67,54,0.28); color: #ff5252; font-weight: bold; }
.duty-item.over .duty-date { color: #ff8a80; }
.duty-item.over::after { content: '!'; margin-left: 3px; }
.row-timeline { flex: 1; position: relative; padding-left: 12px; }
.day-divider { position: absolute; top: 0; bottom: 0; width: 1px; background: rgba(255,255,255,0.12); }

.flight-block {
  position: absolute; top: 6px; height: 40px; border-radius: 5px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; overflow: hidden;
}
.flight-block:hover { transform: scale(1.02); box-shadow: 0 2px 10px rgba(0,0,0,0.4); z-index: 2; }
.block-label { font-size: 11px; font-weight: bold; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.5); }
.block-route { font-size: 9px; color: rgba(255,255,255,0.8); text-shadow: 0 1px 2px rgba(0,0,0,0.5); }

.flight-popup-mask {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.flight-popup-card {
  background: #2a2a3e; border: 1px solid rgba(255,255,255,0.15);
  border-radius: 10px; min-width: 320px; max-width: 420px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  overflow: hidden;
}
.popup-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 18px; background: rgba(0,0,0,0.3);
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.popup-header strong { font-size: 18px; color: #f5d0a9; }
.popup-close {
  font-size: 24px; color: #888; cursor: pointer; line-height: 1;
  padding: 0 4px;
}
.popup-close:hover { color: #fff; }
.popup-body { padding: 14px 18px; }
.popup-row {
  display: flex; justify-content: space-between; padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; color: #ddd;
}
.popup-label { color: #888; font-size: 13px; }
.popup-row:last-child { border-bottom: none; }

.compare-panel {
  margin-top: 12px; flex-shrink: 0; max-height: 180px; overflow: auto;
  background: rgba(0,0,0,0.3); border-radius: 6px; padding: 12px;
}
.compare-panel h3 { font-size: 15px; margin: 0 0 8px 0; }
.compare-panel table { width: 100%; font-size: 13px; border-collapse: collapse; }
.compare-panel th, .compare-panel td { padding: 6px 10px; border: 1px solid rgba(255,255,255,0.1); text-align: center; }
.compare-panel th { background: rgba(0,0,0,0.3); }
.better { background: rgba(76,175,80,0.3); font-weight: bold; color: #4caf50; }
.worse { background: rgba(244,67,54,0.2); }
</style>
