<template>
  <section class="demand-forecast">
    <h3>实验前客流预测</h3>
    <div class="controls"><el-select v-model="source" size="small" :disabled="loading"><el-option v-for="name in sources" :key="name" :label="name" :value="name" /></el-select><el-input-number v-model="horizon" size="small" :disabled="loading" :min="1" :max="source === '公开月客流' ? 12 : 7" /><span>{{ source === '公开月客流' ? '个月' : '天' }}</span><el-button size="small" :loading="loading" @click="load">预测客流趋势</el-button></div>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" />
    <template v-if="result">
      <p>{{ result.description }}。{{ result.method }}。</p>
      <p>预测合计 <strong>{{ result.total.toLocaleString() }}</strong> 人次；连续留出误差 {{ result.evaluation.mae.toLocaleString() }} 人次，对照 {{ result.evaluation.baseline_mae.toLocaleString() }} 人次。</p>
      <div ref="chart" class="chart" />
      <el-button v-if="source !== '公开月客流'" size="small" :disabled="result.factor < 0.5 || result.factor > 2" @click="$emit('apply', { base_airport: source, demand_factor: result.factor, days: horizon })">将预测比例和天数填入表单</el-button>
      <p class="hint">{{ source === '公开月客流' ? '公开月客流只做方法对照，不把历史国际客流冒充成都当前日客流。' : `建议客流比例 ${result.factor}，相对于固定历史末期周均值；填表后仍需确认才能运行实验。` }}</p>
    </template>
    <p v-else class="hint">基地日数据为平台模拟历史；公开月数据为真实历史基准。使用离线固定模型，点击预测不会运行调度实验。</p>
  </section>
</template>

<script>
import * as echarts from 'echarts'
import api from '@/api/intelligence'
export default {
  props: { config: Object },
  data: () => ({ source: '成都', horizon: 7, result: null, loading: false, error: '', chart: null, revision: 0,
    sources: ['成都', '北京', '上海', '广州', '昆明', '三亚', '重庆', '西安', '公开月客流'] }),
  watch: { 'config.base_airport'(value) { this.source = value }, 'config.days'(value) { this.horizon = value },
    'config.start_date': 'invalidate', source: 'invalidate', horizon: 'invalidate' },
  beforeDestroy() { if (this.chart) this.chart.dispose(); window.removeEventListener('resize', this.resize) },
  mounted() { window.addEventListener('resize', this.resize) },
  methods: {
    invalidate() { this.revision++; this.result = null; if (this.chart) { this.chart.dispose(); this.chart = null } },
    async load() {
      this.loading = true; this.error = ''
      const revision = this.revision
      try {
        const result = await api.demand(this.source, this.horizon, this.config.start_date)
        if (revision !== this.revision) return
        this.result = result
        await this.$nextTick(); this.draw()
      } catch (error) { this.error = error.message } finally { this.loading = false }
    },
    draw() {
      if (this.chart) this.chart.dispose()
      this.chart = echarts.init(this.$refs.chart)
      const history = this.result.history
      const forecast = this.result.forecast
      const gaps = history.map(() => null)
      this.chart.setOption({ animation: false, tooltip: { trigger: 'axis' }, legend: { data: ['历史', '预测', '同期对照'] },
        grid: { left: 65, right: 24, top: 40, bottom: 35 },
        xAxis: { type: 'category', data: [...history.map(row => row.date), ...forecast.map(row => row.date)] },
        yAxis: { type: 'value', name: '人次' }, series: [
          { name: '历史', type: 'line', showSymbol: false, data: history.map(row => row.passengers) },
          { name: '预测', type: 'line', data: [...gaps, ...forecast.map(row => row.used)] },
          { name: '同期对照', type: 'line', lineStyle: { type: 'dashed' }, data: [...gaps, ...forecast.map(row => row.baseline)] }
        ] })
    },
    resize() { if (this.chart) this.chart.resize() }
  }
}
</script>

<style scoped>
h3 { margin: 0 0 16px; font-size: 18px; }
.controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13px; }
.el-select { width: 160px; }.el-input-number { width: 130px; }
p { color: #657489; font-size: 13px; line-height: 1.8; margin-top: 10px; }.hint { font-size: 12px; }
.chart { height: 260px; width: 100%; }
</style>
