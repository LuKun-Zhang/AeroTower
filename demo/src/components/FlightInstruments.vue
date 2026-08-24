<template>
  <div class="instruments-overlay" v-if="visible" @click.self="$emit('close')">
    <div class="instruments-panel">
      <div class="panel-header">
        <span class="flight-label">✈ {{ data.flightNo || '--' }}</span>
        <span class="phase-tag" :class="'phase-' + phase">{{ phaseLabel }}</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>
      <div class="gauges-grid">
        <!-- 空速表 -->
        <div class="gauge-box">
          <canvas ref="asiCanvas" width="180" height="180"></canvas>
          <div class="gauge-label">空速 KIAS</div>
        </div>
        <!-- 姿态仪 -->
        <div class="gauge-box">
          <canvas ref="attCanvas" width="200" height="200"></canvas>
          <div class="gauge-label">姿态</div>
        </div>
        <!-- 高度表 -->
        <div class="gauge-box">
          <canvas ref="altCanvas" width="180" height="180"></canvas>
          <div class="gauge-label">高度 FT</div>
        </div>
        <!-- 航向罗盘 -->
        <div class="gauge-box">
          <canvas ref="hdgCanvas" width="180" height="180"></canvas>
          <div class="gauge-label">航向</div>
        </div>
      </div>
      <div class="digital-panel">
        <div class="digi-item">
          <span class="digi-label">升降率</span>
          <span class="digi-value" :class="vs < 0 ? 'neg' : ''">{{ vsDisplay }}</span>
        </div>
        <div class="digi-item">
          <span class="digi-label">剩余时间</span>
          <span class="digi-value">{{ etaDisplay }}</span>
        </div>
        <div class="digi-item">
          <span class="digi-label">剩余距离</span>
          <span class="digi-value">{{ distanceDisplay }}</span>
        </div>
        <div class="digi-item">
          <span class="digi-label">巡航高度</span>
          <span class="digi-value">{{ cruiseAltDisplay }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FlightInstruments',
  props: {
    visible: { type: Boolean, default: false },
    data: { type: Object, default: function() { return {} } },
  },
  data: function() {
    return {
      _animId: null,
      _lastTime: 0,
    }
  },
  computed: {
    phase: function() {
      var p = this.data.progress || 0
      if (p < 0.16) return 'climb'
      if (p < 0.84) return 'cruise'
      return 'descent'
    },
    phaseLabel: function() {
      var m = { climb: '爬升', cruise: '巡航', descent: '下降' }
      return m[this.phase] || '--'
    },
    vsDisplay: function() {
      var v = this.data.verticalSpeed || 0
      var sign = v >= 0 ? '+' : ''
      return sign + Math.round(v) + ' ft/min'
    },
    etaDisplay: function() {
      var m = this.data.timeRemaining
      if (m == null || isNaN(m)) return '--'
      if (m < 60) return Math.round(m) + 'min'
      var h = Math.floor(m / 60), rm = Math.round(m % 60)
      return h + 'h ' + rm + 'min'
    },
    distanceDisplay: function() {
      var d = this.data.distanceRemaining
      if (d == null || isNaN(d)) return '--'
      return d >= 100 ? Math.round(d) + 'km' : d.toFixed(1) + 'km'
    },
    cruiseAltDisplay: function() {
      var a = this.data.cruiseAlt
      if (!a) return '--'
      return (a / 1000).toFixed(1) + 'k ft'
    },
  },
  watch: {
    visible: function(v) {
      if (v) this._startAnim()
      else this._stopAnim()
    },
  },
  methods: {
    _startAnim: function() {
      this._stopAnim()
      this._lastTime = performance.now()
      this._drawGauges()
    },
    _stopAnim: function() {
      if (this._animId) { cancelAnimationFrame(this._animId); this._animId = null }
    },
    _drawGauges: function() {
      var self = this
      this._drawAirspeed()
      this._drawAttitude()
      this._drawAltimeter()
      this._drawHeading()
      this._animId = requestAnimationFrame(function() { self._drawGauges() })
    },

    /* ========== 空速表 ========== */
    _drawAirspeed: function() {
      var c = this.$refs.asiCanvas
      if (!c) return
      var ctx = c.getContext('2d')
      var w = c.width, h = c.height
      var cx = w / 2, cy = h / 2, r = 78
      ctx.clearRect(0, 0, w, h)

      // 背景
      ctx.save()
      this._roundBg(ctx, cx, cy, r, '#1a1a2e')

      // 速度刻度
      var maxSpd = Math.max(400, (this.data.speed || 300) * 1.4)
      maxSpd = Math.ceil(maxSpd / 50) * 50  // 取整到 50
      var spd = this.data.speed || 0
      var startAngle = Math.PI * 0.75, endAngle = Math.PI * 2.25
      var range = endAngle - startAngle

      // 彩色弧
      ctx.beginPath()
      ctx.arc(cx, cy, r - 4, startAngle, endAngle)
      ctx.strokeStyle = '#2a2a4a'
      ctx.lineWidth = 14
      ctx.stroke()

      // 绿色弧（正常范围 0-80%）
      var gEnd = startAngle + range * 0.8
      ctx.beginPath()
      ctx.arc(cx, cy, r - 4, startAngle, gEnd)
      ctx.strokeStyle = '#00e676'
      ctx.lineWidth = 6
      ctx.stroke()

      // 黄色弧 (80-95%)
      var yEnd = startAngle + range * 0.95
      ctx.beginPath()
      ctx.arc(cx, cy, r - 4, gEnd, yEnd)
      ctx.strokeStyle = '#ffd600'
      ctx.lineWidth = 6
      ctx.stroke()

      // 红色弧 (95-100%)
      ctx.beginPath()
      ctx.arc(cx, cy, r - 4, yEnd, endAngle)
      ctx.strokeStyle = '#ff1744'
      ctx.lineWidth = 6
      ctx.stroke()

      // 刻度线和数字
      var step = maxSpd <= 400 ? 50 : 100
      for (var s = 0; s <= maxSpd; s += step) {
        var ang = startAngle + (s / maxSpd) * range
        var x1 = cx + Math.cos(ang) * (r - 16)
        var y1 = cy + Math.sin(ang) * (r - 16)
        var x2 = cx + Math.cos(ang) * (r - 6)
        var y2 = cy + Math.sin(ang) * (r - 6)
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2)
        ctx.strokeStyle = '#aaa'; ctx.lineWidth = 1.5; ctx.stroke()
        var tx = cx + Math.cos(ang) * (r - 28)
        var ty = cy + Math.sin(ang) * (r - 28)
        ctx.fillStyle = '#ccc'; ctx.font = 'bold 10px monospace'
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
        ctx.fillText(Math.round(s), tx, ty)
      }

      // 指针
      var ptrAngle = startAngle + (spd / maxSpd) * range
      ptrAngle = Math.max(startAngle, Math.min(endAngle, ptrAngle))
      var ptrLen = r - 24
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx + Math.cos(ptrAngle) * ptrLen, cy + Math.sin(ptrAngle) * ptrLen)
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2.5; ctx.stroke()

      // 中心圆 + 数字
      ctx.beginPath(); ctx.arc(cx, cy, 10, 0, Math.PI * 2)
      ctx.fillStyle = '#333'; ctx.fill()
      ctx.fillStyle = '#fff'; ctx.font = 'bold 11px monospace'
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(Math.round(spd), cx, cy)
      ctx.restore()
    },

    /* ========== 姿态仪（人工地平） ========== */
    _drawAttitude: function() {
      var c = this.$refs.attCanvas
      if (!c) return
      var ctx = c.getContext('2d')
      var w = c.width, h = c.height
      var cx = w / 2, cy = h / 2, r = 88
      ctx.clearRect(0, 0, w, h)

      ctx.save()
      ctx.beginPath(); ctx.arc(cx, cy, r + 2, 0, Math.PI * 2)
      ctx.fillStyle = '#1a1a2e'; ctx.fill()
      ctx.clip()

      var pitch = this.data.pitch || 0   // deg, positive = nose up
      var roll = this.data.roll || 0     // deg, positive = right bank
      var pitchOffset = -pitch * 3       // pixels per degree

      // 天空（蓝）
      var skyY = cy + pitchOffset
      ctx.fillStyle = '#1565c0'
      ctx.fillRect(cx - r - 5, skyY - r * 2, r * 2 + 10, r * 2)

      // 地面（棕）
      ctx.fillStyle = '#6d4c41'
      ctx.fillRect(cx - r - 5, skyY, r * 2 + 10, r * 2)

      // 旋转
      ctx.translate(cx, cy)
      ctx.rotate(roll * Math.PI / 180)

      // 地平线
      var hlY = pitchOffset
      ctx.beginPath()
      ctx.moveTo(-r - 10, hlY); ctx.lineTo(r + 10, hlY)
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2.5; ctx.stroke()

      // 俯仰刻度
      for (var p = -30; p <= 30; p += 10) {
        var py = hlY - p * 3
        ctx.beginPath()
        ctx.moveTo(-30, py); ctx.lineTo(30, py)
        ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.stroke()
        if (p !== 0) {
          ctx.fillStyle = '#fff'; ctx.font = '9px monospace'
          ctx.textAlign = 'left'; ctx.fillText(p + '°', -40, py + 3)
        }
      }

      // 固定飞机符号
      ctx.beginPath()
      ctx.moveTo(-28, 0); ctx.lineTo(-8, 0)
      ctx.moveTo(8, 0); ctx.lineTo(28, 0)
      ctx.moveTo(0, -3); ctx.lineTo(0, 8)
      ctx.strokeStyle = '#ffab00'; ctx.lineWidth = 3; ctx.stroke()
      ctx.beginPath()
      ctx.arc(0, 0, 3, 0, Math.PI * 2)
      ctx.fillStyle = '#ffab00'; ctx.fill()

      ctx.restore()
    },

    /* ========== 高度表 ========== */
    _drawAltimeter: function() {
      var c = this.$refs.altCanvas
      if (!c) return
      var ctx = c.getContext('2d')
      var w = c.width, h = c.height
      var cx = w / 2, cy = h / 2, r = 78
      ctx.clearRect(0, 0, w, h)

      ctx.save()
      this._roundBg(ctx, cx, cy, r, '#1a1a2e')

      var alt = this.data.altitude || 0        // meters
      var altFt = Math.round(alt * 3.28084)    // convert to feet
      var maxAlt = Math.max(12000, altFt * 1.3)
      maxAlt = Math.ceil(maxAlt / 2000) * 2000

      var startAngle = Math.PI * 0.75, endAngle = Math.PI * 2.25
      var range = endAngle - startAngle

      // 刻度弧
      ctx.beginPath()
      ctx.arc(cx, cy, r - 4, startAngle, endAngle)
      ctx.strokeStyle = '#2a2a4a'; ctx.lineWidth = 12; ctx.stroke()

      var step = maxAlt <= 12000 ? 2000 : 4000
      for (var a = 0; a <= maxAlt; a += step) {
        var ang = startAngle + (a / maxAlt) * range
        var x1 = cx + Math.cos(ang) * (r - 14)
        var y1 = cy + Math.sin(ang) * (r - 14)
        var x2 = cx + Math.cos(ang) * (r - 6)
        var y2 = cy + Math.sin(ang) * (r - 6)
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2)
        ctx.strokeStyle = '#aaa'; ctx.lineWidth = 1.5; ctx.stroke()
        var tx = cx + Math.cos(ang) * (r - 28)
        var ty = cy + Math.sin(ang) * (r - 28)
        ctx.fillStyle = '#ccc'; ctx.font = '9px monospace'
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
        var label = a >= 1000 ? Math.round(a / 1000) + 'k' : a
        ctx.fillText(label, tx, ty)
      }

      // 指针
      var ptrAngle = startAngle + (altFt / maxAlt) * range
      ptrAngle = Math.max(startAngle, Math.min(endAngle, ptrAngle))
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx + Math.cos(ptrAngle) * (r - 22), cy + Math.sin(ptrAngle) * (r - 22))
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2.5; ctx.stroke()

      // 中心数字
      ctx.beginPath(); ctx.arc(cx, cy, 11, 0, Math.PI * 2)
      ctx.fillStyle = '#333'; ctx.fill()
      ctx.fillStyle = '#fff'; ctx.font = 'bold 10px monospace'
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      ctx.fillText(Math.round(altFt), cx, cy)
      ctx.restore()
    },

    /* ========== 航向罗盘 ========== */
    _drawHeading: function() {
      var c = this.$refs.hdgCanvas
      if (!c) return
      var ctx = c.getContext('2d')
      var w = c.width, h = c.height
      var cx = w / 2, cy = h / 2, r = 82
      ctx.clearRect(0, 0, w, h)

      ctx.save()
      this._roundBg(ctx, cx, cy, r - 2, '#1a1a2e')

      var hdg = this.data.heading || 0
      var dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
      for (var i = 0; i < 72; i++) {
        var deg = i * 5
        var ang = (deg - 90) * Math.PI / 180
        var isMajor = deg % 30 === 0
        var isMid = deg % 10 === 0 && !isMajor
        var inner = isMajor ? r - 18 : (isMid ? r - 14 : r - 10)
        var outer = r - 4
        ctx.beginPath()
        ctx.moveTo(cx + Math.cos(ang) * inner, cy + Math.sin(ang) * inner)
        ctx.lineTo(cx + Math.cos(ang) * outer, cy + Math.sin(ang) * outer)
        ctx.strokeStyle = isMajor ? '#fff' : '#888'
        ctx.lineWidth = isMajor ? 2 : 1
        ctx.stroke()

        if (isMajor) {
          var label = deg === 0 ? 'N' : deg === 90 ? 'E' : deg === 180 ? 'S' : deg === 270 ? 'W' : (deg / 10)
          var lx = cx + Math.cos(ang) * (r - 32)
          var ly = cy + Math.sin(ang) * (r - 32)
          ctx.fillStyle = '#fff'; ctx.font = 'bold 12px monospace'
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
          ctx.fillText(label, lx, ly)
        }
      }

      // 航向指针（三角形）
      var ptrAng = (hdg - 90) * Math.PI / 180
      ctx.beginPath()
      ctx.moveTo(cx + Math.cos(ptrAng) * (r - 6), cy + Math.sin(ptrAng) * (r - 6))
      ctx.lineTo(cx + Math.cos(ptrAng - 0.3) * (r + 4), cy + Math.sin(ptrAng - 0.3) * (r + 4))
      ctx.lineTo(cx + Math.cos(ptrAng + 0.3) * (r + 4), cy + Math.sin(ptrAng + 0.3) * (r + 4))
      ctx.closePath()
      ctx.fillStyle = '#ffab00'; ctx.fill()

      // 中心数字
      ctx.fillStyle = '#fff'; ctx.font = 'bold 18px monospace'
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      var hdgText = String(Math.round(hdg)).padStart(3, '0') + '°'
      ctx.fillText(hdgText, cx, cy)
      ctx.restore()
    },

    _roundBg: function(ctx, cx, cy, r, color) {
      var grad = ctx.createRadialGradient(cx - r * 0.2, cy - r * 0.2, r * 0.1, cx, cy, r)
      grad.addColorStop(0, '#2a2a4a')
      grad.addColorStop(1, color)
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.fillStyle = grad; ctx.fill()
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.strokeStyle = '#444'; ctx.lineWidth = 2; ctx.stroke()
    },
  },
  beforeDestroy: function() {
    this._stopAnim()
  },
}
</script>

<style scoped>
.instruments-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  z-index: 3000; display: flex; align-items: flex-start; justify-content: center;
  pointer-events: none;
  padding-top: 20px;
}
.instruments-panel {
  pointer-events: all;
  background: rgba(10, 10, 30, 0.94);
  border: 1px solid #334;
  border-radius: 14px;
  padding: 16px 20px;
  min-width: 460px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.6);
}
.panel-header {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 10px;
}
.flight-label { font-size: 18px; font-weight: 700; color: #fff; }
.phase-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: #333; color: #aaa;
}
.phase-climb { background: #1b5e20; color: #81c784; }
.phase-cruise { background: #0d47a1; color: #64b5f6; }
.phase-descent { background: #e65100; color: #ffb74d; }
.close-btn {
  margin-left: auto; background: none; border: none; color: #888;
  font-size: 18px; cursor: pointer;
}
.close-btn:hover { color: #fff; }

.gauges-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  justify-items: center;
}
.gauge-box {
  display: flex; flex-direction: column; align-items: center;
}
.gauge-box canvas { display: block; }
.gauge-label {
  margin-top: 2px; font-size: 10px; color: #666; text-transform: uppercase;
  letter-spacing: 1px;
}

.digital-panel {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 6px 16px; margin-top: 10px; padding-top: 10px;
  border-top: 1px solid #333;
}
.digi-item {
  display: flex; justify-content: space-between; align-items: center;
}
.digi-label { font-size: 11px; color: #888; }
.digi-value { font-size: 13px; font-weight: 600; color: #e0e0e0; font-family: monospace; }
.digi-value.neg { color: #ffab00; }
</style>
