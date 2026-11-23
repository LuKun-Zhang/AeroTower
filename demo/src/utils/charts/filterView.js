/**
 * 航班筛选工作台（FilterView）的图表集合。
 * 数据全部来自 vm 已有状态：
 * - vm.stats：total_flights / closed_count / orphan_count / city_coverage（'x/y' 字符串）
 * - vm.chains：已加载任务链，每条是航班对象数组（chain.length = 段数）
 * - vm.orphans：已加载不合格航班 [{ flight, reason }]
 * - vm.bases：基地城市列表
 * 链与 orphans 都是分页加载（「加载更多」），相关图 note 标明基于已加载部分。
 */
import { noData, PALETTE } from '../chartBase'

const grid = { left: 64, right: 30, top: 46, bottom: 60, containLabel: true }

function notRunHint() {
  return noData('还没有筛选结果：先点工具栏「执行筛选」（可直接用默认数据，或先上传 xlsx），出结果后再看本图')
}

export function buildFilterCharts(vm) {
  const stats = vm.stats || {}
  const chains = vm.chains || []
  const orphans = vm.orphans || []

  return [
    {
      id: 'fv-funnel',
      title: '筛选漏斗',
      note: '总航班 → 合格 / 不合格 的数量对比，来自 stats 汇总（全量，不受分页影响）',
      build: () => {
        if (!vm.filterResult) return notRunHint()
        const total = Number(stats.total_flights) || 0
        if (total <= 0) return noData('stats.total_flights 为 0：本次筛选没有输入航班，请检查上传的 xlsx 是否含航班数据')
        const closed = Number(stats.closed_count) || 0
        const orphan = Number(stats.orphan_count) || 0
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid,
          xAxis: { type: 'category', data: ['总航班', '合格航班', '不合格航班'] },
          yAxis: { type: 'value', name: '航班数' },
          series: [{
            name: '航班数', type: 'bar', barWidth: '46%',
            data: [
              { value: total, itemStyle: { color: PALETTE[0] } },
              { value: closed, itemStyle: { color: PALETTE[1] } },
              { value: orphan, itemStyle: { color: PALETTE[3] } },
            ],
            label: { show: true, position: 'top', fontSize: 12 },
          }],
        }
      },
    },
    {
      id: 'fv-pareto',
      title: '不合格原因帕累托图',
      note: `柱=各原因的不合格航班数（降序），折线=累计占比；统计基于已加载的不合格航班（${orphans.length}/${vm.orphanTotal || 0} 条）`,
      build: () => {
        if (!vm.filterResult) return notRunHint()
        if (!orphans.length) {
          return noData(`当前没有已加载的不合格航班（stats.orphan_count=${stats.orphan_count || 0}）：全部航班都合格时无需帕累托分析`)
        }
        const counts = {}
        orphans.forEach(o => {
          const r = o.reason || '未知原因'
          counts[r] = (counts[r] || 0) + 1
        })
        const rows = Object.keys(counts)
          .map(r => ({ reason: r, count: counts[r] }))
          .sort((a, b) => b.count - a.count)
        let cum = 0
        const cumPct = rows.map(r => {
          cum += r.count
          return Math.round((cum / orphans.length) * 1000) / 10
        })
        return {
          tooltip: { trigger: 'axis' },
          legend: { data: ['航班数', '累计占比'], top: 6 },
          grid,
          xAxis: {
            type: 'category',
            data: rows.map(r => r.reason.length > 10 ? r.reason.slice(0, 10) + '…' : r.reason),
            axisLabel: { rotate: 30, fontSize: 11 },
          },
          yAxis: [
            { type: 'value', name: '航班数' },
            { type: 'value', name: '累计 %', min: 0, max: 100, splitLine: { show: false } },
          ],
          series: [
            { name: '航班数', type: 'bar', data: rows.map(r => r.count), itemStyle: { color: PALETTE[2] } },
            {
              name: '累计占比', type: 'line', yAxisIndex: 1, data: cumPct,
              symbolSize: 7, itemStyle: { color: PALETTE[3] },
              label: { show: true, formatter: '{c}%', fontSize: 10 },
            },
          ],
        }
      },
    },
    {
      id: 'fv-chainlen',
      title: '任务链长度分布',
      note: `横轴=链条段数，纵轴=链条数；统计基于已加载任务链（${chains.length}/${vm.chainTotal || 0} 条，可点「加载更多」后再刷新图表）`,
      build: () => {
        if (!vm.filterResult) return notRunHint()
        if (!chains.length) return noData('任务链池为空：筛选没有产出一条合格链，说明航班衔接全部失败，看「不合格原因帕累托图」定位原因')
        const dist = {}
        chains.forEach(c => {
          const n = Array.isArray(c) ? c.length : Number(c && c.length)
          if (n > 0) dist[n] = (dist[n] || 0) + 1
        })
        const keys = Object.keys(dist).map(Number).sort((a, b) => a - b)
        if (!keys.length) return noData('已加载的任务链都是空链（length=0），无法统计段数分布')
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
      id: 'fv-coverage',
      title: '基地航班量与站点覆盖',
      note: `各基地的出港/进港航班数（基于已加载任务链 ${chains.length}/${vm.chainTotal || 0} 条）；末两类为 stats.city_coverage（${stats.city_coverage || '—'}）拆成的已/未覆盖站点数，单位为站点而非航班`,
      build: () => {
        if (!vm.filterResult) return notRunHint()
        const bases = vm.bases || []
        const dep = {}
        const arr = {}
        bases.forEach(b => { dep[b] = 0; arr[b] = 0 })
        chains.forEach(c => {
          (c || []).forEach(f => {
            if (dep[f.departure_airport] !== undefined) dep[f.departure_airport]++
            if (arr[f.arrival_airport] !== undefined) arr[f.arrival_airport]++
          })
        })
        // city_coverage 形如 '12/20'：已覆盖 / 全部站点
        const cov = String(stats.city_coverage || '').match(/(\d+)\s*\/\s*(\d+)/)
        const covered = cov ? Number(cov[1]) : null
        const totalCities = cov ? Number(cov[2]) : null
        const uncovered = (covered !== null && totalCities !== null) ? Math.max(0, totalCities - covered) : null

        if (!bases.length && covered === null) {
          return noData('筛选结果里既没有基地列表（bases）也没有站点覆盖字符串（city_coverage），无法绘制本图')
        }
        const categories = covered !== null ? [...bases, '已覆盖站点', '未覆盖站点'] : [...bases]
        const pad = bases.length
        const depVals = bases.map(b => dep[b])
        const arrVals = bases.map(b => arr[b])
        while (depVals.length < categories.length) { depVals.push(null); arrVals.push(null) }
        const siteVals = new Array(categories.length).fill(null)
        if (covered !== null) { siteVals[pad] = covered; siteVals[pad + 1] = uncovered }
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { data: ['出港航班', '进港航班', '站点数'], top: 6 },
          grid,
          xAxis: { type: 'category', data: categories, axisLabel: { rotate: 30, fontSize: 11 } },
          yAxis: { type: 'value' },
          series: [
            { name: '出港航班', type: 'bar', data: depVals, itemStyle: { color: PALETTE[0] } },
            { name: '进港航班', type: 'bar', data: arrVals, itemStyle: { color: PALETTE[1] } },
            {
              name: '站点数', type: 'bar', data: siteVals,
              itemStyle: { color: PALETTE[4] },
              label: { show: true, position: 'top', fontSize: 11, formatter: p => (p.value === null ? '' : p.value) },
            },
          ],
        }
      },
    },
  ]
}

export default buildFilterCharts
