<template>
  <div class="flight-popup-overlay" v-if="visible" @click.self="$emit('close')">
    <div class="flight-popup">
      <div class="popup-header">
        <span class="flight-no">{{ flight.flight_no }}</span>
        <span class="phase-badge" :class="'phase-' + flight.phase">{{ phaseLabel }}</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>
      <div class="popup-body">
        <div class="route-line">
          <span class="dep">{{ flight.departure_airport }}</span>
          <span class="arrow">→</span>
          <span class="arr">{{ flight.arrival_airport }}</span>
        </div>
        <div class="info-row">
          <span class="label">机型</span>
          <span class="value">{{ flight.ac_type }}</span>
        </div>
        <div class="info-row">
          <span class="label">计划出发</span>
          <span class="value">{{ formatTime(flight.scheduled_dep) }}</span>
        </div>
        <div class="info-row">
          <span class="label">计划到达</span>
          <span class="value">{{ formatTime(flight.scheduled_arr) }}</span>
        </div>
        <div class="info-row" v-if="flight.actual_dep && flight.delay_minutes > 0">
          <span class="label">实际出发</span>
          <span class="value delayed">{{ formatTime(flight.actual_dep) }}</span>
        </div>
        <div class="info-row">
          <span class="label">当前状态</span>
          <span class="value">{{ phaseLabel }}</span>
        </div>
        <div class="info-row" v-if="flight.delay_minutes > 0">
          <span class="label">延误</span>
          <span class="value delayed">{{ flight.delay_minutes }} min</span>
        </div>
        <div class="info-row" v-if="flight.delay_reason">
          <span class="label">原因</span>
          <span class="value reason">{{ flight.delay_reason }}</span>
        </div>
        <div class="info-row">
          <span class="label">进度</span>
          <div class="progress-bar">
            <div class="progress" :style="{ width: flight.progress + '%' }"></div>
          </div>
          <span class="value">{{ flight.progress }}%</span>
        </div>
        <div class="info-row" v-if="flight.passenger_count > 0">
          <span class="label">旅客</span>
          <span class="value">{{ flight.passenger_count }} 人</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
const PHASE_LABELS = {
  scheduled: '计划中', push_back: '推出', taxi_out: '滑出',
  takeoff: '起飞', climb: '爬升', cruise: '巡航',
  descent: '下降', approach: '进近', landing: '着陆',
  taxi_in: '滑入', parked: '到达', delayed: '延误', cancelled: '取消',
}
export default {
  name: 'FlightInfoPopup',
  props: {
    visible: { type: Boolean, default: false },
    flight: { type: Object, default: () => ({}) },
  },
  emits: ['close'],
  computed: {
    phaseLabel() {
      return PHASE_LABELS[this.flight.phase] || this.flight.phase || '--'
    },
  },
  methods: {
    formatTime(t) {
      if (!t || !Array.isArray(t)) return '--'
      const [y, m, d, h, mi] = t
      return `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')} ${String(h||0).padStart(2,'0')}:${String(mi||0).padStart(2,'0')}`
    },
  },
}
</script>

<style scoped>
.flight-popup-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  z-index: 2000; display: flex; align-items: flex-start; justify-content: flex-end;
  pointer-events: none;
}
.flight-popup {
  pointer-events: all;
  margin: 80px 20px 0 0;
  background: #1e1e2e; border: 1px solid #313145; border-radius: 8px;
  width: 280px; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.popup-header {
  display: flex; align-items: center; padding: 10px 12px;
  border-bottom: 1px solid #313145; gap: 8px;
}
.flight-no { font-size: 16px; font-weight: 700; color: #cdd6f4; }
.phase-badge {
  padding: 2px 8px; border-radius: 10px; font-size: 11px;
  margin-left: auto;
}
.phase-cruise, .phase-climb, .phase-descent { background: #1976d2; color: #fff; }
.phase-parked { background: #4caf50; color: #fff; }
.phase-delayed { background: #ff9800; color: #fff; }
.phase-cancelled { background: #f44336; color: #fff; }
.phase-scheduled, .phase-push_back, .phase-taxi_out, .phase-taxi_in,
.phase-takeoff, .phase-approach, .phase-landing { background: #555; color: #ddd; }

.close-btn {
  background: none; border: none; color: #888; cursor: pointer; font-size: 16px;
}
.close-btn:hover { color: #fff; }
.popup-body { padding: 10px 12px; }
.route-line { font-size: 18px; text-align: center; margin-bottom: 10px; color: #cdd6f4; }
.route-line .arrow { color: #888; margin: 0 8px; }
.info-row { display: flex; align-items: center; margin-bottom: 6px; }
.label { color: #8a8aaa; width: 70px; font-size: 12px; flex-shrink: 0; }
.value { color: #cdd6f4; font-size: 13px; }
.delayed { color: #ff9800; }
.reason { color: #ff5722; font-size: 11px; }
.progress-bar {
  flex: 1; height: 4px; background: #313145; border-radius: 2px; margin-right: 8px;
}
.progress { height: 100%; background: #4caf50; border-radius: 2px; }
</style>
