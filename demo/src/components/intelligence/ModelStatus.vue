<template>
  <section class="model-status">
    <div class="title"><h3>模型评估</h3><el-button size="small" :loading="training" @click="$emit('train')">重新训练并评估</el-button></div>
    <p v-if="!report">尚无训练结果。训练完成后可比较模型与简单方法的表现。</p>
    <template v-else>
      <div class="metrics">
        <div><span>延误区分能力 AUC</span><strong>{{ number(report.delay.auc, 3) }}</strong><small>随机判断的对照值为 0.5</small></div>
        <div><span>平均预测误差</span><strong>{{ number(report.delay.mae_minutes, 1) }} <em>分钟</em></strong><small>历史均值预测 {{ number(report.delay.baseline_mae_minutes, 1) }} 分钟</small></div>
        <div><span>恢复代价改善</span><strong>{{ number(report.recovery.improvement * 100, 1) }}<em>%</em></strong><small>{{ report.recovery.passed ? '留出场景达到推荐线' : '当前只并列展示候选' }}</small></div>
      </div>
      <p class="scope">分类命中率 {{ number(report.delay.accuracy * 100, 2) }}%，历史频率对照 {{ number(report.delay.baseline_accuracy * 100, 2) }}%。上方是离线训练成绩，当前是否启用以复核状态为准。</p>
      <p v-if="report.routing" class="scope">排班建议择优命中率 {{ number(report.routing.optimal_selection_rate * 100, 2) }}%，原默认 {{ number(report.routing.default_optimal_rate * 100, 2) }}%；平均计划代价改善 {{ number(report.routing.improvement * 100, 3) }}%。多数场景保留原默认，不宣称大幅节省。</p>
      <p v-if="report.recovery.baseline_definition" class="scope">恢复对照：{{ report.recovery.baseline_definition }}；高于原可行计划代价时保留原方案。</p>
      <p class="scope">{{ report.train_scenarios }} 组训练场景，{{ report.test_scenarios }} 组独立测试场景。{{ report.scope }}</p>
      <p v-if="report.external" class="scope">公开航班检查 {{ report.external.rows }} 条，AUC {{ number(report.external.auc, 3) }}，平均误差 {{ number(report.external.mae_minutes, 1) }} 分钟。{{ report.external.conclusion }}</p>
    </template>
    <p class="scope" v-if="languagePolicy">{{ languagePolicy.model }}：{{ languagePolicy.reason }}<span v-if="languagePolicy.cases"> 首轮提取正确 {{ languagePolicy.raw_exact }} / {{ languagePolicy.cases }}，最多两轮提取合并后 {{ languagePolicy.after_feedback_exact }} / {{ languagePolicy.cases }}。默认{{ languagePolicy.mode === 'template-fallback' ? '使用模板' : '使用本地模型，失败候选明确回退模板' }}。</span></p>
    <p class="scope" v-else>自然语言输入 {{ languageReady ? '本地模型文件已就绪' : '当前可使用描述模板' }}</p>
  </section>
</template>

<script>
export default {
  props: { report: Object, training: Boolean, languageReady: Boolean, languagePolicy: Object },
  methods: { number(value, digits) { return Number.isFinite(value) ? value.toFixed(digits) : '—' } }
}
</script>

<style scoped>
h3 { margin: 0; }
.title { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 22px 0; }
.metrics span, .metrics small { display: block; color: #66748a; font-size: 12px; }
.metrics strong { display: block; font-size: 27px; margin: 10px 0; font-weight: 600; color: #25384c; }
em { font-size: 13px; font-style: normal; }
.scope { font-size: 12px; line-height: 1.8; color: #66748a; margin-bottom: 0; }
@media (max-width: 700px) { .metrics { grid-template-columns: 1fr; } }
</style>
