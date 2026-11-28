/**
 * 等距 3D 立体柱（轴测投影）绘制器，用纯 2D canvas 实现。
 * 不用 echarts-gl 的原因：gl 层是独立 WebGL canvas，getDataURL 导出会拿不到像素（易全黑），
 * 会破坏浮层「所有图表都能导出 PNG」的要求；这里保持单张 2D 画布，导出/透明底/明暗主题都照旧可用。
 *
 * 用法：isoBarOption({ xLabels, yLabels, cells, valueName, theme })
 */
import { themeColors, noData } from '../chartBase'

// 轴测比例：默认横向 2 : 纵向 1（经典 2:1 等距）；网格越大越扁，见 layout()
const TILE_RATIO = 0.5

function clamp01(x) {
  return x < 0 ? 0 : (x > 1 ? 1 : x)
}

function parseHex(hex) {
  const h = String(hex).replace('#', '')
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h
  return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)]
}

// factor > 0 提亮，< 0 压暗
function shade(hex, factor) {
  let rgb
  try { rgb = parseHex(hex) } catch (e) { return hex }
  const out = rgb.map(v => {
    const n = factor >= 0 ? v + (255 - v) * factor : v * (1 + factor)
    return Math.max(0, Math.min(255, Math.round(n)))
  })
  return 'rgb(' + out.join(',') + ')'
}

function niceStep(v) {
  if (v <= 0) return 1
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  return (n >= 5 ? 5 : n >= 2 ? 2 : 1) * p
}

/** 主入口：返回 echarts option（无坐标轴，整个场景由 custom series 自绘） */
export function isoBarOption(cfg) {
  const xLabels = cfg.xLabels || []
  const yLabels = cfg.yLabels || []
  let cells = (cfg.cells || []).filter(c => c && Number.isFinite(c.v) && c.v > 0)
  if (!cells.length) return noData(cfg.emptyText || '当前没有可用数据')

  const cap = cfg.maxBars || 900
  if (cells.length > cap) {
    cells = cells.slice().sort((a, b) => b.v - a.v).slice(0, cap)
  }

  const maxV = cells.reduce((m, c) => Math.max(m, c.v), 0) || 1
  // 遮挡顺序：离镜头远的先画
  const ordered = cells.slice().sort((a, b) => (a.xi + a.yi) - (b.xi + b.yi))
  cfg.occupiedCells = cells.map(c => [c.xi, c.yi])
  const data = ordered.map(c => ({
    value: [c.xi, c.yi, c.v],
    tip: c.tip || null,
  }))

  const stripHtml = s => String(s || '').replace(/<br\s*\/?>/gi, ' ').replace(/<[^>]+>/g, '')
  const csvRows = data.map(c => [
    xLabels[c.value[0]],
    yLabels[c.value[1]],
    c.value[2],
    c.tip ? stripHtml(c.tip) : '',
  ])

  return {
    __csv: {
      header: ['列（X）', '行（Y）', cfg.valueName || '数值', '明细'],
      rows: csvRows,
    },
    tooltip: {
      trigger: 'item',
      formatter: p => {
        const d = p.data || {}
        if (d.tip) return d.tip
        const v = (d.value || [])[2]
        return `${xLabels[(d.value || [])[0]] || ''} × ${yLabels[(d.value || [])[1]] || ''}<br/>${cfg.valueName || '数值'}：${v}`
      },
    },
    visualMap: {
      show: true,
      dimension: 2,
      min: 0,
      max: maxV,
      calculable: true,
      realtime: false,
      precision: 0,
      left: 12,
      bottom: 18,
      itemWidth: 11,
      itemHeight: 110,
      text: [cfg.valueName || '高', '低'],
      inRange: { color: cfg.ramp || ['#2b6cb0', '#3f9fd8', '#57d6a3', '#f2c14e', '#f2737a'] },
    },
    animation: false,
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: 'value', show: false, min: 0, max: Math.max(1, xLabels.length - 1) },
    yAxis: { type: 'value', show: false, min: 0, max: Math.max(1, yLabels.length - 1) },
    series: [
      {
        name: 'floor',
        type: 'custom',
        z: 1,
        silent: true,
        dimensions: ['x', 'y', 'v'],
        markupPoint: [0, 0],
        data: [[0, 0, 0]],
        renderItem: (params, api) => buildFloor(api, xLabels, yLabels, cfg),
      },
      {
        name: cfg.valueName || '数值',
        type: 'custom',
        z: 5,
        dimensions: ['x', 'y', 'v'],
        encode: { x: [0, 1], y: 2 },
        data,
        renderItem: (params, api) => buildBar(api, params, xLabels, yLabels, maxV, cfg),
      },
    ],
  }
}

/** 布局参数：把整个菱形底面按解析几何精确适配并居中 */
function layout(api, nx, ny, cfg) {
  const W = api.getWidth()
  const H = api.getHeight()
  const padL = cfg.padLeft || 66
  const padR = 22
  const padT = 22
  const padB = cfg.padBottom || 46
  const availW = Math.max(140, W - padL - padR)
  const availH = Math.max(140, H - padT - padB)

  const span = Math.max(1, nx + ny)
  // 网格越大菱形要越扁，否则纵向高度会吃掉整个画布、格子被压成细签
  const ratio = cfg.ratio || (span > 46 ? 0.30 : span > 26 ? 0.40 : TILE_RATIO)

  // 菱形水平宽 = (nx + ny) * tileW / 2；纵向高 = (nx + ny + 1) * tileW * ratio / 2
  let tileW = (availW * 0.92) * 2 / span
  const diamondH0 = (span + 1) * tileW * ratio / 2
  // 给柱子留出至少 40% 的可用高度，其余给菱形地面
  const roomForBars = Math.max(availH * 0.4, 40)
  if (diamondH0 > availH - roomForBars) {
    tileW = (availH - roomForBars) * 2 / ((span + 1) * ratio)
  }
  tileW = Math.max(7, Math.min(tileW, 54))
  const tileH = tileW * ratio
  const maxBarH = Math.max(28, Math.min(availH * 0.56, tileW * 3.4))

  // 关键：菱形几何中心在 originX + (nx - ny) * tileW / 4，必须反解 originX 才能真正左右居中
  const originX = padL + availW / 2 - (nx - ny) * (tileW / 4)
  // 纵向：内容范围 = [originY - maxBarH, originY + diamondH + labelBand]，让这段整体居中
  // labelBand 是菱形下沿那圈旋转刻度文字占的高度，漏掉它会让整幅图偏高、底部空一大块
  const diamondH = (span + 1) * tileH / 2
  const labelBand = tileH * 0.75 + 16
  const originY = padT + availH / 2 - (diamondH + labelBand - maxBarH) / 2

  return { tileW, tileH, maxBarH, originX, originY, W, H, padL, padR, padT, padB, availW, availH, ratio }
}

/** 格子 (i, j) 在地面上的中心点 */
function basePoint(L, i, j) {
  return [
    L.originX + (i - j) * (L.tileW / 2),
    L.originY + (i + j) * (L.tileH / 2),
  ]
}

function buildFloor(api, xLabels, yLabels, cfg) {
  const nx = xLabels.length
  const ny = yLabels.length
  const L = layout(api, nx, ny, cfg)
  const c = themeColors(cfg.theme)
  const children = []

  const corner = (i, j) => basePoint(L, i - 0.5, j - 0.5)
  const p00 = corner(0, 0)
  const p10 = corner(nx, 0)
  const p11 = corner(nx, ny)
  const p01 = corner(0, ny)

  // 底面板
  children.push({
    type: 'polygon',
    shape: { points: [p00, p10, p11, p01] },
    style: { fill: c.dark ? 'rgba(120,150,210,0.10)' : 'rgba(60,90,160,0.07)', stroke: c.axis, lineWidth: 1 },
    silent: true,
  })

  // 网格线
  const line = (a, b) => ({
    type: 'line',
    shape: { x1: a[0], y1: a[1], x2: b[0], y2: b[1] },
    style: { stroke: c.split, lineWidth: 1 },
    silent: true,
  })
  for (let i = 1; i < nx; i++) children.push(line(corner(i, 0), corner(i, ny)))
  for (let j = 1; j < ny; j++) children.push(line(corner(0, j), corner(nx, j)))

  // 每个格子一块内缩的小菱形底座：数据稀疏时也能看出网格在哪，避免几根柱子孤零零飘着
  const occupied = {}
  ;(cfg.occupiedCells || []).forEach(o => { occupied[o[0] + '_' + o[1]] = 1 })
  if (nx * ny <= 2200) {
    const k = 0.16
    for (let i = 0; i < nx; i++) {
      for (let j = 0; j < ny; j++) {
        const p = basePoint(L, i + 0.5, j + 0.5)
        const hw = (L.tileW / 2) * (1 - k)
        const hh = (L.tileH / 2) * (1 - k)
        const has = !!occupied[i + '_' + j]
        children.push({
          type: 'polygon',
          shape: {
            points: [[p[0], p[1] - hh], [p[0] + hw, p[1]], [p[0], p[1] + hh], [p[0] - hw, p[1]]],
          },
          style: {
            fill: has
              ? (c.dark ? 'rgba(150,190,255,0.20)' : 'rgba(64,120,200,0.16)')
              : (c.dark ? 'rgba(140,160,210,0.06)' : 'rgba(70,100,160,0.05)'),
            stroke: 'none',
          },
          silent: true,
          z2: 1,
        })
      }
    }
  }

  // 刻度标签：X 沿前左棱（-45°），Y 沿前右棱（+45°），按密度抽稀避免糊成一团
  const stepFor = n => Math.max(1, Math.ceil(n / (cfg.maxTicks || 12)))
  const sx = stepFor(nx)
  for (let i = 0; i < nx; i += sx) {
    const p = basePoint(L, i + 0.5, ny)
    children.push(rotLabel(L, xLabels[i], p[0], p[1] + L.tileH * 0.75, -Math.PI / 4, c.sub))
  }
  const sy = stepFor(ny)
  for (let j = 0; j < ny; j += sy) {
    const p = basePoint(L, nx, j + 0.5)
    children.push(rotLabel(L, yLabels[j], p[0], p[1] + L.tileH * 0.75, Math.PI / 4, c.sub))
  }

  // 不在画布里再画标题：浮层头部已经显示了图表名，重复一层只会挤走居中空间
  return { type: 'group', children }
}

function rotLabel(L, text, x, y, rot, fill) {
  const s = String(text === undefined || text === null ? '' : text)
  const short = s.length > 7 ? s.slice(0, 6) + '…' : s
  return {
    type: 'group',
    position: [x, y],
    rotation: rot,
    children: [{
      type: 'text',
      style: { text: short, x: 0, y: 0, fill, fontSize: 10, textAlign: 'center', textVerticalAlign: 'top' },
      silent: true,
    }],
  }
}

function buildBar(api, params, xLabels, yLabels, maxV, cfg) {
  const i = api.value(0)
  const j = api.value(1)
  const v = api.value(2)
  const L = layout(api, xLabels.length, yLabels.length, cfg)
  const base = basePoint(L, i + 0.5, j + 0.5)

  const t = clamp01(v / maxV)
  // 最小高度给到格子短边的量级，否则小值柱会退化成看不见的一条线
  const minH = Math.max(3, L.tileH * 0.22)
  const h = Math.max(minH, Math.pow(t, cfg.gamma || 0.68) * L.maxBarH)
  const hw = L.tileW / 2
  const hh = L.tileH / 2
  const top = api.visual('color') || cfg.baseColor || '#4f9cf9'

  const bx = base[0]
  const by = base[1]
  // 菱形四角（地面）
  const n = [bx, by - hh]
  const e = [bx + hw, by]
  const s = [bx, by + hh]
  const w = [bx - hw, by]
  // 抬升后的顶点
  const nt = [n[0], n[1] - h]
  const et = [e[0], e[1] - h]
  const st = [s[0], s[1] - h]
  const wt = [w[0], w[1] - h]

  const sideStroke = cfg.theme === 'light' ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.16)'

  const group = { type: 'group', children: [
    // 左侧面（较暗）
    { type: 'polygon', shape: { points: [w, s, st, wt] }, style: { fill: shade(top, -0.42), stroke: sideStroke, lineWidth: 0.6 } },
    // 右侧面（中等）
    { type: 'polygon', shape: { points: [s, e, et, st] }, style: { fill: shade(top, -0.22), stroke: sideStroke, lineWidth: 0.6 } },
    // 顶面（最亮，带轻微高光边）
    { type: 'polygon', shape: { points: [nt, et, st, wt] }, style: { fill: shade(top, 0.12), stroke: shade(top, 0.45), lineWidth: 1 }, emphasis: { style: { fill: shade(top, 0.34), stroke: '#fff', lineWidth: 1.6 } } },
  ] }

  // 高柱顶部标数值，矮柱不标，免得糊
  if (t > 0.72) {
    group.children.push({
      type: 'text',
      style: {
        text: String(Math.round(v * 10) / 10),
        x: wt[0] + hw * 0.1, y: wt[1] - 8,
        fill: themeColors(cfg.theme).text, fontSize: 10, textAlign: 'center',
      },
      silent: true,
    })
  }
  return group
}

export { shade as isoShade, niceStep as isoNiceStep }
