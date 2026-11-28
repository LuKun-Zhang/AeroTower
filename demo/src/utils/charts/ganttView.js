/**
 * 飞机排班（GanttView / “飞机排班”标签）的透明浮层图表集合。
 * 数据全部来自 GanttView 实例：
 *   - aircrafts[]      每架飞机：utilization / idle_time / quality_index / base / tail_no / assigned_flights[]
 *   - enrichedAircrafts 计算属性，给每架飞机补了 dailyDuty[{date, minutes}]
 *   - stats            最近一次「一键排班」结果：base_distribution / aircraft_count ...
 *   - compareData      「算法对比」结果：bipartite / greedy /（后端还会带 chain_coverage）
 * 【严禁编造数据】：任一来源为空一律 return noData 并提示要点哪个按钮。
 */
import { noData, PALETTE } from '../chartBase'

const grid = { left: 64, right: 24, top: 48, bottom: 70, containLabel: true }

// 与页面 idxClass 一致的分档配色语义：≥80 优 / ≥60 中 / <60 差
function idxColor(v) {
  if (v >= 80) return '#4caf50'
  if (v >= 60) return '#ffc107'
  return '#f44336'
}

// 与页面 dayShort 同口径：'2020-11-30' -> '11/30'
function dayShort(dateStr) {
  const m = (dateStr || '').match(/(\d+)-(\d+)-(\d+)/)
  return m ? `${Number(m[2])}/${Number(m[3])}` : (dateStr || '')
}

// 算法对比里实际存在的算法（后端 /schedule/compare 在筛选模式下会额外返回 chain_coverage）
const COMPARE_ALGOS = [
  { key: 'bipartite', name: '二分图匹配' },
  { key: 'greedy', name: '贪心算法' },
  { key: 'chain_coverage', name: '链集合覆盖' },
]

export function buildGanttCharts(vm) {
  return [
    {
      id: 'gv-compare',
      title: '算法对比分组柱状',
      note: '五类指标横向对比各算法（注意单位不同：飞机数/百分比/分钟）。页面表格只画了两种，这里把后端返回的 chain_coverage 也补进来',
      build: () => {
        const cd = vm.compareData
        if (!cd) return noData('尚未运行算法对比，请点击工具栏「算法对比」按钮后再看这张图')
        const algos = COMPARE_ALGOS.filter(a => cd[a.key] && cd[a.key].stats)
        if (!algos.length) return noData('算法对比结果为空，请重新点击「算法对比」')
        const metrics = [
          { label: '飞机数', key: 'aircraft_count' },
          { label: '覆盖率(%)', key: 'coverage' },
          { label: '平均利用率(%)', key: 'avg_utilization' },
          { label: '总空闲(min)', key: 'total_idle_time_minutes' },
          { label: '基地闭环数', key: 'base_closed_count' },
        ]
        const missingChain = !cd.chain_coverage
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: algos.map(a => a.name), top: 6 },
          grid,
          xAxis: { type: 'category', data: metrics.map(m => m.label), axisLabel: { interval: 0, fontSize: 11 } },
          yAxis: { type: 'value' },
          series: algos.map((a, i) => ({
            name: a.name,
            type: 'bar',
            barMaxWidth: 34,
            itemStyle: { color: PALETTE[i % PALETTE.length] },
            data: metrics.map(m => {
              const v = cd[a.key].stats[m.key]
              return typeof v === 'number' ? v : 0
            }),
          })),
          graphic: missingChain ? [{
            type: 'text', left: 'center', bottom: 4,
            style: { text: '本次对比未返回 chain_coverage（链集合覆盖），仅对比现有算法', fontSize: 11, fill: '#e6a23c' },
          }] : undefined,
        }
      },
    },
    {
      id: 'gv-quality',
      title: '飞机质量指数分布',
      note: '按综合质量指数分档的飞机数量，沿用页面 ≥80 优 / ≥60 中 / <60 差 的配色语义',
      build: () => {
        const list = (vm.aircrafts || []).filter(a => typeof a.quality_index === 'number')
        if (!list.length) return noData('还没有排班结果，请先点击「一键排班」，生成排班后才能统计飞机质量指数分布')
        const bins = []
        for (let lo = 0; lo < 100; lo += 10) bins.push({ lo, hi: lo + 10, n: 0 })
        list.forEach(a => {
          let idx = Math.floor(a.quality_index / 10)
          if (idx < 0) idx = 0
          if (idx > 9) idx = 9
          bins[idx].n += 1
        })
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name}<br/>${p[0].value} 架` },
          grid,
          xAxis: { type: 'category', data: bins.map(b => `${b.lo}-${b.hi}`), axisLabel: { interval: 0, fontSize: 11 } },
          yAxis: { type: 'value', name: '架数' },
          series: [{
            type: 'bar',
            barMaxWidth: 40,
            data: bins.map(b => ({ value: b.n, itemStyle: { color: idxColor(b.lo + 5) } })),
            label: { show: true, position: 'top', fontSize: 11 },
          }],
        }
      },
    },
    {
      id: 'gv-duty',
      title: '每日执勤时长 vs 480 上限',
      note: '横条=每架飞机每天的执勤(飞行)分钟数，红色虚线=CCAR-121 日 8 小时(480min)上限，超限的排在前面',
      build: () => {
        const rows = []
        ;(vm.enrichedAircrafts || []).forEach(ac => {
          ;(ac.dailyDuty || []).forEach(dd => {
            rows.push({ label: `${ac.tail_no} ${dayShort(dd.date)}`, minutes: dd.minutes || 0 })
          })
        })
        if (!rows.length) return noData('没有每日执勤数据，请先点击「一键排班」生成排班结果')
        rows.sort((a, b) => b.minutes - a.minutes)
        const shown = rows.slice(0, 40)
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name}<br/>${p[0].value} 分钟` },
          grid: { left: 120, right: 40, top: 24, bottom: 40, containLabel: true },
          xAxis: { type: 'value', name: '执勤(分钟)' },
          yAxis: { type: 'category', data: shown.map(r => r.label).reverse(), axisLabel: { fontSize: 10, interval: 0 } },
          series: [{
            type: 'bar',
            barMaxWidth: 16,
            data: shown.map(r => ({
              value: r.minutes,
              itemStyle: { color: r.minutes > 480 ? '#f56c6c' : PALETTE[1] },
            })).reverse(),
            markLine: {
              symbol: 'none',
              lineStyle: { color: '#f56c6c', type: 'dashed', width: 1.5 },
              label: { formatter: '480 上限', color: '#f56c6c' },
              data: [{ xAxis: 480 }],
            },
          }],
        }
      },
    },
    {
      id: 'gv-base',
      title: '基地分布',
      note: '各川航基地停场/过夜飞机数占比（来自最近一次排班的 stats.base_distribution）',
      build: () => {
        const dist = vm.stats && vm.stats.base_distribution
        if (!dist || !Object.keys(dist).length) return noData('还没有排班统计，请先点击「一键排班」后查看基地分布')
        const data = Object.keys(dist).map(k => ({ name: k ? k : '未指定基地', value: dist[k] }))
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 架 ({d}%)' },
          legend: { top: 6, type: 'scroll' },
          series: [{
            type: 'pie',
            radius: ['38%', '62%'],
            center: ['50%', '58%'],
            data,
            label: { formatter: '{b}\n{c} 架 ({d}%)', fontSize: 11 },
          }],
        }
      },
    },
    {
      id: 'gv-util',
      title: '利用率 vs 空闲时间散点',
      note: '每架飞机一点：横轴=利用率(%)，纵轴=空闲(分钟)。右下角=飞得满且衔接紧，左上=大量等待',
      build: () => {
        const pts = (vm.aircrafts || [])
          .filter(a => typeof a.utilization === 'number')
          .map(a => ({ name: a.tail_no, value: [a.utilization, a.idle_time || 0] }))
        if (!pts.length) return noData('还没有飞机利用率数据，请先点击「一键排班」生成排班')
        return {
          tooltip: { trigger: 'item', formatter: p => `${p.data.name}<br/>利用率 ${p.value[0]}% | 空闲 ${p.value[1]} 分钟` },
          grid,
          xAxis: { type: 'value', name: '利用率(%)', splitLine: { lineStyle: { type: 'dashed' } } },
          yAxis: { type: 'value', name: '空闲(分钟)', splitLine: { lineStyle: { type: 'dashed' } } },
          series: [{
            type: 'scatter',
            symbolSize: 11,
            itemStyle: { color: PALETTE[0], opacity: 0.85 },
            data: pts,
          }],
        }
      },
    },
  ]
}

export default buildGanttCharts
