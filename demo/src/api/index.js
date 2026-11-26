/** API 请求封装 */
import { scoped, currentScope } from './scope'

const BASE_URL = '/api'

async function request(url, options = {}) {
  let username = ''
  try {
    username = JSON.parse(localStorage.getItem('current_user') || '{}').username || ''
  } catch (e) {}
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...(username ? { 'X-Username': username } : {}),
    },
    ...options,
  }

  try {
    const response = await fetch(`${BASE_URL}${url}`, config)
    const data = await response.json()
    if (data.code !== 0) {
      console.error(`[API] ${url} 返回错误:`, data.msg)
      throw new Error(data.msg || '请求失败')
    }
    return data.data
  } catch (err) {
    console.error(`[API] ${url} 请求失败:`, err.message)
    throw err
  }
}

export default {
  /** 获取所有航班 */
  getFlights() {
    return request('/flights')
  },

  /** 获取单个航班 */
  getFlight(id) {
    return request(`/flights/${id}`)
  },

  /** 获取所有飞机 */
  getAircrafts() {
    return request('/aircrafts')
  },

  /** 搜索飞机 */
  searchAircrafts(kw, minIdx, maxIdx, acType) {
    const params = new URLSearchParams()
    if (kw) params.set('kw', kw)
    if (minIdx !== undefined && minIdx !== null) params.set('min_idx', minIdx)
    if (maxIdx !== undefined && maxIdx !== null) params.set('max_idx', maxIdx)
    if (acType) params.set('ac_type', acType)
    return request(`/aircrafts/search?${params.toString()}`)
  },

  /** 更新单架飞机指标并重算指数（返回新 quality_index） */
  updateAircraft(payload) {
    return request('/aircraft/update', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /** 获取所有机场 */
  getAirports() {
    return request('/airports')
  },

  /** 获取机场名称列表 */
  getAirportNames() {
    return request('/airports/names')
  },

  /** 获取当前排班概览 */
  getCurrentSchedule() {
    return request('/schedule/current')
  },

  /** 获取全局Dashboard数据 */
  getDashboard() {
    return request('/schedule/dashboard')
  },

  /** 执行飞机排班算法 */
  runRouting(algorithm = 'bipartite', numAircraft = 12, minGap = 60) {
    return request('/schedule/routing', {
      method: 'POST',
      body: JSON.stringify({
        algorithm,
        num_aircraft: numAircraft,
        min_gap: minGap,
      }),
    })
  },

  /** 对比不同排班算法 */
  compareRouting() {
    return request('/schedule/compare')
  },

  /** 执行跑道调度 */
  runRunway(method = 'fcfs', landing = true, airport = '') {
    return request('/schedule/runway', {
      method: 'POST',
      body: JSON.stringify({ method, landing, airport }),
    })
  },

  /** 保存调度方案到后端，供地图演示 */
  saveSchedule(date, routingAircrafts, runwayItems) {
    return request('/schedule/save', {
      method: 'POST',
      body: JSON.stringify({
        date,
        routing_aircrafts: routingAircrafts,
        runway_items: runwayItems,
      }),
    })
  },

  /** 获取已保存调度的日期列表 */
  getSavedDates() {
    return request('/schedule/saved-dates')
  },

  /** 获取指定日期的地图飞行动画数据 */
  getMapData(date) {
    return request(`/schedule/map-data?date=${encodeURIComponent(date)}`)
  },

  /** 执行登机口自动分配 */
  assignGates(airport = '成都', algorithm = 'bipartite', date = null) {
    return request('/schedule/gates', {
      method: 'POST',
      body: JSON.stringify({ airport, algorithm, date }),
    })
  },

  /** 对比登机口分配算法 */
  compareGates(airport = '成都', date = null) {
    return request('/schedule/gates/compare', {
      method: 'POST',
      body: JSON.stringify({ airport, date }),
    })
  },

  /** 保存登机口分配方案 */
  saveGates(date, gates) {
    return request('/schedule/save-gates', {
      method: 'POST',
      body: JSON.stringify({ date, gates }),
    })
  },

  /** 执行机组自动排班 */
  scheduleCrew(airport = null, date = null, mode = 'greedy', airline = null) {
    return request('/schedule/crew', {
      method: 'POST',
      body: JSON.stringify({ airport, date, mode, airline }),
    })
  },

  /** 获取航司列表 */
  getAirlines() {
    return request('/airlines')
  },

  /** 获取机组可用基地列表（可指定航司） */
  getCrewBases(airline = null) {
    const qs = airline ? `?airline=${encodeURIComponent(airline)}` : ''
    return request('/crew/bases' + qs)
  },

  /** 获取指定基地机组人员列表（按角色分组） */
  getCrewByBase(base = '成都', airline = '四川航空') {
    return request(`/crew/by-base?base=${encodeURIComponent(base)}&airline=${encodeURIComponent(airline)}`)
  },

  /** 获取机组替班变更列表 */
  getCrewSubstitutions() {
    return request('/crew/substitutions')
  },

  /** 获取任务链列表（不执行排班） */
  getPairings(airport = null) {
    return request('/pairings/list', {
      method: 'POST',
      body: JSON.stringify({ airport }),
    })
  },

  /** 手动指派选中pairing → 自动填充剩余 */
  assignPairings(airport = null, date = null, selectedIds = []) {
    return request('/schedule/crew/adjust', {
      method: 'POST',
      body: JSON.stringify({ airport, selected_ids: selectedIds }),
    })
  },

  /** 手动组建机组并分配任务链 */
  assignPairingToTeam(airport, pairingId, captainId, officerId, purserId, attendantIds, capName, offName, purName, att1Name, att2Name) {
    return request('/crew/assign-pairing-to-team', {
      method: 'POST',
      body: JSON.stringify({
        airport,
        pairing_id: pairingId,
        captain_id: captainId,
        officer_id: officerId,
        purser_id: purserId,
        attendant_ids: attendantIds,
        captain_name: capName,
        officer_name: offName,
        purser_name: purName,
        attendant_names: [att1Name, att2Name],
      }),
    })
  },

  /** 导出机组排班表为 xlsx */
  async exportCrewSchedule(airport = null, date = null, airline = null) {
    const resp = await fetch(`${BASE_URL}/crew/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ airport, date, airline }),
    })
    if (!resp.ok) throw new Error('导出失败')
    const blob = await resp.blob()
    const disposition = resp.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    const filename = match ? match[1].replace(/['"]/g, '') : '机组排班表.xlsx'
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  },

  /** 手动为单个航班分配机组 */
  manualAssignFlight(airport, flightId, captainId, officerId, purserId, attendantIds) {
    return request('/crew/manual-assign-flight', {
      method: 'POST',
      body: JSON.stringify({
        airport,
        flight_id: flightId,
        captain_id: captainId,
        officer_id: officerId,
        purser_id: purserId,
        attendant_ids: attendantIds,
      }),
    })
  },

  /** 查询航班可用的机组人员 */
  getAvailableCrew(airport, flightId) {
    return request('/crew/available-for-flight', {
      method: 'POST',
      body: JSON.stringify({ airport, flight_id: flightId }),
    })
  },

  /** 对比机组排班 */
  compareCrew(airport = null, date = null) {
    return request('/schedule/crew/compare', {
      method: 'POST',
      body: JSON.stringify({ airport, date }),
    })
  },

  /** 保存机组排班方案 */
  saveCrew(date, crew) {
    return request('/schedule/save-crew', {
      method: 'POST',
      body: JSON.stringify({ date, crew }),
    })
  },

  /** 交换两个团队中同岗位人员 */
  swapCrewMembers(teamIdA, teamIdB, role, attendantIndex = 0) {
    return request('/schedule/crew/swap', {
      method: 'POST',
      body: JSON.stringify({
        team_id_a: teamIdA,
        team_id_b: teamIdB,
        role,
        attendant_index: attendantIndex,
      }),
    })
  },

  // ========== 异常调度 API ==========

  /** 获取场景模板列表 */
  getAnomalyTemplates(category) {
    const qs = category ? `?category=${encodeURIComponent(category)}` : ''
    return request(`/anomaly/templates${qs}`)
  },

  /** 获取模板详情 */
  getAnomalyTemplate(templateId) {
    return request(`/anomaly/templates/${templateId}`)
  },

  /** 获取异常参数 Schema */
  getAnomalyParamsSchema() {
    return request('/anomaly/templates/params-schema')
  },

  /** 获取表单上下文（机场/飞机/日期动态选项） */
  getAnomalyContext() {
    return request('/anomaly/context')
  },

  /** 获取异常事件列表 */
  getAnomalyEvents(status) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    return request(`/anomaly/events${qs}`)
  },

  /** 获取异常事件详情 */
  getAnomalyEvent(eventId) {
    return request(`/anomaly/events/${eventId}`)
  },

  /** 创建异常事件 */
  createAnomalyEvent(data) {
    return request('/anomaly/events', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  /** 更新异常事件 */
  updateAnomalyEvent(eventId, data) {
    return request(`/anomaly/events/${eventId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  /** 删除异常事件 */
  deleteAnomalyEvent(eventId) {
    return request(`/anomaly/events/${eventId}`, {
      method: 'DELETE',
    })
  },

  /** 分析异常事件影响并生成恢复方案 */
  analyzeAnomalyEvent(eventId) {
    return request(`/anomaly/events/${eventId}/analyze`, {
      method: 'POST',
    })
  },

  /** 批量分析多个事件 */
  batchAnalyze(eventIds) {
    return request('/anomaly/events/batch-analyze', {
      method: 'POST',
      body: JSON.stringify({ event_ids: eventIds }),
    })
  },

  /** 获取影响分析报告 */
  getImpactReport(eventId) {
    return request(`/anomaly/events/${eventId}/impact`)
  },

  /** 获取恢复方案 */
  getRecoveryPlan(planId) {
    return request(`/anomaly/plans/${planId}`)
  },

  /** 确认恢复方案 */
  confirmPlan(planId) {
    return request(`/anomaly/plans/${planId}/confirm`, {
      method: 'POST',
    })
  },

  /** 拒绝恢复方案 */
  rejectPlan(planId) {
    return request(`/anomaly/plans/${planId}/reject`, {
      method: 'POST',
    })
  },

  /** 执行恢复方案 */
  executePlan(planId) {
    return request(`/anomaly/plans/${planId}/execute`, {
      method: 'POST',
    })
  },

  /** 回滚恢复方案 */
  rollbackPlan(planId) {
    return request(`/anomaly/plans/${planId}/rollback`, {
      method: 'POST',
    })
  },

  /** 人工微调方案 */
  adjustPlan(planId, adjustments) {
    return request(`/anomaly/plans/${planId}/adjust`, {
      method: 'POST',
      body: JSON.stringify({ adjustments }),
    })
  },

  /** 获取备份资源 */
  getBackupResources() {
    return request('/anomaly/backup-resources')
  },

  /** 设置备份资源 */
  setBackupResources(data) {
    return request('/anomaly/backup-resources', {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  /** 自动生成备份资源 */
  generateBackupResources() {
    return request('/anomaly/backup-resources/generate', {
      method: 'POST',
    })
  },

  /** 获取模块异常标记覆盖数据 */
  getAnomalyOverlays(status) {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    return request(`/anomaly/overlays${qs}`)
  },

  /** 获取审计日志 */
  getAuditLog(action, targetType, limit, offset) {
    const params = new URLSearchParams()
    if (action) params.set('action', action)
    if (targetType) params.set('target_type', targetType)
    if (limit) params.set('limit', limit)
    if (offset) params.set('offset', offset)
    return request(`/anomaly/audit-log?${params.toString()}`)
  },

  // ========== 模拟引擎 API（自动识别 live / replay 作用域） ==========

  /** 初始化仿真 */
  initSimulation(airport) {
    return request(scoped('/init', '/simulation/init'), {
      method: 'POST',
      body: JSON.stringify({ airport }),
    })
  },

  /** 启动仿真 */
  startSimulation() {
    return request(scoped('/start', '/simulation/start'), { method: 'POST' })
  },

  /** 暂停仿真 */
  pauseSimulation() {
    return request(scoped('/pause', '/simulation/pause'), { method: 'POST' })
  },

  /** 恢复仿真 */
  resumeSimulation() {
    return request(scoped('/resume', '/simulation/resume'), { method: 'POST' })
  },

  /** 停止仿真 */
  stopSimulation() {
    return request(scoped('/stop', '/simulation/stop'), { method: 'POST' })
  },

  /** 单步执行 */
  stepSimulation() {
    return request(scoped('/step', '/simulation/step'), { method: 'POST' })
  },

  /** 设置倍速 */
  setSimSpeed(speed) {
    return request(scoped('/speed', '/simulation/speed'), {
      method: 'POST',
      body: JSON.stringify({ speed }),
    })
  },

  /** 跳转到指定进度 */
  jumpSimulation(progressPct) {
    return request(scoped('/jump', '/simulation/jump'), {
      method: 'POST',
      body: JSON.stringify({ progress_pct: progressPct }),
    })
  },

  /** 按绝对业务分钟同步引擎时钟（供「模拟大引擎」统一时钟驱动） */
  syncSimTime(currentMinutes) {
    return request(scoped('/sync', '/simulation/sync_time'), {
      method: 'POST',
      body: JSON.stringify({ current_minutes: currentMinutes }),
    })
  },

  /** 获取仿真快照 */
  getSimSnapshot() {
    return request(scoped('/snapshot', '/simulation/snapshot'))
  },

  /** 获取航班状态 */
  getSimFlights() {
    return request(scoped('/flights', '/simulation/flights'))
  },

  /** 获取 KPI */
  getSimKpi() {
    return request(scoped('/kpi', '/simulation/kpi'))
  },

  /** 获取天气 */
  getSimWeather(airport) {
    const qs = airport ? `?airport=${encodeURIComponent(airport)}` : ''
    return request(scoped('/weather', '/simulation/weather') + qs)
  },

  /** 获取仿真上下文（机场/飞机/基地） */
  getSimContext() {
    return request(scoped('/context', '/simulation/context'))
  },

  _rejectInReplay() {
    if (currentScope()) {
      return Promise.reject(new Error('回放模式不支持注入事件'))
    }
    return null
  },

  /** 注入机场异常 */
  injectAirportAnomaly(airport, capacityRatio, durationMin) {
    const reject = this._rejectInReplay()
    if (reject) return reject
    return request('/simulation/inject/airport', {
      method: 'POST',
      body: JSON.stringify({ airport, capacity_ratio: capacityRatio, duration_min: durationMin }),
    })
  },

  /** 注入机组请假 */
  injectCrewAbsence(crewNames, base) {
    const reject = this._rejectInReplay()
    if (reject) return reject
    return request('/simulation/inject/crew', {
      method: 'POST',
      body: JSON.stringify({ crew_names: crewNames, base }),
    })
  },

  /** 注入飞机故障 */
  injectAircraftFailure(tailNo, durationMin) {
    const reject = this._rejectInReplay()
    if (reject) return reject
    return request('/simulation/inject/aircraft', {
      method: 'POST',
      body: JSON.stringify({ tail_no: tailNo, duration_min: durationMin }),
    })
  },

  /** 获取活跃事件 */
  getSimEvents() {
    return request(scoped('/events', '/simulation/events'))
  },

  /** 移除事件 */
  removeSimEvent(index) {
    return request(scoped(`/events/${index}`, `/simulation/events/${index}`), { method: 'DELETE' })
  },

  // ========== 旅客流 / 天气中断（带作用域） ==========

  /** 获取旅客流调度；回放时读实验工件 */
  getPaxflowSchedule(disrupted = true) {
    const live = '/paxflow/schedule' + (disrupted ? '?disrupted=true' : '')
    return request(scoped('/paxflow', live))
  },

  /** 获取旅客编号清单；回放时返回空清单，前端用兜底编号 */
  getPaxflowManifests(payload) {
    return request(scoped('/manifests', '/paxflow/manifests'), {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  /** 读取当前天气中断计划（回放时读实验情景） */
  getWeatherDisruption() {
    return request(scoped('/weather_disruption', '/weather/disruption'))
  },

  // ========== 天气中断联动 API ==========

  /** 天气页自动回传当前各省天气 + 气旋推演时间线 */
  weatherStream(payload) {
    return request('/weather/stream', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}
