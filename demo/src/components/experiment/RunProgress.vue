<template>
  <div class="run-progress">
    <div class="rp-head">
      <span class="rp-title">{{ title }}</span>
      <span class="rp-pct">{{ progress.pct || 0 }}%</span>
    </div>
    <el-progress :percentage="progress.pct || 0" :show-text="false" :stroke-width="6"
                 color="#409eff" />
    <div class="rp-stages">
      <div v-for="s in stages" :key="s.name" class="rp-stage" :class="stageClass(s)">
        <span class="rp-dot"></span>
        <span class="rp-name">{{ s.name }}</span>
        <span class="rp-state">{{ stateText(s) }}</span>
      </div>
    </div>
    <div v-if="progress.message" class="rp-msg">{{ progress.message }}</div>
  </div>
</template>

<script>
const STAGES = [
  { name: '校验条件', at: 1 },
  { name: '生成航班计划', at: 51 },
  { name: '构建任务链', at: 55 },
  { name: '四类调度', at: 78 },
  { name: '编译中断计划', at: 83 },
  { name: '冻结计划推演', at: 95 },
  { name: '汇总指标与落盘', at: 100 },
]

export default {
  name: 'RunProgress',
  props: {
    progress: { type: Object, default: () => ({}) },
    status: { type: String, default: 'running' },
  },
  computed: {
    stages() { return STAGES },
    currentAt() {
      const pct = this.progress.pct || 0
      let at = 0
      for (const s of STAGES) { if (pct >= s.at) at = s.at }
      return at
    },
    title() {
      if (this.status === 'failed') return '运行失败'
      if (this.status === 'succeeded') return '运行完成'
      return '正在运行'
    },
  },
  methods: {
    stageClass(s) {
      if (this.status === 'failed') {
        return s.name === this.progress.stage ? 'failed' : ''
      }
      if (this.progress.pct >= s.at) return 'done'
      const next = STAGES.find(x => x.at > (this.progress.pct || 0))
      return next && next.name === s.name ? 'active' : ''
    },
    stateText(s) {
      const cls = this.stageClass(s)
      if (cls === 'done') return '完成'
      if (cls === 'active') return '进行中'
      if (cls === 'failed') return '失败'
      return '等待'
    },
  },
}
</script>

<style scoped>
.run-progress { background: #1e1e2e; border-radius: 8px; padding: 14px 18px; }
.rp-head { display: flex; align-items: baseline; margin-bottom: 8px; }
.rp-title { font-size: 13px; color: #cdd6f4; }
.rp-pct { margin-left: auto; font-size: 18px; color: #409eff; font-weight: 500; }
.rp-stages { display: flex; flex-wrap: wrap; gap: 4px 18px; margin-top: 12px; }
.rp-stage { display: flex; align-items: center; gap: 5px; font-size: 12px; color: #5a5a7a; }
.rp-dot { width: 6px; height: 6px; border-radius: 50%; background: #3d3d5c; }
.rp-stage.done { color: #67c23a; }
.rp-stage.done .rp-dot { background: #67c23a; }
.rp-stage.active { color: #409eff; }
.rp-stage.active .rp-dot { background: #409eff; }
.rp-stage.failed { color: #f56c6c; }
.rp-stage.failed .rp-dot { background: #f56c6c; }
.rp-state { color: inherit; opacity: 0.7; }
.rp-msg { margin-top: 8px; font-size: 12px; color: #f56c6c; }
</style>
