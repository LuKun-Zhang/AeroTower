<template>
  <div class="condition-form">
    <div class="cf-section">
      <h3>基本信息</h3>
      <el-input v-model="form.name" size="small" maxlength="60" placeholder="实验名称" />
    </div>

    <div class="cf-section">
      <h3>客流与日期</h3>
      <div class="cf-row">
        <div class="cf-field">
          <label>实验日期</label>
          <el-select v-model="form.dates" multiple size="small" style="width:100%">
            <el-option v-for="d in dateOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </div>
        <div class="cf-field">
          <label>基地城市</label>
          <el-select v-model="form.bases" multiple size="small" style="width:100%">
            <el-option v-for="c in baseOptions" :key="c" :label="c" :value="c" />
          </el-select>
        </div>
      </div>
      <div class="cf-row">
        <div class="cf-field">
          <label>客流模板</label>
          <el-select v-model="form.traffic.template" size="small" style="width:100%">
            <el-option label="演示客流" value="demo" />
            <el-option label="自定义（粘贴）" value="custom" />
          </el-select>
        </div>
        <div class="cf-field">
          <label>全局缩放（模板模式）</label>
          <el-input-number v-model="form.traffic.scale" :min="0.1" :max="3" :step="0.1"
                           :precision="2" size="small" style="width:100%" />
        </div>
      </div>
      <div v-if="form.traffic.template === 'custom'">
        <label class="cf-label">城市对客流（每行：出发城市,到达城市,人次/天）</label>
        <el-input v-model="form.traffic.pastedText" type="textarea" :rows="5" size="small"
                  placeholder="北京,成都,1000&#10;成都,北京,900" />
      </div>
      <p class="cf-hint">日均总客流约 {{ totalPax }} 人次；留空则使用演示客流。</p>
    </div>

    <div class="cf-section">
      <h3>机队</h3>
      <div class="cf-row">
        <div class="cf-field">
          <label>机队规模</label>
          <el-input-number v-model="form.fleet.size" :min="10" :max="200" :step="10"
                           size="small" style="width:100%" @change="resetMix" />
        </div>
        <div class="cf-field">
          <label>机型配比（合计 {{ mixTotal }} / {{ form.fleet.size }}）</label>
          <div class="cf-mix">
            <span v-for="t in ['A319','A320','A321']" :key="t">
              {{ t }}
              <el-input-number v-model="form.fleet.mix[t]" :min="0" :max="form.fleet.size"
                               size="mini" controls-position="right" />
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="cf-section">
      <h3>算法选择</h3>
      <div class="cf-row">
        <div class="cf-field" v-for="group in algorithmGroups" :key="group.key">
          <label>{{ group.label }}</label>
          <el-select v-model="form.algorithms[group.key]" size="small" style="width:100%">
            <el-option v-for="opt in group.options" :key="opt.value"
                       :label="opt.label" :value="opt.value" />
          </el-select>
        </div>
      </div>
    </div>

    <div class="cf-section">
      <h3>中断情景</h3>
      <div class="cf-row">
        <div class="cf-field">
          <label>天气</label>
          <el-select v-model="form.disruption.weather" size="small" style="width:100%">
            <el-option v-for="w in weatherOptions" :key="w.value"
                       :label="w.label" :value="w.value" />
          </el-select>
          <p class="cf-hint">天气只影响延误与准点率，不改变航班计划</p>
        </div>
        <div class="cf-field">
          <label>异常</label>
          <el-select v-model="form.disruption.anomaly" size="small" style="width:100%">
            <el-option label="无" value="none" />
            <el-option label="机场临时关闭" value="airport_closure" />
          </el-select>
        </div>
      </div>
      <div v-if="form.disruption.anomaly === 'airport_closure'" class="cf-row">
        <div class="cf-field">
          <label>关闭机场</label>
          <el-input v-model="form.disruption.anomaly_params.airport" size="small" />
        </div>
        <div class="cf-field">
          <label>起止时刻</label>
          <div class="cf-dt">
            <el-input v-model="form.disruption.anomaly_params.start" size="small" placeholder="2020-11-30 10:00" />
            <span>至</span>
            <el-input v-model="form.disruption.anomaly_params.end" size="small" placeholder="2020-11-30 12:00" />
          </div>
        </div>
      </div>
    </div>

    <div class="cf-section">
      <h3>运行参数</h3>
      <div class="cf-row">
        <div class="cf-field">
          <label>客座率</label>
          <el-input-number v-model="form.load_factor" :min="0.3" :max="1" :step="0.01"
                           :precision="2" size="small" style="width:100%" />
        </div>
        <div class="cf-field">
          <label>过站时间（分钟）</label>
          <el-input-number v-model="form.min_turnaround" :min="20" :max="180" :step="5"
                           size="small" style="width:100%" />
        </div>
        <div class="cf-field">
          <label>单日最大段数</label>
          <el-input-number v-model="form.max_segments_per_day" :min="1" :max="8"
                           size="small" style="width:100%" />
        </div>
        <div class="cf-field">
          <label>随机种子</label>
          <el-input-number v-model="form.seed" :min="0" :max="999999"
                           size="small" style="width:100%" />
        </div>
      </div>
      <p class="cf-hint">同条件 + 同种子才能复现；留空会随机生成。</p>
    </div>

    <div class="cf-actions">
      <el-button type="primary" :loading="saving" @click="submit">保存并运行</el-button>
    </div>
  </div>
</template>

<script>
const DATES = ['2020-11-30', '2020-12-01', '2020-12-02', '2020-12-03', '2020-12-04', '2020-12-05']
const BASES = ['成都', '重庆', '昆明', '宜宾', '绵阳', '杭州']

export default {
  name: 'ConditionForm',
  props: { saving: { type: Boolean, default: false } },
  data() {
    return {
      dateOptions: DATES,
      baseOptions: BASES,
      weatherOptions: [
        { value: 'none', label: '无' },
        { value: 'sichuan_storm', label: '四川盆地雷暴（首日 14-18 时）' },
        { value: 'east_rain', label: '华东强降雨（次日 08-14 时）' },
        { value: 'south_typhoon', label: '华南台风（次日全天）' },
      ],
      algorithmGroups: [
        { key: 'routing', label: '飞机排班', options: [
          { value: 'chain_coverage', label: '链覆盖（推荐）' },
          { value: 'bipartite', label: '二分图匹配' },
          { value: 'greedy', label: '贪心' },
          { value: 'vrp', label: 'VRP 平衡贪心' },
        ] },
        { key: 'runway', label: '跑道调度', options: [
          { value: 'multi_runway', label: '多跑道贪心' },
          { value: 'optimized', label: 'ILS 局部优化' },
        ] },
        { key: 'gate', label: '登机口', options: [
          { value: 'bipartite', label: '二分图' },
          { value: 'greedy', label: '评分贪心' },
        ] },
        { key: 'crew', label: '机组排班', options: [
          { value: 'chain', label: '飞机链切割' },
          { value: 'pairing', label: 'Pairing 拆分' },
        ] },
      ],
      form: {
        name: '实验 ' + new Date().toLocaleString('zh-CN', { hour12: false }).slice(0, 16),
        dates: ['2020-11-30'],
        bases: ['成都'],
        traffic: { template: 'demo', scale: 1, pastedText: '' },
        fleet: { size: 100, mix: { A319: 10, A320: 50, A321: 40 } },
        algorithms: { routing: 'chain_coverage', runway: 'multi_runway', gate: 'bipartite', crew: 'chain' },
        disruption: {
          weather: 'none', anomaly: 'none',
          anomaly_params: { airport: '成都', start: '2020-11-30 10:00', end: '2020-11-30 12:00' },
        },
        load_factor: 0.78,
        min_turnaround: 60,
        max_segments_per_day: 5,
        seed: Math.floor(100000 + Math.random() * 900000),
      },
    }
  },
  computed: {
    mixTotal() {
      return ['A319', 'A320', 'A321'].reduce((n, t) => n + (this.form.fleet.mix[t] || 0), 0)
    },
    totalPax() {
      if (this.form.traffic.template === 'custom') {
        const rows = this.parsePasted()
        return rows.reduce((n, r) => n + r.daily_pax, 0)
      }
      const demo = 17980
      return Math.round(demo * this.form.traffic.scale)
    },
  },
  methods: {
    resetMix(size) {
      this.form.fleet.mix = {
        A319: Math.round(size * 0.1),
        A320: Math.round(size * 0.5),
        A321: size - Math.round(size * 0.1) - Math.round(size * 0.5),
      }
    },
    parsePasted() {
      const rows = []
      for (const line of (this.form.traffic.pastedText || '').split('\n')) {
        const text = line.trim()
        if (!text) continue
        const parts = text.split(/[,，\s]+/)
        if (parts.length < 3) continue
        const pax = parseInt(parts[2], 10)
        if (!parts[0] || !parts[1] || parts[0] === parts[1] || isNaN(pax) || pax <= 0) continue
        rows.push({ origin: parts[0], destination: parts[1], daily_pax: pax })
      }
      return rows
    },
    buildPayload() {
      if (!this.form.dates.length || !this.form.bases.length) {
        this.$message.warning('请选择日期与基地')
        return null
      }
      if (this.mixTotal !== this.form.fleet.size) {
        this.$message.warning('机型配比合计必须等于机队规模')
        return null
      }
      const traffic = { template: this.form.traffic.template, scale: this.form.traffic.scale }
      if (this.form.traffic.template === 'custom') {
        traffic.pasted = this.parsePasted()
        if (!traffic.pasted.length) {
          this.$message.warning('请至少填写一条有效的城市对客流')
          return null
        }
      }
      return {
        name: this.form.name,
        dates: this.form.dates,
        bases: this.form.bases,
        traffic,
        fleet: this.form.fleet,
        algorithms: this.form.algorithms,
        disruption: this.form.disruption,
        load_factor: this.form.load_factor,
        min_turnaround: this.form.min_turnaround,
        max_segments_per_day: this.form.max_segments_per_day,
        seed: this.form.seed,
      }
    },
    submit() {
      const payload = this.buildPayload()
      if (payload) this.$emit('submit', payload)
    },
  },
}
</script>

<style scoped>
.condition-form { color: #cdd6f4; }
.cf-section { background: #1e1e2e; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; }
.cf-section h3 { margin: 0 0 10px; font-size: 13px; color: #8a8aaa; font-weight: 500; }
.cf-row { display: flex; gap: 16px; flex-wrap: wrap; }
.cf-field { flex: 1; min-width: 180px; margin-bottom: 8px; }
.cf-field label, .cf-label { display: block; font-size: 12px; color: #6a6a8a; margin-bottom: 4px; }
.cf-mix { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.cf-mix > span { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #8a8aaa; }
.cf-dt { display: flex; align-items: center; gap: 6px; }
.cf-dt span { color: #6a6a8a; font-size: 12px; }
.cf-hint { margin: 4px 0 0; font-size: 12px; color: #6a6a8a; }
.cf-actions { text-align: center; padding: 8px 0 20px; }
::v-deep .el-input__inner, ::v-deep .el-textarea__inner {
  background: #2d2d44; border-color: #3d3d5c; color: #cdd6f4;
}
</style>
