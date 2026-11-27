<template>
  <div v-title data-title="航班调度分析系统" class="home-page">
    <!-- 左侧：分析历史 -->
    <div class="home-left">
      <div class="history-header">
        <h3>分析历史</h3>
        <el-button type="primary" size="mini" icon="el-icon-document" class="boundary-btn"
                   @click="$router.push('/boundary-docs')">边界说明</el-button>
      </div>
      <div class="history-list" v-if="historyList.length">
        <div
          v-for="item in historyList"
          :key="item.id"
          class="history-item"
          :class="{ active: activeId === item.id, loading: loadingId === item.id }"
          @click="loadingId ? null : goAnalysis(item.id)"
        >
          <i v-if="loadingId === item.id" class="el-icon-loading history-loading"></i>
          <div class="history-date">{{ item.date }}</div>
          <div class="history-file">{{ item.filename }}</div>
          <div class="history-count">{{ item.flightCount }} 条航班</div>
          <i class="el-icon-delete delete-btn" @click.stop="deleteHistory(item.id)" title="删除"></i>
        </div>
      </div>
      <div class="history-empty" v-else>
        <p>暂无分析记录</p>
        <p>上传航班计划开始分析</p>
      </div>
    </div>

    <!-- 右侧：上传区域 -->
    <div class="home-right">
      <div class="welcome-text">
        <h1>Hi {{ username }}，今天你想分析什么航班？</h1>
        <el-button type="text" class="logout-btn" @click="logout">退出登录</el-button>
      </div>
      <div class="upload-area">
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.xls"
          style="display:none"
          @change="handleUpload"
        />
        <div class="upload-box" @click="uploading ? null : $refs.fileInput.click()" :class="{ loading: uploading }">
          <template v-if="!uploading">
            <div class="upload-icon">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#409eff" stroke-width="1.5">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <div class="upload-text">点击上传原始航班计划</div>
            <div class="upload-hint">支持 .xlsx 格式文件</div>
          </template>
          <template v-else>
            <div class="upload-progress-inner">
              <div class="upload-progress-text">{{ uploadProgress }}%</div>
              <el-progress :percentage="uploadProgress" :show-text="false" :stroke-width="8"></el-progress>
              <div class="upload-progress-status">{{ uploadStatus }}</div>
            </div>
          </template>
        </div>
      </div>

      <!-- 新链路入口：客流量 → 航班计划 -->
      <div class="new-feature-section">
        <div class="divider-text"><span>全链路模式（客流量 → 航班 → 调度 → 仿真）</span></div>
        <div class="feature-links">
          <el-button type="primary" plain icon="el-icon-data-analysis" @click="$router.push('/intelligence')">智能实验中心</el-button>
          <el-button type="primary" icon="el-icon-data-line" @click="$router.push('/traffic-input')">
            客流量输入
          </el-button>
          <el-button icon="el-icon-search" @click="$router.push('/passenger-lookup')">
            旅客追溯
          </el-button>
        </div>
      </div>
    </div>

    <!-- 历史加载遮罩 -->
    <div v-if="loadingId" class="history-loading-overlay" @click.stop>
      <div class="history-loading-card">
        <i class="el-icon-loading" style="font-size:36px;color:#409eff"></i>
        <p style="margin:16px 0 6px;font-size:15px;color:#303133">正在加载历史数据</p>
        <p style="margin:0;font-size:12px;color:#909399">请稍候，正在恢复航班分析结果...</p>
      </div>
    </div>
  </div>
</template>

<script>
const HISTORY_KEY = 'flight_analysis_history'

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
  } catch (e) {
    return []
  }
}

function saveHistory(list) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list))
}

function genId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function getUsername() {
  try {
    const u = JSON.parse(localStorage.getItem('current_user') || '{}')
    return u.username || ''
  } catch (e) {
    return ''
  }
}

export default {
  name: 'Home',
  data() {
    return {
      historyList: loadHistory(),
      activeId: null,
      loadingId: null,
      uploading: false,
      uploadProgress: 0,
      uploadStatus: '',
      _pollTimer: null,
    }
  },
  computed: {
    username() {
      return getUsername()
    },
  },
  beforeDestroy() {
    if (this._pollTimer) clearInterval(this._pollTimer)
  },
  created() {
    this._syncFromBackend()
  },
  methods: {
    async _syncFromBackend() {
      try {
        const uname = this.username
        if (!uname) return
        const resp = await fetch('/api/flights/history?username=' + encodeURIComponent(uname))
        const json = await resp.json()
        if (json.code !== 0 || !json.data) return
        const backendList = json.data
        if (!backendList.length) return

        // 以后端为准，合并前端 localStorage 中的记录
        const localMap = {}
        this.historyList.forEach(item => { localMap[item.id] = item })

        const merged = backendList.map(item => ({
          id: item.id,
          date: item.upload_time || '',
          filename: item.filename || '',
          flightCount: item.active_count || item.flight_count || 0,
          timestamp: 0,
        }))
        // 去重：已存在的保留
        this.historyList = merged.filter(m => !localMap[m.id]).concat(this.historyList)
        saveHistory(this.historyList)
      } catch (e) {
        console.warn('[同步历史] 后端不可用，使用本地缓存')
      }
    },
    _startPolling() {
      if (this._pollTimer) return
      const self = this
      console.log('[进度轮询] 开始轮询 /api/flights/progress')
      this._pollTimer = setInterval(async () => {
        try {
          const resp = await fetch('/api/flights/progress')
          const json = await resp.json()
          if (json.code === 0 && json.data) {
            const prev = self.uploadProgress
            self.uploadProgress = json.data.progress
            if (json.data.stage) self.uploadStatus = json.data.stage
            console.log(`[进度轮询] ${prev}% -> ${json.data.progress}% | ${json.data.stage}`)
          }
        } catch (e) {
          console.warn('[进度轮询] 请求失败:', e.message || e)
        }
      }, 200)
    },
    _stopPolling() {
      console.log('[进度轮询] 停止轮询')
      if (this._pollTimer) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
    },
    async handleUpload(e) {
      const file = e.target.files[0]
      if (!file) return
      this.uploading = true
      this.uploadProgress = 0
      this.uploadStatus = '正在准备上传...'
      this._startPolling()

      try {
        // 先生成 history_id
        const id = genId()
        const uname = this.username

        // Step 1: 上传并解析文件（传入 history_id 和 username）
        const formData = new FormData()
        formData.append('file', file)
        formData.append('history_id', id)
        formData.append('username', uname)
        const resp1 = await fetch('/api/flights/upload', { method: 'POST', body: formData })
        const json1 = await resp1.json()
        if (json1.code !== 0) throw new Error(json1.msg)

        // Step 2: 筛选并保存（传入 history_id 和 username）
        const formData2 = new FormData()
        formData2.append('history_id', id)
        formData2.append('username', uname)
        const resp2 = await fetch('/api/flights/apply', { method: 'POST', body: formData2 })
        const json2 = await resp2.json()
        if (json2.code !== 0) throw new Error(json2.msg)

        this._stopPolling()
        this.uploadProgress = 100
        this.uploadStatus = '分析完成，正在跳转...'

        // Step 3: 创建历史记录
        const today = new Date()
        const dateStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')} ${String(today.getHours()).padStart(2,'0')}:${String(today.getMinutes()).padStart(2,'0')}`
        const entry = {
          id,
          date: dateStr,
          filename: file.name,
          flightCount: json2.data.active_flights || 0,
          timestamp: Date.now()
        }
        this.historyList.unshift(entry)
        saveHistory(this.historyList)

        // Step 4: 跳转
        this.uploading = false
        this.$refs.fileInput.value = ''
        this.$nextTick(() => {
          this.$router.push({ name: 'AnalysisApp', params: { id } })
        })

      } catch (err) {
        this._stopPolling()
        this.uploadProgress = 0
        this.uploadStatus = ''
        this.$refs.fileInput.value = ''
        this.$message.error('分析失败: ' + err.message)
        this.uploading = false
      }
    },
    async goAnalysis(id) {
      this.activeId = id
      this.loadingId = id
      const uname = this.username
      try {
        // 先触发加载，再跳转；添加超时保护（30s）
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 30000)
        const resp = await fetch('/api/flights/history/' + id + '?username=' + encodeURIComponent(uname), {
          method: 'POST',
          signal: controller.signal,
        })
        clearTimeout(timeoutId)
        const json = await resp.json()
        if (json.code !== 0) throw new Error(json.msg || '加载失败')
        console.log('[Home] 历史加载完成:', json.msg)
        this.loadingId = null
        this.$router.push({ name: 'AnalysisApp', params: { id } })
      } catch (e) {
        this.loadingId = null
        this.activeId = null
        if (e.name === 'AbortError') {
          this.$message.error('加载超时，请检查后端服务是否正常')
        } else {
          this.$message.error('加载历史记录失败: ' + (e.message || '未知错误'))
        }
        console.error('[Home] 历史加载失败:', e)
      }
    },
    async deleteHistory(id) {
      try {
        await this.$confirm('确认删除该条分析记录吗？', '提示', {
          confirmButtonText: '确认删除',
          cancelButtonText: '取消',
          type: 'warning',
        })
        // 删除后端文件
        fetch('/api/flights/history/' + id + '?username=' + encodeURIComponent(this.username), { method: 'DELETE' }).catch(() => {})
        // 从列表移除
        this.historyList = this.historyList.filter(item => item.id !== id)
        saveHistory(this.historyList)
        this.$message.success('已删除')
      } catch (e) {
        // 用户取消
      }
    },
    logout() {
      localStorage.removeItem('current_user')
      this.$router.push({ name: 'Login' })
    },
  },
}
</script>

<style scoped>
.home-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  background: #f5f6f8;
  color: #333;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* === 左侧历史面板 === */
.home-left {
  width: 300px;
  min-width: 300px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}
.history-header {
  padding: 20px 16px 12px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
}
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.history-item {
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: all 0.15s;
  border: 1px solid transparent;
  position: relative;
}
.history-item:hover {
  background: #f0f5ff;
}
.history-item .delete-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #c0c4cc;
  font-size: 14px;
  display: none;
  cursor: pointer;
  padding: 4px;
}
.history-item:hover .delete-btn {
  display: block;
}
.history-item .delete-btn:hover {
  color: #f56c6c;
}
.history-item.active {
  background: #e6f0ff;
  border-color: #409eff;
}
.history-item.loading {
  opacity: 0.6;
  pointer-events: none;
}
.history-loading {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: #409eff;
  font-size: 16px;
}
.history-date {
  font-size: 13px;
  color: #666;
  margin-bottom: 4px;
}
.history-file {
  font-size: 14px;
  font-weight: 500;
  color: #1a1a1a;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-count {
  font-size: 12px;
  color: #999;
}
.history-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 14px;
}
.history-empty p {
  margin: 4px 0;
}

/* === 右侧上传区域 === */
.home-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.welcome-text h1 {
  font-size: 28px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 40px;
  text-align: center;
}
.welcome-text {
  position: relative;
}
.logout-btn {
  position: absolute;
  right: -120px;
  top: 0;
  color: #999;
  font-size: 13px;
}
.logout-btn:hover {
  color: #f56c6c;
}
.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.upload-box {
  width: 260px;
  height: 260px;
  border: 2px dashed #d9d9d9;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.25s;
  background: #fff;
}
.upload-box:hover {
  border-color: #409eff;
  background: #f0f5ff;
  box-shadow: 0 4px 16px rgba(64,158,255,0.12);
}
.upload-box.loading {
  cursor: default;
  border-color: #409eff;
  background: #f0f5ff;
}
.upload-icon {
  margin-bottom: 16px;
}
.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}
.upload-hint {
  font-size: 13px;
  color: #999;
}

/* 方形组件内的进度条 */
.upload-progress-inner {
  width: 100%;
  padding: 0 24px;
  text-align: center;
}
.upload-progress-text {
  font-size: 36px;
  font-weight: 700;
  color: #409eff;
  margin-bottom: 12px;
}
.upload-progress-status {
  margin-top: 12px;
  font-size: 14px;
  color: #666;
}

/* === 历史加载遮罩 === */
.history-loading-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.35);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}
.history-loading-card {
  background: #fff;
  border-radius: 12px;
  padding: 36px 48px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}

/* 新链路入口 */
.new-feature-section {
  margin-top: 32px;
  text-align: center;
}
.divider-text {
  color: #999;
  font-size: 13px;
  margin-bottom: 16px;
  position: relative;
}
.divider-text span {
  background: #f5f6f8;
  padding: 0 12px;
  position: relative;
  z-index: 1;
}
.divider-text::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: #e0e0e0;
}
.feature-links {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
