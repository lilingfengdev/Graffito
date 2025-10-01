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
    // 延迟一下以确保登录流程完成
    setTimeout(() => {
      initSSE()
    }, 500)
  }
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

/* ===== Element Plus 组件深度优化 ===== */

/* 卡片组件 */
.el-card {
  background: var(--card-bg) !important;
  border: 1px solid var(--xw-card-border) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: var(--xw-radius-xl) !important;
  transition: var(--xw-transition-transform), var(--xw-transition-colors), box-shadow 0.2s var(--xw-ease-out) !important;
  transform: translateZ(0);
}

.el-card:hover {
  transform: translateY(-2px) translateZ(0);
  box-shadow: var(--xw-shadow-hover) !important;
}

/* 按钮组件 - 主按钮 */
.el-button--primary {
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-dark)) !important;
  border: none !important;
  border-radius: var(--xw-radius-lg) !important;
  font-weight: 500 !important;
  transition: var(--xw-transition-transform), var(--xw-transition-colors), box-shadow 0.2s var(--xw-ease-out) !important;
  transform: translateZ(0);
  will-change: transform;
}

.el-button--primary:hover {
  background: linear-gradient(135deg, var(--xw-primary-light), var(--xw-primary)) !important;
  box-shadow: var(--xw-shadow-md) !important;
  transform: translateY(-1px) translateZ(0) !important;
}

.el-button--primary:active {
  transform: translateY(0) scale(0.98) translateZ(0) !important;
}

.el-button--primary:focus {
  box-shadow: 0 0 0 3px var(--xw-focus-ring) !important;
}

/* 深色模式按钮增强 */
html.dark .el-button--primary:hover {
  box-shadow: var(--xw-shadow-md), 0 0 15px rgba(99, 102, 241, 0.4) !important;
}

/* 通用按钮优化 */
.el-button {
  border-radius: var(--xw-radius-lg) !important;
  font-weight: 500 !important;
  transition: var(--xw-transition-transform), var(--xw-transition-colors) !important;
  transform: translateZ(0);
}

.el-button:hover {
  transform: translateY(-1px) translateZ(0);
}

.el-button:active {
  transform: translateY(0) scale(0.98) translateZ(0);
}

/* 输入框组件 */
.el-input__wrapper {
  border-radius: var(--xw-radius-lg) !important;
  transition: var(--xw-transition-colors), box-shadow 0.2s var(--xw-ease-out) !important;
  background: var(--xw-bg-tertiary) !important;
}

.el-input__wrapper:hover {
  border-color: var(--xw-border-secondary) !important;
}

.el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset, 0 0 0 3px var(--xw-focus-ring) !important;
  border-color: var(--xw-primary) !important;
}

.el-select .el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset, 0 0 0 3px var(--xw-focus-ring) !important;
}

/* 深色模式输入框增强 */
html.dark .el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset, 0 0 0 3px var(--xw-focus-ring), 0 0 10px rgba(99, 102, 241, 0.2) !important;
}

/* 文本域 */
.el-textarea__inner {
  border-radius: var(--xw-radius-lg) !important;
  transition: var(--xw-transition-colors), box-shadow 0.2s var(--xw-ease-out) !important;
  background: var(--xw-bg-tertiary) !important;
}

.el-textarea__inner:hover {
  border-color: var(--xw-border-secondary) !important;
}

.el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset, 0 0 0 3px var(--xw-focus-ring) !important;
  border-color: var(--xw-primary) !important;
}

html.dark .el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--xw-primary) inset, 0 0 0 3px var(--xw-focus-ring), 0 0 10px rgba(99, 102, 241, 0.2) !important;
}

/* 下拉菜单 - 深度优化 */
.el-dropdown-menu {
  background: var(--xw-card-bg) !important;
  border: 1px solid var(--xw-card-border) !important;
  border-radius: var(--xw-radius-xl) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--xw-shadow-xl) !important;
  padding: var(--xw-space-2) !important;
  min-width: 180px;
  animation: xw-fade-scale-in 0.2s var(--xw-ease-out);
}

html.dark .el-dropdown-menu {
  box-shadow: var(--xw-shadow-xl), 0 0 30px rgba(0, 0, 0, 0.5) !important;
  border-color: rgba(99, 102, 241, 0.2) !important;
}

.el-dropdown-menu__item {
  border-radius: var(--xw-radius-lg) !important;
  margin: var(--xw-space-1) 0 !important;
  padding: var(--xw-space-3) var(--xw-space-4) !important;
  transition: var(--xw-transition-transform), var(--xw-transition-colors) !important;
  font-weight: 500;
  position: relative;
  overflow: hidden;
  display: flex !important;
  align-items: center !important;
  gap: var(--xw-space-2) !important;
}

.el-dropdown-menu__item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--xw-primary);
  transform: scaleY(0);
  transition: transform 0.2s var(--xw-ease-out);
  border-radius: 0 3px 3px 0;
}

.el-dropdown-menu__item:hover {
  background: var(--xw-gradient-highlight) !important;
  color: var(--xw-primary) !important;
  transform: translateX(3px);
}

.el-dropdown-menu__item:hover::before {
  transform: scaleY(1);
}

html.dark .el-dropdown-menu__item:hover {
  background: rgba(99, 102, 241, 0.15) !important;
  box-shadow: inset 0 0 10px rgba(99, 102, 241, 0.1);
}

.el-dropdown-menu__item--divided {
  margin-top: var(--xw-space-3) !important;
  border-top: 1px solid var(--xw-border-primary) !important;
  padding-top: var(--xw-space-4) !important;
}

.el-dropdown-menu__item .el-icon {
  margin-right: 0 !important;
  transition: transform 0.2s var(--xw-ease-out);
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  flex-shrink: 0 !important;
}

.el-dropdown-menu__item:hover .el-icon {
  transform: scale(1.1);
}

/* 选择框下拉菜单 */
.el-select-dropdown {
  background: var(--xw-card-bg) !important;
  border: 1px solid var(--xw-card-border) !important;
  border-radius: var(--xw-radius-xl) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--xw-shadow-xl) !important;
  padding: var(--xw-space-2) !important;
}

html.dark .el-select-dropdown {
  box-shadow: var(--xw-shadow-xl), 0 0 30px rgba(0, 0, 0, 0.5) !important;
  border-color: rgba(99, 102, 241, 0.2) !important;
}

.el-select-dropdown__item {
  border-radius: var(--xw-radius-lg) !important;
  margin: var(--xw-space-1) 0 !important;
  padding: var(--xw-space-3) var(--xw-space-4) !important;
  transition: var(--xw-transition-colors) !important;
  display: flex !important;
  align-items: center !important;
}

.el-select-dropdown__item:hover {
  background: var(--xw-gradient-highlight) !important;
  color: var(--xw-primary) !important;
}

.el-select-dropdown__item.is-selected {
  background: var(--xw-primary-lightest) !important;
  color: var(--xw-primary) !important;
  font-weight: 600;
}

html.dark .el-select-dropdown__item.is-selected {
  background: rgba(99, 102, 241, 0.2) !important;
}

/* 对话框 */
.el-dialog {
  background: var(--xw-card-bg) !important;
  border: 1px solid var(--xw-card-border) !important;
  border-radius: var(--xw-radius-2xl) !important;
  backdrop-filter: blur(20px);
  box-shadow: var(--xw-shadow-2xl) !important;
}

.el-dialog__header {
  border-bottom: 1px solid var(--xw-border-primary) !important;
}

/* 标签页 */
.el-tabs__item {
  transition: var(--xw-transition-colors) !important;
}

.el-tabs__item:hover {
  color: var(--xw-primary) !important;
}

.el-tabs__item.is-active {
  color: var(--xw-primary) !important;
}

/* 分页器 */
.el-pagination button,
.el-pagination .el-pager li {
  background: var(--xw-bg-secondary) !important;
  border-radius: var(--xw-radius) !important;
  transition: var(--xw-transition-colors) !important;
}

.el-pagination button:hover,
.el-pagination .el-pager li:hover {
  color: var(--xw-primary) !important;
}

.el-pagination .el-pager li.is-active {
  background: var(--xw-primary) !important;
  color: white !important;
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

/* ============================================
   移动端全局优化
   ============================================ */

/* 移动端视口设置 */
@media (max-width: 768px) {
  html {
    /* 防止 iOS 字体自动调整 */
    -webkit-text-size-adjust: 100%;
    text-size-adjust: 100%;
    /* 优化触摸滚动 */
    -webkit-overflow-scrolling: touch;
  }
  
  body {
    /* 防止橡皮筋效果 */
    overflow-x: hidden;
    overscroll-behavior-x: none;
  }
  
  /* 优化移动端卡片样式 */
  .el-card {
    margin-bottom: 12px !important;
    border-radius: var(--xw-radius-xl) !important;
  }
  
  .el-card__body {
    padding: 16px !important;
  }
  
  /* 优化移动端表格 */
  .el-table {
    font-size: 14px !important;
  }
  
  .el-table th,
  .el-table td {
    padding: 10px 8px !important;
  }
  
  .el-table__header th {
    font-size: 13px !important;
  }
  
  /* 优化移动端分页 */
  .el-pagination {
    padding: 12px 0 !important;
    justify-content: center !important;
  }
  
  .el-pagination button,
  .el-pagination .el-pager li {
    min-width: 32px !important;
    min-height: 32px !important;
    font-size: 14px !important;
  }
  
  /* 优化移动端标签 */
  .el-tag {
    padding: 4px 10px !important;
    font-size: 13px !important;
  }
  
  /* 优化移动端消息提示 */
  .el-message {
    min-width: 300px !important;
    max-width: calc(100vw - 32px) !important;
    border-radius: var(--xw-radius-lg) !important;
  }
  
  .el-message-box {
    width: 90% !important;
    max-width: 400px !important;
    border-radius: var(--xw-radius-xl) !important;
  }
  
  /* 优化移动端气泡确认框 */
  .el-popconfirm {
    max-width: calc(100vw - 32px) !important;
  }
  
  /* 优化移动端下拉菜单 */
  .el-dropdown-menu {
    max-width: calc(100vw - 32px) !important;
  }
  
  /* 优化移动端选择器 */
  .el-select-dropdown {
    max-width: calc(100vw - 32px) !important;
  }
  
  /* 优化移动端日期选择器 */
  .el-date-picker,
  .el-picker-panel {
    max-width: calc(100vw - 16px) !important;
  }
  
  /* 优化移动端抽屉 */
  .el-drawer {
    max-width: 100vw !important;
  }
  
  .el-drawer__body {
    padding: 16px !important;
  }
}

/* 超小屏幕优化 */
@media (max-width: 480px) {
  /* 优化极小屏幕的卡片 */
  .el-card__body {
    padding: 12px !important;
  }
  
  /* 优化极小屏幕的表格 */
  .el-table {
    font-size: 13px !important;
  }
  
  .el-table th,
  .el-table td {
    padding: 8px 6px !important;
  }
  
  /* 优化极小屏幕的按钮 */
  .el-button {
    padding: 10px 16px !important;
    font-size: 14px !important;
  }
  
  .el-button--small {
    padding: 8px 12px !important;
    font-size: 13px !important;
  }
  
  .el-button--large {
    padding: 12px 20px !important;
    font-size: 15px !important;
  }
  
  /* 优化极小屏幕的消息提示 */
  .el-message {
    min-width: 260px !important;
  }
}

/* 触摸设备优化 */
@media (hover: none) and (pointer: coarse) {
  /* 增大可触摸元素的点击区域 */
  button,
  a,
  .el-button,
  .el-link,
  .el-checkbox,
  .el-radio,
  .el-switch {
    min-width: 44px;
    min-height: 44px;
  }
  
  /* 移除悬停效果（触摸设备不需要） */
  .el-button:hover,
  .el-link:hover,
  .el-card:hover {
    transform: none !important;
  }
  
  /* 优化触摸反馈 */
  .el-button:active,
  .el-link:active {
    transform: scale(0.96) !important;
    transition: transform 0.1s ease !important;
  }
  
  /* 圆形按钮优化 */
  .el-button.is-circle {
    min-width: 44px !important;
    min-height: 44px !important;
    padding: 0 !important;
  }
  
  /* 图标按钮优化 */
  .el-button.is-text,
  .el-button.is-link {
    min-height: 40px;
    padding: 8px 12px;
  }
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
  
  /* 触摸友好的交互 - 按钮优化 */
  .el-button {
    min-height: 44px;
    padding: 12px 20px;
    font-size: 15px;
    touch-action: manipulation;
    border-radius: var(--xw-radius-lg) !important;
    font-weight: 500;
    letter-spacing: 0.3px;
  }
  
  .el-button--small {
    min-height: 36px;
    padding: 8px 14px;
    font-size: 14px;
  }
  
  .el-button--large {
    min-height: 48px;
    padding: 14px 24px;
    font-size: 16px;
  }
  
  /* 按钮图标间距 */
  .el-button .el-icon {
    margin-right: 6px;
  }
  
  .el-button .el-icon + span {
    margin-left: 2px;
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
  
  .el-dialog__footer {
    padding: 16px 24px !important;
    display: flex;
    flex-direction: column-reverse;
    gap: 12px;
  }
  
  .el-dialog__footer .el-button {
    width: 100%;
    margin: 0 !important;
    min-height: 44px;
  }
  
  /* 按钮组移动端优化 */
  .el-button-group {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  
  .el-button-group .el-button {
    width: 100%;
    margin: 0 !important;
    border-radius: var(--xw-radius-lg) !important;
  }
  
  .el-button-group .el-button:first-child,
  .el-button-group .el-button:last-child {
    border-radius: var(--xw-radius-lg) !important;
  }
  
  /* 表单按钮移动端优化 */
  .el-form-item__content .el-button + .el-button {
    margin-left: 0 !important;
    margin-top: 10px;
  }
  
  /* Popconfirm 按钮优化 */
  .el-popconfirm__action {
    display: flex;
    flex-direction: column-reverse;
    gap: 8px;
  }
  
  .el-popconfirm__action .el-button {
    width: 100%;
    margin: 0 !important;
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
    min-height: 44px;
    padding: 11px 18px;
    font-size: 14px;
  }
  
  .el-button--small {
    min-height: 36px;
    padding: 8px 12px;
    font-size: 13px;
  }
  
  /* 超小屏对话框按钮优化 */
  .el-dialog__footer {
    padding: 12px 20px !important;
    gap: 10px;
  }
  
  .el-dialog__footer .el-button {
    min-height: 48px;
    font-size: 15px;
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

