/**
 * 透明浮层图表基座：统一主题、配色、空态、CSV 导出。
 * 各屏的图表定义放在 src/utils/charts/<screen>.js，只依赖本文件的导出。
 */
import * as echarts from 'echarts'

export { echarts }

export const PALETTE = [
  '#4f9cf9', '#67c23a', '#e6a23c', '#f56c6c', '#b37feb',
  '#36cfc9', '#ff9c6e', '#5cdbd3', '#f759ab', '#85a9f0',
]

export function themeColors(theme) {
  const dark = theme !== 'light'
  return {
    dark,
    text: dark ? '#e6ebf5' : '#303133',
    sub: dark ? '#a8b2c9' : '#909399',
    axis: dark ? 'rgba(230,235,245,0.45)' : 'rgba(48,49,51,0.35)',
    split: dark ? 'rgba(230,235,245,0.14)' : 'rgba(48,49,51,0.10)',
    tooltipBg: dark ? 'rgba(16,18,34,0.88)' : 'rgba(255,255,255,0.94)',
    pillBg: dark ? 'rgba(30,32,58,0.55)' : 'rgba(255,255,255,0.65)',
    pillBorder: dark ? 'rgba(140,160,210,0.45)' : 'rgba(48,49,51,0.25)',
  }
}

function applyAxis(axis, c) {
  if (!axis) return
  const list = Array.isArray(axis) ? axis : [axis]
  list.forEach(a => {
    if (!a) return
    a.axisLine = Object.assign({ lineStyle: { color: c.axis } }, a.axisLine || {})
    a.axisTick = Object.assign({ lineStyle: { color: c.axis } }, a.axisTick || {})
    a.axisLabel = Object.assign({ color: c.sub }, a.axisLabel || {})
    if (a.splitLine !== undefined && a.splitLine !== null) {
      a.splitLine = Object.assign({ lineStyle: { color: c.split } }, a.splitLine || {})
    }
    if (a.name !== undefined) a.nameTextStyle = Object.assign({ color: c.sub }, a.nameTextStyle || {})
    if (a.type === 'category' && !a.data && !a.name) a.data = []
  })
}

/** 把主题色合进 option（图表本身背景保持透明） */
export function withTheme(option, theme) {
  const c = themeColors(theme)
  const o = option || {}
  o.color = o.color || PALETTE
  o.backgroundColor = 'transparent'
  // 默认关掉入场动画：动画靠 requestAnimationFrame 推进，标签页被节流/隐藏时
  // 只会停在首帧，导出的图片就是残缺的。需要动画的图表自己显式打开。
  if (o.animation === undefined) o.animation = false
  o.textStyle = Object.assign({ color: c.text }, o.textStyle || {})
  if (o.title) o.title.textStyle = Object.assign({ color: c.text }, o.title.textStyle || {})
  if (o.tooltip) {
    o.tooltip = Object.assign(
      { backgroundColor: c.tooltipBg, borderColor: c.axis, textStyle: { color: c.text } },
      o.tooltip
    )
  }
  const legends = Array.isArray(o.legend) ? o.legend : (o.legend ? [o.legend] : [])
  legends.forEach(l => { l.textStyle = Object.assign({ color: c.text }, l.textStyle || {}) })
  applyAxis(o.xAxis, c)
  applyAxis(o.yAxis, c)
  if (o.radar) {
    const rs = Array.isArray(o.radar) ? o.radar : [o.radar]
    rs.forEach(r => {
      r.axisName = Object.assign({ color: c.text }, r.axisName || {})
      r.axisLine = Object.assign({ lineStyle: { color: c.axis } }, r.axisLine || {})
      r.splitLine = Object.assign({ lineStyle: { color: c.split } }, r.splitLine || {})
    })
  }
  if (o.visualMap) {
    const vs = Array.isArray(o.visualMap) ? o.visualMap : [o.visualMap]
    vs.forEach(v => { v.textStyle = Object.assign({ color: c.sub }, v.textStyle || {}) })
  }
  return o
}

/** 空态：图表构建函数返回它，浮层显示提示而不是画一张空图 */
export function noData(msg) {
  return { __empty: msg || '当前没有可用数据' }
}

export function isEmptyOption(opt) {
  return !opt || opt.__empty
}

const fmtCell = v => (v === null || v === undefined ? '' : String(v))

function flattenSeriesData(data) {
  return (data || []).map(item => {
    if (item === null || item === undefined) return ''
    if (Array.isArray(item)) return item.map(fmtCell).join(' ')
    if (typeof item === 'object') {
      if (item.value !== undefined) {
        return Array.isArray(item.value) ? item.value.map(fmtCell).join(' ') : fmtCell(item.value)
      }
      return fmtCell(item.name)
    }
    return fmtCell(item)
  })
}

/** 从 option 自动推导 CSV，图表定义不需要各写一份导出逻辑 */
export function optionToCsv(option) {
  const o = option || {}

  // custom 系列（立体柱等自绘图表）无法从 series.data 反推行列标签，
  // 允许图表自己带一份 __csv = { header: [...], rows: [[...], ...] } 作为权威导出
  if (o.__csv && Array.isArray(o.__csv.rows)) {
    const esc = v => {
      const s = v === null || v === undefined ? '' : String(v)
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
    }
    const head = (o.__csv.header || []).map(esc).join(',')
    const body = o.__csv.rows.map(r => r.map(esc).join(','))
    return [head].concat(body).join('\n')
  }

  const lines = []
  const push = arr => lines.push(arr.map(v => {
    const s = fmtCell(v)
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }).join(','))

  const series = (o.series || []).filter(s => s && s.data !== undefined)

  // 饼图 / 漏斗：name-value 两列
  const isPie = series.some(s => s.type === 'pie' || s.type === 'funnel')
  if (isPie) {
    push(['名称', '数值'])
    series.forEach(s => {
      (s.data || []).forEach(d => push([d && d.name, d && d.value]))
    })
    return lines.join('\n')
  }

  // 热力图：三元组 [x, y, value]
  const heat = series.find(s => s.type === 'heatmap')
  if (heat) {
    const xs = (Array.isArray(o.xAxis) ? o.xAxis[0] : o.xAxis || {}).data || []
    const ys = (Array.isArray(o.yAxis) ? o.yAxis[0] : o.yAxis || {}).data || []
    push(['X', 'Y', '数值'])
    ;(heat.data || []).forEach(d => {
      const v = Array.isArray(d) ? d : (d && d.value) || []
      push([xs[v[0]] !== undefined ? xs[v[0]] : v[0], ys[v[1]] !== undefined ? ys[v[1]] : v[1], v[2]])
    })
    return lines.join('\n')
  }

  // 直角坐标系：类目 + 各系列
  const xa = Array.isArray(o.xAxis) ? o.xAxis[0] : o.xAxis
  const categories = (xa && xa.data) || null
  if (categories && categories.length) {
    push(['类目'].concat(series.map((s, i) => s.name || `系列${i + 1}`)))
    categories.forEach((cat, idx) => {
      push([cat].concat(series.map(s => flattenSeriesData(s.data)[idx] !== undefined ? flattenSeriesData(s.data)[idx] : '')))
    })
    return lines.join('\n')
  }

  // 兜底：逐系列平铺
  push(['系列', '索引', '数值'])
  series.forEach(s => {
    const vals = flattenSeriesData(s.data)
    vals.forEach((v, idx) => push([s.name || '系列', idx + 1, v]))
  })
  return lines.join('\n')
}

export function downloadText(filename, text, mime) {
  const blob = new Blob(['' + text], { type: (mime || 'text/plain') + ';charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

export function safeSum(arr) {
  return (arr || []).reduce((s, v) => s + (Number(v) || 0), 0)
}

/**
 * 趋势图历史缓冲。仿真 KPI 都是瞬时值，要画曲线必须自己攒点。
 * 按 ts 幂等写入：同一次采样被重复 build 不会把点越堆越多。
 */
const _seriesBuffers = {}

export function addSample(key, ts, values, maxPoints) {
  if (ts === undefined || ts === null || ts === '') return getSamples(key)
  if (!_seriesBuffers[key]) _seriesBuffers[key] = { order: [], map: {}, max: maxPoints || 600 }
  const b = _seriesBuffers[key]
  if (!Object.prototype.hasOwnProperty.call(b.map, ts)) b.order.push(ts)
  b.map[ts] = values
  while (b.order.length > b.max) {
    const drop = b.order.shift()
    delete b.map[drop]
  }
  return getSamples(key)
}

/** 返回 [[ts, values], ...]，按采样先后排列 */
export function getSamples(key) {
  const b = _seriesBuffers[key]
  if (!b) return []
  return b.order.map(t => [t, b.map[t]])
}

export function resetSamples(key) {
  delete _seriesBuffers[key]
}
