/**
 * 异常调度页（RecoveryView）的图表集合。
 * 数据在 Vuex store（demo/src/store/index.js）：
 *   state.selectedAnomaly / impactReport / recoveryPlan / backupResources / auditLogs。
 * build 闭包捕获 vm，每次渲染都读 vm.$store.state 的最新值。
 */
import { noData, PALETTE, themeColors } from '../chartBase'

const grid = { left: 76, right: 24, top: 46, bottom: 70, containLabel: true }

function noImpact() {
  return noData('尚未生成影响报告：请先在左侧选择异常事件，并点击「影响分析」')
}
function noPlan() {
  return noData('尚未生成恢复方案：请先选择异常事件并点击「影响分析」（分析完成后方案自动生成）')
}

// direct_impacted_flights / flights_to_cancel 项可能是字符串或 {flight_id, flight_no}
function fidOf(item) {
  if (item === null || item === undefined) return ''
  return String(typeof item === 'object' ? item.flight_id : item)
}

export function buildRecoveryCharts(vm) {
  return [
    {
      id: 'rv-sankey',
      title: '影响传播桑基图',
      note: '事件 → 直接影响 → 级联层(L1/L2…) → 拟取消；取消量按 flight_id 真实归属到直接影响或对应级联层，不做猜测分摊',
      build: (theme) => {
        const st = vm.$store.state
        const impact = st.impactReport
        if (!impact) return noImpact()
        const evName = ((st.selectedAnomaly || {}).title || '异常事件').slice(0, 14)
        const direct = impact.direct_impacted_flights || []
        const cascades = (impact.cascade_chains || []).map(c => ({ level: c.level || 1, fid: fidOf(c) }))
        const cancels = (impact.flights_to_cancel || []).map(fidOf)
        const directIds = new Set(direct.map(fidOf))

        const levels = {}
        cascades.forEach(c => { levels[c.level] = (levels[c.level] || 0) + 1 })
        const levelKeys = Object.keys(levels).map(Number).sort((a, b) => a - b)

        // 取消航班归属：direct / level k / 未匹配（阈值提升新增）
        const cancelDirect = cancels.filter(id => directIds.has(id)).length
        const cancelByLevel = {}
        const cancelCascadeIds = cancels.filter(id => !directIds.has(id))
        cancelCascadeIds.forEach(id => {
          const hit = cascades.find(c => c.fid === id)
          if (hit) cancelByLevel[hit.level] = (cancelByLevel[hit.level] || 0) + 1
        })
        const cancelUnmatched = cancelCascadeIds.length -
          Object.keys(cancelByLevel).reduce((s, k) => s + cancelByLevel[k], 0)

        const totalFlow = direct.length + cascades.length
        if (!totalFlow) return noData('影响报告里直接/级联受影响航班都是 0，没有可传播的影响')

        const c = themeColors(theme)
        const directNode = `直接影响 ${direct.length}`
        const nodes = [{ name: evName }]
        if (direct.length > 0) nodes.push({ name: directNode })
        levelKeys.forEach(lv => nodes.push({ name: `L${lv} 级联 ${levels[lv]}` }))
        const cancelTotal = cancels.length
        if (cancelTotal > 0) nodes.push({ name: `拟取消 ${cancelTotal}` })

        const links = []
        if (direct.length > 0) links.push({ source: evName, target: directNode, value: direct.length })
        levelKeys.forEach(lv => {
          if (direct.length > 0) links.push({ source: directNode, target: `L${lv} 级联 ${levels[lv]}`, value: levels[lv] })
          else links.push({ source: evName, target: `L${lv} 级联 ${levels[lv]}`, value: levels[lv] })
        })
        if (cancelTotal > 0) {
          if (cancelDirect > 0) links.push({ source: directNode, target: `拟取消 ${cancelTotal}`, value: cancelDirect })
          levelKeys.forEach(lv => {
            const cv = cancelByLevel[lv] || 0
            if (cv > 0) links.push({ source: `L${lv} 级联 ${levels[lv]}`, target: `拟取消 ${cancelTotal}`, value: cv })
          })
          if (cancelUnmatched > 0) {
            nodes.push({ name: `延迟提升取消 ${cancelUnmatched}` })
            links.push({ source: evName, target: `延迟提升取消 ${cancelUnmatched}`, value: cancelUnmatched })
            links.push({ source: `延迟提升取消 ${cancelUnmatched}`, target: `拟取消 ${cancelTotal}`, value: cancelUnmatched })
          }
        }
        if (!links.length) return noData('影响报告里没有任何可连线的航班流')

        return {
          tooltip: { trigger: 'item', triggerOn: 'mousemove' },
          series: [{
            type: 'sankey', left: 24, right: 130, top: 24, bottom: 24,
            nodeGap: 14, nodeWidth: 14,
            emphasis: { focus: 'adjacency' },
            data: nodes, links,
            label: { color: c.text, fontSize: 11 },
            lineStyle: { color: 'gradient', opacity: 0.32 },
          }],
        }
      },
    },
    {
      id: 'rv-cascade-bars',
      title: '级联层延迟与航班数',
      note: 'cascade_chains 按 level 聚合：左轴该层累计延迟分钟，右轴该层航班数',
      build: () => {
        const impact = vm.$store.state.impactReport
        if (!impact) return noImpact()
        const cascades = (impact.cascade_chains || []).map(x => ({ level: x.level || 1, delay: Number(x.delay_minutes) || 0 }))
        if (!cascades.length) return noData('本次影响没有级联航班（cascade_chains 为空），仅存在直接影响')
        const byLevel = {}
        cascades.forEach(c => {
          if (!byLevel[c.level]) byLevel[c.level] = { delay: 0, count: 0 }
          byLevel[c.level].delay += c.delay
          byLevel[c.level].count += 1
        })
        const lvKeys = Object.keys(byLevel).map(Number).sort((a, b) => a - b)
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 6 },
          grid,
          xAxis: { type: 'category', data: lvKeys.map(l => `L${l}`) },
          yAxis: [
            { type: 'value', name: '延迟(分钟)' },
            { type: 'value', name: '航班数', minInterval: 1, splitLine: { show: false } },
          ],
          series: [
            { name: '累计延迟(分钟)', type: 'bar', barMaxWidth: 42, data: lvKeys.map(l => byLevel[l].delay), itemStyle: { color: PALETTE[2] } },
            { name: '航班数', type: 'bar', yAxisIndex: 1, barMaxWidth: 42, data: lvKeys.map(l => byLevel[l].count), itemStyle: { color: PALETTE[0] } },
          ],
        }
      },
    },
    {
      id: 'rv-change-pie',
      title: '恢复方案变更类型构成',
      note: 'recovery_plan 五类变更条目数量：飞机/机组/登机口/跑道/时刻',
      build: (theme) => {
        const plan = vm.$store.state.recoveryPlan
        if (!plan) return noPlan()
        const defs = [
          ['飞机变更', 'aircraft_changes'],
          ['机组变更', 'crew_changes'],
          ['登机口变更', 'gate_changes'],
          ['跑道变更', 'runway_changes'],
          ['时刻变更', 'flight_changes'],
        ]
        const data = defs
          .map(([n, k]) => ({ name: n, value: (plan[k] || []).length }))
          .filter(d => d.value > 0)
        if (!data.length) return noData('恢复方案中五类变更条目均为空，没有可统计的方案变更')
        const c = themeColors(theme)
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} 项 ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie', radius: ['36%', '62%'], center: ['50%', '58%'], data,
            label: { color: c.text, formatter: '{b}\n{c} 项' },
            labelLine: { lineStyle: { color: c.axis } },
          }],
        }
      },
    },
    {
      id: 'rv-backup-bars',
      title: '备份资源四类计数',
      note: 'backupResources 池中备份飞机/机组/登机口/跑道的可用条数',
      build: () => {
        const r = vm.$store.state.backupResources
        if (!r) return noData('备份资源池尚未加载：点击事件卡上的「备份资源」按钮打开管理窗口')
        const defs = [
          ['备份飞机', 'backup_aircraft'],
          ['备份机组', 'backup_crew'],
          ['备份登机口', 'backup_gates'],
          ['备份跑道', 'backup_runways'],
        ]
        const names = defs.map(d => d[0])
        const counts = defs.map(d => (r[d[1]] || []).length)
        if (counts.every(v => v === 0)) return noData('备份资源池为空：可在「备份资源」弹窗中点「自动生成备份资源」')
        return {
          tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
          grid: { left: 100, right: 40, top: 20, bottom: 46, containLabel: true },
          yAxis: { type: 'category', data: names.slice().reverse(), axisLabel: { interval: 0 } },
          xAxis: { type: 'value', name: '条', minInterval: 1 },
          series: [{
            type: 'bar', data: counts.slice().reverse(), barMaxWidth: 26,
            itemStyle: { color: PALETTE[5] },
            label: { show: true, position: 'right' },
          }],
        }
      },
    },
    {
      id: 'rv-coverage-gauge',
      title: '方案覆盖率',
      note: 'recovery_plan.coverage_rate（后端为受影响航班生成方案的覆盖比例，0~1 换算成百分比）',
      build: (theme) => {
        const plan = vm.$store.state.recoveryPlan
        if (!plan || typeof plan.coverage_rate !== 'number') return noPlan()
        const c = themeColors(theme)
        return {
          series: [{
            type: 'gauge', min: 0, max: 100, splitNumber: 5, radius: '78%', center: ['50%', '58%'],
            progress: { show: true, width: 14, itemStyle: { color: PALETTE[1] } },
            axisLine: { lineStyle: { width: 14, color: [[1, c.split]] } },
            axisTick: { lineStyle: { color: c.axis } },
            splitLine: { lineStyle: { color: c.axis } },
            axisLabel: { color: c.sub, fontSize: 10 },
            pointer: { itemStyle: { color: PALETTE[2] } },
            title: { color: c.sub, offsetCenter: [0, '82%'] },
            detail: { formatter: '{value}%', color: c.text, fontSize: 26, offsetCenter: [0, '54%'] },
            data: [{ value: Math.round(plan.coverage_rate * 1000) / 10, name: '方案覆盖率' }],
          }],
        }
      },
    },
    {
      id: 'rv-audit-scatter',
      title: '调度日志时序散点',
      note: 'auditLogs 按 timestamp 排序铺开：横轴日志时间，纵轴动作类型；悬浮看 detail',
      build: () => {
        const logs = (vm.$store.state.auditLogs || []).filter(l => l && l.timestamp)
        if (!logs.length) return noData('暂无调度日志：在左侧选中异常事件后系统会自动拉取审计日志')
        const sorted = logs.slice().sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)))
        const xs = sorted.map(l => String(l.timestamp))
        const actions = []
        sorted.forEach(l => {
          const a = String(l.action || '未知')
          if (actions.indexOf(a) < 0) actions.push(a)
        })
        const data = sorted.map((l, i) => [i, actions.indexOf(String(l.action || '未知')), l.detail || '', l.timestamp])
        return {
          tooltip: {
            formatter: p => `${p.data[3]}<br/>${actions[p.data[1]]}<br/>${p.data[2] || '（无 detail）'}`,
          },
          grid: { left: 90, right: 24, top: 24, bottom: 92, containLabel: false },
          xAxis: { type: 'category', data: xs, axisLabel: { rotate: 45, fontSize: 9, interval: 'auto' } },
          yAxis: { type: 'category', data: actions, axisLabel: { fontSize: 11, interval: 0 } },
          series: [{
            name: '调度日志', type: 'scatter', symbolSize: 11,
            itemStyle: { color: PALETTE[0], opacity: 0.85 },
            data,
          }],
        }
      },
    },
  ]
}

export default buildRecoveryCharts
