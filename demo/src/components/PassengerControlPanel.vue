<template>
  <div class="pax-ctrl-panel">
    <div class="panel-header" @click="open = !open">
      <span>👥 旅客流量控制</span>
      <span class="toggle">{{ open ? '▼' : '▲' }}</span>
    </div>
    <div class="panel-body" v-if="open">
      <div class="ctrl-item">
        <label>入港旅客 <span class="val">{{ paxParams.inboundRate }} 人/min</span></label>
        <input type="range" min="1" max="30" :value="paxParams.inboundRate"
          @input="$emit('update', { ...paxParams, inboundRate: Number($event.target.value) })" />
      </div>
      <div class="ctrl-item">
        <label>离港旅客 <span class="val">{{ paxParams.outboundRate }} 人/min</span></label>
        <input type="range" min="1" max="30" :value="paxParams.outboundRate"
          @input="$emit('update', { ...paxParams, outboundRate: Number($event.target.value) })" />
      </div>
      <div class="ctrl-item">
        <label>中转比例 <span class="val">{{ (paxParams.transitRatio * 100).toFixed(0) }}%</span></label>
        <input type="range" min="0" max="30" :value="paxParams.transitRatio * 100"
          @input="$emit('update', { ...paxParams, transitRatio: Number($event.target.value) / 100 })" />
      </div>
      <div class="ctrl-item">
        <label>客座率 <span class="val">{{ (paxParams.loadFactor * 100).toFixed(0) }}%</span></label>
        <input type="range" min="30" max="100" :value="paxParams.loadFactor * 100"
          @input="$emit('update', { ...paxParams, loadFactor: Number($event.target.value) / 100 })" />
      </div>
      <button class="reset-btn" @click="$emit('reset')">重置默认</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PassengerControlPanel',
  props: {
    paxParams: { type: Object, default: () => ({ inboundRate: 10, outboundRate: 6, transitRatio: 0.05, loadFactor: 0.78 }) },
  },
  emits: ['update', 'reset'],
  data() {
    return { open: true }
  },
}
</script>

<style scoped>
.pax-ctrl-panel {
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
.ctrl-item { margin-bottom: 8px; }
.ctrl-item label {
  display: flex;
  justify-content: space-between;
  color: #a0b0e0;
  margin-bottom: 3px;
  font-weight: 500;
}
.val { color: #409eff; font-weight: 700; }
.ctrl-item input[type="range"] {
  width: 100%;
  height: 4px;
  -webkit-appearance: none;
  background: #2d2d44;
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.ctrl-item input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #409eff;
  cursor: pointer;
}
.reset-btn {
  width: 100%;
  padding: 5px;
  background: #2d2d44;
  color: #8a8aaa;
  border: 1px solid #444;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
}
.reset-btn:hover { background: #3d3d5c; color: #cdd6f4; }
</style>
