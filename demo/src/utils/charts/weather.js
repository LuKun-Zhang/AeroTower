/**
 * 模拟大引擎 → 天气 / 天气气象图（WeatherMap3D）的图表集合。
 * vm 是 WeatherMap3D 打开浮层时打包的只读视图：
 *   mode、weatherGroups[]（图例分组 {type,label,count,provinces}）、
 *   cycloneStates[]（{id,intensity,terrainWear,efPeak,...}）、
 *   predictProvinceTimeline(min)（气旋确定性推演，返回 {timeline:{省:[{t,time,type}]}}）、
 *   getBusinessClock()（统一业务时刻 {current_time,...}）、
 *   streamSummary（/api/weather/stream 响应，由外层 WeatherView 传入，可能为 null）。
 * 风级 windForce 与页面气象小图同一推导口径：round(intensity*8)+2 级，不是新增数据源。
 * 趋势图用 addSample 按业务时刻字符串幂等攒历史。
 */
import { noData, PALETTE, addSample, getSamples } from '../chartBase'
import { isoBarOption } from './isoBars'

/** 天气类型 → 立体柱等级数（0~5）；映射含义写进图表 note，防止误读 */
const WX_TYPE_NUM = {
  sunny: 0, cloudy: 1, rain_light: 2, rain_moderate: 3, rain_heavy: 4, thunderstorm: 5,
}
/** 天气类型 → 原始中文名（悬浮 tip 直接给人话，不让人猜数字） */
const WX_TYPE_LABEL = {
  sunny: '晴', cloudy: '多云', rain_light: '小雨', rain_moderate: '中雨', rain_heavy: '大雨', thunderstorm: '雷暴',
}

const grid = { left: 76, right: 30, top: 52, bottom: 60, containLabel: true }

function windForceOf(intensity) {
  return Math.round(intensity * 8) + 2
}

export function buildWeatherCharts(vm) {
  return [
    {
      id: 'wx-forecast24',
      title: '未来 24 小时 省份×时刻 天气立体柱',
      note: '等距 3D 立体柱矩阵：横轴=时刻、纵轴=省份，柱高=天气等级（0=晴 1=多云 2=小雨 3=中雨 4=大雨 5=雷暴，与页面 HTML 色块表同一份数据）。晴=等级 0，渲染器不画柱、但格子底座仍在，说明该省该时段无不利天气；具体天气中文名看悬浮 tip。省份全量 34 个会把菱形压糊，按「24 小时峰值等级↓、累计等级和↓」排序只展示 Top 17 省份。数据来自组件 predictProvinceTimeline(1440)，30 分钟一档',
      build: (theme) => {
        if (!vm || typeof vm.predictProvinceTimeline !== 'function') {
          return noData('天气推演组件未就绪')
        }
        const predicted = vm.predictProvinceTimeline(1440)
        const tl = (predicted && predicted.timeline) || {}
        const provinces = Object.keys(tl).filter(p => (tl[p] || []).length > 0)
        if (!provinces.length) return noData('省份气象锚点还没加载完成（地形/边界数据未就绪），稍后重新打开图表')
        const levelOf = type => (WX_TYPE_NUM[type] !== undefined ? WX_TYPE_NUM[type] : 0)
        // 省份筛减规则：先看最恶劣的一刻（峰值等级），再看全天累计，取 Top 17
        const scored = provinces.map(p => {
          const levels = tl[p].map(e => levelOf(e.type))
          return {
            name: p,
            peak: levels.reduce((m, n) => Math.max(m, n), 0),
            sum: levels.reduce((a, n) => a + n, 0),
          }
        }).sort((a, b) => (b.peak - a.peak) || (b.sum - a.sum))
        const picked = scored.slice(0, 17).map(s => s.name)
        const times = tl[picked[0]].map(e => e.time)
        const cells = []
        picked.forEach((p, yi) => {
          tl[p].forEach((e, xi) => {
            const lv = levelOf(e.type)
            cells.push({
              xi, yi, v: lv,
              tip: `${p} · ${e.time}<br/>天气：${WX_TYPE_LABEL[e.type] || e.type}（等级 ${lv}）`,
            })
          })
        })
        return isoBarOption({
          theme,
          xLabels: times,
          yLabels: picked,
          cells,
          valueName: '天气等级',
          sceneTitle: '天气等级 0晴 → 5雷暴（晴不画柱）',
          maxBars: 900,
          maxTicks: 12,
          ramp: ['#9ec4f0', '#4f9cf9', '#36cfc9', '#e6a23c', '#f56c6c'],
          emptyText: '未来 24 小时 Top 省份全程晴（等级 0，无柱可画）',
        })
      },
    },
    {
      id: 'wx-typepie',
      title: '天气类型构成饼图',
      note: '直接画右上角图例的 count：动态/自定义模式下 count 是该类型的云层网格面积占比 %（非省份数），手动/自动模式下是省份个数；两种口径都以数值大小画扇区',
      build: () => {
        const groups = (vm.weatherGroups || [])
          .map(g => ({ name: g.label, value: parseFloat(g.count) || 0 }))
          .filter(d => d.value > 0)
        if (!groups.length) return noData('图例里还没有天气分组统计（省份天气数据未就绪）')
        return {
          tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
          legend: { top: 6 },
          series: [{
            type: 'pie', radius: ['36%', '62%'], center: ['50%', '58%'],
            data: groups,
            label: { formatter: '{b}\n{c} ({d}%)' },
          }],
        }
      },
    },
    {
      id: 'wx-cycintensity',
      title: '气旋强度时序',
      note: '每个活跃气旋按 id 一条强度实线（intensity×100%）+ 一条地形磨损虚线；同点还采了 efPeak 有效峰值与风级 windForce=round(强度×8)+2 级（与页面气象小图同口径），见 CSV 与浮层数据',
      build: () => {
        if (!vm || typeof vm.getBusinessClock !== 'function') return noData('天气推演组件未就绪')
        const clock = vm.getBusinessClock()
        const ts = clock && clock.current_time
        const states = vm.cycloneStates || []
        states.forEach(cs => {
          addSample('cyc-intensity-' + cs.id, ts, {
            intensity: Math.round(cs.intensity * 1000) / 10,
            terrainWear: Math.round((cs.terrainWear || 0) * 1000) / 10,
            efPeak: Math.round((cs.efPeak || 0) * 1000) / 10,
            windForce: windForceOf(cs.intensity),
          }, 720)
        })
        // 汇总所有气旋 id 的历史
        const perId = {}
        for (let id = 1; id <= 5; id++) {
          const s = getSamples('cyc-intensity-' + id)
          if (s.length) perId[id] = s
        }
        const ids = Object.keys(perId)
        if (!ids.length) {
          return noData('当前没有活跃气旋、也没有历史采样——请确认处于「动态演示/自定义气旋」模式并让仿真运行一段时间（浮层里点「实时」可持续采样）')
        }
        const totalPoints = ids.reduce((n, id) => n + perId[id].length, 0)
        if (totalPoints < 2) return noData('需要先启动仿真并让它运行一段时间（气旋采样还不足 2 个点）')
        const timeSet = {}
        ids.forEach(id => perId[id].forEach(s => { timeSet[s[0]] = true }))
        const times = Object.keys(timeSet).sort()
        const series = []
        ids.forEach((id, i) => {
          const map = {}
          perId[id].forEach(s => { map[s[0]] = s[1] })
          const color = PALETTE[i % PALETTE.length]
          series.push({
            name: `气旋#${id} 强度%`, type: 'line', symbol: 'circle', symbolSize: 4,
            lineStyle: { color }, itemStyle: { color },
            data: times.map(t => (map[t] ? map[t].intensity : null)),
          })
          series.push({
            name: `气旋#${id} 地形磨损%`, type: 'line', symbol: 'none',
            lineStyle: { color, type: 'dashed' }, itemStyle: { color },
            data: times.map(t => (map[t] ? map[t].terrainWear : null)),
          })
        })
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 4, type: 'scroll' },
          grid,
          xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 9 } },
          yAxis: { type: 'value', name: '百分比 %', min: 0 },
          series,
        }
      },
    },
    {
      id: 'wx-disruption',
      title: '天气中断联动计数堆叠面积',
      note: '数据来自 /api/weather/stream 的自动回传响应（直达/途经受影响航班数、被延误数、被取消数），按响应里的业务时刻 current_time 攒历史；每 2 秒回传一次',
      build: () => {
        const s = vm && vm.streamSummary
        if (!s) {
          return noData('本页没有接入 /api/weather/stream 的回传响应——该数据目前只在独立「天气气象图」页面自动回传并保存（每 2 秒一次）')
        }
        if (s.error) return noData('最近一次回传失败：' + s.error + '（请确认后端服务已启动）')
        const ts = s.clock && s.clock.current_time
        if (!ts) return noData('回传响应里没有 clock.current_time 业务时刻，无法采样')
        if (s.direct_count === undefined && s.transit_count === undefined
          && s.delay_count === undefined && s.cancel_count === undefined) {
          return noData('回传响应里还没有 direct/transit/delay/cancel 计数字段（后端尚未返回该结构）')
        }
        addSample('wx-disruption', ts, {
          direct_count: s.direct_count || 0,
          transit_count: s.transit_count || 0,
          delay_count: s.delay_count || 0,
          cancel_count: s.cancel_count || 0,
        }, 1000)
        const samples = getSamples('wx-disruption')
        if (samples.length < 2) return noData('需要先让自动回传运行一段时间（当前已攒 ' + samples.length + ' 个点，趋势图至少需要 2 个；浮层里点「实时」可持续采样）')
        const times = samples.map(x => x[0])
        const pick = k => samples.map(x => (x[1][k] !== undefined ? x[1][k] : null))
        const area = (name, key, color) => ({
          name, type: 'line', stack: 'wx', symbol: 'none',
          areaStyle: { opacity: 0.55, color }, lineStyle: { color, width: 1 },
          data: pick(key),
        })
        return {
          tooltip: { trigger: 'axis' },
          legend: { top: 4 },
          grid,
          xAxis: { type: 'category', data: times, axisLabel: { rotate: 30, fontSize: 9 } },
          yAxis: { type: 'value', name: '航班数' },
          series: [
            area('直达受影响', 'direct_count', PALETTE[0]),
            area('途经受影响', 'transit_count', PALETTE[5]),
            area('被延误', 'delay_count', PALETTE[2]),
            area('被取消', 'cancel_count', PALETTE[3]),
          ],
        }
      },
    },
  ]
}

export default buildWeatherCharts
