import Vue from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import ElementUI from 'element-ui';
import 'element-ui/lib/theme-chalk/index.css';

Vue.config.productionTip = false
Vue.use(ElementUI);

// 全局缩短提示框默认显示时间（从 3000ms → 2000ms），避免长时间遮挡操作栏
const _msg = Vue.prototype.$message
Vue.prototype.$message = function (opts) {
  const options = typeof opts === 'string' ? { message: opts } : { ...opts }
  if (!options.duration && options.duration !== 0) {
    options.duration = 2000
  }
  return _msg(options)
}
;['success', 'warning', 'info', 'error'].forEach(type => {
  const _fn = _msg[type]
  Vue.prototype.$message[type] = function (msgOrOpts) {
    const options = typeof msgOrOpts === 'string' ? { message: msgOrOpts } : { ...msgOrOpts }
    if (!options.duration && options.duration !== 0) {
      options.duration = 2000
    }
    return _fn(options)
  }
})

// 全局自定义指令
Vue.directive('title', {
  inserted: function (el) {
    document.title = el.dataset.title
  },
  componentUpdated: function (el) {
    document.title = el.dataset.title
  }
})

new Vue({
  router,
  store,
  render: h => h(App)
}).$mount('#app')
