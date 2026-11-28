<template>
  <div v-title data-title="动态航班调度" class="app-layout">
    <div class="header">
      <div class="back-btn" @click="$router.push('/')">
        <i class="el-icon-arrow-left"></i> 返回首页
      </div>
      <h1></h1>
    </div>

    <!-- 全局告警条 -->
    <div v-if="globalAlert.show" class="global-alert-bar" :class="'alert-bar-' + globalAlert.type">
      <i class="el-icon-warning"></i>
      <span>{{ globalAlert.message }}</span>
      <el-button type="text" size="mini" style="color:#fff;margin-left:auto" @click="dismissAlert">×</el-button>
    </div>

    <!-- 模块标签切换 -->
    <div class="tab-bar">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.key === 'recovery' && pendingAnomalyCount" class="tab-badge">{{ pendingAnomalyCount }}</span>
      </div>
    </div>

    <!-- 内容区域 -->
    <div class="charts" :class="{ 'charts--full': isMapTab }">
      <keep-alive>
        <GanttView v-if="activeTab === 'routing'" key="routing" />
        <RunwayView v-else-if="activeTab === 'runway'" key="runway" />
        <GateView v-else-if="activeTab === 'gate'" key="gate" />
        <CrewView v-else-if="activeTab === 'crew'" key="crew" />
        <FilterView v-else-if="activeTab === 'filter'" key="filter" />
        <DashboardView v-else-if="activeTab === 'dashboard'" key="dashboard" @nav="navTo" />
        <RecoveryView v-else-if="activeTab === 'recovery'" key="recovery" />
        <div v-else key="empty" style="display:none"></div>
      </keep-alive>

      <!-- 地图视图 -->
      <div v-show="isMapTab" class="map-view">
        <!-- 右侧地图区域（满宽） -->
        <div class="map-right">
          <div class="mapa-full">
            <Map v-if="flagMap" :currentTime="currentTime" @totalSlices="onTotalSlices" @filteredData="onFilteredData"></Map>
            <Mapa v-else @dateSelected="onMapDateSelected"></Mapa>
          </div>
        </div>
        <!-- 底部统计图表工具栏 -->
        <div class="map-stats-bar">
          <template v-if="!flagMap">
            <div class="stat-panel" :style="{flex: '1'}">
              <pie4 :heatmapData="mapHeatmap"></pie4>
            </div>
            <div class="stat-panel" @click="qiehuan" :style="{flex: flag ? '1' : '1'}">
              <pie2 v-if="flag" :aircraftStats="mapAircraftStats"></pie2>
              <pie3 v-else :aircraftStats="mapAircraftStats"></pie3>
            </div>
            <!-- 演示控制按钮 -->
            <div class="map-ctrl-btn">
              <el-button type="info" size="small" @click.stop="changeMap">打开演示控制</el-button>
            </div>
          </template>
          <template v-else>
            <div class="stat-panel" style="flex:1">
              <ctrl @changeTime="changeTime" :maxSlices="totalSlices"></ctrl>
            </div>
            <div class="stat-panel" style="flex:1">
              <ProgressBar :currentTime="currentTime" :timeSlices="mapTimeSlices" :filteredMode="mapFilteredMode"></ProgressBar>
            </div>
            <!-- 演示控制按钮 -->
            <div class="map-ctrl-btn">
              <el-button type="info" size="small" @click.stop="changeMap">返回统计页</el-button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import * as echarts from "echarts";
import Map from "@/components/Map";
import Mapa from "@/components/Map-a";
import ProgressBar from "@/components/ProgressBar";
import Pie4 from "@/components/Pie4";
import Pie2 from "@/components/Pie2";
import Pie3 from "@/components/Pie3";
import Ctrl from "@/components/Ctrl";
import RunwayView from "@/views/RunwayView";
import GanttView from "@/views/GanttView";
import GateView from "@/views/GateView";
import CrewView from "@/views/CrewView";
import FilterView from "@/views/FilterView";
import DashboardView from "@/views/DashboardView";
import RecoveryView from "@/views/RecoveryView";

export default {
  name: "FlightScheduler",
  data() {
    return {
      flag: false,
      flagMap: true,
      currentTime: 0,
      totalSlices: 657,
      mapTimeSlices: [],
      mapFilteredMode: false,
      mapStats: null,
      statsDate: '',
      activeTab: "filter",
      tabs: [
        { key: "filter", label: "航班筛选" },
        { key: "dashboard", label: "总览" },
        { key: "routing", label: "飞机排班" },
        { key: "runway", label: "跑道调度" },
        { key: "gate", label: "登机口分配" },
        { key: "crew", label: "机组排班" },
        { key: "recovery", label: "异常调度" },
        { key: "map", label: "地图视图" },
        { key: "simhub", label: "模拟大引擎" },
      ],
    };
  },
  components: {
    Map,
    Mapa,
    ProgressBar,
    Pie2,
    Pie3,
    Ctrl,
    Pie4,
    RunwayView,
    GanttView,
    GateView,
    CrewView,
    FilterView,
    DashboardView,
    RecoveryView,
  },
  computed: {
    isMapTab() {
      return this.activeTab === 'map';
    },
    mapHeatmap() {
      return this.mapStats ? this.mapStats.heatmap : null;
    },
    mapAircraftStats() {
      return this.mapStats ? this.mapStats.aircraft_stats : [];
    },
    globalAlert() {
      return this.$store.state.globalAlert;
    },
    pendingAnomalyCount() {
      const list = this.$store.state.activeAnomalies || [];
      return list.filter(e => e.status === 'pending' || e.status === 'analyzing' || e.status === 'recovering').length;
    },
  },
  watch: {
    activeTab(newVal) {
      if (newVal === 'simhub') {
        this.$router.push('/simulation-hub')
        return
      }
      // 地图区是 v-show：组件在隐藏状态下就已 mounted，echarts 拿到的容器尺寸是 0，
      // 会退化成 100x100 的小画布（表现为地图只出现在左上角一小块）。切回来时必须补 resize。
      if (newVal === 'map') {
        this.$nextTick(() => this.resizeMapViewCharts())
      }
    },
  },
  methods: {
    resizeMapViewCharts() {
      const root = this.$el && this.$el.querySelector('.map-view')
      if (!root) return
      const hosts = root.querySelectorAll('[_echarts_instance_]')
      for (let i = 0; i < hosts.length; i++) {
        const inst = echarts.getInstanceByDom(hosts[i])
        if (inst) inst.resize()
      }
    },
    dismissAlert() {
      this.$store.commit('CLEAR_GLOBAL_ALERT');
    },
    qiehuan() { this.flag = !this.flag; },
    changeMap() {
      this.flagMap = !this.flagMap;
      if (!this.flagMap) {
        this.fetchMapStats(this.statsDate);
      }
    },
    changeTime(currentTime) { this.currentTime = currentTime; },
    onTotalSlices(n) { this.totalSlices = n || 657; },
    onFilteredData(data) {
      this.mapTimeSlices = data.timeslices || [];
      this.mapFilteredMode = true;
      this.totalSlices = this.mapTimeSlices.length || 657;
      this.fetchMapStats();
    },
    onMapDateSelected(date) {
      this.statsDate = date || '';
      this.fetchMapStats(date || undefined);
    },
    navTo(tab) { this.activeTab = tab; },
    async fetchMapStats(date) {
      try {
        var url = '/api/map/stats';
        if (date) url += '?date=' + encodeURIComponent(date);
        var res = await fetch(url);
        var json = await res.json();
        if (json.code === 0 && json.data) {
          this.mapStats = json.data;
        }
      } catch (e) {
        console.warn('[App] 统计API加载失败', e);
      }
    },
  },
  created() {
    this.fetchMapStats();
  },
};
</script>

<style>
@font-face {
  font-family: electronicFont;
  src: url(../assets/DS-DIGIT.TTF);
}

.app-layout {
  font-size: calc(100vw / 24);
  color: #fff;
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-image: url(../assets/bg.jpg);
  background-size: cover;
  background-repeat: no-repeat;
  background-color: #0a0a1a;
  overflow: hidden;
  font-family: Arial, Helvetica, sans-serif;
}

/* 地图视图时去掉 padding，让地图填满 */
.charts--full {
  padding: 0;
}

.header {
  width: 100vw;
  text-align: center;
  position: relative;
  height: 1.25rem;
  line-height: 1.25rem;
  background-image: url(../assets/head_bg.png);
  background-size: 100%;
  background-repeat: no-repeat;
  flex-shrink: 0;
}

.header h1 {
  width: 100%;
  font-size: 0.6rem;
  line-height: 1.25rem;
}

.back-btn {
  position: absolute;
  left: 0.15rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.88rem;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  padding: 8px 40px;
  border-radius: 6px;
  transition: all 0.2s;
  z-index: 10;
  line-height: 1.6;
}
.back-btn:hover {
  color: #fff;
  background: rgba(255,255,255,0.1);
}

.tab-bar {
  display: flex;
  justify-content: center;
  gap: 4px;
  padding: 4px 0;
  flex-shrink: 0;
}
.tab-item {
  padding: 4px 18px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
  background: rgba(255,255,255,0.08);
  transition: all 0.2s;
  user-select: none;
}
.tab-item:hover { background: rgba(255,255,255,0.15); }
.tab-item.active {
  background: rgba(43,196,243,0.35);
  color: #fff;
  font-weight: bold;
}
.tab-item {
  position: relative;
}
.tab-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #F56C6C;
  color: #fff;
  font-size: 10px;
  min-width: 16px;
  height: 16px;
  line-height: 16px;
  border-radius: 8px;
  text-align: center;
  padding: 0 4px;
}

/* 全局告警条 */
.global-alert-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 20px;
  font-size: 13px;
  color: #fff;
  flex-shrink: 0;
}
.alert-bar-success { background: #67C23A; }
.alert-bar-warning { background: #E6A23C; }
.alert-bar-info { background: #409EFF; }
.alert-bar-error { background: #F56C6C; }

.charts {
  flex: 1;
  width: 100vw;
  padding: 0.1rem 0.15rem;
  display: flex;
  overflow-y: auto;
}

/* 地图视图时去掉 padding 和滚动，让地图填满 */
.charts--full {
  padding: 0;
  overflow: hidden;
}

/* ========== 地图视图：上地图 + 下统计 ========== */
.map-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 100%;
}
.map-right {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.mapa-full {
  flex: 1;
  min-height: 0;
}
.map-stats-bar {
  flex: none;
  display: flex;
  flex-direction: row;
  min-height: 250px;
  overflow: hidden;
  padding: 6px;
  gap: 6px;
  background: rgba(0,0,0,0.2);
}
.stat-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: stretch;
  cursor: pointer;
}
.stat-panel > div,
.stat-panel > div > div {
  flex: 1;
  width: 100%;
  height: 100%;
}
.map-ctrl-btn {
  text-align: center;
  margin-bottom: 6px;
  writing-mode: horizontal-tb;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
}

/* 隐藏旧布局样式 */
.charts .mid,
.charts .right {
  display: none;
}

.full-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.mid .title {
  margin: 0.1rem 0.1rem 2rem 0.1rem;
  padding: 0.2rem 1rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: rgba(255,255,255,0.2);
}
.mid .title .number {
  width: 100%;
  height: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.7rem;
  color: #f5d0a9;
  border: 1px solid rgba(255,255,255,0.1);
  position: relative;
}
.borderTop, .borderbottom {
  position: absolute;
  width: 100%;
  height: 0.1rem;
}
.borderTop { top: 0; left: 0; }
.borderbottom { bottom: 0; right: 0; }
.borderTop::before {
  content: "";
  position: absolute;
  top: 0; left: 0;
  width: 0.4rem; height: 0.2rem;
  border-left: 2px solid skyblue;
  border-top: 2px solid skyblue;
}
.borderbottom::after {
  content: "";
  position: absolute;
  bottom: 0; right: 0;
  width: 0.4rem; height: 0.2rem;
  border-bottom: 2px solid skyblue;
  border-right: 2px solid skyblue;
}
</style>
