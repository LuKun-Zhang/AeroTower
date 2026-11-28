<template>
  <div
    v-show="visible"
    ref="overlay"
    class="chart-overlay"
    :class="['chart-overlay--' + effectiveTheme]"
    :style="overlayStyle"
  >
    <div class="chart-overlay__header" @mousedown="startDrag">
      <span class="chart-overlay__title">{{ pageTitle }}</span>
      <div class="chart-overlay__tools">
        <button class="ov-btn" @click.stop="cycleSize">{{ sizeLabel }}</button>
        <button class="ov-btn" @click.stop="cycleTheme" :title="'图表文字配色（当前：' + effectiveTheme + '）'">明/暗</button>
        <button class="ov-btn" :class="{ 'ov-btn--on': autoRefresh }" @click.stop="toggleRefresh">实时</button>
        <button class="ov-btn" @click.stop="close">✕</button>
      </div>
    </div>

    <div class="chart-overlay__chips">
      <button
        v-for="(c, i) in charts"
        :key="c.id || i"
        class="chart-overlay__chip"
        :class="{ 'chart-overlay__chip--active': i === activeIndex }"
        @click="select(i)"
      >{{ c.title }}</button>
    </div>

    <div class="chart-overlay__body">
      <div v-if="emptyMsg" class="chart-overlay__empty">{{ emptyMsg }}</div>
      <div v-show="!emptyMsg" ref="chart" class="chart-overlay__canvas" :style="canvasStyle"></div>
    </div>

    <div class="chart-overlay__footer">
      <span class="chart-overlay__note">{{ currentNote }}</span>
      <div class="chart-overlay__exports">
        <button class="ov-btn ov-btn--export" @click="exportPng('transparent')">下载图片（透明底）</button>
        <button class="ov-btn ov-btn--export" @click="exportPng(effectiveTheme === 'light' ? '#ffffff' : '#141428')">下载图片（带底色）</button>
        <button class="ov-btn ov-btn--export" @click="exportCsv">下载数据（CSV）</button>
      </div>
    </div>
  </div>
</template>

<script>
import { echarts, withTheme, isEmptyOption, optionToCsv } from '../utils/chartBase'

const SIZES = [
  { key: '中', w: 780, h: 500 },
  { key: '小', w: 560, h: 380 },
  { key: '大', w: 1040, h: 660 },
  { key: '全屏', w: 0, h: 0 },
]

const CHROME_H = 168

// "rgb(20,20,40)" / "rgba(255,255,255,0.06)" / "transparent" → {r,g,b,a}；完全透明返回 null
function parseColor(bg) {
  if (!bg || bg === 'transparent') return null
  const open = bg.indexOf('(')
  if (open < 0) return null
  const parts = bg.slice(open + 1).replace(')', '').split(',').map(s => parseFloat(s))
  if (parts.length < 3 || isNaN(parts[0])) return null
  const alpha = parts.length > 3 ? parts[3] : 1
  if (alpha <= 0) return null
  return { r: parts[0], g: parts[1], b: parts[2], a: alpha }
}

// src 叠在 dst 之上（dst 用非预乘存储），返回合成色
function compositeOver(src, dst) {
  const outA = src.a + dst.a * (1 - src.a)
  if (outA <= 0) return { r: 0, g: 0, b: 0, a: 0 }
  return {
    r: (src.r * src.a + dst.r * dst.a * (1 - src.a)) / outA,
    g: (src.g * src.a + dst.g * dst.a * (1 - src.a)) / outA,
    b: (src.b * src.a + dst.b * dst.a * (1 - src.a)) / outA,
    a: outA,
  }
}

function luminance(c) {
  return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b
}

export default {
  name: 'ChartOverlay',
  props: {
    visible: { type: Boolean, default: false },
    charts: { type: Array, default: () => [] },
    title: { type: String, default: '' },
    theme: { type: String, default: 'auto' },
  },
  data() {
    return {
      activeIndex: 0,
      sizeIndex: 0,
      manualTheme: null,
      detectedTheme: 'dark',
      autoRefresh: true,
      emptyMsg: '',
      pos: null,
      dragging: null,
      chart: null,
      chartDom: null,
      lastOption: null,
      lastExport: null,
      refreshTimer: null,
    }
  },
  computed: {
    effectiveTheme() {
      if (this.theme && this.theme !== 'auto') return this.theme
      return this.manualTheme || this.detectedTheme
    },
    currentSize() {
      const s = SIZES[this.sizeIndex]
      if (s.key === '全屏') {
        return {
          w: Math.max((window.innerWidth || 1200) - 48, 320),
          h: Math.max((window.innerHeight || 800) - 48, 260),
        }
      }
      return s
    },
    sizeLabel() { return SIZES[this.sizeIndex].key },
    canvasWH() {
      const s = this.currentSize
      return { w: s.w, h: Math.max(s.h - CHROME_H, 200) }
    },
    currentChart() { return this.charts[this.activeIndex] || null },
    currentNote() {
      const c = this.currentChart
      return c && c.note ? c.note : ''
    },
    pageTitle() {
      const c = this.currentChart
      return (this.title ? this.title + ' · ' : '') + (c ? c.title : '图表')
    },
    overlayStyle() {
      const base = { width: this.currentSize.w + 'px' }
      if (this.pos) {
        base.left = this.pos.x + 'px'
        base.top = this.pos.y + 'px'
        base.right = 'auto'
      }
      return base
    },
    canvasStyle() {
      const wh = this.canvasWH
      return { width: wh.w + 'px', height: wh.h + 'px' }
    },
  },
  watch: {
    visible(val) {
      if (val) {
        // 等 DOM 落地再测底色，否则浮层显隐状态和页面尺寸都还是上一帧的
        this.$nextTick(() => {
          this.detectTheme(); this.ensureChart(); this.render()
          if (this.autoRefresh) this.startTimer()
        })
      } else {
        this.stopTimer()
        this.autoRefresh = false
        this.dispose()
      }
    },
    charts() {
      this.activeIndex = 0
      if (this.visible) this.$nextTick(() => { this.ensureChart(); this.render() })
    },
    activeIndex() {
      if (this.visible) this.$nextTick(() => this.render())
    },
    effectiveTheme() {
      if (this.visible) this.$nextTick(() => this.render())
    },
    sizeIndex() {
      if (this.visible) this.$nextTick(() => { this.resetSize(); this.render() })
    },
  },
  mounted() {
    window.addEventListener('mousemove', this.onDrag)
    window.addEventListener('mouseup', this.stopDrag)
    window.addEventListener('resize', this.onWindowResize)
  },
  beforeDestroy() {
    window.removeEventListener('mousemove', this.onDrag)
    window.removeEventListener('mouseup', this.stopDrag)
    window.removeEventListener('resize', this.onWindowResize)
    this.stopTimer()
    this.dispose()
  },
  methods: {
    detectTheme() {
      try {
        const col = this.probeBackground()
        this.detectedTheme = col === null ? 'dark' : (luminance(col) < 140 ? 'dark' : 'light')
      } catch (e) {
        this.detectedTheme = 'dark'
      }
    },
    // 取图表文字底下真正合成出来的颜色，决定用亮色还是暗色文字。
    // 两个坑：1) 采样时必须把浮层藏起来，否则 elementFromPoint 命中的是浮层自己；
    // 2) 页面常见「深色壳 + rgba(255,255,255,0.06) 面板」，单看那一层是白的，
    //    必须按 alpha 从下往上合成，否则会误判成浅色主题。
    probeBackground() {
      const vw = window.innerWidth || document.documentElement.clientWidth || 1200
      const vh = window.innerHeight || document.documentElement.clientHeight || 800
      const pts = [
        [Math.max(24, vw * 0.12), Math.max(140, vh * 0.45)],
        [Math.max(24, vw * 0.12), Math.max(140, vh * 0.72)],
        [Math.max(24, vw * 0.3), Math.max(140, vh * 0.3)],
      ]
      const panel = this.$refs.overlay
      const prevDisplay = panel ? panel.style.display : ''
      if (panel) panel.style.display = 'none'
      let hits = []
      try {
        hits = pts.map(p => document.elementFromPoint(p[0], p[1])).filter(Boolean)
      } finally {
        if (panel) panel.style.display = prevDisplay
      }
      for (let k = 0; k < hits.length; k++) {
        const layers = []
        let node = hits[k]
        let guard = 0
        let accA = 0
        while (node && guard < 14 && accA < 0.98) {
          const c = parseColor(getComputedStyle(node).backgroundColor)
          if (c) {
            layers.push(c)
            accA = c.a + accA * (1 - c.a)
          }
          node = node.parentElement
          guard++
        }
        if (!layers.length) continue
        let col = { r: 0, g: 0, b: 0, a: 0 }
        for (let i = layers.length - 1; i >= 0; i--) col = compositeOver(layers[i], col)
        if (col.a < 0.15) continue
        return col
      }
      return null
    },
    ensureChart() {
      const dom = this.$refs.chart
      if (!dom) return
      if (this.chart && this.chartDom === dom) {
        this.resetSize()
        return
      }
      this.dispose()
      // 显式传宽高：容器未布局、或宿主视口为 0 时也能确定渲染尺寸
      const wh = this.canvasWH
      this.chart = echarts.init(dom, null, { renderer: 'canvas', width: wh.w, height: wh.h })
      this.chartDom = dom
    },
    resetSize() {
      if (this.chart) {
        const wh = this.canvasWH
        this.chart.resize({ width: wh.w, height: wh.h })
      }
    },
    render() {
      if (!this.chart) this.ensureChart()
      const c = this.currentChart
      if (!c || !this.chart) { this.emptyMsg = '该页面暂无图表'; return }
      let opt = null
      try {
        opt = c.build(this.effectiveTheme)
      } catch (e) {
        this.emptyMsg = '图表构建失败：' + e.message
        this.chart.clear()
        return
      }
      if (isEmptyOption(opt)) {
        this.emptyMsg = (opt && opt.__empty) ? opt.__empty : '当前没有可用数据'
        this.chart.clear()
        return
      }
      this.emptyMsg = ''
      this.lastOption = withTheme(opt, this.effectiveTheme)
      this.chart.setOption(this.lastOption, true)
    },
    select(i) { this.activeIndex = i },
    close() {
      this.stopTimer()
      this.autoRefresh = false
      this.$emit('update:visible', false)
      this.$emit('close')
    },
    toggleRefresh() {
      this.autoRefresh = !this.autoRefresh
      this.stopTimer()
      if (this.autoRefresh) this.startTimer()
    },
    startTimer() {
      this.stopTimer()
      this.refreshTimer = setInterval(() => { if (this.visible) this.render() }, 1000)
    },
    stopTimer() {
      if (this.refreshTimer) { clearInterval(this.refreshTimer); this.refreshTimer = null }
    },
    cycleSize() { this.sizeIndex = (this.sizeIndex + 1) % SIZES.length },
    cycleTheme() { this.manualTheme = this.effectiveTheme === 'dark' ? 'light' : 'dark' },
    startDrag(e) {
      const rect = this.$refs.overlay.getBoundingClientRect()
      this.dragging = { dx: e.clientX - rect.left, dy: e.clientY - rect.top }
    },
    onDrag(e) {
      if (!this.dragging) return
      this.pos = {
        x: Math.max(0, e.clientX - this.dragging.dx),
        y: Math.max(0, e.clientY - this.dragging.dy),
      }
    },
    stopDrag() { this.dragging = null },
    onWindowResize() {
      if (this.visible && SIZES[this.sizeIndex].key === '全屏') this.$nextTick(() => { this.resetSize(); this.render() })
    },
    exportPng(bg) {
      if (!this.chart || this.emptyMsg) return
      const url = this.chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: bg })
      this.triggerDownload(url, this.fileName('png'))
    },
    exportCsv() {
      if (!this.lastOption) return
      const blob = new Blob(['' + optionToCsv(this.lastOption)], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      this.triggerDownload(url, this.fileName('csv'))
      setTimeout(() => URL.revokeObjectURL(url), 2000)
    },
    triggerDownload(url, name) {
      const a = document.createElement('a')
      a.href = url
      a.download = name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      this.lastExport = { url: String(url).slice(0, 48), name }
    },
    fileName(ext) {
      const t = (this.currentChart && this.currentChart.title) || 'chart'
      return t.replace(/[^0-9A-Za-z一-龥_-]+/g, '_') + '.' + ext
    },
    dispose() {
      if (this.chart) { this.chart.dispose(); this.chart = null; this.chartDom = null }
    },
  },
}
</script>

<style scoped>
.chart-overlay {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 9999;
  background: transparent;
  border: 1px solid rgba(150, 170, 220, 0.35);
  border-radius: 8px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
  font-size: 13px;
}
.chart-overlay__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  cursor: move;
  border-bottom: 1px solid rgba(150, 170, 220, 0.25);
}
.chart-overlay__title { font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chart-overlay__tools { display: flex; gap: 6px; flex-shrink: 0; }
.chart-overlay__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(150, 170, 220, 0.25);
  max-height: 96px;
  overflow-y: auto;
}
.chart-overlay__chip {
  border: 1px solid transparent;
  border-radius: 14px;
  padding: 2px 10px;
  cursor: pointer;
  font-size: 12px;
  line-height: 20px;
}
.chart-overlay__body { position: relative; }
.chart-overlay__canvas { display: block; }
.chart-overlay__empty {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
.chart-overlay__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-top: 1px solid rgba(150, 170, 220, 0.25);
}
.chart-overlay__note { font-size: 11px; opacity: 0.75; }
.chart-overlay__exports { display: flex; gap: 6px; flex-shrink: 0; }
.ov-btn {
  border: 1px solid rgba(150, 170, 220, 0.45);
  background: rgba(120, 140, 190, 0.18);
  color: inherit;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.ov-btn:hover { background: rgba(120, 140, 190, 0.34); }
.ov-btn--on { border-color: #67c23a; color: #67c23a; }
.ov-btn--export { border-color: rgba(79, 156, 249, 0.6); }
.chart-overlay--dark { color: #e6ebf5; }
.chart-overlay--dark .chart-overlay__chip { background: rgba(30, 32, 58, 0.55); color: #cdd6f4; }
.chart-overlay--dark .chart-overlay__chip--active { background: rgba(79, 156, 249, 0.75); color: #fff; }
.chart-overlay--dark .chart-overlay__empty { color: #a8b2c9; }
.chart-overlay--light { color: #303133; }
.chart-overlay--light .chart-overlay__chip { background: rgba(255, 255, 255, 0.65); color: #303133; border-color: rgba(48, 49, 51, 0.2); }
.chart-overlay--light .chart-overlay__chip--active { background: #409eff; color: #fff; border-color: #409eff; }
.chart-overlay--light .ov-btn { background: rgba(255, 255, 255, 0.7); color: #303133; border-color: rgba(48, 49, 51, 0.25); }
.chart-overlay--light .chart-overlay__empty { color: #909399; }
</style>
