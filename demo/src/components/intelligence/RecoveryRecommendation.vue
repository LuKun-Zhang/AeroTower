<template>
  <section class="recovery-recommendation">
    <h4>策略推荐</h4>
    <p v-if="!impact">完成影响分析后，可比较候选策略的预测代价。</p>
    <el-button v-else size="small" :loading="loading" @click="load">比较恢复策略</el-button>
    <el-alert v-if="error" :title="error" type="warning" :closable="false" />
    <template v-if="result">
      <p>{{ result.reason }}</p>
      <p v-if="result.original">原系统方案代价 {{ result.original.cost }}。{{ result.guarded ? '已触发保护：保留原方案。' : '以下候选与原方案使用同一代价口径。' }}</p>
      <el-table :data="result.candidates" size="mini">
        <el-table-column label="策略" min-width="110"><template slot-scope="{ row }">{{ row.name }}<el-tag v-if="row.strategy === result.recommended" size="mini" type="success">推荐</el-tag></template></el-table-column>
        <el-table-column prop="predicted_cost" label="预测代价" min-width="85" />
        <el-table-column label="预计延误/取消" min-width="110"><template slot-scope="{ row }">{{ row.predicted_delay_minutes == null ? '—' : row.predicted_delay_minutes }}分 / {{ row.predicted_cancellations == null ? '—' : row.predicted_cancellations }}班</template></el-table-column>
        <el-table-column label="约束检查" min-width="140"><template slot-scope="{ row }">{{ row.feasible ? '通过' : row.violations.join('；') }}</template></el-table-column>
      </el-table>
      <p>{{ result.execution }}</p>
      <p>{{ result.assumptions }}</p>
      <p>取消数为模型期望值，可能有小数。详细比较可在智能实验中心查看。</p>
    </template>
  </section>
</template>

<script>
import api from '@/api/intelligence'
export default {
  props: { eventId: String, impact: Object },
  data: () => ({ result: null, loading: false, error: '' }),
  watch: { eventId() { this.result = null; this.error = '' }, impact() { this.result = null } },
  methods: {
    async load() {
      const id = this.eventId
      this.loading = true
      try { const result = await api.recovery(id); if (id === this.eventId) this.result = result } catch (error) { this.error = error.message } finally { this.loading = false }
    }
  }
}
</script>

<style scoped>
.recovery-recommendation { color: #243448; font-size: 14px; background: white; border: 1px solid #e6ebf0; padding: 16px; border-radius: 6px; margin-bottom: 14px; }
h4 { font-size: 14px; line-height: 22px; color: #243448; margin: 0 0 12px; }
p { font-size: 12px; line-height: 1.7; color: #657489; }
</style>
