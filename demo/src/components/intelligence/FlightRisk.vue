<template>
  <section class="flight-risk">
    <h3>延误风险预估</h3>
    <div class="controls">
      <span>天气</span><el-select v-model="weather" size="small"><el-option v-for="(label, key) in choices" :key="key" :label="label" :value="key" /></el-select>
      <span>可用跑道</span><el-input-number v-model="capacity" :min="1" :max="4" size="small" />
      <span>前序延误分钟</span><el-input-number v-model="previousDelay" :min="0" :max="180" size="small" />
      <el-button size="small" :loading="loading" @click="predict">按上述条件预估</el-button>
    </div>
    <p>{{ note || '请先确认当前条件。预测按本系统模拟样本训练，供实验参考。' }}</p>
  </section>
</template>

<script>
import api from '@/api/intelligence'
export default {
  props: { flights: Array },
  data: () => ({ weather: 'clear', capacity: 2, previousDelay: 0, loading: false, note: '', revision: 0,
    choices: { clear: '晴朗', rain: '降雨', storm: '雷暴', fog: '大雾', snow: '降雪' } }),
  watch: { weather: 'clearPrediction', capacity: 'clearPrediction', previousDelay: 'clearPrediction', flights: 'clearPrediction' },
  methods: {
    clearPrediction() { this.revision++; this.note = ''; this.$emit('predicted', {}) },
    async predict() {
      this.loading = true
      const revision = this.revision
      try {
        const result = await api.predict(this.flights, { weather: this.weather, capacity: this.capacity,
          previous_delay: this.previousDelay, flight_count: Math.max(8, Math.min(240, this.flights.length)) })
        if (revision !== this.revision) return
        this.note = result.reason || result.scope
        this.$emit('predicted', Object.fromEntries(result.flights.map(row => [row.flight_id, row])))
      } catch (error) { this.note = error.message } finally { this.loading = false }
    }
  }
}
</script>

<style scoped>
.flight-risk { color: #243448; background: white; padding: 20px; border: 1px solid #e8edf3; border-radius: 8px; margin: 18px 0; }
h3 { margin: 0 0 14px; }
.controls { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13px; }
.el-select { width: 110px; }
.el-input-number { width: 115px; }
p { color: #6b7788; font-size: 12px; margin-bottom: 0; }
</style>
