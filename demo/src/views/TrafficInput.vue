<template>
  <div v-title data-title="客流量输入" class="traffic-input-page">
    <div class="page-header">
      <h2>📊 客流量数据输入</h2>
      <div class="header-actions">
        <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
        <el-button size="small" @click="loadDefaultData">加载演示数据</el-button>
        <el-button size="small" @click="clearAll">全部清零</el-button>
      </div>
    </div>

    <!-- 使用指引 -->
    <div class="guide-bar">
      <span>💡 系统已自动生成所有城市两两组合的方向客流（共 {{ allFlowCount }} 条）。按「起始站」筛选后直接填写各方向客流量（人次/天），客流量为 0 的条目也会显示。如 北京 → 成都 100 人：北京出港 100、成都进港 100。</span>
    </div>

    <!-- 全局参数 -->
    <div class="params-section">
      <h3>全局参数</h3>
      <el-row :gutter="16">
        <el-col :span="4">
          <label>目标枢纽</label>
          <el-input v-model="params.hub" size="small" disabled />
        </el-col>
        <el-col :span="4">
          <label>机队机型（100 架）</label>
          <div class="fleet-mix-display">
            <span class="mix-chip">A319 <i>×10</i></span>
            <span class="mix-chip">A320 <i>×50</i></span>
            <span class="mix-chip">A321 <i>×40</i></span>
          </div>
        </el-col>
        <el-col :span="4">
          <label>客座率</label>
          <el-input-number v-model="params.load_factor" :min="0.1" :max="1" :step="0.01" :precision="2" size="small" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <label>过站时间(分钟)</label>
          <el-input-number v-model="params.min_turnaround" :min="30" :max="120" :step="5" size="small" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <label>单日最大段数</label>
          <el-input-number v-model="params.max_segments_per_day" :min="2" :max="8" size="small" style="width:100%" />
        </el-col>
        <el-col :span="4">
          <label>日期范围</label>
          <el-select v-model="params.dates" multiple size="small" style="width:100%" placeholder="选择日期">
            <el-option v-for="d in dateOptions" :key="d" :label="d" :value="d" />
          </el-select>
        </el-col>
      </el-row>
      <el-row :gutter="16" style="margin-top:10px">
        <el-col :span="24">
          <label>川航基地（任务链首尾需落在基地，可多选）</label>
          <el-select v-model="params.bases" multiple size="small" style="width:100%" placeholder="选择基地城市">
            <el-option v-for="c in CITY_LIST" :key="c" :label="c" :value="c" />
          </el-select>
        </el-col>
      </el-row>
    </div>

    <!-- 方向流明细表（全量城市两两组合） -->
    <div class="table-section">
      <h3>方向客流明细（起始站 → 到达站）</h3>

      <!-- 起始站筛选 -->
      <div class="filter-bar">
        <label>起始站筛选：</label>
        <select v-model="originFilter" class="native-select filter-select">
          <option value="全部">全部城市</option>
          <option v-for="c in CITY_LIST" :key="c" :value="c">{{ c }}</option>
        </select>
        <span class="filter-hint">
          共 {{ filteredFlows.length }} 条方向流，其中 {{ nonZeroCount }} 条客流量 &gt; 0
        </span>
      </div>

      <el-table
        v-if="filteredFlows.length"
        :data="filteredFlows"
        border
        stripe
        size="small"
        style="width:100%"
        max-height="480"
      >
        <el-table-column label="序号" type="index" width="60" />
        <el-table-column label="起始站（出港）" width="160" align="center">
          <template #default="{ row }">
            <span class="origin-tag">{{ row.origin }}</span>
            <span v-if="isBase(row.origin)" class="base-mark">基</span>
          </template>
        </el-table-column>
        <el-table-column label="到达站（进港）" width="160" align="center">
          <template #default="{ row }">
            <span class="dest-tag">{{ row.destination }}</span>
            <span v-if="isBase(row.destination)" class="base-mark">基</span>
          </template>
        </el-table-column>
        <el-table-column label="客流量（人次/天）" min-width="200" align="center">
          <template #default="{ row }">
            <input
              type="number"
              class="pax-input"
              min="0"
              step="10"
              :value="row.daily_pax"
              @input="updatePax(row, $event)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button type="text" size="small" style="color:#f56c6c" @click="clearPax(row)">清零</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="empty-table" v-else>
        <p>暂无方向客流数据</p>
      </div>
    </div>

    <!-- 城市进出港汇总表（程序自动计算） -->
    <div class="table-section" v-if="citySummary.length">
      <h3>城市进出港汇总（自动计算）</h3>
      <el-table :data="citySummary" border stripe size="small" style="width:100%" max-height="480">
        <el-table-column label="城市" prop="city" width="180">
          <template #default="{ row }">
            <span v-if="row.city === params.hub" class="hub-tag">★ {{ row.city }}（枢纽）</span>
            <span v-else-if="row.is_base" class="base-tag">✈ {{ row.city }}（基地）</span>
            <span v-else>{{ row.city }}</span>
          </template>
        </el-table-column>
        <el-table-column label="出港（出发）" width="150" align="center">
          <template #default="{ row }">
            <span class="outbound-tag">{{ row.outbound }} 人</span>
          </template>
        </el-table-column>
        <el-table-column label="进港（到达）" width="150" align="center">
          <template #default="{ row }">
            <span class="inbound-tag">{{ row.inbound }} 人</span>
          </template>
        </el-table-column>
        <el-table-column label="出港占比" width="130" align="center">
          <template #default="{ row }">
            <span class="ratio-bar">{{ row.outbound_pct }}%</span>
          </template>
        </el-table-column>
        <el-table-column label="进港占比" width="130" align="center">
          <template #default="{ row }">
            <span class="ratio-bar">{{ row.inbound_pct }}%</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 生成按钮 -->
    <div class="action-section">
      <el-button
        type="primary"
        size="large"
        :loading="generating"
        :disabled="nonZeroCount === 0"
        @click="generateFlights"
        icon="el-icon-s-promotion"
      >
        {{ generating ? '正在生成航班计划...' : '生成航班计划' }}
      </el-button>
      <p class="action-hint" v-if="nonZeroCount > 0">
        当前共 {{ nonZeroCount }} 条方向流有效（客流量 &gt; 0），日均总客流量 {{ totalPax }} 人次
      </p>
    </div>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="客流量输入" />
  </div>
</template>

<script>
import ChartOverlay from '@/components/ChartOverlay'
import { buildTrafficCharts } from '@/utils/charts/trafficInput'

const CITY_LIST = [
  '成都', '北京', '上海', '广州', '深圳', '昆明', '杭州', '南京', '武汉',
  '长沙', '西安', '重庆', '贵阳', '拉萨', '三亚', '厦门', '青岛',
  '大连', '沈阳', '哈尔滨', '郑州', '天津', '济南', '福州', '南宁',
  '南昌', '合肥', '太原', '石家庄', '呼和浩特', '乌鲁木齐', '宜宾', '绵阳',
]

// 演示数据：18 个城市与成都（枢纽）的非对称双向客流
// 每项 [城市, 城市→成都, 成都→城市]，与后端 DEFAULT_TRAFFIC 保持一致
const DEFAULT_PAIRS = [
  ['北京', 1000, 900], ['上海', 900, 800], ['广州', 700, 650], ['深圳', 600, 550],
  ['昆明', 500, 450], ['杭州', 450, 400], ['南京', 400, 350], ['武汉', 350, 300],
  ['西安', 350, 300], ['重庆', 300, 250], ['长沙', 250, 200], ['贵阳', 200, 180],
  ['拉萨', 180, 150], ['三亚', 250, 200], ['厦门', 200, 180], ['青岛', 200, 180],
  ['沈阳', 180, 150], ['哈尔滨', 150, 130],
  ['宜宾', 120, 100], ['绵阳', 100, 80],
]

// 演示数据：基地间航线（非成都枢纽）的非对称双向客流
// 每项 [出发站, 到达站, 出发→到达, 到达→出发]，与后端 DEFAULT_TRAFFIC 保持一致
const DEFAULT_BASE_PAIRS = [
  ['重庆', '北京', 300, 250],
  ['昆明', '上海', 350, 300],
  ['宜宾', '杭州', 200, 180],
]

// 演示数据：三角航线（非基地城市之间的衔接航线，用于飞机轮转）
// 只有 成都↔X 的往返航班时，飞机到达 X 后唯一的选择就是飞回成都，
// 任务链必然退化成「成都↔X 每天往返」。增加城市间衔接航线后，
// 飞机到站后可以顺路接上下一个城市 → 形成 成都→X→Y→成都 的多城轮转。
// 每项 [出发站, 到达站, 出发→到达, 到达→出发]，与后端 DEFAULT_TRAFFIC 保持一致
const TRIANGLE_PAIRS = [
  ['贵阳', '重庆', 100, 90],
  ['贵阳', '昆明', 100, 90],
  ['广州', '深圳', 150, 130],
  ['广州', '三亚', 120, 100],
  ['广州', '长沙', 100, 90],
  ['武汉', '长沙', 100, 90],
  ['武汉', '南京', 90, 80],
  ['杭州', '上海', 130, 110],
  ['厦门', '福州', 90, 80],
  ['青岛', '济南', 90, 80],
  ['青岛', '大连', 80, 70],
  ['西安', '郑州', 90, 80],
  ['北京', '天津', 100, 90],
]

export default {
  name: 'TrafficInput',
  components: { ChartOverlay },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      params: {
        hub: '成都',
        bases: ['成都', '重庆', '昆明', '宜宾', '绵阳', '杭州'],
        load_factor: 0.78,
        min_turnaround: 60,
        max_segments_per_day: 5,
        max_daily_flight_hours: 8,
        num_aircraft: 100,
        dates: ['2020-11-30', '2020-12-01', '2020-12-02', '2020-12-03', '2020-12-04', '2020-12-05'],
      },
      // 全量两两组合：所有 (origin, destination) 且 origin !== destination
      flows: [],
      originFilter: '全部',
      generating: false,
      dateOptions: [
        '2020-11-30', '2020-12-01', '2020-12-02',
        '2020-12-03', '2020-12-04', '2020-12-05',
      ],
    }
  },
  computed: {
    CITY_LIST() {
      return CITY_LIST
    },
    allFlowCount() {
      return this.flows.length
    },
    // 按起始站筛选后的方向流
    filteredFlows() {
      if (this.originFilter === '全部') return this.flows
      return this.flows.filter(f => f.origin === this.originFilter)
    },
    // 客流量 > 0 的方向流数量
    nonZeroCount() {
      return this.flows.filter(f => f.daily_pax > 0).length
    },
    // 城市进出港汇总（程序自动计算）
    citySummary() {
      const map = {}
      for (const f of this.flows) {
        if (!map[f.origin]) map[f.origin] = { city: f.origin, outbound: 0, inbound: 0 }
        if (!map[f.destination]) map[f.destination] = { city: f.destination, outbound: 0, inbound: 0 }
        map[f.origin].outbound += f.daily_pax
        map[f.destination].inbound += f.daily_pax
      }
      return Object.values(map).map(c => {
        const total = c.outbound + c.inbound
        return {
          ...c,
          is_base: this.params.bases.includes(c.city),
          outbound_pct: total ? Math.round(c.outbound / total * 100) : 0,
          inbound_pct: total ? Math.round(c.inbound / total * 100) : 0,
        }
      })
    },
    totalPax() {
      return this.flows.reduce((sum, f) => sum + f.daily_pax, 0)
    },
  },
  methods: {
    openCharts() {
      this.chartList = buildTrafficCharts(this)
      this.chartsOpen = true
    },
    // 初始化全量两两组合（客流量默认 0）
    initFlows() {
      const flows = []
      for (const a of CITY_LIST) {
        for (const b of CITY_LIST) {
          if (a !== b) {
            flows.push({ origin: a, destination: b, daily_pax: 0 })
          }
        }
      }
      this.flows = flows
    },
    // 行内编辑客流量
    updatePax(row, e) {
      let v = parseInt(e.target.value, 10)
      if (isNaN(v) || v < 0) v = 0
      row.daily_pax = v
    },
    clearPax(row) {
      row.daily_pax = 0
    },
    clearAll() {
      this.flows.forEach(f => { f.daily_pax = 0 })
      this.$message.success('已全部清零')
    },
    loadDefaultData() {
      this.initFlows()
      const defaultMap = {}
      for (const [city, toHub, fromHub] of DEFAULT_PAIRS) {
        defaultMap[`${city}→${this.params.hub}`] = toHub    // 城市→成都（城市出港）
        defaultMap[`${this.params.hub}→${city}`] = fromHub  // 成都→城市（成都出港）
      }
      for (const [o, d, od, doPax] of DEFAULT_BASE_PAIRS) {
        defaultMap[`${o}→${d}`] = od
        defaultMap[`${d}→${o}`] = doPax
      }
      for (const [o, d, od, doPax] of TRIANGLE_PAIRS) {
        defaultMap[`${o}→${d}`] = od
        defaultMap[`${d}→${o}`] = doPax
      }
      for (const f of this.flows) {
        const key = `${f.origin}→${f.destination}`
        if (defaultMap[key]) f.daily_pax = defaultMap[key]
      }
      this.originFilter = '全部'
      this.$message.success(
        `已加载演示数据（${DEFAULT_PAIRS.length * 2 + DEFAULT_BASE_PAIRS.length * 2 + TRIANGLE_PAIRS.length * 2} 条方向流有效）`
      )
    },
    isBase(city) {
      return this.params.bases.includes(city)
    },
    async generateFlights() {
      const cityTraffic = this.flows
        .filter(f => f.daily_pax > 0)
        .map(f => ({ origin: f.origin, destination: f.destination, daily_pax: f.daily_pax }))

      if (cityTraffic.length === 0) {
        this.$message.warning('请至少填写一条客流量大于 0 的方向客流')
        return
      }

      this.generating = true
      const payload = {
        ...this.params,
        city_traffic: cityTraffic,
      }

      try {
        const res = await fetch('/api/generate/flights', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        const json = await res.json()
        if (json.code !== 0) {
          this.$message.error(json.msg || '生成失败')
          return
        }

        this.$message.success(
          `生成成功！${json.data.stats.total_flights} 个航班，${json.data.stats.total_chains} 条链（首尾均基地 ${json.data.stats.based_chains} 条，空飞 ${json.data.stats.ferry_flights || 0} 个），${json.data.stats.total_passengers} 旅客`
        )
        this.$router.push('/schedule-overview')
      } catch (e) {
        this.$message.error('请求失败: ' + e.message)
      } finally {
        this.generating = false
      }
    },
  },
  mounted() {
    if (this.flows.length === 0) {
      this.loadDefaultData()
    }
  },
}
</script>

<style scoped>
.traffic-input-page {
  padding: 20px 30px;
  background: #141428;
  min-height: 100vh;
  height: 100vh;
  overflow-y: auto;
  color: #cdd6f4;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0;
  color: #fff;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.guide-bar {
  background: #1a2a3e;
  border: 1px solid #2a4a6e;
  border-radius: 6px;
  padding: 10px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  color: #8ab4d8;
}
.params-section {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 20px;
}
.params-section h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #8a8aaa;
}
.params-section label {
  display: block;
  font-size: 12px;
  color: #6a6a8a;
  margin-bottom: 4px;
}
.params-section .el-col {
  margin-bottom: 8px;
}
.fleet-mix-display {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.mix-chip {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  height: 32px;
  padding: 0 10px;
  line-height: 30px;
  font-size: 13px;
  color: #cdd6f4;
  background: #2d2d44;
  border: 1px solid #3d3d5c;
  border-radius: 4px;
}
.mix-chip i {
  font-style: normal;
  font-weight: 700;
  color: #ffd54f;
}
.table-section {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 20px;
}
.table-section h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #8a8aaa;
}
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #8a8aaa;
}
.filter-select {
  width: 160px;
}
.filter-hint {
  color: #6a6a8a;
  font-size: 12px;
}
.empty-table {
  text-align: center;
  padding: 40px;
  color: #6a6a8a;
  font-size: 14px;
}
.origin-tag { color: #409eff; font-weight: 600; }
.dest-tag { color: #67c23a; font-weight: 600; }
.base-mark {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  font-size: 11px;
  line-height: 16px;
  color: #fff;
  background: #b8860b;
  border-radius: 3px;
  vertical-align: 1px;
}
.base-tag { color: #e6a23c; font-weight: 700; }
.inbound-tag { color: #67c23a; font-weight: 600; }
.outbound-tag { color: #409eff; font-weight: 600; }
.hub-tag { color: #ffd54f; font-weight: 700; }
.pax-count { font-weight: 700; font-size: 15px; }
.ratio-bar { font-family: 'Courier New', monospace; }

.action-section {
  text-align: center;
  padding: 20px 0;
}
.action-hint {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: #6a6a8a;
}

/* 行内客流量输入框 */
.pax-input {
  width: 140px;
  height: 30px;
  background: #2d2d44;
  border: 1px solid #3d3d5c;
  border-radius: 4px;
  color: #ffd54f;
  font-size: 14px;
  font-weight: 700;
  text-align: center;
  padding: 0 8px;
  outline: none;
}
.pax-input:focus {
  border-color: #409eff;
}

/* 原生 select（深色） */
.native-select {
  height: 34px;
  background: #2d2d44;
  border: 1px solid #3d3d5c;
  border-radius: 4px;
  color: #cdd6f4;
  font-size: 13px;
  padding: 0 10px;
  cursor: pointer;
  outline: none;
}
.native-select:focus {
  border-color: #409eff;
}
.native-select option {
  background: #2d2d44;
  color: #cdd6f4;
}

/* element-ui 深色覆盖 */
::v-deep .el-input__inner,
::v-deep .el-input-number input,
::v-deep .el-select .el-input__inner {
  background: #2d2d44;
  border-color: #3d3d5c;
  color: #cdd6f4;
}
::v-deep .el-table {
  background: transparent;
  color: #cdd6f4;
}
::v-deep .el-table th {
  background: #2d2d44;
  color: #8a8aaa;
}
::v-deep .el-table tr,
::v-deep .el-table td {
  background: transparent;
  border-color: #313145;
}
</style>
