<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, provide, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import NProgress from 'nprogress'
import { usePWA, useSSENotifications } from '@/composables'

const router = useRouter()

// PWA 功能
const {
  isInstallable,
  isInstalled,
  needsUpdate,
  install: installPWA,
  update: updatePWA
} = usePWA()

// SSE 通知功能
const {
  isConnected: sseConnected,
  isConnecting: sseConnecting,
  initialize: initSSE,
  cleanup: cleanupSSE
} = useSSENotifications()

// 主题管理
const isDark = ref(true)
const theme = ref('dark')

// 主题切换函数
const toggleTheme = () => {
  isDark.value = !isDark.value
  theme.value = isDark.value ? 'dark' : 'light'
  applyTheme()
  localStorage.setItem('theme', theme.value)
}

// 应用主题
const applyTheme = () => {
  const html = document.documentElement
  if (isDark.value) {
    html.classList.add('dark')
    html.classList.remove('light')
  } else {
    html.classList.add('light')
    html.classList.remove('dark')
  }
}

// 初始化主题
const initTheme = () => {
  const savedTheme = localStorage.getItem('theme') || 'dark'
  theme.value = savedTheme
  isDark.value = savedTheme === 'dark'
  applyTheme()
}

// 提供给子组件使用
provide('theme', {
  isDark,
  theme,
  toggleTheme
})

// Setup progress bar for navigation
router.beforeEach((to, from, next) => {
  NProgress.start()
  next()
})

router.afterEach(() => {
  NProgress.done()
})

onMounted(() => {
  initTheme()
  
  // 检查是否已登录，如果已登录则初始化 SSE
  const token = localStorage.getItem('access_token')
  if (token) {
    initSSE()
  }
})

onUnmounted(() => {
  cleanupSSE()
})

// 监听路由变化，在登录后初始化 SSE
watch(() => router.currentRoute.value.path, (newPath) => {
  const token = localStorage.getItem('access_token')
  if (token && !sseConnected.value && !sseConnecting.value) {
    setTimeout(() => {
      initSSE()
    }, 500)
  }
})
</script>

<style>
/* 极简 App.vue 样式 - 所有样式已迁移到设计系统 */

/* Element Plus 主题变量映射 */
:root {
  --el-color-primary: var(--xw-primary);
  --el-color-primary-light-3: var(--xw-primary-light);
  --el-color-primary-light-5: var(--xw-primary-lighter);
  --el-color-primary-light-7: var(--xw-primary-lightest);
  --el-color-success: var(--xw-success);
  --el-color-warning: var(--xw-warning);
  --el-color-danger: var(--xw-danger);
  --el-color-info: var(--xw-info);
}

/* 主题适配 */
html.dark {
  --el-bg-color: var(--xw-bg-secondary);
  --el-bg-color-page: var(--xw-bg-primary);
  --el-text-color-primary: var(--xw-text-primary);
  --el-text-color-regular: var(--xw-text-secondary);
  --el-border-color: var(--xw-border-primary);
  --card-bg: var(--xw-card-bg);
  --sidebar-bg: var(--xw-backdrop-blur);
}

html.light {
  --el-bg-color: var(--xw-bg-primary);
  --el-bg-color-page: var(--xw-bg-primary);
  --el-text-color-primary: var(--xw-text-primary);
  --el-text-color-regular: var(--xw-text-secondary);
  --el-border-color: var(--xw-border-primary);
  --card-bg: var(--xw-card-bg);
  --sidebar-bg: var(--xw-backdrop-blur);
}

/* NProgress 进度条 */
#nprogress .bar {
  background: var(--xw-primary) !important;
  height: 2px !important;
}

/* 页面转场动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
