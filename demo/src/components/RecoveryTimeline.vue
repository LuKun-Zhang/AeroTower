<template>
  <div class="recovery-timeline">
    <div class="section-title">
      <i class="el-icon-s-operation"></i> 恢复方案
      <el-tag v-if="plan" :type="planStatusType" size="mini">{{ planStatusLabel }}</el-tag>
    </div>

    <div v-if="!plan" class="empty-state">
      <i class="el-icon-document"></i>
      <p>暂无恢复方案</p>
    </div>

    <div v-else class="plan-container">
      <!-- 方案概览 -->
      <div class="plan-summary">
        <div class="summary-row">
          <span class="summary-label">策略:</span>
          <span class="summary-val">{{ strategyLabels.join(' → ') }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">覆盖率:</span>
          <span class="summary-val">{{ (plan.coverage_rate * 100).toFixed(0) }}%</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">总变更:</span>
          <span class="summary-val">{{ plan.flight_changes.length }} 项</span>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="plan-actions" v-if="plan.status === 'draft'">
        <el-button size="small" type="success" icon="el-icon-check" @click="$emit('confirm')">确认方案</el-button>
        <el-button size="small" type="danger" icon="el-icon-close" @click="$emit('reject')">拒绝</el-button>
      </div>
      <div class="plan-actions" v-if="plan.status === 'confirmed'">
        <el-button size="small" type="primary" icon="el-icon-video-play" @click="onExecClick">执行</el-button>
        <el-button size="small" type="warning" icon="el-icon-refresh-left" @click="$emit('rollback')">回滚</el-button>
      </div>

      <!-- 变更列表（按类型分组） -->
      <div class="change-groups" v-if="groupedChanges.length">
        <div v-for="(group, idx) in groupedChanges" :key="idx" class="change-group">
          <div class="group-header">
            <el-tag size="mini" :type="group.tagType">{{ group.label }}</el-tag>
            <span class="group-count">{{ group.changes.length }} 项</span>
          </div>
          <div class="change-list">
            <div v-for="(change, ci) in group.changes.slice(0, 8)" :key="ci" class="change-item">
              <span class="change-fid" :title="change.flight_id">
                {{ change.flight_no || change.flight_id }}
              </span>
              <span class="change-route" v-if="change.departure_airport && change.arrival_airport">
                {{ change.departure_airport }} → {{ change.arrival_airport }}
              </span>
              <span class="change-times" v-if="change.change_type === 'DELAY'">
                <span class="time-old">{{ change.origin_dep }}</span>
                <span class="time-arrow">&rarr;</span>
                <span class="time-new">{{ change.new_dep }}</span>
                <span class="delay-badge">+{{ change.delay_minutes }}min</span>
              </span>
              <span class="change-times" v-else-if="change.change_type === 'CANCEL'">
                <span class="time-old">{{ change.origin_dep }}</span>
                <span class="time-arrow">&rarr;</span>
                <span class="time-canceled">取消</span>
                <span class="delay-badge danger">+{{ change.delay_minutes }}min</span>
              </span>
              <span class="change-times" v-else-if="change.change_type === 'REASSIGN_AIRCRAFT'">
                <span class="time-old">{{ change.origin_dep }}</span>
                <span class="time-new" style="text-decoration:none;color:#409EFF;font-weight:600">重新分配</span>
              </span>
              <span class="change-other" v-else>
                <span class="time-old">{{ change.old_value }}</span>
                <span v-if="change.new_value">&rarr;</span>
                <span class="time-new">{{ change.new_value }}</span>
              </span>
              <el-tooltip v-if="change.reason" :content="change.reason" placement="top">
                <i class="el-icon-question reason-icon"></i>
              </el-tooltip>
            </div>
            <div v-if="group.changes.length > 8" class="change-more">
              ...还有 {{ group.changes.length - 8 }} 项
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { STRATEGY_LABELS, CHANGE_TYPE_LABELS } from '@/utils/anomaly-helper'

export default {
  name: 'RecoveryTimeline',
  props: {
    plan: { type: Object, default: null },
  },
  computed: {
    planStatusType() {
      const map = { draft: 'warning', confirmed: 'primary', executed: 'success', rolled_back: 'info' }
      return map[this.plan ? this.plan.status : ''] || 'info'
    },
    planStatusLabel() {
      const map = { draft: '草稿', confirmed: '已确认', executed: '已执行', rolled_back: '已回滚' }
      return map[this.plan ? this.plan.status : ''] || (this.plan ? this.plan.status : '')
    },
    strategyLabels() {
      if (!this.plan) return []
      const names = (this.plan.strategy || '').split('+')
      return names.map(n => STRATEGY_LABELS[n.trim()] || n.trim())
    },
    groupedChanges() {
      if (!this.plan) return []
      const groups = {
        aircraft: { label: '更换飞机', changes: [], tagType: 'primary' },
        time: { label: '延迟', changes: [], tagType: 'warning' },
        crew: { label: '更换机组', changes: [], tagType: 'success' },
        gate: { label: '更换登机口', changes: [], tagType: 'info' },
        runway: { label: '更换跑道', changes: [], tagType: '' },
        cancel: { label: '取消航班', changes: [], tagType: 'danger' },
        merge: { label: '合并航班', changes: [], tagType: '' },
      }
      const all = [
        ...(this.plan.aircraft_changes || []),
        ...(this.plan.crew_changes || []),
        ...(this.plan.gate_changes || []),
        ...(this.plan.runway_changes || []),
        ...(this.plan.flight_changes || []),
      ]
      for (const c of all) {
        const type = (c.change_type || '').toUpperCase()
        if (type.includes('AIRCRAFT')) groups.aircraft.changes.push(c)
        else if (type === 'DELAY') groups.time.changes.push(c)
        else if (type.includes('CREW')) groups.crew.changes.push(c)
        else if (type.includes('GATE')) groups.gate.changes.push(c)
        else if (type.includes('RUNWAY')) groups.runway.changes.push(c)
        else if (type === 'CANCEL') groups.cancel.changes.push(c)
        else if (type === 'MERGE') groups.merge.changes.push(c)
        else groups.aircraft.changes.push(c)
      }
      return Object.values(groups).filter(g => g.changes.length > 0)
    },
  },
  methods: {
    onExecClick() {
      console.log('[RecoveryTimeline] 点击执行按钮, plan:', this.plan)
      this.$emit('execute')
    },
  },
}
</script>

<style scoped>
.recovery-timeline {
  background: #fff;
  border-radius: 4px;
  padding: 16px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-title i { color: #67C23A; }
.empty-state {
  text-align: center;
  padding: 30px 0;
  color: #c0c4cc;
}
.empty-state i { font-size: 28px; display: block; margin-bottom: 8px; }
.plan-summary {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 10px 14px;
  margin-bottom: 10px;
}
.summary-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 2px 0;
}
.summary-label { color: #909399; }
.summary-val { font-weight: 600; color: #303133; }
.plan-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.change-group {
  margin-bottom: 10px;
}
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.group-count { font-size: 11px; color: #909399; }
.change-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  font-size: 11px;
  border-bottom: 1px solid #f5f7fa;
  flex-wrap: wrap;
}
.change-fid { font-weight: 600; color: #303133; min-width: 60px; font-size: 11px; }
.change-route {
  color: #909399;
  font-size: 10px;
  background: #f5f7fa;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}
.change-times {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex: 1;
  min-width: 0;
}
.change-other { display: inline-flex; align-items: center; gap: 3px; }
.time-old { text-decoration: line-through; color: #F56C6C; font-size: 10px; white-space: nowrap; }
.time-arrow { color: #c0c4cc; font-size: 10px; }
.time-new { color: #67C23A; font-weight: 600; font-size: 10px; white-space: nowrap; }
.time-canceled { color: #F56C6C; font-weight: 700; font-size: 10px; white-space: nowrap; }
.delay-badge {
  color: #E6A23C;
  background: #fdf6ec;
  padding: 0 4px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}
.delay-badge.danger { color: #F56C6C; background: #fef0f0; }
.reason-icon {
  color: #909399;
  font-size: 12px;
  cursor: help;
  margin-left: auto;
  flex-shrink: 0;
}
.change-more {
  font-size: 11px;
  color: #909399;
  padding: 4px 8px;
}
</style>
