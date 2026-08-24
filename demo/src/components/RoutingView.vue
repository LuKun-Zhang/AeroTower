<template>
  <div id="routing-view">
    <div class="dragRectTop"></div>

    <div class="toolbar">
      <h2>🛫 飞机排班</h2>
      <div class="controls">
        <el-select v-model="algorithm" size="small" style="width:140px">
          <el-option label="二分图匹配" value="bipartite" />
          <el-option label="贪心算法" value="greedy" />
        </el-select>
        <el-button type="primary" size="small" @click="runRouting">一键排班</el-button>
        <el-button size="small" @click="compareRouting">算法对比</el-button>
      </div>
    </div>

    <!-- 统计指标 -->
    <div class="stats-bar" v-if="stats">
      <span>飞机数: <b>{{ stats.aircraft_count }}</b></span>
      <span>航班覆盖: <b>{{ stats.coverage }}%</b></span>
      <span>平均利用率: <b>{{ stats.avg_utilization }}%</b></span>
      <span>总空闲: <b>{{ stats.total_idle_time_minutes }}min</b></span>
    </div>

    <!-- 甘特图 -->
    <div class="gantt-container" v-if="aircrafts.length > 0">
      <div class="gantt-header">
        <div class="gantt-label-col">飞机</div>
        <div class="gantt-time-axis">
          <span v-for="h in timeLabels" :key="h" :style="{left: h * hourWidth + 'px'}">{{ h }}:00</span>
        </div>
      </div>
      <div class="gantt-body">
        <div class="gantt-row" v-for="ac in displayAircrafts" :key="ac.ac_id">
          <div class="gantt-label-col">
            <div class="ac-label">{{ ac.tail_no }}</div>
            <div class="ac-sub">{{ ac.ac_type }}</div>
          </div>
          <div class="gantt-timeline">
            <div
              v-for="(f, idx) in ac.assigned_flights"
              :key="idx"
              class="flight-block"
              :style="getBlockStyle(f)"
              :title="`${f.flight_no}: ${f.departure_airport}→${f.arrival_airport} (${f.time_departure} - ${f.time_arrival})`"
            >
              <span class="block-label">{{ f.flight_no }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 对比面板 -->
    <div v-if="compareData" class="compare-panel">
      <h3>算法对比</h3>
      <table>
        <tr>
          <th>指标</th>
          <th>二分图匹配</th>
          <th>贪心算法</th>
        </tr>
        <tr>
          <td>所需飞机数</td>
          <td>{{ compareData.bipartite.stats.aircraft_count }}</td>
          <td>{{ compareData.greedy.stats.aircraft_count }}</td>
        </tr>
        <tr>
          <td>利用率</td>
          <td>{{ compareData.bipartite.stats.avg_utilization }}%</td>
          <td>{{ compareData.greedy.stats.avg_utilization }}%</td>
        </tr>
        <tr>
          <td>空闲时间</td>
          <td>{{ compareData.bipartite.stats.total_idle_time_minutes }}min</td>
          <td>{{ compareData.greedy.stats.total_idle_time_minutes }}min</td>
        </tr>
      </table>
    </div>

    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import api from '@/api'

export default {
  data() {
    return {
      algorithm: 'bipartite',
      aircrafts: [],
      stats: null,
      compareData: null,
      startHour: 5,
      endHour: 24,
    }
  },
  computed: {
    displayAircrafts() {
      // 只显示有任务的飞机，最多15架
      return this.aircrafts.filter(a => a.assigned_flights.length > 0).slice(0, 15)
    },
    timeLabels() {
      const labels = []
      for (let h = this.startHour; h <= this.endHour; h++) {
        labels.push(h)
      }
      return labels
    },
    hourWidth() {
      return 38
    },
  },
  methods: {
    async runRouting() {
      try {
        const result = await api.runRouting(this.algorithm)
        this.aircrafts = result.aircrafts || []
        this.stats = result.stats || null
        this.compareData = null
        this.$message.success(`排班完成: ${this.stats.aircraft_count} 架飞机`)
      } catch (e) {
        this.$message.error('排班失败: ' + e.message)
      }
    },
    async compareRouting() {
      try {
        const result = await api.compareRouting()
        this.compareData = result
        this.$message.success('算法对比完成')
      } catch (e) {
        this.$message.error('对比失败: ' + e.message)
      }
    },
    getBlockStyle(flight) {
      // 从 time_departure 和 time_arrival 字符串解析小时
      const depMatch = flight.time_departure.match(/(\d+):(\d+)/)
      const arrMatch = flight.time_arrival.match(/(\d+):(\d+)/)
      if (!depMatch || !arrMatch) return {}

      const depH = parseInt(depMatch[1]), depM = parseInt(depMatch[2])
      const arrH = parseInt(arrMatch[1]), arrM = parseInt(arrMatch[2])

      const left = ((depH - this.startHour) * 60 + depM) * (this.hourWidth / 60)
      const width = Math.max(
        ((arrH - depH) * 60 + (arrM - depM)) * (this.hourWidth / 60),
        30
      )

      // 颜色根据航班号
      const hue = (flight.flight_no.charCodeAt(flight.flight_no.length - 1) * 37) % 360
      return {
        left: left + 'px',
        width: width + 'px',
        background: `hsl(${hue}, 60%, 55%)`,
      }
    },
  },
  mounted() {
    // 自动加载当前排班
    this.runRouting()
    // 监听恢复执行完成事件，自动刷新排班
    this.$root.$on('filter-needs-refresh', this.runRouting)
  },
  beforeDestroy() {
    this.$root.$off('filter-needs-refresh', this.runRouting)
  },
}
</script>

<style scoped>
#routing-view {
  border: 0.5px solid rgba(255,255,255,0.2);
  position: relative;
  background: rgba(255,255,255,0.1);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  gap: 8px;
}
.toolbar h2 {
  font-size: 16px;
  margin: 0;
  white-space: nowrap;
}
.controls {
  display: flex;
  gap: 6px;
  align-items: center;
}

.stats-bar {
  display: flex;
  gap: 20px;
  padding: 6px 12px;
  font-size: 12px;
  background: rgba(0,0,0,0.2);
  border-top: 1px solid rgba(255,255,255,0.1);
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.stats-bar b {
  color: #f5d0a9;
}

.gantt-container {
  flex: 1;
  overflow: auto;
  font-size: 11px;
}
.gantt-header {
  display: flex;
  border-bottom: 1px solid rgba(255,255,255,0.2);
  position: sticky;
  top: 0;
  background: rgba(0,0,0,0.4);
  z-index: 1;
}
.gantt-label-col {
  width: 70px;
  min-width: 70px;
  padding: 4px;
  text-align: center;
  border-right: 1px solid rgba(255,255,255,0.2);
}
.gantt-time-axis {
  flex: 1;
  position: relative;
  height: 20px;
}
.gantt-time-axis span {
  position: absolute;
  font-size: 9px;
  color: #888;
  transform: translateX(-50%);
}
.gantt-body {
  flex: 1;
  overflow-y: auto;
}
.gantt-row {
  display: flex;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  min-height: 36px;
}
.ac-label { color: #f5d0a9; font-weight: bold; font-size: 11px; }
.ac-sub { color: #888; font-size: 9px; }
.gantt-timeline {
  flex: 1;
  position: relative;
}
.flight-block {
  position: absolute;
  top: 4px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: opacity 0.2s;
}
.flight-block:hover { opacity: 0.8; }
.block-label {
  font-size: 9px;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
}

.compare-panel {
  padding: 12px;
  border-top: 1px solid rgba(255,255,255,0.2);
  max-height: 200px;
  overflow: auto;
}
.compare-panel h3 { font-size: 14px; margin-bottom: 8px; }
.compare-panel table { width: 100%; font-size: 12px; border-collapse: collapse; }
.compare-panel th, .compare-panel td {
  padding: 4px 8px;
  border: 1px solid rgba(255,255,255,0.2);
  text-align: center;
}
.compare-panel th { background: rgba(0,0,0,0.3); }

.dragRectTop, .dragRectBottom {
  width: 100%;
  height: 10px;
  position: absolute;
  left: 0;
}
.dragRectTop { top: 0; }
.dragRectBottom { bottom: 0; }
.dragRectTop::before, .dragRectBottom::before {
  content: "";
  width: 10px; height: 10px;
  border-left: 2px solid skyblue;
  display: block;
  position: absolute;
  left: 0;
}
.dragRectTop::before { border-top: 2px solid skyblue; top: 0; }
.dragRectBottom::before { border-bottom: 2px solid skyblue; bottom: 0; }
.dragRectTop::after, .dragRectBottom::after {
  content: "";
  width: 10px; height: 10px;
  border-right: 2px solid skyblue;
  display: block;
  position: absolute;
  right: 0;
}
.dragRectTop::after { border-top: 2px solid skyblue; top: 0; }
.dragRectBottom::after { border-bottom: 2px solid skyblue; bottom: 0; }
</style>
