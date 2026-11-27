<template>
  <div class="exp-page">
    <div class="exp-header">
      <button class="exp-back" @click="$router.push('/experiments')">← 实验列表</button>
      <div class="eh-main">
        <h2>{{ record ? record.name : '实验详情' }}</h2>
        <span v-if="record" class="eh-status" :class="'st-' + record.status">{{ statusText }}</span>
      </div>
      <div class="eh-actions" v-if="record">
        <el-button v-if="record.status === 'draft' || record.status === 'failed' || record.status === 'interrupted'"
                   type="primary" size="small" @click="run">运行</el-button>
        <el-button size="small" @click="exportOne">导出</el-button>
        <el-button size="small" :disabled="record.status === 'running'" @click="rerun">重跑</el-button>
        <el-button size="small" type="danger" plain @click="remove">删除</el-button>
      </div>
    </div>

    <div class="exp-body" v-if="loading"><p class="exp-tip">加载中…</p></div>

    <div class="exp-body" v-else-if="record">
      <RunProgress v-if="record.status === 'running'" :progress="record.progress" status="running" />
      <RunProgress v-else-if="record.status === 'failed'" :progress="record.progress"
                   :status="'failed'" />

      <div v-if="record.status === 'failed'" class="exp-error">
        <div class="ee-title">失败阶段：{{ (record.error || {}).stage }}</div>
        <div class="ee-msg">{{ (record.error || {}).message }}</div>
        <details v-if="(record.error || {}).traceback">
          <summary>查看调用栈</summary>
          <pre>{{ record.error.traceback }}</pre>
        </details>
      </div>

      <template v-if="record.status === 'succeeded'">
        <ReplayPanel v-if="record.replay && record.replay.sim_start !== undefined"
                     :simStart="record.replay.sim_start" :simEnd="record.replay.sim_end"
                     :hasPaxflow="!!record.replay.has_paxflow" :weatherMeta="weatherMeta"
                     :initialTab="$route.query.tab || 'flight'"
                     :initialMinutes="$route.query.t && !isNaN(Number($route.query.t)) ? Number($route.query.t) : null" />
        <div class="exp-results">
          <MetricCards :values="metrics.values || {}" />
          <MetricChart :series="metrics.series || { points: [] }" />
        </div>
      </template>

      <ConditionSummary :conditions="record.conditions || {}" :warnings="record.warnings || []" />

      <div class="exp-meta">
        <span>创建 {{ record.created_at }}</span>
        <span v-if="record.finished_at">完成 {{ record.finished_at }}</span>
        <span v-if="record.duration_sec">耗时 {{ record.duration_sec }} s</span>
        <span>工件 {{ Math.round((diskBytes || 0) / 1024) }} KB</span>
      </div>
    </div>

    <div class="exp-body" v-else><p class="exp-tip">{{ loadError || '实验不存在' }}</p></div>
  </div>
</template>

<script>
import RunProgress from '@/components/experiment/RunProgress'
import ReplayPanel from '@/components/experiment/ReplayPanel'
import MetricCards from '@/components/experiment/MetricCards'
import MetricChart from '@/components/experiment/MetricChart'
import ConditionSummary from '@/components/experiment/ConditionSummary'
import api from '@/api/experiment'
import { setApiScope, clearApiScope } from '@/api/scope'

const STATUS = {
  draft: '草稿', running: '运行中', succeeded: '已完成',
  failed: '失败', interrupted: '中断',
}

export default {
  name: 'ExperimentDetailView',
  components: { RunProgress, ReplayPanel, MetricCards, MetricChart, ConditionSummary },
  data() {
    return {
      loading: true,
      record: null,
      metrics: {},
      weatherMeta: {},
      diskBytes: 0,
      loadError: '',
      _timer: null,
    }
  },
  computed: {
    statusText() { return STATUS[this.record.status] || this.record.status },
  },
  watch: {
    '$route.params.id'(id) {
      if (!id) return
      setApiScope(id)
      if (this._timer) { clearInterval(this._timer); this._timer = null }
      this.loading = true
      this.record = null
      this.loadError = ''
      this.load()
    },
  },
  created() {
    setApiScope(this.$route.params.id)
    this.load()
  },
  beforeDestroy() {
    clearApiScope()
    if (this._timer) clearInterval(this._timer)
  },
  methods: {
    async load() {
      try {
        const data = await api.get(this.$route.params.id)
        this.record = data.record
        this.metrics = data.metrics || {}
        this.weatherMeta = data.weather_meta || {}
        this.diskBytes = data.disk_bytes || 0
        this.loading = false
        if (this.record.status === 'running') this.poll()
        else if (this._timer) { clearInterval(this._timer); this._timer = null }
      } catch (e) {
        this.loading = false
        this.loadError = e.message || '加载失败'
        this.$message.error(this.loadError)
      }
    },
    poll() {
      if (this._timer) return
      this._timer = setInterval(async () => {
        try {
          const p = await api.progress(this.$route.params.id)
          if (this.record) this.record.progress = p
          if (p.status !== 'running') {
            clearInterval(this._timer)
            this._timer = null
            this.load()
          }
        } catch (e) {}
      }, 1000)
    },
    async rerun() {
      try {
        const record = await api.rerun(this.record.id)
        this.$message.success('已启动重跑')
        this.$router.push(`/experiments/${record.id}`)
      } catch (e) {
        this.$message.error(e.message || '重跑失败')
      }
    },
    async run() {
      try {
        await api.run(this.record.id)
        this.$message.success('已启动')
        this.record.status = 'running'
        this.record.progress = { pct: 1, stage: '校验条件', message: '' }
        this.poll()
      } catch (e) {
        this.$message.error(e.message || '启动失败')
      }
    },
    async exportOne() {
      try {
        await api.export(this.record.id)
      } catch (e) {
        this.$message.error(e.message || '导出失败')
      }
    },
    async remove() {
      try {
        await this.$confirm('确认删除该实验？', '提示', {
          confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
        })
        await api.remove(this.record.id)
        this.$router.replace('/experiments')
      } catch (e) {
        if (e !== 'cancel') this.$message.error(e.message || '删除失败')
      }
    },
  },
}
</script>

<style scoped>
.exp-page { height: 100vh; background: #141428; color: #cdd6f4; overflow-y: auto; }
.exp-header {
  display: flex; align-items: center; gap: 16px;
  padding: 10px 24px; background: #1a1a2e; border-bottom: 1px solid #2d2d44;
}
.eh-main { display: flex; align-items: center; gap: 10px; }
.eh-main h2 { margin: 0; font-size: 16px; color: #fff; font-weight: 500; }
.eh-status { font-size: 12px; padding: 2px 8px; border-radius: 10px; background: #2d2d44; color: #b4b2a9; }
.eh-status.st-running { background: rgba(64,158,255,0.18); color: #409eff; }
.eh-status.st-succeeded { background: rgba(103,194,58,0.18); color: #67c23a; }
.eh-status.st-failed { background: rgba(245,108,108,0.18); color: #f56c6c; }
.eh-status.st-interrupted { background: rgba(230,162,60,0.18); color: #e6a23c; }
.eh-actions { margin-left: auto; display: flex; gap: 8px; }
.exp-back {
  padding: 5px 12px; font-size: 13px; color: #409eff; cursor: pointer;
  background: rgba(64,158,255,0.1); border: 1px solid rgba(64,158,255,0.3);
  border-radius: 4px;
}
.exp-body { max-width: 1400px; margin: 0 auto; padding: 16px 24px 40px; }
.exp-tip { color: #7a7a9a; font-size: 13px; }
.exp-results { margin-top: 12px; display: flex; flex-direction: column; gap: 12px; }
.exp-error {
  margin: 12px 0; padding: 12px 16px; border-radius: 8px;
  background: rgba(245,108,108,0.1); border: 1px solid rgba(245,108,108,0.35);
}
.ee-title { font-size: 13px; color: #f56c6c; margin-bottom: 4px; }
.ee-msg { font-size: 12px; color: #f0b0b0; }
.exp-error pre { white-space: pre-wrap; font-size: 11px; color: #c09090; margin: 8px 0 0; }
.exp-meta { display: flex; gap: 18px; font-size: 11px; color: #6a6a8a; margin-top: 14px; }
</style>
