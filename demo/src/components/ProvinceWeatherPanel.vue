<template>
  <div class="province-weather-panel">
    <div class="pwp-title">省份天气实时表</div>
    <div class="pwp-grid" v-if="list.length">
      <div class="pwp-row" v-for="item in list" :key="item.name">
        <span class="pwp-name">{{ item.name }}</span>
        <span class="pwp-badge" :class="'w-' + item.type">{{ item.label }}</span>
      </div>
    </div>
    <div class="pwp-empty" v-else>暂无天气数据</div>
  </div>
</template>

<script>
import api from '@/api'

const WEATHER_LABELS = {
  sunny: '晴',
  cloudy: '多云',
  rain_light: '小雨',
  rain_moderate: '中雨',
  rain_heavy: '大雨',
  thunderstorm: '雷暴',
}

export default {
  name: 'ProvinceWeatherPanel',
  props: {
    interval: { type: Number, default: 2000 },
  },
  data() {
    return {
      list: [],
      _timer: null,
    }
  },
  mounted() {
    this.fetch()
    this._timer = setInterval(() => this.fetch(), this.interval)
  },
  beforeDestroy() {
    if (this._timer) { clearInterval(this._timer); this._timer = null }
  },
  methods: {
    async fetch() {
      try {
        const data = await api.getWeatherDisruption()
        if (data) {
          const pw = data.province_weather || {}
          this.list = Object.keys(pw).map(name => ({
            name,
            type: pw[name] || 'sunny',
            label: WEATHER_LABELS[pw[name]] || '晴',
          }))
        }
      } catch (e) {
        // 静默失败，保留上一次数据
      }
    },
  },
}
</script>

<style scoped>
.province-weather-panel {
  background: rgba(10, 15, 30, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  padding: 8px 10px;
  color: #d0d4e0;
  font-size: 12px;
}
.pwp-title {
  font-weight: 700;
  font-size: 13px;
  color: #409eff;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.pwp-grid {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 320px;
  overflow-y: auto;
}
.pwp-grid::-webkit-scrollbar { width: 4px; }
.pwp-grid::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }
.pwp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 4px;
  border-radius: 3px;
}
.pwp-row:nth-child(odd) { background: rgba(255, 255, 255, 0.03); }
.pwp-name { color: #8a8da0; flex-shrink: 0; }
.pwp-badge {
  padding: 1px 8px;
  border-radius: 9px;
  font-weight: 600;
  white-space: nowrap;
}
.w-sunny { background: rgba(255, 193, 7, 0.18); color: #ffc107; }
.w-cloudy { background: rgba(158, 158, 158, 0.18); color: #cfd8dc; }
.w-rain_light { background: rgba(96, 165, 250, 0.18); color: #90caf9; }
.w-rain_moderate { background: rgba(33, 150, 243, 0.2); color: #42a5f5; }
.w-rain_heavy { background: rgba(25, 118, 210, 0.24); color: #64b5f6; }
.w-thunderstorm { background: rgba(171, 71, 188, 0.22); color: #ce93d8; }
.pwp-empty {
  color: #6a6a8a;
  text-align: center;
  padding: 12px 0;
}
</style>
