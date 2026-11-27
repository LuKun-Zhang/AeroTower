import Vue from 'vue'
import VueRouter from 'vue-router'
import Login from '../views/Login.vue'

Vue.use(VueRouter)

const routes = [
  {
    path: '/intelligence',
    name: 'IntelligenceCenter',
    component: () => import('../views/IntelligenceCenter.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/analysis/:id',
    name: 'AnalysisApp',
    component: () => import('../views/AnalysisApp.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/plane-preview',
    name: 'PlaneModelPreview',
    component: () => import('../views/PlaneModelPreview.vue')
  },
  {
    path: '/weather',
    name: 'WeatherView',
    component: () => import('../views/WeatherView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/simulation-hub',
    name: 'SimulationHub',
    component: () => import('../views/SimulationHub.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/mountain-preview',
    name: 'MountainPreview',
    component: () => import('../views/MountainPreview.vue')
  },
  {
    path: '/paxflow',
    name: 'TerminalFlowView',
    component: () => import('../views/TerminalFlowView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/traffic-input',
    name: 'TrafficInput',
    component: () => import('../views/TrafficInput.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/schedule-overview',
    name: 'ScheduleOverview',
    component: () => import('../views/ScheduleOverview.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/passenger-lookup',
    name: 'PassengerLookup',
    component: () => import('../views/PassengerLookup.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/flight/:flightId/passengers',
    name: 'FlightPassengers',
    component: () => import('../views/FlightPassengers.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/boundary-docs',
    name: 'BoundaryDocs',
    component: () => import('../views/BoundaryDocs.vue'),
    meta: { requiresAuth: true }
  }
]

const router = new VueRouter({
  routes
})

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, from, next) => {
  const user = localStorage.getItem('current_user')
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!user) {
      next({ name: 'Login' })
    } else {
      next()
    }
  } else if (to.name === 'Login' && user) {
    // 已登录用户访问登录页，自动跳转首页
    const userData = JSON.parse(user)
    next({ name: 'Home', params: { username: userData.username } })
  } else {
    next()
  }
})

export default router
