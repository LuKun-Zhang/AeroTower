<template>
  <div id="pie" :style="totalsize">
    <div class="dragRectTop"></div>
    <h2 style="text-align:center;font-size:13px;margin:2px 0;">航班24h分布热力图</h2>
    <!-- <br/> -->
    <e-charts :size="size" :options="options" />
    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import ECharts from '@/components/ECharts'
      // prettier-ignore
var hours = ['12am', '1am', '2am', '3am', '4am', '5am', '6am', '7am', '8am', '9am', '10am', '11am', '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm'];
// prettier-ignore
var days = ['11.30', '12.1', '12.2', '12.3', '12.4', '12.5', '12.6'];
// prettier-ignore
// var data = [[0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 3, 0], [0, 4, 0], [0, 5, 1], [0, 6, 7], [0, 7, 13], [0, 8, 17], [0, 9, 20], [0, 10, 19], [0, 11, 17], [0, 12, 18], [0, 13, 18], [0, 14, 14], [0, 15, 13], [0, 16, 12], [0, 17, 11], [0, 18, 10], [0, 19, 11], [0, 20, 14], [0, 21, 13], [0, 22, 12], [0, 23, 11], [1, 0, 9], [1, 1, 8], [1, 2, 0], [1, 3, 0], [1, 4, 0], [1, 5, 0], [1, 6, 8], [1, 7, 15], [1, 8, 19], [1, 9, 20], [1, 10, 18], [1, 11, 15], [1, 12, 15], [1, 13, 15], [1, 14, 13], [1, 15, 14], [1, 16, 16], [1, 17, 12], [1, 18, 10], [1, 19, 9], [1, 20, 11], [1, 21, 13], [1, 22, 11], [1, 23, 10], [2, 0, 8], [2, 1, 3], [2, 2, 0], [2, 3, 0], [2, 4, 0], [2, 5, 1], [2, 6, 8], [2, 7, 16], [2, 8, 19], [2, 9, 21], [2, 10, 20], [2, 11, 18], [2, 12, 18], [2, 13, 19], [2, 14, 13], [2, 15, 11], [2, 16, 11], [2, 17, 13], [2, 18, 12], [2, 19, 12], [2, 20, 12], [2, 21, 14], [2, 22, 14], [2, 23, 11], [3, 0, 8], [3, 1, 4], [3, 2, 0], [3, 3, 0], [3, 4, 0], [3, 5, 0], [3, 6, 7], [3, 7, 14], [3, 8, 17], [3, 9, 18], [3, 10, 15], [3, 11, 16], [3, 12, 16], [3, 13, 14], [3, 14, 14], [3, 15, 14], [3, 16, 15], [3, 17, 14], [3, 18, 10], [3, 19, 11], [3, 20, 11], [3, 21, 12], [3, 22, 9], [3, 23, 9], [4, 0, 7], [4, 1, 1], [4, 2, 0], [4, 3, 0], [4, 4, 0], [4, 5, 1], [4, 6, 9], [4, 7, 15], [4, 8, 19], [4, 9, 22], [4, 10, 20], [4, 11, 19], [4, 12, 18], [4, 13, 18], [4, 14, 14], [4, 15, 12], [4, 16, 11], [4, 17, 11], [4, 18, 11], [4, 19, 11], [4, 20, 11], [4, 21, 12], [4, 22, 11], [4, 23, 9], [5, 0, 6], [5, 1, 3], [5, 2, 0], [5, 3, 0], [5, 4, 0], [5, 5, 0], [5, 6, 9], [5, 7, 16], [5, 8, 20], [5, 9, 21], [5, 10, 19], [5, 11, 18], [5, 12, 18], [5, 13, 17], [5, 14, 16], [5, 15, 15], [5, 16, 15], [5, 17, 12], [5, 18, 12], [5, 19, 12], [5, 20, 13], [5, 21, 15], [5, 22, 15], [5, 23, 14], [6, 0, 13], [6, 1, 3], [6, 2, 0], [6, 3, 0], [6, 4, 0], [6, 5, 1], [6, 6, 9], [6, 7, 17], [6, 8, 19], [6, 9, 21], [6, 10, 20], [6, 11, 20], [6, 12, 20], [6, 13, 19], [6, 14, 15], [6, 15, 14], [6, 16, 13], [6, 17, 12], [6, 18, 12], [6, 19, 11], [6, 20, 14], [6, 21, 15], [6, 22, 14], [6, 23, 12]];
var data = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0], [5, 0, 1], [6, 0, 7], [7, 0, 13], [8, 0, 17], [9, 0, 20], [10, 0, 19], [11, 0, 17], [12, 0, 18], [13, 0, 18], [14, 0, 14], [15, 0, 13], [16, 0, 12], [17, 0, 11], [18, 0, 10], [19, 0, 11], [20, 0, 14], [21, 0, 13], [22, 0, 12], [23, 0, 11], [0, 1, 9], [1, 1, 8], [2, 1, 0], [3, 1, 0], [4, 1, 0], [5, 1, 0], [6, 1, 8], [7, 1, 15], [8, 1, 19], [9, 1, 20], [10, 1, 18], [11, 1, 15], [12, 1, 15], [13, 1, 15], [14, 1, 13], [15, 1, 14], [16, 1, 16], [17, 1, 12], [18, 1, 10], [19, 1, 9], [20, 1, 11], [21, 1, 13], [22, 1, 11], [23, 1, 10], [0, 2, 8], [1, 2, 3], [2, 2, 0], [3, 2, 0], [4, 2, 0], [5, 2, 1], [6, 2, 8], [7, 2, 16], [8, 2, 19], [9, 2, 21], [10, 2, 20], [11, 2, 18], [12, 2, 18], [13, 2, 19], [14, 2, 13], [15, 2, 11], [16, 2, 11], [17, 2, 13], [18, 2, 12], [19, 2, 12], [20, 2, 12], [21, 2, 14], [22, 2, 14], [23, 2, 11], [0, 3, 8], [1, 3, 4], [2, 3, 0], [3, 3, 0], [4, 3, 0], [5, 3, 0], [6, 3, 7], [7, 3, 14], [8, 3, 17], [9, 3, 18], [10, 3, 15], [11, 3, 16], [12, 3, 16], [13, 3, 14], [14, 3, 14], [15, 3, 14], [16, 3, 15], [17, 3, 14], [18, 3, 10], [19, 3, 11], [20, 3, 11], [21, 3, 12], [22, 3, 9], [23, 3, 9], [0, 4, 7], [1, 4, 1], [2, 4, 0], [3, 4, 0], [4, 4, 0], [5, 4, 1], [6, 4, 9], [7, 4, 15], [8, 4, 19], [9, 4, 22], [10, 4, 20], [11, 4, 19], [12, 4, 18], [13, 4, 18], [14, 4, 14], [15, 4, 12], [16, 4, 11], [17, 4, 11], [18, 4, 11], [19, 4, 11], [20, 4, 11], [21, 4, 12], [22, 4, 11], [23, 4, 9], [0, 5, 6], [1, 5, 3], [2, 5, 0], [3, 5, 0], [4, 5, 0], [5, 5, 0], [6, 5, 9], [7, 5, 16], [8, 5, 20], [9, 5, 21], [10, 5, 19], [11, 5, 18], [12, 5, 18], [13, 5, 17], [14, 5, 16], [15, 5, 15], [16, 5, 15], [17, 5, 12], [18, 5, 12], [19, 5, 12], [20, 5, 13], [21, 5, 15], [22, 5, 15], [23, 5, 14], [0, 6, 13], [1, 6, 3], [2, 6, 0], [3, 6, 0], [4, 6, 0], [5, 6, 1], [6, 6, 9], [7, 6, 17], [8, 6, 19], [9, 6, 21], [10, 6, 20], [11, 6, 20], [12, 6, 20], [13, 6, 19], [14, 6, 15], [15, 6, 14], [16, 6, 13], [17, 6, 12], [18, 6, 12], [19, 6, 11], [20, 6, 14], [21, 6, 15], [22, 6, 14], [23, 6, 12]];
var maxValue = data.reduce(function (max, item) {
  return Math.max(max, item[2]);
}, -Infinity);
export default {
  components: {
    ECharts
  },
  props: { heatmapData: Object },
  data: function () {
    return{

      options:{
        tooltip: {
          trigger: 'item',
          formatter:function(params) {
          if (params.data[1] == 0)
        	return "11.30日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次" 
          else if (params.data[1] == 1)
        	return "12.1日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次"
          else if (params.data[1] == 2)
        	return "12.2日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次"  
          else if (params.data[1] == 3)
        	return "12.3日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次" 
          else if (params.data[1] == 4)
        	return "12.4日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次"
          else if (params.data[1] == 5)
        	return "12.5日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次"
          else if (params.data[1] == 6)
        	return "12.6日" + params.data[0] + "时到" + (params.data[0] + 1) + "时<br>共有航班" + params.data[2] + "架次"
        }
        },
  grid: {
    height: '50%',
    top: '10%'
  },
  xAxis: {
    type: 'category',
    data: hours,
    splitArea: {
      show: true
    },
    axisLabel: {
            show: true,
            lineStyle:{
              color:'black',//更改坐标轴颜色
            },
            textStyle: {
              color: 'white',  //更改坐标轴文字颜色
              fontSize : 12      //更改坐标轴文字大小
            }
          },
  },
  yAxis: {
    type: 'category',
    data: days,
    splitArea: {
      show: true
    },
    axisLabel: {
            show: true,
            lineStyle:{
              color:'black',//更改坐标轴颜色
            },
            textStyle: {
              color: 'white',  //更改坐标轴文字颜色
              fontSize : 12      //更改坐标轴文字大小
            }
          },
  },
  visualMap: {
    type: 'continuous',
    min: 0,
    max: maxValue,
    textStyle: {
        color: 'white',
        fontSize : 10
    },
    dimension: 2,
    orient: 'horizontal',
    left: 'center',
    bottom: '22%',
    calculable: true
  },
  // visualMap: {
  //   min: 0,
  //   max: 10,
  //   calculable: true,
  //   orient: 'horizontal',
  //   left: 'center',
  //   bottom: '22%'
  // },
  series: [
    {
      name: 'Punch Card',
      type: 'heatmap',
      data: data,
      // label: {
      //   show: true
      // },
      
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }
  ]
      },
      size: {
        width: '100%',
        height: '100%'
      },
      totalsize: {
        width: '100%',
        height: '100%'
      }
    }
  },
  watch: {
    heatmapData: {
      immediate: true,
      handler: '_applyHeatmap'
    }
  },
  methods: {
    _applyHeatmap() {
      if (!this.heatmapData || !this.heatmapData.data) return;
      var maxV = 0;
      for (var i = 0; i < this.heatmapData.data.length; i++) {
        maxV = Math.max(maxV, this.heatmapData.data[i][2]);
      }
      var s0 = this.options.series[0];
      var vm = this.options.visualMap;
      var xa = this.options.xAxis;
      var ya = this.options.yAxis;
      this.options = Object.assign({}, this.options, {
        xAxis: Object.assign({}, xa, {
          data: this.heatmapData.hour_labels || xa.data,
        }),
        yAxis: Object.assign({}, ya, {
          data: this.heatmapData.day_labels || ya.data,
        }),
        visualMap: Object.assign({}, vm, {
          max: maxV > 0 ? maxV : vm.max,
        }),
        series: [Object.assign({}, s0, {
          data: this.heatmapData.data,
        })]
      });
      this.$forceUpdate();
    }
  }
}
</script>

<style scoped>
#pie {
  width: 100%;
  height: 100%;
  /* background-image: url(../assets/line.png); */
  border: 0.5px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  position: relative;
}

.title {
  text-align: center;
  position: relative;
}

.dragRectTop {
  width: 100%;
  height: 10px;
  position: absolute;
  top: 0;
  left: 0;
}

.dragRectTop::before {
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

.dragRectTop::after {
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

.dragRectBottom {
  width: 100%;
  height: 10px;
  position: absolute;
  bottom: 0;
  left: 0;
}

.dragRectBottom::before {
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

.dragRectBottom::after {
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