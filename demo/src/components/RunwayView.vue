<template>
  <div id="runway-view">
    <div class="dragRectTop"></div>

    <div class="toolbar">
      <h2>🛬 跑道调度</h2>
      <div class="controls">
        <el-select v-model="mode" size="small" style="width:120px" @change="loadData">
          <el-option label="对比模式" value="compare" />
          <el-option label="FCFS" value="fcfs" />
          <el-option label="优化排序" value="optimized" />
        </el-select>
        <el-button type="primary" size="small" @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- 跑道时间线 -->
    <div class="timeline-container" v-if="schedule.length > 0">
      <div v-for="(runway, rIdx) in ['跑道 02L']" :key="rIdx" class="runway-lane">
        <div class="runway-label">{{ runway }}</div>
        <div class="timeline-scroll">
          <div
            v-for="(item, idx) in displayItems"
            :key="idx"
            class="timeline-item"
            :class="{ delayed: item.delay > 0 }"
            :style="getItemStyle(item, idx)"
            :title="`${item.flight_no} | 预计: ${fmtMin(item.target_time)} | 实际: ${fmtMin(item.actual_time)} | 延误: ${item.delay}min`"
          >
            <span class="item-label">{{ item.flight_no }}</span>
            <span v-if="item.delay > 0" class="delay-badge">+{{ item.delay }}</span>
          </div>

          <!-- 时间标尺 -->
          <div class="time-ruler">
            <span v-for="t in timeMarks" :key="t" :style="{left: (t - startMin) * pxPerMin + 'px'}"
              >{{ fmtMin(t) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 对比面板 -->
    <div v-if="compareResult" class="compare-panel">
      <h3>调度对比</h3>
      <table>
        <tr>
          <th>方案</th>
          <th>总延误(min)</th>
          <th>平均延误(min)</th>
        </tr>
        <tr>
          <td>FCFS (先到先服务)</td>
          <td>{{ compareResult.fcfs.total_delay }}</td>
          <td>{{ compareResult.fcfs.avg_delay }}</td>
        </tr>
        <tr>
          <td>ILS-CPS (优化排序)</td>
          <td>{{ compareResult.optimized.total_delay }}</td>
          <td>{{ compareResult.optimized.avg_delay }}</td>
        </tr>
      </table>
      <div class="improvement" v-if="compareResult.improvement > 0">
        优化改善：<b>{{ compareResult.improvement }}%</b>
      </div>
    </div>

    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import api from '@/api'

export default {
  data() {
    return {
      mode: 'compare',
      schedule: [],
      compareResult: null,
      startMin: 5 * 60,
      pxPerMin: 0.5,
    }
  },
  computed: {
    displayItems() {
      // 只显示前30个
      return this.schedule.slice(0, 30)
    },
    timeMarks() {
      const marks = []
      for (let h = 5; h <= 24; h++) {
        marks.push(h * 60)
      }
      return marks
    },
  },
  methods: {
    async loadData() {
      try {
        const result = await api.runRunway(this.mode)
        if (this.mode === 'compare') {
          this.schedule = result.fcfs.schedule
          this.compareResult = result
        } else if (this.mode === 'fcfs') {
          this.schedule = result
          this.compareResult = null
        } else {
          this.schedule = result
          this.compareResult = null
        }
      } catch (e) {
        this.$message.error('加载失败: ' + e.message)
      }
    },
    getItemStyle(item) {
      const left = (item.target_time - this.startMin) * this.pxPerMin
      const width = Math.max(24, 3 * this.pxPerMin)
      return {
        left: left + 'px',
        width: width + 'px',
        top: '4px',
      }
    },
    fmtMin(m) {
      const h = Math.floor(m / 60)
      const mi = m % 60
      return `${h}:${mi.toString().padStart(2, '0')}`
    },
  },
  mounted() {
    this.loadData()
  },
}
</script>

<style scoped>
#runway-view {
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
}
.toolbar h2 { font-size: 16px; margin: 0; white-space: nowrap; }
.controls { display: flex; gap: 6px; align-items: center; }

.timeline-container {
  flex: 1;
  overflow: hidden;
  padding: 8px;
}
.runway-lane {
  margin-bottom: 4px;
}
.runway-label {
  font-size: 12px;
  color: #f5d0a9;
  margin-bottom: 4px;
}
.timeline-scroll {
  position: relative;
  height: 42px;
  background: rgba(0,0,0,0.2);
  border-radius: 4px;
  overflow: hidden;
}
.timeline-item {
  position: absolute;
  height: 28px;
  border-radius: 4px;
  background: rgba(43,196,243,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.timeline-item.delayed {
  background: rgba(220,80,60,0.8);
}
.item-label {
  font-size: 9px;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
}
.delay-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  font-size: 8px;
  background: #f56;
  color: #fff;
  padding: 0 3px;
  border-radius: 6px;
}
.time-ruler {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 12px;
}
.time-ruler span {
  position: absolute;
  font-size: 8px;
  color: #666;
  transform: translateX(-50%);
}

.compare-panel {
  padding: 12px;
  border-top: 1px solid rgba(255,255,255,0.2);
  font-size: 12px;
}
.compare-panel h3 { font-size: 14px; margin-bottom: 8px; }
.compare-panel table {
  width: 100%;
  border-collapse: collapse;
}
.compare-panel th, .compare-panel td {
  padding: 4px 8px;
  border: 1px solid rgba(255,255,255,0.2);
  text-align: center;
}
.compare-panel th { background: rgba(0,0,0,0.3); }
.improvement { margin-top: 8px; color: #4caf50; }

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
