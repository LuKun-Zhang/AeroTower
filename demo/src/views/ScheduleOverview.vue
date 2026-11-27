<template>
  <div v-title data-title="航班计划总览" class="schedule-overview-page">
    <div class="page-header">
      <el-button icon="el-icon-arrow-left" size="small" @click="$router.push('/traffic-input')">返回修改</el-button>
      <h2>📋 航班计划总览</h2>
    </div>

    <!-- 步骤指示器 -->
    <div class="steps-bar">
      <div class="step done"><span class="step-num">✓</span> 客流量输入</div>
      <div class="step-arrow">→</div>
      <div class="step active"><span class="step-num">2</span> 航班计划</div>
      <div class="step-arrow">→</div>
      <div class="step"><span class="step-num">3</span> 调度执行</div>
    </div>

    <div v-if="loading" class="empty-state">
      <p>正在加载航班计划数据...</p>
    </div>
    <div v-else-if="!statsData" class="empty-state">
      <p>暂无航班计划数据</p>
      <el-button type="primary" @click="$router.push('/traffic-input')">前往客流量输入</el-button>
    </div>

    <template v-else>
      <!-- KPI 摘要 -->
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.total_flights }}</div>
          <div class="kpi-label">总航班数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.total_chains }}</div>
          <div class="kpi-label">任务链数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.cities_covered }}</div>
          <div class="kpi-label">覆盖城市</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ (stats.total_passengers || 0).toLocaleString() }}</div>
          <div class="kpi-label">总旅客数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ (stats.total_seats || 0).toLocaleString() }}</div>
          <div class="kpi-label">总座位数</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ stats.ferry_flights || 0 }}</div>
          <div class="kpi-label">空飞（调机）</div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-row">
        <el-button type="primary" size="large" icon="el-icon-check" @click="commitAndGo" :loading="committing">
          确认并进入调度
        </el-button>
      </div>

      <!-- 任务链明细 -->
      <FlightRisk :flights="flights" @predicted="riskById = $event" />
      <div class="chains-section">
        <h3>任务链明细（{{ chains.length }} 条）</h3>
        <el-collapse v-model="activeChains">
          <el-collapse-item
            v-for="chain in chains"
            :key="chain.chain_id"
            :name="chain.chain_id"
          >
            <template #title>
              <div class="chain-title">
                <span class="chain-badge">链 {{ chain.chain_id }}</span>
                <span class="chain-info">{{ chain.ac_type || 'A319' }} / {{ chain.segments }}段 / {{ chain.total_pax }}旅客</span>
                <span class="chain-route">{{ chain.route }}</span>
              </div>
            </template>

            <!-- 展开后显示每段航班信息 -->
            <div class="chain-detail">
              <el-table :data="getChainFlights(chain)" border size="small" style="width:100%" :row-class-name="ferryRowClass">
                <el-table-column label="航班号" width="120">
                  <template #default="{ row: f }">
                    <span>{{ f.flight_no }}</span>
                    <span v-if="f.is_ferry" class="ferry-tag">空飞</span>
                  </template>
                </el-table-column>
                <el-table-column label="出发" width="180">
                  <template #default="{ row: f }">
                    {{ f.departure_airport }} {{ f.time_departure }}
                  </template>
                </el-table-column>
                <el-table-column label="到达" width="180">
                  <template #default="{ row: f }">
                    {{ f.arrival_airport }} {{ f.time_arrival }}
                  </template>
                </el-table-column>
                <el-table-column label="旅客数" width="80" align="center">
                  <template #default="{ row: f }">
                    <span v-if="f.is_ferry">—</span>
                    <span v-else>{{ f.pax_count }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="延误风险" width="115">
                  <template #default="{ row: f }">
                    <span v-if="riskById[f.flight_id] && riskById[f.flight_id].probability != null">{{ (riskById[f.flight_id].probability * 100).toFixed(1) }}% / {{ riskById[f.flight_id].minutes }}分</span>
                    <span v-else>尚未预估</span>
                    <RiskExplanation :prediction="riskById[f.flight_id]" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120" align="center">
                  <template #default="{ row: f }">
                    <el-button v-if="!f.is_ferry" type="text" size="mini" @click="viewFlightPax(f)">查看旅客</el-button>
                    <span v-else class="ferry-hint">不载客</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </template>
  </div>
</template>

<script>
import FlightRisk from '@/components/intelligence/FlightRisk'
import RiskExplanation from '@/components/intelligence/RiskExplanation'
export default {
  name: 'ScheduleOverview',
  components: { FlightRisk, RiskExplanation },
  data() {
    return {
      statsData: null,
      riskById: {},
      chainsList: [],
      flightsList: [],
      activeChains: [],
      committing: false,
      loading: true,
    }
  },
  computed: {
    stats() {
      return this.statsData || {}
    },
    chains() {
      return this.chainsList || []
    },
    flights() {
      return this.flightsList || []
    },
    username() {
      try {
        const u = JSON.parse(localStorage.getItem('current_user') || '{}')
        return u.username || ''
      } catch (e) {
        return ''
      }
    },
  },
  methods: {
    async loadData() {
      this.loading = true
      try {
        const res = await fetch('/api/generate/data?type=stats')
        const json = await res.json()
        if (json.code !== 0) {
          this.$message.warning(json.msg || '暂无数据')
          return
        }
        this.statsData = json.data

        // 同时拉链和航班
        const [chainRes, flightRes] = await Promise.all([
          fetch('/api/generate/data?type=chains'),
          fetch('/api/generate/data?type=flights&limit=2000'),
        ])
        const chainJson = await chainRes.json()
        const flightJson = await flightRes.json()
        if (chainJson.code === 0) this.chainsList = chainJson.data
        if (flightJson.code === 0) this.flightsList = flightJson.data
      } catch (e) {
        console.error('加载数据失败:', e)
        this.$message.error('加载航班数据失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    getChainFlights(chain) {
      return (chain.flights || [])
        .map(fid => this.flightsList.find(f => f.flight_id === fid))
        .filter(Boolean)
    },
    ferryRowClass({ row }) {
      return row.is_ferry ? 'ferry-row' : ''
    },
    viewFlightPax(flight) {
      this.$router.push(`/flight/${flight.flight_id}/passengers`)
    },
    async commitAndGo() {
      this.committing = true
      try {
        const res = await fetch('/api/generate/commit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: this.username }),
        })
        const json = await res.json()
        if (json.code !== 0) {
          this.$message.error(json.msg || '提交失败')
          return
        }
        this.$message.success(json.msg)
        const historyId = json.data && json.data.history_id
        if (historyId) {
          // 直接进入航班筛选页面（任务链池 = 本次生成的全部任务链，不合格航班 = 0）
          this.$router.push({ name: 'AnalysisApp', params: { id: historyId } })
        } else {
          this.$router.push('/')
        }
      } catch (e) {
        this.$message.error('请求失败: ' + e.message)
      } finally {
        this.committing = false
      }
    },
  },
  async mounted() {
    await this.loadData()
    if (!this.statsData) {
      this.$message.info('请先在客流量输入页生成航班计划')
    }
  },
}
</script>

<style scoped>
.schedule-overview-page {
  padding: 20px 30px;
  background: #141428;
  min-height: 100vh;
  height: 100vh;
  overflow-y: auto;
  color: #cdd6f4;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  color: #fff;
}
.steps-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding: 12px 20px;
  background: #1e1e2e;
  border-radius: 8px;
}
.step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #6a6a8a;
}
.step.active { color: #409eff; font-weight: 700; }
.step.done { color: #67c23a; }
.step-num {
  display: inline-flex;
  width: 22px; height: 22px;
  border-radius: 50%;
  background: #2d2d44;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
.step.active .step-num { background: #409eff; color: #fff; }
.step.done .step-num { background: #67c23a; color: #fff; }
.step-arrow { color: #4a4a6a; }
.kpi-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.kpi-card {
  flex: 1;
  background: #1e1e2e;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}
.kpi-value {
  font-size: 28px;
  font-weight: 700;
  color: #ffd54f;
  font-family: 'Courier New', monospace;
}
.kpi-label {
  font-size: 12px;
  color: #8a8aaa;
  margin-top: 4px;
}
.action-row {
  text-align: center;
  margin-bottom: 24px;
}
.chains-section {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 16px 20px;
}
.chains-section h3 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #8a8aaa;
}
.chain-title {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}
.chain-badge {
  background: #409eff;
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
}
.chain-info {
  color: #8a8aaa;
  font-size: 12px;
  white-space: nowrap;
}
.chain-route {
  color: #cdd6f4;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chain-detail {
  padding: 8px 0;
}
.ferry-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 0 4px;
  font-size: 11px;
  line-height: 16px;
  color: #fff;
  background: #e64545;
  border-radius: 3px;
  vertical-align: 1px;
}
.ferry-hint {
  color: #e64545;
  font-size: 12px;
  font-weight: 600;
}
/* 空飞（调机）航班整行红色标注 */
.ferry-row {
  background: rgba(230, 69, 69, 0.12) !important;
}
.ferry-row:hover > td {
  background: rgba(230, 69, 69, 0.2) !important;
}
.empty-state {
  text-align: center;
  padding: 80px 0;
  color: #8a8aaa;
}
::v-deep .el-collapse {
  border: none;
}
::v-deep .el-collapse-item__header {
  background: #2d2d44;
  color: #cdd6f4;
  border-color: #3d3d5c;
  padding: 0 12px;
  height: 40px;
  line-height: 40px;
}
::v-deep .el-collapse-item__wrap {
  background: #1e1e2e;
  border-color: #3d3d5c;
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
