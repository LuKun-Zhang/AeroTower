<template>
  <div v-title data-title="航班旅客明细" class="flight-pax-page">
    <div class="page-header">
      <el-button icon="el-icon-arrow-left" size="small" @click="$router.back()">返回</el-button>
      <h2>航班旅客明细 — {{ flightNo }}</h2>
      <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
      <el-radio-group v-model="viewMode" size="small" class="view-toggle">
        <el-radio-button label="3d">3D 机舱视图</el-radio-button>
        <el-radio-button label="2d">2D 座位图</el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="!flight" class="empty-state">
      <p>未找到该航班信息</p>
    </div>

    <template v-else>
      <!-- 统计 -->
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.occupied }}</div>
          <div class="kpi-label">已售座位</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.total - stats.occupied }}</div>
          <div class="kpi-label">空座</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.business }}</div>
          <div class="kpi-label">公务舱</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.economy }}</div>
          <div class="kpi-label">经济舱</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ ((stats.occupied / stats.total) * 100).toFixed(1) }}%</div>
          <div class="kpi-label">客座率</div>
        </div>
      </div>

      <div class="seat-map-section">
        <div class="seat-map-legend">
          <span class="legend-item"><span class="dot occupied"></span> 已分配</span>
          <span class="legend-item"><span class="dot empty"></span> 空座</span>
          <span class="legend-item"><span class="dot business"></span> 公务舱</span>
        </div>

        <!-- 3D 机舱视图：A320 模型为背景 + 座位覆盖 -->
        <div v-show="viewMode === '3d'" class="seat3d-wrap">
          <div class="view-toolbar">
            <el-button-group size="mini">
              <el-button size="mini" @click="setView('quarter')">斜视</el-button>
              <el-button size="mini" @click="setView('top')">俯视</el-button>
              <el-button size="mini" @click="setView('side')">侧视</el-button>
              <el-button size="mini" @click="setView('front')">正视</el-button>
              <el-button size="mini" @click="setView('reset')">复位</el-button>
            </el-button-group>
            <el-button size="mini" @click="toggleRotate">{{ autoRotate ? '暂停旋转' : '自动旋转' }}</el-button>
            <el-button size="mini" @click="flipSeats">翻转机头</el-button>
            <span class="seat3d-hint">拖拽旋转 · 滚轮缩放 · 点击座位查看旅客</span>
          </div>
          <div class="seat3d-canvas" ref="seat3d">
            <div class="seat3d-loading" v-if="modelLoading">{{ flight?.ac_type || 'A320' }} 模型加载中…</div>
            <div class="seat3d-error" v-if="modelError">模型加载失败：{{ modelError }}</div>
            <div class="seat3d-info" v-if="selectedSeat">{{ selectedSeat }}</div>
          </div>
        </div>

        <!-- 2D 座位图（排数/列数按航班机型 layout 动态渲染） -->
        <div v-show="viewMode === '2d'" class="seat-map">
          <div class="cabin-section" v-if="businessSeats > 0">
            <div class="cabin-label">公务舱 (C{{ businessSeats }})</div>
            <div v-for="row in businessRows" :key="'b'+row" class="seat-row">
              <template v-for="col in ['A','C','D','F']">
                <div
                  :key="'b'+row+col"
                  class="seat"
                  :class="{
                    occupied: seats[row+col],
                    empty: !seats[row+col],
                    business: true,
                  }"
                  :title="seats[row+col] || '空座'"
                >
                  {{ row }}{{ col }}
                  <span class="seat-pax" v-if="seats[row+col]">{{ seats[row+col] }}</span>
                </div>
              </template>
            </div>
          </div>
          <div class="cabin-section">
            <div class="cabin-label">经济舱 (Y{{ economySeats }})</div>
            <div v-for="row in economyRows" :key="'e'+row" class="seat-row">
              <template v-for="col in economyColsOf(row)">
                <div
                  :key="'e'+row+col"
                  class="seat"
                  :class="{
                    occupied: seats[row+col],
                    empty: !seats[row+col],
                  }"
                  :title="seats[row+col] || '空座'"
                >
                  {{ row }}{{ col }}
                  <span class="seat-pax" v-if="seats[row+col]">{{ seats[row+col] }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="航班旅客明细" />
  </div>
</template>

<script>
import ChartOverlay from '@/components/ChartOverlay'
import { buildFlightPassengersCharts } from '@/utils/charts/flightPassengers'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'

// 机型 → 3D 模型文件 / 机身相对长度（与后端 aircraft_types.py 保持一致）
const MODEL_MAP = {
  A319: { glb: '/models/a319.glb', fuselage: 12.6 },
  A320: { glb: '/models/A320.glb', fuselage: 14.0 },
  A321: { glb: '/models/a321.glb', fuselage: 16.6 },
}
const BUSINESS_COLS = ['A', 'C', 'D', 'F']   // 公务舱 2-2 列
const ECONOMY_COLS = ['A', 'B', 'C', 'D', 'E', 'F']  // 经济舱 3-3 列
const NOSE_MARGIN = 2.4         // 机头端（驾驶舱）留空
const TAIL_MARGIN = 1.6         // 机尾端留空

export default {
  name: 'FlightPassengers',
  components: { ChartOverlay },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      flight: null,
      seats: {},
      stats: { total: 0, occupied: 0, business: 0, economy: 0 },
      viewMode: '3d',
      modelLoading: false,
      modelError: '',
      selectedSeat: '',
      autoRotate: false,
    }
  },
  computed: {
    flightId() { return this.$route.params.flightId },
    flightNo() { return this.flight?.flight_no || '' },
    // 座位布局解析：'C8Y124' → { C: 8, Y: 124 }（与后端 aircraft_types 同口径）
    parsedLayout() {
      const m = {}
      const s = (this.flight && this.flight.layout) || 'C8Y124'
      ;(s.match(/[CY]\d+/g) || []).forEach(part => { m[part[0]] = parseInt(part.slice(1)) })
      return { C: m.C || 0, Y: m.Y || 0 }
    },
    businessSeats() { return this.parsedLayout.C },
    economySeats() { return this.parsedLayout.Y },
    businessRows() {
      const rows = []
      for (let r = 1; r <= Math.floor(this.businessSeats / 4); r++) rows.push(r)
      return rows
    },
    economyRows() {
      const rows = []
      const n = Math.ceil(this.economySeats / 6)
      const start = this.businessRows.length + 1
      for (let r = start; r < start + n; r++) rows.push(r)
      return rows
    },
    economyLastCols() {
      const n = Math.ceil(this.economySeats / 6)
      return this.economySeats - (n - 1) * 6
    },
    modelInfo() {
      return MODEL_MAP[this.flight && this.flight.ac_type] || MODEL_MAP.A320
    },
  },
  watch: {
    viewMode(val) {
      if (val === '3d') {
        this.$nextTick(() => {
          this.ensure3D()
          this.onResize3D()
        })
      }
    },
  },
  methods: {
    openCharts() {
      this.chartList = buildFlightPassengersCharts(this)
      this.chartsOpen = true
    },
    economyColsOf(row) {
      if (this.economyRows.length && row === this.economyRows[this.economyRows.length - 1]) {
        return ECONOMY_COLS.slice(0, this.economyLastCols)
      }
      return ECONOMY_COLS
    },
    async loadData() {
      try {
        const res = await fetch(`/api/generate/data?type=flights&flight_id=${this.flightId}`)
        const json = await res.json()
        if (json.code !== 0 || !json.data) return
        this.flight = json.data

        const manifest = this.flight.passenger_manifest || {}
        this.seats = {}
        for (const [seat, pid] of Object.entries(manifest)) {
          this.seats[seat] = pid
        }

        const occupied = Object.values(manifest).filter(Boolean).length
        let business = 0
        for (const row of this.businessRows) {
          for (const col of BUSINESS_COLS) {
            if (manifest[row + col]) business++
          }
        }
        this.stats = {
          total: this.businessSeats + this.economySeats,
          occupied,
          business,
          economy: occupied - business,
        }

        // 3D 场景若已就绪，按最新数据重建座位
        if (this._modelReady) this.buildSeats()

        // 首次进入默认 3D 视图：等 DOM 可见后初始化场景
        this.$nextTick(() => {
          this.ensure3D()
          this.onResize3D()
        })
      } catch (e) {
        console.error('加载航班数据失败:', e)
      }
    },

    /* ---------------- 3D 场景 ---------------- */

    ensure3D() {
      if (this._renderer) return
      const el = this.$refs.seat3d
      if (!el || el.clientWidth === 0) return

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setSize(el.clientWidth, el.clientHeight)
      renderer.toneMapping = THREE.ACESFilmicToneMapping
      renderer.toneMappingExposure = 1.2
      el.appendChild(renderer.domElement)
      this._renderer = renderer

      const scene = new THREE.Scene()
      scene.background = new THREE.Color(0x141428)
      this._scene = scene

      const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.1, 100)
      camera.position.set(9, 5, 10)
      this._camera = camera

      const controls = new OrbitControls(camera, renderer.domElement)
      controls.enableDamping = true
      controls.dampingFactor = 0.08
      controls.minDistance = 4
      controls.maxDistance = 30
      controls.target.set(0, 0, 0)
      this._controls = controls

      // 灯光
      scene.add(new THREE.AmbientLight(0x8899bb, 0.7))
      const sun = new THREE.DirectionalLight(0xffffff, 1.2)
      sun.position.set(8, 12, 6)
      scene.add(sun)
      const fill = new THREE.DirectionalLight(0x88aaff, 0.4)
      fill.position.set(-6, -2, -4)
      scene.add(fill)

      // 底部参考网格
      const grid = new THREE.GridHelper(22, 22, 0x334466, 0x222244)
      grid.position.y = -2.2
      scene.add(grid)

      renderer.domElement.addEventListener('click', this.onSeatClick)
      renderer.domElement.addEventListener('mousemove', this.onSeatHover)
      window.addEventListener('resize', this.onResize3D)

      this.loadModel()
      this.animate3D()
    },

    loadModel() {
      this.modelLoading = true
      this.modelError = ''
      const loader = new GLTFLoader()
      const draco = new DRACOLoader()
      draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
      loader.setDRACOLoader(draco)

      const modelPath = this.modelInfo.glb
      const fuselageLen = this.modelInfo.fuselage
      this._fuselageLen = fuselageLen

      loader.load(
        modelPath,
        (gltf) => {
          const plane = gltf.scene

          // 半透明机身作为背景，座位可透过机身看到
          plane.traverse((o) => {
            if (o.isMesh) {
              const mats = Array.isArray(o.material) ? o.material : [o.material]
              mats.forEach((m) => {
                if (!m) return
                m.transparent = true
                m.opacity = 0.2
                m.depthWrite = false
                m.side = THREE.DoubleSide
              })
            }
          })

          // 包围盒 → 居中对齐到原点
          const box = new THREE.Box3().setFromObject(plane)
          const center = box.getCenter(new THREE.Vector3())
          plane.position.set(-center.x, -center.y, -center.z)

          // 机身轴向判别：机翼沿轴高度对称、机身沿轴（机头尖/尾翼钝）不对称。
          // 不能用「较长轴即机身」——A319 机身长 ≈ 翼展，会误判旋转 90°。
          const alongX = this.fuselageAlongX(plane)
          if (alongX) plane.rotation.y = Math.PI / 2

          // 缩放：机身长度 = 机型对应长度
          const box2 = new THREE.Box3().setFromObject(plane)
          const size2 = box2.getSize(new THREE.Vector3())
          const scale = fuselageLen / size2.z
          plane.scale.setScalar(scale)

          // 缩放后再次居中：世界中心即对象位置 + 旋转/缩放后的局部几何中心偏移，
          // 直接减去世界中心才能把模型几何中心归零
          const box3 = new THREE.Box3().setFromObject(plane)
          const c3 = box3.getCenter(new THREE.Vector3())
          plane.position.sub(c3)

          // 机头朝向检测（+Z 或 -Z）：统计机身两端最外侧 30% 的顶点平均半径，
          // 半径更小（收敛的锥形）的一端为机头
          this._noseAtPlusZ = this.detectNose(plane, fuselageLen / 2)

          this._scene.add(plane)
          this._modelReady = true
          this.modelLoading = false

          this.buildSeats()
        },
        undefined,
        (err) => {
          console.error(`${this.flight && this.flight.ac_type} 模型加载失败:`, err)
          this.modelLoading = false
          this.modelError = err && err.message ? err.message : '未知错误'
        }
      )
    },

    fuselageAlongX(plane) {
      // 统计全部顶点在水平两轴两侧的分布：机翼轴对称（两侧翼面相似），
      // 机身轴不对称（机头收敛 vs 尾翼钝）。取不对称性更大的水平轴为机身轴。
      // 注意：调用前 plane 已居中（position = -bbox 中心），故按世界原点分割。
      const v = new THREE.Vector3()
      const acc = {
        x: { neg: 0, pos: 0, cNeg: 0, cPos: 0 },
        z: { neg: 0, pos: 0, cNeg: 0, cPos: 0 },
      }
      let count = 0
      plane.updateMatrixWorld(true)
      plane.traverse((o) => {
        if (!o.isMesh || !o.geometry) return
        const pos = o.geometry.attributes.position
        if (!pos) return
        const m = o.matrixWorld
        for (let i = 0; i < pos.count; i++) {
          v.set(pos.getX(i), pos.getY(i), pos.getZ(i)).applyMatrix4(m)
          count++
          if (v.x < 0) { acc.x.neg += v.x; acc.x.cNeg++ } else { acc.x.pos += v.x; acc.x.cPos++ }
          if (v.z < 0) { acc.z.neg += v.z; acc.z.cNeg++ } else { acc.z.pos += v.z; acc.z.cPos++ }
        }
      })
      if (count === 0) {
        // 无几何数据时回退：取较长轴为机身轴
        const box = new THREE.Box3().setFromObject(plane)
        const size = box.getSize(new THREE.Vector3())
        return size.x >= size.z
      }
      const asym = (a) => {
        const negM = a.cNeg ? -a.neg / a.cNeg : 0
        const posM = a.cPos ? a.pos / a.cPos : 0
        return Math.abs(posM - negM) / Math.max(posM, negM, 1e-6)
      }
      return asym(acc.x) > asym(acc.z)
    },

    detectNose(plane, halfLen) {
      plane.updateMatrixWorld(true)
      const v = new THREE.Vector3()
      let rPos = 0, rNeg = 0, cntPos = 0, cntNeg = 0
      plane.traverse((o) => {
        if (!o.isMesh || !o.geometry) return
        const pos = o.geometry.attributes.position
        if (!pos) return
        const m = o.matrixWorld
        const limit = halfLen * 0.7
        for (let i = 0; i < pos.count; i++) {
          v.set(pos.getX(i), pos.getY(i), pos.getZ(i)).applyMatrix4(m)
          const r = Math.sqrt(v.x * v.x + v.y * v.y)
          if (v.z > limit) { rPos += r; cntPos++ }
          else if (v.z < -limit) { rNeg += r; cntNeg++ }
        }
      })
      if (cntPos === 0 || cntNeg === 0) return true
      return (rPos / cntPos) <= (rNeg / cntNeg)
    },

    buildSeats() {
      if (!this._modelReady || !this._scene) return

      // 清理旧座位
      ;(this._seatMeshes || []).forEach((m) => {
        this._scene.remove(m)
        m.geometry.dispose()
        m.material.dispose()
      })
      this._seatMeshes = []
      this._selectedMesh = null
      this.selectedSeat = ''

      const fuselageLen = this._fuselageLen || this.modelInfo.fuselage
      const halfLen = fuselageLen / 2
      const nosePlus = this._noseAtPlusZ ? !this._flip : this._flip
      const z1 = nosePlus ? halfLen - NOSE_MARGIN : -halfLen + TAIL_MARGIN
      const dir = nosePlus ? -1 : 1
      const totalRows = this.businessRows.length + this.economyRows.length
      const pitch = ((halfLen - NOSE_MARGIN) - (-(halfLen - TAIL_MARGIN))) / Math.max(1, totalRows - 1)
      // 实测校准（A320.glb，机身长度缩放为 14 后）：
      // 机身主体垂直中心 y=-0.93（包围盒被垂直尾翼/起落架撑开，需用机身本体实测值）
      // 机身半径 0.77 → 座位放在机身内靠下的客舱地板高度
      const fusR = 0.77
      const fusCenterY = -0.93
      const seatY = fusCenterY - fusR * 0.45
      const cabinHalfW = fusR * 0.72   // 机舱半宽（小于机身半径，保证座位在舱内）

      const businessCount = this.businessRows.length
      const lastRow = totalRows
      for (let r = 1; r <= totalRows; r++) {
        const isBusiness = r <= businessCount
        let cols
        if (isBusiness) cols = BUSINESS_COLS
        else if (r === lastRow) cols = ECONOMY_COLS.slice(0, this.economyLastCols)
        else cols = ECONOMY_COLS
        const n = cols.length
        const z = z1 + (r - 1) * pitch * dir

        cols.forEach((col, i) => {
          const seatName = `${r}${col}`
          const pid = this.seats[seatName]
          const occupied = !!pid
          const x = -cabinHalfW + (i + 0.5) * ((2 * cabinHalfW) / n)

          const color = isBusiness ? 0xe6a23c : (occupied ? 0x67c23a : 0x3d3d5c)
          const geo = new THREE.BoxGeometry(
            isBusiness ? 0.22 : 0.18,
            isBusiness ? 0.09 : 0.07,
            pitch * (isBusiness ? 0.85 : 0.75)
          )
          const mat = new THREE.MeshPhongMaterial({ color })
          const mesh = new THREE.Mesh(geo, mat)
          mesh.position.set(x, seatY, z)
          mesh.userData = { seat: seatName, pid, occupied, business: isBusiness, color }
          this._scene.add(mesh)
          this._seatMeshes.push(mesh)
        })
      }
    },

    /* ---------------- 交互 ---------------- */

    onSeatClick(e) {
      const hit = this.pickSeat(e)
      if (!hit) {
        this.clearSelected()
        return
      }
      const ud = hit.object.userData
      if (this._selectedMesh && this._selectedMesh !== hit.object) this.clearSelected()
      this._selectedMesh = hit.object
      hit.object.material.emissive.set(0x88ccff)
      hit.object.scale.setScalar(1.25)
      this.selectedSeat = `${ud.seat} — ${ud.pid ? '旅客 ' + ud.pid : '空座'}`
    },

    onSeatHover(e) {
      if (!this._renderer || !this._seatMeshes || !this._seatMeshes.length) return
      const hit = this.pickSeat(e)
      this._renderer.domElement.style.cursor = hit ? 'pointer' : 'grab'
    },

    pickSeat(e) {
      const el = this.$refs.seat3d
      if (!el || !this._camera) return null
      const rect = el.getBoundingClientRect()
      const mouse = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1
      )
      const raycaster = new THREE.Raycaster()
      raycaster.setFromCamera(mouse, this._camera)
      const hits = raycaster.intersectObjects(this._seatMeshes, false)
      return hits.length ? hits[0] : null
    },

    clearSelected() {
      if (this._selectedMesh) {
        this._selectedMesh.material.emissive.set(0x000000)
        this._selectedMesh.scale.setScalar(1)
        this._selectedMesh = null
      }
      this.selectedSeat = ''
    },

    /* ---------------- 视角控制 ---------------- */

    setView(view) {
      const controls = this._controls
      if (!controls) return
      const pos = {
        quarter: { x: 9, y: 5, z: 10 },
        top: { x: 0.01, y: 13, z: 0.01 },
        side: { x: 13, y: 0.6, z: 0 },
        front: { x: 0, y: 1.2, z: 13 },
        reset: { x: 9, y: 5, z: 10 },
      }[view]
      if (!pos) return
      controls.target.set(0, 0, 0)
      this._camera.position.set(pos.x, pos.y, pos.z)
      controls.update()
    },

    toggleRotate() {
      this.autoRotate = !this.autoRotate
      if (this._controls) this._controls.autoRotate = this.autoRotate
    },

    flipSeats() {
      this._flip = !this._flip
      this.buildSeats()
    },

    /* ---------------- 生命周期 ---------------- */

    animate3D() {
      this._raf = requestAnimationFrame(this.animate3D)
      if (!this._renderer || !this._scene || !this._camera) return
      if (this._renderer.domElement.clientWidth === 0) return
      if (this._controls) this._controls.update()
      this._renderer.render(this._scene, this._camera)
    },

    onResize3D() {
      const el = this.$refs.seat3d
      if (!el || !this._camera || !this._renderer) return
      if (el.clientWidth === 0 || el.clientHeight === 0) return
      this._camera.aspect = el.clientWidth / el.clientHeight
      this._camera.updateProjectionMatrix()
      this._renderer.setSize(el.clientWidth, el.clientHeight)
    },
  },
  mounted() {
    this.loadData()
  },
  beforeDestroy() {
    cancelAnimationFrame(this._raf)
    window.removeEventListener('resize', this.onResize3D)
    if (this._renderer) {
      this._renderer.domElement.removeEventListener('click', this.onSeatClick)
      this._renderer.domElement.removeEventListener('mousemove', this.onSeatHover)
      this._renderer.dispose()
      if (this.$refs.seat3d && this._renderer.domElement.parentNode) {
        this.$refs.seat3d.removeChild(this._renderer.domElement)
      }
    }
  },
}
</script>

<style scoped>
.flight-pax-page {
  padding: 20px 30px;
  background: #141428;
  min-height: 100vh;
  height: 100vh;
  overflow-y: auto;
  color: #cdd6f4;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}
.page-header h2 { margin: 0; color: #fff; }
.view-toggle { margin-left: auto; }
.kpi-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.kpi-card {
  flex: 1;
  background: #1e1e2e;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.kpi-value {
  font-size: 24px;
  font-weight: 700;
  color: #ffd54f;
  font-family: 'Courier New', monospace;
}
.kpi-label {
  font-size: 12px;
  color: #8a8aaa;
}
.seat-map-section {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 20px;
}
.seat-map-section h3 { margin: 0 0 12px 0; font-size: 14px; color: #8a8aaa; }
.seat-map-legend {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  font-size: 12px;
  color: #8a8aaa;
}
.dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
.dot.occupied { background: #67c23a; }
.dot.empty { background: #3d3d5c; }
.dot.business { background: #e6a23c; }
.legend-item { display: inline-flex; align-items: center; }

/* ---- 3D 机舱视图 ---- */
.seat3d-wrap {
  display: flex;
  flex-direction: column;
}
.view-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.seat3d-hint {
  font-size: 12px;
  color: #6a6a8a;
  margin-left: 4px;
}
.seat3d-canvas {
  position: relative;
  width: 100%;
  height: 560px;
  border-radius: 8px;
  overflow: hidden;
  background: #141428;
}
.seat3d-canvas canvas { display: block; }
.seat3d-loading,
.seat3d-error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 13px;
  color: #8a8aaa;
  z-index: 2;
}
.seat3d-error { color: #f56c6c; }
.seat3d-info {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(20, 20, 40, 0.85);
  border: 1px solid #3355aa;
  font-size: 13px;
  color: #9fc1ff;
  z-index: 2;
}

/* ---- 2D 座位图 ---- */
.seat-map {
  max-height: 600px;
  overflow-y: auto;
}
.cabin-section { margin-bottom: 16px; }
.cabin-label {
  font-size: 13px;
  font-weight: 700;
  color: #8a8aaa;
  margin-bottom: 8px;
}
.seat-row {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
  justify-content: center;
}
.seat {
  width: 60px; height: 32px;
  border-radius: 4px;
  font-size: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}
.seat.occupied { background: #2d6a2d; color: #67c23a; }
.seat.empty { background: #2d2d44; color: #4a4a6a; }
.seat.business { border: 1px solid #e6a23c; }
.seat:hover { transform: scale(1.1); z-index: 1; }
.seat.occupied:hover { background: #3d8a3d; }
.seat-pax {
  font-size: 8px;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 54px;
}
.empty-state { text-align: center; padding: 80px; color: #8a8aaa; }
</style>
