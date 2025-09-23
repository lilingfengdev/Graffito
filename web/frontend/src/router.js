import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Register from './views/Register.vue'
import Layout from './views/Layout.vue'
import Dashboard from './views/Dashboard.vue'
import Audit from './views/Audit.vue'
import SubmissionDetail from './views/SubmissionDetail.vue'
import UserManagement from './views/UserManagement.vue'
import StoredPosts from './views/StoredPosts.vue'

const routes = [
  { path: '/login', component: Login },
  { path: '/register', component: Register },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard,
        meta: { title: '仪表板', icon: 'Odometer' }
      },
      {
        path: 'audit',
        name: 'Audit',
        component: Audit,
        meta: { title: '审核管理', icon: 'Document' }
      },
      {
        path: 'submission/:id',
        name: 'SubmissionDetail',
        component: SubmissionDetail,
        meta: { title: '投稿详情', hidden: true }
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: UserManagement,
        meta: { title: '用户管理', icon: 'User' }
      },
      {
        path: 'stored',
        name: 'StoredPosts',
        component: StoredPosts,
        meta: { title: '暂存区', icon: 'Box' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const isAuthPage = to.path === '/login' || to.path === '/register'
  if (!token && !isAuthPage) {
    next('/login')
  } else if (token && isAuthPage) {
    next('/')
  } else {
    next()
  }
})

export default router

