<template>
  <div ref='echarts' :style="size">
  </div>
</template>

<script>
import * as echarts from 'echarts'
export default {
  name: 'ECharts',
  props: {
    options: Object,
    size: Object
  },
  mounted () {
    // 首先获取div
    // var mainDiv = document.getElementById('main')
    // 基于准备好的dom，初始化echarts实例
    this.myChart = echarts.init(this.$refs.echarts);
    // 使用刚指定的配置项和数据显示图表。
    this.myChart.setOption(this.options);
  },
  data: function () {
    return {
      myChart: {}
    }
  },
  watch: {
    // 监听options改变，重新生成图表，动态刷新
    options: {
      handler: function (val) {
        if (!val) return;
        this.myChart.setOption(val, true);  // notMerge: true = 完全替换
      },
      deep: true
    }
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped lang="scss">
h3 {
  margin: 40px 0 0;
}
ul {
  list-style-type: none;
  padding: 0;
}
li {
  display: inline-block;
  margin: 0 10px;
}
a {
  color: #42b983;
}
</style>
