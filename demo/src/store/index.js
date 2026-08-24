import Vue from 'vue'
import Vuex from 'vuex'
import api from '@/api'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    // 异常调度
    activeAnomalies: [],       // 当前活跃的异常事件
    selectedAnomaly: null,     // 当前选中的异常事件
    impactReport: null,        // 当前影响报告
    recoveryPlan: null,        // 当前恢复方案
    templates: [],             // 场景模板列表
    backupResources: null,     // 备份资源池
    overlays: null,            // 模块覆盖标记数据
    auditLogs: [],             // 审计日志
    loading: false,            // 加载状态

    // 全局告警
    globalAlert: {
      show: false,
      message: '',
      type: 'warning',
    },
  },

  mutations: {
    SET_ACTIVE_ANOMALIES(state, list) {
      state.activeAnomalies = list
    },
    SET_SELECTED_ANOMALY(state, event) {
      state.selectedAnomaly = event
    },
    SET_IMPACT_REPORT(state, report) {
      state.impactReport = report
    },
    SET_RECOVERY_PLAN(state, plan) {
      state.recoveryPlan = plan
    },
    SET_TEMPLATES(state, templates) {
      state.templates = templates
    },
    SET_BACKUP_RESOURCES(state, resources) {
      state.backupResources = resources
    },
    SET_OVERLAYS(state, overlays) {
      state.overlays = overlays
    },
    SET_AUDIT_LOGS(state, logs) {
      state.auditLogs = logs
    },
    SET_LOADING(state, val) {
      state.loading = val
    },
    SET_GLOBAL_ALERT(state, alert) {
      state.globalAlert = { ...state.globalAlert, ...alert }
    },
    CLEAR_GLOBAL_ALERT(state) {
      state.globalAlert.show = false
    },
    CLEAR_ALL(state) {
      state.activeAnomalies = []
      state.selectedAnomaly = null
      state.impactReport = null
      state.recoveryPlan = null
      state.overlays = null
      state.auditLogs = []
    },
  },

  actions: {
    // ===== 异常事件 =====
    async fetchAnomalyEvents({ commit }, status) {
      commit('SET_LOADING', true)
      try {
        const data = await api.getAnomalyEvents(status)
        commit('SET_ACTIVE_ANOMALIES', data.events || [])
        return data.events
      } finally {
        commit('SET_LOADING', false)
      }
    },

    async fetchAnomalyEvent({ commit }, eventId) {
      const event = await api.getAnomalyEvent(eventId)
      commit('SET_SELECTED_ANOMALY', event)
      return event
    },

    async createAnomalyEvent({ commit, dispatch }, data) {
      const event = await api.createAnomalyEvent(data)
      await dispatch('fetchAnomalyEvents')
      return event
    },

    async updateAnomalyEvent({ commit, dispatch }, { eventId, data }) {
      const event = await api.updateAnomalyEvent(eventId, data)
      await dispatch('fetchAnomalyEvents')
      return event
    },

    async deleteAnomalyEvent({ commit, dispatch }, eventId) {
      await api.deleteAnomalyEvent(eventId)
      commit('SET_SELECTED_ANOMALY', null)
      commit('SET_IMPACT_REPORT', null)
      commit('SET_RECOVERY_PLAN', null)
      await dispatch('fetchAnomalyEvents')
    },

    // ===== 影响分析 & 恢复 =====
    async analyzeEvent({ commit }, eventId) {
      const result = await api.analyzeAnomalyEvent(eventId)
      commit('SET_IMPACT_REPORT', result.impact_report)
      if (result.recovery_plan) {
        commit('SET_RECOVERY_PLAN', result.recovery_plan)
      }
      return result
    },

    async confirmPlan({ commit, dispatch }, planId) {
      const result = await api.confirmPlan(planId)
      // 更新 recoveryPlan 状态为 confirmed，让"执行"按钮可见
      if (result && result.plan) {
        commit('SET_RECOVERY_PLAN', result.plan)
      }
      commit('SET_GLOBAL_ALERT', {
        show: true,
        message: '恢复方案已确认，可点击"执行"开始执行',
        type: 'success',
      })
      await dispatch('fetchAnomalyEvents')
      return result
    },

    async executePlan({ commit, dispatch }, planId) {
      const result = await api.executePlan(planId)
      const summary = result.summary || {}
      commit('SET_GLOBAL_ALERT', {
        show: true,
        message: `恢复方案已执行：${summary.total_flights || '?'} 个航班，` +
          `延迟 ${summary.delayed || 0} 班，取消 ${summary.canceled || 0} 班`,
        type: 'success',
      })
      await dispatch('fetchAnomalyEvents')
      await dispatch('fetchAuditLog')
      return result
    },

    async rollbackPlan({ commit, dispatch }, planId) {
      const result = await api.rollbackPlan(planId)
      commit('SET_GLOBAL_ALERT', {
        show: true,
        message: '恢复方案已回滚',
        type: 'info',
      })
      await dispatch('fetchAnomalyEvents')
      await dispatch('fetchAuditLog')
      return result
    },

    async adjustPlan({ commit, dispatch }, { planId, adjustments }) {
      const result = await api.adjustPlan(planId, adjustments)
      commit('SET_RECOVERY_PLAN', result.plan)
      return result
    },

    // ===== 资源 & 覆盖数据 =====
    async fetchTemplates({ commit }, category) {
      const data = await api.getAnomalyTemplates(category)
      commit('SET_TEMPLATES', data.templates || [])
      return data.templates
    },

    async fetchBackupResources({ commit }) {
      const data = await api.getBackupResources()
      commit('SET_BACKUP_RESOURCES', data)
      return data
    },

    async generateBackupResources({ commit, dispatch }) {
      const data = await api.generateBackupResources()
      commit('SET_BACKUP_RESOURCES', data.resources)
      return data
    },

    async fetchOverlays({ commit }, status) {
      const data = await api.getAnomalyOverlays(status)
      commit('SET_OVERLAYS', data)
      return data
    },

    async fetchAuditLog({ commit }, params = {}) {
      const data = await api.getAuditLog(
        params.action, params.targetType, params.limit, params.offset
      )
      commit('SET_AUDIT_LOGS', data.logs || [])
      return data.logs
    },
  },

  modules: {},
})

