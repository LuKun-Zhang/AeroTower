/**
 * 总览仪表盘页（DashboardView，1.5s 轮询仿真快照）的图表集合。
 * 数据来源均为页面已有状态：
 *   vm.allFlights（snap.flights）、vm.kpi（snap.kpi）、vm.weatherList（snap.weather 值列表）、
 *   vm.simTime（snap.current_time，'YYYY-MM-DD HH:MM'）。
 * KPI 曲线用 chartBase 的 addSample/getSamples 自行攒历史（key 'dash-kpi'）。
 */
import { noData, themeColors, addSample, getSamples } from '../chartBase'

const SAMPLE_KEY = 'dash-kpi'
const grid = { left: 60, right: 46, top: 46, bottom: 60, containLabel: true }

const NO_SIM = '暂无航班快照：请先启动仿真（本页每 1.5 秒轮询一次 /sim/snapshot，启动后稍候再打开图表）'

export function buildDashboardCharts(vm) {
  return [
    {
      id: 'db-hourly-trend',
      title: '航班状态按小时趋势',
      note: '沿用页面 buildTrend 逻辑：flights[] 按 scheduled_dep[3] 小时分桶，堆叠柱=正常/延误/取消，折线=该小时准点率（右轴%）',
      build: (theme) => {
        const flights = vm.allFlights || []
        if (!flights.length) return noData(NO_SIM)
        // 与 DashboardView.buildTrend 同一套分桶规则
        const hours = {}
        for (const f of flights) {
          if (!f.scheduled_dep || !Array.isArray(f.scheduled_dep)) continue
          const h = f.scheduled_dep[3] || 0
          const key = `${String(h).padStart(2, '0')}:00`
          if (!hours[key]) hours[key] = { normal: 0, delayed: 0, cancelled: 0 }
          if (f.is_cancelled) hours[key].cancelled++
          else if (f.is_delayed || f.delay_minutes > 0) hours[key].delayed++
          else hours[key].normal++
        }
        const keys = Object.keys(hours).sort()
        if (!keys.length) return noData('快照里的航班都没有可用的 scheduled_dep 起飞时间，无法按小时分桶')
        const buckets = keys.map(k => hours[k])
        const punct = buckets.map(b => {
          const t = b.normal + b.delayed + b.cancelled
          return t ? Math.round(b.normal / t * 1000) / 10 : 0
        })
        const c = themeColors(theme)
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 6 },
          grid,
          xAxis: { type: 'category', data: keys, axisLabel: { interval: 'auto', fontSize: 10 } },
          yAxis: [
            { type: 'value', name: '航班数', minInterval: 1 },
            { type: 'value', name: '准点率(%)', max: 100, splitLine: { show: false } },
          ],
          series: [
            { name: '正常', type: 'bar', stack: 'st', data: buckets.map(b => b.normal), itemStyle: { color: '#4caf50' } },
            { name: '延误', type: 'bar', stack: 'st', data: buckets.map(b => b.delayed), itemStyle: { color: '#ff9800' } },
            { name: '取消', type: 'bar', stack: 'st', data: buckets.map(b => b.cancelled), itemStyle: { color: '#f44336' } },
            {
              name: '准点率', type: 'line', yAxisIndex: 1, data: punct, smooth: true,
              symbolSize: 5, lineStyle: { color: PALETTE_LINE(c) }, itemStyle: { color: PALETTE_LINE(c) },
            },
          ],
        }
      },
    },
    {
      id: 'db-kpi-history',
      title: 'KPI 时序曲线',
      note: '页面 1.5s 轮询里用 addSample 攒下的仿真历史（含卡片未展示的 avg_delay 平均延误）；比率的左轴 %，分钟/架次的右轴',
      build: () => {
        const k = vm.kpi || {}
        const ts = vm.simTime
        if (ts && ts !== '--') {
          addSample(SAMPLE_KEY, ts, {
            punctuality: Number(k.punctuality) || 0,
            completion_rate: Number(k.completion_rate) || 0,
            avg_delay: Number(k.avg_delay) || 0,
            delayed_count: Number(k.delayed_count) || 0,
            cancelled_count: Number(k.cancelled_count) || 0,
          })
        }
        const samples = getSamples(SAMPLE_KEY)
        if (samples.length < 2) {
          return noData('KPI 历史采样不足 2 个点：需先启动仿真并保持页面轮询（每 1.5 秒采样一次），稍后再打开')
        }
        const xs = samples.map(s => s[0].slice(11))
        const v = key => samples.map(s => s[1][key])
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 6 },
          grid,
          xAxis: { type: 'category', data: xs, axisLabel: { fontSize: 10, interval: 'auto' } },
          yAxis: [
            { type: 'value', name: '比率(%)', max: 100 },
            { type: 'value', name: '分钟 / 架次', splitLine: { show: false } },
          ],
          series: [
            { name: '准点率(%)', type: 'line', data: v('punctuality'), smooth: true, showSymbol: false },
            { name: '完成率(%)', type: 'line', data: v('completion_rate'), smooth: true, showSymbol: false },
            { name: '平均延误(分)', type: 'line', yAxisIndex: 1, data: v('avg_delay'), smooth: true, showSymbol: false },
            { name: '延误架次', type: 'line', yAxisIndex: 1, data: v('delayed_count'), smooth: true, showSymbol: false },
            { name: '取消架次', type: 'line', yAxisIndex: 1, data: v('cancelled_count'), smooth: true, showSymbol: false },
          ],
        }
      },
    },
    {
      id: 'db-weather-scatter',
      title: '机场天气散点',
      note: 'weather{} 各机场 能见度×风速，颜色区分是否触发容量下降（is_disrupted）；左下=低能见强风，最该盯',
      build: (theme) => {
        const list = (vm.weatherList || []).filter(w => w && typeof w.visibility_m === 'number' && typeof w.wind_ms === 'number')
        if (!list.length) return noData('天气列表为空：仿真快照尚未返回 weather 数据，请先启动仿真')
        const c = themeColors(theme)
        const mk = arr => arr.map(w => ({ value: [w.visibility_m, w.wind_ms], name: w.airport, label: w.label || '' }))
        const seriesBase = {
          type: 'scatter', symbolSize: 16,
          label: { show: true, position: 'top', formatter: p => p.name, fontSize: 10, color: c.text },
        }
        return {
          tooltip: {
            formatter: p => `${p.name}（${p.data.label || ''}）<br/>能见度 ${p.value[0]} m｜风速 ${p.value[1]} m/s`,
          },
          legend: { top: 6 },
          grid,
          xAxis: { type: 'value', name: '能见度(m)', axisLabel: { formatter: v => v >= 1000 ? (v / 1000) + 'km' : v } },
          yAxis: { type: 'value', name: '风速(m/s)', scale: true },
          series: [
            {
              name: '正常', ...seriesBase,
              itemStyle: { color: '#4caf50', opacity: 0.85 },
              data: mk(list.filter(w => !w.is_disrupted)),
            },
            {
              name: '扰动天气', ...seriesBase,
              itemStyle: { color: '#f56c6c', opacity: 0.9 },
              data: mk(list.filter(w => w.is_disrupted)),
            },
          ],
        }
      },
    },
  ]
}

// 折线颜色随明暗微调，保证透明底上可见
function PALETTE_LINE(c) {
  return c.dark ? '#b37feb' : '#7c3aed'
}

export default buildDashboardCharts
