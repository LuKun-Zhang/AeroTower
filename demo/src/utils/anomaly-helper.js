/** 异常调度工具函数 */

// ========== 四大异常分类 ==========

export const ANOMALY_CATEGORIES = [
  {
    key: 'weather',
    label: '天气异常',
    icon: 'el-icon-cloudy',
    description: '省级天气灾害 → 起降机场+途经航线航班均受影响，自动延迟或取消',
    color: '#00BCD4',
    subTypes: [
      { value: 'weather_typhoon', label: '台风' },
      { value: 'weather_storm', label: '雷暴' },
      { value: 'weather_rain', label: '暴雨' },
      { value: 'weather_snow', label: '暴雪' },
      { value: 'weather_fog', label: '大雾' },
      { value: 'weather_enroute', label: '航路天气' },
    ],
  },
  {
    key: 'airport',
    label: '机场异常',
    icon: 'el-icon-office-building',
    description: '机场天气、跑道关闭等 → 自动查找受影响航班，安排备降或取消',
    color: '#409EFF',
    subTypes: [
      { value: 'weather_airport_closure', label: '天气关闭' },
      { value: 'weather_capacity', label: '大雾低能见度' },
      { value: 'runway_closure', label: '跑道关闭' },
      { value: 'runway_degrade', label: '跑道降级' },
    ],
  },
  {
    key: 'aircraft',
    label: '飞机异常',
    icon: 'el-icon-service',
    description: '飞机机械故障等 → 调整飞机排班，替换故障飞机',
    color: '#E6A23C',
    subTypes: [
      { value: 'aircraft_failure', label: '机械故障' },
      { value: 'aircraft_maintenance', label: '定检超时' },
      { value: 'aircraft_diversion', label: '备降/迫降' },
    ],
  },
  {
    key: 'crew',
    label: '机组异常',
    icon: 'el-icon-user-solid',
    description: '机组成员请假 → 同基地同岗位替班，不影响其他排班',
    color: '#67C23A',
    subTypes: [
      { value: 'crew_substitution', label: '人员替班' },
    ],
  },
]

/** event_type → category 映射 */
export const ANOMALY_CATEGORY_MAP = {}
ANOMALY_CATEGORIES.forEach(cat => {
  cat.subTypes.forEach(st => {
    ANOMALY_CATEGORY_MAP[st.value] = cat.key
  })
})

/** 通过 event_type 反查分类信息 */
export function getCategoryInfo(eventType) {
  const key = ANOMALY_CATEGORY_MAP[eventType]
  return ANOMALY_CATEGORIES.find(c => c.key === key) || null
}

// ========== 兼容旧版类型标签 ==========

/** 保留完整标签映射，供事件列表展示用 */
export const ANOMALY_TYPE_LABELS = {}
ANOMALY_CATEGORIES.forEach(cat => {
  cat.subTypes.forEach(st => {
    ANOMALY_TYPE_LABELS[st.value] = `${cat.label} · ${st.label}`
  })
})

// ========== 优先级 ==========

export const PRIORITY_CONFIG = {
  P0: { label: '紧急(P0)', color: '#F56C6C', type: 'danger' },
  P1: { label: '严重(P1)', color: '#E6A23C', type: 'warning' },
  P2: { label: '重要(P2)', color: '#409EFF', type: 'primary' },
  P3: { label: '一般(P3)', color: '#909399', type: 'info' },
}

// ========== 状态 ==========

export const STATUS_CONFIG = {
  pending: { label: '待处理', color: '#E6A23C', type: 'warning' },
  analyzing: { label: '分析中', color: '#409EFF', type: 'primary' },
  recovering: { label: '恢复中', color: '#67C23A', type: 'success' },
  resolved: { label: '已解决', color: '#909399', type: 'info' },
}

// ========== 变更类型 ==========

export const CHANGE_TYPE_LABELS = {
  CANCEL: '取消航班',
  DELAY: '延迟',
  REASSIGN_AIRCRAFT: '更换飞机',
  REASSIGN_CREW: '更换机组',
  REASSIGN_GATE: '更换登机口',
  REASSIGN_RUNWAY: '更换跑道',
  MERGE: '合并航班',
  ADD: '新增航班',
}

// ========== 策略 ==========

export const STRATEGY_LABELS = {
  ResourceReplacementStrategy: '资源替换',
  TimeShiftStrategy: '时间平移',
  ChainReplanningStrategy: '链重规划',
  MergeFlightsStrategy: '航班合并',
  CancelFlightsStrategy: '航班取消',
  AircraftExclusionRecovery: '飞机异常恢复',
  AirportClosureRecovery: '机场关闭恢复',
  WeatherProvinceRecovery: '天气省份恢复',
}
