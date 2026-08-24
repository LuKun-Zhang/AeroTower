<template>
  <div class="heatmap-panel">
    <div class="panel-header" @click="open = !open">
      <span>🔥 路段拥堵热力图</span>
      <span class="toggle">{{ open ? '▼' : '▲' }}</span>
    </div>
    <div class="panel-body" v-if="open">
      <div class="toggle-row">
        <span class="toggle-label">热力图覆盖</span>
        <button class="toggle-btn" :class="{ active: enabled }" @click="$emit('toggle')">
          {{ enabled ? 'ON' : 'OFF' }}
        </button>
      </div>

      <div class="legend">
        <div class="leg-item"><span class="leg-dot" style="background:#4caf50"></span>畅通</div>
        <div class="leg-item"><span class="leg-dot" style="background:#ffeb3b"></span>轻度</div>
        <div class="leg-item"><span class="leg-dot" style="background:#ff9800"></span>中度</div>
        <div class="leg-item"><span class="leg-dot" style="background:#f44336"></span>拥堵</div>
      </div>

      <div class="sec-title" v-if="topCongested.length">拥堵 TOP5</div>
      <div v-for="item in topCongested" :key="item.idx" class="cong-row">
        <span class="cong-name">#{{ item.idx }}</span>
        <div class="cong-bar-wrap">
          <div class="cong-bar" :style="{ width: (item.density * 100).toFixed(0) + '%', background: densityColor(item.density) }"></div>
        </div>
        <span class="cong-pct">{{ (item.density * 100).toFixed(0) }}%</span>
      </div>
      <div v-if="!topCongested.length && enabled" class="empty">当前无拥堵路段</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CongestionHeatmap',
  props: {
    enabled: { type: Boolean, default: false },
    levels: { type: Array, default: () => [] },
    corridorLabels: { type: Array, default: () => [] },
  },
  emits: ['toggle'],
  data() {
    return { open: true }
  },
  computed: {
    topCongested() {
      return [...this.levels]
        .filter(l => l.density > 0.05)
        .sort((a, b) => b.density - a.density)
        .slice(0, 5)
    },
  },
  methods: {
    densityColor(d) {
      if (d > 0.85) return '#f44336'
      if (d > 0.6) return '#ff9800'
      if (d > 0.3) return '#ffeb3b'
      return '#4caf50'
    },
  },
}
</script>

<style scoped>
.heatmap-panel {
  background: #1e1e2e;
  border: 1px solid #313145;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  overflow: hidden;
}
.panel-header {
  padding: 6px 10px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  color: #cdd6f4;
  font-weight: 600;
  user-select: none;
}
.panel-header:hover { background: #252538; }
.toggle { color: #8a8aaa; font-size: 10px; }
.panel-body { padding: 6px 10px 10px; }
.toggle-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.toggle-label { color: #a0b0e0; font-weight: 600; }
.toggle-btn {
  padding: 2px 14px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  background: #555;
  color: #999;
}
.toggle-btn.active { background: #f44336; color: #fff; }

.legend { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.leg-item { display: flex; align-items: center; gap: 3px; color: #8a8aaa; font-size: 10px; }
.leg-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; }

.sec-title { color: #a0b0e0; font-weight: 600; margin-bottom: 4px; font-size: 11px; }
.cong-row {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 3px;
}
.cong-name { color: #cdd6f4; font-size: 10px; min-width: 24px; }
.cong-bar-wrap { flex: 1; height: 6px; background: #2d2d44; border-radius: 3px; overflow: hidden; }
.cong-bar { height: 100%; border-radius: 3px; transition: width 0.3s; }
.cong-pct { color: #8a8aaa; font-size: 10px; min-width: 30px; text-align: right; }
.empty { color: #6a6a8a; text-align: center; padding: 6px; font-size: 10px; }
</style>
