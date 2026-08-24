<template>
  <div id="ver-bar" :style="size">
    <div class="dragRectTop"></div>
    <e-charts :size="size" :options="options" />
    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import ECharts from '@/components/ECharts'
var data = [70, 56, 66, 95, 60]
var titlename = ["拉萨-哈尔滨", "西安-广州", "西安-北京", "西宁-北京", "西安-拉萨"]
var valdata = [702, 350, 610, 750, 920]
export default {
  components: {
    ECharts
  },
  data: function () {
    return {
      options: {
        title: {
          text: '当前航班运行情况',
          left: "center",
          top: "20px",
          textStyle: {
            color: "#fff"
          }
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        grid: {
          top: "20%",
          left: '10%',
          right: '10%',
          bottom: '5%',
          containLabel: true
        },
        xAxis: {
          show: false
        },
        yAxis: [
          {
            max: 5,
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
              fontSize: "14"
            }
          },
          {
            animationDuration: 300,
            animationDurationUpdate: 300,
            max: 5,
            show: true,
            data: valdata,
            inverse: true,
            axisLabel: {
              color: "#fff",
              fontSize: "12"
            },
            axisLine: {
              show: false
            },
            splitLine: {
              show: false
            },
            axisTick: {
              show: false
            }
          }
        ],
        series: [
          {
            realtimeSort: true, //柱状图自动排序，排序自动让Y轴名字跟着数据动
            name: "条",
            type: 'bar',
            yAxisIndex: 0,
            data: data,
            barGategoryGap: 70,
            barWidth: 15,
            itemStyle: {
              normal: {
                barBorderRadius: 15,
                // params当前item
                color: "#ffa502"
              }
            },
            label: {
              normal: {
                show: true,
                valueAnimation: true, 
                position: "inside",
                formatter: "{c}%",
                color: "#303F9F",
              }
            }
          },
          {
            name: "框",
            type: 'bar',
            yAxisIndex: 1,
            data: [100, 100, 100, 100, 100],
            barGategoryGap: 50,
            barWidth: 15,
            itemStyle: {
              normal: {
                barBorderRadius: 15,
                // params当前item
                color: "none",
                borderColor: "#FF9800",
                borderWidth: 1
              }
            }
          }
        ]
      },
      size: {
        width: '100%',
        height: '3.875rem'
      }
    }
  }
}
</script>

<style scoped>

#ver-bar{
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