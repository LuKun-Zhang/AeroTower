<template>
  <div class="flight-board">
    <div class="panel-header" @click="open = !open">
      <span>✈ 航班动态</span>
      <span class="toggle">{{ open ? '▼' : '▲' }}</span>
    </div>
    <div class="panel-body" v-if="open">
      <div class="flight-list">
        <div v-for="f in flights" :key="f.flightNo" class="flight-row"
          :class="rowClass(f)"
          @click="$emit('selectFlight', f)">
          <div class="f-info">
            <span class="f-no">{{ f.flightNo }}</span>
            <span class="f-gate">{{ f.gateName }}</span>
          </div>
          <div class="f-time">{{ timeText(f) }}</div>
          <div class="f-runway" v-if="f.runway">
            <span>{{ f.runway }}</span>
            <span class="f-rw-time" v-if="f.rwStart != null && f.rwEnd != null">
              {{ formatTime(f.rwStart) }} - {{ formatTime(f.rwEnd) }}
            </span>
            <span class="f-rw-label">{{ f.type === 'departure' ? '起飞' : '降落' }}</span>
          </div>
          <div class="f-progress">
            <div class="prog-bar">
              <div class="prog-fill" :style="{ width: boardProgress(f) + '%' }"></div>
            </div>
            <span class="prog-text">
              {{ statusLabel(f) }}
              <span v-if="isDelayed(f)" class="delay-badge">延误 {{ f.delayMinutes }} min</span>
              <span v-if="f.reason" class="reason-badge">{{ f.reason }}</span>
            </span>
          </div>
        </div>
        <div v-if="!flights.length" class="empty">暂无航班数据</div>
      </div>
      <div class="board-summary">
        <div class="sum-item">
          <span class="sum-dot" style="background:#4caf50"></span>
          登机中: {{ boardingCount }}
        </div>
        <div class="sum-item">
          <span class="sum-dot" style="background:#ff9800"></span>
          等待中: {{ scheduledCount }}
        </div>
        <div class="sum-item">
          <span class="sum-dot" style="background:#2196f3"></span>
          已起飞: {{ departedCount }}
        </div>
        <div class="sum-item">
          <span class="sum-dot" style="background:#f44336"></span>
          取消: {{ cancelledCount }}
        </div>
        <div class="sum-item">
          <span class="sum-dot" style="background:#ff9800"></span>
          延误: {{ delayedCount }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FlightBoard',
  props: {
    flights: { type: Array, default: () => [] },
    simTime: { type: Number, default: 0 },
  },
  emits: ['selectFlight'],
  data() {
    return { open: true }
  },
  computed: {
    boardingCount() { return this.flights.filter(f => f.status === 'boarding').length },
    scheduledCount() { return this.flights.filter(f => f.status === 'scheduled').length },
    departedCount() { return this.flights.filter(f => f.status === 'departed').length },
    cancelledCount() { return this.flights.filter(f => f.cancelled || f.status === 'cancelled').length },
    delayedCount() { return this.flights.filter(f => this.isDelayed(f)).length },
  },
  methods: {
    formatTime(min) {
      if (min == null || isNaN(min)) return '--:--'
      const h = Math.floor(min / 60) % 24
      const m = Math.floor(min % 60)
      return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0')
    },
    isDelayed(f) {
      return !f.cancelled && (f.delayMinutes > 0 || f.disruptionType === 'delay')
    },
    rowClass(f) {
      const cls = ['status-' + (f.status || 'scheduled')]
      if (f.cancelled || f.status === 'cancelled') cls.push('is-cancelled')
      if (this.isDelayed(f)) cls.push('is-delayed')
      return cls
    },
    timeText(f) {
      const t = f.type === 'departure' ? f.scheduledDep : f.scheduledArr
      return this.formatTime(t)
    },
    boardProgress(f) {
      if (f.cancelled || f.status === 'cancelled') return 0
      if (f.status === 'departed') return 100
      if (f.status === 'scheduled') return 0
      if (!f.paxTotal) return 0
      return Math.min(100, Math.round(f.paxBoarded / f.paxTotal * 100))
    },
    statusLabel(f) {
      if (f.cancelled || f.status === 'cancelled') return '已取消'
      if (f.status === 'scheduled') return '等待中'
      if (f.status === 'boarding') return '登机中 ' + this.boardProgress(f) + '%'
      if (f.status === 'departed') return '已起飞'
      return f.status
    },
  },
}
</script>

<style scoped>
.flight-board {
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
.panel-body { padding: 4px 8px 8px; }
.flight-list { max-height: 220px; overflow-y: auto; margin-bottom: 6px; }
.flight-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  margin-bottom: 2px;
  border-radius: 4px;
  cursor: pointer;
  background: #252538;
}
.flight-row:hover { background: #2d2d44; }
.f-info { min-width: 80px; }
.f-no { color: #cdd6f4; font-weight: 700; display: block; font-size: 11px; }
.f-gate { color: #6a6a8a; font-size: 10px; }
.f-time { color: #409eff; font-weight: 600; min-width: 32px; text-align: center; font-size: 11px; }
.f-runway {
  color: #ffd54f;
  font-size: 10px;
  min-width: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.3;
}
.f-rw-time { color: #8a8aaa; font-size: 9px; }
.f-rw-label { color: #ffd54f; font-size: 9px; font-weight: 600; }
.f-progress { flex: 1; min-width: 0; }
.prog-bar {
  height: 4px;
  background: #2d2d44;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 1px;
}
.prog-fill { height: 100%; border-radius: 2px; transition: width 0.3s; }
.status-scheduled .prog-fill { background: #ff9800; }
.status-boarding .prog-fill { background: #4caf50; }
.status-departed .prog-fill { background: #2196f3; }
.status-cancelled { background: #2a2a2a; opacity: 0.55; }
.status-cancelled .f-no,
.status-cancelled .f-time { text-decoration: line-through; color: #888; }
.status-cancelled .prog-fill { background: #666; }
.is-delayed { border-left: 2px solid #ff9800; }
.is-delayed .f-time { color: #ff9800; }
.is-delayed .f-no { color: #ffb74d; }
.delay-badge { color: #ff9800; font-weight: 600; margin-left: 4px; }
.reason-badge { color: #ffb74d; font-size: 9px; margin-left: 4px; }
.prog-text { color: #8a8aaa; font-size: 10px; }

.board-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 4px;
  border-top: 1px solid #313145;
}
.sum-item { display: flex; align-items: center; gap: 3px; color: #8a8aaa; font-size: 10px; }
.sum-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.empty { color: #6a6a8a; text-align: center; padding: 10px; font-size: 11px; }
</style>
