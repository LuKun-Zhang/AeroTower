/**
 * 跑道调度（RunwayView / “跑道调度”标签）的透明浮层图表集合。
 * 数据全部来自 RunwayView 实例：
 *   - schedule[]    当前机场+当前日期下所选算法的调度条目：
 *                   runway / actual_time~end_time（绝对分钟，从月初算起）/ type(landing|takeoff) / delay
 *   - runwayStats   仅 CP-SAT 会返回的分机场统计（total_delay/avg_delay/landing_count/takeoff_count/runways）
 *   - runwayCount   计算属性，当前机场跑道数
 * 说明：本页只保留“当前所选算法”的结果，没有同时保存 FCFS/CP-SAT/ILS-CPS 三套，
 *       因此不画三算法对比图，改为第 5 张单算法 KPI 柱。
 */
import { noData } from '../chartBase'
import { isoBarOption } from './isoBars'

const SLOT = 30 // 30 分钟一格的桶
const grid = { left: 60, right: 24, top: 40, bottom: 66, containLabel: true }

// 绝对分钟 -> 当日分钟（与页面时间轴口径一致）
function minuteOfDay(absMin) {
  const m = (Number(absMin) || 0) % 1440
  return m < 0 ? m + 1440 : m
}
// 30 分钟桶的标签 "HH:MM"
function slotLabel(i) {
  const total = i * SLOT
  const h = Math.floor(total / 60)
  const mm = total % 60
  return `${h}:${String(mm).padStart(2, '0')}`
}
function hourLabel(h) {
  return `${h}:00`
}

export function buildRunwayCharts(vm) {
  return [
    {
      id: 'rw-heat',
      title: '跑道 × 时间占用立体柱',
      note: '菱形地面：左前棱=30 分钟时段，右前棱=跑道；每根柱子立在该跑道该时段上，柱高=覆盖到该时段的起降架次（1 架次占满几个时段就长几根柱）。跑道只有 1~2 条所以沿纵深排布，可拖左下色条只保留高占用时段',
      build: (theme) => {
        const items = (vm.schedule || []).filter(s => s.actual_time !== undefined)
        if (!items.length) return noData('当前机场/日期没有调度结果，请先在左侧选机场并点「刷新」')
        const runways = Array.from(new Set(items.map(s => s.runway))).sort((a, b) => a - b)
        const rIdx = {}
        runways.forEach((r, i) => { rIdx[r] = i })
        const cells = {}
        items.forEach(s => {
          const start = minuteOfDay(s.actual_time)
          const end = minuteOfDay(s.end_time === undefined ? s.actual_time : s.end_time)
          const from = Math.floor(start / SLOT)
          // 占用可能跨午夜，按 start~end 覆盖的桶逐个计一次；跨天只覆盖起点当天
          const to = end >= start ? Math.floor(end / SLOT) : Math.floor(start / SLOT)
          for (let b = from; b <= to && b < 48; b++) {
            const k = `${rIdx[s.runway]}_${b}`
            cells[k] = (cells[k] || 0) + 1
          }
        })
        // 48 个 30 分钟桶做 x 轴（与页面时间轴同口径），跑道做 y 轴
        const buckets = Array.from({ length: 48 }, (_, i) => slotLabel(i))
        const list = Object.keys(cells).map(k => {
          const p = k.split('_')
          const yi = Number(p[0])
          const xi = Number(p[1])
          const v = cells[k]
          return {
            xi,
            yi,
            v,
            tip: `跑道 ${runways[yi]} ${buckets[xi]}<br/>占用 ${v} 架次`,
          }
        })
        if (!list.length) return noData('调度条目都没有可用的占用时刻，请确认后端返回了 actual_time')
        return isoBarOption({
          theme,
          xLabels: buckets,
          yLabels: runways.map(r => `跑道 ${r}`),
          cells: list,
          valueName: '架次',
          maxTicks: 12,
          emptyText: '当前机场/日期没有任何时段被占用',
          sceneTitle: '跑道 × 30 分钟时段 占用架次',
        })
      },
    },
    {
      id: 'rw-hourly',
      title: '起降架次按小时堆叠',
      note: '按占用开始时刻的小时统计，蓝=降落 绿=起飞，可看高峰是否集中在少数小时',
      build: () => {
        const items = (vm.schedule || []).filter(s => s.actual_time !== undefined)
        if (!items.length) return noData('当前机场/日期没有调度结果，请先在左侧选机场并点「刷新」')
        const land = new Array(24).fill(0)
        const take = new Array(24).fill(0)
        items.forEach(s => {
          const h = Math.floor(minuteOfDay(s.actual_time) / 60) % 24
          if (s.type === 'landing') land[h] += 1
          else take[h] += 1
        })
        const hasAny = land.some(v => v) || take.some(v => v)
        if (!hasAny) return noData('这些航班都没有可用的开始时刻')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: ['降落', '起飞'], top: 6 },
          grid,
          xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => hourLabel(i)), axisLabel: { interval: 2, fontSize: 10 } },
          yAxis: { type: 'value', name: '架次' },
          series: [
            { name: '降落', type: 'bar', stack: 'h', barMaxWidth: 26, itemStyle: { color: '#2bc4f3' }, data: land },
            { name: '起飞', type: 'bar', stack: 'h', barMaxWidth: 26, itemStyle: { color: '#4caf50' }, data: take },
          ],
        }
      },
    },
    {
      id: 'rw-delayhist',
      title: '延误分布直方图',
      note: '按延误分钟分桶，统计各区间航班数（准点单独一档）',
      build: () => {
        const items = (vm.schedule || []).filter(s => typeof s.delay === 'number')
        if (!items.length) return noData('当前机场/日期没有调度结果，请先在左侧选机场并点「刷新」')
        const buckets = [
          { label: '准点(0)', test: d => d === 0 },
          { label: '1-5', test: d => d >= 1 && d <= 5 },
          { label: '6-15', test: d => d >= 6 && d <= 15 },
          { label: '16-30', test: d => d >= 16 && d <= 30 },
          { label: '31-60', test: d => d >= 31 && d <= 60 },
          { label: '>60', test: d => d > 60 },
        ]
        const data = buckets.map(b => ({
          value: items.filter(s => b.test(s.delay)).length,
          itemStyle: { color: b.label === '准点(0)' ? '#4caf50' : (b.label === '>60' || b.label === '31-60' ? '#f56c6c' : '#e6a23c') },
        }))
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name} min<br/>${p[0].value} 架` },
          grid,
          xAxis: { type: 'category', data: buckets.map(b => b.label), axisLabel: { interval: 0, fontSize: 11 } },
          yAxis: { type: 'value', name: '架数' },
          series: [{ type: 'bar', barMaxWidth: 44, data, label: { show: true, position: 'top', fontSize: 11 } }],
        }
      },
    },
    {
      id: 'rw-runwaydelay',
      title: '各跑道延误总量',
      note: '把当前机场每架次延误分钟按跑道聚合，可看哪条跑道被拖累最多',
      build: () => {
        const items = (vm.schedule || []).filter(s => typeof s.delay === 'number')
        if (!items.length) return noData('当前机场/日期没有调度结果，请先在左侧选机场并点「刷新」')
        const map = {}
        items.forEach(s => { map[s.runway] = (map[s.runway] || 0) + s.delay })
        const rws = Object.keys(map).map(Number).sort((a, b) => a - b)
        if (!rws.length) return noData('没有可按跑道聚合的延误数据')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `跑道 ${p[0].name}<br/>合计延误 ${p[0].value} 分钟` },
          grid,
          xAxis: { type: 'category', data: rws.map(r => `跑道 ${r}`), axisLabel: { interval: 0 } },
          yAxis: { type: 'value', name: '延误(分钟)' },
          series: [{ type: 'bar', barMaxWidth: 60, itemStyle: { color: '#f56c6c' }, data: rws.map(r => map[r]), label: { show: true, position: 'top', fontSize: 11 } }],
        }
      },
    },
    {
      id: 'rw-kpi',
      title: '当前算法 KPI',
      note: '所选算法（页面当前只保留这一套结果，无法与另两套同图对比）整体指标；注意各柱单位不同（分钟/架次/条数）',
      build: () => {
        const items = vm.schedule || []
        const s = vm.runwayStats
        let kpi
        if (s && (s.total_delay !== undefined || s.landing_count !== undefined)) {
          kpi = {
            total_delay: s.total_delay || 0,
            avg_delay: s.avg_delay || 0,
            landing_count: s.landing_count || 0,
            takeoff_count: s.takeoff_count || 0,
            runways: s.runways || vm.runwayCount || 1,
          }
        } else if (items.length) {
          // 该页 fcfs/ils_cps 后端不返回 stats，这里从真实 schedule 聚合（非编造）
          const total = items.reduce((sum, i) => sum + (Number(i.delay) || 0), 0)
          kpi = {
            total_delay: total,
            avg_delay: Math.round(total / items.length * 10) / 10,
            landing_count: items.filter(i => i.type === 'landing').length,
            takeoff_count: items.filter(i => i.type === 'takeoff').length,
            runways: vm.runwayCount || (items[0] && items[0].runway_total) || 1,
          }
        } else {
          return noData('当前没有调度结果，请先在左侧选机场（如需带 stats 的对比可选 CP-SAT）并点「刷新」')
        }
        const cats = [
          { label: '总延误(min)', key: 'total_delay', color: '#f56c6c' },
          { label: '平均延误(min)', key: 'avg_delay', color: '#e6a23c' },
          { label: '降落架次', key: 'landing_count', color: '#2bc4f3' },
          { label: '起飞架次', key: 'takeoff_count', color: '#4caf50' },
          { label: '跑道数', key: 'runways', color: '#b37feb' },
        ]
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid,
          xAxis: { type: 'category', data: cats.map(c => c.label), axisLabel: { interval: 0, fontSize: 11 } },
          yAxis: { type: 'value' },
          series: [{
            type: 'bar',
            barMaxWidth: 52,
            data: cats.map(c => ({ value: kpi[c.key], itemStyle: { color: c.color } })),
            label: { show: true, position: 'top', fontSize: 11 },
          }],
        }
      },
    },
  ]
}

export default buildRunwayCharts
