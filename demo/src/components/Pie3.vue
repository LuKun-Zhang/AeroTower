<template>
  <div id="pie" :style="size">
    <div class="dragRectTop"></div>
    <e-charts :size="size" :options="options2" />
    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import ECharts from '@/components/ECharts'
export default {
  components: {
    ECharts
  },
  props: { aircraftStats: Array },
  data: function () {
    return {
      flag:true,
      // options: {
      //   title: {
      //     text: '飞机执飞航班数量分析',
      //     textStyle: {
      //       color: "rgba(255,255,255,0.9)"
      //     },
      //     left: "center",
      //     top: "5px"
      //   },
      //   tooltip: {
      //     trigger: 'item',
      //     formatter: " {b}号飞机执飞数量:{c}({d}%)"
      //   },
      //   // legend: {
      //   //   // top: '90%',
      //   //   left: 'right',
      //   //   orient: 'vertical',
      //   //   textStyle: {
      //   //     color: "rgba(255,255,255,0.6)",
      //   //     fontSize: "12"
      //   //   }
      //   // },
      //   series: [
      //     {
      //       name: 'Access From',
      //       type: 'pie',
      //       radius: '50%',
      //       left: 'left',
      //       // roseType: "radius",
      //       // avoidLabelOverlap: false,
      //       color: ["#a0e85b", "#1b511d", "#c6edc5", "#0f144c", "#967ff2", "#803673", "#bf11af", "#edcbde", "#1a119b", "#918ea2", "#445082", "#fa79f5", "#8c2efc", "#c479a3", "#faf679", "#829951", "#30972e", "#3a2006", "#e9ad6f", "#84541a", "#ed4b04", "#8f0f1b"],
      //       // label: {
      //       //   // show: false,
      //       //   position: 'center'
      //       // },
      //       emphasis: {
      //         itemStyle: {
      //           shadowBlur: 10,
      //           shadowOffsetX: 0,
      //           shadowColor: 'rgba(0, 0, 0, 0.5)'
      //         }
      //       },
      //       data: [
      //         { value: 27, name: '1' },
      //         { value: 33, name: '2' },
      //         { value: 40, name: '3' },
      //         { value: 31, name: '4' },
      //         { value: 33, name: '5' },
      //         { value: 27, name: '6' },
      //         { value: 34, name: '7' },
      //         { value: 35, name: '8' },
      //         { value: 26, name: '9' },
      //         { value: 31, name: '10' },
      //         { value: 31, name: '11' },
      //         { value: 26, name: '12' },
      //         { value: 28, name: '13' },
      //         { value: 30, name: '14' },
      //         { value: 24, name: '15' },
      //         { value: 36, name: '16' },
      //         { value: 27, name: '17' },
      //         { value: 26, name: '18' },
      //         { value: 27, name: '19' },
      //         { value: 32, name: '20' },
      //         { value: 16, name: '21' },
      //         { value: 12, name: '22' },
      //       ]
      //     }
      //   ]
      // },
      size: {
        width: '100%',
        height: '100%'
      },
      options2: {
        title: {
          text: '飞机执飞航班数量分析',
          textStyle: {
            color: "rgba(255,255,255,0.9)"
          },
          left: "center",
          top: "5px"
        },
        tooltip: {
          trigger: 'item',
          formatter: " {b}号飞机执飞数量:{c}"
        },
        xAxis: {
          type: 'category',
          data: ['1', '2', '3', '4', '5', '6', '7','8','9', '10', '11', '12', '13', '14', '15', '16', '17','18','19', '20', '21', '22'],
          axisLabel: {
            // show: true,
            interval:0,
            textStyle: {
              color: 'white',  //更改坐标轴文字颜色
              fontSize : 12      //更改坐标轴文字大小
            }
          },
          // splitLine:{ //修改背景线条样式
          //   show:false,//是否展示 
          // }
        },
        yAxis: {
          type: 'value',
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
          splitLine:{ //修改背景线条样式
            show:false,//是否展示 
            lineStyle:{ 
              color:"#353b5a",//线条颜色
              type:"dashed"//线条样式，默认是实现，dashed是虚线
            } 
          }
        },
        series: [
          {
            data: [

              {
                value: 27,
                itemStyle: {
                  color: '#a0e85b'
                }
              },
              {
                value: 33,
                itemStyle: {
                  color: '#1b511d'
                }
              },
              {
                value: 40,
                itemStyle: {
                  color: '#c6edc5'
                }
              },
              
              {
                value: 31,
                itemStyle: {
                  color: '#0f144c'
                }
              },
              {
                value: 33,
                itemStyle: {
                  color: '#967ff2'
                }
              },
              {
                value: 27,
                itemStyle: {
                  color: '#803673'
                }
              },
              {
                value: 34,
                itemStyle: {
                  color: '#bf11af'
                }
              },
              {
                value: 35,
                itemStyle: {
                  color: '#edcbde'
                }
              },
              {
                value: 26,
                itemStyle: {
                  color: '#1a119b'
                }
              },
              {
                value: 31,
                itemStyle: {
                  color: '#918ea2'
                }
              },
              {
                value: 31,
                itemStyle: {
                  color: '#445082'
                }
              },
              
              {
                value: 26,
                itemStyle: {
                  color: '#fa79f5'
                }
              },
              {
                value: 28,
                itemStyle: {
                  color: '#8c2efc'
                }
              },
              {
                value: 30,
                itemStyle: {
                  color: '#c479a3'
                }
              },
              {
                value: 24,
                itemStyle: {
                  color: '#faf679'
                }
              },
              {
                value: 36,
                itemStyle: {
                  color: '#829951'
                }
              },
              {
                value: 27,
                itemStyle: {
                  color: '#30972e'
                }
              },
              {
                value: 26,
                itemStyle: {
                  color: '#3a2006'
                }
              },
              {
                value: 27,
                itemStyle: {
                  color: '#e9ad6f'
                }
              },
              {
                value: 32,
                itemStyle: {
                  color: '#84541a'
                }
              },
              {
                value: 16,
                itemStyle: {
                  color: '#ed4b04'
                }
              },
              {
                value: 12,
                itemStyle: {
                  color: '#8f0f1b'
                }
              },
            ],
            type: 'bar'
          }
        ]
      },
    }
  },
  watch: {
    aircraftStats: {
      immediate: true,
      handler: '_applyAircraftStats'
    }
  },
  methods: {
    _applyAircraftStats() {
      if (!this.aircraftStats || this.aircraftStats.length === 0) return;
      var stats = this.aircraftStats.slice(0, 22);
      var names = stats.map(function (s) { return s.name; });
      var s1 = this.options2.series[0];
      var xa = this.options2.xAxis;
      this.options2 = Object.assign({}, this.options2, {
        xAxis: Object.assign({}, xa, { data: names }),
        series: [Object.assign({}, s1, {
          data: stats.map(function (s) {
            return { value: s.value, itemStyle: { color: '#a0e85b' } };
          })
        })]
      });
      this.$forceUpdate();
    },
    qiehuan() {
      this.flag = !this.flag
    }
  }
}
</script>

<style scoped>

#pie{
  width: 100%;
  height: 100%;
  /* background-image: url(../assets/line.png); */
  border: 0.5px solid rgba(255,255,255,0.2);
  background: rgba(255, 255, 255, 0.1);
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