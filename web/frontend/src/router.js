import { createRouter, createWebHistory } from 'vue-router'
import api from './api'

// 路由懒加载，降低首屏体积
const Login = () => import('./views/Login.vue')
const Register = () => import('./views/Register.vue')
const Layout = () => import('./views/Layout.vue')
const Dashboard = () => import('./views/Dashboard.vue')
const Audit = () => import('./views/Audit.vue')
const SubmissionDetail = () => import('./views/SubmissionDetail.vue')
const UserManagement = () => import('./views/UserManagement.vue')
const StoredPosts = () => import('./views/StoredPosts.vue')
const LogsManagement = () => import('./views/LogsManagement.vue')
const FeedbackManagement = () => import('./views/FeedbackManagement.vue')
const ReportManagement = () => import('./views/ReportManagement.vue')
const NotFound = () => import('./views/NotFound.vue')

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
      },
      {
        path: 'logs',
        name: 'LogsManagement',
        component: LogsManagement,
        meta: { title: '系统日志', icon: 'Memo', requiresSuperAdmin: true }
      },
      {
        path: 'feedbacks',
        name: 'FeedbackManagement',
        component: FeedbackManagement,
        meta: { title: '反馈管理', icon: 'ChatDotRound' }
      },
      {
        path: 'reports',
        name: 'ReportManagement',
        component: ReportManagement,
        meta: { title: '举报审核', icon: 'Warning' }
      }
    ]
  },
  // 404 兜底路由
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: NotFound, meta: { title: '未找到', hidden: true } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('access_token') || localStorage.getItem('token')
  const isAuthPage = to.path === '/login' || to.path === '/register'
  
  if (!token && !isAuthPage) {
    next('/login')
  } else if (token && isAuthPage) {
    next('/')
  } else if (token && to.meta.requiresSuperAdmin) {
    // 检查超级管理员权限
    try {
      const userStr = localStorage.getItem('user')
      let user = null
      
      if (userStr) {
        user = JSON.parse(userStr)
      } else {
        // 如果没有用户信息，尝试从 API 获取
        const { data } = await api.get('/auth/me')
        localStorage.setItem('user', JSON.stringify(data))
        user = data
      }
      
      // 检查超级管理员权限
      if (!user.is_superadmin) {
        next('/')
        return
      }
      
      next()
    } catch (error) {
      console.error('权限检查失败:', error)
      next('/')
    }
  } else {
    next()
  }
})

// 动态设置页面标题
router.afterEach((to) => {
  const baseTitle = 'Graffito 审核后台'
  if (to.meta && to.meta.title) {
    document.title = `${to.meta.title} - ${baseTitle}`
  } else {
    document.title = baseTitle
  }
})

export default router

