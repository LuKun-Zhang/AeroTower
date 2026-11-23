<template>
  <div class="filter-page">
    <div class="page-header">
      <h2>航班计划筛选</h2>
      <p>上传原始航班计划 xlsx → 筛选合格任务链 → 保存 → 自动排班</p>
      <div v-if="filteredMode" class="active-badge">已激活筛选模式 — 所有排班模块使用 {{ activeFlightCount }} 条合格航班</div>
    </div>

    <!-- 操作栏 -->
    <div class="toolbar">
      <div class="upload-section">
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.xls"
          style="display:none"
          @change="handleUpload"
        />
        <el-button type="primary" size="small" @click="$refs.fileInput.click()" :loading="uploading">
          {{ uploadedFile ? '更换文件' : '上传航班计划 xlsx' }}
        </el-button>
        <span v-if="uploadedFile" class="file-hint">已加载: {{ uploadedFile }} ({{ uploadedCount }}条)</span>
      </div>

      <div class="action-group">
        <el-button size="small" type="primary" plain icon="el-icon-data-analysis" @click="openCharts">图表</el-button>
        <el-button type="success" size="small" @click="runFilter" :loading="filtering" :disabled="!uploadedFile && !hasDefault">
          执行筛选
        </el-button>
        <el-button type="warning" size="small" @click="applyAndSchedule" :loading="applying" :disabled="!filterResult">
          保存并执行排班计划
        </el-button>
        <el-button size="small" @click="exportResult" :disabled="!filterResult" icon="el-icon-download">
          导出 xlsx
        </el-button>
      </div>
    </div>

    <!-- 筛选统计 -->
    <div class="stats-panel" v-if="filterResult">
      <div class="stat-item highlight">
        <span class="stat-value">{{ stats.total_flights }}</span>
        <span class="stat-label">总航班</span>
      </div>
      <div class="stat-item good">
        <span class="stat-value">{{ stats.closed_count }}</span>
        <span class="stat-label">合格航班</span>
      </div>
      <div class="stat-item warn">
        <span class="stat-value">{{ stats.orphan_count }}</span>
        <span class="stat-label">不合格航班</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ stats.coverage_pct }}%</span>
        <span class="stat-label">覆盖率</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ chainTotal }}</span>
        <span class="stat-label">任务链</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ stats.elapsed_sec }}s</span>
        <span class="stat-label">耗时</span>
      </div>
    </div>

    <div class="bases-info" v-if="bases.length">
      <span>川航基地: </span>
      <el-tag v-for="b in bases" :key="b" size="small" type="success" style="margin-right:4px">{{ b }}</el-tag>
      <span style="margin-left:12px">站点覆盖: {{ stats.city_coverage }}</span>
    </div>

    <div class="main-content" v-if="filterResult">
      <!-- 左侧: 任务链池 -->
      <div class="panel chains-panel">
        <h4>任务链池 ({{ chains.length }} / {{ chainTotal }}条)</h4>
        <div class="chains-list">
          <div
            v-for="(chain, ci) in chains"
            :key="ci"
            class="chain-item"
            @click="selectedChainIdx = ci"
            :class="{ active: selectedChainIdx === ci }"
          >
            <div class="chain-header">
              <span class="chain-id">链 #{{ chainOffset + ci + 1 }}</span>
              <span class="chain-info">{{ chain.length }}段 | {{ chainDays(chain) }}</span>
            </div>
            <div class="chain-summary">
              <span class="chain-route">
                {{ chain[0].departure_airport }}
                <span v-for="i in Math.min(2, chain.length-1)" :key="i">→ ...</span>
                → {{ chain[chain.length-1].arrival_airport }}
              </span>
            </div>
          </div>
        </div>
        <div v-if="chains.length < chainTotal" class="load-more-wrap">
          <el-button size="small" @click="loadMoreChains" :loading="chainLoading">
            加载更多任务链 (已显示 {{ chains.length }} / {{ chainTotal }})
          </el-button>
        </div>
      </div>

      <!-- 中间: 选中任务链详情 -->
      <div class="panel detail-panel" v-if="selectedChainIdx !== null && chains[selectedChainIdx]">
        <h4>任务链 #{{ chainOffset + selectedChainIdx + 1 }} 详情</h4>
        <div class="chain-detail-list">
          <div v-for="(f, fi) in chains[selectedChainIdx]" :key="fi" class="flight-row">
            <span class="seg-num">{{ fi + 1 }}.</span>
            <span class="flight-no">{{ f.flight_no }}</span>
            <span class="route">{{ f.departure_airport }} → {{ f.arrival_airport }}</span>
            <br />
            <span class="time">{{ f.time_departure }}</span>
            <span class="arrow">→</span>
            <span class="time">{{ f.time_arrival }}</span>
            <span class="dur">{{ f.timespan }}分钟</span>
          </div>
        </div>
      </div>
      <div class="panel detail-panel" v-else>
        <div class="empty-hint">点击左侧任务链查看详情</div>
      </div>

      <!-- 右侧: 不合格航班 -->
      <div class="panel orphans-panel">
        <h4>不合格航班 ({{ orphans.length }} / {{ orphanTotal }}条)</h4>
        <div class="orphan-reasons" v-if="orphanReasons.length">
          <div v-for="r in orphanReasons" :key="r.reason" class="reason-bar">
            <span class="reason-count">{{ r.count }}</span>
            <span class="reason-text">{{ r.reason }}</span>
          </div>
        </div>
        <div class="orphans-table-wrap">
          <table class="orphans-table">
            <thead>
              <tr>
                <th>航班号</th>
                <th>出发</th>
                <th>到达</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(o, i) in orphans" :key="i">
                <td>{{ o.flight.flight_no }}</td>
                <td>{{ o.flight.departure_airport }}</td>
                <td>{{ o.flight.arrival_airport }}</td>
                <td class="reason-cell" :title="o.reason">{{ o.reason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="orphans.length < orphanTotal" class="load-more-wrap">
          <el-button size="small" @click="loadMoreOrphans" :loading="orphanLoading">
            加载更多不合格航班 (已显示 {{ orphans.length }} / {{ orphanTotal }})
          </el-button>
        </div>
      </div>
    </div>

    <div v-else-if="!uploadedFile" class="empty-state">
      <p>请上传航班计划 xlsx 文件，或直接点击「执行筛选」使用默认数据</p>
    </div>

    <chart-overlay :visible.sync="chartsOpen" :charts="chartList" title="航班筛选" />
  </div>
</template>

<script>
import ChartOverlay from '@/components/ChartOverlay'
import { buildFilterCharts } from '@/utils/charts/filterView'

const PAGE_SIZE_CHAINS = 50
const PAGE_SIZE_ORPHANS = 50

export default {
  components: { ChartOverlay },
  data() {
    return {
      chartsOpen: false,
      chartList: [],
      uploadedFile: '',
      uploadedCount: 0,
      uploading: false,
      filtering: false,
      applying: false,
      hasDefault: true,
      filteredMode: false,
      activeFlightCount: 0,
      filterResult: null,
      stats: {},
      bases: [],
      chains: [],
      chainTotal: 0,
      chainOffset: 0,
      chainLoading: false,
      orphans: [],
      orphanTotal: 0,
      orphanOffset: 0,
      orphanLoading: false,
      selectedChainIdx: null,
    }
  },
  mounted() {
    this.checkStatus()
    // 监听恢复执行完成事件，强制下次激活时刷新筛选结果
    this.$root.$on('filter-needs-refresh', () => {
      this.filterResult = null
    })
  },
  beforeDestroy() {
    this.$root.$off('filter-needs-refresh')
  },
  activated() {
    this.checkStatus()
  },
  computed: {
    orphanReasonMap() {
      // 从当前已加载的 orphans 计算原因分布
      const map = {}
      for (const o of this.orphans) {
        const r = o.reason || '未知原因'
        map[r] = (map[r] || 0) + 1
      }
      return map
    },
    orphanReasons() {
      const arr = []
      for (const [reason, count] of Object.entries(this.orphanReasonMap)) {
        arr.push({ reason, count })
      }
      arr.sort((a, b) => b.count - a.count)
      return arr.slice(0, 5)
    },
  },
  methods: {
    openCharts() {
      this.chartList = buildFilterCharts(this)
      this.chartsOpen = true
    },
    async checkStatus(retryCount) {
      retryCount = retryCount || 0
      const uname = this._getUsername()
      try {
        const resp = await fetch('/api/flights/status?username=' + encodeURIComponent(uname))
        const json = await resp.json()
        if (json.code === 0) {
          this.filteredMode = json.data.filtered_mode
          this.activeFlightCount = json.data.active_flights
          if (json.data.uploaded_file) {
            this.uploadedFile = json.data.uploaded_file
            this.uploadedCount = json.data.uploaded_count
          }
          // 首次进入或数据已过期时加载筛选结果
          if (this.filteredMode && !this.filterResult) {
            console.log('[FilterView] 首次加载筛选结果...')
            await this.runFilter()
          }
          // 如果筛选模式未激活且带 history_id 参数，可能是后端尚未就绪，重试
          if (!this.filteredMode && this.$route.params.id && retryCount < 5) {
            console.log(`[FilterView] 后端尚未就绪，${retryCount + 1}/5 次重试...`)
            await new Promise(resolve => setTimeout(resolve, 1000))
            return this.checkStatus(retryCount + 1)
          }
        }
      } catch (e) {
        console.warn('[FilterView] 状态检查失败:', e.message || e)
        // 网络错误时也重试
        if (this.$route.params.id && retryCount < 3) {
          await new Promise(resolve => setTimeout(resolve, 1500))
          return this.checkStatus(retryCount + 1)
        }
      }
    },
    _getUsername() {
      try {
        const u = JSON.parse(localStorage.getItem('current_user') || '{}')
        return u.username || ''
      } catch (e) {
        return ''
      }
    },
    async applyAndSchedule() {
      this.applying = true
      try {
        const uname = this._getUsername()
        const formData = new FormData()
        formData.append('username', uname)
        const resp = await fetch('/api/flights/apply', { method: 'POST', body: formData })
        const json = await resp.json()
        if (json.code !== 0) throw new Error(json.msg)
        this.filteredMode = true
        this.activeFlightCount = json.data.active_flights
        this.$message({
          message: `筛选完成：${json.data.active_flights} 条合格航班`,
          type: 'success',
          duration: 2500,
        })
      } catch (err) {
        this.$message.error('保存失败: ' + err.message)
      }
      this.applying = false
    },
    async handleUpload(e) {
      const file = e.target.files[0]
      if (!file) return
      this.uploading = true
      try {
        const uname = this._getUsername()
        const formData = new FormData()
        formData.append('file', file)
        formData.append('username', uname)
        const resp = await fetch('/api/flights/upload', { method: 'POST', body: formData })
        const json = await resp.json()
        if (json.code !== 0) throw new Error(json.msg)
        this.uploadedFile = file.name
        this.uploadedCount = json.data.flight_count
        this.$message.success(`上传成功: ${json.data.flight_count} 条航班, ${json.data.airport_count} 个机场`)
      } catch (err) {
        this.$message.error('上传失败: ' + err.message)
      }
      this.uploading = false
    },

    async _fetchFilterPage(chainOffset, chainLimit, orphanOffset, orphanLimit) {
      const params = new URLSearchParams({
        chain_offset: chainOffset,
        chain_limit: chainLimit,
        orphan_offset: orphanOffset,
        orphan_limit: orphanLimit,
      })
      const resp = await fetch(`/api/flights/filter?${params}`)
      const json = await resp.json()
      if (json.code !== 0) throw new Error(json.msg)
      return json.data
    },

    async runFilter() {
      this.filtering = true
      this.selectedChainIdx = null
      try {
        const data = await this._fetchFilterPage(0, PAGE_SIZE_CHAINS, 0, PAGE_SIZE_ORPHANS)
        this.filterResult = data
        this.stats = data.stats
        this.bases = data.bases || []
        this.chains = data.chains || []
        this.chainTotal = data.chain_total || 0
        this.chainOffset = 0
        this.orphans = data.orphan_flights || []
        this.orphanTotal = data.orphan_total || 0
        this.orphanOffset = 0
        this.$message.success(`筛选完成: ${this.stats.closed_count} 条合格, ${this.stats.orphan_count} 条不合格, ${this.chainTotal} 条任务链`)
      } catch (err) {
        this.$message.error('筛选失败: ' + err.message)
      }
      this.filtering = false
    },

    async loadMoreChains() {
      this.chainLoading = true
      try {
        const newOffset = this.chainOffset + this.chains.length
        const data = await this._fetchFilterPage(newOffset, PAGE_SIZE_CHAINS, 0, 0)
        this.chains = this.chains.concat(data.chains || [])
        this.chainTotal = data.chain_total || this.chainTotal
        this.chainOffset = newOffset
        this.$message.success(`已加载 ${this.chains.length} / ${this.chainTotal} 条任务链`)
      } catch (err) {
        this.$message.error('加载失败: ' + err.message)
      }
      this.chainLoading = false
    },

    async loadMoreOrphans() {
      this.orphanLoading = true
      try {
        const newOffset = this.orphanOffset + this.orphans.length
        const data = await this._fetchFilterPage(0, 0, newOffset, PAGE_SIZE_ORPHANS)
        this.orphans = this.orphans.concat(data.orphan_flights || [])
        this.orphanTotal = data.orphan_total || this.orphanTotal
        this.orphanOffset = newOffset
        this.$message.success(`已加载 ${this.orphans.length} / ${this.orphanTotal} 条不合格航班`)
      } catch (err) {
        this.$message.error('加载失败: ' + err.message)
      }
      this.orphanLoading = false
    },

    exportResult() {
      window.open('/api/flights/export', '_blank')
    },
    chainDays(chain) {
      const dates = new Set()
      for (const f of chain) {
        const m = (f.time_departure || '').match(/(\d+-\d+-\d+)/)
        if (m) dates.add(m[1])
      }
      return dates.size + '天'
    },
  },
}
</script>

<style scoped>
.filter-page {
  padding: 16px 20px;
  background: rgba(0,0,0,0.3);
  color: #eee;
  flex: 1;
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.page-header h2 { margin: 0 0 4px; font-size: 18px; color: #f5d0a9; }
.page-header p { margin: 0; font-size: 13px; color: #999; }
.active-badge {
  margin-top: 8px;
  padding: 6px 12px;
  background: rgba(103,194,58,0.2);
  border: 1px solid rgba(103,194,58,0.4);
  border-radius: 4px;
  font-size: 13px;
  color: #67c23a;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 14px 0;
  flex-wrap: wrap;
}
.file-hint { font-size: 12px; color: #aaa; margin-left: 8px; }
.action-group { display: flex; gap: 8px; }

.stats-panel {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.stat-item {
  background: rgba(255,255,255,0.08);
  border-radius: 8px;
  padding: 8px 16px;
  text-align: center;
  min-width: 90px;
}
.stat-item.highlight { border: 1px solid #409eff; }
.stat-item.good { border: 1px solid #67c23a; }
.stat-item.warn { border: 1px solid #e6a23c; }
.stat-value { display: block; font-size: 22px; font-weight: bold; }
.stat-label { display: block; font-size: 11px; color: #999; margin-top: 2px; }

.bases-info { margin-bottom: 10px; font-size: 13px; color: #aaa; }

.main-content {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
}
.panel {
  background: rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 12px;
  overflow-y: auto;
}
.panel h4 { margin: 0 0 8px; font-size: 14px; color: #f5d0a9; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; }

.chains-panel { flex: 0 0 280px; }
.chains-list { max-height: calc(100% - 30px); overflow-y: auto; }
.chain-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 6px;
  background: rgba(255,255,255,0.04);
  border: 1px solid transparent;
}
.chain-item:hover { background: rgba(255,255,255,0.08); }
.chain-item.active { border-color: #409eff; background: rgba(64,158,255,0.12); }
.chain-header { display: flex; justify-content: space-between; font-size: 12px; }
.chain-id { font-weight: bold; color: #409eff; }
.chain-info { color: #888; }
.chain-summary { margin-top: 4px; font-size: 12px; color: #aaa; }
.chain-route { color: #f5d0a9; }

.detail-panel { flex: 1; min-width: 200px; }
.chain-detail-list { overflow-y: auto; max-height: calc(100% - 30px); }
.flight-row {
  padding: 8px 10px;
  margin-bottom: 6px;
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
}
.seg-num { color: #409eff; font-weight: bold; margin-right: 6px; }
.flight-no { color: #f5d0a9; font-weight: bold; margin-right: 10px; }
.route { color: #ccc; }
.time { color: #aaa; }
.arrow { margin: 0 6px; color: #666; }
.dur { color: #888; margin-left: 10px; }

.orphans-panel { flex: 0 0 380px; display: flex; flex-direction: column; }
.orphan-reasons { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.reason-bar {
  background: rgba(230,162,60,0.15);
  border: 1px solid rgba(230,162,60,0.3);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 11px;
}
.reason-count { font-weight: bold; color: #e6a23c; margin-right: 4px; }
.reason-text { color: #ccc; }

.orphans-table-wrap { flex: 1; overflow-y: auto; }
.orphans-table { width: 100%; font-size: 12px; border-collapse: collapse; }
.orphans-table th {
  position: sticky; top: 0;
  background: rgba(0,0,0,0.5);
  padding: 6px 8px;
  text-align: left;
  color: #aaa;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.orphans-table td {
  padding: 5px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.reason-cell { color: #e6a23c; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: #777; }
.load-more-wrap {
  text-align: center;
  padding: 10px 0;
}
.empty-hint { text-align: center; color: #777; padding: 40px 0; }
</style>
