<template>
  <div class="sim-timeline">
    <div class="timeline-controls">
      <div class="ctrl-group">
        <button class="ctrl-btn" @click="$emit('step')" :disabled="!running" title="单步">⏭</button>
        <button class="ctrl-btn" @click="$emit('start')" v-if="!running" title="启动">▶</button>
        <button class="ctrl-btn" @click="$emit('pause')" v-if="running && !paused" title="暂停">⏸</button>
        <button class="ctrl-btn" @click="$emit('resume')" v-if="paused" title="继续">▶</button>
        <button class="ctrl-btn" @click="$emit('stop')" v-if="running" title="停止">⏹</button>
      </div>
      <div class="speed-group">
        <span class="speed-label">倍速</span>
        <select class="speed-select" :value="speed" @change="$emit('speedChange', Number($event.target.value))">
          <option :value="1">1x</option>
          <option :value="2">2x</option>
          <option :value="5">5x</option>
          <option :value="10">10x</option>
        </select>
      </div>
    </div>
    <div class="timeline-track" ref="track" @mousedown="onTrackDown" :class="{ scrubbing: dragging }">
      <div class="timeline-fill" :style="{ width: displayProgress + '%' }"></div>
      <div class="timeline-cursor" :style="{ left: displayProgress + '%' }"></div>
      <!-- 小时刻度（时钟刻度线） -->
      <div v-for="(mk, i) in timeMarks" :key="'t' + i"
           class="time-tick" :style="{ left: mk.pct + '%' }"></div>
      <!-- 航班事件标记（起飞/降落） -->
      <div v-for="(evt, i) in eventMarks" :key="i"
           class="event-mark" :style="{ left: evt.pct + '%' }"
           :title="evt.label"
           :class="'mark-' + evt.type"></div>
    </div>
    <div class="time-scale">
      <div v-for="(mk, i) in timeMarks" :key="'l' + i"
           class="time-scale-item" :style="{ left: mk.pct + '%' }">
        <span class="time-scale-label">{{ mk.label }}</span>
      </div>
    </div>
    <div class="timeline-info">
      <span class="time-current">🕒 {{ currentTime }}</span>
      <span class="time-range">{{ simStart }} ~ {{ simEnd }}</span>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SimulationTimeline',
  props: {
    running: { type: Boolean, default: false },
    paused: { type: Boolean, default: false },
    speed: { type: Number, default: 1 },
    progress: { type: Number, default: 0 },
    currentTime: { type: String, default: '--' },
    simStart: { type: String, default: '--' },
    simEnd: { type: String, default: '--' },
    totalMinutes: { type: Number, default: 1020 },
    events: { type: Array, default: () => [] },
  },
  emits: ['start', 'pause', 'resume', 'stop', 'step', 'speedChange', 'jump'],
  data() {
    return {
      dragging: false,
      // 拖动过程中的本地进度显示（父组件轮询同步有 200ms 延迟，拖动时先本地跟随）
      dragProgress: null,
      _syncTimer: null,
    }
  },
  mounted() {
    document.addEventListener('mousemove', this.onDocMove)
    document.addEventListener('mouseup', this.onDocUp)
  },
  beforeDestroy() {
    document.removeEventListener('mousemove', this.onDocMove)
    document.removeEventListener('mouseup', this.onDocUp)
    if (this._syncTimer) { clearTimeout(this._syncTimer); this._syncTimer = null }
  },
  watch: {
    // 松开后等真实进度（父组件轮询同步的模拟时间）追上本地拖动位置再回落到 prop，
    // 避免跳转完成后进度条回弹到旧位置
    progress(val) {
      if (this.dragProgress === null) return
      if (Math.abs(val - this.dragProgress) < 1) {
        this.dragProgress = null
        if (this._syncTimer) { clearTimeout(this._syncTimer); this._syncTimer = null }
      }
    },
  },
  computed: {
    // 拖动中显示本地位置（即时反馈），松开后回落到父组件同步的真实进度
    displayProgress() {
      return this.dragProgress !== null ? this.dragProgress : this.progress
    },
    eventMarks() {
      return this.events.map(e => ({
        ...e,
        pct: (e.progress_pct !== undefined ? e.progress_pct : e.pct) || 0,
        type: e.event_type || e.type || 'airport',
        label: e.label || '',
      }))
    },
    // 时钟刻度：按小时生成（00:00、01:00、02:00 …）
    timeMarks() {
      const total = this.totalMinutes || 1020
      const marks = []
      const hours = Math.floor(total / 60)
      for (let h = 0; h <= hours; h++) {
        marks.push({
          pct: (h * 60 / total) * 100,
          label: String(h).padStart(2, '0') + ':00',
        })
      }
      return marks
    },
  },
  methods: {
    onTrackDown(e) {
      console.log('[TIMELINE] onTrackDown')
      this.dragging = true
      this._lastMoveEmit = 0
      this.updateFromEvent(e)
      e.preventDefault()
    },
    onDocMove(e) {
      if (!this.dragging) return
      // 节流：拖动过程约 60ms 触发一次跳转，避免高频快进卡顿
      const now = Date.now()
      if (now - (this._lastMoveEmit || 0) < 60) return
      this._lastMoveEmit = now
      this.updateFromEvent(e)
    },
    onDocUp(e) {
      if (!this.dragging) return
      console.log('[TIMELINE] onDocUp')
      this.dragging = false
      this.updateFromEvent(e)  // 松开时确保停在最终位置
      // 兜底：若父组件长时间未同步真实进度（如跳转计算量大），最迟 2s 后回落到 prop
      clearTimeout(this._syncTimer)
      this._syncTimer = setTimeout(() => { this.dragProgress = null }, 2000)
    },
    updateFromEvent(e) {
      const rect = this.$refs.track.getBoundingClientRect()
      const pct = ((e.clientX - rect.left) / rect.width) * 100
      const clamped = Math.max(0, Math.min(100, Math.round(pct)))
      console.log('[TIMELINE] emit jump pct=' + clamped)
      this.dragProgress = clamped
      this.$emit('jump', clamped)
    },
  },
}
</script>

<style scoped>
.sim-timeline {
  background: #1e1e2e;
  border-bottom: 1px solid #313145;
  padding: 8px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.timeline-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ctrl-group {
  display: flex;
  gap: 4px;
}
.ctrl-btn {
  background: #2d2d44;
  border: 1px solid #444;
  color: #cdd6f4;
  width: 34px;
  height: 30px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ctrl-btn:hover { background: #3d3d5c; }
.ctrl-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.speed-group { display: flex; align-items: center; gap: 6px; }
.speed-label { color: #8a8aaa; font-size: 12px; }
.speed-select {
  background: #2d2d44;
  color: #cdd6f4;
  border: 1px solid #444;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 12px;
}
.timeline-track {
  position: relative;
  height: 8px;
  background: #2d2d44;
  border-radius: 4px;
  cursor: pointer;
}
.timeline-track:hover { background: #3a3a55; }
/* 拖动过程中禁用过渡动画，保证进度条即时跟随鼠标 */
.timeline-track.scrubbing .timeline-fill,
.timeline-track.scrubbing .timeline-cursor {
  transition: none;
}
.timeline-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #8bc34a);
  border-radius: 4px;
  transition: width 0.2s;
}
.timeline-cursor {
  position: absolute;
  top: -3px;
  width: 3px;
  height: 14px;
  background: #fff;
  border-radius: 2px;
  margin-left: -1px;
  transition: left 0.2s;
  cursor: ew-resize;
  box-shadow: 0 0 4px rgba(255, 255, 255, 0.5);
}
/* 小时刻度线（时钟刻度） */
.time-tick {
  position: absolute;
  top: 0;
  width: 1px;
  height: 100%;
  background: rgba(255, 255, 255, 0.22);
}
/* 刻度标签行 */
.time-scale {
  position: relative;
  height: 14px;
}
.time-scale-item {
  position: absolute;
  transform: translateX(-50%);
  white-space: nowrap;
}
.time-scale-label {
  font-size: 10px;
  color: #8a8aaa;
  font-family: 'Courier New', monospace;
}
.event-mark {
  position: absolute;
  top: -2px;
  width: 8px;
  height: 12px;
  border-radius: 2px;
}
.mark-airport { background: #ff9800; }
.mark-takeoff { background: #ff9800; border: 1px solid #fff; }
.mark-landing { background: #4caf50; border: 1px solid #fff; }
.mark-weather_trigger { background: #2196f3; }
.mark-crew_absence { background: #e91e63; }
.mark-aircraft_failure { background: #f44336; }

.timeline-info {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #8a8aaa;
}
.time-current {
  color: #ffd54f;
  font-weight: 700;
  font-size: 13px;
  font-family: 'Courier New', monospace;
}
</style>
