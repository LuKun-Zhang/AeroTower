<template>
  <div class="recovery-view">
    <!-- 全局告警条 -->
    <div v-if="globalAlert.show" class="global-alert" :class="'alert-' + globalAlert.type">
      <i class="el-icon-warning"></i>
      <span>{{ globalAlert.message }}</span>
      <i class="el-icon-close" style="cursor:pointer;margin-left:auto" @click="dismissAlert"></i>
    </div>

    <!-- 三栏布局 -->
    <div class="recovery-layout">
      <!-- 左侧：异常事件面板 -->
      <div class="left-panel">
        <AnomalyPanel @select="onSelectEvent" />
      </div>

      <!-- 中间：影响分析 + 备份资源 -->
      <div class="center-panel">
        <!-- 事件详情 -->
        <div class="detail-card" v-if="selectedEvent">
          <div class="card-header">
            <h4>{{ selectedEvent.title }}</h4>
            <el-tag :type="getPriorityType(selectedEvent.priority)" size="small">{{ selectedEvent.priority }}</el-tag>
          </div>
          <div class="card-body">
            <div class="detail-row" v-if="selectedEvent.description">
              <span class="detail-label">描述:</span> {{ selectedEvent.description }}
            </div>
            <div class="detail-row">
              <span class="detail-label">类型:</span> {{ getAnomalyLabel(selectedEvent.event_type) }}
            </div>
            <div class="detail-row" v-if="selectedEvent.start_time">
              <span class="detail-label">时间:</span> {{ selectedEvent.start_time }} ~ {{ selectedEvent.end_time }}
            </div>
            <div class="detail-row" v-if="selectedEvent.affected_airports.length">
              <span class="detail-label">{{ isWeatherEvent ? '受影响省份:' : '受影响机场:' }}</span>
              <el-tag v-for="ap in selectedEvent.affected_airports" :key="ap" size="mini" type="warning" style="margin:2px">{{ ap }}</el-tag>
            </div>
            <div class="detail-row" v-if="selectedEvent.affected_aircraft.length">
              <span class="detail-label">受影响飞机:</span>
              <el-tag v-for="ac in selectedEvent.affected_aircraft" :key="ac" size="mini" type="danger" style="margin:2px">{{ ac }}</el-tag>
            </div>
          </div>
          <div class="card-actions">
            <el-button type="primary" size="small" icon="el-icon-search" @click="analyzeEvent" :loading="analyzing">影响分析</el-button>
            <el-button size="small" icon="el-icon-setting" @click="showBackupDialog = true">备份资源</el-button>
            <el-button type="danger" size="small" icon="el-icon-delete" plain @click="deleteEvent">删除</el-button>
          </div>
        </div>

        <div v-else class="empty-hint">
          <i class="el-icon-info"></i>
          <p>请从左侧选择一个异常事件</p>
        </div>

        <!-- 影响树 -->
        <ImpactTree :impact="impactReport" :eventTitle="selectedEvent ? selectedEvent.title : ''" />
      </div>

      <!-- 恢复方案 + 审计日志 -->
      <div class="right-panel">
        <!-- 调试：测试进度遮罩 -->
        <el-button size="mini" type="info" @click="executing = true; execStage = '测试中...'; execProgress = 50; execStatus = 'running'">[测试进度窗口]</el-button>
        <RecoveryTimeline
          :plan="recoveryPlan"
          @confirm="confirmPlan"
          @reject="rejectPlan"
          @execute="executePlan"
          @rollback="rollbackPlan"
        />

        <!-- 审计日志 -->
        <div class="audit-log" style="margin-top:16px">
          <div class="section-title">
            <i class="el-icon-document-copy"></i> 调度日志
          </div>
          <div class="log-list" v-if="auditLogs.length">
            <div v-for="log in auditLogs.slice(0, 15)" :key="log.log_id" class="log-item">
              <el-tag size="mini" :type="actionType(log.action)">{{ log.action }}</el-tag>
              <span class="log-detail">{{ log.detail }}</span>
              <span class="log-time">{{ log.timestamp }}</span>
            </div>
          </div>
          <div v-else class="empty-hint" style="padding:15px 0;font-size:12px;">暂无调度日志</div>
        </div>
      </div>
    </div>

    <!-- 备份资源管理对话框 -->
    <el-dialog title="备份资源管理" :visible.sync="showBackupDialog" width="700px">
      <el-button size="small" type="primary" icon="el-icon-magic-stick" @click="generateBackup">自动生成备份资源</el-button>
      <el-table :data="backupResourceTable" border size="small" style="margin-top:12px">
        <el-table-column prop="tail_no" label="备份飞机" />
        <el-table-column prop="crew_id" label="备份机组" />
        <el-table-column prop="gate_id" label="备份登机口" />
        <el-table-column prop="runway_id" label="备份跑道" />
      </el-table>
      <div slot="footer">
        <el-button @click="showBackupDialog = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- 分析中遮罩 -->
    <div v-if="analyzing" class="analyzing-overlay" @click.stop>
      <div class="analyzing-box">
        <i class="el-icon-loading analyzing-spin"></i>
        <p class="analyzing-title">正在分析影响范围...</p>
        <p class="analyzing-sub">约需数秒，请稍候</p>
      </div>
    </div>

    <!-- 执行进度遮罩 -->
    <div v-if="executing" class="analyzing-overlay" @click.stop>
      <div class="analyzing-box" style="width: 380px">
        <p class="analyzing-title" style="margin-bottom: 16px">正在执行恢复方案</p>
        <el-progress
          :percentage="execProgress"
          :status="execStatus === 'error' ? 'exception' : undefined"
          :stroke-width="16"
          :text-inside="true"
        ></el-progress>
        <p class="analyzing-sub" style="margin-top: 12px">{{ execStage }}</p>
        <div v-if="execStatus === 'done' || execStatus === 'error' || execStatus === 'partial'" style="margin-top: 18px">
          <el-button type="primary" size="small" @click="onExecComplete">确定</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import { ANOMALY_TYPE_LABELS, PRIORITY_CONFIG, STATUS_CONFIG } from '@/utils/anomaly-helper'
import AnomalyPanel from '@/components/AnomalyPanel'
import ImpactTree from '@/components/ImpactTree'
import RecoveryTimeline from '@/components/RecoveryTimeline'

export default {
  name: 'RecoveryView',
  components: { AnomalyPanel, ImpactTree, RecoveryTimeline },
  data() {
    return {
      analyzing: false,
      showBackupDialog: false,
      executing: false,
      execProgress: 0,
      execStage: '',
      execStatus: 'idle',    // idle | running | done | error | partial
      _pollTimer: null,
    }
  },
  computed: {
    ...mapState({
      selectedEvent: state => state.selectedAnomaly,
      impactReport: state => state.impactReport,
      recoveryPlan: state => state.recoveryPlan,
      auditLogs: state => state.auditLogs,
      backupResources: state => state.backupResources,
      globalAlert: state => state.globalAlert,
    }),
    backupResourceTable() {
      if (!this.backupResources) return []
      const ac = (this.backupResources.backup_aircraft || []).slice(0, 10)
      const cr = (this.backupResources.backup_crew || []).slice(0, 10)
      const gt = (this.backupResources.backup_gates || []).slice(0, 10)
      const rw = (this.backupResources.backup_runways || []).slice(0, 10)
      const maxLen = Math.max(ac.length, cr.length, gt.length, rw.length, 1)
      const rows = []
      for (let i = 0; i < maxLen; i++) {
        rows.push({
          tail_no: ac[i] ? ac[i].tail_no : '',
          crew_id: cr[i] ? cr[i].crew_id : '',
          gate_id: gt[i] ? gt[i].gate_id : '',
          runway_id: rw[i] ? rw[i].runway_id : '',
        })
      }
      return rows
    },
    isWeatherEvent() {
      const t = (this.selectedEvent || {}).event_type || ''
      // 仅省份级天气异常显示"受影响省份"
      return ['weather_storm', 'weather_rain', 'weather_snow', 'weather_fog', 'weather_typhoon'].includes(t)
    },
  },
  methods: {
    ...mapActions([
      'fetchAnomalyEvents', 'fetchAnomalyEvent', 'deleteAnomalyEvent',
      'analyzeEvent',
      'adjustPlan', 'fetchBackupResources', 'generateBackupResources',
      'fetchAuditLog', 'fetchOverlays',
    ]),
    getAnomalyLabel(type) { return ANOMALY_TYPE_LABELS[type] || type },
    getPriorityType(p) { return (PRIORITY_CONFIG[p] || {}).type || 'info' },
    actionType(a) {
      const m = { execute: 'success', rollback: 'warning', adjust: 'info', confirm: 'primary' }
      return m[a] || 'info'
    },
    async onSelectEvent(event) {
      await this.fetchAnomalyEvent(event.event_id)
      this.fetchOverlays()
      this.fetchAuditLog()
    },
    async handleAnalyze() {
      if (!this.selectedEvent) return
      this.analyzing = true
      try {
        await this.$store.dispatch('analyzeEvent', this.selectedEvent.event_id)
        this.fetchOverlays()
        this.$message.success('影响分析完成，方案已生成')
      } catch (e) {
        this.$message.error('分析失败: ' + (e.message || '未知错误'))
      } finally {
        this.analyzing = false
      }
    },
    async analyzeEvent() { return this.handleAnalyze() },
    deleteEvent() {
      if (!this.selectedEvent) return
      this.$confirm('确定删除该异常事件吗？', '确认', { type: 'warning' }).then(async () => {
        await this.deleteAnomalyEvent(this.selectedEvent.event_id)
        this.$message.success('已删除')
      }).catch(() => {})
    },
    async confirmPlan() {
      if (!this.recoveryPlan) return
      try {
        await this.$store.dispatch('confirmPlan', this.recoveryPlan.plan_id)
        this.$message.success('方案已确认')
      } catch (e) {
        this.$message.error('确认失败: ' + (e.message || '未知错误'))
      }
    },
    rejectPlan() {
      if (!this.recoveryPlan) return
      this.$store.commit('SET_RECOVERY_PLAN', { ...this.recoveryPlan, status: 'rejected' })
      this.$message.info('方案已拒绝')
    },
    async executePlan() {
      console.log('[RecoveryView] executePlan 调用, plan:', this.recoveryPlan)
      if (!this.recoveryPlan) {
        console.log('[RecoveryView] 无 plan，退出')
        return
      }
      console.log('[RecoveryView] 弹出确认框...')
      try {
        await this.$confirm('确定执行该恢复方案吗？', '确认执行', { type: 'warning' })
      } catch (e) {
        console.log('[RecoveryView] 用户取消确认:', e)
        return
      }
      console.log('[RecoveryView] 用户确认，开始执行...')

      // 先打开进度弹窗
      this.executing = true
      this.execProgress = 0
      this.execStage = '正在启动...'
      this.execStatus = 'running'
      console.log('[RecoveryView] 进度弹窗已打开:', this.executing)

      this._startPolling()
      console.log('[RecoveryView] 轮询已启动')

      // 后台发起执行
      try {
        const resp = await fetch('/api/anomaly/plans/' + this.recoveryPlan.plan_id + '/execute', { method: 'POST' })
        const json = await resp.json()
        console.log('[RecoveryView] 执行 API 返回:', json)
        if (json.code !== 0) throw new Error(json.msg || '启动失败')
      } catch (e) {
        console.error('[RecoveryView] 执行 API 失败:', e)
        this._stopPolling()
        this.executing = false
        this.$message.error('启动执行失败: ' + (e.message || '未知错误'))
      }
    },
    _startPolling() {
      if (this._pollTimer) clearInterval(this._pollTimer)
      this._pollTimer = setInterval(async () => {
        try {
          const resp = await fetch('/api/anomaly/execute-progress')
          const json = await resp.json()
          if (json.code === 0 && json.data) {
            this.execProgress = json.data.progress || 0
            this.execStage = json.data.stage || ''
            this.execStatus = json.data.status || 'running'

            if (this.execStatus === 'done') {
              this._stopPolling()
              const summary = json.data.result ? json.data.result.summary : null
              let alertMsg = '恢复方案已执行'
              let notifyMsg = '恢复方案已应用到排班数据。'
              if (summary) {
                if (summary.is_aircraft_recovery) {
                  const excluded = (summary.excluded_aircraft || []).join(', ')
                  alertMsg = `飞机异常恢复完成：排除 ${excluded}，共重新分配 ${summary.reassigned || 0} 个航班`
                  notifyMsg = `已排除飞机 ${excluded}，${summary.reassigned || 0} 个航班已重新分配到其他可用飞机。请切换到「飞机排班」查看新的分配结果。`
                } else {
                  alertMsg = `恢复方案已执行：${summary.total_flights} 个航班，延迟 ${summary.delayed} 班，取消 ${summary.canceled} 班`
                  notifyMsg = `恢复方案已应用到排班数据。已取消 ${summary.canceled || 0} 班，延迟 ${summary.delayed || 0} 班。请切换到「航班筛选」标签查看更新后的航班集合，以及「飞机排班」「机组排班」「登机口分配」「跑道调度」查看调度结果。`
                }
              }
              this.$store.commit('SET_GLOBAL_ALERT', {
                show: true,
                message: alertMsg,
                type: 'success',
              })
              this.$store.dispatch('fetchAnomalyEvents')
              this.fetchAuditLog()
              this.$notify({
                title: '执行完成',
                message: notifyMsg,
                type: 'success',
                duration: 8000,
              })
              if (summary && summary.is_aircraft_recovery) {
                this.$message.success(alertMsg)
              } else {
                this.$message.success(`恢复方案执行完成：取消 ${summary ? summary.canceled || 0 : 0} 班，延迟 ${summary ? summary.delayed || 0 : 0} 班`)
              }
              this.$root.$emit('filter-needs-refresh')
            } else if (this.execStatus === 'error') {
              this._stopPolling()
              const msg = (json.data.result && json.data.result.msg) || '执行失败'
              this.$message.error(msg)
            } else if (this.execStatus === 'partial') {
              this._stopPolling()
              this.$message.warning('方案部分完成，部分排班算法可能出错')
            }
          }
        } catch (e) {
          // 网络错误，继续轮询
        }
      }, 600)
    },
    _stopPolling() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
    },
    onExecComplete() {
      this._stopPolling()
      this.executing = false
      this.execStatus = 'idle'
    },
    rollbackPlan() {
      if (!this.recoveryPlan) return
      this.$confirm('确定回滚该恢复方案吗？', '确认回滚', { type: 'warning' }).then(async () => {
        try {
          await this.$store.dispatch('rollbackPlan', this.recoveryPlan.plan_id)
          this.$message.success('方案已回滚')
        } catch (e) {
          this.$message.error('回滚失败: ' + (e.message || '未知错误'))
        }
      }).catch(() => {})
    },
    generateBackup() {
      this.generateBackupResources()
      this.$message.success('备份资源已生成')
    },
    dismissAlert() {
      this.$store.commit('CLEAR_GLOBAL_ALERT')
    },
  },
  mounted() {
    this.fetchBackupResources()
    this.fetchOverlays()
    this.fetchAuditLog()
  },
  beforeDestroy() {
    this._stopPolling()
  },
}
</script>

<style scoped>
.recovery-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  padding: 8px;
  gap: 8px;
}
.global-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 4px;
  font-size: 13px;
  color: #fff;
}
.alert-success { background: #67C23A; }
.alert-warning { background: #E6A23C; }
.alert-info { background: #409EFF; }
.alert-error { background: #F56C6C; }
.recovery-layout {
  flex: 1;
  display: flex;
  gap: 8px;
  overflow: hidden;
}
.left-panel {
  width: 280px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
}
.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.right-panel {
  width: 340px;
  min-width: 340px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.detail-card {
  background: #fff;
  border-radius: 4px;
  padding: 14px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.card-header h4 {
  margin: 0;
  font-size: 14px;
  color: #303133;
}
.card-body { margin-bottom: 10px; }
.detail-row {
  font-size: 12px;
  color: #606266;
  padding: 3px 0;
}
.detail-label { color: #909399; margin-right: 6px; }
.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
}
.empty-hint {
  text-align: center;
  color: #c0c4cc;
  padding: 30px 0;
}
.empty-hint i { font-size: 28px; display: block; margin-bottom: 8px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.log-list {
  background: #fff;
  border-radius: 4px;
  padding: 8px;
  max-height: 300px;
  overflow-y: auto;
}
.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px solid #f5f7fa;
}
.log-detail {
  flex: 1;
  color: #606266;
}
.log-time {
  color: #c0c4cc;
  font-size: 10px;
  white-space: nowrap;
}

/* 分析中遮罩 */
.analyzing-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 3000;
}
.analyzing-box {
  background: #fff;
  border-radius: 8px;
  padding: 32px 40px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}
.analyzing-spin {
  font-size: 36px;
  color: #409EFF;
  animation: analyzing-rotate 1s linear infinite;
}
.analyzing-title {
  margin: 16px 0 4px;
  font-size: 15px;
  color: #303133;
  font-weight: 500;
}
.analyzing-sub {
  margin: 0;
  font-size: 12px;
  color: #909399;
}
@keyframes analyzing-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
