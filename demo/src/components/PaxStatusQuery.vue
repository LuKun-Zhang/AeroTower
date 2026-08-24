<template>
  <div class="pax-query-panel">
    <div class="panel-header" @click="open = !open">
      <span>🔍 乘客粒子查询</span>
      <span class="toggle">{{ open ? '▼' : '▲' }}</span>
    </div>

    <div class="panel-body" v-if="open">
      <div class="query-row">
        <select v-model="flightNo" class="flight-select" :disabled="!flights.length" @change="onFlightChange">
          <option value="" disabled>选择航班号</option>
          <option v-for="f in flightOptions" :key="f.value" :value="f.value">
            {{ f.label }}
          </option>
        </select>
      </div>

      <!-- 乘客列表：选择航班后自动列出全部乘客状态 -->
      <div v-if="flightNo && paxList.length" class="pax-list-box">
        <div class="pax-list-header">
          全部乘客状态（{{ paxList.length }} 人）
          <span class="pax-summary">
            · 登机中 {{ boardingCount }} · 已登机 {{ boardedCount }}
          </span>
        </div>
        <div class="pax-list">
          <div v-for="p in paxList" :key="p.seq" class="pax-item" :class="'st-k-' + p.status">
            <span class="pax-seq">{{ p.paxId || ('#' + p.seq) }}</span>
            <span class="pax-badge" :class="'st-' + p.status">{{ p.statusText }}</span>
            <span class="pax-phase" v-if="p.phase">{{ p.phase }}</span>
          </div>
        </div>
      </div>

      <!-- 手动输入乘客编号查询（单独查询） -->
      <div class="query-row" style="margin-top:6px;">
        <input
          v-model="paxNo"
          class="pax-input"
          placeholder="乘客编号 或 序号（精准查询）"
          @keyup.enter="doQuery"
        />
      </div>
      <div class="query-actions">
        <button class="query-btn" @click="doQuery" :disabled="querying">精准查询</button>
        <button class="clear-btn" @click="clearResult">清除</button>
        <label class="auto-label">
          <input type="checkbox" v-model="autoRefresh" /> 实时刷新
        </label>
      </div>

      <!-- 精确查询结果 -->
      <div v-if="result && !flightNo" class="result-box" :class="'st-' + result.status">
        <div class="res-top">
          <span class="pax-id">{{ result.paxId || ('#' + paxNo) }}</span>
          <span class="status-badge" :class="'st-' + result.status">{{ result.statusText }}</span>
        </div>
        <div class="res-info">
          <template v-if="result.status === 'unknown'">
            <div class="info-line">{{ result.statusText }}</div>
          </template>
          <template v-else>
            <div class="info-line">航班：{{ result.flightNo || flightNo }}</div>
            <div class="info-line" v-if="result.paxSeq">航班内序号：{{ result.paxSeq }}</div>
            <div class="info-line" v-if="result.phase">阶段：{{ result.phase }}</div>
            <div class="info-line" v-if="result.terminal">航站楼：{{ result.terminal }}</div>
            <div class="info-line" v-if="result.gate">登机口：{{ result.gate }}</div>
            <div class="info-line" v-if="result.at != null">
              完成时刻：{{ formatMin(result.at) }}（模拟时间）
            </div>
            <div class="info-line hint">{{ statusHint }}</div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PaxStatusQuery',
  props: {
    queryFn: { type: Function, default: null },
    flights: { type: Array, default: () => [] },
  },
  data() {
    return {
      open: true,
      flightNo: '',
      paxNo: '',
      querying: false,
      autoRefresh: true,
      result: null,
      paxList: [],
      _timer: null,
      _listTimer: null,
    }
  },
  computed: {
    // 航班下拉：去重 + 显示航班号/类型/时刻
    flightOptions() {
      const seen = new Set()
      const list = []
      for (const f of this.flights) {
        if (!f || !f.flightNo || seen.has(f.flightNo)) continue
        seen.add(f.flightNo)
        const t = f.type === 'departure' ? '离港' : '到港'
        const time = f.type === 'departure'
          ? (f.takeoffTime != null ? this.formatMin(f.takeoffTime) : '')
          : (f.scheduledArr != null ? this.formatMin(f.scheduledArr) : '')
        list.push({
          value: f.flightNo,
          label: `${f.flightNo} · ${t} ${time}${f.paxTotal ? ' · ' + f.paxTotal + '人' : ''}`,
        })
      }
      return list
    },
    // 当前选中航班的乘客总数
    selectedFlight() {
      return this.flightNo ? this.flights.find(f => f.flightNo === this.flightNo) : null
    },
    // 乘客列表统计
    boardingCount() { return this.paxList.filter(p => p.status === 'boarding').length },
    boardedCount() { return this.paxList.filter(p => p.status === 'boarded').length },
    statusHint() {
      if (!this.result) return ''
      const hints = {
        not_entered: '该乘客尚未进入航站楼（未到航班登机时间或航班未开始）',
        boarding: '该乘客已在航站楼内，正在候机或前往登机口',
        deboarding: '该乘客正在下机，沿走廊前往出口',
        boarded: '该乘客已登机完毕，随航班起飞',
        exited: '该乘客已走出航站楼出口',
      }
      return hints[this.result.status] || ''
    },
  },
  watch: {
    // 当 flights 列表变化时（如 flux 同步），刷新乘客列表
    flights: {
      deep: false,
      handler() {
        if (this.flightNo && this.autoRefresh) {
          this.refreshPaxList()
        }
      },
    },
  },
  mounted() {
    // 实时刷新精确查询结果
    this._timer = setInterval(() => {
      if (this.autoRefresh && this.result && this.flightNo && this.paxNo) {
        this.refresh()
      }
      // 乘客列表实时刷新
      if (this.flightNo && this.autoRefresh && !this.paxNo) {
        this.refreshPaxList()
      }
    }, 800)
  },
  beforeDestroy() {
    if (this._timer) { clearInterval(this._timer); this._timer = null }
    if (this._listTimer) { clearInterval(this._listTimer); this._listTimer = null }
  },
  methods: {
    formatMin(min) {
      if (min == null || isNaN(min)) return '--'
      const h = Math.floor(min / 60) % 24
      const m = Math.floor(min % 60)
      return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0')
    },
    // 选择航班 → 自动拉取全部乘客状态
    onFlightChange() {
      this.paxNo = ''
      this.result = null
      this.paxList = []
      if (!this.flightNo) return
      const flight = this.selectedFlight
      if (!flight || !flight.paxTotal) return
      this.refreshPaxList()
    },
    // 批量刷新全部乘客状态
    refreshPaxList() {
      if (!this.queryFn || !this.flightNo) return
      const flight = this.selectedFlight
      if (!flight || !flight.paxTotal) { this.paxList = []; return }
      const list = []
      for (let seq = 1; seq <= flight.paxTotal; seq++) {
        try {
          const r = this.queryFn(this.flightNo, String(seq)) || {}
          list.push({
            seq,
            paxId: r.paxId || null,
            status: r.status || 'unknown',
            statusText: r.statusText || '未知',
            phase: r.phase || '',
          })
        } catch (e) {
          list.push({ seq, paxId: null, status: 'unknown', statusText: '查询异常', phase: '' })
        }
      }
      this.paxList = list
    },
    async refresh() {
      if (!this.queryFn) return
      try {
        this.result = this.queryFn(this.flightNo, this.paxNo) || null
      } catch (e) {
        console.warn('[PaxQuery] 刷新失败:', e)
      }
    },
    async doQuery() {
      const pno = this.paxNo.trim()
      if (!this.flightNo) {
        this.result = { status: 'unknown', statusText: '请选择航班号' }
        return
      }
      if (!pno) {
        this.result = { status: 'unknown', statusText: '请输入乘客编号或序号' }
        return
      }
      this.querying = true
      try {
        await this.refresh()
        if (!this.result) {
          this.result = { status: 'unknown', statusText: '查询失败' }
        }
      } finally {
        this.querying = false
      }
    },
    clearResult() {
      this.result = null
      this.paxNo = ''
    },
  },
}
</script>

<style scoped>
.pax-query-panel {
  background: #1e1e2e;
  border: 1px solid #313145;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  overflow: hidden;
}
.panel-header {
  padding: 6px 10px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  color: #cdd6f4;
  font-weight: 600;
  user-select: none;
}
.panel-header:hover { background: #252538; }
.toggle { color: #8a8aaa; font-size: 10px; }
.panel-body { padding: 6px 10px 10px; }

.query-row { margin-bottom: 6px; }
.flight-select {
  width: 100%;
  padding: 5px 6px;
  font-size: 12px;
  color: #cdd6f4;
  background: #2d2d44;
  border: 1px solid #3d3d5c;
  border-radius: 4px;
  outline: none;
}
.flight-select option { background: #2d2d44; color: #cdd6f4; }
.pax-input {
  width: 100%;
  padding: 5px 6px;
  font-size: 12px;
  color: #cdd6f4;
  background: #2d2d44;
  border: 1px solid #3d3d5c;
  border-radius: 4px;
  outline: none;
  box-sizing: border-box;
}
.pax-input::placeholder { color: #6a6a8a; }
.query-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.query-btn, .clear-btn {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
}
.query-btn {
  background: #409eff;
  color: #fff;
}
.query-btn:hover { background: #66b1ff; }
.query-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.clear-btn {
  background: #2d2d44;
  color: #8a8aaa;
  border-color: #444;
}
.clear-btn:hover { background: #3d3d5c; color: #cdd6f4; }
.auto-label {
  margin-left: auto;
  color: #8a8aaa;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
}

/* 乘客列表 */
.pax-list-box {
  border: 1px solid #3d3d5c;
  border-radius: 5px;
  background: #252538;
  margin-bottom: 6px;
  overflow: hidden;
}
.pax-list-header {
  padding: 5px 8px;
  font-size: 11px;
  color: #cdd6f4;
  font-weight: 600;
  border-bottom: 1px solid #313145;
}
.pax-summary { color: #8a8aaa; font-weight: 400; }
.pax-list {
  max-height: 180px;
  overflow-y: auto;
  padding: 4px;
}
.pax-list::-webkit-scrollbar { width: 3px; }
.pax-list::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }
.pax-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  margin-bottom: 2px;
  border-radius: 3px;
  font-size: 11px;
  background: rgba(255,255,255,0.03);
  border-left: 3px solid transparent;
}
.pax-item.st-k-boarding   { border-left-color: #409eff; }
.pax-item.st-k-boarded    { border-left-color: #67c23a; }
.pax-item.st-k-deboarding { border-left-color: #ff9800; }
.pax-item.st-k-exited     { border-left-color: #67c23a; }
.pax-item.st-k-unknown    { border-left-color: transparent; }
.pax-seq { color: #6a6a8a; font-family: 'Courier New', monospace; min-width: 75px; font-size: 10px; }
.pax-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  white-space: nowrap;
}
.pax-phase { color: #6a6a8a; font-size: 10px; }
.pax-badge.st-not_entered { background: rgba(140,140,170,0.2); color: #a0a0c0; }
.pax-badge.st-boarding    { background: rgba(64,158,255,0.2); color: #409eff; }
.pax-badge.st-deboarding  { background: rgba(255,152,0,0.2);  color: #ff9800; }
.pax-badge.st-boarded     { background: rgba(103,194,58,0.2);  color: #67c23a; }
.pax-badge.st-exited      { background: rgba(103,194,58,0.2);  color: #67c23a; }
.pax-badge.st-unknown     { background: rgba(245,108,108,0.2); color: #f56c6c; }

.result-box {
  border-radius: 5px;
  padding: 8px;
  border: 1px solid #3d3d5c;
  background: #252538;
}
.res-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 6px;
}
.pax-id {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  font-weight: 700;
  color: #ffd54f;
  word-break: break-all;
}
.status-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.status-badge.st-not_entered { background: rgba(140,140,170,0.2); color: #a0a0c0; }
.status-badge.st-boarding   { background: rgba(64,158,255,0.2); color: #409eff; }
.status-badge.st-deboarding{ background: rgba(255,152,0,0.2);  color: #ff9800; }
.status-badge.st-boarded   { background: rgba(103,194,58,0.2);  color: #67c23a; }
.status-badge.st-exited    { background: rgba(103,194,58,0.2);  color: #67c23a; }
.status-badge.st-unknown   { background: rgba(245,108,108,0.2); color: #f56c6c; }

.res-info { display: flex; flex-direction: column; gap: 2px; }
.info-line { color: #a0b0e0; font-size: 11px; }
.info-line.hint { color: #6a6a8a; font-size: 10px; margin-top: 4px; }
</style>
