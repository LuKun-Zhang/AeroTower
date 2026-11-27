<template>
  <section>
    <div class="heading"><h3>模型复核与回退</h3><div><el-button size="small" :loading="working" @click="run('regular')">立即用新场景复核</el-button><el-button size="small" :disabled="working" @click="run('shift-demo')">验证失准回退</el-button></div></div>
    <p>每7天复核固定模型；服务运行时自动检查，离线期间不运行，重新启动后补做。复核不重新训练。</p>
    <div class="states"><el-tag v-for="(label, scope) in labels" :key="scope" :type="enabled(scope) ? 'success' : 'warning'">{{ label }}：{{ enabled(scope) ? '启用' : '停用并回退' }}</el-tag></div>
    <p v-if="status">下次到期：{{ time(status.next_due) }}。{{ status.health.mode === 'shift-demo' ? '当前为人为失准演示结果；执行正常复核通过后恢复。' : '未通过的方向停止使用模型：延误显示均值，恢复与排班保留规则，客流使用同期值。' }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="status && status.monitor_error" class="error">自动复核启动失败：{{ status.monitor_error }}</p>
    <el-table v-if="status && status.history.length" :data="status.history" size="mini"><el-table-column label="复核方式"><template slot-scope="{ row }">{{ row.mode === 'shift-demo' ? '失准演示' : row.automatic ? '到期自动复核' : '正常复核' }}</template></el-table-column><el-table-column label="状态"><template slot-scope="{ row }">{{ states[row.status] || row.status }}</template></el-table-column><el-table-column label="模型版本"><template slot-scope="{ row }">{{ report && row.model_version === report.version ? '当前 ' : '历史 ' }}{{ row.model_version.slice(0, 8) }}</template></el-table-column><el-table-column label="时间"><template slot-scope="{ row }">{{ time(row.created_at) }}</template></el-table-column></el-table>
  </section>
</template>

<script>
import api from '@/api/intelligence'
export default {
  props: { report: Object },
  data: () => ({ status: null, working: false, error: '', timer: null,
    labels: { delay: '延误预测', recovery: '恢复推荐', routing: '排班建议', demand: '客流预测' },
    states: { queued: '等待', running: '复核中', completed: '复核完成', failed: '复核失败' } }),
  created() { this.refresh(); this.timer = setInterval(this.refresh, 10000) },
  beforeDestroy() { clearInterval(this.timer) },
  methods: {
    enabled(scope) {
      const saved = this.status && this.status.health.enabled
      if (saved && saved[scope] === false) return false
      if (!this.report) return false
      return scope === 'demand' ? !!this.report.demand : !!(this.report[scope] && this.report[scope].passed)
    },
    time(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未安排' },
    async refresh() { try { this.status = await api.reviews() } catch (error) { this.error = error.message } },
    async run(mode) {
      if (mode === 'shift-demo') {
        try { await this.$confirm('将人为扰动预测来验证失准检测。系统会临时停用延误模型，正常复核通过后恢复；不会改动已保存的权重或活动排班。继续？', '确认失准演示') } catch (_) { return }
      }
      this.working = true; this.error = ''
      try {
        let job = await api.startReview(mode)
        while (['queued', 'running'].includes(job.status)) {
          await new Promise(resolve => setTimeout(resolve, 1000))
          job = await api.review(job.id)
        }
        if (job.status !== 'completed') throw new Error(job.error || '复核失败')
        await this.refresh(); this.$emit('changed')
      } catch (error) { this.error = error.message } finally { this.working = false }
    }
  }
}
</script>

<style scoped>
.heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
h3 { margin: 0; font-size: 18px; }p { color: #657489; font-size: 12px; line-height: 1.8; margin: 12px 0; }
.states { display: flex; flex-wrap: wrap; gap: 10px; }.error { color: #c84141; }
</style>
