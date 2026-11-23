<template>
  <div id="gate-view">
    <div class="dragRectTop"></div>

    <!-- 未筛选提示 -->
    <div class="empty-hint" v-if="!filteredReady">
      <p>请先在「航班筛选」页面上传文件、执行筛选并点击「保存并执行排班计划」</p>
    </div>

    <template v-if="filteredReady">
    <div class="toolbar">
      <h2>登机口分配</h2>
      <div class="controls">
        <el-select v-model="airport" size="small" filterable style="width:130px" @change="onAirportChange">
          <el-option v-for="ap in airportOptions" :key="ap" :label="ap" :value="ap" />
        </el-select>
        <el-select v-model="algorithm" size="small" style="width:120px">
          <el-option label="CP-SAT" value="cp_sat" />
          <el-option label="二分图匹配" value="bipartite" />
          <el-option label="贪心算法" value="greedy" />
        </el-select>
        <el-select v-model="date" size="small" style="width:115px" placeholder="全部日期" @change="onDateChange">
          <el-option label="全部日期" value="" />
          <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
        </el-select>
        <el-button type="primary" size="small" @click="assignGates" :loading="loading">分配</el-button>
        <el-button size="small" @click="compareGates" :loading="compareLoading">算法对比</el-button>
        <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
        <span class="hint-tip" v-if="gates.length > 0">点击色块查看详情</span>
        <span v-if="stats.avg_utilization > 0" class="info">
          {{ stats.total_gates }} 机位 | 利用率 {{ stats.avg_utilization }}%
        </span>
      </div>
    </div>

    <!-- 统计面板 -->
    <div class="stats-bar" v-if="stats.total_gates">
      <span>总机位: <b>{{ stats.total_gates }}</b></span>
      <span>已用: <b>{{ stats.used_gates }}</b></span>
      <span>平均利用率: <b>{{ stats.avg_utilization }}%</b></span>
      <span>最高: <b>{{ stats.max_utilization }}%</b></span>
      <span v-if="date">日期: <b>{{ date }}</b></span>
    </div>

    <!-- 冲突告警 -->
    <div class="conflict-area" v-if="conflictCount > 0">
      <el-alert type="warning" :closable="false" show-icon>
        <span slot="title">{{ conflictCount }} 个登机口冲突检测到</span>
      </el-alert>
      <div class="conflict-list">
        <div v-for="(c, i) in conflicts.slice(0, 5)" :key="i" class="conflict-item">
          {{ c.gate }}: {{ c.flight_a }} ↔ {{ c.flight_b }}
        </div>
      </div>
    </div>

    <!-- 算法对比面板 -->
    <div v-if="compareData" class="compare-panel">
      <h3>算法对比 — {{ compareData.airport }} ({{ compareData.date || '全部' }}, {{ compareData.flight_count }} 航班)</h3>
      <table>
        <tr>
          <th>指标</th>
          <th>贪心算法</th>
          <th>二分图匹配</th>
          <th>CP-SAT</th>
        </tr>
        <tr>
          <td>已用机位</td>
          <td>{{ compareData.greedy.stats.used_gates }} / {{ compareData.greedy.stats.total_gates }}</td>
          <td>{{ compareData.bipartite.stats.used_gates }} / {{ compareData.bipartite.stats.total_gates }}</td>
          <td>{{ compareData.cp_sat.stats.used_gates }} / {{ compareData.cp_sat.stats.total_gates }}</td>
        </tr>
        <tr>
          <td>平均利用率</td>
          <td>{{ compareData.greedy.stats.avg_utilization }}%</td>
          <td>{{ compareData.bipartite.stats.avg_utilization }}%</td>
          <td>{{ compareData.cp_sat.stats.avg_utilization }}%</td>
        </tr>
        <tr>
          <td>最高利用率</td>
          <td>{{ compareData.greedy.stats.max_utilization }}%</td>
          <td>{{ compareData.bipartite.stats.max_utilization }}%</td>
          <td>{{ compareData.cp_sat.stats.max_utilization }}%</td>
        </tr>
        <tr>
          <td>冲突数</td>
          <td :class="{ 'has-conflict': compareData.greedy.conflict_count > 0 }">{{ compareData.greedy.conflict_count }}</td>
          <td :class="{ 'has-conflict': compareData.bipartite.conflict_count > 0 }">{{ compareData.bipartite.conflict_count }}</td>
          <td :class="{ 'has-conflict': compareData.cp_sat.conflict_count > 0 }">{{ compareData.cp_sat.conflict_count }}</td>
        </tr>
      </table>
    </div>

    <!-- 登机口时间线 -->
    <div class="timeline-container" v-if="gates.length > 0">
      <div class="timeline-body">
        <div class="gate-row" v-for="g in displayGates" :key="g.gate_id">
          <div class="gate-label">
            <span class="gate-name">{{ g.name }}</span>
            <span class="gate-type-tag" :class="g.gate_type">{{ typeLabel(g.gate_type) }}</span>
            <span class="gate-rwy-tag">RWY{{ g.runway_group }}</span>
          </div>
          <div class="gate-timeline" :style="{ minWidth: timelinePx + 'px' }">
            <div v-for="(f, fi) in g.assigned_flights" :key="fi"
                   class="block" :class="['dir-' + f.direction, { active: hoverBlock === f }]" :style="blockStyle(f, fi)"
                   @click="onBlockClick(f, $event)">
                <span class="blk-no">{{ f.flight }}</span>
              </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!loading && gates.length === 0" class="empty-tip">选择机场点击"分配"或"算法对比"开始</div>

    <!-- 浮动信息提示栏 -->
    <div
      class="hover-detail"
      v-if="hoverBlock"
      :style="{ left: hoverPosition.x + 'px', top: hoverPosition.y + 'px' }"
      @click.stop
    >
      <div class="hd-arrow"></div>
      <div class="hd-row"><span class="hd-label">航班号</span><strong>{{ hoverBlock.flight }}</strong></div>
      <div class="hd-row"><span class="hd-label">机型</span>{{ hoverBlock.ac_type }} / {{ hoverBlock.tail_no }}</div>
      <div class="hd-row">
        <span class="hd-label">阶段</span>
        <span class="ops-badge" :class="'ops-' + (hoverBlock.ops_type || 'arrival')">{{ hoverBlock.ops_label || '仅到达' }}</span>
      </div>
      <div class="hd-row">
        <span class="hd-label">方向</span>
        <span class="dir-badge" :class="'dir-' + hoverBlock.direction">{{ hoverBlock.direction === 'arrival' ? '↓ 降落' : '↑ 起飞' }}</span>
      </div>
      <div class="hd-row"><span class="hd-label">航线</span>{{ hoverBlock.from }} → {{ hoverBlock.to }}</div>
      <div class="hd-row"><span class="hd-label">跑道</span>跑道 {{ hoverBlock.runway || '?' }} | 滑入 {{ hoverBlock.taxi_in || 0 }}min / 滑出 {{ hoverBlock.taxi_out || 0 }}min</div>
      <div class="hd-row"><span class="hd-label">登机口占用</span>{{ hoverBlock.start_time }} ~ {{ hoverBlock.end_time }}</div>
      <div class="hd-row"><span class="hd-label">占用时长</span>{{ hoverBlock.end_min - hoverBlock.start_min }} 分钟</div>
    </div>

    <div class="dragRectBottom"></div>
    </template>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="登机口分配" />
  </div>
</template>

<script>
import api from '@/api'
import ChartOverlay from '@/components/ChartOverlay'
import { buildGateCharts } from '@/utils/charts/gateView'

export default {
  components: { ChartOverlay },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      filteredReady: false,
      airport: '成都',
      algorithm: 'bipartite',
      date: '',
      dates: [],
      airportOptions: ['成都', '北京', '上海', '广州', '重庆', '深圳'],
      gates: [],
      conflicts: [],
      conflictCount: 0,
      stats: {},
      compareData: null,
      hoverBlock: null,
      hoverPosition: { x: 0, y: 0 },
      loading: false,
      compareLoading: false,
      startHour: 5,
      pxPerMin: 0.7,
    }
  },
  computed: {
    displayGates() {
      return this.gates.filter(g => g.assigned_flights.length > 0).slice(0, 20)
    },
    timelinePx() {
      return (24 - this.startHour) * 60 * this.pxPerMin
    },
  },
  methods: {
    openCharts() {
      this.chartList = buildGateCharts(this)
      this.chartsOpen = true
    },
    _init() {
      this.checkFiltered().then(() => {
        if (this.filteredReady) {
          this.fetchAirports().then(() => {
            this.assignGates()
          })
        }
      })
    },
    async checkFiltered() {
      try {
        const resp = await fetch('/api/flights/status')
        const json = await resp.json()
        this.filteredReady = json.data && json.data.filtered_mode
      } catch (e) { this.filteredReady = false }
    },
    async fetchAirports() {
      try {
        this.airportOptions = await api.getAirportNames()
      } catch (e) {
        this.airportOptions = ['成都', '北京', '上海', '广州', '重庆', '深圳']
      }
    },
    async assignGates() {
      this.loading = true
      this.compareData = null
      try {
        const d = this.date || null
        const result = await api.assignGates(this.airport, this.algorithm, d)
        this.gates = result.gates || []
        this.conflicts = result.conflicts || []
        this.conflictCount = result.conflict_count || 0
        this.stats = result.stats || {}
        this.dates = result.dates || []
        this.$message.success(`${this.airport} 登机口分配完成`)
      } catch (e) {
        this.$message.error('分配失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    async compareGates() {
      this.compareLoading = true
      try {
        const d = this.date || null
        this.compareData = await api.compareGates(this.airport, d)
        this.$message.success(`算法对比完成: ${this.compareData.flight_count} 航班`)
      } catch (e) {
        this.$message.error('对比失败: ' + e.message)
      } finally {
        this.compareLoading = false
      }
    },
    onAirportChange() {
      this.date = ''
      this.compareData = null
      this.assignGates()
    },
    onDateChange() {
      this.assignGates()
    },
    blockStyle(f, idx) {
      const dayMin = f.start_min % 1440
      const baseMin = dayMin < this.startHour * 60 ? dayMin + 1440 : dayMin
      
      const left = (baseMin - this.startHour * 60) * this.pxPerMin
      const endDayMin = f.end_min % 1440
      const endBaseMin = endDayMin < this.startHour * 60 ? endDayMin + 1440 : endDayMin
      const width = Math.max(28, (endBaseMin - baseMin) * this.pxPerMin)
      // 方向决定底色：降落蓝、起飞绿
      const bg = f.direction === 'arrival'
        ? 'hsla(200, 65%, 50%, 0.75)'
        : 'hsla(140, 50%, 45%, 0.70)'
      return {
        left: Math.max(0, left) + 'px',
        width: width + 'px',
        background: bg,
      }
    },
    typeLabel(type) {
      return { large: '大', medium: '中', small: '小' }[type] || type
    },
    onBlockClick(f, event) {
      if (this.hoverBlock === f) {
        this.hoverBlock = null
        return
      }
      this.hoverBlock = f
      const rect = event.currentTarget.getBoundingClientRect()
      this.hoverPosition = {
        x: rect.left + rect.width / 2,
        y: rect.top,
      }
    },
    _onDocClick(e) {
      // 点击浮窗外部时关闭
      if (this.hoverBlock && !e.target.closest('.block') && !e.target.closest('.hover-detail')) {
        this.hoverBlock = null
      }
    },
  },
  mounted() {
    this._init()
    document.addEventListener('click', this._onDocClick, true)
  },
  beforeDestroy() {
    document.removeEventListener('click', this._onDocClick, true)
  },
  activated() { this._init() },
};

</script>

<style scoped>
#gate-view {
  border: 0.5px solid rgba(255,255,255,0.2);
  position: relative;
  background: rgba(255,255,255,0.1);
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  gap: 8px;
  flex-shrink: 0;
}
.toolbar h2 { font-size: 16px; margin: 0; white-space: nowrap; }
.controls { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.hint-tip { font-size: 11px; color: #888; margin-left: 4px; }
.controls .info { font-size: 12px; color: #f5d0a9; margin-left: 8px; }

.stats-bar {
  display: flex;
  gap: 20px;
  padding: 4px 12px;
  font-size: 12px;
  background: rgba(0,0,0,0.2);
  flex-shrink: 0;
}

.conflict-area {
  padding: 4px 12px;
  flex-shrink: 0;
}
.conflict-list {
  margin-top: 4px;
  font-size: 11px;
  color: #f56;
}
.conflict-item { padding: 1px 0; }

.compare-panel {
  padding: 10px 12px;
  border-top: 1px solid rgba(255,255,255,0.2);
  flex-shrink: 0;
  font-size: 12px;
}
.compare-panel h3 { font-size: 13px; margin-bottom: 6px; }
.compare-panel table { width: 100%; border-collapse: collapse; }
.compare-panel th, .compare-panel td {
  padding: 3px 8px;
  border: 1px solid rgba(255,255,255,0.15);
  text-align: center;
}
.compare-panel th { background: rgba(0,0,0,0.3); }
.has-conflict { color: #f56; font-weight: bold; }

.timeline-container {
  flex: 1;
  overflow: auto;
  padding: 4px 12px;
  min-height: 0;
}
.timeline-body { min-width: 600px; }
.gate-row {
  display: flex;
  margin-bottom: 3px;
  min-height: 28px;
  align-items: flex-start;
}
.gate-label {
  width: 80px;
  flex-shrink: 0;
  font-size: 11px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-top: 2px;
}
.gate-name { color: #f5d0a9; }
.gate-type-tag {
  font-size: 9px;
  padding: 0 3px;
  border-radius: 3px;
  align-self: flex-start;
}
.gate-type-tag.large { background: rgba(220,80,80,0.5); }
.gate-type-tag.medium { background: rgba(43,196,243,0.5); }
.gate-type-tag.small { background: rgba(120,200,120,0.5); }
.gate-rwy-tag {
  font-size: 8px;
  padding: 0 3px;
  border-radius: 3px;
  background: rgba(255,200,100,0.3);
  color: #fd8;
  align-self: flex-start;
}

.gate-timeline {
  flex: 1;
  position: relative;
  height: 26px;
  background: rgba(0,0,0,0.15);
  border-radius: 3px;
}
.block {
  position: absolute;
  top: 3px;
  height: 20px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  white-space: nowrap;
  padding: 0 3px;
  min-width: 28px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.block:hover { transform: scaleY(1.25); box-shadow: 0 0 8px rgba(255,255,255,0.4); }
.block.active { transform: scaleY(1.25); box-shadow: 0 0 12px rgba(255,255,255,0.6); border: 1px solid #fff; }
.blk-no { font-size: 8px; font-weight: bold; color: #fff; }

.empty-tip {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 14px;
}

.hover-detail {
  position: fixed;
  transform: translate(-50%, calc(-100% - 12px));
  z-index: 9999;
  padding: 10px 14px;
  background: rgba(20, 22, 30, 0.95);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #ccc;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  min-width: 220px;
  pointer-events: auto;
}
.hd-arrow {
  position: absolute;
  bottom: -7px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 7px solid rgba(20, 22, 30, 0.95);
}
.hd-row { display: flex; align-items: center; gap: 6px; }
.hd-label { color: #888; font-size: 11px; min-width: 64px; }
.hd-row strong { color: #f5d0a9; }
.dir-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
}
.dir-badge.dir-arrival { background: rgba(43,196,243,0.3); color: #7df; }
.dir-badge.dir-departure { background: rgba(76,175,80,0.3); color: #7f7; }
.ops-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
}
.ops-badge.ops-arrival { background: rgba(43,196,243,0.25); color: #7df; }
.ops-badge.ops-departure { background: rgba(76,175,80,0.25); color: #7f7; }
.ops-badge.ops-turnaround { background: rgba(255,160,60,0.25); color: #f90; }

.dragRectTop, .dragRectBottom {
  width: 100%; height: 10px; position: absolute; left: 0;
}
.dragRectTop { top: 0; }
.dragRectBottom { bottom: 0; }
.dragRectTop::before, .dragRectBottom::before {
  content: ""; width: 10px; height: 10px; border-left: 2px solid skyblue; display: block; position: absolute; left: 0;
}
.dragRectTop::before { border-top: 2px solid skyblue; top: 0; }
.dragRectBottom::before { border-bottom: 2px solid skyblue; bottom: 0; }
.dragRectTop::after, .dragRectBottom::after {
  content: ""; width: 10px; height: 10px; border-right: 2px solid skyblue; display: block; position: absolute; right: 0;
}
.dragRectTop::after { border-top: 2px solid skyblue; top: 0; }
.dragRectBottom::after { border-bottom: 2px solid skyblue; bottom: 0; }
</style>
