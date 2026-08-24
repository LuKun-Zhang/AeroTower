<template>
  <div id="bar">
    <div class="dragRectTop"></div>
    <div class="title">
      <br>
      <h2>22 架 A319 执飞 632 个航班</h2>
      <br>
      <row>
        <input type="button" value="1" style="margin: 5px; width: 25px; height: 25px; background-color: #a0e85b; border-radius: 50%; border: none">
        <input type="button" value="2" style="margin: 5px; width: 25px; height: 25px; background-color: #1b511d; border-radius: 50%; border: none">
        <input type="button" value="3" style="margin: 5px; width: 25px; height: 25px; background-color: #c6edc5; border-radius: 50%; border: none">
        <input type="button" value="4" style="margin: 5px; width: 25px; height: 25px; background-color: #0f144c; border-radius: 50%; border: none">
        <input type="button" value="5" style="margin: 5px; width: 25px; height: 25px; background-color: #967ff2; border-radius: 50%; border: none">
        <input type="button" value="6" style="margin: 5px; width: 25px; height: 25px; background-color: #803673; border-radius: 50%; border: none">
        <input type="button" value="7" style="margin: 5px; width: 25px; height: 25px; background-color: #bf11af; border-radius: 50%; border: none">
        <input type="button" value="8" style="margin: 5px; width: 25px; height: 25px; background-color: #edcbde; border-radius: 50%; border: none">
        <input type="button" value="9" style="margin: 5px; width: 25px; height: 25px; background-color: #1a119b; border-radius: 50%; border: none">
        </row>
      <row>
        <input type="button" value="10" style="margin: 5px; width: 25px; height: 25px; background-color: #918ea2; border-radius: 50%; border: none">
        <input type="button" value="11" style="margin: 5px; width: 25px; height: 25px; background-color: #445082; border-radius: 50%; border: none">
        <input type="button" value="12" style="margin: 5px; width: 25px; height: 25px; background-color: #fa79f5; border-radius: 50%; border: none">
        <input type="button" value="13" style="margin: 5px; width: 25px; height: 25px; background-color: #8c2efc; border-radius: 50%; border: none">
        <input type="button" value="14" style="margin: 5px; width: 25px; height: 25px; background-color: #c479a3; border-radius: 50%; border: none">
        <input type="button" value="15" style="margin: 5px; width: 25px; height: 25px; background-color: #faf679; border-radius: 50%; border: none">
        <input type="button" value="16" style="margin: 5px; width: 25px; height: 25px; background-color: #829951; border-radius: 50%; border: none">
        <input type="button" value="17" style="margin: 5px; width: 25px; height: 25px; background-color: #30972e; border-radius: 50%; border: none">
        <input type="button" value="18" style="margin: 5px; width: 25px; height: 25px; background-color: #3a2006; border-radius: 50%; border: none">
      </row>
      <row>
        <input type="button" value="19" style="margin: 5px; width: 25px; height: 25px; background-color: #e9ad6f; border-radius: 50%; border: none">
        <input type="button" value="20" style="margin: 5px; width: 25px; height: 25px; background-color: #84541a; border-radius: 50%; border: none">
        <input type="button" value="21" style="margin: 5px; width: 25px; height: 25px; background-color: #ed4b04; border-radius: 50%; border: none">
        <input type="button" value="22" style="margin: 5px; width: 25px; height: 25px; background-color: #8f0f1b; border-radius: 50%; border: none">
      </row>
      <!-- <el-button type="primary" plain > A319 </el-button>
      <el-button type="primary" plain> A320 </el-button> -->
    </div>
    <div class="dragRectBottom"></div>
  </div>
  
</template>

<script>
export default {
  data: function () {
    return {
    }
  },
}
</script>

<style scoped>

#bar{
	/* background-image: url(../assets/line.png); */
  border: 0.5px solid rgba(255,255,255,0.2);
  position: relative;
  background: rgba(255, 255, 255, 0.1);
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