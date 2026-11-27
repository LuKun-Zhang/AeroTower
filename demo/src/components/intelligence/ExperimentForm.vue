<template>
  <section>
    <h3>确认实验条件</h3>
    <el-form label-position="top" size="small" class="conditions">
      <el-form-item label="实验开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="yyyy-MM-dd" :clearable="false" /></el-form-item>
      <el-form-item label="连续运行天数"><el-input-number v-model="form.days" :min="1" :max="7" /></el-form-item>
      <el-form-item label="基地机场"><el-select v-model="form.base_airport"><el-option v-for="name in options.airports" :key="name" :value="name" :label="name" /></el-select></el-form-item>
      <el-form-item label="天气"><el-select v-model="form.weather"><el-option v-for="(label, key) in options.weather" :key="key" :value="key" :label="label" /></el-select></el-form-item>
      <el-form-item label="基准航班数"><el-input-number v-model="form.flight_count" :min="8" :max="240" /></el-form-item>
      <el-form-item label="客流比例"><el-input-number v-model="form.demand_factor" :min="0.5" :max="2" :step="0.1" :precision="2" /></el-form-item>
      <el-form-item label="可用跑道数"><el-input-number v-model="form.capacity" :min="1" :max="4" /></el-form-item>
      <el-form-item label="前序延误分钟"><el-input-number v-model="form.previous_delay" :min="0" :max="180" /></el-form-item>
      <el-form-item label="异常类型"><el-select v-model="form.event_type"><el-option v-for="(label, key) in eventNames" :key="key" :value="key" :label="label" /></el-select></el-form-item>
      <el-form-item label="异常持续分钟"><el-input-number v-model="form.disruption_minutes" :min="0" :max="480" /></el-form-item>
      <el-form-item label="可用备份飞机数"><el-input-number v-model="form.backup_aircraft" :min="0" :max="12" /></el-form-item>
      <el-form-item label="可用备份机组数"><el-input-number v-model="form.backup_crew" :min="0" :max="12" /></el-form-item>
      <el-form-item label="可用备份登机口数"><el-input-number v-model="form.backup_gates" :min="0" :max="12" /></el-form-item>
      <el-form-item label="开始小时"><el-input-number v-model="form.start_hour" :min="0" :max="18" /></el-form-item>
      <el-form-item label="首段起飞分布窗口（分钟）"><el-input-number v-model="form.spread_minutes" :min="60" :max="720" /></el-form-item>
      <el-form-item label="场景随机种子"><el-input-number v-model="form.seed" :min="0" :max="2147483647" /></el-form-item>
      <el-form-item label="模型参与预测与推荐"><el-switch v-model="form.model_enabled" active-text="启用" inactive-text="对照" /></el-form-item>
    </el-form>
    <p class="hint">表单值会随实验保存。同一条件和种子可以重跑。</p>
    <el-button type="primary" :loading="busy" @click="$emit('run', { ...form })">确认条件并运行</el-button>
    <el-button :disabled="busy" @click="$emit('batch', { ...form })">比较三种天气</el-button>
  </section>
</template>

<script>
export default {
  props: { value: Object, options: Object, busy: Boolean },
  data: () => ({ form: {}, eventNames: { airport_closure: '机场关闭', aircraft_failure: '飞机故障', crew_absence: '机组请假', gate_failure: '登机口故障' } }),
  watch: {
    value: { immediate: true, handler(value) { if (JSON.stringify(value) !== JSON.stringify(this.form)) this.form = { ...value } } },
    form: { deep: true, handler(value) { if (JSON.stringify(value) !== JSON.stringify(this.value)) this.$emit('input', { ...value }) } }
  }
}
</script>

<style scoped>
h3 { margin: 0 0 16px; }
.conditions { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
.conditions .el-form-item { margin-bottom: 14px; }
.conditions .el-select, .conditions .el-input-number, .conditions .el-date-editor { width: 100%; }
.hint { color: #6b7788; font-size: 12px; line-height: 1.6; }
.el-button { margin: 5px 6px 0 0; }
</style>
