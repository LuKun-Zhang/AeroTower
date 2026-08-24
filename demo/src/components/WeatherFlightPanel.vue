<template>
  <div class="weather-flight-panel">
    <div class="wfp-title">
      天气航班调整
      <span class="wfp-count" v-if="adjusted.length">({{ adjusted.length }})</span>
    </div>

    <div class="wfp-list" v-if="adjusted.length">
      <div
        class="wfp-item"
        :class="'t-' + f.weather_disruption"
        v-for="f in adjusted"
        :key="f.flight_id"
      >
        <div class="wfp-row1">
          <span class="wfp-tag">{{ f.weather_disruption === 'cancel' ? '取消' : '延误' }}</span>
          <span class="wfp-no">{{ f.flight_no || f.flight_id }}</span>
          <span class="wfp-route">{{ f.departure_airport }} → {{ f.arrival_airport }}</span>
        </div>
        <div class="wfp-row2">
          <span class="wfp-time">{{ formatDep(f.scheduled_dep) }}</span>
          <span class="wfp-delay" v-if="f.weather_disruption === 'delay'">+{{ f.delay_minutes }}min</span>
          <span class="wfp-reason">{{ f.delay_reason }}</span>
        </div>
      </div>
    </div>

    <div class="wfp-empty" v-else>暂无天气影响的航班</div>
  </div>
</template>

<script>
export default {
  name: 'WeatherFlightPanel',
  props: {
    // 来自 SimMapView 的实时航班快照（每 500ms 轮询更新）
    flights: { type: Array, default: () => [] },
  },
  computed: {
    adjusted() {
      // 只保留因天气被延误或取消的航班；天气恢复后 weather_disruption 变回 null，自动移出面板
      return (this.flights || []).filter(f => f && f.weather_disruption)
    },
  },
  methods: {
    formatDep(dep) {
      if (!dep || !dep.length || dep.length < 5) return '--'
      const mm = String(dep[1]).padStart(2, '0')
      const dd = String(dep[2]).padStart(2, '0')
      const hh = String(dep[3]).padStart(2, '0')
      const mi = String(dep[4]).padStart(2, '0')
      return `${mm}-${dd} ${hh}:${mi}`
    },
  },
}
</script>

<style scoped>
.weather-flight-panel {
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 8px 10px;
  color: #d0d4e0;
  font-size: 12px;
}
.wfp-title {
  font-weight: 700;
  font-size: 13px;
  color: #ff9800;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.wfp-count { color: #ffb74d; font-weight: 600; }
.wfp-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 300px;
  overflow-y: auto;
}
.wfp-list::-webkit-scrollbar { width: 4px; }
.wfp-list::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }

.wfp-item {
  padding: 4px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  border-left: 3px solid #ff9800;
}
.wfp-item.t-cancel { border-left-color: #f44336; }
.wfp-item.t-delay { border-left-color: #ff9800; }

.wfp-row1 {
  display: flex;
  align-items: center;
  gap: 6px;
}
.wfp-tag {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: 8px;
  font-weight: 700;
  font-size: 11px;
  background: rgba(255, 152, 0, 0.2);
  color: #ff9800;
}
.t-cancel .wfp-tag {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
}
.wfp-no { font-weight: 600; color: #e6ebff; }
.wfp-route { color: #8a8da0; }

.wfp-row2 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 11px;
  color: #6a6a8a;
}
.wfp-delay { color: #ff9800; font-weight: 600; }
.t-cancel .wfp-delay { color: #f44336; }
.wfp-reason {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.wfp-empty {
  color: #6a6a8a;
  text-align: center;
  padding: 12px 0;
}
</style>
