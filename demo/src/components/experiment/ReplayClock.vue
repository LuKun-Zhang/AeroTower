<template>
  <div class="replay-clock">
    <div class="rc-controls">
      <button class="rc-btn" @click="$emit('toggle')">{{ playing ? '⏸' : '▶' }}</button>
      <button class="rc-btn" @click="$emit('reset')">⏹</button>
      <span class="rc-label">倍速</span>
      <select class="rc-speed" :value="speed" @change="$emit('speed', Number($event.target.value))">
        <option :value="1">1x</option>
        <option :value="2">2x</option>
        <option :value="5">5x</option>
        <option :value="10">10x</option>
      </select>
      <span class="rc-time">{{ clockText }}</span>
    </div>
    <div class="rc-track" ref="track" @mousedown="onDown">
      <div class="rc-fill" :style="{ width: progress + '%' }"></div>
      <div class="rc-cursor" :style="{ left: progress + '%' }"></div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ReplayClock',
  props: {
    progress: { type: Number, default: 0 },
    clockText: { type: String, default: '' },
    playing: { type: Boolean, default: false },
    speed: { type: Number, default: 1 },
  },
  data() {
    return { dragging: false }
  },
  mounted() {
    document.addEventListener('mousemove', this.onMove)
    document.addEventListener('mouseup', this.onUp)
  },
  beforeDestroy() {
    document.removeEventListener('mousemove', this.onMove)
    document.removeEventListener('mouseup', this.onUp)
  },
  methods: {
    onDown(e) {
      this.dragging = true
      this.emitSeek(e)
      e.preventDefault()
    },
    onMove(e) {
      if (this.dragging) this.emitSeek(e)
    },
    onUp(e) {
      if (!this.dragging) return
      this.dragging = false
      this.emitSeek(e)
    },
    emitSeek(e) {
      const rect = this.$refs.track.getBoundingClientRect()
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
      this.$emit('seek', pct)
    },
  },
}
</script>

<style scoped>
.replay-clock { background: #1e1e2e; border-top: 1px solid #313145; padding: 10px 16px; }
.rc-controls { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.rc-btn {
  background: #2d2d44; border: 1px solid #444; color: #cdd6f4;
  width: 32px; height: 26px; border-radius: 4px; cursor: pointer; font-size: 13px;
}
.rc-btn:hover { background: #3d3d5c; }
.rc-label { font-size: 12px; color: #8a8aaa; }
.rc-speed {
  background: #2d2d44; color: #cdd6f4; border: 1px solid #444;
  border-radius: 4px; padding: 2px 6px; font-size: 12px;
}
.rc-time {
  margin-left: auto; color: #ffd54f; font-size: 14px; font-weight: 500;
  font-family: 'Courier New', monospace;
}
.rc-track { position: relative; height: 8px; background: #2d2d44; border-radius: 4px; cursor: pointer; }
.rc-fill { height: 100%; background: #409eff; border-radius: 4px; }
.rc-cursor {
  position: absolute; top: -3px; width: 3px; height: 14px; margin-left: -1.5px;
  background: #fff; border-radius: 2px; cursor: ew-resize;
}
</style>
