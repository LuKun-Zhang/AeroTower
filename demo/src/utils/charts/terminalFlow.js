/**
 * 模拟大引擎 → 旅客流（TerminalFlowView）的图表集合。
 * 数据全部来自 TerminalFlowView 每 200ms 从 TerminalLayout 轮询回来的 vm 字段：
 *   congestionLevels[]（{corridorIdx, density, level}）、corridorControlList[]（走廊名）、
 *   simTime（业务分钟）、paxCount、planeCount、
 *   evacuationActive / evacuationTotal / evacuationArrived、
 *   simFlights[]（paxBoarded / paxTotal / type）。
 * 趋势图用 addSample 按业务分钟（Math.floor(simTime)）幂等攒历史。
 */
import { noData, PALETTE, addSample, getSamples } from '../chartBase'
import { isoBarOption } from './isoBars'

const grid = { left: 76, right: 30, top: 52, bottom: 60, containLabel: true }

/** 业务分钟 → 'HH:MM'（与页面 header 的 formatTime 同口径） */
function fmtMin(m) {
  const h = Math.floor(m / 60) % 24
  const mm = Math.floor(m % 60)
  return String(h).padStart(2, '0') + ':' + String(mm).padStart(2, '0')
}

/** 当前仿真业务时刻（分钟取整做幂等键）；未推进时返回 null */
function bizMinute(vm) {
  const t = Math.floor(vm.simTime || 0)
  return t > 0 ? t : null
}

/** 采样并做「至少 2 点」的空态判断 */
function sampleOrHint(key, ts, values, need) {
  addSample(key, ts, values, 1500)
  const samples = getSamples(key)
  if (samples.length < 2) {
    return { __emptySeries: true, msg: noData(need + '（当前已攒 ' + samples.length + ' 个点；浮层里点「实时」可持续采样）') }
  }
  return { samples }
}

export function buildTerminalFlowCharts(vm) {
  return [
    {
      id: 'tf-congheat',
      title: '路段拥堵 × 时间 立体柱',
      note: '等距 3D 立体柱矩阵：横轴=业务时刻桶、纵轴=走廊。柱高=拥堵密度%+1 基线——density 0（畅通）在原始语义里是有意义的取值，但渲染器不画 0 值柱，故整体平移 +1 让畅通也立一根矮柱，柱高大小顺序与原 density 完全一致，真实密度%看悬浮 tip。走廊全量可能很多，按「历史峰值密度↓」排序只展示 Top 16 走廊；时间桶只保留最近 60 个采样点。数据口径不变：格子来自该走廊在该业务时刻的 density（旅客数/容量，0-100%）。需要先在右侧「拥堵热力图」面板开启统计；关闭统计时布局会清空 levels，也就攒不到新点',
      build: (theme) => {
        const ts = bizMinute(vm)
        if (ts === null) return noData('仿真时间轴还没推进——请先启动旅客流仿真并让它运行一段时间')
        const levels = vm.congestionLevels || []
        if (!levels.length) return noData('当前没有拥堵采样数据——请先在右侧「拥堵热力图」面板打开开关，再让仿真运行一段时间')
        const vals = {}
        levels.forEach(cl => { vals['c' + cl.corridorIdx] = Math.round((cl.density || 0) * 100) })
        const r = sampleOrHint('tflow-cong', ts, vals, '需要先启动仿真并让它运行一段时间')
        if (r.__emptySeries) return r.msg
        const corridorNames = (vm.corridorControlList || [])
        const nameOf = k => {
          const i = parseInt(k.slice(1), 10)
          const c = corridorNames[i]
          return c ? c.label : ('走廊#' + i)
        }
        // 走廊筛减：按历史峰值密度取 Top 16，再按走廊序号排 y 轴顺序
        const union = {}
        r.samples.forEach(([, v]) => Object.keys(v).forEach(k => { union[k] = true }))
        const allKeys = Object.keys(union).sort((a, b) => parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10))
        const peakOf = k => {
          let peak = 0
          r.samples.forEach(([, v]) => { if (v[k] !== undefined) peak = Math.max(peak, v[k]) })
          return peak
        }
        const keptKeys = allKeys
          .slice().sort((a, b) => peakOf(b) - peakOf(a))
          .slice(0, 16)
          .sort((a, b) => parseInt(a.slice(1), 10) - parseInt(b.slice(1), 10))
        // 时间桶：保持现有 ts（业务分钟）口径，只画最近 60 个采样桶
        const recent = r.samples.slice(-60)
        const times = recent.map(s => fmtMin(s[0]))
        const cells = []
        recent.forEach(([, v], xi) => {
          keptKeys.forEach((k, yi) => {
            if (v[k] !== undefined) {
              const d = v[k]
              cells.push({
                xi, yi, v: d + 1,
                tip: `${nameOf(k)} · ${times[xi]}<br/>拥堵密度 ${d}%`,
              })
            }
          })
        })
        return isoBarOption({
          theme,
          xLabels: times,
          yLabels: keptKeys.map(nameOf),
          cells,
          valueName: '拥堵度%+1',
          sceneTitle: '拥堵密度%（+1 基线，看 tip 原值）',
          maxBars: 960,
          maxTicks: 10,
          ramp: ['#67c23a', '#e6a23c', '#f56c6c'],
          emptyText: '走廊统计里还没有任何密度采样记录',
        })
      },
    },
    {
      id: 'tf-paxcount',
      title: '在场旅客数时序',
      note: 'paxCount=航站楼层在场旅客粒子数，planeCount=在场飞机数，均取自 TerminalLayout 轮询快照，按业务分钟攒历史',
      build: () => {
        const ts = bizMinute(vm)
        if (ts === null) return noData('仿真还没启动或时间轴未推进——请先启动旅客流仿真')
        const r = sampleOrHint('pax-count', ts, {
          paxCount: vm.paxCount || 0,
          planeCount: vm.planeCount || 0,
        }, '需要先启动仿真并让它运行一段时间')
        if (r.__emptySeries) return r.msg
        const times = r.samples.map(s => fmtMin(s[0]))
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 4 },
          grid,
          xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 10 } },
          yAxis: { type: 'value', name: '人数 / 架次' },
          series: [
            { name: '在场旅客', type: 'line', data: r.samples.map(s => s[1].paxCount), symbol: 'circle', symbolSize: 5, lineStyle: { color: PALETTE[0] }, areaStyle: { opacity: 0.18, color: PALETTE[0] } },
            { name: '在场飞机', type: 'line', data: r.samples.map(s => s[1].planeCount), symbol: 'triangle', symbolSize: 6, lineStyle: { color: PALETTE[2] } },
          ],
        }
      },
    },
    {
      id: 'tf-evac',
      title: '疏散进度双线',
      note: 'totalEvacuating=疏散中旅客数，totalArrived=累计已到达出口数。仅在开启疏散（或已有疏散计数）时采样',
      build: () => {
        const hasEvacData = vm.evacuationActive
          || (vm.evacuationTotal || 0) > 0
          || (vm.evacuationArrived || 0) > 0
        const ts = bizMinute(vm)
        if (hasEvacData && ts !== null) {
          addSample('evac', ts, {
            totalEvacuating: vm.evacuationTotal || 0,
            totalArrived: vm.evacuationArrived || 0,
          }, 1500)
        }
        const samples = getSamples('evac')
        if (!samples.length) return noData('还没有疏散数据——请在右侧「紧急疏散」面板点「开始疏散」，并让仿真运行一段时间后再打开图表')
        if (samples.length < 2) return noData('需要先启动仿真并让它运行一段时间（疏散采样还不足 2 个点，浮层里点「实时」可持续采样）')
        const times = samples.map(s => fmtMin(s[0]))
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 4 },
          grid,
          xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 10 } },
          yAxis: { type: 'value', name: '人数' },
          series: [
            { name: '疏散中', type: 'line', data: samples.map(s => s[1].totalEvacuating), symbol: 'circle', symbolSize: 5, lineStyle: { color: PALETTE[3] }, areaStyle: { opacity: 0.15, color: PALETTE[3] } },
            { name: '已到达出口(累计)', type: 'line', data: samples.map(s => s[1].totalArrived), symbol: 'circle', symbolSize: 5, lineStyle: { color: PALETTE[1] } },
          ],
        }
      },
    },
    {
      id: 'tf-boarding',
      title: '各航班登机进度排行',
      note: '当前快照 simFlights[] 中出发航班的 paxBoarded/paxTotal 百分比（页面里是逐行 CSS 进度条，这里排成条形），进度高的在上方',
      build: () => {
        const rows = (vm.simFlights || [])
          .filter(f => f.type === 'departure' && (f.paxTotal || 0) > 0)
          .map(f => ({
            name: f.flightNo,
            pct: Math.round((f.paxBoarded || 0) / f.paxTotal * 100),
            boarded: f.paxBoarded || 0,
            total: f.paxTotal,
          }))
          .sort((a, b) => a.pct - b.pct)
        if (!rows.length) return noData('当前日期没有携带旅客的出发航班（paxTotal 都是 0）——请确认已加载航班调度并启动仿真')
        return {
          tooltip: {
            trigger: 'axis', axisPointer: { type: 'shadow' },
            formatter: ps => ps.map(p => {
              const r = rows[p.dataIndex]
              return `${r.name}：${r.boarded}/${r.total} 人（${r.pct}%）`
            }).join('<br/>'),
          },
          grid: { left: 96, right: 48, top: 24, bottom: 40, containLabel: true },
          xAxis: { type: 'value', name: '登机进度 %', max: 100 },
          yAxis: { type: 'category', data: rows.map(r => r.name), axisLabel: { fontSize: 10 } },
          series: [{
            name: '登机进度%', type: 'bar', data: rows.map(r => r.pct),
            itemStyle: { color: p => (p.value >= 100 ? PALETTE[1] : PALETTE[0]) },
            label: { show: true, position: 'right', fontSize: 10, formatter: '{c}%' },
          }],
        }
      },
    },
  ]
}

export default buildTerminalFlowCharts
