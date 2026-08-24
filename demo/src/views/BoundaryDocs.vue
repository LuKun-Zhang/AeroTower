<template>
  <div v-title data-title="系统边界与依据文档" class="bd-page">
    <!-- 顶栏 -->
    <div class="bd-header">
      <el-button icon="el-icon-arrow-left" size="small" @click="$router.push('/')">返回</el-button>
      <h2>系统边界与依据文档</h2>
      <span class="bd-header-sub">本页面汇总航班调度系统各模块所采用的限制条件及其官方依据文档</span>
    </div>

    <div class="bd-body">
      <!-- ========== 左侧可伸缩目录栏 ========== -->
      <aside class="bd-toc" :class="{ collapsed: tocCollapsed }">
        <div class="bd-toc-toggle" @click="tocCollapsed = !tocCollapsed" :title="tocCollapsed ? '展开目录' : '收起目录'">
          <i :class="tocCollapsed ? 'el-icon-s-unfold' : 'el-icon-s-fold'"></i>
          <span v-if="!tocCollapsed">目录</span>
        </div>

        <div v-if="!tocCollapsed" class="bd-toc-groups">
          <div v-for="group in groups" :key="group.name" class="bd-toc-group">
            <div class="bd-toc-group-title">
              <i :class="group.icon"></i>
              <span>{{ group.name }}</span>
            </div>
            <div
              v-for="item in group.items"
              :key="item.id"
              class="bd-toc-item"
              :class="{ active: activeId === item.id }"
              @click="activeId = item.id"
            >
              <span class="bd-toc-item-title">{{ item.title }}</span>
              <span class="bd-toc-item-doc">{{ item.doc }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- ========== 右侧文档内容区 ========== -->
      <main class="bd-content">
        <div v-if="!activeItem" class="bd-empty">
          <i class="el-icon-document"></i>
          <p>从左侧目录选择一项边界限制，查看系统实现与官方依据文档</p>
        </div>

        <article v-else class="bd-doc">
          <header class="bd-doc-header">
            <span class="bd-doc-tag">{{ activeItem.doc }}</span>
            <h1>{{ activeItem.title }}</h1>
            <p class="bd-doc-module">所属模块：{{ activeItem.module }}</p>
          </header>

          <!-- 系统实现 -->
          <section class="bd-section">
            <h2><i class="el-icon-setting"></i> 本系统实现</h2>
            <p class="bd-system-text">{{ activeItem.system }}</p>
            <div v-if="activeItem.codes" class="bd-code-refs">
              <div v-for="c in activeItem.codes" :key="c" class="bd-code-ref">{{ c }}</div>
            </div>
          </section>

          <!-- 官方依据 -->
          <section class="bd-section">
            <h2><i class="el-icon-notebook-2"></i> 官方依据文档</h2>
            <p class="bd-basis-name">{{ activeItem.doc }}（{{ activeItem.docFullName }}）</p>
            <div v-for="(clause, i) in activeItem.clauses" :key="i" class="bd-clause">
              <div class="bd-clause-title">{{ clause.title }}</div>
              <blockquote>{{ clause.text }}</blockquote>
            </div>
          </section>

          <!-- 来源链接 -->
          <footer class="bd-source">
            <h3><i class="el-icon-link"></i> 官方来源</h3>
            <a v-if="activeItem.source" :href="activeItem.source" target="_blank" rel="noopener">{{ activeItem.source }}</a>
            <p v-if="activeItem.note" class="bd-note">{{ activeItem.note }}</p>
            <div v-if="activeItem.pdf" class="bd-pdf-wrap">
              <PdfDoc :src="activeItem.pdf" :page="activeItem.page" :title="activeItem.docFullName + '（官方 PDF）'" />
            </div>
            <div v-else class="bd-no-pdf">
              <i class="el-icon-document-copy"></i>
              <span>该依据暂无官方 PDF 版，请点击上方网页链接查看全文</span>
            </div>
          </footer>
        </article>
      </main>
    </div>
  </div>
</template>

<script>
/**
 * 系统边界与依据文档
 * 目录结构：分组（模块） → 边界限制项
 * 每项包含：系统实现取值 + 官方依据条款原文 + 官方来源链接
 * 依据文档均取自中国民用航空局/交通运输部公开规章原文。
 */
import PdfDoc from '../components/PdfDoc.vue'

// 官方规章 PDF（已下载到 demo/public/docs 本地目录，同源内嵌预览避免跨域限制）
const PDF_CCAR93 = '/docs/ccar93.pdf'
const PDF_CCAR121 = '/docs/ccar121.pdf'

export default {
  name: 'BoundaryDocs',
  components: { PdfDoc },
  data() {
    return {
      tocCollapsed: false,
      activeId: 'wake-separation',
      groups: [
        {
          name: '跑道调度',
          icon: 'el-icon-s-promotion',
          items: [
            {
              id: 'wake-separation',
              title: '起降尾流间隔',
              doc: 'CCAR-93',
              module: '跑道调度（runway_service / config）',
              system: '同一跑道相邻两次起降操作，在跑道占用时间结束后追加「前机→后机」尾流间隔：重型→重型 2 分钟、重型→中型 3 分钟、重型→轻型 4 分钟、中型→轻型 3 分钟、中型→中型 2 分钟（无强制尾流仅管制缓冲）、后机更重仅 1 分钟。',
              page: 88,
              codes: ['backend/config.py → MIN_SEPARATION', 'backend/services/runway_service.py → solve_multi_runway（前机→后机取间隔）'],
              docFullName: '民用航空空中交通管理规则',
              pdf: PDF_CCAR93,
              clauses: [
                { title: '第二百四十九条（非雷达间隔的尾流间隔，2022 修正版）', text: '当使用下述跑道起飞时，前后起飞离场的航空器为重型机和中型机、重型机和轻型机、中型机和轻型机，其非雷达间隔的尾流间隔不得小于3分钟；前后起飞离场的航空器为A380-800型机和中型机、A380-800型机和轻型机，其非雷达间隔的尾流间隔不得少于4分钟：同一跑道的中间部分；跑道中心线之间距离小于760米的平行跑道的跑道中间部分。' },
                { title: '第二百五十四条（雷达间隔的尾流间隔标准）', text: '前后起飞离场或者前后进近的航空器，其雷达间隔的尾流间隔标准应当按照下列规定：前、后航空器均为重型航空器时，不小于7.4公里；重型航空器在前，中型航空器在后时，不小于9.3公里；重型航空器在前，轻型航空器在后时，不小于11.1公里；中型航空器在前，轻型航空器在后时，不小于9.3公里。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
              note: '系统以时间（分钟）形式近似模拟尾流间隔；演示机队均为中型机（A319/A320/A321），故常规间隔取 2 分钟管制缓冲。',
            },
            {
              id: 'wake-category',
              title: '机型尾流分类',
              doc: 'CCAR-93',
              module: '跑道调度（runway_service._get_category）',
              system: '按最大允许起飞全重将机型分为重型 / 中型 / 轻型三类：A319、A320、A321 均为中型机；重型机型映射含 A330/A340/A350/A380/B767/B777/B787/B747 等。',
              page: 86,
              codes: ['backend/services/runway_service.py → _get_category'],
              docFullName: '民用航空空中交通管理规则',
              pdf: PDF_CCAR93,
              clauses: [
                { title: '第二百四十七条（机型种类分类）', text: '尾流间隔标准根据机型种类而定，本规则中航空器机型种类按航空器最大允许起飞全重分为下列三类：（一）重型机：最大允许起飞全重等于或大于136000千克的航空器；（二）中型机：最大允许起飞全重大于7000千克，小于136000千克的航空器；（三）轻型机：最大允许起飞全重等于或小于7000千克的航空器。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
            },
            {
              id: 'runway-occupancy',
              title: '跑道占用时长（ROT）',
              doc: '机场运行实践',
              module: '跑道调度（runway_service._get_runway_duration）',
              system: '按机型区分跑道占用时长：重型机 3 分钟；中型机中 A321（机身最长）3 分钟，A319/A320 等 2 分钟；其余 2 分钟。',
              page: 88,
              pdf: PDF_CCAR93,
              codes: ['backend/services/runway_service.py → _get_runway_duration'],
              docFullName: '机场跑道占用时间（Runway Occupancy Time）运行惯例',
              clauses: [
                { title: '运行实践', text: '跑道占用时间指航空器从允许进入跑道至离开跑道所用的时间。中型机（B737/A320 级别）典型跑道占用时间约 40～65 秒，大型机更长。本系统以分钟取整近似，并按机型差异体现占用长度差异。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
              note: 'ROT 无统一强制标准，此处取行业运行惯例并做演示简化。',
            },
          ],
        },
        {
          name: '机组排班',
          icon: 'el-icon-user',
          items: [
            {
              id: 'crew-duty',
              title: '机组日执勤期 ≤ 14 小时',
              doc: 'CCAR-121FS',
              module: '机组排班（crew_service）',
              system: '飞行机组（双人制）单个值勤期内执勤时间不超过 14 小时；因运行延误可将值勤期延长至 16 小时，且延长后休息期可相应缩减。',
              page: 172,
              codes: ['backend/services/crew_service.py → max_duty_hours=14'],
              docFullName: '大型飞机公共航空运输承运人运行合格审定规则',
              pdf: PDF_CCAR121,
              clauses: [
                { title: '第121.483条（双人制机组值勤期限制）', text: '在双人制飞行机组中，每名驾驶员的值勤期不得超过14小时；发生运行延误时，值勤期可以延长至不超过16小时。' },
                { title: '第121.481条（概则：值勤定义）', text: '值勤，是指机组成员按照合格证持有人的要求执行的所有任务，包括但不限于飞行值勤、置位、备份（包括主备份和其它备份）和培训等。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
              note: '本系统以「第一班报到 → 最后一班发动机关车」的连续区间近似值勤期。',
            },
            {
              id: 'crew-flight-time',
              title: '机组日飞行时间 ≤ 8 小时',
              doc: 'CCAR-121FS',
              module: '机组排班（crew_service）',
              system: '飞行机组单日飞行时间不超过 8 小时；双人制机组不超过 2 个航段时可延长至 9 小时。',
              page: 172,
              codes: ['backend/services/crew_service.py → max_daily_hours=8'],
              docFullName: '大型飞机公共航空运输承运人运行合格审定规则',
              pdf: PDF_CCAR121,
              clauses: [
                { title: '第121.483条（双人制机组飞行时间限制）', text: '在双人制飞行机组中，每名驾驶员可安排的值勤期内飞行时间不得超过8小时；对于不超过2个航段的飞行，飞行时间可以延长至9小时。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
            {
              id: 'crew-7day',
              title: '机组连续 7 日飞行 ≤ 40 小时',
              doc: 'CCAR-121FS',
              module: '机组排班（crew_service._is_avail_fast）',
              system: '任意连续 7 个日历日滚动飞行时间不超过 40 小时（代码常量 CCAR121_7DAY_MAX_HOURS = 40h）。',
              page: 176,
              codes: ['backend/services/crew_service.py → CCAR121_7DAY_MAX_HOURS = 40 * 60'],
              docFullName: '大型飞机公共航空运输承运人运行合格审定规则',
              pdf: PDF_CCAR121,
              clauses: [
                { title: '第121.487条 / 附录飞行时间限制（连续 7 日）', text: '任何连续 7 个日历日内，飞行时间累计不得超过 40 小时；任一日历月飞行时间不得超过 100 小时；任意连续 3 个日历月不得超过 270 小时；任一日历年不得超过 1000 小时。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
          ],
        },
        {
          name: '飞机排班',
          icon: 'el-icon-s-operation',
          items: [
            {
              id: 'aircraft-daily-hours',
              title: '飞机日飞行时长 ≤ 8 小时',
              doc: 'CCAR-121FS / 运行规范',
              module: '航班生成（flight_generator）',
              system: '单架飞机每日累计飞行时间不超过 8 小时（max_daily_flight_hours=8），用于任务链构建时约束单链飞行时长。',
              codes: ['backend/services/flight_generator.py → max_daily_flight_hours=8'],
              docFullName: '大型飞机公共航空运输承运人运行合格审定规则及承运人运行规范',
              pdf: PDF_CCAR121,
              clauses: [
                { title: '运行规范要求', text: '合格证持有人的运行规范中批准飞机的日利用率/飞行时间限制；行业典型窄体机日利用率为 8～10 小时。本系统取 8 小时作为演示边界。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
            {
              id: 'aircraft-segments',
              title: '飞机日航班段数 ≤ 5 段',
              doc: '航司运行惯例',
              module: '航班生成（flight_generator）',
              system: '单架飞机单日最多执飞 5 个航段（max_segments_per_day=5），与飞行时长上限共同约束任务链长度。',
              codes: ['backend/services/flight_generator.py → max_segments_per_day=5'],
              docFullName: '航司运行惯例（无强制规章上限）',
              clauses: [
                { title: '运行实践', text: '国内窄体机每日典型 4～8 段（短航线）；本系统取 5 段作为演示边界，配合 8 小时日飞行时长共同约束。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
            {
              id: 'turnaround',
              title: '最小过站时间 60 分钟',
              doc: '机场运行标准',
              module: '航班生成（flight_generator）',
              system: '飞机落地到再次起飞的最小过站时间为 60 分钟（min_turnaround=60），任务链衔接必须满足「前段到达 + 60 分钟 ≤ 后段起飞」。',
              codes: ['backend/services/flight_generator.py → min_turnaround=60'],
              docFullName: '机场过站时间（Turnaround Time）运行标准',
              clauses: [
                { title: '运行实践', text: '过站时间受停靠廊桥/机位、上客、加油、清洁、配餐等因素影响。IATA 地面运行实践建议窄体机典型过站 40～60 分钟，国内枢纽机场普遍按 60 分钟排布。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
          ],
        },
        {
          name: '航班生成',
          icon: 'el-icon-s-data',
          items: [
            {
              id: 'load-factor',
              title: '客座率 78%',
              doc: '行业统计数据',
              module: '航班生成（flight_generator）',
              system: '航班座位分配按 78% 客座率（load_factor=0.78）将旅客切批为航班，即每班载客数 ≈ 机型座位数 × 78%。',
              codes: ['backend/services/flight_generator.py → load_factor=0.78'],
              docFullName: '民航客运市场统计（客座率行业水平）',
              clauses: [
                { title: '行业水平', text: '中国民航整体客座率近年约 75%～85%；本系统取 78% 作为演示基准。' },
              ],
              source: 'https://www.caac.gov.cn/XXGK/XXGK/TJSJ/index_1215.html',
            },
            {
              id: 'slot-spacing',
              title: '航班时刻错峰 6 分钟',
              doc: '本系统设计',
              module: '航班生成（flight_generator._wave_dep）',
              system: '同一 30 分钟档位内安排多个航班时，按 6 分钟间隔错峰排布（slot_spacing=6），溢出则顺延下一档，避免同一时刻起降扎堆。',
              codes: ['backend/services/flight_generator.py → _wave_dep / _slot_occupy'],
              docFullName: '本系统设计约束（非规章强制）',
              clauses: [
                { title: '设计说明', text: '航班时刻通常按时刻表协调（IATA 时隙分配）发布；本系统用错峰近似模拟航站时隙，使跑道调度输入更贴近真实分布。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
            },
          ],
        },
        {
          name: '基础设施',
          icon: 'el-icon-location',
          items: [
            {
              id: 'runway-count',
              title: '机场跑道数量',
              doc: '机场公布资料',
              module: '跑道调度（airports_runway.json）',
              system: '按机场真实跑道数量调度：成都 2 条跑道，其余机场按 airports_runway.json 配置，未收录机场默认 1 条。起飞降落混用全部跑道。',
              codes: ['backend/data/airports_runway.json', 'backend/services/runway_service.py → get_runway_count'],
              docFullName: '各机场公布资料（跑道构型）',
              pdf: PDF_CCAR93,
              clauses: [
                { title: '示例（成都双流机场）', text: '成都双流国际机场拥有 2 条平行跑道，可支持双跑道独立平行运行，典型小时容量约 40 架次以上。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
            },
            {
              id: 'gate-buffer',
              title: '登机口最小缓冲 20 分钟',
              doc: '机场运行标准',
              module: '登机口分配（gate_service）',
              system: '同一登机口前后两个航班之间最小缓冲 20 分钟（MIN_BUFFER=20），即前机离口时间 + 20 分钟 ≤ 后机到达登机口时间；登机口数量取自 airports_gates.json 真实配置。',
              codes: ['backend/services/gate_service.py → MIN_BUFFER = 20', 'backend/data/airports_gates.json'],
              docFullName: '机场地面运行标准（登机口周转）',
              clauses: [
                { title: '运行实践', text: '登机口周转需覆盖旅客下机、清洁、配餐、加油、登机等流程，典型周转时间 40～60 分钟；缓冲区间保证地面保障时序安全。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
            },
          ],
        },
        {
          name: '机队与机型',
          icon: 'el-icon-data-board',
          items: [
            {
              id: 'fleet-mix',
              title: '机队规模与机型比例',
              doc: '川航实际机队',
              module: '机队数据（aircraft_index.json / aircraft_types.py）',
              system: '机队共 100 架窄体机，比例 A319:10 / A320:50 / A321:40；航班切批按该比例轮转分配机型，排班匹配时优先同机型。',
              codes: ['backend/services/aircraft_types.py → FLEET_MIX', 'backend/data/aircraft_index.json'],
              docFullName: '四川航空机队公开资料',
              clauses: [
                { title: '机队数据', text: '演示机队 100 架按川航实际窄体机队构成近似取 10/50/40 比例，注册号 B-6388～B-6487。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
            {
              id: 'seat-layout',
              title: '机型座位布局',
              doc: '川航实际布局',
              module: '机队数据（aircraft_types.py）',
              system: 'A319：公务舱 8 座 + 经济舱 124 座（C8Y124）；A320：C8Y156；A321：C8Y186。座位分配与 3D 机舱渲染按各机型布局动态生成。',
              codes: ['backend/services/aircraft_types.py → type_layout', 'demo/src/views/FlightPassengers.vue'],
              docFullName: '各机型座舱布局（航司实际构型）',
              clauses: [
                { title: '布局数据', text: '三机型均为公务舱 2-2、经济舱 3-3 布局；经济舱最后一排可能不满 6 座。' },
              ],
              source: 'https://www.gov.cn/zhengce/202404/content_6945829.htm',
            },
            {
              id: 'ac-duration',
              title: '飞机飞行时长估算',
              doc: '航程数据',
              module: '航班生成（flight_generator.FLIGHT_DURATION）',
              system: '任意城市对航程以「两城市相对成都的时长之和」估算，用于任务链时间衔接、过站校验与跑道占用计算。',
              codes: ['backend/services/flight_generator.py → FLIGHT_DURATION / duration_between'],
              docFullName: '航程数据（估算代理）',
              clauses: [
                { title: '设计说明', text: '演示环境无真实航路时刻数据，采用基于距离的时长估算代理；接入真实航班时刻后应替换为该航班实际飞行时长。' },
              ],
              source: 'https://www.gov.cn/zhengce/2022-11/03/content_5717885.htm',
            },
          ],
        },
      ],
    }
  },
  computed: {
    activeItem() {
      for (const g of this.groups) {
        const it = g.items.find(i => i.id === this.activeId)
        if (it) return it
      }
      return null
    },
  },
}
</script>

<style scoped>
.bd-page {
  width: 100vw; height: 100vh; display: flex; flex-direction: column;
  background: #f5f6f8; color: #303133; font-family: -apple-system, BlinkMacSystemFont,
    'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow: hidden;
}
.bd-header {
  display: flex; align-items: center; gap: 16px;
  padding: 12px 20px; background: #fff; border-bottom: 1px solid #e8e8e8; flex-shrink: 0;
}
.bd-header h2 { margin: 0; font-size: 17px; color: #1a1a1a; }
.bd-header-sub { font-size: 12px; color: #909399; margin-left: auto; }

.bd-body { flex: 1; display: flex; min-height: 0; }

/* ========== 左侧目录栏 ========== */
.bd-toc {
  width: 260px; min-width: 260px; background: #fff; border-right: 1px solid #e8e8e8;
  display: flex; flex-direction: column; transition: all 0.2s; overflow: hidden;
}
.bd-toc.collapsed { width: 44px; min-width: 44px; }
.bd-toc-toggle {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px 0; cursor: pointer; color: #606266; border-bottom: 1px solid #f0f0f0;
  font-size: 13px; flex-shrink: 0;
}
.bd-toc-toggle:hover { background: #f5f7fa; }
.bd-toc-groups { flex: 1; overflow-y: auto; padding: 8px 6px 16px; }
.bd-toc-group { margin-bottom: 10px; }
.bd-toc-group-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 600; color: #909399; padding: 6px 10px;
}
.bd-toc-item {
  padding: 8px 10px 8px 26px; border-radius: 6px; cursor: pointer;
  border-left: 3px solid transparent; transition: all 0.15s;
}
.bd-toc-item:hover { background: #f5f7fa; }
.bd-toc-item.active { background: #ecf5ff; border-left-color: #409eff; }
.bd-toc-item-title { display: block; font-size: 13px; color: #303133; line-height: 1.4; }
.bd-toc-item.active .bd-toc-item-title { color: #409eff; font-weight: 600; }
.bd-toc-item-doc { display: block; font-size: 11px; color: #a0a0a8; margin-top: 2px; }

/* ========== 右侧内容区 ========== */
.bd-content { flex: 1; overflow-y: auto; padding: 24px 32px; background: #f5f6f8; }
.bd-empty {
  height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #c0c4cc;
}
.bd-empty i { font-size: 48px; }
.bd-empty p { margin-top: 12px; font-size: 14px; }

.bd-doc { max-width: 860px; margin: 0 auto; }
.bd-doc-header { padding-bottom: 16px; border-bottom: 1px solid #e8e8e8; margin-bottom: 20px; }
.bd-doc-tag {
  display: inline-block; background: #409eff; color: #fff; font-size: 12px;
  padding: 2px 10px; border-radius: 4px; margin-bottom: 8px;
}
.bd-doc-header h1 { margin: 4px 0 6px; font-size: 24px; color: #1a1a1a; }
.bd-doc-module { margin: 0; font-size: 12px; color: #909399; }

.bd-section { background: #fff; border-radius: 8px; padding: 16px 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.bd-section h2 { margin: 0 0 12px; font-size: 16px; color: #303133; display: flex; align-items: center; gap: 8px; }
.bd-section h2 i { color: #409eff; }
.bd-system-text { font-size: 14px; line-height: 1.8; color: #4a4a52; margin: 0; }
.bd-code-refs { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.bd-code-ref {
  font-size: 11px; color: #476582; background: #f0f6fa; border: 1px solid #dbe7f0;
  border-radius: 4px; padding: 3px 8px; font-family: Consolas, Menlo, monospace;
}
.bd-basis-name { font-size: 13px; color: #606266; margin: 0 0 12px; }
.bd-clause { margin-bottom: 14px; }
.bd-clause:last-child { margin-bottom: 0; }
.bd-clause-title { font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 6px; }
.bd-clause blockquote {
  margin: 0; padding: 10px 14px; background: #fafafc; border-left: 3px solid #dcdfe6;
  font-size: 13px; line-height: 1.8; color: #4a4a52; border-radius: 0 4px 4px 0;
}
.bd-source { background: #fff; border-radius: 8px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.bd-source h3 { margin: 0 0 8px; font-size: 15px; color: #303133; display: flex; align-items: center; gap: 8px; }
.bd-source h3 i { color: #409eff; }
.bd-source a {
  font-size: 13px; color: #409eff; word-break: break-all; text-decoration: none;
}
.bd-source a:hover { text-decoration: underline; }
.bd-pdf-wrap { margin-top: 14px; }
.bd-no-pdf {
  margin-top: 14px; display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: #909399; background: #f5f7fa;
  border: 1px dashed #dcdfe6; border-radius: 6px; padding: 12px 16px;
}
.bd-no-pdf i { color: #c0c4cc; font-size: 18px; }
.bd-note { margin: 10px 0 0; font-size: 12px; color: #b9821c; background: #fdf6ec; border: 1px solid #f5dab1; border-radius: 4px; padding: 8px 12px; line-height: 1.6; }
</style>
