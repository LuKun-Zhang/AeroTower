/**
 * 登机口分配（GateView / “登机口分配”标签）的透明浮层图表集合。
 * 数据全部来自 GateView 实例：
 *   - gates[]        每个机位：name / gate_type(large|medium|small) / utilization /
 *                    assigned_flights[].start_min~end_min（绝对分钟，从月初算起）
 *   - conflicts[]    每条冲突：gate / flight_a / flight_b / overlap_min
 *   - compareData    「算法对比」结果：greedy / bipartite / cp_sat，各自 stats + conflict_count
 */
import { noData } from '../chartBase'
import { isoBarOption } from './isoBars'

const SLOT = 30
const GT_TOP_N = 20 // 机位可能很多，纵深轴只保留占用分钟数最高的前 N 个（数据选择，不改动数值）
const grid = { left: 64, right: 24, top: 40, bottom: 70, containLabel: true }

const TYPE_COLORS = { large: '#f56c6c', medium: '#4f9cf9', small: '#67c23a' }
const TYPE_LABELS = { large: '大机型', medium: '中机型', small: '小机型' }

function minuteOfDay(absMin) {
  const m = (Number(absMin) || 0) % 1440
  return m < 0 ? m + 1440 : m
}
function slotLabel(i) {
  const total = i * SLOT
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

export function buildGateCharts(vm) {
  return [
    {
      id: 'gt-heat',
      title: '机位 × 时间占用立体柱',
      note: `菱形地面：左前棱=30 分钟时段，右前棱=机位；柱高=该机位该时段实际被占用的分钟数（航班占用区间与时段求交，最高 30）。机位较多时取占用最高的前 ${GT_TOP_N} 个机位，其余不画`,
      build: (theme) => {
        const gates = (vm.gates || []).filter(g => (g.assigned_flights || []).length)
        if (!gates.length) return noData('还没有机位分配结果，请先点「分配」（或先筛选航班并保存排班）')
        // 逐个机位把「航班占用区间 ∩ 30 分钟时段」折算成占用分钟数
        const perGate = gates.map(g => {
          const buckets = {}
          ;(g.assigned_flights || []).forEach(a => {
            const start = minuteOfDay(a.start_min)
            const end = minuteOfDay(a.end_min === undefined ? a.start_min : a.end_min)
            const from = Math.floor(start / SLOT)
            // 占用可能跨午夜：跨天时只统计起点当天那段（与页面时间轴口径一致）
            const to = end >= start ? Math.floor(end / SLOT) : from
            for (let b = from; b <= to && b < 48; b++) {
              const s = Math.max(start, b * SLOT)
              const e = Math.min(end >= start ? end : 1440, (b + 1) * SLOT)
              const mins = e - s
              if (mins > 0) buckets[b] = (buckets[b] || 0) + mins
            }
          })
          const total = Object.keys(buckets).reduce((sum, b) => sum + buckets[b], 0)
          return { name: g.name, buckets, total }
        })
        // 纵深轴控制在 GT_TOP_N 个：按占用分钟数从高到低取前 N（真实聚合值排序，非编造）
        const rows = perGate
          .filter(r => r.total > 0)
          .sort((a, b) => b.total - a.total)
          .slice(0, GT_TOP_N)
        const bucketsX = Array.from({ length: 48 }, (_, i) => slotLabel(i))
        const cells = []
        rows.forEach((r, yi) => {
          Object.keys(r.buckets).forEach(b => {
            const xi = Number(b)
            const v = Math.round(r.buckets[b] * 10) / 10
            cells.push({ xi, yi, v, tip: `${r.name} ${bucketsX[xi]}<br/>占用 ${v} 分钟` })
          })
        })
        if (!cells.length) return noData('机位航班缺少可解析的占用时间段，请检查排班里的 start_min/end_min')
        return isoBarOption({
          theme,
          xLabels: bucketsX,
          yLabels: rows.map(r => r.name),
          cells,
          valueName: '占用分钟',
          maxBars: GT_TOP_N * 48,
          maxTicks: 12,
          emptyText: '机位航班缺少可解析的占用时间段',
          sceneTitle: '机位 × 30 分钟时段 占用分钟',
        })
      },
    },
    {
      id: 'gt-utilrank',
      title: '机位利用率排行',
      note: '全部已分配机位按利用率从低到高排序，顶端吃紧、底端闲置一目了然',
      build: () => {
        const rows = (vm.gates || [])
          .filter(g => typeof g.utilization === 'number')
          .slice()
          .sort((a, b) => a.utilization - b.utilization)
        if (!rows.length) return noData('还没有机位分配结果，请先点「分配」后再看利用率排行')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name}<br/>利用率 ${p[0].value}%` },
          grid: { left: 88, right: 36, top: 20, bottom: 36, containLabel: true },
          xAxis: { type: 'value', name: '利用率(%)', max: 100 },
          yAxis: { type: 'category', data: rows.map(g => g.name), axisLabel: { fontSize: 10, interval: 0 } },
          series: [{
            type: 'bar',
            barMaxWidth: 14,
            data: rows.map(g => ({
              value: g.utilization,
              itemStyle: { color: g.utilization >= 60 ? '#f56c6c' : (g.utilization >= 30 ? '#e6a23c' : '#67c23a') },
            })),
          }],
        }
      },
    },
    {
      id: 'gt-radar',
      title: '三算法能力雷达',
      note: 'greedy / bipartite / cp_sat 在已用机位、平均/最高利用率、冲突数四个维度对比（每维按各算法最大值归一）',
      build: () => {
        const cd = vm.compareData
        if (!cd) return noData('尚未运行算法对比，请点击「算法对比」按钮后再看这张雷达图')
        const algos = [
          { key: 'greedy', name: '贪心算法' },
          { key: 'bipartite', name: '二分图匹配' },
          { key: 'cp_sat', name: 'CP-SAT' },
        ].filter(a => cd[a.key] && cd[a.key].stats)
        if (!algos.length) return noData('算法对比结果为空，请重新点击「算法对比」')
        const dims = [
          { label: '已用机位', get: a => (cd[a.key].stats.used_gates || 0) },
          { label: '平均利用率', get: a => (cd[a.key].stats.avg_utilization || 0) },
          { label: '最高利用率', get: a => (cd[a.key].stats.max_utilization || 0) },
          { label: '冲突数', get: a => (cd[a.key].conflict_count || 0) },
        ]
        const indicators = dims.map(d => {
          const max = algos.reduce((m, a) => Math.max(m, d.get(a)), 0)
          return { name: d.label, max: max > 0 ? max : 1 }
        })
        return {
          tooltip: { trigger: 'item' },
          legend: { data: algos.map(a => a.name), top: 6 },
          radar: { indicator: indicators, center: ['50%', '58%'], radius: '62%' },
          series: [{
            type: 'radar',
            symbolSize: 5,
            areaStyle: { opacity: 0.12 },
            data: algos.map((a, i) => ({
              name: a.name,
              value: dims.map(d => d.get(a)),
              lineStyle: { color: ['#4f9cf9', '#67c23a', '#e6a23c'][i % 3] },
              itemStyle: { color: ['#4f9cf9', '#67c23a', '#e6a23c'][i % 3] },
            })),
          }],
        }
      },
    },
    {
      id: 'gt-type',
      title: '机位类型构成',
      note: '大/中/小机型机位数量占比（gate_type：large/medium/small）',
      build: () => {
        const gates = vm.gates || []
        if (!gates.length) return noData('还没有机位分配结果，请先点「分配」后再看机位类型构成')
        const counts = {}
        gates.forEach(g => { counts[g.gate_type] = (counts[g.gate_type] || 0) + 1 })
        const data = Object.keys(counts).map(t => ({
          name: TYPE_LABELS[t] || t,
          value: counts[t],
          itemStyle: { color: TYPE_COLORS[t] },
        }))
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie',
            radius: ['38%', '62%'],
            center: ['50%', '58%'],
            data,
            label: { formatter: '{b}\n{c} 个 ({d}%)', fontSize: 11 },
          }],
        }
      },
    },
    {
      id: 'gt-conflict',
      title: '冲突分布',
      note: '按机位聚合当前算法的冲突次数，可定位最容易打架的机位',
      build: () => {
        const conflicts = vm.conflicts || []
        if (!conflicts.length) return noData('当前分配没有检测到冲突（这是好事）；如需看冲突分布请换更宽松的算法或增大航班量')
        const map = {}
        conflicts.forEach(c => { map[c.gate] = (map[c.gate] || 0) + 1 })
        const gates = Object.keys(map).sort((a, b) => map[b] - map[a])
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name}<br/>${p[0].value} 次冲突` },
          grid,
          xAxis: { type: 'category', data: gates, axisLabel: { interval: 0, rotate: gates.length > 8 ? 30 : 0, fontSize: 11 } },
          yAxis: { type: 'value', name: '冲突次数', minInterval: 1 },
          series: [{ type: 'bar', barMaxWidth: 48, itemStyle: { color: '#f56c6c' }, data: gates.map(g => map[g]), label: { show: true, position: 'top', fontSize: 11 } }],
        }
      },
    },
  ]
}

export default buildGateCharts
