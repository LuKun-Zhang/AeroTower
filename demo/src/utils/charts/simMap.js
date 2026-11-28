/**
 * 模拟大引擎 → 航班模拟（SimMapView）的图表集合。
 * 数据全部来自 SimMapView 轮询快照后已存在 vm 上的字段：
 *   flights[]（phase / delay_minutes / is_*）、flightCount、airborneCount、
 *   delayedCount、cancelledCount、punctuality、activeEvents[]、simCurrentTime。
 * 说明：SimMapView 目前只把 snap.kpi.punctuality 落到 vm，kpi 的其余字段
 * （completion_rate、avg_delay）这里按后端 _update_kpi 的同一口径从 flights[] 推导，
 * 不引入新接口、不写死数字。
 * 趋势图用 addSample 按业务时刻（vm.simCurrentTime）幂等攒历史。
 */
import { noData, PALETTE, addSample, getSamples } from '../chartBase'

const PHASES = [
  'scheduled', 'push_back', 'taxi_out', 'takeoff', 'climb', 'cruise',
  'descent', 'approach', 'landing', 'taxi_in', 'parked', 'delayed', 'cancelled',
]
const PHASE_LABELS = {
  scheduled: '计划中', push_back: '推出', taxi_out: '滑出', takeoff: '起飞',
  climb: '爬升', cruise: '巡航', descent: '下降', approach: '进近',
  landing: '着陆', taxi_in: '滑入', parked: '靠桥', delayed: '延误', cancelled: '取消',
}

const DELAY_BINS = [
  { label: '0-15 分钟', min: 0, max: 15 },
  { label: '15-30 分钟', min: 15, max: 30 },
  { label: '30-60 分钟', min: 30, max: 60 },
  { label: '60-120 分钟', min: 60, max: 120 },
  { label: '120-240 分钟', min: 120, max: 240 },
  { label: '≥240 分钟', min: 240, max: Infinity },
]

const grid = { left: 64, right: 64, top: 56, bottom: 52, containLabel: true }

function round1(v) { return Math.round(v * 10) / 10 }

/** 快照是否已可用（启动了仿真且轮询到了航班） */
function snapshotReady(vm) {
  return vm.initialized
    && vm.simCurrentTime && vm.simCurrentTime !== '--'
    && (vm.flights || []).length > 0
}

/** 趋势样本图公共空态判断：先采样，样本不足 2 个时给出可操作提示 */
function trendEmptyHint(key, ts, values, need) {
  addSample(key, ts, values, 720)
  const samples = getSamples(key)
  if (samples.length < 2) {
    return noData(need + '（当前已攒 ' + samples.length + ' 个点，趋势图至少需要 2 个；浮层里点「实时」可持续采样）')
  }
  return samples
}

export function buildSimMapCharts(vm) {
  return [
    {
      id: 'sm-kpi',
      title: '运行 KPI 时序',
      note: '左轴=百分比（准点率/完成率，完成率=已靠桥架次/总架次，与后端 kpi 同口径），右轴=架次与分钟（延误/取消架次、激活事件数、平均延误分钟）。数据来自当前快照轮询值，按业务时刻攒历史',
      build: () => {
        if (!snapshotReady(vm)) return noData('还没有仿真快照——请先点「🚀 启动仿真」并等时间轴推进')
        const flights = vm.flights
        const total = flights.length
        const parked = flights.filter(f => f.phase === 'parked').length
        const delayedFlights = flights.filter(f => (f.delay_minutes || 0) > 0)
        const avgDelay = delayedFlights.length
          ? round1(delayedFlights.reduce((s, f) => s + f.delay_minutes, 0) / delayedFlights.length)
          : 0
        const sampled = trendEmptyHint('sim-kpi', vm.simCurrentTime, {
          punctuality: vm.punctuality || 0,
          completion_rate: round1(parked / total * 100),
          avg_delay: avgDelay,
          delayed_count: vm.delayedCount || 0,
          cancelled_count: vm.cancelledCount || 0,
          active_events: (vm.activeEvents || []).length,
        }, '需要先启动仿真并让它运行一段时间')
        if (typeof sampled === 'object' && sampled.__empty) return sampled
        const times = sampled.map(s => s[0])
        const pick = k => sampled.map(s => (s[1][k] !== undefined ? s[1][k] : null))
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 4 },
          grid,
          xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 10 } },
          yAxis: [
            { type: 'value', name: '百分比 %', min: 0, max: 100 },
            { type: 'value', name: '架次 / 分钟' },
          ],
          series: [
            { name: '准点率 %', type: 'line', data: pick('punctuality'), symbol: 'circle', symbolSize: 5, lineStyle: { color: PALETTE[1] } },
            { name: '完成率 %', type: 'line', data: pick('completion_rate'), symbol: 'circle', symbolSize: 5, lineStyle: { color: PALETTE[0] } },
            { name: '延误架次', type: 'line', yAxisIndex: 1, data: pick('delayed_count'), symbol: 'triangle', symbolSize: 6, lineStyle: { color: PALETTE[2] } },
            { name: '取消架次', type: 'line', yAxisIndex: 1, data: pick('cancelled_count'), symbol: 'triangle', symbolSize: 6, lineStyle: { color: PALETTE[3] } },
            { name: '激活事件数', type: 'line', yAxisIndex: 1, data: pick('active_events'), symbol: 'diamond', symbolSize: 6, lineStyle: { color: PALETTE[4], type: 'dashed' } },
            { name: '平均延误(分钟)', type: 'line', yAxisIndex: 1, data: pick('avg_delay'), symbol: 'none', lineStyle: { color: PALETTE[5], type: 'dotted' } },
          ],
        }
      },
    },
    {
      id: 'sm-state',
      title: '航班状态数量堆叠面积',
      note: '把底部状态栏的裸数字变成曲线。堆叠三条（空中/延误/取消）为快照瞬时数量，口径可能小幅重叠（延误航班也可能在空中）；「总航班数」单列虚线便于对比',
      build: () => {
        if (!snapshotReady(vm)) return noData('还没有仿真快照——请先点「🚀 启动仿真」并等时间轴推进')
        const sampled = trendEmptyHint('sim-state', vm.simCurrentTime, {
          flightCount: vm.flightCount || 0,
          airborneCount: vm.airborneCount || 0,
          delayedCount: vm.delayedCount || 0,
          cancelledCount: vm.cancelledCount || 0,
        }, '需要先启动仿真并让它运行一段时间')
        if (typeof sampled === 'object' && sampled.__empty) return sampled
        const times = sampled.map(s => s[0])
        const pick = k => sampled.map(s => (s[1][k] !== undefined ? s[1][k] : null))
        const area = (name, key, color) => ({
          name, type: 'line', stack: 'state', symbol: 'none',
          areaStyle: { opacity: 0.5, color }, lineStyle: { color, width: 1 },
          data: pick(key),
        })
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 4 },
          grid,
          xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 10 } },
          yAxis: { type: 'value', name: '架次' },
          series: [
            area('空中', 'airborneCount', PALETTE[0]),
            area('延误', 'delayedCount', PALETTE[2]),
            area('取消', 'cancelledCount', PALETTE[3]),
            { name: '总航班数', type: 'line', symbol: 'none', lineStyle: { color: PALETTE[4], type: 'dashed' }, data: pick('flightCount') },
          ],
        }
      },
    },
    {
      id: 'sm-delayhist',
      title: '延误分钟数分布',
      note: '对当前快照 flights[] 的 delay_minutes（>0 才算延误）分桶计数；随仿真推进重复打开图表或用「实时」可看到分布变化',
      build: () => {
        if (!snapshotReady(vm)) return noData('还没有仿真快照——请先点「🚀 启动仿真」并等时间轴推进')
        const delayed = vm.flights.filter(f => (f.delay_minutes || 0) > 0)
        if (!delayed.length) return noData('当前快照里没有 delay_minutes > 0 的航班（还没有延误发生，或延误事件尚未注入）')
        const counts = DELAY_BINS.map(b => delayed.filter(f => f.delay_minutes >= b.min && f.delay_minutes < b.max).length)
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid,
          xAxis: { type: 'category', data: DELAY_BINS.map(b => b.label) },
          yAxis: { type: 'value', name: '架次' },
          series: [{
            name: '延误航班数', type: 'bar', data: counts,
            itemStyle: { color: PALETTE[2] },
            label: { show: true, position: 'top', fontSize: 11 },
          }],
        }
      },
    },
    {
      id: 'sm-phase',
      title: '航班相位分布',
      note: '当前快照 flights[] 按 phase 计数（scheduled→parked 全流程 + delayed/cancelled 异常态），可以看出航班在运行链路上的堆积位置',
      build: () => {
        if (!snapshotReady(vm)) return noData('还没有仿真快照——请先点「🚀 启动仿真」并等时间轴推进')
        const counts = {}
        vm.flights.forEach(f => { counts[f.phase] = (counts[f.phase] || 0) + 1 })
        const labels = PHASES.map(p => PHASE_LABELS[p])
        const data = PHASES.map(p => counts[p] || 0)
        if (!data.some(v => v > 0)) return noData('快照里的航班都没有可识别的 phase 字段')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid: { left: 56, right: 24, top: 40, bottom: 70, containLabel: true },
          xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10, interval: 0 } },
          yAxis: { type: 'value', name: '架次' },
          series: [{
            name: '航班数', type: 'bar', data, itemStyle: { color: PALETTE[0] },
            label: { show: true, position: 'top', fontSize: 10 },
          }],
        }
      },
    },
  ]
}

export default buildSimMapCharts
