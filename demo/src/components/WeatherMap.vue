<template>
  <div class="weather-map-wrapper">
    <div class="weather-header">
      <h3>🌦 天气卫星云图</h3>
      <span class="weather-time">{{ currentTime }}</span>
    </div>
    <div id="weather-map-chart" ref="chart" class="weather-chart"></div>
    <div class="weather-legend">
      <span class="leg-item"><i class="leg-dot dot-clear"></i>晴</span>
      <span class="leg-item"><i class="leg-dot dot-cloudy"></i>多云</span>
      <span class="leg-item"><i class="leg-dot dot-rain"></i>雨</span>
      <span class="leg-item"><i class="leg-dot dot-thunder"></i>雷暴</span>
      <span class="leg-item"><i class="leg-dot dot-fog"></i>雾</span>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import * as china from '@/utils/china'

// 天气颜色映射
const WEATHER_COLORS = {
  clear: '#4caf50',
  cloudy: '#90a4ae',
  rain: '#42a5f5',
  thunderstorm: '#f44336',
  fog: '#b0bec5',
}

const WEATHER_ICONS = {
  clear: '☀', cloudy: '⛅', rain: '🌧', thunderstorm: '⛈', fog: '🌫',
}

export default {
  name: 'WeatherMap',
  props: {
    weatherData: { type: Object, default: () => ({}) },
    currentTime: { type: String, default: '' },
  },
  data() {
    return {
      chart: null,
    }
  },
  watch: {
    weatherData: {
      deep: true,
      handler() { this.renderChart() },
    },
  },
  methods: {
    renderChart() {
      if (!this.$refs.chart) return
      if (!this.chart) {
        this.chart = echarts.init(this.$refs.chart)
      }

      const seriesData = []
      const airports = Object.values(this.weatherData || {})

      airports.forEach(w => {
        const color = WEATHER_COLORS[w.weather] || '#888'
        const icon = WEATHER_ICONS[w.weather] || '?'
        seriesData.push({
          name: icon + ' ' + (w.airport || ''),
          value: [w.lng, w.lat, w.capacity_ratio || 1.0],
          itemStyle: { color },
          weather: w,
        })
      })

      const option = {
        backgroundColor: 'transparent',
        geo: {
          map: 'china',
          roam: true,
          zoom: 1.2,
          center: [106, 32],
          label: { show: false },
          itemStyle: {
            areaColor: '#1a1a2e',
            borderColor: '#2a2a4a',
            borderWidth: 1,
          },
          emphasis: {
            itemStyle: { areaColor: '#2a2a3e' },
          },
        },
        series: [{
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: seriesData,
          symbolSize: (val) => Math.max(8, Math.min(24, (val[2] || 0.5) * 20 + 8)),
          showEffectOn: 'render',
          rippleEffect: {
            brushType: 'stroke',
            scale: 3,
            period: 4,
          },
          label: {
            show: true,
            formatter: (p) => p.name || '',
            position: 'right',
            fontSize: 10,
            color: '#cdd6f4',
          },
        }],
      }

      this.chart.setOption(option, true)
    },
    handleResize() {
      this.chart?.resize()
    },
  },
  mounted() {
    window.addEventListener('resize', this.handleResize)
    this.$nextTick(() => {
      this.renderChart()
    })
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize)
    this.chart?.dispose()
  },
}
</script>

<style scoped>
.weather-map-wrapper {
  border-top: 1px solid #313145;
  background: rgba(10, 10, 26, 0.6);
  padding: 8px 12px;
  flex-shrink: 0;
}
.weather-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.weather-header h3 {
  margin: 0;
  font-size: 13px;
  color: #aaa;
}
.weather-time {
  font-size: 11px;
  color: #cdd6f4;
}
.weather-chart {
  width: 100%;
  height: 240px;
}
.weather-legend {
  display: flex;
  gap: 20px;
  justify-content: center;
  margin-top: 4px;
}
.leg-item {
  font-size: 11px;
  color: #888;
  display: flex;
  align-items: center;
  gap: 4px;
}
.leg-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.dot-clear { background: #4caf50; }
.dot-cloudy { background: #90a4ae; }
.dot-rain { background: #42a5f5; }
.dot-thunder { background: #f44336; }
.dot-fog { background: #b0bec5; }
</style>
