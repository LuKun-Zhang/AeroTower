<template>
  <div id="ver-bar" :style="size">
    <div class="dragRectTop"></div>
    <e-charts :size="size" :options="options" />
    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import ECharts from '@/components/ECharts'
var data = [] //完成百分比
var titlename = [] //始终点
export default {
  components: {
    ECharts
  },
  data: function () {
    return {
      Barcolor: [],
      options: {
        year: 2022,
        title: {
          text: '当前航班运行情况',
          left: "center",
          top: "5px",
          textStyle: {
            color: "#fff",
            fontSize: 12
          }
        },
        grid: {
          top: "22px",
          left: '8%',
          right: '8%',
          bottom: '0',
          containLabel: true
        },
        xAxis: {
          show: false,
          max: 100,//设置最大值
        },
        yAxis: [
          {
            // max: 5,
            show: true,
            data: titlename,
            inverse: true,
            axisLine: {
              show: false
            },
            splitLine: {
              show: false
            },
            axisTick: {
              show: false
            },
            axisLabel: {
              color: "#fff",
              fontSize: "11"
            }
          },
        ],
        series: [
          {
            realtimeSort: true, //柱状图自动排序，排序自动让Y轴名字跟着数据动
            showBackground: true,
            backgroundStyle: {
              color: 'rgba(220, 220, 220, 0.8)',
              borderRadius: 15, // 统一设置四个角的圆角大小
            },
            name: "条",
            type: 'bar',
            yAxisIndex: 0,
            data: data,
            barCategoryGap: '20%',
            barWidth: 14,
            itemStyle: {
              normal: {
                barBorderRadius: 15,
              }
            },
            label: {
              normal: {
                show: true,
                valueAnimation: true, 
                position: "inside",
                formatter: "{c}%",
                color: "#000000", //进度条百分比颜色
                fontSize: 10,
              }
            }
          },
        ]
      },
      size: {
        width: '100%',
        height: '100%'
      }
    }
  },
  props: ["currentTime", "timeSlices", "filteredMode"],
  watch: {
    currentTime: function(){
      if (this.filteredMode && this.timeSlices && this.timeSlices.length > 0) {
        this._renderFromSlice(this.currentTime % this.timeSlices.length);
      } else {
        const testJson = require('../static/json/ProgressBar_A319');
        var idx = this.currentTime % testJson.length;
        this.options.yAxis[0].data = testJson[idx].title;
        this.options.series[0].data = testJson[idx].data;
      }
      this.options = { ...this.options };
    }
  },
  methods: {
    _renderFromSlice(idx) {
      var slice = this.timeSlices[idx] || [];
      var titles = [];
      var values = [];
      for (var i = 0; i < slice.length; i++) {
        var item = slice[i];
        titles.push((item.flight_no || '') + ' ' + item.from + '→' + item.to);
        values.push(Math.round((item.progress || 0) * 100));
      }
      this.options.yAxis[0].data = titles;
      this.options.series[0].data = values;
    }
  },
}
</script>

<style scoped>

#ver-bar{
	/* background-image: url(../assets/line.png); */
  border: 0.5px solid rgba(255,255,255,0.2);
  background: rgba(255, 255, 255, 0.1);
  position: relative;
}
.title{
    text-align: center;
    position: relative;
}
.dragRectTop{
    width: 100%;
    height: 10px;
    position: absolute;
    top: 0;
    left: 0
}

.dragRectTop::before{
    content: "";
    width: 10px;
    height: 10px;
    border-left: 2px solid skyblue;
    border-top: 2px solid skyblue;
    display: block;
    position: absolute;
    left: 0;
    top: 0;
}

.dragRectTop::after{
    content: "";
    width: 10px;
    height: 10px;
    border-right: 2px solid skyblue;
    border-top: 2px solid skyblue;
    display: block;
    position: absolute;
    right: 0;
    top: 0;
}

.dragRectBottom{
    width: 100%;
    height: 10px;
    position: absolute;
    bottom: 0;
    left: 0
}

.dragRectBottom::before{
    content: "";
    width: 10px;
    height: 10px;
    border-left: 2px solid skyblue;
    border-bottom: 2px solid skyblue;
    display: block;
    position: absolute;
    left: 0;
    bottom: 0;
}

.dragRectBottom::after{
    content: "";
    width: 10px;
    height: 10px;
    border-right: 2px solid skyblue;
    border-bottom: 2px solid skyblue;
    display: block;
    position: absolute;
    right: 0;
    bottom: 0;
}
</style>