<template>
  <div class="evac-panel">
    <div class="panel-header" @click="open = !open">
      <span>🚨 应急疏散</span>
      <span class="toggle">{{ open ? '▼' : '▲' }}</span>
    </div>
    <div class="panel-body" v-if="open">
      <!-- 触发按钮 -->
      <div class="trigger-row">
        <button v-if="!active" class="trigger-btn start" @click="$emit('start', targetArea)">🚨 启动疏散</button>
        <button v-else class="trigger-btn stop" @click="$emit('stop')">⏹ 停止疏散</button>
      </div>

      <!-- 疏散范围 -->
      <div class="section">
        <div class="sec-title">疏散范围</div>
        <div class="radio-group">
          <label class="radio-item" :class="{ active: targetArea === 'T1' }">
            <input type="radio" value="T1" v-model="targetArea" :disabled="active" /> T1 航站楼
          </label>
          <label class="radio-item" :class="{ active: targetArea === 'T2' }">
            <input type="radio" value="T2" v-model="targetArea" :disabled="active" /> T2 航站楼
          </label>
          <label class="radio-item" :class="{ active: targetArea === 'all' }">
            <input type="radio" value="all" v-model="targetArea" :disabled="active" /> 全部区域
          </label>
        </div>
      </div>

      <!-- 可用出口 -->
      <div class="section">
        <div class="sec-title">可用出口 ({{ availableExits.length }})</div>
        <div class="exit-list">
          <span v-for="ex in exitGates" :key="ex" class="exit-tag"
            :class="{ open: isExitAvailable(ex), closed: !isExitAvailable(ex) }">
            {{ ex }}
          </span>
        </div>
      </div>

      <!-- 疏散状态 -->
      <div class="section" v-if="active">
        <div class="sec-title">疏散状态</div>
        <div class="stat-grid">
          <div class="stat-item">
            <span class="stat-val">{{ totalEvacuating }}</span>
            <span class="stat-lbl">在途旅客</span>
          </div>
          <div class="stat-item">
            <span class="stat-val green">{{ totalArrived }}</span>
            <span class="stat-lbl">已到达出口</span>
          </div>
        </div>
        <div class="evac-progress" v-if="totalEvac > 0">
          <div class="evac-bar">
            <div class="evac-fill" :style="{ width: evacPct + '%' }"></div>
          </div>
          <span class="evac-pct">{{ evacPct }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'EvacuationPanel',
  props: {
    active: { type: Boolean, default: false },
    totalEvacuating: { type: Number, default: 0 },
    totalArrived: { type: Number, default: 0 },
    exitGates: { type: Array, default: () => [] },
    availableExits: { type: Array, default: () => [] },
  },
  emits: ['start', 'stop'],
  data() {
    return {
      open: true,
      targetArea: 'all',
    }
  },
  computed: {
    totalEvac() { return this.totalEvacuating + this.totalArrived },
    evacPct() {
      if (this.totalEvac === 0) return 0
      return Math.round(this.totalArrived / this.totalEvac * 100)
    },
  },
  methods: {
    isExitAvailable(name) { return this.availableExits.includes(name) },
  },
}
</script>

<style scoped>
.evac-panel {
  background: #1e1e2e;
  border: 1px solid #f4433644;
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
  color: #f44336;
  font-weight: 600;
  user-select: none;
}
.panel-header:hover { background: #252538; }
.toggle { color: #8a8aaa; font-size: 10px; }
.panel-body { padding: 6px 10px 10px; }

.trigger-row { margin-bottom: 10px; }
.trigger-btn {
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
}
.trigger-btn.start { background: #f44336; color: #fff; }
.trigger-btn.stop { background: #555; color: #fff; }
.trigger-btn:hover { opacity: 0.85; }

.section { margin-bottom: 8px; }
.sec-title { color: #a0b0e0; font-weight: 600; margin-bottom: 4px; font-size: 11px; }

.radio-group { display: flex; flex-direction: column; gap: 2px; }
.radio-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border-radius: 3px;
  color: #cdd6f4;
  cursor: pointer;
  font-size: 11px;
}
.radio-item:hover { background: #252538; }
.radio-item.active { background: #f4433622; color: #f44336; }
.radio-item input { margin: 0; accent-color: #f44336; }

.exit-list { display: flex; flex-wrap: wrap; gap: 3px; }
.exit-tag {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
}
.exit-tag.open { background: #4caf5022; color: #4caf50; border: 1px solid #4caf5044; }
.exit-tag.closed { background: #f4433622; color: #f44336; border: 1px solid #f4433644; text-decoration: line-through; }

.stat-grid { display: flex; gap: 8px; margin-bottom: 6px; }
.stat-item { flex: 1; text-align: center; background: #252538; border-radius: 4px; padding: 6px 4px; }
.stat-val { display: block; font-size: 20px; font-weight: 700; color: #f44336; }
.stat-val.green { color: #4caf50; }
.stat-lbl { display: block; font-size: 10px; color: #8a8aaa; margin-top: 2px; }

.evac-progress { display: flex; align-items: center; gap: 6px; }
.evac-bar { flex: 1; height: 6px; background: #2d2d44; border-radius: 3px; overflow: hidden; }
.evac-fill { height: 100%; background: #4caf50; border-radius: 3px; transition: width 0.3s; }
.evac-pct { color: #4caf50; font-size: 11px; font-weight: 700; }
</style>
