<template>
  <div class="metric-wrap">
    <div class="metric-grid">
      <div v-for="m in primary" :key="m.key" class="metric-card">
        <div class="mc-value">{{ fmt(values[m.key], m.unit) }}</div>
        <div class="mc-label">{{ m.label }}</div>
      </div>
    </div>
    <div class="metric-grid secondary">
      <div v-for="m in secondary" :key="m.key" class="metric-card small">
        <div class="mc-value">{{ fmt(values[m.key], m.unit) }}</div>
        <div class="mc-label">{{ m.label }}</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MetricCards',
  props: { values: { type: Object, default: () => ({}) } },
  data() {
    return {
      primary: [
        { key: 'total_flights', label: '计划航班数' },
        { key: 'on_time_rate', label: '全程准点率', unit: '%' },
        { key: 'completion_rate', label: '完成率', unit: '%' },
        { key: 'cancelled_count', label: '取消航班' },
        { key: 'delayed_count', label: '延误航班' },
        { key: 'avg_delay_min', label: '平均延误', unit: ' 分钟' },
      ],
      secondary: [
        { key: 'aircraft_utilization', label: '飞机利用率', unit: '%' },
        { key: 'runway_avg_delay_min', label: '跑道平均延误', unit: ' 分钟' },
        { key: 'gate_avg_utilization', label: '登机口利用率', unit: '%' },
        { key: 'crew_coverage', label: '机组覆盖率', unit: '%' },
      ],
    }
  },
  methods: {
    fmt(value, unit) {
      if (value === null || value === undefined || value === '') return '—'
      return `${value}${unit || ''}`
    },
  },
}
</script>

<style scoped>
.metric-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.metric-grid.secondary { grid-template-columns: repeat(4, 1fr); margin-top: 10px; }
.metric-card {
  background: #1e1e2e; border: 1px solid #2d2d44; border-radius: 8px;
  padding: 12px 10px; text-align: center;
}
.metric-card.small { padding: 9px 8px; }
.mc-value { font-size: 22px; color: #ffd54f; font-weight: 500; }
.metric-card.small .mc-value { font-size: 17px; color: #cdd6f4; }
.mc-label { font-size: 11px; color: #7a7a9a; margin-top: 4px; }
@media (max-width: 1100px) {
  .metric-grid { grid-template-columns: repeat(3, 1fr); }
  .metric-grid.secondary { grid-template-columns: repeat(2, 1fr); }
}
</style>
