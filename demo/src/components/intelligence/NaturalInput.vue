<template>
  <section class="natural-input">
    <h3>用一句话配置</h3>
    <el-input v-model="text" type="textarea" :rows="3" maxlength="500" show-word-limit
              placeholder="例如：成都基地，客流涨两成，加一场雷暴" />
    <p v-if="defaultModel" class="hint">默认使用本地模型提取；失败时回退模板，生成可能需要1—2分钟。</p>
    <el-checkbox v-else v-model="tryModel" :disabled="loading">本次试用本地模型（可能需要1—2分钟）</el-checkbox>
    <el-button size="small" :loading="loading" @click="$emit('parse', { text, useModel: tryModel ? true : null })" :disabled="!text.trim()">生成条件草稿</el-button>
    <div v-if="draft" class="draft">
      <p>{{ draft.method === 'local-qwen' ? '本地模型已解析并核对原文' : '已按支持的描述模板提取' }}</p>
      <p v-if="!Object.keys(draft.fields).length">没有找到支持的明确条件，请直接填写下方表单。</p>
      <p v-for="(value, key) in draft.fields" :key="key">{{ labels[key] || key }} {{ display(key, value) }} <span>依据“{{ draft.evidence[key] }}”</span></p>
      <p v-for="warning in draft.warnings" :key="warning" class="warning">{{ warning }}</p>
      <p v-if="draft.model_error" class="warning">{{ draft.model_error.includes('内存') ? draft.model_error : '本地模型暂时不可用，已使用模板。' }}</p>
      <el-button size="small" type="primary" plain @click="$emit('apply', draft.fields)">填入表单，继续确认</el-button>
    </div>
  </section>
</template>

<script>
export default {
  props: { draft: Object, loading: Boolean, defaultModel: Boolean },
  data: () => ({ text: '', labels: { base_airport: '基地', demand_factor: '客流比例', weather: '天气',
    flight_count: '航班数', capacity: '可用跑道', backup_aircraft: '备份飞机', disruption_minutes: '异常时长',
    previous_delay: '前序延误', start_hour: '开始小时', start_date: '开始日期', days: '天数',
    backup_crew: '备用机组', backup_gates: '备用登机口', event_type: '异常类型' }, tryModel: false }),
  methods: {
    display(key, value) {
      return key === 'weather' ? ({ clear: '晴朗', rain: '降雨', storm: '雷暴', fog: '大雾', snow: '降雪' }[value]) : value
    }
  }
}
</script>

<style scoped>
h3 { margin: 0 0 14px; }
.natural-input > .el-button { margin-top: 12px; }
.el-checkbox { display: block; margin-top: 12px; white-space: normal; }
.draft { margin-top: 14px; font-size: 13px; line-height: 1.7; }
.draft span { color: #748194; }
.warning { color: #966319; }
</style>
