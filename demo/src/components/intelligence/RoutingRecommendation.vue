<template>
  <section class="routing-recommendation">
    <div class="heading"><h4>排班算法建议</h4><el-button size="small" :loading="loading" @click="load">根据当前航班建议算法</el-button><el-button v-if="result && result.enabled" size="small" type="primary" @click="$emit('select', result.recommended)">选用建议</el-button></div>
    <p v-if="error">{{ error }}</p>
    <template v-if="result">
      <p>{{ result.reason }}。{{ result.guarded ? '候选计划代价高于原默认可行方案，已保留原算法。' : '' }}</p>
      <el-table :data="result.candidates" size="mini"><el-table-column label="算法" min-width="190"><template slot-scope="{ row }">{{ row.name }} <el-tag v-if="row.algorithm === result.recommended" size="mini">建议</el-tag></template></el-table-column><el-table-column prop="predicted_cost" label="预测代价" /><el-table-column prop="cost" label="计划代价" /><el-table-column prop="aircraft" label="飞机数" /><el-table-column prop="unassigned" label="未分配航班" /><el-table-column label="约束"><template slot-scope="{ row }">{{ row.feasible ? '通过所列检查' : row.violations.join('；') }}</template></el-table-column></el-table>
      <p>{{ result.execution }}。代价为未分配航班×10000＋飞机×100＋空闲分钟×0.05；预测不低于已知未分配与飞机成本。硬约束失败的整套计划视为不可执行。</p>
    </template>
  </section>
</template>

<script>
import api from '@/api/intelligence'
export default {
  props: { aircraftLimit: Number },
  data: () => ({ result: null, loading: false, error: '' }),
  watch: { aircraftLimit() { this.result = null } },
  methods: {
    async load() { this.loading = true; this.error = ''; const fleet = this.aircraftLimit; try { const result = await api.routing(fleet); if (fleet === this.aircraftLimit) this.result = result } catch (error) { this.error = error.message } finally { this.loading = false } }
  }
}
</script>

<style scoped>
.routing-recommendation { background: white; color: #243448; border-radius: 6px; padding: 12px 16px; margin: 8px 0; font-size: 13px; flex-shrink: 0; }
.heading { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }h4 { color: #243448; font-size: 14px; margin: 0; }
p { color: #657489; line-height: 1.6; font-size: 12px; margin: 8px 0; }
</style>
