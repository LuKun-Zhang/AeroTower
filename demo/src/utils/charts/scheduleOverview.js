/**
 * 航班计划总览页（/schedule-overview）的图表集合。
 * 数据全部来自 ScheduleOverview 已加载的状态：
 * - vm.stats：statsData（total_flights / total_chains / ferry_flights / ...）
 * - vm.chains：chainsList（每条含 chain_id / segments / total_pax / flights）
 * - vm.flights：flightsList（后端生成结果 to_dict 口径，含 time_departure / layout / pax_count / is_ferry）
 */
import { noData, PALETTE } from '../chartBase'

const grid = { left: 64, right: 30, top: 46, bottom: 42, containLabel: true }

// time_departure 可能是字符串 'YYYY-MM-DD HH:MM'（生成结果 to_dict 口径），
// 也可能是数组 [y, m, d, h, min]（调度侧序列化口径），两种都解析出小时。
function departureHour(t) {
  if (Array.isArray(t)) {
    const h = parseInt(t[3], 10)
    return h >= 0 && h < 24 ? h : null
  }
  if (typeof t === 'string') {
    const m = t.match(/(\d{1,2}):(\d{2})/)
    if (m) {
      const h = parseInt(m[1], 10)
      return h >= 0 && h < 24 ? h : null
    }
  }
  return null
}

// layout 形如 'C8Y124' → 公务 8 + 经济 124 = 132 座；解析不出返回 null
function layoutSeats(layout) {
  if (typeof layout !== 'string') return null
  const parts = layout.match(/[CY]\d+/g) || []
  if (!parts.length) return null
  let total = 0
  parts.forEach(p => { total += parseInt(p.slice(1), 10) || 0 })
  return total > 0 ? total : null
}

function emptyPlanHint() {
  return noData('还没有航班计划数据：请先在「客流量输入」页填客流并点「生成航班计划」')
}

export function buildScheduleOverviewCharts(vm) {
  const flights = vm.flights || []
  const chains = vm.chains || []
  const stats = vm.stats || {}

  return [
    {
      id: 'so-hourly',
      title: '航段按小时分布',
      note: '按航班起飞小时（0-23 点）分桶计数；统计基于已加载航班（接口上限 2000 条）',
      build: () => {
        if (!flights.length) return emptyPlanHint()
        const buckets = new Array(24).fill(0)
        let parsed = 0
        flights.forEach(f => {
          const h = departureHour(f.time_departure)
          if (h !== null) { buckets[h]++; parsed++ }
        })
        if (!parsed) {
          return noData('航班数据里的 time_departure 解析不出小时：既不是含 HH:MM 的字符串，也不是 [y,m,d,h,min] 数组，无法分桶')
        }
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid,
          xAxis: { type: 'category', data: buckets.map((_, i) => `${i}时`), axisLabel: { interval: 1, fontSize: 10 } },
          yAxis: { type: 'value', name: '航段数' },
          series: [{
            name: '起飞航段', type: 'bar', data: buckets,
            itemStyle: { color: PALETTE[0] },
          }],
        }
      },
    },
    {
      id: 'so-chainlen',
      title: '任务链段数分布',
      note: '横轴=每条任务链的航段数，纵轴=该段数的链条数（全量链列表）',
      build: () => {
        if (!chains.length) return noData('还没有任务链：请先在「客流量输入」页生成航班计划')
        const dist = {}
        chains.forEach(c => {
          const n = Number(c.segments)
          if (n > 0) dist[n] = (dist[n] || 0) + 1
        })
        const keys = Object.keys(dist).map(Number).sort((a, b) => a - b)
        if (!keys.length) return noData('任务链的 segments 字段都不是正数，无法统计段数分布')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid,
          xAxis: { type: 'category', data: keys.map(n => `${n} 段`) },
          yAxis: { type: 'value', name: '链条数' },
          series: [{
            name: '链条数', type: 'bar', data: keys.map(n => dist[n]),
            itemStyle: { color: PALETTE[5] },
            label: { show: true, position: 'top', fontSize: 11 },
          }],
        }
      },
    },
    {
      id: 'so-city',
      title: '各城市航班量 vs 旅客量',
      note: '按出港城市汇总（不含空飞航班），左轴=航班数，右轴=旅客人次，Top 16 按旅客量排序',
      build: () => {
        const revenue = flights.filter(f => !f.is_ferry)
        if (!revenue.length) return noData('已加载航班里没有载客航班（全是空飞或航班为空）')
        const map = {}
        revenue.forEach(f => {
          const c = f.departure_airport || '未知'
          if (!map[c]) map[c] = { flights: 0, pax: 0 }
          map[c].flights++
          map[c].pax += Number(f.pax_count) || 0
        })
        const rows = Object.keys(map)
          .map(c => ({ city: c, flights: map[c].flights, pax: map[c].pax }))
          .sort((a, b) => b.pax - a.pax)
          .slice(0, 16)
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: ['航班数', '旅客人次'], top: 6 },
          grid,
          xAxis: { type: 'category', data: rows.map(r => r.city), axisLabel: { rotate: 40, fontSize: 11 } },
          yAxis: [
            { type: 'value', name: '航班数' },
            { type: 'value', name: '旅客人次', splitLine: { show: false } },
          ],
          series: [
            { name: '航班数', type: 'bar', data: rows.map(r => r.flights), itemStyle: { color: PALETTE[0] } },
            { name: '旅客人次', type: 'bar', yAxisIndex: 1, data: rows.map(r => r.pax), itemStyle: { color: PALETTE[2] } },
          ],
        }
      },
    },
    {
      id: 'so-ferry',
      title: '空飞（调机）占比',
      note: 'ferry_flights / total_flights，来自页面 stats 汇总',
      build: () => {
        const total = Number(stats.total_flights)
        if (!(total > 0)) return emptyPlanHint()
        const ferry = Math.min(total, Math.max(0, Number(stats.ferry_flights) || 0))
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 班 ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie', radius: ['40%', '64%'], center: ['50%', '58%'],
            data: [
              { name: '载客航班', value: total - ferry, itemStyle: { color: PALETTE[1] } },
              { name: '空飞（调机）', value: ferry, itemStyle: { color: PALETTE[3] } },
            ],
            label: { formatter: '{b}\n{c} 班 ({d}%)' },
          }],
        }
      },
    },
    {
      id: 'so-loadfactor',
      title: '客座利用分布',
      note: '每点=一个载客航班：x=按 layout 解析的座位数（如 C8Y124=132），y=pax_count，颜色=客座率；基于已加载航班（上限 2000 条）',
      build: () => {
        const pts = []
        let noLayout = 0
        flights.forEach(f => {
          if (f.is_ferry) return
          const seats = layoutSeats(f.layout)
          if (!seats) { noLayout++; return }
          const pax = Number(f.pax_count) || 0
          pts.push({ value: [seats, pax, Math.round((pax / seats) * 1000) / 10], name: f.flight_no })
        })
        if (!pts.length) {
          return noData(noLayout
            ? '航班数据里的 layout 都解析不出座位数（形如 C8Y124 的字段缺失或格式不符），无法计算客座利用率'
            : '已加载航班里没有载客航班')
        }
        return {
          tooltip: {
            trigger: 'item',
            formatter: p => `${p.data.name}<br/>座位 ${p.value[0]} · 旅客 ${p.value[1]} · 客座率 ${p.value[2]}%`,
          },
          grid,
          xAxis: { type: 'value', name: '座位数', min: 0 },
          yAxis: { type: 'value', name: '旅客数', min: 0 },
          visualMap: {
            dimension: 2, min: 0, max: 100, calculable: true,
            orient: 'horizontal', left: 'center', bottom: 0,
            inRange: { color: ['#36cfc9', '#e6a23c', '#f56c6c'] },
          },
          series: [{
            name: '航班', type: 'scatter', symbolSize: 7,
            data: pts,
          }],
        }
      },
    },
  ]
}

export default buildScheduleOverviewCharts
