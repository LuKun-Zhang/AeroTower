<template>
  <div class="intelligence-center">
    <header><div><el-button type="text" icon="el-icon-arrow-left" @click="$router.push('/')">返回首页</el-button><h1>智能实验中心</h1><p>保存实验条件，比较延误预测与恢复策略。</p></div><el-button size="small" :loading="loading" @click="refresh">刷新结果</el-button></header>
    <div v-if="error" class="error"><el-alert :title="error" type="error" show-icon :closable="false" /></div>
    <div class="card"><ModelStatus :report="report" :training="training" :language-ready="languageReady" :language-policy="languagePolicy" @train="train" /></div>
    <div class="card"><ModelReview :report="report" @changed="refresh" /></div>
    <div v-if="options" class="card"><DemandForecast :config="config" @apply="applyForecast" /></div>
    <div v-if="options" class="workspace">
      <aside>
        <div class="card"><NaturalInput :draft="draft" :loading="parsing" :default-model="!!languagePolicy && languagePolicy.mode === 'local-qwen'" @parse="parse" @apply="applyDraft" /></div>
        <div class="card"><ExperimentForm v-model="config" :options="options" :busy="running" @run="run" @batch="batch" /></div>
      </aside>
      <main>
        <div class="card"><ExperimentResults :record="record" :weather="options.weather" @rerun="rerun" /></div>
        <div class="card"><h3>历史实验</h3><el-table :data="records" size="small" highlight-current-row @row-click="selectRecord"><el-table-column label="提交时间" min-width="150"><template slot-scope="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column><el-table-column prop="config.base_airport" label="基地" width="75" /><el-table-column label="天气" width="90"><template slot-scope="{ row }">{{ options.weather[row.config.weather] }}</template></el-table-column><el-table-column label="状态"><template slot-scope="{ row }">{{ states[row.status] || row.status }}</template></el-table-column></el-table></div>
      </main>
    </div>
  </div>
</template>

<script>
import api from '@/api/intelligence'
import ModelStatus from '@/components/intelligence/ModelStatus.vue'
import NaturalInput from '@/components/intelligence/NaturalInput.vue'
import ExperimentForm from '@/components/intelligence/ExperimentForm.vue'
import ExperimentResults from '@/components/intelligence/ExperimentResults.vue'
import DemandForecast from '@/components/intelligence/DemandForecast.vue'
import ModelReview from '@/components/intelligence/ModelReview.vue'

export default {
  name: 'IntelligenceCenter',
  components: { ModelStatus, NaturalInput, ExperimentForm, ExperimentResults, DemandForecast, ModelReview },
  data: () => ({ options: null, config: {}, report: null, languageReady: false, languagePolicy: null, draft: null,
    records: [], record: null, selectedId: null, parsing: false, running: false,
    training: false, loading: false, error: '', timer: null,
    states: { queued: '等待运行', running: '运行中', completed: '已完成', failed: '失败' } }),
  async created() {
    await this.refresh()
    this.timer = setInterval(this.poll, 1500)
  },
  beforeDestroy() { clearInterval(this.timer) },
  methods: {
    async refresh() {
      this.loading = true
      try {
        const [options, models, records] = await Promise.all([api.options(), api.models(), api.records()])
        this.options = options
        if (!Object.keys(this.config).length) this.config = { ...options.defaults }
        this.report = models.report
        this.languageReady = models.language_model_ready
        this.languagePolicy = models.language_policy
        this.records = records
        if (!this.selectedId && records.length) await this.selectRecord(records[0])
        this.error = ''
      } catch (error) { this.error = error.message } finally { this.loading = false }
    },
    async selectRecord(row) {
      this.selectedId = row.id
      try {
        const record = await api.record(row.id)
        if (this.selectedId === row.id) this.record = record
      } catch (error) { this.error = error.message }
    },
    async poll() {
      if (this.record && ['queued', 'running'].includes(this.record.status)) {
        await this.selectRecord(this.record)
        if (this.record.status === 'completed' || this.record.status === 'failed') await this.refresh()
      }
    },
    async parse({ text, useModel }) {
      this.parsing = true
      try { this.draft = await api.draft(text, useModel) } catch (error) { this.$message.error(error.message) } finally { this.parsing = false }
    },
    applyDraft(fields) { this.config = { ...this.config, ...fields }; this.$message.success('已填入表单，请核对完整条件后运行') },
    applyForecast(fields) { this.config = { ...this.config, ...fields }; this.$message.success('已填入预测比例和天数，请核对后运行') },
    async run(config) {
      this.running = true
      try {
        const record = await api.create(config)
        await this.selectRecord(record)
        await this.refresh()
      } catch (error) { this.$message.error(error.message) } finally { this.running = false }
    },
    async batch(config) {
      try {
        await this.$confirm('将按表单条件运行晴朗、降雨、雷暴三组实验，只改变天气。确认开始？', '确认批量实验')
        this.running = true
        const records = await api.batch(['clear', 'rain', 'storm'].map(weather => ({ ...config, weather })))
        await this.selectRecord(records[0])
        await this.refresh()
      } catch (error) { if (error !== 'cancel' && error !== 'close') this.$message.error(error.message) } finally { this.running = false }
    },
    async rerun(id) {
      try { const record = await api.rerun(id); await this.selectRecord(record); await this.refresh() } catch (error) { this.$message.error(error.message) }
    },
    async train() {
      this.training = true
      try {
        const job = await api.train()
        let state = job
        while (['queued', 'running'].includes(state.status)) {
          await new Promise(resolve => setTimeout(resolve, 1200))
          state = await api.job(job.id)
        }
        if (state.status !== 'completed') throw new Error(state.error || '训练未完成')
        await this.refresh()
        this.$message.success('训练与评估完成，已更新模型结果')
      } catch (error) { this.$message.error(error.message) } finally { this.training = false }
    },
    formatTime(value) { return new Date(value).toLocaleString('zh-CN', { hour12: false }) }
  }
}
</script>

<style scoped>
.intelligence-center { height: 100vh; overflow-y: auto; box-sizing: border-box; background: #f3f5f8; color: #243448; padding: 24px 32px 48px; }
header { display: flex; justify-content: space-between; align-items: center; max-width: 1550px; margin: 0 auto 24px; }
h1 { font-size: 26px; margin: 8px 0; font-weight: 600; }
header p { color: #6b7788; font-size: 14px; margin: 0; }
.card { background: white; border: 1px solid #e5eaf0; border-radius: 8px; padding: 22px; margin-bottom: 20px; }
.intelligence-center > .card, .workspace, .error { max-width: 1550px; margin-left: auto; margin-right: auto; }
.workspace { display: grid; grid-template-columns: 370px minmax(0, 1fr); gap: 20px; align-items: start; }
main { min-width: 0; }
h3 { margin-top: 0; }
.error { margin-bottom: 20px; }
@media (max-width: 1050px) { .workspace { grid-template-columns: 1fr; } .intelligence-center { padding: 18px; } }
</style>
