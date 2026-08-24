<template>
  <div class="gate-ctrl-panel">
    <div class="panel-header" @click="open = !open">
      <span>🚪 闸门控制</span>
      <span class="toggle">{{ open ? '▼' : '▲' }}</span>
    </div>
    <div class="panel-body" v-if="open">
      <!-- 入口 -->
      <div class="section" v-if="entryGates.length">
        <div class="sec-title">入口 ({{ openEntryCount }}/{{ entryGates.length }})</div>
        <div v-for="g in entryGates" :key="g.name" class="gate-row">
          <span class="gate-name">{{ g.name }}</span>
          <span class="gate-status" :class="gateStatus(g.name)">{{ gateStatus(g.name) === 'open' ? '开启' : '关闭' }}</span>
          <button class="gate-btn" :class="gateStatus(g.name)"
            @click="$emit('toggleGate', g.name)">{{ gateStatus(g.name) === 'open' ? '关闭' : '开启' }}</button>
        </div>
      </div>

      <!-- 出口 -->
      <div class="section" v-if="exitGates.length">
        <div class="sec-title">出口 ({{ openExitCount }}/{{ exitGates.length }})</div>
        <div v-for="g in exitGates" :key="g.name" class="gate-row">
          <span class="gate-name">{{ g.name }}</span>
          <span class="gate-status" :class="gateStatus(g.name)">{{ gateStatus(g.name) === 'open' ? '开启' : '关闭' }}</span>
          <button class="gate-btn" :class="gateStatus(g.name)"
            @click="$emit('toggleGate', g.name)">{{ gateStatus(g.name) === 'open' ? '关闭' : '开启' }}</button>
        </div>
      </div>

      <!-- 登机口 -->
      <div class="section" v-if="boardingGates.length">
        <div class="sec-title">登机口 ({{ openBoardingCount }}/{{ boardingGates.length }})</div>
        <div v-for="g in boardingGates.slice(0, 8)" :key="g.name" class="gate-row">
          <span class="gate-name">{{ g.name }}</span>
          <span class="gate-status" :class="gateStatus(g.name)">{{ gateStatus(g.name) === 'open' ? '开启' : '关闭' }}</span>
          <button class="gate-btn" :class="gateStatus(g.name)"
            @click="$emit('toggleGate', g.name)">{{ gateStatus(g.name) === 'open' ? '关闭' : '开启' }}</button>
        </div>
        <div v-if="boardingGates.length > 8" class="more-hint">...还有 {{ boardingGates.length - 8 }} 个登机口</div>
      </div>

      <!-- 路段控制 -->
      <div class="section" v-if="corridorList.length">
        <div class="sec-title">路段控制</div>
        <div v-for="c in corridorList" :key="c.idx" class="gate-row">
          <span class="gate-name">{{ c.label }}</span>
          <span class="gate-status" :class="c.blocked ? 'closed' : 'open'">{{ c.blocked ? '封锁' : '通行' }}</span>
          <button class="gate-btn" :class="c.blocked ? 'closed' : 'open'"
            @click="$emit('toggleCorridor', c.idx, !c.blocked)">{{ c.blocked ? '解封' : '封锁' }}</button>
        </div>
      </div>

      <div class="batch-btns">
        <button class="batch-btn open-all" @click="$emit('setAllGates', 'open')">全部开启</button>
        <button class="batch-btn close-all" @click="$emit('setAllGates', 'closed')">全部关闭</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GateControlPanel',
  props: {
    entryGates: { type: Array, default: () => [] },
    exitGates: { type: Array, default: () => [] },
    boardingGates: { type: Array, default: () => [] },
    gateStates: { type: Object, default: () => ({}) },
    corridorList: { type: Array, default: () => [] },
  },
  emits: ['toggleGate', 'toggleCorridor', 'setAllGates'],
  data() {
    return { open: true }
  },
  computed: {
    openEntryCount() { return this.entryGates.filter(g => this.gateStatus(g.name) === 'open').length },
    openExitCount() { return this.exitGates.filter(g => this.gateStatus(g.name) === 'open').length },
    openBoardingCount() { return this.boardingGates.filter(g => this.gateStatus(g.name) === 'open').length },
  },
  methods: {
    gateStatus(name) {
      const gs = this.gateStates[name]
      return gs ? gs.status : 'open'
    },
  },
}
</script>

<style scoped>
.gate-ctrl-panel {
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
.panel-body { padding: 4px 8px 8px; max-height: 400px; overflow-y: auto; }
.section { margin-bottom: 6px; }
.sec-title { color: #a0b0e0; font-weight: 600; margin-bottom: 3px; font-size: 11px; }
.gate-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  border-radius: 3px;
}
.gate-row:hover { background: #252538; }
.gate-name { color: #cdd6f4; flex: 1; font-size: 11px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gate-status { font-size: 10px; min-width: 30px; text-align: center; font-weight: 600; }
.gate-status.open { color: #4caf50; }
.gate-status.closed { color: #f44336; }
.gate-btn {
  padding: 1px 8px;
  border-radius: 3px;
  border: none;
  cursor: pointer;
  font-size: 10px;
  font-weight: 600;
  min-width: 32px;
}
.gate-btn.open { background: #f44336; color: #fff; }
.gate-btn.closed { background: #4caf50; color: #fff; }
.gate-btn:hover { opacity: 0.85; }
.more-hint { color: #6a6a8a; font-size: 10px; padding: 2px 6px; }
.batch-btns { display: flex; gap: 4px; margin-top: 6px; }
.batch-btn {
  flex: 1;
  padding: 4px;
  border-radius: 4px;
  border: 1px solid #444;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
}
.open-all { background: #4caf50; color: #fff; border-color: #4caf50; }
.close-all { background: #f44336; color: #fff; border-color: #f44336; }
.batch-btn:hover { opacity: 0.85; }
</style>
