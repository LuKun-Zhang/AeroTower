<template>
  <div class="anomaly-panel">
    <div class="panel-header">
      <h3><i class="el-icon-warning-outline"></i> 异常事件</h3>
      <div class="panel-actions">
        <el-button type="primary" size="small" icon="el-icon-plus" @click="openCreate">新建事件</el-button>
        <el-button size="small" icon="el-icon-refresh" @click="refresh">刷新</el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="status-filter">
      <el-tag
        v-for="s in statusFilters"
        :key="s.value"
        :type="currentStatus === s.value ? '' : 'info'"
        :effect="currentStatus === s.value ? 'dark' : 'plain'"
        :color="currentStatus === s.value ? s.color : ''"
        size="small"
        style="cursor:pointer;margin-right:6px;"
        @click="filterByStatus(s.value)"
      >{{ s.label }}</el-tag>
    </div>

    <!-- 事件列表 -->
    <div class="event-list" v-loading="loading">
      <div
        v-for="event in events"
        :key="event.event_id"
        class="event-card"
        :class="{ selected: selectedId === event.event_id }"
        @click="selectEvent(event)"
      >
        <div class="event-card-top">
          <el-tag :type="getPriorityType(event.priority)" size="mini">{{ event.priority }}</el-tag>
          <span class="event-title">{{ event.title }}</span>
        </div>
        <div class="event-card-meta">
          <span class="event-type">{{ getAnomalyLabel(event.event_type) }}</span>
          <el-tag :type="getStatusType(event.status)" size="mini">{{ getStatusLabel(event.status) }}</el-tag>
        </div>
        <div class="event-card-time" v-if="event.start_time">
          {{ event.start_time }} ~ {{ event.end_time }}
        </div>
        <div class="event-card-desc" v-if="event.description">{{ event.description }}</div>
      </div>
      <div v-if="events.length === 0 && !loading" class="empty-hint">暂无异常事件</div>
    </div>

    <!-- ========== 创建事件对话框 ========== -->
    <el-dialog
      :title="createStep === 0 ? '选择异常类型' : '创建' + selectedCategory.label + '事件'"
      :visible.sync="showCreateDialog"
      width="600px"
      :close-on-click-modal="false"
      @close="resetCreateDialog"
    >
      <!-- 步骤 0：选择分类 -->
      <div v-if="createStep === 0" class="category-grid">
        <div
          v-for="cat in ANOMALY_CATEGORIES"
          :key="cat.key"
          class="category-card"
          :style="{ borderColor: cat.color }"
          @click="selectCategory(cat)"
        >
          <div class="category-icon" :style="{ color: cat.color }">
            <i :class="cat.icon"></i>
          </div>
          <div class="category-info">
            <div class="category-label" :style="{ color: cat.color }">{{ cat.label }}</div>
            <div class="category-desc">{{ cat.description }}</div>
          </div>
          <i class="el-icon-arrow-right category-arrow"></i>
        </div>
      </div>

      <!-- 步骤 1：分类专属表单 -->
      <div v-if="createStep === 1">
        <div class="step-back" @click="createStep = 0">
          <i class="el-icon-arrow-left"></i> 返回选择类型
        </div>

        <el-form ref="createForm" :model="createForm" :rules="createRules" label-width="100px" size="small" class="create-form">

          <!-- 公共字段：标题 -->
          <el-form-item label="事件标题" prop="title">
            <el-input v-model="createForm.title" :placeholder="titlePlaceholder" />
          </el-form-item>

          <!-- 子类型 -->
          <el-form-item label="异常子类" prop="sub_type">
            <el-select v-model="createForm.sub_type" placeholder="选择具体异常类型" style="width:100%">
              <el-option
                v-for="st in selectedCategory.subTypes"
                :key="st.value"
                :label="st.label"
                :value="st.value"
              />
            </el-select>
          </el-form-item>

          <!-- ========== 天气·省份异常专属 ========== -->
          <template v-if="selectedCategory.key === 'weather'">
            <el-form-item label="受影响省份" prop="affected_provinces">
              <el-select
                v-model="createForm.affected_provinces" multiple filterable
                placeholder="选择受天气影响的省份（可多选）" style="width:100%"
                :loading="ctxLoading"
              >
                <el-option v-for="p in formContext.provinces" :key="p" :label="p" :value="p" />
              </el-select>
            </el-form-item>
            <el-form-item label="严重程度" prop="severity">
              <el-select v-model="createForm.severity" style="width:100%">
                <el-option :value="1" label="轻微（延误30min）" />
                <el-option :value="2" label="轻度（延误1h）" />
                <el-option :value="3" label="中度（延误2h）" />
                <el-option :value="4" label="重度（延误3h）" />
                <el-option :value="5" label="极重（取消航班）" />
              </el-select>
            </el-form-item>
          </template>

          <!-- ========== 机场异常专属 ========== -->
          <template v-if="selectedCategory.key === 'airport'">
            <el-form-item label="受影响机场" prop="affected_airports">
              <el-select
                v-model="createForm.affected_airports" multiple filterable
                placeholder="选择受影响的机场（可多选）" style="width:100%"
                :loading="ctxLoading"
              >
                <el-option v-for="ap in formContext.airports" :key="ap" :label="ap" :value="ap" />
              </el-select>
            </el-form-item>
          </template>

          <!-- ========== 飞机异常专属 ========== -->
          <template v-if="selectedCategory.key === 'aircraft'">
            <el-form-item label="受影响飞机" prop="affected_aircraft">
              <el-select
                v-model="createForm.affected_aircraft" multiple filterable
                placeholder="选择受影响的飞机（可多选）" style="width:100%"
                :loading="ctxLoading"
              >
                <el-option
                  v-for="ac in formContext.aircrafts"
                  :key="ac.tail_no"
                  :label="`${ac.tail_no}${ac.ac_type ? ' (' + ac.ac_type + ')' : ''}`"
                  :value="ac.tail_no"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="维修小时" v-if="createForm.sub_type !== 'aircraft_diversion'">
              <el-input-number v-model="createForm.repair_hours" :min="1" :max="72" :step="1" />
            </el-form-item>
          </template>

          <!-- ========== 机组异常专属 ========== -->
          <template v-if="selectedCategory.key === 'crew'">
            <el-form-item label="基地" prop="crew_base">
              <el-select
                v-model="createForm.crew_base"
                placeholder="选择川航基地"
                style="width:100%"
                @change="onCrewBaseChange"
              >
                <el-option
                  v-for="b in formContext.bases"
                  :key="b"
                  :label="b"
                  :value="b"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="请假人员" prop="affected_crew">
              <el-select
                v-model="createForm.affected_crew"
                placeholder="选择请假人员"
                style="width:100%"
                filterable
                :disabled="!createForm.crew_base"
                :loading="crewBaseLoading"
              >
                <el-option-group
                  v-for="group in crewRoleGroups"
                  :key="group.role"
                  :label="group.label"
                >
                  <el-option
                    v-for="m in group.members"
                    :key="m.crew_id"
                    :label="`${m.name}（${group.label}）`"
                    :value="m.name"
                  />
                </el-option-group>
              </el-select>
            </el-form-item>
            <el-form-item label="开始时间" prop="crew_start_time">
              <el-date-picker
                v-model="createForm.crew_start_time"
                type="datetime"
                placeholder="选择请假开始时间"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd HH:mm"
                :default-value="defaultDateValue"
                style="width:100%"
              />
            </el-form-item>
            <el-form-item label="结束时间" prop="crew_end_time">
              <el-date-picker
                v-model="createForm.crew_end_time"
                type="datetime"
                placeholder="选择请假结束时间"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd HH:mm"
                :default-value="defaultDateValue"
                style="width:100%"
              />
            </el-form-item>
          </template>

          <!-- 公共：时间 -->
          <template v-if="selectedCategory.key !== 'crew'">
            <el-form-item label="开始时间">
              <el-date-picker
                :key="'start-' + ctxKey"
                v-model="createForm.start_time"
                type="datetime"
                placeholder="选择开始日期时间"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd HH:mm"
                :default-value="defaultDateValue"
                :picker-options="datePickerOptions"
                style="width:100%"
              />
            </el-form-item>
            <el-form-item label="结束时间">
              <el-date-picker
                :key="'end-' + ctxKey"
                v-model="createForm.end_time"
                type="datetime"
                placeholder="选择结束日期时间"
                format="yyyy-MM-dd HH:mm"
                value-format="yyyy-MM-dd HH:mm"
                :default-value="defaultDateValue"
                :picker-options="datePickerOptions"
                style="width:100%"
              />
            </el-form-item>
          </template>

          <!-- 公共：优先级 -->
          <el-form-item label="优先级">
            <el-radio-group v-model="createForm.priority">
              <el-radio-button label="P0">P0 紧急</el-radio-button>
              <el-radio-button label="P1">P1 严重</el-radio-button>
              <el-radio-button label="P2">P2 重要</el-radio-button>
              <el-radio-button label="P3">P3 一般</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <!-- 公共：描述 -->
          <el-form-item label="描述">
            <el-input v-model="createForm.description" type="textarea" :rows="2" placeholder="补充描述（可选）" />
          </el-form-item>

        </el-form>
      </div>

      <div slot="footer" v-if="createStep === 1">
        <el-button @click="createStep = 0">上一步</el-button>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitCreate" :loading="creating">创建事件</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import {
  ANOMALY_CATEGORIES, ANOMALY_TYPE_LABELS,
  PRIORITY_CONFIG, STATUS_CONFIG, getCategoryInfo,
} from '@/utils/anomaly-helper'
import api from '@/api'

/** 默认表单 */
const emptyForm = () => ({
  title: '',
  sub_type: '',
  priority: 'P2',
  affected_airports: [],
  affected_aircraft: [],
  affected_flights: [],
  affected_crew: [],  // 机组替班时为单个人员姓名
  affected_provinces: [],
  severity: 3,
  start_time: '',
  end_time: '',
  repair_hours: 4,
  delay_minutes: 120,
  cancel_reason: '',
  crew_base: '',
  crew_start_time: '',
  crew_end_time: '',
  description: '',
})

export default {
  name: 'AnomalyPanel',
  data() {
    return {
      ANOMALY_CATEGORIES,
      showCreateDialog: false,
      creating: false,
      createStep: 0,
      selectedCategory: null,
      currentStatus: '',
      ctxLoading: false,
      ctxKey: 0,
      crewBaseLoading: false,
      crewByBase: [],
      formContext: {
        airports: [],
        aircrafts: [],
        flights: [],
        crew: [],
        dates: [],
        provinces: [],
        bases: ['成都', '重庆', '昆明', '杭州', '绵阳', '宜宾'],
      },
      createForm: emptyForm(),
      createRules: {
        title: [{ required: true, message: '必填', trigger: 'blur' }],
        sub_type: [{ required: true, message: '必选', trigger: 'change' }],
        affected_airports: [{ type: 'array', required: false, min: 1, message: '至少选择一个机场', trigger: 'change' }],
        affected_aircraft: [{ type: 'array', required: false, min: 1, message: '至少选择一架飞机', trigger: 'change' }],
        affected_flights: [{ type: 'array', required: false, min: 1, message: '至少选择一个航班', trigger: 'change' }],
        crew_date: [{ required: false, message: '必选', trigger: 'change' }],
        crew_base: [{ required: false, message: '必选', trigger: 'change' }],
        affected_crew: [{ type: 'array', required: false }],
        crew_start_time: [{ required: false, message: '必选', trigger: 'change' }],
        crew_end_time: [{ required: false, message: '必选', trigger: 'change' }],
      },
      statusFilters: [
        { label: '全部', value: '', color: '' },
        { label: '待处理', value: 'pending', color: '#E6A23C' },
        { label: '分析中', value: 'analyzing', color: '#409EFF' },
        { label: '恢复中', value: 'recovering', color: '#67C23A' },
        { label: '已解决', value: 'resolved', color: '#909399' },
      ],
    }
  },
  computed: {
    ...mapState({
      events: state => state.activeAnomalies,
      loading: state => state.loading,
      selectedId: state => state.selectedAnomaly ? state.selectedAnomaly.event_id : null,
    }),
    crewRoleGroups() {
      const roleLabels = { captain: '机长', first_officer: '副驾驶', purser: '乘务长', attendant: '乘务员' }
      const groups = {}
      for (const m of this.crewByBase) {
        if (!groups[m.role]) groups[m.role] = { role: m.role, label: roleLabels[m.role] || m.role, members: [] }
        groups[m.role].members.push(m)
      }
      return Object.values(groups)
    },
    datePickerOptions() {
      const validDates = new Set(this.formContext.dates)
      return {
        disabledDate(time) {
          const d = time.getFullYear() + '-' +
            String(time.getMonth() + 1).padStart(2, '0') + '-' +
            String(time.getDate()).padStart(2, '0')
          return !validDates.has(d)
        },
      }
    },
    defaultDateValue() {
      const dates = this.formContext.dates
      if (dates.length > 0) {
        // Element UI 的 default-value 必须是 Date 对象
        return new Date(dates[0] + 'T08:00:00')
      }
      return null
    },
    titlePlaceholder() {
      const m = {
        airport: '如：成都双流机场暴雨关闭',
        aircraft: '如：B-6388 发动机故障',
        crew: '如：机长张三突发请假',
      }
      return (this.selectedCategory && m[this.selectedCategory.key]) || '事件标题'
    },
  },
  methods: {
    ...mapActions([
      'fetchAnomalyEvents', 'createAnomalyEvent', 'deleteAnomalyEvent',
      'fetchOverlays',
    ]),
    getAnomalyLabel(type) {
      return ANOMALY_TYPE_LABELS[type] || type
    },
    getCategoryLabel(type) {
      const info = getCategoryInfo(type)
      return info ? info.label : ''
    },
    getPriorityType(p) {
      return (PRIORITY_CONFIG[p] || {}).type || 'info'
    },
    getStatusType(s) {
      return (STATUS_CONFIG[s] || {}).type || 'info'
    },
    getStatusLabel(s) {
      return (STATUS_CONFIG[s] || {}).label || s
    },
    filterByStatus(status) {
      this.currentStatus = status
      this.fetchAnomalyEvents(status || undefined)
    },
    selectEvent(event) {
      this.$emit('select', event)
    },
    refresh() {
      this.fetchAnomalyEvents(this.currentStatus || undefined)
    },

    // -------- 创建流程 --------
    openCreate() {
      this.createStep = 0
      this.selectedCategory = null
      this.createForm = emptyForm()
      this.showCreateDialog = true
      this.loadContext()
    },
    selectCategory(cat) {
      this.selectedCategory = cat
      this.createStep = 1
      this.createForm = emptyForm()
      // 动态调整校验规则
      this.applyCategoryRules(cat.key)
    },
    applyCategoryRules(key) {
      const rules = { ...this.createRules }
      if (key === 'weather') rules.affected_provinces = [{ type: 'array', required: true, min: 1, message: '至少选择一个省份', trigger: 'change' }]
      else if (key === 'airport') rules.affected_airports = [{ type: 'array', required: true, min: 1, message: '至少选择一个机场', trigger: 'change' }]
      else if (key === 'aircraft') rules.affected_aircraft = [{ type: 'array', required: true, min: 1, message: '至少选择一架飞机', trigger: 'change' }]
      else if (key === 'crew') {
        rules.crew_base = [{ required: true, message: '必选基地', trigger: 'change' }]
        rules.affected_crew = [{ required: true, message: '至少选择一人', trigger: 'change' }]
        rules.crew_start_time = [{ required: true, message: '必选开始时间', trigger: 'change' }]
        rules.crew_end_time = [{ required: true, message: '必选结束时间', trigger: 'change' }]
      }
      this.createRules = rules
    },
    resetCreateDialog() {
      this.createStep = 0
      this.selectedCategory = null
      this.createForm = emptyForm()
    },

    async submitCreate() {
      this.$refs.createForm.validate(async (valid) => {
        if (!valid) return
        this.creating = true
        try {
          // 构建提交数据：sub_type → event_type，拼装描述
          const sub = this.createForm.sub_type
          const catLabel = this.selectedCategory.label
          const subLabel = (this.selectedCategory.subTypes.find(s => s.value === sub) || {}).label || ''
          const descParts = [`[${catLabel}·${subLabel}]`]
          if (this.createForm.description) descParts.push(this.createForm.description)

          const payload = {
            event_type: sub,
            title: this.createForm.title,
            description: descParts.join(' '),
            priority: this.createForm.priority,
            affected_airports: this.createForm.affected_airports,
            affected_aircraft: this.createForm.affected_aircraft,
            affected_flights: this.createForm.affected_flights,
            affected_crew: Array.isArray(this.createForm.affected_crew) ? this.createForm.affected_crew : (this.createForm.affected_crew ? [this.createForm.affected_crew] : []),
            start_time: this.createForm.start_time,
            end_time: this.createForm.end_time,
            duration_minutes: this.createForm.repair_hours ? this.createForm.repair_hours * 60 : 0,
            delay_minutes: this.createForm.delay_minutes,
            severity: this.createForm.severity,
          }

          // 天气·省份异常：省份列表覆盖 affected_airports
          if (this.selectedCategory.key === 'weather') {
            payload.affected_airports = this.createForm.affected_provinces
            payload.severity = this.createForm.severity
          }

          // 机组异常：使用 crew_start_time / crew_end_time
          if (this.selectedCategory.key === 'crew' && this.createForm.crew_start_time) {
            payload.start_time = this.createForm.crew_start_time + ':00'
            payload.end_time = this.createForm.crew_end_time + ':00'
            delete payload.crew_date
          }

          await this.createAnomalyEvent(payload)
          this.showCreateDialog = false
          this.resetCreateDialog()
          this.$message.success('事件创建成功')
        } catch (e) {
          this.$message.error('创建失败: ' + (e.message || '未知错误'))
        } finally {
          this.creating = false
        }
      })
    },

    async onCrewBaseChange(base) {
      if (!base) return
      this.crewBaseLoading = true
      try {
        const data = await api.getCrewByBase(base, '四川航空')
        this.crewByBase = data.crew || []
      } catch (e) {
        console.error('[AnomalyPanel] 加载基地人员失败:', e)
        this.crewByBase = []
      } finally {
        this.crewBaseLoading = false
      }
    },

    async loadContext() {
      this.ctxLoading = true
      try {
        const [data, bases] = await Promise.all([
          api.getAnomalyContext(),
          api.getCrewBases('四川航空'),
        ])
        this.formContext = {
          airports: data.airports || [],
          aircrafts: data.aircrafts || [],
          flights: data.flights || [],
          crew: data.crew || [],
          provinces: data.provinces || [],
          bases: bases && bases.length ? bases : ['成都', '重庆', '昆明', '杭州', '绵阳', '宜宾'],
          dates: (data.dates && data.dates.length) ? data.dates : (() => {
            const days = []
            for (let d = 30; d <= 30; d++) days.push(`2020-11-${String(d).padStart(2, '0')}`)
            for (let d = 1; d <= 6; d++) days.push(`2020-12-${String(d).padStart(2, '0')}`)
            return days
          })(),
        }
        console.log('[AnomalyPanel] 上下文已加载:', {
          airports: this.formContext.airports.length,
          aircrafts: this.formContext.aircrafts.length,
          flights: this.formContext.flights.length,
          crew: this.formContext.crew.length,
          dates: this.formContext.dates.length,
          bases: this.formContext.bases.length,
        })
      } catch (e) {
        console.error('[AnomalyPanel] 加载表单上下文失败:', e)
        this.formContext = {
          airports: ['成都', '重庆', '昆明', '杭州', '北京', '三亚', '乌鲁木齐', '哈尔滨'],
          aircrafts: [...Array(12)].map((_, i) => ({
            tail_no: `B-${6388 + i}`,
            ac_type: 'A320',
            base: '成都',
          })),
          flights: [],
          crew: ['CA_Zhang', 'FO_Li', 'CA_Wang', 'FO_Chen'],
          provinces: ['四川', '重庆', '云南', '贵州', '广东', '广西', '海南', '福建', '浙江', '江苏', '湖北', '湖南', '江西', '安徽', '河南', '河北', '山东', '陕西', '甘肃', '青海', '宁夏', '新疆', '西藏', '内蒙古', '黑龙江', '吉林', '辽宁', '北京', '上海', '天津'],
          bases: ['成都', '重庆', '昆明', '杭州', '绵阳', '宜宾'],
          dates: (() => {
            const days = []
            for (let d = 30; d <= 30; d++) days.push(`2020-11-${String(d).padStart(2, '0')}`)
            for (let d = 1; d <= 6; d++) days.push(`2020-12-${String(d).padStart(2, '0')}`)
            return days
          })(),
        }
      } finally {
        this.ctxLoading = false
        this.ctxKey++
      }
    },
  },
  mounted() {
    this.fetchAnomalyEvents()
    this.loadContext()
  },
}
</script>

<style scoped>
.anomaly-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 4px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}
.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: #303133;
}
.panel-header h3 i {
  color: #E6A23C;
  margin-right: 6px;
}
.status-filter {
  padding: 8px 16px;
  border-bottom: 1px solid #ebeef5;
}
.event-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.event-card {
  padding: 10px 12px;
  margin-bottom: 6px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
.event-card:hover {
  border-color: #409EFF;
  background: #ecf5ff;
}
.event-card.selected {
  border-color: #409EFF;
  background: #d9ecff;
}
.event-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.event-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}
.event-card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}
.event-card-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}
.event-card-desc {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty-hint {
  text-align: center;
  color: #c0c4cc;
  padding: 40px 0;
  font-size: 13px;
}

/* ====== 分类卡片 ====== */
.category-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 8px 0;
}
.category-card {
  display: flex;
  align-items: center;
  padding: 20px 16px;
  border: 2px solid #ebeef5;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}
.category-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.category-icon {
  font-size: 32px;
  margin-right: 14px;
  flex-shrink: 0;
}
.category-info {
  flex: 1;
  min-width: 0;
}
.category-label {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}
.category-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
.category-arrow {
  font-size: 18px;
  color: #c0c4cc;
  flex-shrink: 0;
}

/* ====== 表单步骤 ====== */
.step-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #409EFF;
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 16px;
  user-select: none;
}
.step-back:hover {
  color: #337ECC;
}
.create-form {
  margin-top: 8px;
}
</style>
