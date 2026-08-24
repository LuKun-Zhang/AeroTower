<template>
  <div class="weather-page">
    <div class="weather-header">
      <button class="back-btn" @click="$router.push({ name: 'Home' })">← 返回主页</button>
      <h2 class="page-title">天气气象图</h2>
      <span class="header-hint">滚轮缩放 · 右键旋转 · 拖拽平移</span>
    </div>
    <div class="weather-body">
      <WeatherMap3D
        ref="weatherMap"
        :weatherData="{}"
        :currentTime="''"
      />

      <!-- 实时中断联动摘要（每 2s 自动回传刷新，无发布按钮） -->
      <div class="stream-summary" v-if="summary">
        <div class="summary-title">天气中断联动 · 自动回传</div>
        <div class="summary-row" v-if="summary.clock">
          <span class="k">当前业务时刻</span>
          <span class="v">{{ summary.clock.current_time }}</span>
        </div>
        <div class="summary-row" v-if="summary.affected_provinces !== undefined">
          <span class="k">受影响省份</span>
          <span class="v">{{ summary.affected_provinces.length ? summary.affected_provinces.join('、') : '无' }}</span>
        </div>
        <div class="summary-row" v-if="summary.direct_count !== undefined">
          <span class="k">直达 / 途经</span>
          <span class="v">{{ summary.direct_count }} / {{ summary.transit_count }}</span>
        </div>
        <div class="summary-row" v-if="summary.delay_count !== undefined">
          <span class="k">延误 / 取消</span>
          <span class="v">{{ summary.delay_count }} / {{ summary.cancel_count }}</span>
        </div>
        <div class="summary-error" v-if="summary.error">{{ summary.error }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import WeatherMap3D from '@/components/WeatherMap3D'
import api from '@/api'

export default {
  name: 'WeatherView',
  components: { WeatherMap3D },
  data() {
    return {
      summary: null,
      _timer: null,
    }
  },
  mounted() {
    this._startStream()
  },
  beforeDestroy() {
    this._stopStream()
  },
  methods: {
    _startStream() {
      this._stopStream()
      this._pushStream()
      this._timer = setInterval(() => this._pushStream(), 2000)
    },
    _stopStream() {
      if (this._timer) {
        clearInterval(this._timer)
        this._timer = null
      }
    },
    async _pushStream() {
      const wm = this.$refs.weatherMap
      if (!wm) return
      try {
        const clock = wm.getBusinessClock()
        const predicted = wm.predictProvinceTimeline(10080)
        const payload = {
          mode: wm.getMode(),
          province_weather: wm.getCurrentProvinceWeather(),
          clock,
          anchor: predicted.anchor,
          minutes_per_step: predicted.minutes_per_step,
          timeline: predicted.timeline,
        }
        const data = await api.weatherStream(payload)
        this.summary = { ...data, clock }
      } catch (err) {
        this.summary = {
          error: err && err.message ? err.message : '自动回传失败',
          clock: null,
        }
      }
    },
  },
}
</script>

<style scoped>
.weather-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: #e8ecf2;
}

.weather-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 16px;
  background: rgba(10, 15, 30, 0.92);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  z-index: 100;
  flex-shrink: 0;
}

.back-btn {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.2s;
}

.back-btn:hover {
  background: rgba(64, 158, 255, 0.25);
  color: #66b1ff;
}

.page-title {
  font-size: 16px;
  font-weight: 700;
  color: #d0d8f0;
  margin: 0;
}

.header-hint {
  margin-left: auto;
  font-size: 11px;
  color: #687090;
}

.weather-body {
  flex: 1;
  min-height: 0;
  position: relative;
}

/* ——— 自动回传摘要浮层 ——— */
.stream-summary {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 30;
  min-width: 240px;
  max-width: 300px;
  padding: 10px 12px;
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #d0d4e0;
  font-size: 12px;
  backdrop-filter: blur(6px);
}
.summary-title {
  font-weight: 700;
  font-size: 13px;
  color: #409eff;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.summary-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}
.summary-row .k {
  color: #8a8da0;
  flex-shrink: 0;
}
.summary-row .v {
  color: #e0e4f0;
  text-align: right;
  word-break: break-all;
}
.summary-error {
  margin-top: 6px;
  padding: 6px 8px;
  color: #ff7777;
  background: rgba(255, 80, 80, 0.1);
  border-radius: 4px;
  font-size: 11px;
}
</style>
