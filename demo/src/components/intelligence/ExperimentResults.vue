<template>
  <section>
    <div class="heading"><h3>实验结果</h3><div v-if="record && record.status === 'completed'"><el-button size="small" @click="$emit('rerun', record.id)">按相同条件重跑</el-button><a :href="`/api/intelligence/experiments/${record.id}/export`" download><el-button size="small">导出 CSV</el-button></a></div></div>
    <el-empty v-if="!record" description="填写条件并运行，或选择一条历史实验" />
    <el-alert v-else-if="record.status === 'failed'" :title="record.error" type="error" :closable="false" />
    <div v-else-if="record.status !== 'completed'" class="waiting"><i class="el-icon-loading" /> 实验正在运行，完成后自动显示结果</div>
    <template v-else>
      <p class="conditions">{{ record.config.start_date }} 起 {{ record.config.days }} 天 · {{ record.config.base_airport }} · {{ weather[record.config.weather] }} · 客流 {{ record.config.demand_factor }} 倍 · {{ record.config.capacity }} 条跑道 · 种子 {{ record.config.seed }}</p>
      <div class="metrics"><div><strong>{{ result.metrics.flights }}</strong><span>航班</span></div><div><strong>{{ result.metrics.delayed }}</strong><span>延误超过 15 分钟</span></div><div><strong>{{ result.metrics.mean_delay }}</strong><span>实际平均延误分钟</span></div></div>
      <h4>预测与实际对照</h4>
      <p class="footnote">本次模型 MAE：{{ result.metrics.prediction_mae == null ? '未启用' : result.metrics.prediction_mae }} 分钟；历史均值 MAE：{{ result.metrics.baseline_mae }} 分钟。MAE 是预测与实际的平均绝对差。</p>
      <p v-if="result.metrics.prediction_accuracy != null" class="footnote">分类命中率：{{ (result.metrics.prediction_accuracy * 100).toFixed(2) }}%<span v-if="result.metrics.prediction_total">，判断正确 {{ result.metrics.prediction_correct }} / {{ result.metrics.prediction_total }} 架</span>（概率达到50%判为延误，实际超过15分钟算延误）。</p>
      <el-alert v-if="!result.prediction.enabled" :title="result.prediction.reason" type="warning" :closable="false" />
      <el-table :data="pageFlights" size="small" border>
        <el-table-column prop="flight_no" label="航班" width="95" />
        <el-table-column prop="departure_airport" label="出发" width="80" />
        <el-table-column prop="arrival_airport" label="到达" width="80" />
        <el-table-column label="延误风险"><template slot-scope="{ row }">{{ probability(row.prediction) }}<RiskExplanation :prediction="row.prediction" /></template></el-table-column>
        <el-table-column label="预测分钟"><template slot-scope="{ row }">{{ row.prediction && row.prediction.minutes != null ? row.prediction.minutes : '—' }}</template></el-table-column>
        <el-table-column prop="actual_delay" label="实际分钟" />
        <el-table-column label="历史均值"><template slot-scope="{ row }">{{ row.prediction ? row.prediction.baseline_minutes : '—' }}</template></el-table-column>
      </el-table>
      <el-pagination small layout="prev, pager, next, total" :total="result.flights.length" :page-size="20" :current-page.sync="page" />
      <h4>恢复策略比较</h4>
      <p class="recommendation">{{ result.recovery.reason }}</p>
      <p v-if="result.recovery.original" class="footnote">同一条件下原系统恢复代价：{{ result.recovery.original.cost }}，延误 {{ result.recovery.original.delay_minutes }} 分钟，取消 {{ result.recovery.original.canceled }} 班，未恢复 {{ result.recovery.original.unrecovered || 0 }} 架次（按取消等价代价计）。{{ result.recovery.guarded ? '候选计划代价更高，已建议保留原方案。' : '候选与原方案采用相同代价口径。' }}</p>
      <el-table :data="result.recovery.candidates" size="small" border>
        <el-table-column label="策略" min-width="140"><template slot-scope="{ row }">{{ row.name }} <el-tag v-if="result.recovery.recommended === row.strategy" size="mini" type="success">推荐</el-tag></template></el-table-column>
        <el-table-column prop="predicted_cost" label="预测代价" />
        <el-table-column label="预计延误/取消"><template slot-scope="{ row }">{{ row.predicted_delay_minutes == null ? '—' : row.predicted_delay_minutes }}分 / {{ row.predicted_cancellations == null ? '—' : row.predicted_cancellations }}班</template></el-table-column>
        <el-table-column prop="cost" label="实际代价" />
        <el-table-column prop="canceled" label="取消数" width="75" />
        <el-table-column label="校验结果" min-width="170"><template slot-scope="{ row }">{{ row.feasible ? '通过已实现的约束检查' : row.violations.join('；') }}</template></el-table-column>
      </el-table>
      <p class="footnote">代价为等价延误分钟，取消一班计 240，资源变更一次计 8。预计取消数是模型期望值，可能有小数；分项分别预测，不保证与总代价严格相加。页面展示模拟实验结果。</p>
    </template>
  </section>
</template>

<script>
import RiskExplanation from './RiskExplanation.vue'
export default {
  components: { RiskExplanation },
  props: { record: Object, weather: Object },
  data: () => ({ page: 1 }),
  computed: {
    result() { return this.record && this.record.result },
    pageFlights() { return this.result.flights.slice((this.page - 1) * 20, this.page * 20) }
  },
  watch: { 'record.id'() { this.page = 1 } },
  methods: { probability(prediction) { return prediction && prediction.probability != null ? `${(prediction.probability * 100).toFixed(1)}%` : '—' } }
}
</script>

<style scoped>
h3 { margin: 0; }
h4 { margin: 24px 0 12px; }
.heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.heading a { margin-left: 8px; }
.conditions, .footnote { color: #6b7788; font-size: 12px; line-height: 1.8; }
.metrics { display: flex; gap: 32px; margin: 22px 0; }
.metrics strong, .metrics span { display: block; }
.metrics strong { font-size: 25px; margin-bottom: 7px; color: #25384c; }
.metrics span { font-size: 12px; color: #6b7788; }
.waiting { padding: 50px 0; color: #6b7788; text-align: center; }
.recommendation { font-size: 13px; line-height: 1.8; }
.el-pagination { text-align: right; margin-top: 12px; }
</style>
