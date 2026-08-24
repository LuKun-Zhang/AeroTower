<template>
  <div id="crew-view">
    <div class="dragRectTop"></div>

    <!-- ===== 未筛选提示 ===== -->
    <div class="empty-hint" v-if="!filteredReady">
      <div class="empty-icon">&#9992;</div>
      <p>请先在「航班筛选」页面上传文件、执行筛选并点击「保存并执行排班计划」</p>
    </div>

    <!-- ===== 左侧控制面板 (1/5) ===== -->
    <template v-if="filteredReady">
    <div class="sidebar">
      <h2>机组排班 · 川航</h2>

      <div class="side-section">
        <label class="side-label">机组基地</label>
        <el-select v-model="base" size="small" filterable style="width:100%" @change="onBaseChange" placeholder="选择基地">
          <el-option label="成都" value="成都" />
          <el-option label="重庆" value="重庆" />
          <el-option label="昆明" value="昆明" />
          <el-option label="杭州" value="杭州" />
          <el-option label="绵阳" value="绵阳" />
          <el-option label="宜宾" value="宜宾" />
        </el-select>
      </div>

      <div class="side-section">
        <label class="side-label">日期</label>
        <el-select v-model="date" size="small" style="width:100%" placeholder="全部日期">
          <el-option label="全部日期" value="" />
          <el-option v-for="d in dates" :key="d" :label="d" :value="d" />
        </el-select>
      </div>

      <div class="side-section">
        <label class="side-label">角色筛选</label>
        <el-select v-model="roleFilter" size="small" style="width:100%">
          <el-option label="全部" value="" />
          <el-option label="机长" value="captain" />
          <el-option label="副驾驶" value="first_officer" />
          <el-option label="乘务长" value="purser" />
          <el-option label="乘务员" value="attendant" />
        </el-select>
      </div>

      <div class="side-section">
        <label class="side-label">搜索人员</label>
        <el-input v-model="crewSearchText" size="small" style="width:100%" placeholder="输入姓名定位机组" clearable @clear="crewSearchText=''; crewSearch=''" @keyup.enter.native="doCrewSearch" />
      </div>

      <div class="side-actions">
        <el-button size="small" @click="doCrewSearch" style="width:100%" :disabled="!crewSearchText.trim()">定位机组</el-button>
        <el-button size="small" @click="togglePanel" style="width:100%">
          {{ showPairingPanel ? '收起任务池' : '展开任务池' }} ({{ pairings.length }})
        </el-button>
        <el-button size="small" @click="showRoster = !showRoster" :disabled="crew.length === 0" style="width:100%">人员名册</el-button>
        <el-button size="small" @click="openTeamBuilder" :disabled="!hasSchedule" style="width:100%">组建机组</el-button>
        <el-button size="small" @click="showSwapPanel = true" :disabled="teamGroups.length < 2" style="width:100%">人员调换</el-button>
        <el-button size="small" @click="doExport" :disabled="crew.length === 0" :loading="exporting" style="width:100%">导出Excel</el-button>
      </div>

      <div class="side-info" v-if="report.summary">
        <p>{{ report.summary }}</p>
        <p class="side-crew-count">{{ crew.length }} 人池</p>
      </div>
    </div>

    <!-- ===== 右侧主区域 (4/5) ===== -->
    <div class="main-area">
      <!-- 上半部分：任务池 + 详情 -->
      <div class="top-area" v-if="showPairingPanel">
        <!-- 任务池列表 -->
        <div class="pairing-panel">
          <div class="pp-header">
            <span>任务池 ({{ pairings.length }} 个任务链) | 基地: {{ pairingBase }}</span>
            <span class="pp-stats" v-if="coverage">
              覆盖率 {{ coverage.coverage_pct }}%（{{ coverage.covered_flights }}/{{ coverage.total_flights }}）
              <template v-if="coverage.uncovered_flights > 0">
                未覆盖 {{ coverage.uncovered_flights }} 班
                <el-button size="mini" type="warning" @click="showUncovered = true">查看</el-button>
              </template>
            </span>
            <span class="pp-stats">
              已选 {{ checkedPairings.length }} 条
              <el-button size="mini" type="success" @click="assignSelected" :loading="assigning" :disabled="checkedPairings.length === 0">自动填充</el-button>
            </span>
          </div>
          <div class="pp-list">
            <div class="pp-item" v-for="p in displayedPairings" :key="p.pairing_id"
                 :class="{ 'pp-selected': isPairingAssigned(p.pairing_id), 'pp-active': selectedPairing === p }"
                 @click="selectedPairing = selectedPairing === p ? null : p">
              <el-checkbox size="mini" :value="checkedPairings.includes(p.pairing_id)"
                           @change="toggleCheck(p.pairing_id)"
                           @click.native.stop />
              <span class="pp-id">#{{ p.pairing_id }}</span>
              <span class="pp-days">{{ p.num_days }}天</span>
              <span class="pp-seg">{{ p.num_flights }}段</span>
              <span class="pp-range">{{ p.start_date }} ~ {{ p.end_date }}</span>
              <span class="pp-hours">{{ p.total_flight_hours }}h</span>
              <span class="pp-util">{{ (p.utilization * 100).toFixed(0) }}%</span>
              <span class="pp-cost">{{ p.cost?.toFixed(0) }}</span>
              <span class="pp-base">{{ p.base }}</span>
            </div>
            <div v-if="pairings.length > pairingLoadLimit" class="pp-load-more">
              <el-button size="mini" type="text" @click="pairingLoadLimit += 200">
                加载更多 (已显示 {{ Math.min(pairingLoadLimit, pairings.length) }} / {{ pairings.length }})
              </el-button>
            </div>
          </div>
        </div>

        <!-- 选中 pairing 的航班链详情 -->
        <div class="pairing-detail" v-if="selectedPairing">
          <div class="pd-header">
            <strong>任务链 #{{ selectedPairing.pairing_id }}</strong>
            {{ selectedPairing.start_date }} ~ {{ selectedPairing.end_date }}
            ({{ selectedPairing.num_days }}天 {{ selectedPairing.num_flights }}段
            {{ selectedPairing.total_flight_hours }}飞行小时
            {{ selectedPairing.total_duty_hours }}执勤小时)
          </div>
          <div class="pd-chain">
            <span v-for="(f, fi) in selectedPairing.flights" :key="fi" class="pd-flight">
              {{ f.date }} {{ f.flight_no }}
              <span class="pd-ac">({{ f.ac_type }})</span>
              {{ f.departure_airport }}{{ f.dep_time }}→{{ f.arrival_airport }}{{ f.arr_time }}
              <span class="pd-arrow" v-if="fi < selectedPairing.flights.length - 1">→</span>
            </span>
          </div>
        </div>

        <!-- 对比面板 -->
        <div v-if="compareData" class="compare-panel">
          <h3>机组排班对比 ({{ compareData.date || '全部' }})</h3>
          <table>
            <tr><th>指标</th><th>全机场</th><th>{{ compareData.airport || '筛选' }}</th></tr>
            <tr><td>已排班人数</td><td>{{ compareData.full.assigned }}</td><td>{{ compareData.filtered.assigned }}</td></tr>
            <tr><td>违规数</td><td :class="{ 'has-conflict': compareData.full.initial_violations > 0 }">{{ compareData.full.violations }}</td><td :class="{ 'has-conflict': compareData.filtered.violations > 0 }">{{ compareData.filtered.violations }}</td></tr>
          </table>
        </div>
      </div>

      <!-- 未覆盖航班弹窗 -->
      <el-dialog
        title="未排班航班清单"
        :visible.sync="showUncovered"
        width="700px"
        append-to-body>
        <div v-if="uncoveredFlights.length === 0" style="color:#aaa;text-align:center;padding:20px;">
          所有航班均已排班
        </div>
        <el-table v-else :data="uncoveredFlights" size="mini" max-height="400" stripe>
          <el-table-column prop="flight_no" label="航班号" width="90" />
          <el-table-column prop="date" label="日期" width="100" />
          <el-table-column label="出发" width="120">
            <template slot-scope="s">{{ s.row.departure_airport }} {{ s.row.dep_time }}</template>
          </el-table-column>
          <el-table-column label="到达" width="120">
            <template slot-scope="s">{{ s.row.arrival_airport }} {{ s.row.arr_time }}</template>
          </el-table-column>
          <el-table-column prop="ac_type" label="机型" width="70" />
          <el-table-column label="原因" min-width="140">
            <template slot-scope="s">
              <el-tag size="mini" type="info">无法形成闭环</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <span slot="footer" class="dialog-footer">
          <el-button size="small" @click="showUncovered = false">关闭</el-button>
        </span>
      </el-dialog>

      <!-- 下半部分：排班甘特图 -->
      <div class="gantt-container" v-if="crewRows.length > 0">
        <div class="gantt-body">
          <template v-for="(group, gi) in crewRows">
            <div class="date-header" v-if="group.is_team_header && (gi === 0 || crewRows[gi-1].team_id !== group.team_id)" :key="'th-'+gi"
                 :class="{ 'sub-team-header': group.is_substitute_team }">
              <span class="team-header">
                <span class="team-icon">{{ group.is_substitute_team ? '&#x1F504;' : '&#x2708;' }}</span>
                机组 {{ group.members.join(' / ') }}
                <span class="team-badge" :class="{ 'team-badge-sub': group.is_substitute_team }">{{ group.team_label }}</span>
              </span>
            </div>
            <div class="date-header" v-else-if="!group.is_team_header && (gi === 0 || group.date !== crewRows[gi-1].date)" :key="'dh-'+gi">
              <span class="date-tag">{{ group.date }}</span>
            </div>
            <template v-if="!group.is_team_header">
              <div class="crew-row" :key="group.row_key" :class="{ 'row-absent': group.is_absent, 'row-substitute': group.is_substitute_mark, 'row-violation': group.has_violations }">
                <div class="crew-label">
                  <span class="crew-name">{{ group.name }}</span>
                  <span class="role-tag" :class="group.role">{{ group.role_label }}</span>
                  <span class="sub-tag tag-absent" v-if="group.is_absent">请假</span>
                  <span class="sub-tag tag-sub" v-if="group.is_substitute_mark">替换</span>
                </div>
                <div class="crew-timeline" :style="{ minWidth: timelinePx + 'px' }">
                  <div v-for="(f, fi) in group.flights" :key="fi"
                       class="block" :class="{ active: hoverBlock === f }" :style="blockStyle(f, fi)"
                       @click="onBlockClick(f, $event)">
                    <span class="blk-no">{{ f.flight_no }}</span>
                  </div>
                </div>
                <div class="crew-stats">
                  <span class="stat-val">{{ group.day_hours }}h</span>
                </div>
              </div>
            </template>
          </template>
        </div>
      </div>

      <div v-if="!loading && crew.length === 0" class="empty-tip">切换基地或日期查看排班结果</div>
    </div>

    <!-- 悬浮航班详情弹窗 -->
    <div class="hover-popup" v-if="hoverBlock" :style="popupStyle" @click.stop>
      <div class="hp-close" @click="hoverBlock = null">✕</div>
      <div class="hd-row"><span class="hd-label">航班号</span><strong>{{ hoverBlock.flight_no }}</strong></div>
      <div class="hd-row"><span class="hd-label">日期</span>{{ hoverBlock.date }}</div>
      <div class="hd-row"><span class="hd-label">航线</span>{{ hoverBlock.from }} → {{ hoverBlock.to }}</div>
      <div class="hd-row"><span class="hd-label">执勤时段</span>{{ fmtTime(hoverBlock.duty_start_min) }} ~ {{ fmtTime(hoverBlock.duty_end_min) }}</div>
      <div class="hd-row"><span class="hd-label">执勤时长</span>{{ hoverBlock.duty_end_min - hoverBlock.duty_start_min }} 分钟</div>
    </div>

    <!-- 人员名册弹窗 -->
    <div class="roster-overlay" v-if="showRoster" @click.self="showRoster = false">
      <div class="roster-panel">
        <div class="roster-header">
          <h3>机组人员名册</h3>
          <el-select v-model="rosterBaseFilter" size="small" style="width:110px" clearable placeholder="基地筛选">
            <el-option v-for="b in rosterBases" :key="b" :label="b" :value="b" />
          </el-select>
          <span class="roster-count">共 {{ filteredRoster.length }} 人</span>
          <span class="roster-close" @click="showRoster = false">✕</span>
        </div>
        <div class="roster-body">
          <table class="roster-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>姓名</th>
                <th>职务</th>
                <th>基地</th>
                <th>航司</th>
                <th>资质</th>
                <th>今日飞行(h)</th>
                <th>总飞行(h)</th>
                <th>7天飞行(h)</th>
                <th>30天飞行(h)</th>
                <th>最小休息(h)</th>
                <th>任务数</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in filteredRoster" :key="c.crew_id" :class="{ 'roster-violation': c.violations && c.violations.length > 0 }">
                <td>{{ c.crew_id }}</td>
                <td><strong>{{ c.name }}</strong></td>
                <td><span class="role-tag" :class="c.role">{{ c.role_label }}</span></td>
                <td>{{ c.base }}</td>
                <td>{{ c.airline }}</td>
                <td>{{ (c.qualifications || []).join(', ') }}</td>
                <td>{{ c.daily_flight_hours }}h</td>
                <td>{{ c.total_flight_hours }}h</td>
                <td>{{ c.seven_day_flight_hours }}h</td>
                <td>{{ c.thirty_day_flight_hours }}h</td>
                <td>{{ c.min_rest_hours >= 0 ? c.min_rest_hours + 'h' : '-' }}</td>
                <td>{{ c.flight_count }}</td>
                <td>
                  <span v-if="c.violations && c.violations.length > 0" class="roster-status violation" :title="c.violations.join('&#10;')">{{ c.violations.length }}项违规</span>
                  <span v-else-if="c.flight_count > 0" class="roster-status active">合规</span>
                  <span v-else class="roster-status idle">空闲</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 组建机组弹窗 -->
    <div class="roster-overlay" v-if="showTeamBuilder" @click.self="showTeamBuilder = false">
      <div class="roster-panel" style="max-width: 520px">
        <div class="roster-header">
          <h3>组建机组</h3>
          <span class="roster-close" @click="showTeamBuilder = false">✕</span>
        </div>
        <div v-if="showTeamBuilder" class="roster-body">
          <div class="team-form-group">
            <label>机长</label>
            <el-select v-model="teamMembers.captain" size="small" style="width:100%" placeholder="选择机长" filterable>
              <el-option v-for="c in teamCrewOptions.captains" :key="c.crew_id" :label="`${c.name} (${c.flight_count}班)`" :value="c.crew_id" />
            </el-select>
          </div>
          <div class="team-form-group">
            <label>副驾驶</label>
            <el-select v-model="teamMembers.officer" size="small" style="width:100%" placeholder="选择副驾驶" filterable>
              <el-option v-for="c in teamCrewOptions.officers" :key="c.crew_id" :label="`${c.name} (${c.flight_count}班)`" :value="c.crew_id" />
            </el-select>
          </div>
          <div class="team-form-group">
            <label>乘务长</label>
            <el-select v-model="teamMembers.purser" size="small" style="width:100%" placeholder="选择乘务长" filterable>
              <el-option v-for="c in teamCrewOptions.pursers" :key="c.crew_id" :label="`${c.name} (${c.flight_count}班)`" :value="c.crew_id" />
            </el-select>
          </div>
          <div class="team-form-group">
            <label>乘务员 ①</label>
            <el-select v-model="teamMembers.attendant1" size="small" style="width:100%" placeholder="选择乘务员" filterable>
              <el-option v-for="c in teamCrewOptions.attendants" :key="c.crew_id" :label="`${c.name} (${c.flight_count}班)`" :value="c.crew_id" />
            </el-select>
          </div>
          <div class="team-form-group">
            <label>乘务员 ②</label>
            <el-select v-model="teamMembers.attendant2" size="small" style="width:100%" placeholder="选择乘务员" filterable>
              <el-option v-for="c in teamCrewOptions.attendants" :key="c.crew_id" :label="`${c.name} (${c.flight_count}班)`" :value="c.crew_id" />
            </el-select>
          </div>

          <!-- 分配模式切换 -->
          <div class="team-form-group">
            <el-radio-group v-model="teamMembers.assignMode" size="mini" @change="onAssignModeChange">
              <el-radio-button label="pairing">分配任务链</el-radio-button>
              <el-radio-button label="flight">分配单个航班</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 任务链模式 -->
          <template v-if="teamMembers.assignMode === 'pairing'">
            <div class="team-form-group">
              <label>任务链</label>
              <el-select v-model="teamMembers.pairingId" size="small" style="width:100%" placeholder="选择任务链" filterable>
                <el-option v-for="p in teamPairingOptions" :key="p.pairing_id" :label="`#${p.pairing_id} ${p.num_flights}段 ${p.num_days}天 ${p.total_flight_hours}h`" :value="p.pairing_id" />
              </el-select>
            </div>
          </template>

          <!-- 单航班模式 -->
          <template v-if="teamMembers.assignMode === 'flight'">
            <div class="team-form-group">
              <label>日期</label>
              <el-select v-model="teamDateFilter" size="small" style="width:100%" placeholder="选日期" @change="loadTeamFlights">
                <el-option v-for="d in teamDates" :key="d" :label="d" :value="d" />
              </el-select>
            </div>
            <div class="team-form-group">
              <label>航班 ({{ teamFlightOptions.length }} 个)</label>
              <el-select v-model="teamMembers.flightId" size="small" style="width:100%" placeholder="选择航班" filterable>
                <el-option v-for="f in teamFlightOptions" :key="f.flight_id" :label="`${f.flight_no} ${f.from}→${f.to} ${f.date}`" :value="f.flight_id" />
              </el-select>
            </div>
          </template>

          <div class="team-form-actions">
            <el-button size="small" @click="showTeamBuilder = false">取消</el-button>
            <el-button size="small" type="primary" :loading="teamAssigning" @click="doAssignTeam">指派给机组</el-button>
          </div>
          <div v-if="teamResult" class="team-result" :class="{ 'team-err': teamResult.code !== 0 }">
            {{ teamResult.msg }}
          </div>
        </div>
      </div>
    </div>
    </template>

    <!-- 人员调换弹窗 -->
    <div class="roster-overlay" v-if="showSwapPanel" @click.self="showSwapPanel = false">
      <div class="roster-panel" style="max-width: 420px">
        <div class="roster-header">
          <h3>人员调换</h3>
          <span class="roster-close" @click="showSwapPanel = false">✕</span>
        </div>
        <div class="roster-body" v-if="showSwapPanel">
          <p style="color:#888; font-size:12px; margin-bottom:16px">交换两个团队中同岗位人员，不改变排班结构</p>
          <div class="team-form-group">
            <label>团队 A</label>
            <el-select v-model="swap.teamA" size="small" style="width:100%" placeholder="选择团队A">
              <el-option v-for="g in teamGroups" :key="'a'+g.team_id"
                :label="`机组${g.team_id} (${g.captain})`" :value="g.team_id" />
            </el-select>
          </div>
          <div class="team-form-group">
            <label>团队 B</label>
            <el-select v-model="swap.teamB" size="small" style="width:100%" placeholder="选择团队B">
              <el-option v-for="g in teamGroups" :key="'b'+g.team_id"
                :label="`机组${g.team_id} (${g.captain})`" :value="g.team_id"
                :disabled="g.team_id === swap.teamA" />
            </el-select>
          </div>
          <div class="team-form-group">
            <label>岗位</label>
            <el-select v-model="swap.role" size="small" style="width:100%" placeholder="选择岗位">
              <el-option label="机长" value="captain" />
              <el-option label="副驾驶" value="first_officer" />
              <el-option label="乘务长" value="purser" />
              <el-option label="乘务员①" value="attendant:0" />
              <el-option label="乘务员②" value="attendant:1" />
            </el-select>
          </div>
          <div v-if="swapPreview" class="swap-preview">
            <div class="swap-row">
              <div class="swap-card">
                <span class="swap-label">机组{{ swap.teamA }}</span>
                <strong>{{ swapPreview.nameA }}</strong>
              </div>
              <span class="swap-arrow">⇄</span>
              <div class="swap-card">
                <span class="swap-label">机组{{ swap.teamB }}</span>
                <strong>{{ swapPreview.nameB }}</strong>
              </div>
            </div>
          </div>
          <div style="margin-top:16px; display:flex; gap:8px; justify-content:flex-end">
            <el-button size="small" @click="showSwapPanel = false">取消</el-button>
            <el-button size="small" type="primary" :disabled="!canSwap" :loading="swap.loading" @click="doSwap">调换</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import api from '@/api'

export default {
  data() {
    return {
      filteredReady: false,
      base: '成都',
      date: '',
      dates: [],
      crewSearch: '',
      crewSearchText: '',
      crew: [],
      pairings: [],
      pairingLoadLimit: 200,   // 任务池分页加载：初始 200，点击"加载更多"+200
      assignedPairings: [],
      uncoveredIds: [],
      showUncovered: false,
      coverage: null,
      showPairingPanel: true,
      showRoster: false,
      rosterBaseFilter: '',
      selectedPairing: null,
      checkedPairings: [],
      assigning: false,
      report: {},
      hoverBlock: null,
      popupX: 0,
      popupY: 0,
      loading: false,
      roleFilter: '',
      startHour: 5,
      pxPerMin: 0.4,
      // 组建机组
      showTeamBuilder: false,
      teamMembers: { captain: null, officer: null, purser: null, attendant1: null, attendant2: null, pairingId: null, flightId: null, assignMode: 'pairing' },
      teamAssigning: false,
      teamResult: null,
      teamDateFilter: '',
      teamDates: [],
      // 导出
      exporting: false,
      // 团队
      teamGroups: [],
      // 组建机组航班选项
      teamFlightOptions: [],
      // 人员调换
      showSwapPanel: false,
      swap: { teamA: null, teamB: null, role: '', loading: false },
      // 替班信息
      substitutions: [],
      pollTimer: null,
    }
  },
  computed: {
    // 请假信息：{ 人员名 → Set<日期> }
    absentInfo() {
      const info = {}
      if (!this.substitutions.length) return info
      const subTeam = this.teamGroups.find(tg => tg.is_substitute)
      if (!subTeam) return info

      // 请假人员名（从 old_value 提取）
      const absentNames = new Set()
      for (const s of this.substitutions) {
        if (s.old_value) absentNames.add(s.old_value.split('(')[0].trim())
      }

      // 从替班航班中提取请假日期
      const subFlightIds = new Set()
      for (const s of this.substitutions) {
        if (s.flight_id) subFlightIds.add(String(s.flight_id))
      }
      const dates = new Set()
      const subCap = this.displayCrew.find(c => c.name === subTeam.captain && c.role === 'captain')
      if (subCap) {
        for (const f of subCap.assigned_flights) {
          if (subFlightIds.has(String(f.flight_id || '')) && f.date) {
            dates.add(f.date)
          }
        }
      }

      for (const name of absentNames) {
        info[name] = dates
      }
      return info
    },
    // 替班信息：{ 人员名 → Set<日期> }
    substituteInfo() {
      const info = {}
      if (!this.substitutions.length) return info
      const subTeam = this.teamGroups.find(tg => tg.is_substitute)
      if (!subTeam) return info

      const subFlightIds = new Set()
      for (const s of this.substitutions) {
        if (s.flight_id) subFlightIds.add(String(s.flight_id))
      }
      const dates = new Set()
      const subCap = this.displayCrew.find(c => c.name === subTeam.captain && c.role === 'captain')
      if (subCap) {
        for (const f of subCap.assigned_flights) {
          if (subFlightIds.has(String(f.flight_id || '')) && f.date) {
            dates.add(f.date)
          }
        }
      }

      if (dates.size > 0) {
        info[subTeam.captain] = dates
      }
      return info
    },
    uncoveredFlights() {
      // 兼容旧格式 (array of IDs) 和新格式 (array of objects)
      if (!this.uncoveredIds || this.uncoveredIds.length === 0) return []
      if (typeof this.uncoveredIds[0] === 'object') return this.uncoveredIds
      // 旧格式：尝试从 pairings 数据中查找航班详情
      const map = {}
      for (const p of this.pairings) {
        for (const f of p.flights) {
          map[f.flight_id] = f
        }
      }
      return this.uncoveredIds.map(id => map[id] || { flight_id: id, flight_no: `ID:${id}`, date: '?', departure_airport: '?', arrival_airport: '?', dep_time: '?', arr_time: '?', ac_type: '?' })
    },
    assigned_team() { return null },
    hasSchedule() {
      return this.crew.length > 0
    },
    canSwap() {
      return this.swap.teamA != null && this.swap.teamB != null &&
             this.swap.teamA !== this.swap.teamB && this.swap.role
    },
    swapPreview() {
      if (!this.canSwap) return null
      const gA = this.teamGroups.find(g => g.team_id === this.swap.teamA)
      const gB = this.teamGroups.find(g => g.team_id === this.swap.teamB)
      if (!gA || !gB) return null
      const getName = (group, roleKey) => {
        if (roleKey === 'captain') return group.captain
        if (roleKey === 'first_officer') return group.officer
        if (roleKey === 'purser') return group.purser
        if (roleKey.startsWith('attendant')) {
          const idArr = group.attendant_ids || []
          const nameArr = group.attendants || []
          const idx = roleKey === 'attendant:1' ? 1 : 0
          return nameArr[idx] || `乘务员${idx + 1}`
        }
        return '?'
      }
      if (this.swap.role.startsWith('attendant')) {
        const roleKey = this.swap.role
        return { nameA: getName(gA, roleKey), nameB: getName(gB, roleKey) }
      }
      return { nameA: getName(gA, this.swap.role), nameB: getName(gB, this.swap.role) }
    },
    displayCrew() {
      let list = this.crew
      // 按姓名搜索 → 找出该人员所属所有团队ID，显示整个团队
      if (this.crewSearch.trim()) {
        const kw = this.crewSearch.trim()
        const matched = this.crew.filter(c => c.name.includes(kw))
        if (matched.length === 0) return []
        const teamIds = new Set(matched.map(c => c.team_id).filter(tid => tid != null && tid >= 0))
        // 显示匹配人员 + 同团队成员
        list = this.crew.filter(c => {
          if (matched.includes(c)) return true
          return c.team_id != null && c.team_id >= 0 && teamIds.has(c.team_id)
        })
      }
      if (this.roleFilter) {
        list = list.filter(c => c.role === this.roleFilter)
      }
      return list.filter(c => c.assigned_flights.length > 0)
    },
    crewRows() {
      const rows = []
      // 建立 team_id → 人员列表 的映射
      const teamMap = {}  // team_id → [crew_members]
      for (const c of this.displayCrew) {
        const tid = c.team_id ?? -1
        if (!teamMap[tid]) teamMap[tid] = []
        teamMap[tid].push(c)
      }

      // 替班信息：航班ID集合、替班日期集合、替班机长名、替班成员名
      const subFlightIds = new Set()
      const subDates = new Set()
      for (const s of this.substitutions) {
        const fid = s.flight_id
        if (fid) subFlightIds.add(String(fid))
      }
      const subTeam = this.teamGroups.find(tg => tg.is_substitute)
      const subCaptainName = subTeam ? subTeam.captain : ''

      // 收集替班日期（从替班机长的替班航班中提取）
      if (subCaptainName && subFlightIds.size > 0) {
        const subCap = this.displayCrew.find(c => c.name === subCaptainName && c.role === 'captain')
        if (subCap) {
          for (const f of subCap.assigned_flights) {
            if (subFlightIds.has(String(f.flight_id || '')) && f.date) {
              subDates.add(f.date)
            }
          }
        }
      }

      // 角色排序
      const roleOrder = { captain: 0, first_officer: 1, purser: 2, attendant: 3 }

      // 按共飞航班数排序团队（team_groups 已排序）
      const teamOrder = this.teamGroups.map(g => g.team_id)
      const sortedTeamIds = Object.keys(teamMap).map(Number).sort((a, b) => {
        const ai = teamOrder.indexOf(a)
        const bi = teamOrder.indexOf(b)
        if (ai >= 0 && bi >= 0) return ai - bi
        if (ai >= 0) return -1
        if (bi >= 0) return 1
        return a - b
      })

      for (const tid of sortedTeamIds) {
        const members = teamMap[tid].sort((a, b) => {
          const ra = roleOrder[a.role] ?? 4
          const rb = roleOrder[b.role] ?? 4
          return ra - rb
        })

        // 团队信息行
        const tg = this.teamGroups.find(g => g.team_id === tid)
        const isSubTeam = tg && tg.is_substitute
        const subFor = tg ? tg.substitute_for : ''
        const teamLabel = tg
          ? (isSubTeam
              ? `${tg.shared_flights}班 替班 (${tg.captain}→${subFor})`
              : `${tg.shared_flights}班 共飞`)
          : (members.length >= 5 ? '自动配对' : '散兵')

        rows.push({
          row_key: `team-${tid}`,
          is_team_header: true,
          team_id: tid,
          team_label: teamLabel,
          is_substitute_team: isSubTeam,
          substitute_for: subFor,
          members: members.map(m => m.name),
        })

        // 队员行
        for (const c of members) {
          // 替班机长：从原团队中过滤掉替班航班
          let flights = c.assigned_flights
          if (subFlightIds.size > 0 && c.role === 'captain' && c.name === subCaptainName) {
            flights = flights.filter(f => !subFlightIds.has(String(f.flight_id || '')))
          }

          const byDate = {}
          for (const f of flights) {
            const d = f.date
            if (!byDate[d]) {
              byDate[d] = { date: d, flights: [], totalSpan: 0 }
            }
            byDate[d].flights.push(f)
            byDate[d].totalSpan += (f.duty_end_min - f.duty_start_min)
          }

          // 请假人员：为无航班的请假日期补充空行
          const absentDates = this.absentInfo[c.name]
          if (absentDates && absentDates.size > 0) {
            for (const ad of absentDates) {
              if (!byDate[ad]) {
                byDate[ad] = { date: ad, flights: [], totalSpan: 0 }
              }
            }
          }

          const dates = Object.keys(byDate).sort()
          for (const d of dates) {
            const h = byDate[d].totalSpan / 60
            const isAbsentDate = absentDates && absentDates.has(d)
            // 替班机长在原团队不显示"替换"标签，仅在替班组显示
            rows.push({
              row_key: `${c.crew_id}-${d}`,
              crew_id: c.crew_id,
              name: c.name,
              role: c.role,
              role_label: c.role_label,
              date: d,
              flights: byDate[d].flights,
              day_hours: Math.round(h * 10) / 10,
              is_team_header: false,
              is_absent: isAbsentDate,
              is_substitute_mark: false,
            })
          }
        }
      }

      // 替班组：显示替班航班（替班机长替班航班 + 替班成员替班日期航班）
      if (subTeam && subDates.size > 0 && subCaptainName) {
        // 按角色排序替班成员
        const subMemberOrder = [
          { name: subTeam.captain, role: 'captain' },
          { name: subTeam.officer, role: 'first_officer' },
          { name: subTeam.purser, role: 'purser' },
          ...(subTeam.attendants || []).map(n => ({ name: n, role: 'attendant' }))
        ]

        // 替班团队头部
        rows.push({
          row_key: `team-${subTeam.team_id}`,
          is_team_header: true,
          team_id: subTeam.team_id,
          team_label: `${subTeam.shared_flights}班 替班 (${subTeam.captain}→${subTeam.substitute_for})`,
          is_substitute_team: true,
          substitute_for: subTeam.substitute_for,
          members: subMemberOrder.map(m => m.name),
        })

        // 每个替班成员在替班日期的航班
        for (const sm of subMemberOrder) {
          const crew = this.displayCrew.find(c => c.name === sm.name)
          if (!crew) continue

          // 收集该成员在替班日期的航班
          const byDate = {}
          for (const f of crew.assigned_flights) {
            const d = f.date
            if (!d || !subDates.has(d)) continue
            // 如果是替班机长，只取替班航班；其他成员取所有替班日期航班
            if (sm.role === 'captain' && !subFlightIds.has(String(f.flight_id || ''))) continue
            if (!byDate[d]) {
              byDate[d] = { date: d, flights: [], totalSpan: 0 }
            }
            byDate[d].flights.push(f)
            byDate[d].totalSpan += (f.duty_end_min - f.duty_start_min)
          }
          const dates = Object.keys(byDate).sort()
          for (const d of dates) {
            const h = byDate[d].totalSpan / 60
            rows.push({
              row_key: `sub-${crew.crew_id}-${d}`,
              crew_id: crew.crew_id,
              name: crew.name,
              role: crew.role,
              role_label: crew.role_label,
              date: d,
              flights: byDate[d].flights,
              day_hours: Math.round(h * 10) / 10,
              is_team_header: false,
              is_absent: (this.absentInfo[crew.name] || new Set()).has(d),
              is_substitute_mark: (this.substituteInfo[crew.name] || new Set()).has(d),
            })
          }
        }


      }

      // CCAR-121 违规检测：为每个 crew 行标注违规信息
      const violationMap = {}
      for (const c of this.displayCrew) {
        if (c.violations && c.violations.length > 0) {
          violationMap[c.crew_id] = c.violations
        }
      }
      for (const row of rows) {
        if (!row.is_team_header && row.crew_id && violationMap[row.crew_id]) {
          row.has_violations = true
          row.violations = violationMap[row.crew_id]
        }
      }

      return rows
    },
    timelinePx() {
      return (24 - this.startHour) * 60 * this.pxPerMin
    },
    popupStyle() {
      return {
        left: this.popupX + 'px',
        top: this.popupY + 'px',
      }
    },
    pairingBase() {
      const bases = [...new Set(this.pairings.map(p => p.base))]
      return bases.join(', ') || '--'
    },
    rosterBases() {
      return [...new Set(this.crew.map(c => c.base).filter(Boolean))].sort()
    },
    filteredRoster() {
      let list = this.crew
      if (this.rosterBaseFilter) {
        list = list.filter(c => c.base === this.rosterBaseFilter)
      }
      return list.sort((a, b) => {
        const roleOrder = { captain: 0, first_officer: 1, purser: 2, attendant: 3 }
        return (roleOrder[a.role] ?? 4) - (roleOrder[b.role] ?? 4)
      })
    },
    // 组建机组：人员选项
    teamCrewOptions() {
      const byRole = (role) => this.crew.filter(c => c.role === role)
      return {
        captains: byRole('captain'),
        officers: byRole('first_officer'),
        pursers: byRole('purser'),
        attendants: byRole('attendant'),
      }
    },
    // 组建机组：任务链选项
    teamPairingOptions() {
      return this.pairings
    },
    displayedPairings() {
      return this.pairings.slice(0, this.pairingLoadLimit)
    },
  },
  watch: {
    base() { this.resetDisplay(); this.doSchedule() },
    date() { this.resetDisplay(); this.doSchedule() },
    pairings() { this.pairingLoadLimit = 200 },
  },
  methods: {
    // 辅助：检查值是否未选择（null/undefined/空字符串，0是合法值）
    isNotSelected(v) {
      return v === null || v === undefined || v === ''
    },
    _init() {
      this.checkFiltered().then(() => {
        if (this.filteredReady) {
          this.doSchedule()
        }
      })
    },
    startPolling() {
      this.stopPolling()
      this.pollTimer = setInterval(async () => {
        try {
          const data = await api.getCrewSubstitutions()
          const subs = data.substitutions || []
          if (subs.length !== this.substitutions.length) {
            this.substitutions = subs
          }
        } catch (e) {
          // 忽略轮询错误
        }
      }, 5000)
    },
    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },
    async checkFiltered() {
      try {
        const resp = await fetch('/api/flights/status')
        const json = await resp.json()
        this.filteredReady = json.data && json.data.filtered_mode
      } catch (e) {
        this.filteredReady = false
      }
    },
    resetDisplay() {
      this.pairings = []
      this.assignedPairings = []
      this.checkedPairings = []
      this.uncoveredIds = []
      this.coverage = null
      this.selectedPairing = null
      this.compareData = null
      this.hoverBlock = null
    },
    doCrewSearch() {
      this.crewSearch = this.crewSearchText
    },
    async doSchedule() {
      this.loading = true
      this.compareData = null
      this.resetDisplay()
      try {
        const a = this.base || null
        const d = this.date || null
        // 先执行排班（后端会在非分析模式下清除过期替班数据），再获取替班信息
        const result = await api.scheduleCrew(a, d, 'chain')
        let subData = { substitutions: [] }
        try {
          subData = await api.getCrewSubstitutions()
        } catch (e) {
          // 忽略获取替班数据失败
        }
        this.crew = result.crew || []
        this.report = result.report || {}
        this.dates = result.dates || []
        this.teamGroups = result.team_groups || []
        this.pairings = result.pairings || []
        this.assignedPairings = result.assigned_pairings || []
        this.uncoveredIds = result.uncovered_flights || []
        this.coverage = result.coverage || null
        this.substitutions = subData.substitutions || []
        this.showPairingPanel = this.pairings.length > 0
        this.checkedPairings = this.assignedPairings.map(a => a.pairing_id)
        const subInfo = this.substitutions.length > 0 ? ` (替班${this.substitutions.length}人)` : ''
        this.$message.success(
          `机组排班: ${this.crew.length} 人, ${this.pairings.length} 条任务链${subInfo} (覆盖率 ${this.coverage?.coverage_pct ?? '?'}%)`
        )
        // 如有替班数据，开启轮询自动刷新
        if (this.substitutions.length > 0 && !this.pollTimer) {
          this.startPolling()
        }
      } catch (e) {
        this.$message.error('排班失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },
    isPairingAssigned(pid) {
      return this.assignedPairings.some(a => a.pairing_id === pid)
    },
    togglePanel() {
      this.showPairingPanel = !this.showPairingPanel
      this.selectedPairing = null
    },
    toggleCheck(pid) {
      const idx = this.checkedPairings.indexOf(pid)
      if (idx >= 0) {
        this.checkedPairings.splice(idx, 1)
      } else {
        this.checkedPairings.push(pid)
      }
    },
    async assignSelected() {
      if (this.checkedPairings.length === 0) return
      this.assigning = true
      this.compareData = null
      try {
        const a = this.base || null
        const result = await api.assignPairings(a, null, this.checkedPairings)
        this.crew = result.crew || []
        this.report = result.report || {}
        this.dates = result.dates || []
        this.teamGroups = result.team_groups || []
        this.pairings = result.pairings || []
        this.assignedPairings = result.assigned_pairings || []
        this.uncoveredIds = result.uncovered_flights || []
        this.coverage = result.coverage || null
        this.checkedPairings = this.assignedPairings.map(a => a.pairing_id)
        this.$message.success(
          `手动 ${this.assignedPairings.length} 条 + 自动填充, ${this.uncoveredIds.length} 航班未覆盖 (${this.coverage?.coverage_pct ?? '?'}%)`
        )
      } catch (e) {
        this.$message.error('调整失败: ' + e.message)
      } finally {
        this.assigning = false
      }
    },
    onBaseChange() {
      this.date = ''
    },
    onBlockClick(f, event) {
      if (this.hoverBlock === f) {
        this.hoverBlock = null
      } else {
        this.hoverBlock = f
        const rect = event.currentTarget.getBoundingClientRect()
        const container = this.$el.querySelector('.gantt-container')
        const cRect = container ? container.getBoundingClientRect() : { left: 0, top: 0 }
        this.popupX = rect.left - cRect.left + rect.width + 8
        this.popupY = rect.top - cRect.top
      }
    },
    fmtTime(minVal) {
      const m = minVal % 1440
      const h = Math.floor(m / 60)
      const mi = m % 60
      return `${h}:${mi.toString().padStart(2, '0')}`
    },
    blockStyle(f, idx) {
      const dayMin = f.duty_start_min % 1440
      const baseMin = dayMin < this.startHour * 60 ? dayMin + 1440 : dayMin
      const left = (baseMin - this.startHour * 60) * this.pxPerMin
      const endDayMin = f.duty_end_min % 1440
      const endBaseMin = endDayMin < this.startHour * 60 ? endDayMin + 1440 : endDayMin
      const width = Math.max(20, (endBaseMin - baseMin) * this.pxPerMin)
      const hues = [200, 340, 140, 40, 270, 170, 80, 220, 320, 50]
      const hue = hues[idx % hues.length]
      return {
        left: Math.max(0, left) + 'px',
        width: width + 'px',
        background: `hsla(${hue}, 55%, 52%, 0.7)`,
      }
    },
    // ========== 组建机组 ==========
    async openTeamBuilder() {
      this.teamMembers = { captain: null, officer: null, purser: null, attendant1: null, attendant2: null, pairingId: null, flightId: null, assignMode: 'pairing' }
      this.teamResult = null
      this.teamDateFilter = ''
      this.teamDates = this.dates || []
      this.teamFlightOptions = []
      // 如果没有任务链数据，先获取（不重新跑排班）
      if (this.pairings.length === 0) {
        try {
          const res = await api.getPairings(this.base || null)
          if (res && res.pairings) {
            this.pairings = res.pairings
          }
        } catch (e) {
          // 忽略错误
        }
      }
      this.teamMembers.assignMode = this.pairings.length > 0 ? 'pairing' : 'flight'
      this.loadTeamFlights()
      this.showTeamBuilder = true
    },
    onAssignModeChange() {
      this.teamMembers.pairingId = null
      this.teamMembers.flightId = null
      if (this.teamMembers.assignMode === 'flight') {
        this.teamDates = this.dates || []
        this.loadTeamFlights()
      }
    },
    loadTeamFlights() {
      const seen = {}
      const list = []
      for (const c of this.crew) {
        for (const a of c.assigned_flights) {
          if (!seen[a.flight_id]) {
            seen[a.flight_id] = true
            if (this.teamDateFilter && a.date !== this.teamDateFilter) continue
            list.push(a)
          }
        }
      }
      list.sort((a, b) => (a.date + a.flight_no).localeCompare(b.date + b.flight_no))
      this.teamFlightOptions = list
    },
    async doAssignTeam() {
      const tm = this.teamMembers
      if (this.isNotSelected(tm.captain) || this.isNotSelected(tm.officer) ||
          this.isNotSelected(tm.purser) || this.isNotSelected(tm.attendant1) ||
          this.isNotSelected(tm.attendant2)) {
        this.teamResult = { code: 1, msg: '请完整选择所有角色' }
        return
      }
      if (tm.attendant1 === tm.attendant2) {
        this.teamResult = { code: 1, msg: '两名乘务员不能是同一人' }
        return
      }
      if (tm.assignMode === 'pairing') {
        if (this.isNotSelected(tm.pairingId)) {
          this.teamResult = { code: 1, msg: '请选择任务链' }
          return
        }
      } else {
        if (this.isNotSelected(tm.flightId)) {
          this.teamResult = { code: 1, msg: '请选择航班' }
          return
        }
      }
      this.teamAssigning = true
      this.teamResult = null
      try {
        // 获取选中人员的名字
        const findName = (list, id) => {
          if (id === null || id === undefined || id === '') return ''
          const found = list.find(c => c.crew_id === id)
          return found ? found.name : ''
        }
        const capName = findName(this.teamCrewOptions.captains, tm.captain)
        const offName = findName(this.teamCrewOptions.officers, tm.officer)
        const purName = findName(this.teamCrewOptions.pursers, tm.purser)
        const att1Name = findName(this.teamCrewOptions.attendants, tm.attendant1)
        const att2Name = findName(this.teamCrewOptions.attendants, tm.attendant2)

        let result
        if (tm.assignMode === 'pairing') {
          result = await api.assignPairingToTeam(
            this.base || null, tm.pairingId,
            tm.captain, tm.officer, tm.purser,
            [tm.attendant1, tm.attendant2],
            capName, offName, purName, att1Name, att2Name
          )
        } else {
          result = await api.manualAssignFlight(
            this.base || null, tm.flightId,
            tm.captain, tm.officer, tm.purser,
            [tm.attendant1, tm.attendant2]
          )
        }
        if (result) {
          this.crew = result.crew || []
          this.report = result.report || {}
          this.teamGroups = result.team_groups || []
          this.pairings = result.pairings || []
          this.assignedPairings = result.assigned_pairings || []
          this.assigned_team = result.assigned_team
          this.uncoveredIds = result.uncovered_flights || []
          this.coverage = result.coverage || null
          this.checkedPairings = this.assignedPairings.map(a => a.pairing_id)
          this.teamResult = {
            code: 0,
            msg: `指派成功! ${result.assigned_team.captain}机组 → pairing#${result.assigned_team.pairing_id} (${result.assigned_team.first_officer}/${result.assigned_team.purser}/${result.assigned_team.attendants?.join('/')})`
          }
          this.$message.success(`机组指派成功 (${this.assignedPairings.length}条任务链, 覆盖率${this.coverage?.coverage_pct ?? '?'}%)`)
        }
      } catch (e) {
        this.teamResult = { code: 1, msg: '指派失败: ' + e.message }
      } finally {
        this.teamAssigning = false
      }
    },
    // 人员调换
     async doSwap() {
        if (!this.canSwap) return
        this.swap.loading = true
        try {
          const parts = this.swap.role.split(':')
          const role = parts[0]
          const attIdx = parts.length > 1 ? parseInt(parts[1]) : 0
          const result = await api.swapCrewMembers(this.swap.teamA, this.swap.teamB, role, attIdx)
          this.teamGroups = result.team_groups || []
          if (result.crew) {
            this.crew = result.crew
          }
          this.$message.success(result.msg || '调换成功')
        } catch (e) {
          this.$message.error('调换失败: ' + e.message)
        } finally {
          this.swap.loading = false
        }
      },
    // 导出 Excel
    async doExport() {
      this.exporting = true
      try {
        await api.exportCrewSchedule(this.base || null, this.date || null, this.airline || null)
        this.$message.success('排班表已下载')
      } catch (e) {
        this.$message.error('导出失败: ' + e.message)
      } finally {
        this.exporting = false
      }
    },
  },
  mounted() { this._init() },
  activated() { this._init() },
}
</script>

<style scoped>
#crew-view {
  border: 0.5px solid rgba(255,255,255,0.2);
  position: relative;
  background: rgba(255,255,255,0.1);
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

/* ===== 左侧控制面板 (1/5) ===== */
.sidebar {
  width: 20%;
  min-width: 200px;
  max-width: 260px;
  flex-shrink: 0;
  padding: 12px 14px;
  border-right: 1px solid rgba(255,255,255,0.15);
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}
.sidebar h2 {
  font-size: 16px;
  margin: 0 0 8px;
  color: #f5d0a9;
  white-space: nowrap;
}

.side-section {
  margin-bottom: 8px;
}
.side-label {
  display: block;
  font-size: 11px;
  color: #888;
  margin-bottom: 4px;
}

.side-actions {
   display: flex;
   flex-direction: column;
   gap: 6px;
   margin-top: 8px;
   padding-top: 8px;
   border-top: 1px solid rgba(255,255,255,0.1);
 }
 .side-actions .el-button {
   justify-content: center;
 }

.side-info {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.1);
  font-size: 12px;
  color: #aaa;
  line-height: 1.6;
}
.side-info p { margin: 0; }
.side-crew-count { color: #f5d0a9; font-weight: 600; }

/* ===== 右侧主区域 (4/5) ===== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

/* 上半部分：任务池 + 详情 */
.top-area {
  flex-shrink: 0;
  max-height: 40%;
  overflow: auto;
  border-bottom: 1px solid rgba(255,255,255,0.12);
}

/* Pairing Panel */
.pairing-panel {
  flex-shrink: 0;
  max-height: 160px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.pp-header {
  padding: 6px 12px;
  font-size: 12px;
  color: #aaa;
  display: flex;
  justify-content: space-between;
  background: rgba(0,0,0,0.2);
}
.pp-stats { color: #f5d0a9; }
.pp-list {
  flex: 1;
  overflow-y: auto;
  padding: 2px 0;
}
.pp-item {
  display: flex;
  gap: 8px;
  padding: 3px 12px;
  font-size: 11px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  align-items: center;
}
.pp-item:hover { background: rgba(255,255,255,0.05); }
.pp-selected { background: rgba(43,180,243,0.1); }
.pp-active { background: rgba(43,180,243,0.2); }
.pp-id { color: #f5d0a9; font-weight: bold; min-width: 30px; }
.pp-days { color: #5b9bd5; min-width: 28px; }
.pp-seg { color: #aaa; min-width: 30px; }
.pp-range { flex: 1; color: #ccc; }
.pp-hours { color: #8c8; min-width: 36px; text-align: right; }
.pp-util { color: #aaf; min-width: 36px; text-align: right; font-size: 11px; }
.pp-cost { color: #faa; min-width: 30px; text-align: right; font-size: 11px; }
.pp-base { color: #888; font-size: 10px; }

/* Pairing Detail */
.pairing-detail {
  padding: 6px 12px;
  font-size: 12px;
  color: #ccc;
  background: rgba(0,0,0,0.2);
  flex-shrink: 0;
}
.pd-header { margin-bottom: 4px; }
.pd-header strong { color: #f5d0a9; }
.pd-chain { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; }
.pd-flight { color: #aaa; font-size: 11px; }
.pd-ac { color: #666; font-size: 10px; }
.pd-arrow { color: #5b9bd5; margin: 0 2px; }

.compare-panel {
  padding: 10px 12px;
  flex-shrink: 0;
  font-size: 12px;
}
.compare-panel h3 { font-size: 13px; margin-bottom: 6px; }
.compare-panel table { width: 100%; border-collapse: collapse; }
.compare-panel th, .compare-panel td {
  padding: 3px 8px;
  border: 1px solid rgba(255,255,255,0.15);
  text-align: center;
}
.compare-panel th { background: rgba(0,0,0,0.3); }
.has-conflict { color: #f56; font-weight: bold; }

.gantt-container {
  flex: 1;
  overflow: auto;
  padding: 4px 12px;
  min-height: 0;
  position: relative;
}
.gantt-body { min-width: 600px; }

.crew-row {
  display: flex;
  align-items: stretch;
  margin-bottom: 4px;
}
.crew-row:hover { background: rgba(64,158,255,0.04); }
/* CCAR-121 违规高亮 */
.crew-row.row-violation {
  border-left: 3px solid #f56c6c;
  background: rgba(245, 108, 108, 0.08);
}
.crew-row.row-violation:hover {
  background: rgba(245, 108, 108, 0.14);
}
.date-header {
  padding: 6px 0 2px;
  margin-bottom: 2px;
}
.date-tag {
  background: #409eff;
  color: #fff;
  padding: 2px 10px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}
.team-header {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(64, 158, 255, 0.1);
  border-left: 3px solid #409eff;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #409eff;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.team-icon { font-size: 14px; }
.team-badge {
  background: #409eff;
  color: #fff;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 500;
  margin-left: 4px;
}
.team-badge-sub {
  background: #e6a23c;
}
.sub-team-header .team-header {
  border-left-color: #e6a23c;
  background: rgba(230, 162, 60, 0.1);
  color: #e6a23c;
}
.crew-label {
  width: 90px;
  flex-shrink: 0;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 2px;
}
.crew-name { color: #f5d0a9; }
.role-tag {
  font-size: 9px;
  padding: 0 3px;
  border-radius: 3px;
}
.role-tag.captain { background: rgba(43,180,243,0.35); }
.role-tag.first_officer { background: rgba(120,200,120,0.35); }
.role-tag.purser { background: rgba(200,160,80,0.35); }
.role-tag.attendant { background: rgba(180,120,200,0.35); }

/* 替班标识 */
.sub-tag {
  font-size: 8px;
  padding: 0 3px;
  border-radius: 3px;
  color: #fff;
  margin-left: 2px;
  font-weight: bold;
}
.tag-absent {
  background: rgba(244, 67, 54, 0.7);
}
.tag-sub {
  background: rgba(76, 175, 80, 0.7);
}
.row-absent {
  background: rgba(244, 67, 54, 0.06);
  border-left: 2px solid rgba(244, 67, 54, 0.5);
}
.row-absent .crew-name {
  color: #ef9a9a;
}
.row-substitute {
  background: rgba(76, 175, 80, 0.06);
  border-left: 2px solid rgba(76, 175, 80, 0.5);
}
.row-substitute .crew-name {
  color: #a5d6a7;
}

.crew-timeline {
  flex: 1;
  position: relative;
  height: 24px;
  background: rgba(0,0,0,0.15);
  border-radius: 3px;
}
.block {
  position: absolute;
  top: 2px;
  height: 20px;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  white-space: nowrap;
  padding: 0 3px;
  min-width: 28px;
  transition: transform 0.15s, box-shadow 0.15s;
}
.block:hover { transform: scaleY(1.25); box-shadow: 0 0 8px rgba(255,255,255,0.4); }
.block.active { transform: scaleY(1.25); box-shadow: 0 0 12px rgba(255,255,255,0.6); border: 1px solid #fff; }
.blk-no { font-size: 8px; font-weight: bold; color: #fff; }

.crew-stats {
  width: 45px;
  flex-shrink: 0;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 2px;
}
.stat-val { color: #aaa; }

.empty-tip {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  font-size: 14px;
}

.hover-popup {
  position: absolute;
  z-index: 100;
  padding: 10px 14px;
  background: rgba(15, 20, 35, 0.95);
  border: 1px solid rgba(64, 158, 255, 0.5);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #ccc;
  min-width: 200px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.6);
  pointer-events: auto;
}
.hp-close {
  position: absolute;
  top: 4px;
  right: 8px;
  cursor: pointer;
  color: #888;
  font-size: 14px;
  line-height: 1;
}
.hp-close:hover { color: #fff; }
.hd-row { display: flex; align-items: center; gap: 6px; }
.hd-label { color: #888; font-size: 11px; min-width: 56px; }
.hd-row strong { color: #f5d0a9; }

/* 人员名册弹窗 */
.roster-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
}
.roster-panel {
  width: 85vw;
  max-width: 960px;
  max-height: 80vh;
  background: rgba(18, 24, 42, 0.98);
  border: 1px solid rgba(64, 158, 255, 0.4);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 8px 40px rgba(0,0,0,0.7);
}
.roster-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}
.roster-header h3 { font-size: 18px; margin: 0; color: #f5d0a9; }
.roster-count { color: #888; font-size: 13px; margin-left: 8px; }
.roster-close {
  margin-left: auto;
  cursor: pointer;
  color: #888;
  font-size: 20px;
  padding: 0 4px;
}
.roster-close:hover { color: #fff; }
.roster-body {
  flex: 1;
  overflow: auto;
  padding: 0;
}
.roster-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  color: #ccc;
}
.roster-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
}
.roster-table th {
  background: rgba(64, 158, 255, 0.15);
  color: #aac;
  font-weight: 600;
  padding: 8px 10px;
  text-align: left;
  border-bottom: 2px solid rgba(64, 158, 255, 0.3);
  white-space: nowrap;
}
.roster-table td {
  padding: 7px 10px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.roster-table tbody tr:hover {
  background: rgba(64, 158, 255, 0.06);
}
.roster-table td strong { color: #f5d0a9; }
.roster-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
}
.roster-status.active { background: rgba(100, 200, 100, 0.2); color: #8c8; }
.roster-status.idle { background: rgba(150, 150, 150, 0.15); color: #888; }
.roster-status.violation { background: rgba(245, 108, 108, 0.25); color: #f56c6c; font-weight: bold; cursor: help; }
.roster-violation td { color: #f5a0a0; }
.roster-violation td:first-child { border-left: 3px solid #f56c6c; }

.dragRectTop, .dragRectBottom {
  width: 100%; height: 10px; position: absolute; left: 0;
}
.dragRectTop { top: 0; }
.dragRectBottom { bottom: 0; }
.dragRectTop::before, .dragRectBottom::before {
  content: ""; width: 10px; height: 10px; border-left: 2px solid skyblue; display: block; position: absolute; left: 0;
}
.dragRectTop::before { border-top: 2px solid skyblue; top: 0; }
.dragRectBottom::before { border-bottom: 2px solid skyblue; bottom: 0; }
.dragRectTop::after, .dragRectBottom::after {
  content: ""; width: 10px; height: 10px; border-right: 2px solid skyblue; display: block; position: absolute; right: 0;
}
.dragRectTop::after { border-top: 2px solid skyblue; top: 0; }
.dragRectBottom::after { border-bottom: 2px solid skyblue; bottom: 0; }

/* ===== 组建机组 ===== */
.team-form-group {
  margin-bottom: 12px;
}
.team-form-group label {
  display: block;
  color: #aaa;
  font-size: 12px;
  margin-bottom: 4px;
  font-weight: 500;
}
.team-form-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.team-result {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(100, 200, 100, 0.15);
  color: #8c8;
  font-size: 13px;
}
.team-result.team-err {
  background: rgba(255, 100, 100, 0.15);
  color: #d88;
}

/* 人员调换 */
.swap-preview {
  margin-top: 4px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  padding: 10px;
}
.swap-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.swap-card {
  flex: 1;
  text-align: center;
  background: rgba(0, 160, 255, 0.08);
  border-radius: 4px;
  padding: 8px 4px;
}
.swap-card .swap-label {
  display: block;
  font-size: 11px;
  color: #999;
  margin-bottom: 4px;
}
.swap-card strong {
  color: #e0e8ff;
  font-size: 14px;
}
.swap-arrow {
  font-size: 18px;
  color: #0af;
  flex-shrink: 0;
}
</style>
