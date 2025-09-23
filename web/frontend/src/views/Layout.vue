<template>
  <el-container class="layout-container">
    <!-- 移动端遮罩层 -->
    <div 
      v-if="isMobile && !collapsed" 
      class="mobile-overlay" 
      @click="toggleCollapse"
    ></div>
    
    <!-- 侧边栏 -->
    <el-aside 
      :width="isMobile ? '280px' : (collapsed ? '64px' : '250px')" 
      class="sidebar"
      :class="{ 'mobile': isMobile, 'mobile-hidden': isMobile && collapsed }"
    >
      <div class="logo-container" :class="{ 'collapsed': collapsed }">
        <div class="logo" v-if="!collapsed">
          <el-icon size="28" color="#6366f1"><Document /></el-icon>
          <span class="logo-text">XWall</span>
        </div>
        <div class="logo-collapsed" v-else>
          <el-icon size="28" color="#6366f1"><Document /></el-icon>
        </div>
        <el-button 
          :icon="collapsed ? Expand : Fold" 
          text 
          @click="toggleCollapse"
          class="collapse-btn"
          :class="{ 'collapsed': collapsed }"
        />
      </div>
      
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :unique-opened="true"
        router
        background-color="transparent"
        text-color="#cbd5e1"
        active-text-color="#6366f1"
        class="nav-menu"
      >
        <el-menu-item 
          v-for="route in menuRoutes" 
          :key="route.path" 
          :index="'/' + route.path"
          class="nav-item"
        >
          <el-icon><component :is="route.meta.icon" /></el-icon>
          <template #title>{{ route.meta.title }}</template>
        </el-menu-item>
      </el-menu>
      
      <!-- 用户信息 -->
      <div class="user-section">
        <el-dropdown placement="top-start" @command="handleUserCommand">
          <div class="user-info">
            <el-avatar :size="32" style="background-color: #6366f1;">
              {{ userInitial }}
            </el-avatar>
            <span v-show="!collapsed" class="username">{{ user?.display_name || user?.username }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon>
                个人信息
              </el-dropdown-item>
              <el-dropdown-item command="invite" v-if="user?.is_superadmin">
                <el-icon><Plus /></el-icon>
                创建邀请链接
              </el-dropdown-item>
              <el-dropdown-item command="theme" divided>
                <el-icon><component :is="themeIcon" /></el-icon>
                {{ themeText }}
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <!-- 顶部面包屑 -->
      <el-header class="header">
        <div class="header-left">
          <!-- 移动端菜单按钮 -->
          <el-button 
            v-if="isMobile"
            :icon="Menu" 
            text 
            @click="toggleCollapse"
            class="mobile-menu-btn"
          />
          <el-breadcrumb separator=">" class="breadcrumb">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentRoute.meta?.title">
              {{ currentRoute.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-actions">
          <el-badge :value="pendingCount" :hidden="pendingCount === 0" class="badge">
            <el-button :icon="Bell" circle @click="router.push('/audit')" />
          </el-badge>
        </div>
      </el-header>

      <!-- 主要内容 -->
      <el-main class="content">
        <transition name="page-fade" mode="out-in">
          <router-view />
        </transition>
      </el-main>
    </el-container>

    <!-- 邀请链接对话框 -->
    <el-dialog v-model="showInviteDialog" title="创建邀请链接" width="500px">
      <el-form label-width="120px">
        <el-form-item label="有效期设置">
          <div class="time-setting">
            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <el-input-number 
                  v-model="inviteTime.days" 
                  :min="0" 
                  :max="30"
                  placeholder="天"
                  @change="updateInviteMinutes"
                />
                <div class="time-label">天</div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-input-number 
                  v-model="inviteTime.hours" 
                  :min="0" 
                  :max="23"
                  placeholder="小时"
                  @change="updateInviteMinutes"
                />
                <div class="time-label">小时</div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-input-number 
                  v-model="inviteTime.minutes" 
                  :min="0" 
                  :max="59"
                  placeholder="分钟"
                  @change="updateInviteMinutes"
                />
                <div class="time-label">分钟</div>
              </el-col>
            </el-row>
          </div>
        </el-form-item>
        
        <el-form-item label="快捷设置">
          <div class="quick-time-buttons">
            <el-button size="small" @click="setQuickTime(60)">1小时</el-button>
            <el-button size="small" @click="setQuickTime(360)">6小时</el-button>
            <el-button size="small" @click="setQuickTime(720)">12小时</el-button>
            <el-button size="small" @click="setQuickTime(1440)">1天</el-button>
            <el-button size="small" @click="setQuickTime(4320)">3天</el-button>
            <el-button size="small" @click="setQuickTime(10080)">7天</el-button>
          </div>
        </el-form-item>

        <el-form-item label="使用次数限制">
          <div class="uses-setting">
            <el-input-number 
              v-model="inviteMaxUses" 
              :min="1" 
              :max="1000"
              placeholder="次数"
            />
            <div class="uses-hint">
              <el-text type="info" size="small">
                超过该次数后，邀请链接将自动失效
              </el-text>
            </div>
          </div>
        </el-form-item>
        
        <el-form-item label="总计">
          <el-tag type="info" size="large">
            {{ formatDuration(inviteMinutes) }}
          </el-tag>
          <div class="time-hint">
            <el-text type="info" size="small">
              <span v-if="inviteMinutes > 0">
                链接将在 {{ formatDuration(inviteMinutes) }} 后过期
                <span class="expiry-at">（约 {{ formatExpiryAt(inviteMinutes) }} 到期）</span>
              </span>
              <span v-else>
                请选择有效期
              </span>
            </el-text>
          </div>
        </el-form-item>
        
        <el-form-item v-if="inviteLink" label="邀请链接">
          <el-input v-model="inviteLink" readonly>
            <template #append>
              <el-button @click="copyInviteLink">
                <el-icon><DocumentCopy /></el-icon>
                复制
              </el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetInviteDialog">取消</el-button>
        <el-button type="primary" @click="createInvite" :disabled="inviteMinutes <= 0">
          创建邀请链接
        </el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { 
  Document, Expand, Fold, User, SwitchButton, Bell,
  Odometer, Box, Plus, DocumentCopy, Menu
} from '@element-plus/icons-vue'
import api from '../api'
import { useTheme } from '../composables/useTheme'

const route = useRoute()
const router = useRouter()

const collapsed = ref(false)
const isMobile = ref(false)
const user = ref(null)
const pendingCount = ref(0)

// 邀请功能相关
const showInviteDialog = ref(false)
const inviteMinutes = ref(60)
const inviteLink = ref('')
const inviteMaxUses = ref(1)
const inviteTime = ref({
  days: 0,
  hours: 1,
  minutes: 0
})

// 主题相关
const { isDark, toggleTheme, themeIcon, themeText } = useTheme()

// 计算属性
const activeMenu = computed(() => {
  const childPath = route.matched[1]?.path
  return childPath ? `/${childPath}` : route.path
})

const currentRoute = computed(() => route)

const userInitial = computed(() => {
  return user.value?.display_name?.[0] || user.value?.username?.[0] || 'U'
})

const menuRoutes = computed(() => {
  return router.getRoutes()
    .find(r => r.path === '/')
    ?.children
    ?.filter(child => !child.meta?.hidden) || []
})

// 移动端检测方法
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
  // 移动端默认折叠侧边栏
  if (isMobile.value) {
    collapsed.value = true
  }
}

const handleResize = () => {
  checkMobile()
}

// 方法
const toggleCollapse = () => {
  collapsed.value = !collapsed.value
}

const handleUserCommand = (command) => {
  switch (command) {
    case 'profile':
      // TODO: 实现个人信息页面
      ElMessage.info('功能开发中')
      break
    case 'invite':
      showInviteDialog.value = true
      inviteLink.value = '' // 重置邀请链接
      resetInviteTime()
      break
    case 'theme':
      toggleTheme()
      ElMessage.success(`已切换到${isDark.value ? '深色' : '浅色'}模式`)
      break
    case 'logout':
      logout()
      break
  }
}

const logout = () => {
  localStorage.removeItem('token')
  router.push('/login')
  ElMessage.success('已退出登录')
}

const fetchUserInfo = async () => {
  try {
    const { data } = await api.get('/auth/me')
    user.value = data
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

const fetchPendingCount = async () => {
  try {
    const { data } = await api.get('/audit/submissions', { 
      params: { status_filter: 'waiting', limit: 1 } 
    })
    pendingCount.value = data.length
  } catch (error) {
    console.error('获取待审核数量失败:', error)
  }
}

const createInvite = async () => {
  try {
    const { data } = await api.post('/invites/create', { 
      expires_in_minutes: inviteMinutes.value,
      max_uses: inviteMaxUses.value
    })
    inviteLink.value = `${location.origin}/register?invite=${data.token}`
    ElMessage.success('邀请链接创建成功')
  } catch (error) {
    ElMessage.error('创建邀请链接失败')
  }
}

const copyInviteLink = async () => {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    ElMessage.success('链接已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

// 时间处理方法
const updateInviteMinutes = () => {
  const { days, hours, minutes } = inviteTime.value
  inviteMinutes.value = (days || 0) * 24 * 60 + (hours || 0) * 60 + (minutes || 0)
}

const setQuickTime = (minutes) => {
  inviteMinutes.value = minutes
  // 将分钟转换为天、小时、分钟
  const days = Math.floor(minutes / (24 * 60))
  const remainingMinutes = minutes % (24 * 60)
  const hours = Math.floor(remainingMinutes / 60)
  const mins = remainingMinutes % 60
  
  inviteTime.value = {
    days,
    hours,
    minutes: mins
  }
}

const formatDuration = (totalMinutes) => {
  if (totalMinutes <= 0) return '0分钟'
  
  const days = Math.floor(totalMinutes / (24 * 60))
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60)
  const minutes = totalMinutes % 60
  
  const parts = []
  if (days > 0) parts.push(`${days}天`)
  if (hours > 0) parts.push(`${hours}小时`)
  if (minutes > 0) parts.push(`${minutes}分钟`)
  
  return parts.join(' ') || '0分钟'
}

const formatExpiryAt = (totalMinutes) => {
  if (!totalMinutes || totalMinutes <= 0) return ''
  const now = new Date()
  const expiry = new Date(now.getTime() + totalMinutes * 60 * 1000)
  const y = expiry.getFullYear()
  const m = String(expiry.getMonth() + 1).padStart(2, '0')
  const d = String(expiry.getDate()).padStart(2, '0')
  const hh = String(expiry.getHours()).padStart(2, '0')
  const mm = String(expiry.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}`
}

const resetInviteTime = () => {
  inviteTime.value = {
    days: 0,
    hours: 1,
    minutes: 0
  }
  inviteMinutes.value = 60
}

const resetInviteDialog = () => {
  showInviteDialog.value = false
  inviteLink.value = ''
  resetInviteTime()
  inviteMaxUses.value = 1
}

onMounted(async () => {
  // 初始化移动端检测
  checkMobile()
  window.addEventListener('resize', handleResize)
  
  await fetchUserInfo()
  await fetchPendingCount()
  
  // 定期更新待审核数量
  setInterval(fetchPendingCount, 30000) // 30秒更新一次
})

// 组件卸载时清理事件监听
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background: var(--el-bg-color-page);
}

.sidebar {
  background: var(--sidebar-bg);
  border-right: 1px solid var(--el-border-color);
  transition: width 0.3s ease, background 0.3s ease;
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(10px);
}

.logo-container {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  position: relative;
}

.logo-container.collapsed {
  justify-content: center;
  flex-direction: column;
  gap: 8px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  flex: 1;
}

.logo-collapsed {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.logo-text {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.collapse-btn {
  color: var(--el-text-color-secondary);
  position: absolute;
  right: 16px;
  transition: all 0.3s ease;
}

.collapse-btn.collapsed {
  position: static;
  margin: 0 auto;
}

.nav-menu {
  flex: 1;
  border: none;
  padding: 16px 0;
}

/* 折叠态：菜单项与图标完全居中 */
:deep(.el-menu--collapse) {
  width: 64px; /* 与 aside 折叠宽度一致，避免视觉偏移 */
}

:deep(.el-menu--collapse .el-menu-item),
:deep(.el-menu--collapse .el-sub-menu__title) {
  padding-left: 0 !important;
  padding-right: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 清除图标默认右侧外边距，确保图标水平正中 */
:deep(.el-menu--collapse .el-menu-item .el-icon),
:deep(.el-menu--collapse .el-sub-menu__title .el-icon) {
  margin: 0 !important;
}

/* 高亮项在折叠时的视觉居中与圆角背景 */
:deep(.el-menu--collapse .el-menu-item.is-active) {
  border-radius: 8px;
}

.nav-item {
  margin: 4px 12px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.nav-item:hover {
  background: rgba(99, 102, 241, 0.1);
}

.nav-item.is-active {
  background: rgba(99, 102, 241, 0.15);
  color: var(--el-color-primary);
}

.user-section {
  padding: 16px;
  border-top: 1px solid var(--el-border-color-light);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: background 0.3s ease;
}

.user-info:hover {
  background: rgba(99, 102, 241, 0.1);
}

.username {
  font-size: 14px;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.main-container {
  background: transparent;
}

.header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--el-border-color);
  backdrop-filter: blur(10px);
  transition: background 0.3s ease;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.badge {
  cursor: pointer;
}

.content {
  padding: 24px;
  overflow-y: auto;
  min-height: calc(100vh - 64px);
}

/* 邀请对话框样式 */
.time-setting {
  width: 100%;
}

.time-setting .el-input-number {
  width: 100%;
}

.time-label {
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.quick-time-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.uses-setting {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 200px;
}

.uses-setting .el-input-number {
  width: 100%;
}

.uses-hint {
  margin-top: 2px;
}

.time-hint {
  margin-top: 8px;
}

.time-hint .expiry-at {
  color: var(--el-text-color-secondary);
}

/* 移动端遮罩层 */
.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
  backdrop-filter: blur(2px);
}

/* 头部移动端适配 */
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.mobile-menu-btn {
  color: var(--el-text-color-primary);
  font-size: 20px;
}

.breadcrumb {
  flex: 1;
}

/* 移动端适配 */
.sidebar.mobile {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
  height: 100vh;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  transform: translateX(0);
  transition: transform 0.3s ease;
}

.sidebar.mobile-hidden {
  transform: translateX(-100%);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .layout-container {
    position: relative;
  }
  
  .main-container {
    margin-left: 0 !important;
    width: 100%;
  }
  
  .header {
    padding: 0 16px;
  }
  
  .breadcrumb {
    font-size: 14px;
  }
  
  .content {
    padding: 16px;
  }
  
  .user-section {
    padding: 12px;
  }
  
  .user-info {
    padding: 12px 8px;
  }
  
  .username {
    font-size: 13px;
  }
  
  /* 邀请对话框移动端适配 */
  :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
  }
  
  .quick-time-buttons {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  
  .time-setting .el-row {
    gap: 8px;
  }
  
  .time-label {
    font-size: 11px;
  }
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .header {
    padding: 0 12px;
  }
  
  .content {
    padding: 12px;
  }
  
  .breadcrumb {
    font-size: 13px;
  }
  
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 3vh auto;
  }
  
  .quick-time-buttons {
    grid-template-columns: 1fr;
  }
  
  .header-actions .el-button {
    padding: 8px;
  }
}
</style>
