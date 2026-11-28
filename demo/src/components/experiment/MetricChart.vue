<template>
  <div class="metric-chart">
    <div class="mc-head">
      <span class="mc-title">指标随时间变化</span>
      <div class="mc-tabs">
        <span :class="{ active: mode === 'status' }" @click="setMode('status')">航班状态</span>
        <span :class="{ active: mode === 'delay' }" @click="setMode('delay')">平均延误</span>
      </div>
    </div>
    <div ref="chart" class="mc-canvas"></div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'MetricChart',
  props: { series: { type: Object, default: () => ({ points: [] }) } },
  data() {
    return { mode: 'status', chart: null }
  },
  watch: {
    series() { this.render() },
  },
  mounted() {
    this.chart = echarts.init(this.$refs.chart)
    this.render()
    window.addEventListener('resize', this.resize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resize)
    if (this.chart) this.chart.dispose()
  },
  methods: {
    setMode(mode) {
      this.mode = mode
      this.render()
    },
    resize() {
      if (this.chart) this.chart.resize()
    },
    render() {
      if (!this.chart) return
      const points = (this.series && this.series.points) || []
      const labels = points.map(p => p.time)
      const base = {
        backgroundColor: 'transparent',
        grid: { left: 48, right: 20, top: 30, bottom: 46 },
        tooltip: { trigger: 'axis' },
        legend: { textStyle: { color: '#a0a0c0', fontSize: 11 } },
        xAxis: {
          type: 'category', data: labels, boundaryGap: false,
          axisLabel: { color: '#7a7a9a', fontSize: 10, hideOverlap: true },
          axisLine: { lineStyle: { color: '#313145' } },
        },
        yAxis: {
          type: 'value',
          axisLabel: { color: '#7a7a9a', fontSize: 10 },
          splitLine: { lineStyle: { color: '#26263a' } },
        },
      }
      const series = this.mode === 'status' ? [
        this.line('在空', points.map(p => p.airborne), '#409eff', true),
        this.line('已到达', points.map(p => p.arrived), '#67c23a', true),
        this.line('延误', points.map(p => p.delayed), '#e6a23c', true),
        this.line('取消', points.map(p => p.cancelled), '#f56c6c', true),
      ] : [
        this.line('平均延误（分钟）', points.map(p => p.avg_delay), '#e6a23c', false),
      ]
      this.chart.setOption({ ...base, series }, true)
    },
    line(name, data, color, stack) {
      return {
        name, type: 'line', data, smooth: true, showSymbol: false,
        stack: stack ? 'total' : undefined,
        areaStyle: stack ? { opacity: 0.12 } : { opacity: 0.08 },
        lineStyle: { width: 1.4, color },
        itemStyle: { color },
      }
    },
  },
}
</script>

<style scoped>
.metric-chart { background: #1e1e2e; border-radius: 8px; padding: 12px 14px; }
.mc-head { display: flex; align-items: center; margin-bottom: 4px; }
.mc-title { font-size: 13px; color: #cdd6f4; }
.mc-tabs { margin-left: auto; display: flex; gap: 4px; }
.mc-tabs span {
  padding: 2px 10px; font-size: 11px; color: #7a7a9a; cursor: pointer;
  border-radius: 10px; background: #2d2d44;
}
.mc-tabs span.active { color: #fff; background: rgba(64,158,255,0.35); }
.mc-canvas { width: 100%; height: 240px; }
</style>
