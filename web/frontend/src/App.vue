<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup>
import { onMounted, provide, ref } from 'vue'
import { useRouter } from 'vue-router'
import NProgress from 'nprogress'

const router = useRouter()

// 主题管理
const isDark = ref(true)
const theme = ref('dark')

// 主题切换函数
const toggleTheme = () => {
  isDark.value = !isDark.value
  theme.value = isDark.value ? 'dark' : 'light'
  applyTheme()
  // 保存到localStorage
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
})
</script>

<style>
/* Global styles */
body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  min-height: 100vh;
  transition: background 0.3s ease, color 0.3s ease;
}

* {
  box-sizing: border-box;
}

/* 基础颜色定义 - 与设计系统保持一致 */
:root {
  --el-color-primary: var(--xw-primary);
  --el-color-primary-light-3: var(--xw-primary-light);
  --el-color-primary-light-5: var(--xw-primary-lighter);
  --el-color-primary-light-7: var(--xw-primary-lightest);
  --el-color-primary-light-8: var(--xw-primary-lightest);
  --el-color-primary-light-9: var(--xw-primary-lightest);
  --el-color-primary-dark-2: var(--xw-primary-dark);
  --el-color-success: var(--xw-success);
  --el-color-warning: var(--xw-warning);
  --el-color-danger: var(--xw-danger);
  --el-color-error: var(--xw-danger);
  --el-color-info: var(--xw-info);
}

/* 深色主题 - 使用设计系统变量 */
html.dark {
  --el-bg-color: var(--xw-bg-secondary);
  --el-bg-color-page: var(--xw-bg-primary);
  --el-bg-color-overlay: var(--xw-bg-tertiary);
  
  --el-text-color-primary: var(--xw-text-primary);
  --el-text-color-regular: var(--xw-text-secondary);
  --el-text-color-secondary: var(--xw-text-tertiary);
  --el-text-color-placeholder: var(--xw-text-quaternary);
  
  --el-border-color: var(--xw-border-primary);
  --el-border-color-light: var(--xw-border-secondary);
  --el-border-color-lighter: var(--xw-border-tertiary);
  --el-border-color-extra-light: var(--xw-bg-secondary);
  
  --el-fill-color: var(--xw-bg-tertiary);
  --el-fill-color-light: var(--xw-bg-quaternary);
  --el-fill-color-lighter: var(--xw-bg-tertiary);
  --el-fill-color-extra-light: var(--xw-bg-secondary);
  
  /* 自定义背景渐变 */
  --app-bg-gradient: var(--xw-gradient-primary);
  --card-bg: var(--xw-card-bg);
  --sidebar-bg: var(--xw-backdrop-blur);
}

html.dark body {
  background: var(--app-bg-gradient);
}

/* 亮色主题 - 使用设计系统变量 */
html.light {
  --el-bg-color: var(--xw-bg-primary);
  --el-bg-color-page: var(--xw-bg-primary);
  --el-bg-color-overlay: var(--xw-bg-primary);
  
  --el-text-color-primary: var(--xw-text-primary);
  --el-text-color-regular: var(--xw-text-secondary);
  --el-text-color-secondary: var(--xw-text-tertiary);
  --el-text-color-placeholder: var(--xw-text-quaternary);
  
  --el-border-color: var(--xw-border-primary);
  --el-border-color-light: var(--xw-border-secondary);
  --el-border-color-lighter: var(--xw-border-secondary);
  --el-border-color-extra-light: var(--xw-border-tertiary);
  
  --el-fill-color: var(--xw-bg-secondary);
  --el-fill-color-light: var(--xw-bg-tertiary);
  --el-fill-color-lighter: var(--xw-border-secondary);
  --el-fill-color-extra-light: var(--xw-bg-secondary);
  
  /* 自定义背景渐变 */
  --app-bg-gradient: var(--xw-gradient-primary);
  --card-bg: var(--xw-card-bg);
  --sidebar-bg: var(--xw-backdrop-blur);
}

html.light body {
  background: var(--app-bg-gradient);
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

/* 深色主题滚动条 */
html.dark ::-webkit-scrollbar-track {
  background: var(--el-bg-color-page);
}

html.dark ::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 3px;
}

html.dark ::-webkit-scrollbar-thumb:hover {
  background: var(--el-border-color-light);
}

/* 浅色主题滚动条 */
html.light ::-webkit-scrollbar-track {
  background: var(--el-fill-color-extra-light);
}

html.light ::-webkit-scrollbar-thumb {
  background: var(--el-border-color);
  border-radius: 3px;
}

html.light ::-webkit-scrollbar-thumb:hover {
  background: var(--el-border-color-light);
}

/* Progress bar customization */
#nprogress .bar {
  background: var(--el-color-primary) !important;
  height: 3px !important;
}

#nprogress .spinner-icon {
  border-top-color: var(--el-color-primary) !important;
  border-left-color: var(--el-color-primary) !important;
}

/* Element Plus component overrides - 使用设计系统 */
.el-card {
  background: var(--card-bg) !important;
  border: 1px solid var(--xw-card-border) !important;
  backdrop-filter: blur(10px);
  border-radius: var(--xw-radius-lg) !important;
}

.el-button--primary {
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-light)) !important;
  border: none !important;
  border-radius: var(--xw-radius) !important;
  font-weight: 500 !important;
  transition: var(--xw-transition) !important;
}

.el-button--primary:hover {
  background: linear-gradient(135deg, var(--xw-primary-dark), var(--xw-primary)) !important;
  box-shadow: var(--xw-shadow-md) !important;
}

.el-button--primary:focus {
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.3) !important;
}

.el-button {
  border-radius: var(--xw-radius) !important;
  font-weight: 500 !important;
  transition: var(--xw-transition) !important;
}

.el-input__wrapper {
  border-radius: var(--xw-radius) !important;
  transition: var(--xw-transition) !important;
}

.el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset !important;
}

.el-select .el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset !important;
}

.el-textarea__inner {
  border-radius: var(--xw-radius) !important;
  transition: var(--xw-transition) !important;
}

.el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset !important;
}

/* 表格样式 - 深色主题 */
html.dark .el-table {
  background: transparent !important;
}

html.dark .el-table tr {
  background: rgba(30, 41, 59, 0.5) !important;
}

html.dark .el-table--striped .el-table__body tr.el-table__row--striped td {
  background: rgba(71, 85, 105, 0.2) !important;
}

/* 表格样式 - 浅色主题 */
html.light .el-table {
  background: transparent !important;
}

html.light .el-table tr {
  background: rgba(255, 255, 255, 0.8) !important;
}

html.light .el-table--striped .el-table__body tr.el-table__row--striped td {
  background: rgba(249, 250, 251, 0.8) !important;
}

/* Loading and transitions */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.3s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

/* 移动端全局样式 */
@media (max-width: 768px) {
  /* 基础响应式设置 */
  html {
    -webkit-text-size-adjust: 100%;
    -ms-text-size-adjust: 100%;
  }
  
  body {
    font-size: 14px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  
  /* 触摸友好的交互 */
  .el-button {
    min-height: 36px;
    touch-action: manipulation;
  }
  
  .el-input__inner {
    font-size: 16px !important; /* 防止iOS缩放 */
    min-height: 36px;
  }
  
  .el-select .el-input__inner {
    font-size: 16px !important;
  }
  
  .el-textarea__inner {
    font-size: 16px !important;
  }
  
  /* 表格移动端优化 */
  .el-table {
    border: 1px solid var(--el-border-color-light);
    border-radius: 8px;
    overflow: hidden;
  }
  
  .el-table .el-table__cell {
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
  
  /* 卡片移动端间距 */
  .el-card {
    margin-bottom: 16px;
    border-radius: 12px;
  }
  
  /* 对话框移动端优化 */
  .el-dialog {
    border-radius: 16px !important;
    margin: 8vh auto !important;
  }
  
  .el-dialog__header {
    padding: 20px 24px 16px;
  }
  
  .el-dialog__body {
    padding: 0 24px 20px;
  }
  
  /* 消息提示移动端优化 */
  .el-message {
    min-width: 280px;
    max-width: 90vw;
  }
  
  /* 分页器移动端优化 */
  .el-pagination {
    padding: 16px 0;
  }
  
  .el-pagination .el-pager {
    margin: 0 8px;
  }
  
  /* 滚动条移动端优化 */
  ::-webkit-scrollbar {
    width: 4px;
    height: 4px;
  }
}

/* 超小屏幕优化 */
@media (max-width: 480px) {
  body {
    font-size: 13px;
  }
  
  .el-button {
    min-height: 32px;
    font-size: 13px;
  }
  
  .el-card {
    margin-bottom: 12px;
    border-radius: 8px;
  }
  
  .el-dialog {
    border-radius: 12px !important;
    margin: 5vh auto !important;
  }
  
  .el-dialog__header {
    padding: 16px 20px 12px;
  }
  
  .el-dialog__body {
    padding: 0 20px 16px;
  }
  
  .el-message {
    min-width: 240px;
    font-size: 13px;
  }
  
  /* 隐藏滚动条 */
  ::-webkit-scrollbar {
    display: none;
  }
}
</style>

