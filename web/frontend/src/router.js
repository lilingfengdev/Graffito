import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Register from './views/Register.vue'
import Audit from './views/Audit.vue'

const routes = [
  { path: '/', redirect: '/audit' },
  { path: '/login', component: Login },
  { path: '/register', component: Register },
  { path: '/audit', component: Audit }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (!token && to.path !== '/login' && to.path !== '/register') {
    next('/login')
  } else {
    next()
  }
})

export default router

