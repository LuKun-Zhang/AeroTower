<template>
  <div v-title data-title="旅客追溯" class="passenger-lookup-page">
    <div class="page-header">
      <h2>🔍 旅客追溯查询</h2>
    </div>

    <!-- 搜索栏 -->
    <div class="search-section">
      <el-input
        v-model="searchId"
        placeholder="输入旅客 ID，如 Pax-1130-00001"
        size="large"
        clearable
        @keyup.enter.native="searchPassenger"
        class="search-input"
      >
        <el-button slot="append" icon="el-icon-search" @click="searchPassenger" :loading="searching">
          查询
        </el-button>
      </el-input>
    </div>

    <!-- 搜索结果 -->
    <div v-if="passenger" class="result-section">
      <div class="passenger-card">
        <div class="card-header">
          <span class="pax-id-badge">{{ passenger.pax_id }}</span>
          <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
        </div>

        <el-row :gutter="16" class="info-grid">
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">出发城市</div>
              <div class="info-value">{{ passenger.origin }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">目的城市</div>
              <div class="info-value">{{ passenger.destination }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">日期</div>
              <div class="info-value">{{ passenger.date }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">航班号</div>
              <div class="info-value">{{ passenger.flight_no || '--' }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">座位号</div>
              <div class="info-value highlight">{{ passenger.seat || '--' }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="info-item">
              <div class="info-label">舱位</div>
              <div class="info-value">{{ cabinText }}</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 轨迹时间轴 -->
      <div class="timeline-section">
        <h3>旅客轨迹</h3>
        <el-timeline>
          <el-timeline-item
            v-for="step in timeline"
            :key="step.key"
            :type="step.type"
            :timestamp="step.time"
            :color="step.color"
          >
            {{ step.text }}
          </el-timeline-item>
        </el-timeline>
      </div>
    </div>

    <div v-else-if="searched" class="not-found">
      <p>未找到该旅客</p>
    </div>

    <div v-else class="hint-section">
      <p>输入旅客 ID 查询完整信息：出发城市、航班号、座位号、登机口、跑道</p>
      <el-divider />
      <p class="hint-examples">
        示例 ID：<el-tag size="mini" v-for="id in sampleIds" :key="id" @click="searchId = id; searchPassenger()" style="cursor:pointer;margin:0 4px">{{ id }}</el-tag>
      </p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PassengerLookup',
  data() {
    return {
      searchId: '',
      searching: false,
      searched: false,
      passenger: null,
      sampleIds: [],
    }
  },
  computed: {
    statusText() {
      return this.passenger?.flight_no ? '已分配' : '未分配'
    },
    statusType() {
      return this.passenger?.flight_no ? 'success' : 'info'
    },
    cabinText() {
      const cabin = this.passenger?.cabin
      if (cabin === 'business') return '公务舱'
      return '经济舱'
    },
    timeline() {
      if (!this.passenger) return []
      const p = this.passenger
      return [
        { key: 'ticket', type: 'primary', color: '#409eff',
          text: `购票：${p.origin} → ${p.destination}`, time: p.date },
        { key: 'checkin', type: 'primary', color: '#409eff',
          text: '值机', time: p.date + ' 起飞前2小时' },
        { key: 'security', type: 'primary', color: '#409eff',
          text: '安检 → 候机区', time: p.date + ' 起飞前1.5小时' },
        { key: 'boarding', type: 'success', color: '#67c23a',
          text: p.flight_no ? `登机：${p.flight_no} 座位 ${p.seat}` : '等待登机',
          time: p.flight_no ? p.date + ' 起飞前30分钟' : '--' },
        { key: 'takeoff', type: 'warning', color: '#e6a23c',
          text: p.flight_no ? `起飞：${p.flight_no}` : '等待起飞',
          time: '--' },
        { key: 'arrive', type: 'success', color: '#67c23a',
          text: `到达：${p.destination}`,
          time: '--' },
      ]
    },
  },
  methods: {
    async searchPassenger() {
      const id = this.searchId.trim()
      if (!id) return
      this.searching = true
      this.searched = true
      this.passenger = null
      try {
        const res = await fetch(`/api/generate/data?type=passengers&pax_id=${encodeURIComponent(id)}`)
        const json = await res.json()
        if (json.code === 0) {
          this.passenger = json.data
        }
      } catch (e) {
        this.$message.error('查询失败')
      } finally {
        this.searching = false
      }
    },
    async loadSampleIds() {
      try {
        const res = await fetch('/api/generate/data?type=passengers&limit=6')
        const json = await res.json()
        if (json.code === 0 && json.data.length) {
          this.sampleIds = json.data.map(p => p.pax_id)
        }
      } catch (e) { /* ignore */ }
    },
  },
  async mounted() {
    await this.loadSampleIds()
  },
}
</script>

<style scoped>
.passenger-lookup-page {
  padding: 20px 30px;
  background: #141428;
  min-height: 100vh;
  height: 100vh;
  overflow-y: auto;
  color: #cdd6f4;
}
.page-header h2 { margin: 0 0 20px 0; color: #fff; }
.search-section { max-width: 600px; margin-bottom: 30px; }
.search-input { background: #1e1e2e; }
.passenger-card {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.pax-id-badge {
  font-size: 18px;
  font-weight: 700;
  color: #ffd54f;
  font-family: 'Courier New', monospace;
}
.info-grid .el-col { margin-bottom: 12px; }
.info-item { padding: 8px 0; }
.info-label { font-size: 12px; color: #8a8aaa; margin-bottom: 4px; }
.info-value { font-size: 16px; color: #cdd6f4; font-weight: 600; }
.info-value.highlight { color: #ffd54f; font-size: 20px; }
.timeline-section {
  background: #1e1e2e;
  border-radius: 8px;
  padding: 20px;
}
.timeline-section h3 { margin: 0 0 16px 0; font-size: 14px; color: #8a8aaa; }
.hint-section { text-align: center; padding: 60px 0; color: #8a8aaa; }
.hint-examples { font-size: 13px; }
.not-found { text-align: center; padding: 40px; color: #f56c6c; }
::v-deep .el-timeline-item__node { background: #2d2d44; }
::v-deep .el-timeline-item__content { color: #cdd6f4; }
::v-deep .el-timeline-item__timestamp { color: #6a6a8a; }
::v-deep .el-input__inner {
  background: #2d2d44;
  border-color: #3d3d5c;
  color: #cdd6f4;
}
</style>
