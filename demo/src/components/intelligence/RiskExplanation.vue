<template>
  <el-popover v-if="prediction && prediction.probability != null" placement="top" width="380" trigger="click">
    <div class="risk-explanation">
      <h4>延误风险依据</h4>
      <p>固定该航班其他输入，比较当前设置与下列参考条件。正值表示当前设置的预测更高，负值表示更低。</p>
      <ul v-if="prediction.effects && prediction.effects.length">
        <li v-for="effect in prediction.effects" :key="effect.factor"><strong>{{ effect.factor }}</strong>（参考：{{ effect.reference }}）<br>风险 {{ signed(effect.probability_delta * 100) }} 个百分点；预计延误 {{ signed(effect.minutes_delta) }} 分钟</li>
      </ul>
      <p v-else-if="prediction.effects">当前条件均采用所检查因素的参考值，没有额外因素可对照。</p>
      <p v-else>这条旧记录没有保存因素对照；按相同条件重跑可生成。</p>
      <p class="scope">这是模型敏感性对照，不代表现实因果，也不表示参考资源实际可用。</p>
    </div>
    <el-button slot="reference" type="text" size="mini">查看依据</el-button>
  </el-popover>
</template>

<script>
export default {
  props: { prediction: Object },
  methods: { signed(value) { const rounded = Number(value.toFixed(1)); return `${rounded > 0 ? '+' : ''}${rounded.toFixed(1)}` } }
}
</script>

<style scoped>
.risk-explanation { color: #243448; font-size: 13px; line-height: 1.65; }
h4 { color: #243448; font-size: 14px; margin: 0 0 8px; }
ul { padding-left: 18px; margin: 10px 0; }
li { margin-bottom: 10px; }
.scope { color: #6b7788; font-size: 12px; }
.el-button { padding: 2px 0; display: block; }
</style>
