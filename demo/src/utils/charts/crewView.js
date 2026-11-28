/**
 * 机组排班页（CrewView）的图表集合。
 * 数据全部来自 POST /schedule/crew 响应在 vm 上的落地：
 *   vm.crew[]（crew_id/name/role_label/daily_flight_hours/seven_day_flight_hours/
 *              thirty_day_flight_hours/violations[]/flight_count/assigned_flights[]）
 *   vm.pairings[]（pairing_id/cost/utilization/num_flights）、vm.coverage、vm.crewRows（甘特行）。
 * 未执行排班时以上均为空，对应图返回 noData。
 */
import { noData, PALETTE, themeColors } from '../chartBase'
import { isoBarOption } from './isoBars'

// 法规上限为后端代码写死值，不是前端编造：
//   日 8h： backend/services/crew_service.py → max_daily_hours=8
//   7 日 40h： backend/models/crew.py → CCAR121_7DAY_MAX_HOURS = 40
//   30 日 100h：backend/models/crew.py → CCAR121_30DAY_MAX_HOURS = 100
const LIMIT_DAILY = 8
const LIMIT_7DAY = 40
const LIMIT_30DAY = 100

// 人员 × 日期 立体柱：纵深轴（人员）只保留总执勤小时最高的前 N 人
const CV_TOP_N = 20

const grid = { left: 76, right: 24, top: 46, bottom: 70, containLabel: true }

function noSchedule() {
  return noData('暂无排班数据：请先在「航班筛选」页上传并执行筛选，再回到本页（系统会自动运行机组排班）')
}

export function buildCrewCharts(vm) {
  return [
    {
      id: 'cv-limit-compliance',
      title: '执勤限制合规',
      note: `每人日/7日/30日飞行小时三组柱，虚线为法规上限（日${LIMIT_DAILY}h、7日${LIMIT_7DAY}h、30日${LIMIT_30DAY}h，均取自 backend/models/crew.py 与 crew_service.py 写死值），取任务最多的前 30 人`,
      build: (theme) => {
        const crew = vm.crew || []
        if (!crew.length) return noSchedule()
        const rows = crew.slice()
          .sort((a, b) => (b.flight_count || 0) - (a.flight_count || 0) || (b.thirty_day_flight_hours || 0) - (a.thirty_day_flight_hours || 0))
          .slice(0, 30)
        const names = rows.map(c => c.name)
        const mk = key => rows.map(c => Number(c[key]) || 0)
        const bar = (name, key, limit, color) => ({
          name,
          type: 'bar',
          data: mk(key),
          itemStyle: { color },
          markLine: {
            symbol: 'none',
            silent: true,
            lineStyle: { type: 'dashed', color },
            label: { formatter: `${name}上限 ${limit}h`, position: 'insideEndTop', color },
            data: [{ yAxis: limit }],
          },
        })
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => `${v} h` },
          legend: { top: 6 },
          grid,
          xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 45, fontSize: 10 } },
          yAxis: { type: 'value', name: '小时' },
          series: [
            bar('日飞行', 'daily_flight_hours', LIMIT_DAILY, PALETTE[0]),
            bar('7日飞行', 'seven_day_flight_hours', LIMIT_7DAY, PALETTE[1]),
            bar('30日飞行', 'thirty_day_flight_hours', LIMIT_30DAY, PALETTE[2]),
          ],
        }
      },
    },
    {
      id: 'cv-role-pie',
      title: '机组角色构成',
      note: '按人员名册 role_label 统计机长/副驾驶/乘务长/乘务员人数',
      build: (theme) => {
        const crew = vm.crew || []
        if (!crew.length) return noSchedule()
        const counts = {}
        crew.forEach(c => {
          const k = c.role_label || c.role || '未知'
          counts[k] = (counts[k] || 0) + 1
        })
        const data = Object.keys(counts).map(k => ({ name: k, value: counts[k] }))
        const c = themeColors(theme)
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie', radius: ['36%', '62%'], center: ['50%', '58%'], data,
            label: { color: c.text, formatter: '{b}\n{c} 人 ({d}%)' },
            labelLine: { lineStyle: { color: c.axis } },
          }],
        }
      },
    },
    {
      id: 'cv-pairing-scatter',
      title: '任务链 成本-利用率',
      note: '每个点是一条任务链（pairings），横轴成本、纵轴利用率%，点大小随段数 num_flights；右下角=便宜又满负荷',
      build: () => {
        const ps = (vm.pairings || []).filter(p => typeof p.cost === 'number' && typeof p.utilization === 'number')
        if (!ps.length) return noData('暂无任务链数据：需先执行机组排班；若刚切换基地/日期请等待排班完成')
        const maxSeg = ps.reduce((m, p) => Math.max(m, p.num_flights || 1), 1)
        return {
          tooltip: {
            formatter: p => `任务链 #${p.data[3]}<br/>成本 ${Math.round(p.data[0])}｜利用率 ${p.data[1]}%｜${p.data[2]} 段`,
          },
          grid,
          xAxis: { type: 'value', name: '成本', scale: true },
          yAxis: { type: 'value', name: '利用率(%)' },
          series: [{
            type: 'scatter',
            symbolSize: d => 6 + ((d[2] || 1) / maxSeg) * 24,
            itemStyle: { color: PALETTE[0], opacity: 0.75 },
            data: ps.map(p => [Math.round(p.cost * 100) / 100, Math.round(p.utilization * 1000) / 10, p.num_flights || 1, p.pairing_id]),
          }],
        }
      },
    },
    {
      id: 'cv-duty-heatmap',
      title: '人员 × 日期 执勤立体柱',
      note: `菱形地面：左前棱=日期（按原顺序），右前棱=人员；柱子立在该人该日格子上，柱高=当日实际执勤小时（由甘特行 day_hours 按人-日聚合）。人员多时取总执勤小时最高的前 ${CV_TOP_N} 人，其余不画；可拖左下色条只保留重执勤日`,
      build: (theme) => {
        const rows = (vm.crewRows || []).filter(r => !r.is_team_header && (r.flights || []).length > 0)
        if (!rows.length) return noData('甘特图中没有执勤航班块：需排班已生成且人员有已分配航班（可先点「自动填充」或「组建机组」）')
        const agg = {}
        rows.forEach(r => {
          const k = `${r.name}|${r.date}`
          agg[k] = (agg[k] || 0) + (Number(r.day_hours) || 0)
        })
        const dates = [...new Set(rows.map(r => r.date))].sort()
        // 渲染器的刻度标签只留 7 个字符，所以轴标签去掉年份（完整日期写在 tooltip 里）
        const xLabels = dates.map(d => {
          const s = String(d)
          return s.length > 7 && s.charAt(4) === '-' ? s.slice(5) : s
        })
        // 键是人名，用无原型对象避免与 Object 内置属性名冲突
        const totals = Object.create(null)
        Object.keys(agg).forEach(k => {
          const p = k.split('|')
          totals[p[0]] = (totals[p[0]] || 0) + agg[k]
        })
        const names = Object.keys(totals)
          .filter(n => totals[n] > 0)
          .sort((a, b) => totals[b] - totals[a])
          .slice(0, CV_TOP_N)
        const nIdx = Object.create(null)
        names.forEach((n, i) => { nIdx[n] = i })
        const cells = []
        Object.keys(agg).forEach(k => {
          const p = k.split('|')
          const yi = nIdx[p[0]]
          const xi = dates.indexOf(p[1])
          if (yi === undefined || xi < 0) return
          const v = Math.round(agg[k] * 10) / 10
          if (!(v > 0)) return
          cells.push({ xi, yi, v, tip: `${p[0]} ${p[1]}<br/>执勤 ${v} 小时` })
        })
        if (!cells.length) return noData('这些人的 day_hours 全是 0，画不出执勤强度：请确认排班结果里已分配航班')
        return isoBarOption({
          theme,
          xLabels,
          yLabels: names,
          cells,
          valueName: '执勤小时',
          maxBars: CV_TOP_N * dates.length,
          maxTicks: 12,
          emptyText: '当前没有大于 0 的当日执勤小时',
          sceneTitle: '人员 × 日期 执勤小时',
        })
      },
    },
    {
      id: 'cv-coverage-gauge',
      title: '航班覆盖率',
      note: (() => {
        const cov = vm.coverage
        return cov
          ? `已覆盖 ${cov.covered_flights}/${cov.total_flights} 班，未覆盖 ${cov.uncovered_flights} 班（数据来自本次排班响应 coverage）`
          : '仪表盘读取排班响应 coverage.coverage_pct'
      })(),
      build: (theme) => {
        const cov = vm.coverage
        if (!cov || cov.coverage_pct === undefined || cov.coverage_pct === null) {
          return noData('暂无覆盖率数据：需先执行机组排班')
        }
        const c = themeColors(theme)
        return {
          series: [{
            type: 'gauge', min: 0, max: 100, splitNumber: 5, radius: '78%', center: ['50%', '58%'],
            progress: { show: true, width: 14, itemStyle: { color: PALETTE[0] } },
            axisLine: { lineStyle: { width: 14, color: [[1, c.split]] } },
            axisTick: { lineStyle: { color: c.axis } },
            splitLine: { lineStyle: { color: c.axis } },
            axisLabel: { color: c.sub, fontSize: 10 },
            pointer: { itemStyle: { color: PALETTE[2] } },
            title: { color: c.sub, offsetCenter: [0, '80%'] },
            detail: { formatter: '{value}%', color: c.text, fontSize: 26, offsetCenter: [0, '52%'] },
            data: [{ value: cov.coverage_pct, name: `覆盖 ${cov.covered_flights}/${cov.total_flights}，未覆盖 ${cov.uncovered_flights}` }],
          }],
        }
      },
    },
    {
      id: 'cv-violations',
      title: '违规类型分布',
      note: '统计 crew[] 每人 violations 文本归类后的条数与涉及人数（CCAR-121 检查产出）',
      build: (theme) => {
        const crew = vm.crew || []
        if (!crew.length) return noSchedule()
        const typeOf = s => {
          if (s.indexOf('日飞行') >= 0) return `日飞行超${LIMIT_DAILY}h`
          if (s.indexOf('7天飞行') >= 0) return `7日飞行超${LIMIT_7DAY}h`
          if (s.indexOf('30天飞行') >= 0) return `30日飞行超${LIMIT_30DAY}h`
          if (s.indexOf('休息') >= 0) return '休息间隔不足'
          return '其他违规'
        }
        const counts = {}
        const persons = {}
        crew.forEach(c => {
          (c.violations || []).forEach(v => {
            const t = typeOf(String(v))
            counts[t] = (counts[t] || 0) + 1
            if (!persons[t]) persons[t] = new Set()
            persons[t].add(c.name || c.crew_id)
          })
        })
        const types = Object.keys(counts)
        if (!types.length) return noData('当前排班没有任何违规记录 —— 全员合规。切换基地/日期制造高压排班后可再次查看')
        const c = themeColors(theme)
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          legend: { top: 6 },
          grid,
          xAxis: { type: 'category', data: types, axisLabel: { interval: 0, rotate: 20, fontSize: 11 } },
          yAxis: { type: 'value', minInterval: 1 },
          series: [
            {
              name: '违规条数', type: 'bar', data: types.map(t => counts[t]),
              itemStyle: { color: PALETTE[3] },
              label: { show: true, position: 'top', color: c.text },
            },
            { name: '涉及人数', type: 'bar', data: types.map(t => persons[t].size), itemStyle: { color: PALETTE[4] } },
          ],
        }
      },
    },
  ]
}

export default buildCrewCharts
