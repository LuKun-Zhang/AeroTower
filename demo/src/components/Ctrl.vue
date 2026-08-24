<template>
  <div id="bar">
    <div class="dragRectTop"></div>
    <h2 style="text-align:center;font-size:14px;margin:4px 0;">动态航班演示控制</h2>
    <template>
    <div class="block" style="margin: auto;width: 73%;">
      <div class="demonstration" style="font-size:14px">演示时间 &ensp;{{nowtime}}</div>
      <div style="display:flex;align-items:center;gap:4px;margin:4px 0;">
        <span style="font-size:11px;color:#aaa;white-space:nowrap">速度</span>
        <el-button :type="speed===0.5?'warning':'default'" size="mini" @click="setSpeed(0.5)" style="padding:2px 6px;font-size:11px">0.5x</el-button>
        <el-button :type="speed===1?'warning':'default'" size="mini" @click="setSpeed(1)" style="padding:2px 6px;font-size:11px">1x</el-button>
        <el-button :type="speed===2?'warning':'default'" size="mini" @click="setSpeed(2)" style="padding:2px 6px;font-size:11px">2x</el-button>
        <el-button :type="speed===4?'warning':'default'" size="mini" @click="setSpeed(4)" style="padding:2px 6px;font-size:11px">4x</el-button>
      </div>
      <div><el-slider v-model="currentTime" :max="maxSlices" :show-tooltip="false"></el-slider></div>
      
    </div>
    </template>
    <div style="text-align: center;">
      <el-button v-if="this.flag === true" type="success" @click="start" style="width:50px;height:24px;padding:0%;font-size:12px">启动</el-button>
      <el-button v-else type="warning" @click="stop" style="width:50px;height:24px;padding:0%;font-size:12px">暂停</el-button>
      <el-button type="primary" @click="reset" style="width:50px;height:24px;padding:0%;font-size:12px">重置</el-button>
    </div>
    <div class="dragRectBottom"></div>
  </div>
</template>

<script>
import ECharts from "@/components/ECharts";

var Time = 0;
export default {
  components: {
    ECharts,
  },
  props: {
    maxSlices: { type: Number, default: 657 }
  },
  data: function () {
    return {
      currentTime: 37,
      updateTime:null,
      nowtime:"",
      flag: false,
      speed: 1,
    }
  },
  methods: {
    setSpeed(s) {
      this.speed = s;
      if (!this.flag) {
        // 播放中则重启定时器
        this._restartInterval();
      }
    },
    _getInterval() {
      return Math.round(3000 / this.speed);
    },
    _restartInterval() {
      if (this.updateTime) {
        clearInterval(this.updateTime);
        var that = this;
        this.updateTime = setInterval(function() {
          that.currentTime++;
          if (that.currentTime >= that.maxSlices) that.currentTime = 0;
        }, that._getInterval());
      }
    },
    start() {
      var that = this;
      this.updateTime = setInterval(function() {
        that.currentTime++;
        if (that.currentTime >= that.maxSlices) that.currentTime = 0;
      }, that._getInterval());
      this.flag = !this.flag;
    },
    stop(){
      clearInterval(this.updateTime)
      this.updateTime = null;
      this.flag = !this.flag
    },
    reset() {
      this.currentTime = 37;
    },
  },
  watch: {
    currentTime: function () {
      this.$emit("changeTime", this.currentTime);
      let myDate = new Date("2020-11-30 0:0:0");
      myDate.setMinutes(myDate.getMinutes() + this.currentTime * 15);
      let year = myDate.getFullYear();
      let month = myDate.getMonth() + 1;
      let date = myDate.getDate();
      let hour =
        myDate.getHours() < 10 ? "0" + myDate.getHours() : myDate.getHours();
      let minute =
        myDate.getMinutes() < 10
          ? "0" + myDate.getMinutes()
          : myDate.getMinutes();
      let second =
        myDate.getSeconds() < 10
          ? "0" + myDate.getSeconds()
          : myDate.getSeconds();
      this.nowtime = `${year}年${month}月${date}日${hour}:${minute}:${second}`;
    },
  },
  created() {
    var that = this;
    this.updateTime = setInterval(function() {
      that.currentTime++;
      if (that.currentTime >= that.maxSlices) that.currentTime = 0;
    }, that._getInterval());
  },
  beforeDestroy() {
    if (this.updateTime) clearInterval(this.updateTime);
  },
};
</script>

<style scoped>
#bar {
  /* background-image: url(../assets/line.png); */
  border: 0.5px solid rgba(255, 255, 255, 0.2);
  position: relative;
  background: rgba(255, 255, 255, 0.1);
}

.title {
  text-align: center;
  position: relative;
}
.slider {
  position: absolute;
  top: 50%;
  left: 50%;
  height: 100px;
  margin: -50px 0 0 -50px;
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