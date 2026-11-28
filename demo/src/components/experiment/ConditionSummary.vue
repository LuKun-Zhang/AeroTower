<template>
  <div class="cond-summary">
    <div class="cs-title">运行条件</div>
    <div class="cs-grid">
      <div class="cs-item"><span>日期</span><b>{{ dates }}</b></div>
      <div class="cs-item"><span>基地</span><b>{{ bases }}</b></div>
      <div class="cs-item"><span>机队</span><b>{{ fleetText }}</b></div>
      <div class="cs-item"><span>种子</span><b>{{ seed }}</b></div>
      <div class="cs-item"><span>天气</span><b>{{ weatherText }}</b></div>
      <div class="cs-item"><span>异常</span><b>{{ anomalyText }}</b></div>
      <div class="cs-item wide"><span>算法</span><b>{{ algoText }}</b></div>
      <div class="cs-item wide"><span>客流</span><b>{{ trafficText }}</b></div>
    </div>
    <div v-if="warnings.length" class="cs-warn">
      <div v-for="(w, i) in warnings" :key="i">· {{ w }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ConditionSummary',
  props: {
    conditions: { type: Object, default: () => ({}) },
    warnings: { type: Array, default: () => [] },
  },
  computed: {
    dates() { return (this.conditions.dates || []).join(', ') },
    bases() { return (this.conditions.bases || []).join('/') },
    seed() { return this.conditions.seed },
    fleetText() {
      const f = this.conditions.fleet || {}
      const m = f.mix || {}
      return `${f.size || 0} 架（A319 ${m.A319 || 0} / A320 ${m.A320 || 0} / A321 ${m.A321 || 0}）`
    },
    weatherText() {
      const w = (this.conditions.disruption || {}).weather
      return { none: '无', sichuan_storm: '四川盆地雷暴', east_rain: '华东强降雨', south_typhoon: '华南台风' }[w] || w
    },
    anomalyText() {
      const d = this.conditions.disruption || {}
      if (d.anomaly !== 'airport_closure') return '无'
      const p = d.anomaly_params || {}
      return `${p.airport} ${p.start} ~ ${p.end}`
    },
    algoText() {
      const a = this.conditions.algorithms || {}
      return `排班 ${a.routing} · 跑道 ${a.runway} · 机位 ${a.gate} · 机组 ${a.crew}`
    },
    trafficText() {
      const t = this.conditions.traffic || {}
      const rows = (t.city_traffic || []).length
      return `${t.template === 'custom' ? '自定义' : '演示'} · ${rows} 条方向流`
    },
  },
}
</script>

<style scoped>
.cond-summary { background: #1e1e2e; border-radius: 8px; padding: 12px 16px; }
.cs-title { font-size: 13px; color: #cdd6f4; margin-bottom: 8px; }
.cs-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 16px; }
.cs-item { display: flex; font-size: 12px; color: #8a8aaa; gap: 8px; }
.cs-item.wide { grid-column: span 2; }
.cs-item span { min-width: 42px; color: #6a6a8a; }
.cs-item b { color: #cdd6f4; font-weight: 400; }
.cs-warn { margin-top: 8px; font-size: 11px; color: #e6a23c; line-height: 1.6; }
</style>
