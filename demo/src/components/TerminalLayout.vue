<template>
  <div class="terminal-layout" ref="root">
    <canvas ref="canvas" class="layout-canvas"></canvas>
    <div class="zoom-hint">滚轮缩放 · 拖拽平移 · 双击复位</div>
  </div>
</template>

<script>
// 飞机下客完成 → 下一航班开始登机 之间所需的调整时间（模拟分钟）
const TURNAROUND_TIME = 5

// 多日航班调度数据（后端 /api/schedule/gates + /api/schedule/runway 快照）
import { MULTI_DAY_SCHEDULE, SCHEDULE_DATES } from '../data/multiDaySchedule'
import api from '@/api'

// 飞机滑行速度（pathProgress / tick）：提高到 0.06 使其在规定跑道占用时间内完成起降
const TAXI_SPEED = 0.04

// 飞机滑行通道配置
const TAXI_CHANNELS = {
  // 登机口 → 通道映射
  gateToChannel: {
    '矩形 16': 't1_left', '矩形 17': 't1_left', '矩形 18': 't1_left',
    '矩形 19': 't1_left', '矩形 20': 't1_left', '矩形 21': 't1_left',
    '矩形 22': 't1_left', '矩形 23': 't1_left', '矩形 24': 't1_left',
    '矩形 25': 't1_mid', '矩形 26': 't1_mid', '矩形 27': 't1_mid',
    '矩形 28': 't1_mid', '矩形 29': 't1_mid', '矩形 30': 't1_mid',
    '矩形 31': 't1_mid', '矩形 32': 't1_mid',
    '矩形 33': 't1_right', '矩形 34': 't1_right', '矩形 35': 't1_right',
    '矩形 36': 't1_right', '矩形 37': 't1_right',
    '矩形 38': 't1_right', '矩形 39': 't1_right',
    '矩形 41': 't1_right', '矩形 42': 't1_right',
    '矩形 43': 't2_left',
    '矩形 44': 't2_left', '矩形 45': 't2_left',
    '矩形 46': 't2_left', '矩形 47': 't2_left', '矩形 48': 't2_left',
    '矩形 49': 't2_left', '矩形 50': 't2_left', '矩形 51': 't2_left',
    '矩形 52': 't2_left',
    '矩形 53': 't2_left', '矩形 54': 't2_left', '矩形 55': 't2_left',
    '矩形 56': 't2_left', '矩形 57': 't2_left', '矩形 58': 't2_left',
    '矩形 59': 't2_left', '矩形 60': 't2_left', '矩形 61': 't2_left',
    '矩形 62': 't2_mid', '矩形 63': 't2_mid', '矩形 64': 't2_mid',
    '矩形 65': 't2_mid', '矩形 66': 't2_mid', '矩形 67': 't2_mid',
    '矩形 68': 't2_mid', '矩形 69': 't2_mid', '矩形 70': 't2_mid',
    '矩形 71': 't2_mid',
    '矩形 72': 't2_right', '矩形 73': 't2_right', '矩形 74': 't2_right',
    '矩形 75': 't2_right', '矩形 76': 't2_right', '矩形 77': 't2_right',
    '矩形 78': 't2_right', '矩形 79': 't2_right', '矩形 80': 't2_right',
    '矩形 81': 't2_right', '矩形 82': 't2_right', '矩形 83': 't2_right',
    '矩形 84': 't2_right', '矩形 85': 't2_right', '矩形 86': 't2_right',
    '矩形 92': 't2_right',
  },
  channelEndpoints: {
    // 跑道一（矩形 14: x=34.4~612, y=522.6~546.6, 中心线 y=534.6）
    // 所有飞机统一从最左侧 x=34 进入，完整滑跑整条跑道
    t1_left:  { x: 34,  y: 534.6, angle: 0,  runway: '跑道一' },
    t1_mid:   { x: 34,  y: 534.6, angle: 0,  runway: '跑道一' },
    t1_right: { x: 34,  y: 534.6, angle: 0,  runway: '跑道一' },
    t2_left:  { x: 34,  y: 534.6, angle: 0,  runway: '跑道一' },
    t2_mid:   { x: 34,  y: 534.6, angle: 0,  runway: '跑道一' },
    // 跑道二（矩形 15: x=632.9~1210.5, y=306.6~330.6, 中心线 y=318.6）
    t2_right: { x: 638, y: 318.6, angle: 0,  runway: '跑道二' },
  },
}

// 工具函数：路径插值
function interpolatePath(waypoints, t) {
  if (!waypoints || waypoints.length < 2) return waypoints[0] || { x: 0, y: 0 }
  const totalSegs = waypoints.length - 1
  const segFloat = t * totalSegs
  const segIdx = Math.min(Math.floor(segFloat), totalSegs - 1)
  const segT = segFloat - segIdx
  const a = waypoints[segIdx], b = waypoints[segIdx + 1]
  return { x: a.x + (b.x - a.x) * segT, y: a.y + (b.y - a.y) * segT }
}

function getPathAngle(waypoints, t) {
  if (!waypoints || waypoints.length < 2) return 0
  const totalSegs = waypoints.length - 1
  const segIdx = Math.min(Math.floor(t * totalSegs), totalSegs - 1)
  const a = waypoints[segIdx], b = waypoints[segIdx + 1]
  return Math.atan2(b.y - a.y, b.x - a.x)
}

export default {
  name: 'TerminalLayout',
  data() {
    return {
      canvasWidth: 1200,
      canvasHeight: 600,
      // 画布视图变换：滚轮缩放、拖拽平移
      dpr: 1,
      viewScale: 1,
      viewX: 0,
      viewY: 0,
      panning: false,
      scaleX: 1,
      scaleY: 1,
      offsetX: 0,
      offsetY: 0,
      // 旅客粒子
      passengers: [],
      routeCorridors: [],
      _animFrame: null,
      layoutData: null,

      // ===== 模拟引擎状态 =====
      simState: {
        running: false,
        paused: false,
        speed: 1,
        currentTime: 0,
        timePerTick: 0.1,
      },
      // 旅客生成参数
      paxParams: {
        inboundRate: 10,
        outboundRate: 6,
        transitRatio: 0.05,
        loadFactor: 0.78,
      },
      // 闸门状态 { name: { status:'open'|'closed', type:'entry'|'exit'|'boarding' } }
      gateStates: {},
      // 模拟航班
      simFlights: [],
      // 疏散模式
      evacuation: {
        active: false,
        targetArea: 'all',
        availableExits: [],
        totalEvacuating: 0,
        totalArrived: 0,
      },
      // 拥堵热力图
      congestion: {
        enabled: false,
        levels: [],
      },
      // 辅助
      paxCounter: 0,
      spawnAccum: 0,
      lastSimTick: 0,
      tickTimer: null,
      entryGates: [],
      exitGates: [],
      boardingGates: [],
      // 候机区中心
      terminalCenters: {},
      // 主干道走廊索引（旅客等待区）
      trunkCorridorIdx: { T1: -1, T2: -1 },
      // 入港旅客已投放总数（控制总量）
      totalInboundSpawned: 0,
      // 已到达航班的下客标记
      arrivedFlightsDeboarded: new Set(),
      // 各到达航班下客完成的时刻（用于周转间隔判断）
      _deboardedAt: {},
      // 各出发航班已投放旅客数（持久计数，不受画布清理影响）
      _spawnedByFlight: {},
      // 乘客编号清单（flight_no -> [pax_id,...]），从后端 /api/paxflow/manifests 拉取；
      // 拉取为空时前端按规则生成兜底编号（格式与后端 Pax-MMDD-XXXXX 一致，航班内唯一）
      _paxManifest: {},
      // 乘客终态日志：key = `${flightNo}|${paxId}` → { status:'boarded'|'exited', ... }
      // 记录已登机/已出站并被清理的粒子，供状态查询组件追溯
      _paxLog: {},
      // 飞机精灵
      airplanes: [],
      // 飞机机队（持久化跟踪每架飞机的生命周期）
      airplaneFleet: [],
      // 测试航班计划
      flightSchedule: [],
      // 门到门滑行中的飞机
      gateTransferPlanes: [],
      // 滑行路径显示
      showTaxiPaths: true,
      // 跑道冷却：防止起飞降落冲突
      runwayCooldown: { '跑道一': 0, '跑道二': 0 },
      // ===== 多日模拟 =====
      currentDate: (SCHEDULE_DATES && SCHEDULE_DATES[0]) || '2020-11-30',
      // 后端 /api/paxflow/schedule 拉取的按天航班调度（优先于静态 MULTI_DAY_SCHEDULE）
      paxflowSchedule: null,
      paxflowDates: [],
      // 模拟总时长（分钟）：一天 24h = 1440
      simTotalMinutes: 1440,
      // 当天是否已发射 day-complete（避免重复通知）
      _dayCompleteEmitted: false,
    }
  },
  async mounted() {
    // HMR 保护：每次挂载强制重置
    if (this._animFrame) { cancelAnimationFrame(this._animFrame); this._animFrame = null }
    this.passengers = []
    this.routeCorridors = []

    // 预加载飞机俯视图
    if (!this._airplaneImg) {
      this._airplaneImg = new Image()
      this._airplaneImg.src = '/airplane.svg'
    }

    if (this._resizeObserver) { this._resizeObserver.disconnect(); this._resizeObserver = null }

    console.log('[DEBUG] Step 1: loadData...')
    await this.loadData()
    console.log('[DEBUG] Step 1 done. layoutData keys:', Object.keys(this.layoutData || {}))
    console.log('[DEBUG] Step 2: initGateStates...')
    this.initGateStates()
    console.log('[DEBUG] Step 2 done. gateStates count:', Object.keys(this.gateStates).length)
    console.log('[DEBUG] Step 3: initPassengers...')
    this.initPassengers()
    console.log('[DEBUG] Step 3 done. entryGates:', this.entryGates.length, 'exitGates:', this.exitGates.length, 'boardingGates:', this.boardingGates.length, 'corridors:', this.routeCorridors.length)
    // 先构造路线再初始化 canvas（需要 routeCorridors 数据）
    console.log('[DEBUG] Step 4: initCanvas...')
    this.initCanvas()
    console.log('[DEBUG] Step 5: buildScene...')
    this.buildScene()
    console.log('[DEBUG] Step 5 done.')
    console.log('[DEBUG] Step 6: startSimulation...')
    this.startSimulation()
    console.log('[DEBUG] Step 7: startAnimation...')
    this.startAnimation()
    window.addEventListener('resize', this.onResize)
    this._resizeObserver = new ResizeObserver(() => {
      this.onResize()
    })
    this._resizeObserver.observe(this.$refs.root)
    console.log('[DEBUG] mounted() COMPLETE. running=', this.simState.running, 'paused=', this.simState.paused, 'flights=', this.simFlights.length, 'pax=', this.passengers.length, 'planes=', this.airplanes.length)
    // 画布缩放 / 拖拽
    const canvas = this.$refs.canvas
    if (canvas) {
      canvas.addEventListener('wheel', this.onViewWheel, { passive: false })
      canvas.addEventListener('mousedown', this.onViewPanStart)
      canvas.addEventListener('dblclick', this.resetView)
      canvas.addEventListener('contextmenu', (e) => e.preventDefault())
    }
    window.addEventListener('mousemove', this.onViewPanMove)
    window.addEventListener('mouseup', this.onViewPanEnd)

    // 异步拉取后端真实航班调度（不阻塞模拟启动；成功后自动切换到最早日期）
    this.loadPaxflowSchedule()
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.onResize)
    window.removeEventListener('mousemove', this.onViewPanMove)
    window.removeEventListener('mouseup', this.onViewPanEnd)
    const canvas = this.$refs.canvas
    if (canvas) {
      canvas.removeEventListener('wheel', this.onViewWheel)
      canvas.removeEventListener('mousedown', this.onViewPanStart)
      canvas.removeEventListener('dblclick', this.resetView)
    }
    if (this._resizeObserver) { this._resizeObserver.disconnect(); this._resizeObserver = null }
    if (this._animFrame) cancelAnimationFrame(this._animFrame)
  },
  methods: {
    async loadData() {
      try {
        const res = await fetch('/terminal_layout.json?v=' + Date.now())
        this.layoutData = await res.json()
      } catch (e) {
        console.error('Failed to load terminal_layout.json', e)
      }
    },

    initCanvas() {
      const root = this.$refs.root
      // 始终以 window 尺寸为准，避免 flex 布局未完成时容器高度异常（如 97px）
      const w = Math.max(root.clientWidth || 0, window.innerWidth - 280)
      const h = Math.max(root.clientHeight || 0, window.innerHeight - 110)
      this.canvasWidth = w
      this.canvasHeight = h
      const canvas = this.$refs.canvas
      if (!canvas) return
      // 内部分辨率按 devicePixelRatio 放大（上限 2，兼顾清晰度与显存），
      // 绘制仍用 CSS 像素坐标，由 transform 统一缩放，放大后文字不糊
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      this.dpr = dpr
      canvas.width = Math.round(this.canvasWidth * dpr)
      canvas.height = Math.round(this.canvasHeight * dpr)
      canvas.style.width = this.canvasWidth + 'px'
      canvas.style.height = this.canvasHeight + 'px'
      const ctx0 = canvas.getContext('2d')
      if (ctx0) ctx0.setTransform(dpr, 0, 0, dpr, 0, 0)
      // 容器也撑到足够大
      if (root) {
        root.style.width = this.canvasWidth + 'px'
        root.style.height = this.canvasHeight + 'px'
      }

      console.log('[TerminalLayout] Canvas size:', this.canvasWidth, 'x', this.canvasHeight)

      const b = this.layoutData.meta.bounds
      const pad = 40
      this.scaleX = (this.canvasWidth - pad * 2) / b.width
      this.scaleY = (this.canvasHeight - pad * 2) / b.height
      this.offsetX = pad - b.min_x * this.scaleX
      this.offsetY = pad - b.min_y * this.scaleY
    },

    onViewWheel(e) {
      e.preventDefault()
      const canvas = this.$refs.canvas
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const mx = (e.clientX - rect.left) * (this.canvasWidth / rect.width)
      const my = (e.clientY - rect.top) * (this.canvasHeight / rect.height)
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
      const next = Math.min(5, Math.max(0.6, this.viewScale * factor))
      const k = next / this.viewScale
      // 以鼠标位置为锚点缩放
      this.viewX = mx - (mx - this.viewX) * k
      this.viewY = my - (my - this.viewY) * k
      this.viewScale = next
    },

    onViewPanStart(e) {
      if (e.button !== 0) return
      this.panning = true
      this._panStart = { x: e.clientX, y: e.clientY, vx: this.viewX, vy: this.viewY }
      e.preventDefault()
    },

    onViewPanMove(e) {
      if (!this.panning || !this._panStart) return
      this.viewX = this._panStart.vx + (e.clientX - this._panStart.x)
      this.viewY = this._panStart.vy + (e.clientY - this._panStart.y)
    },

    onViewPanEnd() {
      this.panning = false
      this._panStart = null
    },

    resetView() {
      this.viewScale = 1
      this.viewX = 0
      this.viewY = 0
    },

    tx(x) { return (x * this.scaleX + this.offsetX) * this.viewScale + this.viewX },
    ty(y) { return (y * this.scaleY + this.offsetY) * this.viewScale + this.viewY },
    tw(w) { return w * this.scaleX * this.viewScale },
    th(h) { return h * this.scaleY * this.viewScale },

    buildScene() {
      this.drawAll()
    },

    drawAll() {
      const canvas = this.$refs.canvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight)

      // 背景
      ctx.fillStyle = '#1a1a2e'
      ctx.fillRect(0, 0, this.canvasWidth, this.canvasHeight)

      // 画网格
      ctx.strokeStyle = 'rgba(255,255,255,0.03)'
      ctx.lineWidth = 1
      for (let i = 0; i < this.canvasWidth; i += 40) {
        ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, this.canvasHeight); ctx.stroke()
      }
      for (let j = 0; j < this.canvasHeight; j += 40) {
        ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(this.canvasWidth, j); ctx.stroke()
      }

      this.drawRunways(ctx)
      this.drawPiers(ctx)
      this.drawTerminals(ctx)
      this.drawGates(ctx)
      this.drawSpines(ctx)
      this.drawBackendGateLabels(ctx)
    },

    // 在 5 个映射登机口上方绘制后端登机口号（辰Gxx），便于对照登机口分配页
    drawBackendGateLabels(ctx) {
      if (!this.flightSchedule.length) return
      const allGates = this.layoutData ? (this.layoutData.gates || []) : []
      ctx.save()
      for (const f of this.flightSchedule) {
        if (!f.backendGate) continue
        const g = allGates.find(x => x.name === f.gateName)
        if (!g) continue
        const cx = this.tx(g.x + g.w / 2)
        const cy = this.ty(g.y + g.h / 2)
        ctx.fillStyle = 'rgba(10, 15, 30, 0.75)'
        ctx.fillRect(cx - 24, cy - 30, 48, 15)
        ctx.strokeStyle = '#ffd54f'
        ctx.lineWidth = 1
        ctx.strokeRect(cx - 24, cy - 30, 48, 15)
        ctx.fillStyle = '#ffd54f'
        ctx.font = 'bold 10px monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(f.backendGate, cx, cy - 22)
      }
      ctx.restore()
    },

    drawRunways(ctx) {
      const runways = this.layoutData.runways || []
      for (const r of runways) {
        const rx = this.tx(r.x), ry = this.ty(r.y), rw = this.tw(r.w), rh = this.th(r.h)
        ctx.fillStyle = '#3a3a5c'
        ctx.fillRect(rx, ry, rw, rh)
        ctx.strokeStyle = '#5a5a8c'
        ctx.lineWidth = 2
        ctx.strokeRect(rx, ry, rw, rh)

        // 跑道中线
        ctx.setLineDash([12, 8])
        ctx.strokeStyle = '#8a8abc'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(rx + 10, ry + rh / 2)
        ctx.lineTo(rx + rw - 10, ry + rh / 2)
        ctx.stroke()
        ctx.setLineDash([])

        // 标签
        if (r.text) {
          ctx.fillStyle = '#aaa'
          ctx.font = `${Math.max(12, rh * 0.7)}px sans-serif`
          ctx.textAlign = 'center'
          ctx.fillText(r.text, rx + rw / 2, ry - 6)
        }
      }
    },

    drawPiers(ctx) {
      const piers = this.layoutData.piers || []
      for (const p of piers) {
        const px = this.tx(p.x), py = this.ty(p.y), pw = this.tw(p.w), ph = this.th(p.h)
        ctx.fillStyle = '#3d5060'
        ctx.fillRect(px, py, pw, ph)
        ctx.strokeStyle = '#5a7a90'
        ctx.lineWidth = 1.5
        ctx.strokeRect(px, py, pw, ph)
      }
    },

    drawTerminals(ctx) {
      const terminals = this.layoutData.terminals || []
      for (const t of terminals) {
        const tx = this.tx(t.x), ty2 = this.ty(t.y), tw = this.tw(t.w), th = this.th(t.h)
        // 航站楼主体
        const grad = ctx.createLinearGradient(tx, ty2, tx, ty2 + th)
        grad.addColorStop(0, '#2c4a6e')
        grad.addColorStop(1, '#1a3350')
        ctx.fillStyle = grad
        ctx.fillRect(tx, ty2, tw, th)
        ctx.strokeStyle = '#4a8ab5'
        ctx.lineWidth = 2.5
        ctx.strokeRect(tx, ty2, tw, th)

        // 标签
        if (t.terminal_name) {
          ctx.fillStyle = '#fff'
          ctx.font = `bold ${Math.max(13, th * 0.55)}px sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'middle'
          ctx.fillText(t.terminal_name, tx + tw / 2, ty2 + th / 2)
        }
      }
    },

    drawGates(ctx) {
      const gates = this.layoutData.gates || []
      for (const g of gates) {
        const gx = this.tx(g.x), gy = this.ty(g.y), gw = this.tw(g.w), gh = this.th(g.h)
        const cx = gx + gw / 2
        const cy = gy + gh / 2
        const isArrow = g.type === 'upArrow' || g.type === 'downArrow'
        const isEntry = g.gate_dir === 'entry'
        const rotDeg = g.rot || 0

        ctx.save()
        ctx.translate(cx, cy)
        if (rotDeg !== 0) {
          ctx.rotate(rotDeg * Math.PI / 180)
        }

        if (isArrow) {
          // 箭头 → 竖直矩形 + 标签
          const rectW = gw * 0.55
          const rectH = gh * 0.85
          if (isEntry) {
            ctx.fillStyle = '#1b5e20'
            ctx.strokeStyle = '#4caf50'
          } else {
            ctx.fillStyle = '#4e342e'
            ctx.strokeStyle = '#ff9800'
          }
          ctx.lineWidth = 1.5
          ctx.fillRect(-rectW / 2, -rectH / 2, rectW, rectH)
          ctx.strokeRect(-rectW / 2, -rectH / 2, rectW, rectH)

          // 标签文字（旋转回来正向显示）
          ctx.rotate(-rotDeg * Math.PI / 180)
          ctx.fillStyle = isEntry ? '#a5d6a7' : '#ffcc80'
          const fontSize = Math.max(8, Math.min(12, gh * 0.35))
          ctx.font = `${fontSize}px sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'middle'
          ctx.fillText(isEntry ? '入口' : '出口', 0, 0)
        } else {
          // 矩形登机口
          ctx.fillStyle = '#557a95'
          ctx.fillRect(-gw / 2, -gh / 2, gw, gh)
          ctx.strokeStyle = '#7aaac0'
          ctx.lineWidth = 0.8
          ctx.strokeRect(-gw / 2, -gh / 2, gw, gh)
        }
        ctx.restore()

        // 标注名称（所有 gate）
        ctx.save()
        ctx.fillStyle = '#ffd54f'
        const fontSize = Math.max(7, Math.min(10, gh * 0.3))
        ctx.font = `bold ${fontSize}px monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        // 获取简短名称
        let label = g.name || ''
        label = label.replace('箭头: ', '')
        ctx.fillText(label, cx, cy + gh * 0.55)
        ctx.restore()
      }
    },

    // ========== 绘制廊桥主干道脊柱线 ==========
    drawSpines(ctx) {
      if (!this._spines) return
      const allSpines = [
        ...this._spines.t1PierSpineXs
          .filter(s => s.key !== '矩形 40')   // 矩形40是连廊，不是独立主干道
          .map(s => ({ ...s, label: s.key + '主干', color: '#4caf50' })),
        ...this._spines.t2PierSpineXs.map(s => ({ ...s, label: s.key + '主干', color: '#2196f3' })),
      ]
      for (const s of allSpines) {
        const sx = this.tx(s.x)
        const syTop = this.ty(s.yTop)
        const syBot = this.ty(s.yBot)
        // 虚线脊柱
        ctx.save()
        ctx.setLineDash([6, 4])
        ctx.strokeStyle = s.color + 'aa'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(sx, syTop)
        ctx.lineTo(sx, syBot)
        ctx.stroke()
        ctx.setLineDash([])
        // 标签
        ctx.fillStyle = s.color
        ctx.font = 'bold 8px monospace'
        ctx.textAlign = 'right'
        ctx.textBaseline = 'bottom'
        ctx.fillText(s.label, sx - 4, syTop - 3)
        ctx.restore()
      }
      // T1/T2 主干水平线
      const t1MainY = this._spines.t1MainY
      const t2MainY = this._spines.t2MainY
      const drawMainRoad = (y, color, label, xStart, xEnd) => {
        const sy = this.ty(y)
        ctx.save()
        ctx.setLineDash([8, 4])
        ctx.strokeStyle = color + '88'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(this.tx(xStart), sy)
        ctx.lineTo(this.tx(xEnd), sy)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.fillStyle = color
        ctx.font = 'bold 9px monospace'
        ctx.textAlign = 'right'
        ctx.fillText(label, this.tx(xEnd) - 4, sy - 5)
        ctx.restore()
      }
      if (this.layoutData && this.layoutData.terminals) {
        const t1 = this.layoutData.terminals[0]
        const t2 = this.layoutData.terminals[1]
        if (t1) drawMainRoad(t1MainY, '#4caf50', 'T1主干道', t1.x, t1.x + t1.w)
        if (t2) drawMainRoad(t2MainY, '#2196f3', 'T2主干道', t2.x, t2.x + t2.w)
      }
    },

    // ========== 旅客流 ==========
    initPassengers() {
      this.passengers = []
      this.routeCorridors = []
      const terminals = this.layoutData.terminals
      const allGates = this.layoutData.gates || []

      if (terminals.length < 2) return

      const t1 = terminals[0]
      const t2 = terminals[1]
      const t1cx = t1.x + t1.w / 2, t1cy = t1.y + t1.h / 2
      const t2cx = t2.x + t2.w / 2, t2cy = t2.y + t2.h / 2

      const gateC = g => ({ x: g.x + g.w / 2, y: g.y + g.h / 2 })

      // Terminal main road Y (必须在 pierSpines 使用之前定义)
      const t1MainY = t1cy  // 350
      const t2MainY = t2cy  // 315

      // Colors
      const t1Green = '#4caf50', t1Green2 = '#81c784'
      const t1Orange = '#ff9800', t1Orange2 = '#ffb74d'
      const t2Blue = '#2196f3', t2Blue2 = '#64b5f6'
      const t2Orange = '#ff9800', t2Orange2 = '#ffb74d'

      const excludedGates = ['矩形 41', '矩形 42', '矩形 43', '矩形 46', '矩形 50', '矩形 53', '矩形 54', '矩形 55', '矩形 56', '矩形 57', '矩形 58', '矩形 59', '矩形 60', '矩形 61']

      // === T1: 入口 → 主干 → pier脊柱 → gate ===
      const t1Entries = allGates.filter(g => g.gate_dir === 'entry' && g.x < t1.x + t1.w + 80)
      const t1Exits = allGates.filter(g => g.gate_dir === 'exit' && g.x < t1.x + t1.w + 80)
      const t1RectGates = allGates.filter(g => {
        if (g.type !== 'rect') return false
        if (excludedGates.includes(g.name)) return false
        const ref = (g.attach || {}).ref || ''
        // 矩形37 应走左边矩形8 主干
        if (g.name === '矩形 37') return true
        return ref.includes('矩形 5') || ref.includes('矩形 6') || ref.includes('矩形 7') ||
               ref.includes('矩形 8') || ref.includes('矩形 40') || ref.includes('航站楼1')
      })

      // === T2: 入口 → 主干 → pier脊柱 → gate ===
      const t2Entries = allGates.filter(g => g.gate_dir === 'entry' && g.x > t2.x - 80)
      const t2Exits = allGates.filter(g => g.gate_dir === 'exit' && g.x > t2.x - 80)
      const t2RectGates = allGates.filter(g => {
        if (g.type !== 'rect') return false
        if (excludedGates.includes(g.name)) return false
        if (g.name === '矩形 37') return false   // 已归入 T1
        const ref = (g.attach || {}).ref || ''
        return ref.includes('矩形 9') || ref.includes('矩形 11') || ref.includes('矩形 12') ||
               ref.includes('矩形 13') || ref.includes('航站楼2')
      })

      // 全部出站口（T1 2个 + T2 2个 = 4个），下客旅客按距离加权选择（仅同航站楼内，不新增跨航站楼路线）

      // 给一个 gate 找所属 pier spine
      const t1PierSpineXs = [
        { key: '矩形 6', x: 34 + 9, yTop: 355, yBot: 444 },
        { key: '矩形 7', x: 145 + 9, yTop: 367, yBot: 444 },
        { key: '矩形 8', x: 261 + 9, yTop: 355, yBot: 444 },
        { key: '矩形 40', x: 244 + 49, yTop: 344, yBot: 362 },
      ]
      const t2PierSpineXs = [
        { key: '矩形 11', x: 341 + 9, yTop: 320, yBot: 409 },
        { key: '矩形 12', x: 452 + 9, yTop: 332, yBot: 409 },
        { key: '矩形 13', x: 568 + 9, yTop: 243, yBot: 409 },
      ]

      // 存储脊柱数据供 drawAll 使用
      this._spines = { t1PierSpineXs, t2PierSpineXs, t1MainY, t2MainY }

      const findNearestSpine = (gateX, spines) => {
        let best = null, bestDist = Infinity
        for (const s of spines) {
          const d = Math.abs(gateX - s.x)
          if (d < bestDist) { bestDist = d; best = s }
        }
        return best
      }

      const getSpine = (g) => {
        // 矩形37 强制走左边矩形8 主干
        if (g.name === '矩形 37') {
          return { x: 261 + 9, yTop: 355, yBot: 444 }  // 矩形8 spine
        }
        const ref = (g.attach || {}).ref || ''
        const gx = g.x + g.w / 2
        for (const s of [...t1PierSpineXs, ...t2PierSpineXs]) {
          if (ref.includes(s.key)) return { x: s.x, yTop: s.yTop, yBot: s.yBot }
        }
        if (ref.includes('矩形 5') || ref.includes('航站楼1')) {
          const ns = findNearestSpine(gx, t1PierSpineXs)
          if (ns) return { x: ns.x, yTop: ns.yTop, yBot: ns.yBot }
          return { x: t1cx, yTop: t1MainY - 20, yBot: t1MainY + 20 }
        }
        if (ref.includes('矩形 9') || ref.includes('航站楼2')) {
          const ns = findNearestSpine(gx, t2PierSpineXs)
          if (ns) return { x: ns.x, yTop: ns.yTop, yBot: ns.yBot }
          return { x: t2cx, yTop: t2MainY - 20, yBot: t2MainY + 20 }
        }
        return null
      }

      // 构建路线: entry → (entry.x, mainY) → (spine.x, mainY) → (spine.x, gateY) → (gate.x, gateY)
      // 3次中转: 在 mainY 转弯, 在 spine.x 转弯, 在 gateY 转弯
      const buildRoute = (entryGate, rectGate, mainY, color) => {
        const eC = gateC(entryGate)
        const gC = gateC(rectGate)
        const spine = getSpine(rectGate)

        let spineX, spineBoundY
        if (spine) {
          spineX = spine.x
          spineBoundY = gC.y  // 脊柱延伸到 gate 高度，保证竖直+水平两段
        } else {
          // 直接挂在 terminal 上的 gate，脊柱 = terminal 中心
          spineX = (rectGate.x < t1.x + t1.w + 200) ? t1cx : t2cx
          spineBoundY = gC.y
        }

        const wps = [
          { x: eC.x, y: eC.y },           // 0: 入口 gate
          { x: eC.x, y: mainY },           // 1: 竖直下落 到主干 road
          { x: spineX, y: mainY },         // 2: 水平 沿主干到 pier spine
          { x: spineX, y: spineBoundY },   // 3: 竖直 沿脊柱到 gate 高度
          { x: gC.x, y: gC.y },            // 4: 水平 延伸到 gate
        ]
        return { waypoints: wps, width: 5, color: color + 'cc', routeType: '' }  // 加宽加半透明
      }

      // 构建离港射线 (gate → 出门方向短标记，不延伸避免形成平行路)
      const buildExitRay = (rectGate, color) => {
        const gC = gateC(rectGate)
        const side = (rectGate.attach || {}).side || ''
        const spine = getSpine(rectGate)
        let dx = 0, dy = 0
        const rayLen = 6
        if (spine) {
          const spineX = spine.x
          if (side === 'left')      { dx = -rayLen }             // gate在脊柱左边 → 向左射出
          else if (side === 'right') { dx = rayLen }             // gate在脊柱右边 → 向右射出
          else if (side === 'top')   { dy = -rayLen }            // gate在上方 → 向上射出
          else if (side === 'bottom'){ dy = rayLen }             // gate在下方 → 向下射出
          else if (gC.x >= spineX)   { dx = rayLen }
          else                       { dx = -rayLen }
        } else {
          dx = rayLen
        }
        return {
          waypoints: [
            { x: gC.x, y: gC.y },
            { x: gC.x + dx, y: gC.y + dy },
          ],
          width: 2, color: color + '66'
        }
      }

      // === 生成路由 ===
      // T1: 每个入口 × 每个 rect gate（多条入口汇入主干）
      if (t1Entries.length && t1RectGates.length) {
        for (const entry of t1Entries) {
          for (const g of t1RectGates) {
            this.routeCorridors.push(Object.assign(buildRoute(entry, g, t1MainY, t1Green), { routeType: 't1-in', gateName: g.name }))
          }
        }
        // T1 离港: 每个 rect gate → 短射线出门即消失
        if (t1Exits.length) {
          for (const g of t1RectGates) {
            this.routeCorridors.push(Object.assign(buildExitRay(g, t1Orange), { routeType: 't1-out' }))
          }
        }
      }

      // T2: 每个入口 × 每个 rect gate
      if (t2Entries.length && t2RectGates.length) {
        for (const entry of t2Entries) {
          for (const g of t2RectGates) {
            this.routeCorridors.push(Object.assign(buildRoute(entry, g, t2MainY, t2Blue), { routeType: 't2-in', gateName: g.name }))
          }
        }
        // T2 离港: 每个 rect gate → 短射线出门即消失
        if (t2Exits.length) {
          for (const g of t2RectGates) {
            this.routeCorridors.push(Object.assign(buildExitRay(g, t2Orange), { routeType: 't2-out' }))
          }
        }
      }

      // T1 干路线：所有入口 → 主干水平线（加宽作为等待区）
      if (t1Entries.length) {
        for (const entry of t1Entries) {
          const eC = gateC(entry)
          this.routeCorridors.push({
            waypoints: [{ x: eC.x, y: eC.y }, { x: eC.x, y: t1MainY }, { x: t1cx, y: t1MainY }],
            width: 24, color: t1Green, label: 'T1到港', routeType: 't1-trunk'
          })
        }
      }
      // 记录 T1 主干道最后一个走廊索引（等待区用）
      this.trunkCorridorIdx.T1 = this.routeCorridors.length - 1

      // T2 干路线（加宽作为等待区）
      if (t2Entries.length) {
        for (const entry of t2Entries) {
          const eC = gateC(entry)
          this.routeCorridors.push({
            waypoints: [{ x: eC.x, y: eC.y }, { x: eC.x, y: t2MainY }, { x: t2cx, y: t2MainY }],
            width: 24, color: t2Blue, label: 'T2到港', routeType: 't2-trunk'
          })
        }
      }
      // 记录 T2 主干道最后一个走廊索引（等待区用）
      this.trunkCorridorIdx.T2 = this.routeCorridors.length - 1

      // 矩形8主干 → 矩形11主干 水平蓝色连接路（仅视觉）
      this.routeCorridors.push({
        waypoints: [
          { x: 270, y: 344 + 8.5 },
          { x: 350, y: 344 + 8.5 },
        ],
        width: 6, color: '#2196f3cc', label: '矩形8↔矩形11', routeType: 'conn'
      })

      // T1主干 → 矩形8脊柱 → 连接线 → 矩形11脊柱 → T2主干 双向联通走廊
      const connY = 344 + 8.5
      const linkRouteWaypoints = [
        { x: t1cx, y: t1MainY },      // T1主干中心
        { x: 270, y: t1MainY },       // T1主干到矩形8脊柱
        { x: 270, y: connY },         // 矩形8脊柱下到连接线
        { x: 350, y: connY },         // 水平穿过连接线
        { x: 350, y: t2MainY },       // 矩形11脊柱上到T2主干
        { x: t2cx, y: t2MainY },      // T2主干到中心
      ]
      this.routeCorridors.push({
        waypoints: linkRouteWaypoints,
        width: 6, color: '#2196f3cc', label: 'T1↔T2联通', routeType: 'link'
      })
      // 反向也加一条，保证双向都有粒子流
      this.routeCorridors.push({
        waypoints: [...linkRouteWaypoints].reverse(),
        width: 6, color: '#2196f3cc', routeType: 'link'
      })

      // 连接线向下垂直延伸到矩形41/42/43
      const gateApproaches = [
        { x: 280.65 + 15.69, gate: '矩形 41' },
        { x: 295.22 + 15.69, gate: '矩形 42' },
        { x: 309.17 + 15.69, gate: '矩形 43' },
      ]
      for (const ga of gateApproaches) {
        this.routeCorridors.push({
          waypoints: [
            { x: ga.x, y: connY },
            { x: ga.x, y: 370 },
          ],
          width: 5, color: '#2196f3cc', label: ga.gate, routeType: 'gate-approach'
        })
        // 反向
        this.routeCorridors.push({
          waypoints: [
            { x: ga.x, y: 370 },
            { x: ga.x, y: connY },
          ],
          width: 5, color: '#2196f3cc', routeType: 'gate-approach'
        })
      }

      // T2水平主干道向下垂直延伸到矩形53~61
      const t2Approaches = [
        { x: 392.45, gate: '矩形 53' },
        { x: 407.03, gate: '矩形 54' },
        { x: 420.97, gate: '矩形 55' },
        { x: 433.86, gate: '矩形 56' },
        { x: 489.28, gate: '矩形 57' },
        { x: 503.86, gate: '矩形 58' },
        { x: 517.81, gate: '矩形 59' },
        { x: 530.70, gate: '矩形 60' },
        { x: 543.44, gate: '矩形 61' },
      ]
      for (const ga of t2Approaches) {
        this.routeCorridors.push({
          waypoints: [
            { x: ga.x, y: t2MainY },
            { x: ga.x, y: 360 },
          ],
          width: 5, color: '#2196f3cc', label: ga.gate, routeType: 'gate-approach'
        })
        this.routeCorridors.push({
          waypoints: [
            { x: ga.x, y: 360 },
            { x: ga.x, y: t2MainY },
          ],
          width: 5, color: '#2196f3cc', routeType: 'gate-approach'
        })
      }

      // 矩形11主干水平延伸到矩形46(左)和矩形50(右)
      const h11Approaches = [
        { xEnd: 312, y: 396.3, gate: '矩形 46', dir: 'left' },
        { xEnd: 392, y: 364.43, gate: '矩形 50', dir: 'right' },
      ]
      const spine11X = 350
      for (const ha of h11Approaches) {
        this.routeCorridors.push({
          waypoints: [
            { x: spine11X, y: ha.y },
            { x: ha.xEnd, y: ha.y },
          ],
          width: 5, color: '#2196f3cc', label: ha.gate, routeType: 'gate-approach'
        })
        this.routeCorridors.push({
          waypoints: [
            { x: ha.xEnd, y: ha.y },
            { x: spine11X, y: ha.y },
          ],
          width: 5, color: '#2196f3cc', routeType: 'gate-approach'
        })
      }

      // T1主干道向上连接到出口(上100, 上101)
      const t1ExitApproaches = [
        { x: 74.90, gate: '上 100' },
        { x: 237.33, gate: '上 101' },
      ]
      for (const ea of t1ExitApproaches) {
        this.routeCorridors.push({
          waypoints: [
            { x: ea.x, y: t1MainY },
            { x: ea.x, y: 285 },
          ],
          width: 5, color: '#ff9800cc', label: ea.gate, routeType: 'exit-approach'
        })
        this.routeCorridors.push({
          waypoints: [
            { x: ea.x, y: 285 },
            { x: ea.x, y: t1MainY },
          ],
          width: 5, color: '#ff9800cc', routeType: 'exit-approach'
        })
      }

      // T2主干道向上连接到出口(上93, 上94)
      const t2ExitApproaches = [
        { x: 381.62, gate: '上 93' },
        { x: 544.05, gate: '上 94' },
      ]
      for (const ea of t2ExitApproaches) {
        this.routeCorridors.push({
          waypoints: [
            { x: ea.x, y: t2MainY },
            { x: ea.x, y: 248 },
          ],
          width: 5, color: '#ff9800cc', label: ea.gate, routeType: 'exit-approach'
        })
        this.routeCorridors.push({
          waypoints: [
            { x: ea.x, y: 248 },
            { x: ea.x, y: t2MainY },
          ],
          width: 5, color: '#ff9800cc', routeType: 'exit-approach'
        })
      }

      // 分类闸门：入口/出口/登机口
      this.entryGates = allGates.filter(g => g.gate_dir === 'entry')
      this.exitGates = allGates.filter(g => g.gate_dir === 'exit')
      this.boardingGates = allGates.filter(g => {
        if (g.type !== 'rect') return false
        // 所有矩形登机口都可以分配飞机（乘客廊道不覆盖的 gate 也允许停靠）
        return true
      })

      // 候机区中心（航站楼矩形中心）
      this.terminalCenters = {}
      for (const t of terminals) {
        this.terminalCenters[t.terminal_name] = {
          x: t.x + t.w / 2,
          y: t.y + t.h / 2,
          w: t.w,
          h: t.h,
        }
      }

      // 旅客由模拟引擎动态生成，初始为空
      this.passengers = []
    },

    startAnimation() {
      console.log('[DEBUG] startAnimation() called.')
      let frameCount = 0
      let tickCount = 0
      const animate = (timestamp) => {
        frameCount++
        // 非活动 tab（display:none）时只跳过绘制，模拟仍继续推进，切回后立即重绘
        const canvasEl = this.$refs.canvas
        const hidden = !!(canvasEl && canvasEl.getClientRects().length === 0)
        try {
          // 模拟引擎 tick（异步跳转期间跳过，由 jumpToTime 内部驱动）
          if (!hidden && this.simState.running && !this.simState.paused && !this._jumpInProgress) {
            const elapsed = timestamp - this.lastSimTick
            const tickInterval = Math.max(30, 200 / this.simState.speed)
            if (elapsed >= tickInterval) {
              this.lastSimTick = timestamp
              this._lastTickAt = performance.now()
              this._lastTickInterval = tickInterval
              tickCount++
              if (tickCount <= 5 || tickCount % 10 === 0) {
                console.log('[DEBUG] simTick #' + tickCount + ' at t=' + this.simState.currentTime.toFixed(1) + ' frame=' + frameCount + ' pax=' + this.passengers.length + ' planes=' + this.airplanes.length)
              }
              this.simTick()
            }
          }

          if (frameCount <= 3) {
            console.log('[DEBUG] draw frame #' + frameCount + ' canvas=' + (this.$refs.canvas ? (this.$refs.canvas.width + 'x' + this.$refs.canvas.height) : 'NULL') + ' running=' + this.simState.running + ' paused=' + this.simState.paused)
          }

          // 快进期间隔帧绘制：把主线程让给模拟推进，画面仍保持约 25–30 FPS 的更新
          const skipDraw = this._jumpInProgress && (frameCount & 1) === 0
          if (!hidden && !skipDraw) {
            this.drawAll()
            this.drawCorridors()
            if (this.congestion.enabled) {
              this.drawHeatmapOverlay()
            }
            this.drawGateOverlays()
            this.drawAirplanes()
            this.drawWaitingStats()
            this.drawPassengers()
          }
        } catch (e) {
          console.error('[TerminalLayout] animation error:', e)
        }
        this._animFrame = requestAnimationFrame(animate)
      }
      this.lastSimTick = performance.now()
      animate(performance.now())
    },

    // ========== 模拟引擎 ==========

    startSimulation() {
      console.log('[DEBUG] startSimulation() called. currentTime was', this.simState.currentTime)
      this.simState.running = true
      this.simState.paused = false
      this.spawnAccum = 0
      this.simState.currentTime = 0
      this.passengers = []
      this.airplanes = []
      this._deboardedAt = {}
      this._spawnedByFlight = {}
      this._dayCompleteEmitted = false
      this._manualIntervention = false
      this._keepAircraft = false
      this.generateSimFlights()
      console.log('[DEBUG] startSimulation() done. flights:', this.simFlights.length, 'gates:', this.boardingGates.length)
      for (const f of this.simFlights) {
        console.log('[DEBUG]   flight:', f.flightNo, 'type:', f.type, 'gate:', f.gateName, 'boardingStart:', f.boardingStart, 'scheduledDep:', f.scheduledDep, 'scheduledArr:', f.scheduledArr)
      }
    },

    // 切换到指定日期播放。保留画布上的飞机精灵（跨天继承）：
    // 前一天降落在登机口的飞机第二天直接复用；前一天起飞在途的飞机第二天降落时复用。
    setDate(date) {
      if (!MULTI_DAY_SCHEDULE[date] && !(this.paxflowSchedule && this.paxflowSchedule[date])) return false
      if (date === this.currentDate) return true
      this.currentDate = date
      this.simState.currentTime = 0
      this.passengers = []
      this.gateTransferPlanes = []
      this.totalInboundSpawned = 0
      this.arrivedFlightsDeboarded = new Set()
      this._deboardedAt = {}
      this._spawnedByFlight = {}
      this.runwayCooldown = { '跑道一': 0, '跑道二': 0 }
      this.spawnAccum = 0
      this._dayCompleteEmitted = false
      this._manualIntervention = false
      this._keepAircraft = true
      this.generateSimFlights()
      this.simState.running = true
      this.simState.paused = false
      console.log('[SIM] 切换到 ' + date + '，航班数=' + this.simFlights.length)
      return true
    },

    // 当前日期在调度列表中的索引（供父组件判断是否有下一天）
    dayIndex() {
      return SCHEDULE_DATES.indexOf(this.currentDate)
    },

    pauseSimulation() {
      this.simState.paused = true
    },

    resumeSimulation() {
      this.simState.paused = false
    },

    stopSimulation() {
      this.simState.running = false
      this.simState.paused = false
      this.simState.currentTime = 0
      this._manualIntervention = false
      this.passengers = []
      this.airplanes = []
      this.airplaneFleet = []
      this.flightSchedule = []
      this.gateTransferPlanes = []
      this.totalInboundSpawned = 0
      this.arrivedFlightsDeboarded = new Set()
      this._deboardedAt = {}
      this._spawnedByFlight = {}
    },

    setSpeed(speed) {
      this.simState.speed = Math.max(0.25, Math.min(10, speed))
    },

    // 显式设置模拟运行状态（不重置时间/旅客/飞机），供统一时钟对齐时使用
    setRunning(running) {
      this.simState.running = !!running
      if (running) this.simState.paused = false
    },

    // 手动拖动进度条跳转（支持前进/回退）：
    // 前进 = 从当前时刻逐 tick 快进；回退 = 重置模拟状态后重新快进到目标时刻，
    // 期间粒子/飞机动画正常演化，保证跳转后画面状态与时刻一致。
    // 手动干预后禁止自动切天（见 checkSimulationComplete），避免拖动预览被切天打断。
    // 异步分批次执行（每批 80 ticks 后让出主线程渲染一帧），避免同步阻塞导致画面冻结。
    async jumpToTime(targetMin) {
      const total = this.simTotalMinutes || 1020
      const target = Math.max(0, Math.min(Math.round(targetMin), total))
      const savedSpeed = this.simState.speed
      const savedRunning = this.simState.running
      const savedPaused = this.simState.paused
      // 快进时用较粗的时间步长，避免 tick 数翻倍把主线程拖慢
      const savedTimePerTick = this.simState.timePerTick
      const beforeTime = this.simState.currentTime
      // 手动拖动过进度条：当天播放完成后不自动切天，画面定格等待用户操作
      this._manualIntervention = true
      this._jumpInProgress = true

      try {
        // 目标时刻早于当前：先重置模拟（旅客/飞机/航班状态重新初始化），再重新快进
        if (target < this.simState.currentTime) {
          console.log('[JUMP] 回退重置: ' + beforeTime.toFixed(1) + ' → 0, 航班=' + this.simFlights.length)
          this.simState.currentTime = 0
          this.passengers = []
          this.airplanes = []
          this.gateTransferPlanes = []
          this.totalInboundSpawned = 0
          this.arrivedFlightsDeboarded = new Set()
          this._deboardedAt = {}
          this._spawnedByFlight = {}
          this.runwayCooldown = { '跑道一': 0, '跑道二': 0 }
          if (typeof this.spawnAccum !== 'undefined') this.spawnAccum = 0
          this._dayCompleteEmitted = false
          this._keepAircraft = true
          try {
            this.generateSimFlights()
          } catch (ge) {
            console.error('[JUMP] generateSimFlights 异常:', ge)
          }
        }

        // 快进期间用标准速度，避免倍速导致动画位移失真
        this.simState.speed = 1
        this.simState.timePerTick = 0.2
        this.simState.running = true
        this.simState.paused = false

        // 异步分批次快进：每批最多 TICKS_PER_BATCH 次 simTick()，
        // 然后 await requestAnimationFrame 让出主线程执行渲染，
        // 避免同步 while 循环长时间阻塞导致画面冻结（飞机"卡住"）。
        let guard = 0
        let tickErrors = 0
        while (this.simState.currentTime < target && guard < 80000) {
          // 按时间预算分片：每批最多占用 20ms 主线程，保证快进期间仍能流畅出帧
          const deadline = performance.now() + 20
          while (
            this.simState.currentTime < target &&
            guard < 80000 &&
            performance.now() < deadline
          ) {
            try {
              this.simTick()
            } catch (te) {
              tickErrors++
              if (tickErrors <= 3) {
                console.error('[JUMP] simTick #' + guard + ' 异常 (t=' + this.simState.currentTime.toFixed(1) + '):', te)
              }
            }
            guard++
          }
          // 每批次后让浏览器渲染一帧
          if (this.simState.currentTime < target) {
            await new Promise(r => requestAnimationFrame(r))
          }
        }
        if (tickErrors > 0) {
          console.warn('[JUMP] 快进过程中 ' + tickErrors + ' 次 simTick 异常')
        }
        console.log('[JUMP] 跳转完成: ' + beforeTime.toFixed(1) + ' → ' + this.simState.currentTime.toFixed(1) + '  (' + guard + ' ticks, 目标=' + target + ')')
      } catch (e) {
        console.error('[JUMP] jumpToTime 顶层异常:', e)
      } finally {
        this._jumpInProgress = false
        if (this.simState.currentTime < target) {
          console.warn('[JUMP] 兜底跳转: 未达目标 ' + target + '，当前=' + this.simState.currentTime.toFixed(1) + '，直接设时')
          this.simState.currentTime = target
        }
        this.simState.speed = savedSpeed
        this.simState.timePerTick = savedTimePerTick
        this.simState.running = savedRunning
        this.simState.paused = savedPaused
        console.log('[JUMP] 状态恢复: running=' + this.simState.running + ' paused=' + this.simState.paused + ' currentTime=' + this.simState.currentTime.toFixed(1))
      }
    },

    simTick() {
      const t = this.simState.timePerTick
      this.simState.currentTime += t

      // 递减跑道冷却
      for (const rw of ['跑道一', '跑道二']) {
        if (this.runwayCooldown[rw] > 0) this.runwayCooldown[rw]--
      }

      // 1. 更新航班状态
      this.updateFlightStatuses()

      // 3. 刚进入登机状态的航班：释放候机旅客到走廊 + 生成飞机精灵
      this.spawnAirplanesForBoarding()
      this.spawnArrivalPlanes()
      this.boardWaitingPassengers()

      // 3. 生成新旅客（进入候机区等待）
      this.spawnPassengers(t)

      // 4. 推进在途旅客移动
      this.advancePassengers()

      // 5. 清理到达终点的旅客
      this.cleanupPassengers()

      // 6. 计算拥堵度
      if (this.congestion.enabled) {
        this.calculateCongestion()
      }

      // 7. 更新飞机动画
      this.updateAirplanes()

      // 8. 航班已 departure → 飞机推出滑行
      this.checkBoardingComplete()

      // 9. 所有预定航班完成后自动停止（播放一次即停，不再空转循环）
      this.checkSimulationComplete()
    },

    generateSimFlights() {
      // 数据源：优先后端 /api/paxflow/schedule 拉取的真实航班调度（含生成航班的跑道排班与登机口分配），
      // 拉取失败/未覆盖当天时回退到静态多日调度快照
      const dayData = (this.paxflowSchedule && this.paxflowSchedule[this.currentDate]) || MULTI_DAY_SCHEDULE[this.currentDate] || []
      if (!dayData.length) {
        console.warn('[SIM] ' + this.currentDate + ' 无航班数据')
        this.flightSchedule = []
        this.simFlights = []
        this.airplaneFleet = []
        this.airplanes = []
        return
      }
      this.flightSchedule = dayData.map(f => ({ ...f }))

      // 重置乘客编号清单/终态日志，并从后端拉取当天乘客编号（异步，投放粒子时即可用）
      this._paxManifest = {}
      this._paxLog = {}
      this.loadPaxManifests(this.flightSchedule.map(f => f.flightNo))

      // 初始化 simFlights（与现有逻辑兼容）。
      // 天气中断：取消航班直接置 cancelled 状态（不生成粒子/飞机）；
      // 延误航班的时间字段已由后端整体后移，这里透传 delayMinutes/reason 供航班动态展示。
      this.simFlights = this.flightSchedule.map(f => ({
        flightId: f.flightId,
        flightNo: f.flightNo,
        tailNo: f.tailNo,
        gateName: f.gateName,
        terminal: f.terminal,
        type: f.type,
        cancelled: !!f.cancelled,
        status: f.cancelled ? 'cancelled' : 'scheduled',
        delayMinutes: f.delayMinutes || 0,
        reason: f.reason || '',
        disruptionType: f.disruptionType || '',
        paxTotal: f.paxTotal,
        runway: f.runway,
        paxBoarded: 0,
        ...(f.type === 'departure'
          ? { scheduledDep: f.boardingEnd, boardingStart: f.boardingStart, boardingEnd: f.boardingEnd, takeoffTime: f.takeoffTime, rwStart: f.rwStart, rwEnd: f.rwEnd }
          : { scheduledArr: f.scheduledArr, rwStart: f.rwStart, rwEnd: f.rwEnd }
        ),
      }))
      this.simFlights.sort((a, b) =>
        (a.scheduledDep || a.scheduledArr || 0) - (b.scheduledDep || b.scheduledArr || 0)
      )

      // 初始化飞机机队：切天时保留过夜/在途飞机（跨天复用），重新开始则清空重建
      const seenTails = new Set()
      const mergedFleet = []
      if (this._keepAircraft && this.airplaneFleet) {
        for (const fp of this.airplaneFleet) {
          seenTails.add(fp.tailNo)
          mergedFleet.push(fp)
        }
      }
      for (const f of this.flightSchedule) {
        if (!seenTails.has(f.tailNo)) {
          seenTails.add(f.tailNo)
          mergedFleet.push({
            tailNo: f.tailNo,
            type: 'A320',
            status: 'IDLE',
            currentGate: null,
            currentFlightNo: null,
          })
        }
      }
      this.airplaneFleet = mergedFleet

      // 预加载始发航班飞机到登机口（切天时同时把过夜飞机重定位到当天登机口）
      this.preloadDeparturePlanes()
    },

    // 从后端 /api/paxflow/schedule 拉取真实航班调度（基于最近历史记录中的生成航班，
    // 含跑道排班与登机口分配，最早日期可能是生成的首日如 2020-11-29）。
    // 成功后优先使用后端数据；若当前日期不在后端日期中，自动切换到最早日期并重建模拟。
    async loadPaxflowSchedule() {
      try {
        const data = await api.getPaxflowSchedule(true)
        if (data && data.schedule) {
          this.paxflowSchedule = data.schedule
          this.paxflowDates = data.dates || []
          const totalFlights = Object.keys(this.paxflowSchedule)
            .reduce((n, d) => n + this.paxflowSchedule[d].length, 0)
          console.log('[SIM] 已加载后端航班调度: ' + this.paxflowDates.length + ' 天，' +
            totalFlights + ' 航班，最早 ' + (this.paxflowDates[0] || '-'))
          // 初次从静态快照切到后端调度：始终从后端最早日期（如 2020-11-29）开始，
          // 避免沿用静态快照默认日期（11-30）而加载了错误的大量航班
          if (this.paxflowDates.length) {
            this._applyBackendDate(this.paxflowDates[0])
          }
        }
      } catch (e) {
        console.warn('[SIM] 后端调度拉取失败，使用静态数据:', e.message)
      }
    },

    // 用后端日期重建当天模拟（与 setDate 语义相同，但不做日期相等的提前返回；
    // 初次从静态快照切到后端调度时清空旧精灵，避免残留）
    _applyBackendDate(date) {
      this.currentDate = date
      this.simState.currentTime = 0
      this.passengers = []
      this.airplanes = []
      this.airplaneFleet = []
      this.gateTransferPlanes = []
      this.totalInboundSpawned = 0
      this.arrivedFlightsDeboarded = new Set()
      this._deboardedAt = {}
      this._spawnedByFlight = {}
      this.runwayCooldown = { '跑道一': 0, '跑道二': 0 }
      this.spawnAccum = 0
      this._dayCompleteEmitted = false
      this._manualIntervention = false
      this._keepAircraft = false
      this.generateSimFlights()
      this.simState.running = true
      this.simState.paused = false
      console.log('[SIM] 后端调度重建 ' + date + '，航班数=' + this.simFlights.length)
    },

    // 从后端 /api/paxflow/manifests 拉取当天航班的真实乘客编号清单。
    // 后端生成的旅客池中有对应 flight_no 时返回真实 Pax-MMDD-XXXXX 编号；
    // 匹配不到（未生成数据/航班号不同）则返回空，粒子投放时用 _resolvePaxId 生成兜底编号。
    async loadPaxManifests(flightNos) {
      try {
        const data = await api.getPaxflowManifests({
          date: this.currentDate, flights: flightNos,
        })
        if (data && data.manifests) {
          const got = {}
          for (const m of data.manifests) {
            if (m.pax_ids && m.pax_ids.length) got[m.flight_no] = m.pax_ids
          }
          this._paxManifest = got
          const hitCount = Object.keys(got).length
          console.log('[PAX] 乘客清单已拉取: ' + this.currentDate +
            ' 匹配航班=' + hitCount + '/' + flightNos.length)
        }
      } catch (e) {
        console.warn('[PAX] 乘客清单拉取失败，使用前端兜底编号:', e.message)
      }
    },

    // 解析乘客编号：优先用后端清单中的真实编号，缺省时按后端规则生成兜底编号。
    // seq 为航班内序号（1 起），与后端清单按下标对应（真实乘客顺序）。
    _resolvePaxId(flightNo, seq) {
      const ids = this._paxManifest[flightNo]
      if (ids && ids.length) {
        return ids[Math.min(seq - 1, ids.length - 1)]
      }
      return this._fallbackPaxId(seq)
    },

    // 兜底编号：格式与后端一致 Pax-MMDD-XXXXX（航班内唯一，序号对齐航班实际人数）
    _fallbackPaxId(seq) {
      const parts = this.currentDate.split('-')
      const mmdd = (parts[1] || '11') + (parts[2] || '30')
      return 'Pax-' + mmdd + '-' + String(seq).padStart(5, '0')
    },

    // 查询某航班某乘客粒子的状态。paxNo 支持两种输入：
    //   1) 完整乘客编号（Pax-1130-00001）
    //   2) 航班内序号（1 ~ paxTotal）
    // 返回 { found, status, statusText, ... }，status ∈ not_entered/boarding/deboarding/boarded/exited
    getPaxStatus(flightNo, paxNo) {
      const raw = String(paxNo == null ? '' : paxNo).trim()
      const isNumeric = /^\d+$/.test(raw)
      const flight = this.simFlights.find(f => f.flightNo === flightNo)
      const flightTotal = flight ? (flight.paxTotal || 0) : 0

      // 1) 活跃粒子查找（乘客正在航站楼内）
      const active = this.passengers.find(p => {
        if (p.flightId !== flightNo) return false
        if (isNumeric) return p.paxSeq === Number(raw)
        return p.paxId === raw
      })
      if (active) {
        if (active.type === 'inbound') {
          // 出发航班旅客：进站/候机/走向登机口 = 登机中
          return {
            found: true,
            paxId: active.paxId,
            paxSeq: active.paxSeq,
            status: 'boarding',
            statusText: '登机中',
            phase: active.status === 'waiting' ? '候机等待' : (active.status === 'walking' ? '前往登机口' : '进站中'),
            terminal: active.terminal,
            gate: active.targetGate,
            active: true,
          }
        }
        // 到达航班旅客：正从登机口走向出口 = 已下机（出站中）
        return {
          found: true,
          paxId: active.paxId,
          paxSeq: active.paxSeq,
          status: 'deboarding',
          statusText: '已下机',
          phase: '出站中',
          terminal: active.terminal,
          gate: active.targetGate || '',
          active: true,
        }
      }

      // 2) 终态日志（粒子已登机/已出站并被清理）
      const findInLog = (matcher) => {
        for (const key in this._paxLog) {
          const log = this._paxLog[key]
          if (log.flightNo === flightNo && matcher(log)) return log
        }
        return null
      }
      const log = isNumeric
        ? findInLog(l => l.paxSeq === Number(raw))
        : this._paxLog[flightNo + '|' + raw]
      if (log) {
        const isBoarded = log.status === 'boarded'
        return {
          found: true,
          paxId: log.paxId,
          paxSeq: log.paxSeq,
          status: log.status,
          statusText: isBoarded ? '已登机' : '已出站',
          terminal: log.terminal,
          at: log.at,
          active: false,
        }
      }

      // 3) 未进站：航班存在但该乘客粒子尚未投放（或航班人数不足）
      if (!flight) {
        return { found: false, status: 'unknown', statusText: '航班不存在', reason: 'flight_not_found' }
      }
      if (isNumeric && Number(raw) > flightTotal) {
        return { found: false, status: 'unknown', statusText: '乘客号超出航班人数', reason: 'out_of_range', total: flightTotal }
      }
      return {
        found: false,
        status: 'not_entered',
        statusText: '未进站',
        total: flightTotal,
        terminal: flight.terminal,
      }
    },

    // 预加载所有机队飞机到画布（切天时对已有精灵做重定位复用，实现跨天飞机继承）
    preloadDeparturePlanes() {
      for (const flight of this.flightSchedule) {
        // 取消航班：不预加载/不生成飞机（前端灰显删除线，无起降效果）
        if (flight.cancelled) continue
        const fleetPlane = this.airplaneFleet.find(p => p.tailNo === flight.tailNo)
        if (!fleetPlane) continue

        // 判断该飞机的当天首航班（只对首航班做精灵加载/重定位，后续航班复用同一精灵）
        const isFirstFlightOfTail = !this.flightSchedule.some(
          f => !f.cancelled && f.tailNo === flight.tailNo && ((f.boardingStart || f.scheduledArr || 0) < (flight.boardingStart || flight.scheduledArr || 0))
        )
        if (!isFirstFlightOfTail) continue

        const channelName = TAXI_CHANNELS.gateToChannel[flight.gateName]
        if (!channelName) continue
        const end = TAXI_CHANNELS.channelEndpoints[channelName]
        const isRunway1 = end.runway === '跑道一'
        const runwayEndX = isRunway1 ? 620 : 1210
        const runwayY = isRunway1 ? 534.6 : 318.6

        const plane = this.airplanes.find(p => p.tailNo === flight.tailNo)

        if (flight.type === 'departure') {
          // 始发/过夜出发航班：飞机直接停在登机口停机位等待上客
          //（11-30 是有记录的第一天，之后每天使用前一天降落的飞机，均无需从跑道端进场滑行）
          const gate = (this.layoutData ? this.layoutData.gates || [] : [])
            .find(g => g.name === flight.gateName)
          if (!gate) continue
          const taxiData = this.generateTaxiPath(flight.gateName)
          if (!taxiData || !taxiData.path || !taxiData.path.length) continue
          const start = taxiData.path[0]  // 登机口侧方停机位 = 滑行路径起点

          if (plane) {
            // 切天复用：把过夜/前序停在登机口的飞机重定位到当天登机口
            plane.flightNo = flight.flightNo
            plane.type = 'departure'
            plane.status = 'PRELOADED_AT_GATE'
            plane.x = start.x
            plane.y = start.y
            plane.angle = getPathAngle(taxiData.path, 0)
            plane.scale = 1.0
            plane.alpha = 1.0
            plane.taxiPath = []
            plane.pathProgress = 0
            plane.pathSpeed = TAXI_SPEED
            plane.assignedRunway = taxiData.end.runway
            plane.readyToTaxi = false
            plane.channelName = taxiData.channelName
            plane.gateName = flight.gateName
            plane._entering = false
            console.log('[FLEET] 过夜复用 ' + flight.tailNo + ' → 停靠 ' + flight.gateName + ' 等待上客 (' + flight.flightNo + ')')
          } else {
            this.airplanes.push({
              id: 'plane_' + flight.tailNo,
              flightNo: flight.flightNo,
              tailNo: flight.tailNo,
              type: 'departure',
              status: 'PRELOADED_AT_GATE',  // 已停靠登机口，等待登机
              x: start.x, y: start.y,
              angle: getPathAngle(taxiData.path, 0),
              scale: 1.0, alpha: 1.0,
              taxiPath: [], pathProgress: 0, pathSpeed: TAXI_SPEED,
              assignedRunway: taxiData.end.runway,
              readyToTaxi: false,
              channelName: taxiData.channelName,
              gateName: flight.gateName,
            })
            console.log('[FLEET] 预加载 ' + flight.tailNo + ' → 停靠 ' + flight.gateName + ' 等待上客 (' + flight.flightNo + ')')
          }
          fleetPlane.status = 'PRELOADED'
          fleetPlane.currentGate = flight.gateName
          fleetPlane.currentFlightNo = flight.flightNo
        } else {
          // 到达首航班：预加载在跑道远端等待，到达时间到后再开始降落
          if (plane) {
            if (plane.status === 'IN_FLIGHT') {
              // 空中飞行中（前一天起飞）：保留，等待降落时由 spawnArrivalPlanes 复用
              plane.gateName = flight.gateName
              plane.flightNo = flight.flightNo
              plane.assignedRunway = end.runway
              plane.channelName = channelName
              console.log('[FLEET] 在途复用 ' + flight.tailNo + ' → 等待降落 (' + flight.flightNo + ')')
            } else {
              // 已在地面（过夜停靠）：重置为等待降落，不可见，到达时间才出现
              plane.status = 'AWAITING_ARRIVAL'
              plane.flightNo = flight.flightNo
              plane.type = 'arrival'
              plane.x = runwayEndX
              plane.y = runwayY
              plane.angle = Math.PI
              plane.scale = 1.0
              plane.alpha = 0
              plane.taxiPath = []
              plane.pathProgress = 0
              plane.assignedRunway = end.runway
              plane.channelName = channelName
              plane.gateName = flight.gateName
              plane.runwayEntryX = end.x
              console.log('[FLEET] 地面复用 ' + flight.tailNo + ' → 等待降落 (' + flight.flightNo + ')')
            }
          } else {
            this.airplanes.push({
              id: 'plane_' + flight.tailNo,
              flightNo: flight.flightNo,
              tailNo: flight.tailNo,
              type: 'arrival',
              status: 'AWAITING_ARRIVAL',
              x: runwayEndX, y: runwayY,
              angle: Math.PI,
              scale: 1.0, alpha: 0,
              taxiPath: [],
              pathProgress: 0, pathSpeed: TAXI_SPEED,
              assignedRunway: end.runway,
              readyToTaxi: false,
              channelName: channelName,
              gateName: flight.gateName,
              runwayEntryX: end.x,
            })
            console.log('[FLEET] 预加载 ' + flight.tailNo + ' → 等待降落 (' + flight.flightNo + ' → ' + flight.gateName + ')')
          }
          fleetPlane.status = 'AWAITING_ARRIVAL'
          fleetPlane.currentGate = null
          fleetPlane.currentFlightNo = flight.flightNo
        }
      }
    },

    updateFlightStatuses() {
      const ct = this.simState.currentTime
      for (const f of this.simFlights) {
        if (f.type === 'departure' && f.status === 'scheduled' && ct >= f.boardingStart) {
          f.status = 'boarding'
          // [DEBUG] 记录转入登机的航班 + 该机尾号此刻的飞机状态
          const ap = this.airplanes.find(p => p.tailNo === f.tailNo)
          console.log('[FLEET][DEBUG] ' + f.flightNo + ' scheduled → boarding @t=' + ct.toFixed(1) +
            ' (tail=' + f.tailNo + ' gate=' + f.gateName + ')' +
            ' | 此刻飞机: ' + (ap ? 'status=' + ap.status + ' flightNo=' + ap.flightNo + ' gateName=' + ap.gateName +
              ' @(' + ap.x.toFixed(0) + ',' + ap.y.toFixed(0) + ')' : '画布上无此飞机'))
        }
        // 登机完成不再由时间驱动，改为 checkBoardingComplete 根据 paxBoarded 判断
        if (f.type === 'arrival' && f.status === 'scheduled' && ct >= f.scheduledArr) {
          console.log('[FLEET] ' + f.flightNo + ' arrival due (tail=' + f.tailNo + ')')
        }
      }
    },

    spawnPassengers(dt) {
      // === 旅客只能在走廊上，候机区在主干道 ===
      this.spawnInboundForFlights()
      this.spawnOutboundForArrivals()
    },

    // 按航班投放入港旅客（总量 = 所有出发航班 paxTotal 之和）
    spawnInboundForFlights() {
      // 取消航班不生成旅客粒子（前端灰显，无登机/出站效果）
      const departureFlights = this.simFlights.filter(f => f.type === 'departure' && !f.cancelled)
      const totalNeeded = departureFlights.reduce((sum, f) => sum + f.paxTotal, 0)
      if (this.totalInboundSpawned >= totalNeeded) return

      // 只投放"该航班的飞机已停在自家登机口"的航班旅客：
      // 避免所有航班粒子从 t=0 就堆在主干道等待（如 CA1003 要等很久才轮到登机，
      // 其粒子会一直以"残留等待群"的形式停在原地，看起来像没有随目标航班转移）。
      const imminentFlights = departureFlights.filter(f => {
        if (f.status === 'departed') return false
        // 临近登机（提前 30 分钟）才开始投放该航班旅客，
        // 避免所有航班粒子整场都堆在等待区、看不出先后时序
        if (this.simState.currentTime < (f.boardingStart || 0) - 30) return false
        return this.airplanes.some(p =>
          p.tailNo === f.tailNo &&
          p.flightNo === f.flightNo &&
          p.gateName === f.gateName &&
          (p.status === 'AT_GATE' || p.status === 'PRELOADED_AT_GATE'))
      })
      if (imminentFlights.length === 0) return

      // 按"已投放计数"而非"画布现存粒子数"计算缺口：
      // 已登机完成并被清理的粒子不占画布，若用现存数统计，已登机的航班会
      // 被反复补投，挤占其他航班（如 MU3002）的投放额度，导致其永远缺几名旅客。
      const needsMore = []
      for (const f of imminentFlights) {
        const alreadySpawned = this._spawnedByFlight[f.flightNo] || 0
        const need = f.paxTotal - alreadySpawned
        if (need > 0) needsMore.push({ flight: f, need })
      }
      if (needsMore.length === 0) return

      const batchSize = Math.min(5, totalNeeded - this.totalInboundSpawned)

      for (let i = 0; i < batchSize; i++) {
        const item = needsMore[Math.floor(Math.random() * needsMore.length)]
        const f = item.flight
        const isT1 = f.terminal === 'T1'
        const terminalKey = isT1 ? 'T1' : 'T2'

        const openEntries = this.entryGates.filter(g => {
          if (!this.isGateOpen(g.name)) return false
          return isT1 ? g.x < 300 : g.x >= 300
        })
        if (openEntries.length === 0) return
        const entry = openEntries[Math.floor(Math.random() * openEntries.length)]

        const entryCorridorIdx = this.findEntryCorridor(entry)
        if (entryCorridorIdx < 0) return

        const trunkIdx = this.trunkCorridorIdx[terminalKey]
        const trunkCorridor = trunkIdx >= 0 ? this.routeCorridors[trunkIdx] : null
        if (!trunkCorridor) return

        const waitProgress = 0.3 + Math.random() * 0.6
        const waitPos = interpolatePath(trunkCorridor.waypoints, waitProgress)

        // 对接乘客编号：优先用后端清单的真实编号，缺省时按规则生成兜底编号
        const paxSeq = (this._spawnedByFlight[f.flightNo] || 0) + 1
        const paxId = this._resolvePaxId(f.flightNo, paxSeq)

        this.passengers.push({
          id: 'pax_' + (this.paxCounter++),
          paxId: paxId,
          paxSeq: paxSeq,
          type: 'inbound',
          status: 'entering',
          corridorIdx: entryCorridorIdx,
          progress: 0,
          speed: 0.012 + Math.random() * 0.012,
          laneOffset: (Math.random() - 0.5) * 1.2,
          color: isT1 ? '#4caf50cc' : '#2196f3cc',
          flightId: f.flightNo,
          targetGate: f.gateName,
          terminal: f.terminal,
          waitCorridorIdx: trunkIdx,
          waitProgress: waitProgress,
          waitX: waitPos.x,
          waitY: waitPos.y,
        })
        this.totalInboundSpawned++
        this._spawnedByFlight[f.flightNo] = (this._spawnedByFlight[f.flightNo] || 0) + 1

        item.need--
        if (item.need <= 0) {
          const idx = needsMore.indexOf(item)
          if (idx >= 0) needsMore.splice(idx, 1)
          if (needsMore.length === 0) break
        }
      }
    },

    // 到达航班下客：从登机口沿出口走廊走到出口门消失
    spawnOutboundForArrivals() {
      const arrivedFlights = this.simFlights.filter(f =>
        f.type === 'arrival' && f.status === 'arrived' &&
        !this.arrivedFlightsDeboarded.has(f.flightNo)
      )
      for (const f of arrivedFlights) {
        const gate = this.boardingGates.find(g => g.name === f.gateName)
        if (!gate || !this.isGateOpen(gate.name)) continue

        // 4个出站口候选：用现有走廊拼接路径（in走廊反向 + 主干道 + link + exit-approach），含路径长度
        const candidates = this.buildExitCandidates(gate)
        if (candidates.length === 0) continue

        const remaining = f.paxTotal - (f._deboardedCount || 0)
        const batchSize = Math.min(5, remaining)
        for (let i = 0; i < batchSize; i++) {
          // 每个旅客独立按距离加权选择出口：越近越可能，越远越少
          const corridor = this.pickWeightedExit(candidates)
          // 对接乘客编号：到达航班乘客与出发航班同源，按航班内序号取编号
          const paxSeq = (f._deboardedCount || 0) + 1
          const paxId = this._resolvePaxId(f.flightNo, paxSeq)
          this.passengers.push({
            id: 'pax_' + (this.paxCounter++),
            paxId: paxId,
            paxSeq: paxSeq,
            type: 'outbound',
            status: 'walking',
            corridorIdx: corridor.idx,
            waypoints: corridor.waypoints,  // 拼接的现有走廊路径（登机口→出口门）
            progress: 0.02 + Math.random() * 0.05,
            speed: 0.008 + Math.random() * 0.012,
            laneOffset: (Math.random() - 0.5) * 1.2,
            color: '#ff9800cc',
            flightId: f.flightNo,
            terminal: f.terminal,
          })
          f._deboardedCount = (f._deboardedCount || 0) + 1
        }

        if (f._deboardedCount >= f.paxTotal) {
          this.arrivedFlightsDeboarded.add(f.flightNo)
          this._deboardedAt[f.flightNo] = this.simState.currentTime
          console.log('[PAX] ' + f.flightNo + ' 下客完成，共' + f.paxTotal + '人 @t=' + this.simState.currentTime.toFixed(1))
        }
      }
    },

    // 该登机口到全部出站口（含跨航站楼）的候选路径，全部由现有走廊点拼接
    buildExitCandidates(gate) {
      const list = []
      for (const ex of this.exitGates) {
        if (!this.isGateOpen(ex.name)) continue
        const wps = this.buildDeboardingPath(gate, ex)
        if (!wps || wps.length < 2) continue
        list.push({ idx: 0, waypoints: wps, dist: this.corridorLength(wps) })
      }
      return list
    },

    // 拼接现有走廊构建 登机口→出口门 的移动路径：
    //   in 走廊反向（登机口→脊柱→主干） + 主干道水平 + （跨航站楼时 link 走廊）+ exit-approach（主干→出口）
    buildDeboardingPath(gate, exitGate) {
      const spines = this._spines
      if (!spines) return null
      const ref = (gate.attach || {}).ref || ''
      const isT1 = ref.includes('矩形 5') || ref.includes('矩形 6') || ref.includes('矩形 7') ||
                   ref.includes('矩形 8') || ref.includes('矩形 40') || ref.includes('航站楼1')
      const mainY = isT1 ? spines.t1MainY : spines.t2MainY
      const otherMainY = isT1 ? spines.t2MainY : spines.t1MainY

      // 1. 登机口 → 脊柱 → 主干（该登机口的 in 走廊 waypoints 反向取前3点）
      const inIdx = this.findInCorridorForGate(gate)
      if (inIdx < 0) return null
      const iw = this.routeCorridors[inIdx].waypoints
      const wps = [
        { x: iw[4].x, y: iw[4].y },   // 登机口
        { x: iw[3].x, y: iw[3].y },   // 脊柱·登机口高度
        { x: iw[2].x, y: iw[2].y },   // 脊柱·主干高度
      ]

      // 2. 出口侧：exit-approach（主干→出口门上方）+ 出口门中心（完整走出门）
      const app = this.findExitApproach(exitGate.name)
      const appX = app ? app.waypoints[0].x : exitGate.x + (exitGate.w || 0) / 2
      const exitCx = exitGate.x + (exitGate.w || 0) / 2
      const exitCy = exitGate.y + (exitGate.h || 0) / 2

      const exitIsT1 = exitGate.x < 300
      if (exitIsT1 === isT1) {
        // 同航站楼：沿主干道水平到出口走廊 x → 竖直到出口门高度 → 水平走到出口门中心
        wps.push({ x: appX, y: mainY })
        wps.push({ x: appX, y: exitCy })
        wps.push({ x: exitCx, y: exitCy })
      } else {
        // 跨航站楼：沿本航站楼主干到 link 走廊 → 对方主干 → 出口走廊 → 出口门中心
        const link = this.findLinkFrom(isT1)
        if (!link) return null
        const lw = link.waypoints
        // link 走廊：起点在本航站楼主干中心（t1cx/t2cx），终点在对方主干中心
        const linkStart = lw[0]
        wps.push({ x: linkStart.x, y: mainY })   // 本航站楼主干水平到 link 起点
        for (const pt of lw) {
          wps.push({ x: pt.x, y: pt.y })          // 沿 link 走廊
        }
        wps.push({ x: appX, y: otherMainY })      // 对方主干水平到出口走廊 x
        wps.push({ x: appX, y: exitCy })          // 竖直到出口门高度
        wps.push({ x: exitCx, y: exitCy })        // 水平到出口门中心
      }
      return wps
    },

    // 查找该登机口的 in 走廊（按 gateName 精确匹配，再校验终点距离）
    // 注意：相邻登机口间距可能 <20，仅凭距离会误匹配到隔壁登机口的走廊，
    // 导致下客粒子从错误登机口涌出，因此必须要求 corridor.gateName === gate.name
    findInCorridorForGate(gate) {
      const gCx = gate.x + gate.w / 2
      const gCy = gate.y + gate.h / 2
      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (!rc.waypoints || rc.waypoints.length !== 5) continue
        if (!rc.routeType || !rc.routeType.includes('in')) continue
        if (rc.gateName !== gate.name) continue
        const last = rc.waypoints[rc.waypoints.length - 1]
        const d = Math.abs(last.x - gCx) + Math.abs(last.y - gCy)
        if (d < 20) return i
      }
      return -1
    },

    // 查找主干道→出口门 的 exit-approach 走廊（label 为出口名，name 形如"箭头: 上 93"）
    findExitApproach(exitName) {
      for (const rc of this.routeCorridors) {
        if (rc.routeType === 'exit-approach' && rc.label && rc.waypoints && rc.waypoints.length === 2) {
          if (exitName.includes(rc.label) || rc.label.includes(exitName)) return rc
        }
      }
      return null
    },

    // 查找"本航站楼→对方航站楼"方向的 link 走廊
    findLinkFrom(isT1) {
      for (const rc of this.routeCorridors) {
        if (rc.routeType !== 'link' || !rc.waypoints || rc.waypoints.length < 2) continue
        const start = rc.waypoints[0]
        if (isT1 && start.x < 300) return rc   // T1主干 → T2
        if (!isT1 && start.x > 400) return rc  // T2主干 → T1
      }
      return null
    },

    // 走廊路径总长度（登机口→出口的行走距离）
    corridorLength(waypoints) {
      let len = 0
      for (let i = 1; i < waypoints.length; i++) {
        len += Math.hypot(waypoints[i].x - waypoints[i - 1].x, waypoints[i].y - waypoints[i - 1].y)
      }
      return len
    },

    // 按距离递减加权随机选择出口：权重 = 1/(dist+50)，越远概率越低
    pickWeightedExit(candidates) {
      const weights = candidates.map(c => 1 / (c.dist + 50))
      const total = weights.reduce((a, b) => a + b, 0)
      let r = Math.random() * total
      for (let i = 0; i < candidates.length; i++) {
        r -= weights[i]
        if (r <= 0) return candidates[i]
      }
      return candidates[candidates.length - 1]
    },

    // 将候机旅客送入走廊前往对应登机口
    boardWaitingPassengers() {
      const boardingFlights = this.simFlights.filter(f => f.status === 'boarding')

      for (const flight of boardingFlights) {
        // 检查飞机是否已经到达登机口（AT_GATE 或 PRELOADED_AT_GATE）
        const plane = this.airplanes.find(p =>
          p.tailNo === flight.tailNo &&
          (p.status === 'AT_GATE' || p.status === 'PRELOADED_AT_GATE') &&
          p.type === 'departure'
        )
        if (!plane) continue  // 飞机尚未到位，不释放旅客

        // [DEBUG][修复] 关键校验：粒子只应在本航班自己的飞机停在自家登机口时释放。
        // 此前只按 tailNo 匹配，CA1003(t=48入boarding) 会误匹配到仍在83上客/待推的
        // B-1234（CA1001），导致 CA1003 粒子涌向没有飞机的 85 登机口。
        // 现在：飞机正在执行的航班号 + 所在登机口 必须与目标航班一致，否则禁止释放。
        if (plane.flightNo !== flight.flightNo || plane.gateName !== flight.gateName) {
          if (!flight._warnedMismatchPlane) {
            flight._warnedMismatchPlane = true
            console.warn('[PAX][DEBUG][WARN] ' + flight.flightNo + ' 释放粒子但飞机不匹配，已拦截！' +
              ' 期望 flightNo=' + flight.flightNo + ' gate=' + flight.gateName +
              ' | 实际飞机 flightNo=' + plane.flightNo + ' gateName=' + plane.gateName +
              ' status=' + plane.status + ' @(' + plane.x.toFixed(0) + ',' + plane.y.toFixed(0) + ')' +
              ' @t=' + this.simState.currentTime.toFixed(1))
          }
          continue  // 禁止释放：飞机在别的登机口执行别的航班
        }

        const gate = this.boardingGates.find(g => g.name === flight.gateName)
        if (!gate || !this.isGateOpen(gate.name)) continue

        const waiting = this.passengers.filter(p =>
          p.status === 'waiting' &&
          p.flightId === flight.flightNo &&
          p.terminal === flight.terminal)
        if (waiting.length === 0) continue

        // 查找已有的走廊：终点靠近该登机口
        const app = this.findExistingApproachCorridor(gate)
        if (!app) continue

        // [DEBUG] 每次释放记录：哪个航班、释放几人、目标登机口、飞机实际位置
        console.log('[PAX][DEBUG] ' + flight.flightNo + ' 释放粒子 → ' + gate.name +
          ' (飞机flightNo=' + plane.flightNo + ' 飞机gate=' + plane.gateName +
          ' 位置=(' + plane.x.toFixed(0) + ',' + plane.y.toFixed(0) + '))' +
          ' 待登机=' + waiting.length + ' @t=' + this.simState.currentTime.toFixed(1))

        // 每 tick 限量释放（排队登机），不再一次性释放全部等待粒子，
        // 避免大量粒子 progress 溢出瞬间消失，看起来像"新粒子在登机"。
        // 主干道上的等待粒子逐个出发，沿主干道走到登机口投影点，再转入走廊走到登机口。
        const batchSize = Math.min(waiting.length, 3)

        // 拼接登机路径（全部取自现有走廊 waypoints，严禁新增路线）：
        //   等待位置(trunk 主干道) → 与等待区同入口的交点(in[1]) → 脊柱投影(in[2])
        //   → 门高度(in[3]) → 登机口中心(in[4])
        // 粒子沿主干道蓝道走到交点，再转入 in 走廊蓝道走到登机口，全程不脱离路线
        const appWp = this.routeCorridors[app.idx].waypoints

        for (let i = 0; i < batchSize; i++) {
          const p = waiting[i]
          if (!p) continue
          p.status = 'walking'
          p.corridorIdx = app.idx
          // 粒子从自身等待位置出发（progress 0），完整走完拼接路径 —— 无瞬移
          p.waypoints = [
            { x: p.waitX, y: p.waitY },
            { x: appWp[1].x, y: appWp[1].y },
            { x: appWp[2].x, y: appWp[2].y },
            { x: appWp[3].x, y: appWp[3].y },
            { x: appWp[4].x, y: appWp[4].y },
          ]
          p.progress = i * 0.003
          p.targetGate = gate.name
          p.laneOffset = (i % 5 - 2) * 0.3
          flight.paxBoarded = Math.min(flight.paxTotal, flight.paxBoarded + 1)
        }
      }
    },

    // 从已有 routeCorridors 中找"终点靠近登机口、与等待区主干道同入口"的 in 走廊
    findExistingApproachCorridor(gate) {
      const toCx = gate.x + gate.w / 2
      const toCy = gate.y + gate.h / 2

      // 等待区主干道走廊（粒子等待位置所在），取其入口中心作为共享交叉点：
      // 只有与它同一入口的 in 走廊，粒子沿主干道的移动才全程在蓝色道路上，
      // 不会横向超出等待区范围（脱离路线）
      const isT1 = gate.x < 300
      const trunkIdx = this.trunkCorridorIdx[isT1 ? 'T1' : 'T2']
      const trunkWp = trunkIdx >= 0 ? this.routeCorridors[trunkIdx].waypoints : null
      const trunkEntry = trunkWp ? trunkWp[0] : null

      let bestIdx = -1, bestDist = Infinity
      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (!rc.waypoints || rc.waypoints.length < 2) continue
        // 排除出口走廊（routeType 含 'out' 或 'exit-approach' 等从 gate 出发的路线）
        if (rc.routeType && (rc.routeType.includes('out') || rc.routeType.includes('exit'))) continue
        // 必须精确匹配该登机口自己的 in 走廊：
        // 相邻登机口间距可能 <30，仅凭距离会误匹配到隔壁登机口的走廊，
        // 导致粒子走到没有飞机的登机口（如 84 误匹配 85）
        if (rc.gateName !== gate.name) continue
        // 必须与等待区主干道共享同一入口（保证粒子沿主干道移动在预设路线上）
        if (trunkEntry) {
          const first = rc.waypoints[0]
          if (Math.abs(first.x - trunkEntry.x) > 2 || Math.abs(first.y - trunkEntry.y) > 2) continue
        }

        const last = rc.waypoints[rc.waypoints.length - 1]
        const dLast = Math.abs(last.x - toCx) + Math.abs(last.y - toCy)
        if (dLast < 30 && dLast < bestDist) {
          bestDist = dLast; bestIdx = i
        }
      }
      if (bestIdx < 0) return null

      const rc = this.routeCorridors[bestIdx]
      const wp = rc.waypoints

      // 计算走廊总长和各段长度，找到主干道→登机口的分界点
      const segLen = []
      let totalLen = 0
      for (let i = 1; i < wp.length; i++) {
        const dx = wp[i].x - wp[i - 1].x
        const dy = wp[i].y - wp[i - 1].y
        const len = Math.sqrt(dx * dx + dy * dy) || 1
        segLen.push(len)
        totalLen += len
      }

      // 起步点定位到"主干道投影点"（waypoint[2]），即主干道与走廊的连接处，
      // 让粒子从主干道端走向登机口。不能压缩到 0.1~0.4：
      // in 走廊从入口到主干道很长，0.4 会把起步点放到入口侧，
      // 视觉上像是"从入口新加载的粒子在登机"，而主干道等待粒子不动。
      let startProgress = 0
      for (let i = 0; i < wp.length - 2; i++) {
        startProgress += segLen[i] / totalLen
      }
      // 兜底夹在 0.5~0.95，确保起步点始终在主干道一侧
      startProgress = Math.max(0.5, Math.min(0.95, startProgress))

      console.log('[PAX] 找到走廊→' + gate.name + ' idx=' + bestIdx + ' wp=' + wp.length + ' startProgress=' + startProgress.toFixed(3))
      return { idx: bestIdx, startProgress }
    },

    findCorridorGateApproach(tc, boardingGate) {
      const toCx = boardingGate.x + boardingGate.w / 2
      const toCy = boardingGate.y + boardingGate.h / 2
      let bestIdx = -1
      let bestDist = Infinity
      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (!rc.waypoints || rc.waypoints.length < 2) continue
        // 匹配任意走廊终点靠近登机口（不再限制 routeType）
        const last = rc.waypoints[rc.waypoints.length - 1]
        const d = Math.abs(last.x - toCx) + Math.abs(last.y - toCy)
        if (d < 25 && d < bestDist) { bestDist = d; bestIdx = i }
      }
      return bestIdx >= 0 ? { idx: bestIdx } : null
    },

    // 找到从入口到航站楼的走廊
    findEntryCorridor(entryGate) {
      const ex = entryGate.x + entryGate.w / 2
      const ey = entryGate.y + entryGate.h / 2
      let bestIdx = -1
      let bestDist = Infinity
      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (!rc.waypoints || rc.waypoints.length < 2) continue
        const first = rc.waypoints[0]
        const d = Math.abs(first.x - ex) + Math.abs(first.y - ey)
        if (d < 20 && d < bestDist) { bestDist = d; bestIdx = i }
      }
      if (bestIdx >= 0) return bestIdx
      // 兜底：找最近的走廊起点
      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (!rc.waypoints || rc.waypoints.length < 2) continue
        const first = rc.waypoints[0]
        const d = Math.abs(first.x - ex) + Math.abs(first.y - ey)
        if (d < bestDist) { bestDist = d; bestIdx = i }
      }
      return bestIdx >= 0 ? bestIdx : 0
    },

    advancePassengers() {
      for (const p of this.passengers) {
        // 候机中的旅客不动
        if (p.status === 'waiting') continue
        if (p.status === 'stranded') continue

        // 疏散模式下加速
        const speedMul = this.evacuation.active ? 2.5 : 1

        p._prevProgress = p.progress
        p.progress += p.speed * speedMul

        // entering 状态：到达主干道区域（约 0.3 进度）转为候机
        if (p.status === 'entering' && p.progress >= 0.30) {
          p.status = 'waiting'
          // 切换到主干道走廊，定位到等待位置
          p.corridorIdx = p.waitCorridorIdx != null ? p.waitCorridorIdx : p.corridorIdx
          p.progress = p.waitProgress || 0.5
          continue
        }

        // 到达终点
        if (p.progress >= 1.0) {
          p.progress = 1.0
          p.status = 'arrived'
        }
      }
    },

    cleanupPassengers() {
      this.passengers = this.passengers.filter(p => {
        if (p.status === 'arrived') {
          if (this.evacuation.active) {
            this.evacuation.totalArrived++
          }
          // 记录乘客终态：出发航班旅客=已登机，到达航班旅客=已出站，
          // 供状态查询组件在粒子被清理后仍能追溯
          if (p.paxId) {
            this._paxLog[p.flightId + '|' + p.paxId] = {
              flightNo: p.flightId,
              paxId: p.paxId,
              paxSeq: p.paxSeq,
              status: p.type === 'inbound' ? 'boarded' : 'exited',
              type: p.type,
              terminal: p.terminal,
              at: Math.round(this.simState.currentTime),
            }
          }
          return false
        }
        return true
      })
      if (this.evacuation.active) {
        this.evacuation.totalEvacuating = this.passengers.length
      }
    },

    calculateCongestion() {
      // 统计每条走廊上的旅客数
      const counts = new Array(this.routeCorridors.length).fill(0)
      for (const p of this.passengers) {
        if (p.corridorIdx >= 0 && p.corridorIdx < counts.length) {
          counts[p.corridorIdx]++
        }
      }
      this.congestion.levels = counts.map((count, i) => {
        const maxCap = this.routeCorridors[i].width >= 10 ? 30 : 6
        const density = Math.min(count / maxCap, 1)
        let level = 'free'
        if (density > 0.85) level = 'blocked'
        else if (density > 0.6) level = 'heavy'
        else if (density > 0.3) level = 'moderate'
        return { corridorIdx: i, density, level }
      })
    },

    // ========== 疏散 ==========

    startEvacuation(targetArea) {
      this.evacuation.active = true
      this.evacuation.targetArea = targetArea || 'all'
      this.evacuation.totalEvacuating = this.passengers.length
      this.evacuation.totalArrived = 0
      this.evacuation.availableExits = this.exitGates
        .filter(g => this.isGateOpen(g.name))
        .map(g => g.name)

      // 重新规划每个旅客的目标为最近出口
      const exits = this.exitGates.filter(g => this.isGateOpen(g.name))
      for (const p of this.passengers) {
        let bestExit = null
        let bestDist = Infinity
        for (const ex of exits) {
          const d = Math.abs(p.corridorIdx - exits.indexOf(ex))
          if (d < bestDist) { bestDist = d; bestExit = ex }
        }
        if (bestExit) {
          const corridor = this.findCorridorForRoute(
            { name: '', x: p.progress, y: 0 }, bestExit, 'out')
          if (corridor) {
            p.corridorIdx = corridor.idx
            p.progress = 0
            p.color = '#f44336cc'
            p.status = 'evacuating'
          }
        }
      }
    },

    stopEvacuation() {
      this.evacuation.active = false
      this.evacuation.totalEvacuating = 0
      this.evacuation.totalArrived = 0
      for (const p of this.passengers) {
        p.status = 'walking'
        // 恢复原始颜色
        if (p.type === 'inbound') p.color = p.terminal === 'T1' ? '#4caf50cc' : '#2196f3cc'
        else if (p.type === 'outbound') p.color = '#ff9800cc'
        else if (p.type === 'transit') p.color = '#e91e63cc'
      }
    },

    // ========== 闸门控制 ==========

    initGateStates() {
      const allGates = this.layoutData ? (this.layoutData.gates || []) : []
      this.gateStates = {}
      for (const g of allGates) {
        this.gateStates[g.name] = {
          status: 'open',
          type: g.gate_dir === 'entry' ? 'entry' :
                g.gate_dir === 'exit' ? 'exit' :
                (g.type === 'rect' ? 'boarding' : 'unknown'),
        }
      }
    },

    setGateStatus(gateName, status) {
      if (this.gateStates[gateName]) {
        this.gateStates[gateName].status = status
      }
    },

    setAllGatesStatus(status) {
      for (const key in this.gateStates) {
        this.gateStates[key].status = status
      }
    },

    setCorridorBlocked(corridorIdx, blocked) {
      if (blocked) {
        // 封锁走廊：该走廊上的旅客变为 stranded
        for (const p of this.passengers) {
          if (p.corridorIdx === corridorIdx) {
            p.speed = 0
            p.status = 'stranded'
          }
        }
      } else {
        for (const p of this.passengers) {
          if (p.corridorIdx === corridorIdx && p.status === 'stranded') {
            p.speed = 0.008 + Math.random() * 0.012
            p.status = 'walking'
          }
        }
      }
    },

    isGateOpen(gateName) {
      const gs = this.gateStates[gateName]
      return gs ? gs.status === 'open' : true
    },

    // ========== 走廊查找 ==========

    findCorridorForRoute(fromGate, toGate, dir) {
      // 在现有走廊中找一条匹配的
      const fromCx = fromGate.x + (fromGate.w || 0) / 2
      const fromCy = fromGate.y + (fromGate.h || 0) / 2
      const toCx = toGate.x + (toGate.w || 0) / 2
      const toCy = toGate.y + (toGate.h || 0) / 2

      let bestIdx = -1
      let bestDist = Infinity

      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (!rc.waypoints || rc.waypoints.length < 2) continue

        // 离港路线检查
        if (dir === 'out' && rc.routeType && (rc.routeType.includes('out') || rc.routeType.includes('exit'))) {
          const first = rc.waypoints[0]
          const last = rc.waypoints[rc.waypoints.length - 1]
          const d1 = Math.abs(first.x - fromCx) + Math.abs(first.y - fromCy)
          const d2 = Math.abs(last.x - toCx) + Math.abs(last.y - toCy)
          if (d1 + d2 < bestDist) { bestDist = d1 + d2; bestIdx = i }
        }
        // 入港路线检查
        if (dir === 'in' && rc.routeType && (rc.routeType.includes('in') || rc.routeType.includes('trunk'))) {
          const first = rc.waypoints[0]
          const last = rc.waypoints[rc.waypoints.length - 1]
          const d1 = Math.abs(first.x - fromCx) + Math.abs(first.y - fromCy)
          const d2 = Math.abs(last.x - toCx) + Math.abs(last.y - toCy)
          if (d1 + d2 < bestDist) { bestDist = d1 + d2; bestIdx = i }
        }
      }

      // fallback: 任意走廊
      if (bestIdx < 0) {
        bestIdx = Math.floor(Math.random() * this.routeCorridors.length)
      }
      return { idx: bestIdx }
    },

    findTransitCorridor(fromGate, toGate) {
      // 查找 T1↔T2 联通走廊
      for (let i = 0; i < this.routeCorridors.length; i++) {
        const rc = this.routeCorridors[i]
        if (rc.routeType === 'link' || rc.routeType === 'conn') {
          return { idx: i }
        }
      }
      return { idx: 0 }
    },

    // ========== 热力图覆盖层 ==========

    drawHeatmapOverlay() {
      const canvas = this.$refs.canvas
      if (!canvas || !this.routeCorridors) return
      const ctx = canvas.getContext('2d')

      for (const cl of this.congestion.levels) {
        const rc = this.routeCorridors[cl.corridorIdx]
        if (!rc || !rc.waypoints || rc.waypoints.length < 2) continue

        let heatColor = 'rgba(76,175,80,0.15)'
        if (cl.level === 'moderate') heatColor = 'rgba(255,235,59,0.2)'
        else if (cl.level === 'heavy') heatColor = 'rgba(255,152,0,0.25)'
        else if (cl.level === 'blocked') heatColor = 'rgba(244,67,54,0.35)'

        ctx.save()
        ctx.strokeStyle = heatColor
        ctx.lineWidth = this.tw(rc.width) * 1.5
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        ctx.beginPath()
        const sx0 = this.tx(rc.waypoints[0].x), sy0 = this.ty(rc.waypoints[0].y)
        ctx.moveTo(sx0, sy0)
        for (let i = 1; i < rc.waypoints.length; i++) {
          ctx.lineTo(this.tx(rc.waypoints[i].x), this.ty(rc.waypoints[i].y))
        }
        ctx.stroke()
        ctx.restore()
      }
    },

    // ========== 闸门覆盖层（关闭的闸门标记） ==========

    drawGateOverlays() {
      const canvas = this.$refs.canvas
      if (!canvas || !this.gateStates) return
      const ctx = canvas.getContext('2d')
      const gates = this.layoutData ? (this.layoutData.gates || []) : []

      for (const g of gates) {
        const gs = this.gateStates[g.name]
        if (!gs || gs.status === 'open') continue

        const gx = this.tx(g.x), gy = this.ty(g.y)
        const gw = this.tw(g.w), gh = this.th(g.h)
        const cx = gx + gw / 2
        const cy = gy + gh / 2

        ctx.save()
        // 红色脉冲边框
        const pulse = 0.4 + 0.3 * Math.sin(Date.now() / 300)
        ctx.strokeStyle = `rgba(244,67,54,${pulse})`
        ctx.lineWidth = 2.5
        ctx.strokeRect(gx - 2, gy - 2, gw + 4, gh + 4)

        // 叉号
        ctx.strokeStyle = '#f44336'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(cx - Math.min(gw, gh) * 0.3, cy - Math.min(gw, gh) * 0.3)
        ctx.lineTo(cx + Math.min(gw, gh) * 0.3, cy + Math.min(gw, gh) * 0.3)
        ctx.moveTo(cx + Math.min(gw, gh) * 0.3, cy - Math.min(gw, gh) * 0.3)
        ctx.lineTo(cx - Math.min(gw, gh) * 0.3, cy + Math.min(gw, gh) * 0.3)
        ctx.stroke()

        // "关闭" 文字
        ctx.fillStyle = '#f44336'
        ctx.font = 'bold 8px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText('关闭', cx, gy - 3)
        ctx.restore()
      }
    },

    // ========== 飞机精灵 ==========

    generateTaxiPath(gateName) {
      const allGates = this.layoutData ? (this.layoutData.gates || []) : []
      const gate = allGates.find(g => g.name === gateName)
      if (!gate) return []
      const channelName = TAXI_CHANNELS.gateToChannel[gateName]
      if (!channelName) return []
      const end = TAXI_CHANNELS.channelEndpoints[channelName]

      // 水平排列的登机口（T1-T2 间隙区）：飞机在门区下方，起点在门区中心下侧
      const HORIZONTAL_GATES = [
        '矩形 41', '矩形 42', '矩形 43', '矩形 46', '矩形 50',
        '矩形 53', '矩形 54', '矩形 55', '矩形 56', '矩形 57',
        '矩形 58', '矩形 59', '矩形 60', '矩形 61',
      ]
      let startX, startY
      if (HORIZONTAL_GATES.includes(gateName)) {
        startX = gate.x + gate.w / 2
        startY = gate.y + gate.h + 18
      } else {
        const side = this.getAirplaneSide(gate)
        startX = side === 'LEFT' ? gate.x - 18 : gate.x + gate.w + 18
        startY = gate.y + gate.h / 2
      }

      // 跑道一：水平段放在 y=490（远低于所有登机口 y≤444 和主干 yBot≤444，不会交叉）
      // 跑道二：跑道与 T2 登机口在同一水平面，直接竖直→水平进入跑道
      let path
      if (end.runway === '跑道二') {
        if (gateName === '矩形 83') {
          // 沿 t2 右线滑行，避免穿过建筑物区域（矩形13）
          const t2RightLineX = 590
          path = [
            { x: startX, y: startY },
            { x: t2RightLineX, y: startY },
            { x: t2RightLineX, y: end.y },
            { x: end.x, y: end.y },
          ]
        } else {
          path = [
            { x: startX, y: startY },
            { x: startX, y: end.y },
            { x: end.x, y: end.y },
          ]
        }
      } else if (HORIZONTAL_GATES.includes(gateName)) {
        // 水平排列登机口：飞机先水平前移 30 单位再转竖直下降
        path = [
          { x: startX, y: startY },
          { x: startX + 30, y: startY },
          { x: startX + 30, y: 490 },
          { x: end.x, y: 490 },
          { x: end.x, y: end.y },
        ]
      } else {
        path = [
          { x: startX, y: startY },
          { x: startX, y: 490 },
          { x: end.x, y: 490 },
          { x: end.x, y: end.y },
        ]
      }
      return { path, channelName, end }
    },

    // 判断飞机应放在登机口左侧还是右侧
    // 计算飞机在左/右侧时，与所有其他登机口的距离冲突数，选择冲突更少的一侧
    getAirplaneSide(gate) {
      const allGates = this.layoutData ? (this.layoutData.gates || []) : []
      const gc = gate.y + gate.h / 2
      let conflictsLeft = 0
      let conflictsRight = 0
      for (const g of allGates) {
        if (g.name === gate.name || !g.name || !g.name.includes('矩形')) continue
        const gcx = g.x + g.w / 2
        const gcy = g.y + g.h / 2
        // 飞机左侧中心(gate.x-18, gc)，20px范围内判定冲突
        if (Math.abs((gate.x - 18) - gcx) < 25 && Math.abs(gc - gcy) < 25) conflictsLeft++
        // 飞机右侧中心(gate.x+gate.w+18, gc)
        if (Math.abs((gate.x + gate.w + 18) - gcx) < 25 && Math.abs(gc - gcy) < 25) conflictsRight++
      }
      if (conflictsLeft < conflictsRight) return 'LEFT'
      if (conflictsRight < conflictsLeft) return 'RIGHT'
      const channelName = TAXI_CHANNELS.gateToChannel[gate.name]
      return channelName === 't1_left' ? 'LEFT' : 'RIGHT'
    },

    spawnAirplane(flight, type) {
      const channelName = TAXI_CHANNELS.gateToChannel[flight.gateName]
      if (!channelName) {
        console.warn('[A320] No channel for gate:', flight.gateName)
        return
      }
      const taxiData = this.generateTaxiPath(flight.gateName)
      if (!taxiData || !taxiData.path.length) {
        console.warn('[A320] No taxi path for gate:', flight.gateName)
        return
      }

      // 水平排列的登机口（T1-T2 间隙区，沿 x 轴排布，与其他竖直堆叠的 gate 不同）
      const HORIZONTAL_GATES = [
        '矩形 41', '矩形 42', '矩形 43', '矩形 46', '矩形 50',
        '矩形 53', '矩形 54', '矩形 55', '矩形 56', '矩形 57',
        '矩形 58', '矩形 59', '矩形 60', '矩形 61',
      ]

      if (type === 'departure') {
        const gate = (this.layoutData ? this.layoutData.gates || [] : [])
          .find(g => g.name === flight.gateName)
        if (!gate) return

        if (HORIZONTAL_GATES.includes(flight.gateName)) {
          // 水平排列登机口：飞机水平摆放(angle=0)，紧贴门区下侧（外侧边）
          const cx = gate.x + gate.w / 2
          const cy = gate.y + gate.h + 18
          this.airplanes.push({
            id: 'plane_' + flight.tailNo,
            flightNo: flight.flightNo,
            tailNo: flight.tailNo,
            type: 'departure',
            status: 'AT_GATE',
            x: cx, y: cy,
            angle: 0,
            scale: 1.0,
            alpha: 1.0,
            taxiPath: taxiData.path,
            pathProgress: 0,
            pathSpeed: TAXI_SPEED,
            assignedRunway: taxiData.end.runway,
            readyToTaxi: false,
            channelName: channelName,
          })
        } else {
          // 竖直堆叠登机口：飞机竖直(π/2)，自动判断左侧/右侧
          const side = this.getAirplaneSide(gate)
          const cx = side === 'LEFT' ? gate.x - 18 : gate.x + gate.w + 18
          const cy = gate.y + gate.h / 2

          this.airplanes.push({
            id: 'plane_' + flight.tailNo,
            flightNo: flight.flightNo,
            tailNo: flight.tailNo,
            type: 'departure',
            status: 'AT_GATE',
            x: cx, y: cy,
            angle: Math.PI / 2,
            scale: 1.0,
            alpha: 1.0,
            taxiPath: taxiData.path,
            pathProgress: 0,
            pathSpeed: TAXI_SPEED,
            assignedRunway: taxiData.end.runway,
            readyToTaxi: false,
            channelName: channelName,
          })
        }
      } else if (type === 'arrival') {
        // 到达航班：从跑道右端出现，面朝左边沿跑道滑入
        const isRunway1 = taxiData.end.runway === '跑道一'
        const runwayEndX = isRunway1 ? 620 : 1210
        const runwayY = isRunway1 ? 534.6 : 318.6
        this.airplanes.push({
          id: 'plane_' + flight.tailNo,
          flightNo: flight.flightNo,
          tailNo: flight.tailNo,
          type: 'arrival',
          status: 'LANDING',
          x: runwayEndX, y: runwayY,
          angle: Math.PI,       // 面朝左
          scale: 1.0,
          alpha: 1.0,
          taxiPath: [...taxiData.path].reverse(),  // 跑道入口→登机口
          pathProgress: 0,
          pathSpeed: TAXI_SPEED,
          assignedRunway: taxiData.end.runway,
          readyToTaxi: false,
          channelName: channelName,
          gateName: flight.gateName,
          runwayEntryX: taxiData.end.x,  // 跑道入口 X（34或638）
        })
      }
    },

    spawnAirplanesForBoarding() {
      // 遍历所有"登机中"的出发航班（幂等重试）：
      // 若航班进入 boarding 时前序下客尚未完成，仅在一次性列表里处理会被永久跳过，
      // 导致等待旅客永远不动。改为每 tick 遍历 boarding 航班，下客完成即激活飞机。
      for (const f of this.simFlights) {
        if (f.type !== 'departure' || f.status !== 'boarding') continue

        const fleetPlane = this.airplaneFleet.find(p => p.tailNo === f.tailNo)
        const visualPlane = this.airplanes.find(p => p.tailNo === f.tailNo)

        if (visualPlane) {
          // 飞机还在空中飞行：等待其前序到达航班降落后再复用，不生成新飞机
          if (visualPlane.status === 'IN_FLIGHT' || visualPlane.status === 'AWAITING_ARRIVAL') {
            continue
          }

          // 已为该航班激活、或正在滑行/起飞：不重复处理（避免每 tick 重置 readyToTaxi 导致无法推出）
          if (
            (visualPlane.status === 'AT_GATE' && visualPlane.flightNo === f.flightNo) ||
            visualPlane.status === 'TAXIING_TO_GATE' ||
            visualPlane.status === 'TAXIING' ||
            visualPlane.status === 'TAKING_OFF'
          ) {
            continue
          }

          // 前序到达航班：需下客完成，且下客完成后经过周转调整时间才能开始登机
          const prevArrival = this.flightSchedule.find(
            sf => sf.tailNo === f.tailNo && sf.type === 'arrival' && sf.nextFlightNo === f.flightNo
          )
          if (prevArrival) {
            const deboardedAt = this._deboardedAt[prevArrival.flightNo]
            // [DEBUG] 记录转场航班的上客前置判断
            console.log('[FLEET][DEBUG] ' + f.flightNo + ' 上客前置检查: 前序=' + prevArrival.flightNo +
              ' 下客完成时刻=' + (deboardedAt === undefined ? '未下客' : deboardedAt.toFixed(1)) +
              ' 当前t=' + this.simState.currentTime.toFixed(1) +
              ' 飞机status=' + visualPlane.status +
              ' fleetGate=' + (fleetPlane ? (fleetPlane.currentGate || 'null') : '无fleet') +
              ' 目标gate=' + f.gateName)
            if (deboardedAt === undefined) {
              continue  // 尚未完成下客，等待
            }
            if (this.simState.currentTime - deboardedAt < TURNAROUND_TIME) {
              continue  // 下客完成后仍需等待调整时间（清洁/加油等）
            }
          }

          // 飞机已在画布上（预加载的、或上一班到达后留下的）
          const currentGate = fleetPlane ? fleetPlane.currentGate : null
          if (currentGate === f.gateName || visualPlane.status === 'PRELOADED_AT_GATE') {
            // 同一登机口或预加载：直接激活为登机状态
            if (visualPlane.flightNo !== f.flightNo) {
              console.log('[FLEET] 复用 ' + f.tailNo + ' @ ' + f.gateName + ' → ' + f.flightNo)
            }
            visualPlane.flightNo = f.flightNo
            visualPlane.id = 'plane_' + f.tailNo
            visualPlane.status = 'AT_GATE'
            visualPlane.readyToTaxi = false
            visualPlane.type = 'departure'
            const channelName = TAXI_CHANNELS.gateToChannel[f.gateName]
            visualPlane.channelName = channelName
            visualPlane.assignedRunway = TAXI_CHANNELS.channelEndpoints[channelName]?.runway || '跑道一'
            if (fleetPlane) {
              fleetPlane.status = 'BOARDING'
              fleetPlane.currentFlightNo = f.flightNo
              fleetPlane.currentGate = f.gateName
            }
          } else if (currentGate && currentGate !== f.gateName) {
            // 不同登机口：门到门滑行
            // [DEBUG] 记录转场触发（含飞机当前实际位置）
            console.log('[FLEET][DEBUG] 转场 ' + f.tailNo + ': ' + currentGate + ' → ' + f.gateName +
              ' (' + f.flightNo + ') @t=' + this.simState.currentTime.toFixed(1) +
              ' 飞机位置=(' + visualPlane.x.toFixed(0) + ',' + visualPlane.y.toFixed(0) + ')' +
              ' 飞机gateName=' + visualPlane.gateName)
            this.startGateTransfer(visualPlane, f, fleetPlane)
          } else {
            // 兜底异常：当前Gate信息不匹配且非预加载，无法复用 —— 禁止凭空创建飞机
            if (!f._warnedNoPlane) {
              f._warnedNoPlane = true
              console.warn('[FLEET] 警告：' + f.flightNo + ' 无匹配飞机可复用（tail=' + f.tailNo + '），跳过')
            }
          }
        } else {
          // 飞机不在画布上 —— 严禁兜底创建新飞机（全局仅允许预加载的 2 架飞机）
          if (!f._warnedNoPlane) {
            f._warnedNoPlane = true
            console.warn('[FLEET] 警告：' + f.flightNo + ' 画布上无飞机（tail=' + f.tailNo + '），跳过')
          }
        }
      }
    },

    // 门到门滑行：飞机从一个登机口滑行到另一个登机口
    startGateTransfer(plane, targetFlight, fleetPlane) {
      const allGates = this.layoutData ? (this.layoutData.gates || []) : []
      const toGate = allGates.find(g => g.name === targetFlight.gateName)
      if (!toGate) { console.warn('[FLEET] 找不到目标登机口'); return }

      const toSide = this.getAirplaneSide(toGate)
      const toCx = toSide === 'LEFT' ? toGate.x - 18 : toGate.x + toGate.w + 18
      const toCy = toGate.y + toGate.h / 2

      // 沿 t2 右线滑行（x=590，在矩形13右侧）
      const t2LineX = 590
      const path = [
        { x: plane.x, y: plane.y },
        { x: t2LineX, y: plane.y },
        { x: t2LineX, y: toCy },
        { x: toCx, y: toCy },
      ]

      plane.taxiPath = path
      plane.pathProgress = 0
      plane.pathSpeed = TAXI_SPEED
      plane.status = 'TAXIING_TO_GATE'
      plane.targetFlight = targetFlight
      plane.targetGate = targetFlight.gateName
      targetFlight._transferPlane = true  // 标记该航班飞机在转场中

      if (fleetPlane) {
        fleetPlane.status = 'TRANSFERRING'
        fleetPlane.currentFlightNo = targetFlight.flightNo
        fleetPlane.currentGate = targetFlight.gateName
      }

      console.log('[FLEET] 门到门路径: (' + plane.x.toFixed(0) + ',' + plane.y.toFixed(0) + ') → (' + toCx.toFixed(0) + ',' + toCy.toFixed(0) + ')')
    },

    spawnArrivalPlanes() {
      // 到达航班到预定时间后，让飞机出现在跑道远端开始降落
      const ct = this.simState.currentTime
      const arrivalFlights = this.simFlights.filter(f =>
        f.type === 'arrival' && f.status === 'scheduled' && ct >= f.scheduledArr
      )
      for (const f of arrivalFlights) {
        // 查找该飞机的现有画布对象（IN_FLIGHT 状态）
        let plane = this.airplanes.find(p => p.tailNo === f.tailNo)

        if (plane) {
          // 可复用降落的状态：
          // - IN_FLIGHT：前序航班已起飞，在空中飞行
          // - AWAITING_ARRIVAL：到达首航班，预加载在跑道远端等待
          // 其他状态（登机口上客/滑行/起飞中）跳过等待，绝不劫持
          const reusable = plane.status === 'IN_FLIGHT' || plane.status === 'AWAITING_ARRIVAL'
          if (!reusable) {
            continue
          }

          const taxiData = this.generateTaxiPath(f.gateName)
          if (!taxiData || !this.isRunwayClear(taxiData.end.runway)) continue

          const isRunway1 = taxiData.end.runway === '跑道一'
          plane.x = isRunway1 ? 620 : 1210
          plane.y = isRunway1 ? 534.6 : 318.6
          plane.angle = Math.PI
          plane.alpha = 1.0
          plane.scale = 1.0           // 重置上一航班起飞时的缩小/渐隐状态
          plane._takeoffPhase = null
          plane.status = 'LANDING'
          plane.flightNo = f.flightNo
          plane.type = 'arrival'
          plane.taxiPath = [...taxiData.path].reverse()
          plane.pathProgress = 0
          plane.assignedRunway = taxiData.end.runway
          plane.gateName = f.gateName
          plane.runwayEntryX = taxiData.end.x
          f.status = 'landing'

          const fleetPlane = this.airplaneFleet.find(fp => fp.tailNo === plane.tailNo)
          if (fleetPlane) {
            fleetPlane.status = 'LANDING'
            fleetPlane.currentFlightNo = f.flightNo
          }
          console.log('[FLEET] 复用 ' + f.tailNo + ' → 开始降落 ' + f.flightNo + ' → ' + f.gateName)
          continue
        }

        // 兜底异常：飞机不在画布上 —— 严禁凭空创建新飞机，仅告警跳过（保持 scheduled 待下次重试）
        if (!f._warnedNoPlane) {
          f._warnedNoPlane = true
          console.warn('[FLEET] 警告：' + f.flightNo + ' 到达航班无可用飞机（tail=' + f.tailNo + '），跳过')
        }
      }
    },

    // 获取跑道上正在起降的飞机数
    getRunwayOccupation(runwayName) {
      return this.airplanes.filter(p =>
        (p.status === 'TAKING_OFF' || p.status === 'LANDING') &&
        p.assignedRunway === runwayName
      ).length
    },

    // 跑道冲突检测：同跑道同时段仅允许1架起降
    isRunwayClear(runwayName) {
      if (this.runwayCooldown[runwayName] > 0) return false
      return this.getRunwayOccupation(runwayName) === 0
    },

    getRunwayAngle(runwayName) {
      return 0  // 两个跑道都是水平方向
    },

    updateAirplanes() {
      for (const plane of this.airplanes) {
        switch (plane.status) {
          case 'PRELOADED_AT_GATE':
            // 预加载飞机：已停靠登机口，等待登机开始，不做任何处理
            break

          case 'AT_GATE':
            // 出发航班等待登机完成 → 自动触发滑行
            if (plane.type === 'departure' && plane.readyToTaxi) {
              // 每次推出起飞前都重新生成"登机口→跑道入口"的滑行路径：
              // 复用的飞机（同登机口续飞 / 转场后）会残留上一航班的到达/转场 taxiPath，
              // 若沿用旧路径，飞机将瞬移到旧路径起点并从错误位置起飞。
              const taxiData = plane.gateName ? this.generateTaxiPath(plane.gateName) : null
              if (!taxiData || !taxiData.path || !taxiData.path.length) {
                // 无有效路径则不推出，避免飞机瞬移消失
                plane.readyToTaxi = false
                break
              }
              plane.taxiPath = taxiData.path
              plane.assignedRunway = taxiData.end.runway
              plane.channelName = taxiData.channelName
              // 飞机对齐到滑行路径起点（登机口侧方停机位），与预加载飞机位置一致
              plane.x = taxiData.path[0].x
              plane.y = taxiData.path[0].y
              plane.angle = getPathAngle(taxiData.path, 0)
              plane.status = 'TAXIING'
              plane.pathProgress = 0
            }
            break

          case 'AT_GATE_IDLE':
            // 到达后待命的飞机：等待下一航班登机（由 spawnAirplanesForBoarding 激活）
            break

          case 'TAXIING_TO_GATE':
            // 门到门滑行
            this.flyGateTransfer(plane)
            break

          case 'TAXIING':
            this.flyPlaneTaxiing(plane)
            break

          case 'TAKING_OFF':
            this.flyPlaneTakeoff(plane)
            break

          case 'LANDING':
            this.flyPlaneLanding(plane)
            break

          case 'IN_FLIGHT':
            // 飞机在空中飞行，等待下一到达航班时间
            break

          case 'AWAITING_ARRIVAL':
            // 预加载的到达飞机，在跑道远端等待到达时间
            break
        }
      }

      // 飞机生命周期管理：
      // - 起飞后有后续航班 → 保留飞机（IN_FLIGHT，alpha=0），等到达时复用
      // - 起飞后无后续航班 → 移除
      this.airplanes = this.airplanes.filter(p => {
        if (p.status === 'DEPARTED') {
          const hasNextFlight = this.flightSchedule.some(
            f => !f.cancelled && f.tailNo === p.tailNo &&
              (f.boardingStart || f.scheduledArr || 0) > this.simState.currentTime
          )
          if (hasNextFlight) {
            // 保留飞机，转为 IN_FLIGHT 状态（不可见）
            p.status = 'IN_FLIGHT'
            p.alpha = 0
            p.flightNo = '...'  // 飞行中无航班号
            p.type = 'arrival'  // 下一次必定是到达
            const fleetPlane = this.airplaneFleet.find(fp => fp.tailNo === p.tailNo)
            if (fleetPlane) {
              fleetPlane.status = 'IN_FLIGHT'
              fleetPlane.currentGate = null
              fleetPlane.currentFlightNo = null
            }
            console.log('[FLEET] ' + p.tailNo + ' 起飞，保留为 IN_FLIGHT（有后续航班）')
            return true
          }
          // 无后续航班，彻底移除
          return false
        }
        return true
      })
    },

    // 门到门滑行更新
    flyGateTransfer(plane) {
      plane.pathProgress += plane.pathSpeed * this.simState.speed
      if (plane.pathProgress >= 1.0) {
        // 到达目标登机口
        plane.status = 'AT_GATE'
        plane.pathProgress = 0
        plane.type = 'departure'
        plane.angle = Math.PI / 2
        // 将目标航班信息写入飞机
        if (plane.targetFlight) {
          plane.flightNo = plane.targetFlight.flightNo
          plane.gateName = plane.targetFlight.gateName  // 同步登机口，避免残留旧登机口导致路径/释放错乱
          plane.assignedRunway = TAXI_CHANNELS.channelEndpoints[
            TAXI_CHANNELS.gateToChannel[plane.targetFlight.gateName]
          ]?.runway || '跑道一'
          plane.targetFlight._transferPlane = false
          plane.targetFlight = null
        }
        // [DEBUG] 记录转场完成 + 检查飞机 gateName 是否更新到位
        console.log('[FLEET][DEBUG] ' + plane.tailNo + ' 转场完成 → ' + plane.flightNo +
          ' @t=' + this.simState.currentTime.toFixed(1) +
          ' | 飞机gateName=' + plane.gateName + '（若仍为旧登机口则说明未更新）' +
          ' 位置=(' + plane.x.toFixed(0) + ',' + plane.y.toFixed(0) + ')')
      } else {
        const pos = interpolatePath(plane.taxiPath, plane.pathProgress)
        plane.x = pos.x
        plane.y = pos.y
        plane.angle = getPathAngle(plane.taxiPath, plane.pathProgress)
      }
    },

    // 手动触发飞机推出（从外部或登机完成时调用）
    pushbackAirplane(flightNo) {
      const plane = this.airplanes.find(p =>
        p.flightNo === flightNo &&
        (p.status === 'AT_GATE' || p.status === 'PRELOADED_AT_GATE')
      )
      if (plane) {
        plane.readyToTaxi = true
      }
    },

    // 自动检测登机完成并推出
    checkBoardingComplete() {
      // 飞机只在乘客全部登机/下客完成后才移动
      const taxiingRunways = new Set(this.airplanes
        .filter(p => p.status === 'TAXIING' && p.type === 'departure')
        .map(p => p.assignedRunway))

      for (const f of this.simFlights.filter(f => f.type === 'departure' && f.status === 'boarding' && !f._transferPlane)) {
        // 条件1：所有乘客已通过登机口（paxBoarded >= paxTotal）
        if (f.paxBoarded < f.paxTotal) continue

        // 条件2：没有乘客还在走向登机口
        const stillWalking = this.passengers.some(
          p => p.flightId === f.flightNo && p.status === 'walking'
        )
        if (stillWalking) continue
        // 注：不再检查"画布上旅客数 >= paxTotal"——登机完成的旅客会被清理移除，
        // 该检查会导致永远不满足的死锁。paxBoarded 每登机一人+1 且不会超过实际
        // 投放数，条件1已隐含"旅客投放完毕"。

        // 标记航班为已出发
        if (f.status !== 'departed') {
          f.status = 'departed'
          // [DEBUG] 记录登机完成时刻
          console.log('[PAX][DEBUG] ' + f.flightNo + ' 登机完成 @t=' + this.simState.currentTime.toFixed(1) +
            ' (paxBoarded=' + f.paxBoarded + '/' + f.paxTotal + ')')
        }

        const plane = this.airplanes.find(p =>
          p.tailNo === f.tailNo &&
          p.flightNo === f.flightNo &&
          (p.status === 'AT_GATE' || p.status === 'PRELOADED_AT_GATE') &&
          p.type === 'departure'
        )
        if (!plane || plane.readyToTaxi) continue
        if (taxiingRunways.has(plane.assignedRunway)) continue
        console.log('[A320] Pushback:', f.flightNo, '(' + f.tailNo + ') gate:', f.gateName)
        plane.readyToTaxi = true
        taxiingRunways.add(plane.assignedRunway)
      }
    },

    // 所有预定航班播放完毕后自动停止模拟（不循环、不空转）
    checkSimulationComplete() {
      if (!this.simState.running) return
      // 出发航班需 departed、到达航班需 arrived（含下客完成）；取消航班直接视为已完成
      const allFlightsDone = this.simFlights.every(f =>
        f.status === 'cancelled' ||
        (f.type === 'departure' && f.status === 'departed') ||
        (f.type === 'arrival' && f.status === 'arrived' && this.arrivedFlightsDeboarded.has(f.flightNo))
      )
      if (!allFlightsDone) return
      // 等旅客粒子全部消散（登机完成 / 下客从出口走出）
      if (this.passengers.length > 0) return
      // 等最后一架飞机完成起飞/降落/转场动画；停在登机口的待命飞机视为已结束
      const hasActivePlane = this.airplanes.some(p =>
        ['TAXIING', 'TAKING_OFF', 'LANDING', 'TAXIING_TO_GATE'].includes(p.status)
      )
      if (hasActivePlane) return
      // 手动拖动过进度条：不停止模拟，由用户决定是否继续播放/切天
      if (this._manualIntervention) {
        console.log('[SIM] 手动干预中，保持运行，不自动切天')
        return
      }
      this.simState.running = false
      console.log('[SIM] ' + this.currentDate + ' 所有预定航班完成 (t=' + this.simState.currentTime.toFixed(1) + ')')
      // 通知父组件：当天播放完成，可自动切换到下一天
      if (!this._dayCompleteEmitted) {
        this._dayCompleteEmitted = true
        this.$emit('day-complete', this.currentDate)
      }
    },

    flyPlaneTaxiing(plane) {
      plane.pathProgress += plane.pathSpeed * this.simState.speed
      if (plane.pathProgress >= 1.0) {
        // 水平门区与竖直门区的朝向
        const HORIZONTAL_GATES = [
          '矩形 41', '矩形 42', '矩形 43', '矩形 46', '矩形 50',
          '矩形 53', '矩形 54', '矩形 55', '矩形 56', '矩形 57',
          '矩形 58', '矩形 59', '矩形 60', '矩形 61',
        ]
        if (plane._entering) {
          // 出发航班进场滑行：滑到登机口后转 AT_GATE 待命上客
          plane._entering = false
          plane.status = 'AT_GATE'
          plane.pathProgress = 0
          plane.angle = HORIZONTAL_GATES.includes(plane.gateName) ? 0 : Math.PI / 2
          const fleetPlane = this.airplaneFleet.find(fp => fp.tailNo === plane.tailNo)
          if (fleetPlane) {
            fleetPlane.status = 'AT_GATE'
            fleetPlane.currentGate = plane.gateName
            fleetPlane.currentFlightNo = plane.flightNo
            console.log('[FLEET] ' + plane.tailNo + ' 进场滑行到位 ' + plane.gateName + '，等待登机')
          }
        } else if (plane.type === 'departure') {
          // 检查跑道是否空闲
          if (!this.isRunwayClear(plane.assignedRunway)) {
            plane.pathProgress = 0.99  // 等待
            return
          }
          plane.status = 'TAKING_OFF'
          plane.angle = this.getRunwayAngle(plane.assignedRunway)
          plane.pathProgress = 0
        } else {
          // 到达航班：逆滑行到达登机口
          plane.status = 'AT_GATE_IDLE'
          plane.pathProgress = 0
          // 设置正确朝向：水平门区 angle=0，竖直门区 angle=π/2
          if (HORIZONTAL_GATES.includes(plane.gateName)) {
            plane.angle = 0
          } else {
            plane.angle = Math.PI / 2
          }
          // 标记航班为已到达
          const flight = this.simFlights.find(f => f.flightNo === plane.flightNo)
          if (flight) flight.status = 'arrived'
          // 更新机队状态：飞机停在登机口等待下一航班
          const fleetPlane = this.airplaneFleet.find(fp => fp.tailNo === plane.tailNo)
          if (fleetPlane) {
            fleetPlane.status = 'IDLE_AT_GATE'
            fleetPlane.currentGate = plane.gateName
            fleetPlane.currentFlightNo = null
            console.log('[FLEET] ' + plane.tailNo + ' 到达 ' + plane.gateName + '，待命等待下一航班')
          }
        }
      } else {
        const pos = interpolatePath(plane.taxiPath, plane.pathProgress)
        plane.x = pos.x
        plane.y = pos.y
        plane.angle = getPathAngle(plane.taxiPath, plane.pathProgress)
      }
    },

    // 起飞动画：跑道滑跑加速 → 离地爬升（上升+缩小+渐隐）→ 消失
    flyPlaneTakeoff(plane) {
      // 滑跑段稳步加速，离地后略提速
      const accel = plane._takeoffPhase === 'climb' ? 0.5 : 0.1
      const move = 50 * (1 + accel) * this.simState.speed
      plane.x += Math.cos(plane.angle) * move
      plane.y += Math.sin(plane.angle) * move

      // 越过跑道右边界后进入离地爬升段
      const runwayEnd = plane.assignedRunway === '跑道一' ? 620 : 1220
      if (plane.x > runwayEnd) {
        if (plane._takeoffPhase !== 'climb') {
          plane._takeoffPhase = 'climb'
          // 释放跑道，允许下一架飞机起降
          this.runwayCooldown[plane.assignedRunway] = 3
        }
        // 爬升：上升 + 缩小 + 渐隐，模拟飞机远去
        plane.y -= 1.1 * this.simState.speed
        plane.scale = Math.max(0.15, plane.scale - 0.02 * this.simState.speed)
        plane.alpha = Math.max(0, plane.alpha - 0.02 * this.simState.speed)
        if (plane.alpha <= 0 || plane.scale <= 0.15) {
          plane.status = 'DEPARTED'
          plane._takeoffPhase = null
        }
      } else {
        plane._takeoffPhase = 'run'
      }
    },

    flyPlaneLanding(plane) {
      // 着陆：从跑道右端向左滑入，大小不变
      plane.x -= 40 * this.simState.speed
      if (plane.x <= plane.runwayEntryX + 15) {
        // 到达跑道入口，开始逆滑行至登机口
        plane.status = 'TAXIING'
        plane.pathProgress = 0
        // 降落完成后设置跑道冷却（3 tick），防止立即有飞机起飞
        this.runwayCooldown[plane.assignedRunway] = 3
      }
    },

    drawTaxiPaths(ctx) {
      // 每个通道画一条代表性滑行路径（从该通道最右侧登机口出发）
      const allGates = this.layoutData ? (this.layoutData.gates || []) : []
      const channelBest = {}  // channelName → { gateName, startX }
      for (const gate of allGates) {
        if (!gate.name || !gate.name.includes('矩形')) continue
        const channelName = TAXI_CHANNELS.gateToChannel[gate.name]
        if (!channelName) continue
        const taxiData = this.generateTaxiPath(gate.name)
        if (!taxiData || !taxiData.path || taxiData.path.length < 2) continue
        const startX = taxiData.path[0].x
        if (!channelBest[channelName] || startX > channelBest[channelName].startX) {
          channelBest[channelName] = { gateName: gate.name, startX }
        }
      }

      // 收集所有竖直滑行线的标注信息
      const vertLabels = []

      // 部分通道竖直段不要太长，限制起点 y 下限
      const vertYClip = { t2_left: 430 }

      const channelLabels = {
        t1_left: 'T1-左线', t1_mid: 'T1-中线', t1_right: 'T1-右线',
        t2_left: 'T2-左线', t2_mid: 'T2-中线', t2_right: 'T2-右线',
      }

      for (const [channelName, info] of Object.entries(channelBest)) {
        const taxiData = this.generateTaxiPath(info.gateName)
        if (!taxiData || !taxiData.path || taxiData.path.length < 2) continue

        // 限制竖直段向上延伸
        const yClip = vertYClip[channelName]
        if (yClip && taxiData.path[0].y < yClip) {
          taxiData.path[0].y = yClip
          // 若路径是水平门型（path[0]→path[1]水平同Y），同步调整path[1]
          if (taxiData.path.length >= 3 && Math.abs(taxiData.path[0].y - taxiData.path[1].y) < 2) {
            taxiData.path[1].y = yClip
          }
        }

        // T2-右线：竖直段向下延伸（不影响飞机路径）
        if (channelName === 't2_right' && taxiData.path.length >= 3) {
          taxiData.path = [
            taxiData.path[0],
            { x: taxiData.path[0].x, y: 490 },
            taxiData.path[1],
            taxiData.path[2],
          ]
        }

        // 记录竖直段起点（路径第一个点）
        // T2-左线：不绘制（会穿越矩形13主干）
        if (channelName === 't2_left') continue

        const vx = taxiData.path[0].x
        const vy = taxiData.path[0].y
        vertLabels.push({ x: vx, yTop: vy, label: channelLabels[channelName] || channelName })

        ctx.save()

        // 构建路径点（跑道一延伸到 x=620）
        const points = taxiData.path.map(p => ({ x: this.tx(p.x), y: this.ty(p.y) }))
        if (taxiData.end.runway === '跑道一') {
          points.push({ x: this.tx(620), y: this.ty(taxiData.end.y) })
        }

        // 灰色宽路面
        ctx.strokeStyle = 'rgba(120, 120, 140, 0.55)'
        ctx.lineWidth = 14
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        ctx.beginPath()
        ctx.moveTo(points[0].x, points[0].y)
        for (let i = 1; i < points.length; i++) {
          ctx.lineTo(points[i].x, points[i].y)
        }
        ctx.stroke()

        // 红色中心引导线
        ctx.strokeStyle = 'rgba(255, 60, 60, 0.55)'
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.moveTo(points[0].x, points[0].y)
        for (let i = 1; i < points.length; i++) {
          ctx.lineTo(points[i].x, points[i].y)
        }
        ctx.stroke()

        // 跑道终点红色圆点 + 标注
        const isRunway1 = taxiData.end.runway === '跑道一'
        const dotX = isRunway1 ? 620 : taxiData.end.x
        const dotY = taxiData.end.y
        ctx.fillStyle = 'rgba(255, 60, 60, 0.7)'
        ctx.beginPath()
        ctx.arc(this.tx(dotX), this.ty(dotY), 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#ff3c3c'
        ctx.font = '9px monospace'
        ctx.fillText(taxiData.end.runway, this.tx(dotX) + 6, this.ty(dotY) + 4)

        ctx.restore()
      }

      // 垂直滑行连接道：矩形6主干左侧 和 矩形11/12主干之间
      const vertRoads = [
        { waypoints: [{ x: 8, y: 358 }, { x: 8, y: 490 }, { x: 34, y: 490 }], label: '连-6左' },
        { waypoints: [{ x: 405, y: 370 }, { x: 405, y: 490 }], label: '连-11/12间' },
      ]
      for (const vr of vertRoads) {
        const sx = vr.waypoints[0].x
        const sy = vr.waypoints[0].y
        vertLabels.push({ x: sx, yTop: sy, label: vr.label })

        ctx.strokeStyle = 'rgba(140, 140, 160, 0.65)'
        ctx.lineWidth = 16
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        ctx.beginPath()
        ctx.moveTo(this.tx(vr.waypoints[0].x), this.ty(vr.waypoints[0].y))
        for (let i = 1; i < vr.waypoints.length; i++) {
          ctx.lineTo(this.tx(vr.waypoints[i].x), this.ty(vr.waypoints[i].y))
        }
        ctx.stroke()
        ctx.strokeStyle = 'rgba(255, 60, 60, 0.5)'
        ctx.lineWidth = 3
        ctx.beginPath()
        ctx.moveTo(this.tx(vr.waypoints[0].x), this.ty(vr.waypoints[0].y))
        for (let i = 1; i < vr.waypoints.length; i++) {
          ctx.lineTo(this.tx(vr.waypoints[i].x), this.ty(vr.waypoints[i].y))
        }
        ctx.stroke()
      }

      // 从左到右排序，在每条竖直线的顶部添加标注
      vertLabels.sort((a, b) => a.x - b.x)
      ctx.save()
      for (const vl of vertLabels) {
        const labelX = this.tx(vl.x)
        const labelY = this.ty(vl.yTop) - 6
        ctx.fillStyle = '#ffd54f'
        ctx.font = 'bold 9px monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText(vl.label, labelX, labelY)
      }
      ctx.restore()
    },

    drawAirplanes() {
      const canvas = this.$refs.canvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')

      // 绘制所有预设滑行路径（红线）
      if (this.showTaxiPaths) {
        this.drawTaxiPaths(ctx)
      }

      if (this.airplanes.length === 0) return

      for (const plane of this.airplanes) {
        if (plane.alpha <= 0 || plane.status === 'IN_FLIGHT') continue
        const sx = this.tx(plane.x)
        const sy = this.ty(plane.y)
        const size = 24 * plane.scale
        const isRunway = plane.status === 'TAKING_OFF' || plane.status === 'LANDING'

        // 使用预加载的飞机俯视图 SVG
        if (this._airplaneImg && this._airplaneImg.complete) {
          ctx.save()
          ctx.globalAlpha = plane.alpha
          ctx.translate(sx, sy)
          // SVG 机头在右上角（对角线方向），校正 +π/4 使 angle=0 时机头向右
          ctx.rotate(plane.angle + Math.PI / 4)
          const imgSize = size * 1.25
          ctx.drawImage(this._airplaneImg, -imgSize / 2, -imgSize / 2, imgSize, imgSize)
          ctx.restore()
          continue
        }

        // 回退：canvas 手绘（图片未加载时）

        ctx.save()
        ctx.globalAlpha = plane.alpha
        ctx.translate(sx, sy)
        ctx.rotate(plane.angle)

        // 机身
        ctx.fillStyle = '#e0e0e0'
        ctx.beginPath()
        ctx.moveTo(size * 1.2, 0)
        ctx.lineTo(-size * 0.3, -size * 0.18)
        ctx.lineTo(-size * 0.45, -size * 0.08)
        ctx.lineTo(-size * 0.45, size * 0.08)
        ctx.lineTo(-size * 0.3, size * 0.18)
        ctx.closePath()
        ctx.fill()
        ctx.strokeStyle = '#888'
        ctx.lineWidth = 1
        ctx.stroke()

        // 机翼
        ctx.fillStyle = '#ccc'
        ctx.beginPath()
        ctx.moveTo(size * 0.3, 0)
        ctx.lineTo(size * 0.1, -size * 0.45)
        ctx.lineTo(-size * 0.05, -size * 0.4)
        ctx.lineTo(size * 0.05, -size * 0.02)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()

        ctx.beginPath()
        ctx.moveTo(size * 0.3, 0)
        ctx.lineTo(size * 0.1, size * 0.45)
        ctx.lineTo(-size * 0.05, size * 0.4)
        ctx.lineTo(size * 0.05, size * 0.02)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()

        // 尾翼
        ctx.fillStyle = '#bbb'
        ctx.beginPath()
        ctx.moveTo(-size * 0.3, 0)
        ctx.lineTo(-size * 0.4, -size * 0.3)
        ctx.lineTo(-size * 0.5, -size * 0.3)
        ctx.lineTo(-size * 0.35, 0)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()

        // 引擎小标
        ctx.fillStyle = '#fff'
        ctx.beginPath()
        ctx.arc(size * 0.05, -size * 0.15, size * 0.1, 0, Math.PI * 2)
        ctx.arc(size * 0.05, size * 0.15, size * 0.1, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = '#666'
        ctx.lineWidth = 0.6
        ctx.stroke()

        // 航行灯（跑道上闪烁）
        if (isRunway) {
          const blink = Math.sin(Date.now() / 200) > 0
          ctx.fillStyle = blink ? '#ff0000' : '#ff4444'
          ctx.beginPath()
          ctx.arc(size * 0.15, 0, size * 0.08, 0, Math.PI * 2)
          ctx.fill()
          ctx.fillStyle = blink ? '#00ff00' : '#44ff44'
          ctx.beginPath()
          ctx.arc(-size * 0.35, 0, size * 0.06, 0, Math.PI * 2)
          ctx.fill()
        }

        // 航班号
        ctx.rotate(-plane.angle)
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 9px monospace'
        ctx.textAlign = 'center'
        const statusLabels = {
          PRELOADED_AT_GATE: '待命', AT_GATE: '停机', AT_GATE_IDLE: '待命',
          TAXIING_TO_GATE: '转场', TAXIING: '滑行', TAKING_OFF: '起飞',
          LANDING: '降落', AWAITING_ARRIVAL: '等待降落',
        }
        ctx.fillText(`${plane.flightNo} (${plane.tailNo || ''}) ${statusLabels[plane.status] || ''}`, 0, -size * 0.55)
        ctx.fillText(plane.assignedRunway || '', 0, -size * 0.55 - 11)

        ctx.restore()
      }
    },

    // ========== 原有更新方法（保留） ==========

    updatePassengers() {
      // 已由 simTick 驱动，保留空方法兼容
    },

    // 绘制走廊底色
    drawCorridors() {
      const canvas = this.$refs.canvas
      if (!canvas || !this.routeCorridors) return
      const ctx = canvas.getContext('2d')

      for (const rc of this.routeCorridors) {
        if (!rc.waypoints || rc.waypoints.length < 2) continue
        ctx.save()
        ctx.strokeStyle = rc.color + '20'
        ctx.lineWidth = this.tw(rc.width)
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        ctx.beginPath()
        const sx0 = this.tx(rc.waypoints[0].x), sy0 = this.ty(rc.waypoints[0].y)
        ctx.moveTo(sx0, sy0)
        for (let i = 1; i < rc.waypoints.length; i++) {
          const sx = this.tx(rc.waypoints[i].x), sy = this.ty(rc.waypoints[i].y)
          ctx.lineTo(sx, sy)
        }
        ctx.stroke()
        ctx.restore()
      }

      // 标注有名称的路线
      for (const rc of this.routeCorridors) {
        if (!rc.waypoints || rc.waypoints.length < 2 || !rc.label) continue
        const midIdx = Math.floor(rc.waypoints.length / 2)
        const mx = this.tx(rc.waypoints[midIdx].x)
        const my = this.ty(rc.waypoints[midIdx].y)
        ctx.save()
        ctx.fillStyle = '#ffeb3b'
        ctx.font = 'bold 9px monospace'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(rc.label, mx, my - 4)
        ctx.restore()
      }
    },

    // ========== 候机区人数标注 ==========

    drawWaitingStats() {
      const canvas = this.$refs.canvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')

      // 统计各航站楼候机人数和登机中人数
      const t1Waiting = this.passengers.filter(p => (p.status === 'waiting' || p.status === 'entering') && p.terminal === 'T1').length
      const t2Waiting = this.passengers.filter(p => (p.status === 'waiting' || p.status === 'entering') && p.terminal === 'T2').length
      const t1Boarding = this.passengers.filter(p => p.status === 'walking' && p.terminal === 'T1' && p.type === 'inbound').length
      const t2Boarding = this.passengers.filter(p => p.status === 'walking' && p.terminal === 'T2' && p.type === 'inbound').length

      for (const [name, tc] of Object.entries(this.terminalCenters)) {
        const isT1 = name === '航站楼1'
        const waiting = isT1 ? t1Waiting : t2Waiting
        const boarding = isT1 ? t1Boarding : t2Boarding
        if (waiting + boarding === 0) continue

        const sx = this.tx(tc.x)
        const sy = this.ty(tc.y - tc.h * 0.35)

        ctx.save()
        // 半透明背景
        const lines = [`候机: ${waiting} 人`, `登机中: ${boarding} 人`]
        const fontSize = 11
        ctx.font = `bold ${fontSize}px sans-serif`
        const maxW = Math.max(...lines.map(l => ctx.measureText(l).width))
        const boxH = lines.length * (fontSize + 4) + 8
        ctx.fillStyle = 'rgba(0,0,0,0.65)'
        ctx.strokeStyle = 'rgba(255,255,255,0.3)'
        ctx.lineWidth = 1
        const rx = 4
        const bx = sx - maxW / 2 - 8
        const by = sy - boxH / 2
        ctx.beginPath()
        ctx.moveTo(bx + rx, by)
        ctx.lineTo(bx + maxW + 16 - rx, by)
        ctx.quadraticCurveTo(bx + maxW + 16, by, bx + maxW + 16, by + rx)
        ctx.lineTo(bx + maxW + 16, by + boxH - rx)
        ctx.quadraticCurveTo(bx + maxW + 16, by + boxH, bx + maxW + 16 - rx, by + boxH)
        ctx.lineTo(bx + rx, by + boxH)
        ctx.quadraticCurveTo(bx, by + boxH, bx, by + boxH - rx)
        ctx.lineTo(bx, by + rx)
        ctx.quadraticCurveTo(bx, by, bx + rx, by)
        ctx.closePath()
        ctx.fill()
        ctx.stroke()

        // 文字
        ctx.fillStyle = '#fff'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(name, sx, by + fontSize / 2 + 4)
        ctx.font = `${fontSize - 1}px sans-serif`
        for (let i = 0; i < lines.length; i++) {
          ctx.fillStyle = '#aaa'
          ctx.fillText(lines[i], sx, by + (i + 1) * (fontSize + 2) + 6)
        }

        ctx.restore()
      }
    },

    // ========== 旅客渲染 ==========

    drawPassengers() {
      const canvas = this.$refs.canvas
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const dense = this.passengers.length > 300

      // 按颜色/状态分组，每组一次性 fill：上千名旅客时避免上千次 arc+fill+stroke 拖垮合成
      // 两次模拟 tick 之间按时间比例插值，画面刷新 60fps，旅客不再每 200ms 跳一格
      const tickGap = this._lastTickInterval || 200
      const tickFrac = this._lastTickAt
        ? Math.min(1, Math.max(0, (performance.now() - this._lastTickAt) / tickGap))
        : 1

      const groups = new Map()
      for (const p of this.passengers) {
        let sx, sy
        if (p.status === 'waiting') {
          sx = this.tx(p.waitX)
          sy = this.ty(p.waitY)
        } else {
          const rc = this.routeCorridors[p.corridorIdx]
          if (!rc) continue
          const wps = p.waypoints || rc.waypoints
          let prog = p.progress
          if (tickFrac < 1 && p._prevProgress != null && p.status !== 'arrived' && Math.abs(p.progress - p._prevProgress) < 0.3) {
            prog = p._prevProgress + (p.progress - p._prevProgress) * tickFrac
          }
          const pos = this.interpolateRoute(wps, prog, p.laneOffset, (p.waypoints ? 5 : rc.width) * 0.85)
          sx = this.tx(pos.x)
          sy = this.ty(pos.y)
        }
        const key = p.status === 'waiting' ? p.color + '|w' : p.color
        let arr = groups.get(key)
        if (!arr) { arr = []; groups.set(key, arr) }
        arr.push(sx, sy)
      }

      for (const [key, pts] of groups) {
        const waiting = key.endsWith('|w')
        const color = waiting ? key.slice(0, -2) : key
        const r = waiting ? 4 : 3
        ctx.beginPath()
        for (let i = 0; i < pts.length; i += 2) {
          ctx.moveTo(pts[i] + r, pts[i + 1])
          ctx.arc(pts[i], pts[i + 1], r, 0, Math.PI * 2)
        }
        ctx.fillStyle = color
        ctx.fill()
        if (!dense) {
          ctx.strokeStyle = waiting ? '#ffffcc' : '#fff'
          ctx.lineWidth = waiting ? 1.0 : 0.6
          ctx.stroke()
        }
      }

      // 候机光晕只在人数较少时绘制（人多了视觉上也分不出来）
      if (!dense) {
        const now = Date.now()
        for (const p of this.passengers) {
          if (p.status !== 'waiting') continue
          const pulse = 0.7 + 0.3 * Math.sin(now / 600 + (p.id || '0').charCodeAt(0 || 0))
          const sx = this.tx(p.waitX)
          const sy = this.ty(p.waitY)
          ctx.beginPath()
          ctx.arc(sx, sy, 8, 0, Math.PI * 2)
          ctx.fillStyle = p.color + Math.floor(30 * pulse).toString(16).padStart(2, '0')
          ctx.fill()
        }
      }
    },

    // 沿路径插值，支持侧向偏移（多车道）
    interpolateRoute(waypoints, t, laneOffset, corridorWidth) {
      if (!waypoints || waypoints.length < 2) return waypoints[0] || { x: 0, y: 0 }
      const totalSegs = waypoints.length - 1
      const segFloat = t * totalSegs
      const segIdx = Math.min(Math.floor(segFloat), totalSegs - 1)
      const segT = segFloat - segIdx
      const a = waypoints[segIdx]
      const b = waypoints[segIdx + 1]

      // 中心点
      const cx = a.x + (b.x - a.x) * segT
      const cy = a.y + (b.y - a.y) * segT

      // 侧向偏移（垂直方向）
      if (laneOffset !== 0 && corridorWidth > 0) {
        const dx = b.x - a.x
        const dy = b.y - a.y
        const len = Math.sqrt(dx * dx + dy * dy)
        if (len > 0.01) {
          const px = -dy / len  // 垂直方向 x
          const py = dx / len   // 垂直方向 y
          const offset = laneOffset * corridorWidth * 0.5
          return { x: cx + px * offset, y: cy + py * offset }
        }
      }
      return { x: cx, y: cy }
    },

    onResize() {
      this.initCanvas()
      this.drawAll()
    },
  },
}
</script>

<style scoped>
.terminal-layout {
  position: absolute;
  top: 0;
  left: 0;
  overflow: hidden;
  background: #1a1a2e;
}

.layout-canvas {
  display: block;
  cursor: grab;
}

.layout-canvas:active {
  cursor: grabbing;
}

.zoom-hint {
  position: absolute;
  right: 10px;
  bottom: 8px;
  padding: 2px 8px;
  font-size: 11px;
  color: rgba(205, 214, 244, 0.55);
  background: rgba(10, 15, 30, 0.55);
  border-radius: 4px;
  pointer-events: none;
  user-select: none;
}
</style>
