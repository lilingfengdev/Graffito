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
      :class="{ 'mobile': isMobile, 'mobile-hidden': isMobile && collapsed, 'collapsed': collapsed }"
    >
      <div class="logo-container" :class="{ 'collapsed': collapsed }">
        <!-- Logo区域 - 统一容器，避免跳动 -->
        <div class="logo-section">
          <el-icon size="28" color="#6366f1" class="logo-icon">
            <Document />
          </el-icon>
          <transition name="logo-text-fade">
            <span v-if="!collapsed" class="logo-text">XWall</span>
          </transition>
        </div>
        
        <!-- 折叠按钮 - 固定位置，避免跳动 -->
        <el-tooltip 
          :content="collapsed ? '展开侧边栏' : '折叠侧边栏'" 
          placement="right"
          :disabled="isMobile"
        >
          <button 
            @click="toggleCollapse"
            class="collapse-btn"
            :class="{ 'collapsed': collapsed }"
          >
            <el-icon class="collapse-icon">
              <component :is="collapsed ? Expand : Fold" />
            </el-icon>
          </button>
        </el-tooltip>
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
      <div class="user-section" :class="{ 'collapsed': collapsed }">
        <el-tooltip 
          :content="user?.display_name || user?.username || '用户'" 
          placement="right"
          :disabled="!collapsed || isMobile"
        >
          <el-dropdown 
            :placement="collapsed ? 'right-start' : 'top-start'" 
            @command="handleUserCommand"
            :trigger="collapsed ? 'hover' : 'click'"
          >
            <div class="user-info" :class="{ 'collapsed': collapsed }">
              <el-avatar :size="collapsed ? 28 : 32" style="background-color: #6366f1;">
                {{ userInitial }}
              </el-avatar>
              <transition name="username-fade">
                <span v-if="!collapsed" class="username">{{ user?.display_name || user?.username }}</span>
              </transition>
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
        </el-tooltip>
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
            <el-button 
              :icon="Bell" 
              circle 
              @click="router.push('/audit')" 
              class="notification-btn"
              :class="{ 'has-notification': pendingCount > 0 }"
            />
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
          <div class="total-duration-container">
            <el-tag type="info" size="large" class="duration-tag">
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

// 触摸手势相关
const touchStartX = ref(0)
const touchStartY = ref(0)
const touchEndX = ref(0)
const touchEndY = ref(0)
const isSwiping = ref(false)

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
  const routes = router.getRoutes()
    .find(r => r.path === '/')
    ?.children
    ?.filter(child => !child.meta?.hidden) || []
  
  // 根据用户权限过滤路由
  return routes.filter(route => {
    // 如果路由需要超级管理员权限，但用户不是超级管理员，则不显示
    if (route.meta?.requiresSuperAdmin && !user.value?.is_superadmin) {
      return false
    }
    // 如果路由需要管理员权限，但用户不是管理员，则不显示
    if (route.meta?.requiresAdmin && !user.value?.is_admin) {
      return false
    }
    return true
  })
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
  localStorage.removeItem('user')
  router.push('/login')
  ElMessage.success('已退出登录')
}

const fetchUserInfo = async () => {
  try {
    const { data } = await api.get('/auth/me')
    user.value = data
    // 保存用户信息到 localStorage，供路由守卫使用
    localStorage.setItem('user', JSON.stringify(data))
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

// 键盘快捷键处理
const handleKeydown = (event) => {
  // Ctrl/Cmd + B 切换侧边栏
  if ((event.ctrlKey || event.metaKey) && event.key === 'b' && !isMobile.value) {
    event.preventDefault()
    toggleCollapse()
  }
}

// 触摸手势处理
const handleTouchStart = (e) => {
  if (!isMobile.value) return
  
  touchStartX.value = e.touches[0].clientX
  touchStartY.value = e.touches[0].clientY
  isSwiping.value = true
}

const handleTouchMove = (e) => {
  if (!isMobile.value || !isSwiping.value) return
  
  touchEndX.value = e.touches[0].clientX
  touchEndY.value = e.touches[0].clientY
}

const handleTouchEnd = () => {
  if (!isMobile.value || !isSwiping.value) return
  
  isSwiping.value = false
  
  const deltaX = touchEndX.value - touchStartX.value
  const deltaY = touchEndY.value - touchStartY.value
  const minSwipeDistance = 50
  
  // 确保水平滑动距离大于垂直滑动距离（避免与页面滚动冲突）
  if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > minSwipeDistance) {
    // 从左边缘向右滑动，打开侧边栏
    if (deltaX > 0 && touchStartX.value < 20 && collapsed.value) {
      collapsed.value = false
    }
    // 向左滑动，关闭侧边栏
    else if (deltaX < 0 && !collapsed.value) {
      collapsed.value = true
    }
  }
  
  // 重置触摸坐标
  touchStartX.value = 0
  touchStartY.value = 0
  touchEndX.value = 0
  touchEndY.value = 0
}

onMounted(async () => {
  // 初始化移动端检测
  checkMobile()
  window.addEventListener('resize', handleResize)
  
  // 添加键盘快捷键
  window.addEventListener('keydown', handleKeydown)
  
  // 添加移动端触摸手势支持
  if (isMobile.value) {
    document.addEventListener('touchstart', handleTouchStart, { passive: true })
    document.addEventListener('touchmove', handleTouchMove, { passive: true })
    document.addEventListener('touchend', handleTouchEnd, { passive: true })
  }
  
  await fetchUserInfo()
  await fetchPendingCount()
  
  // 定期更新待审核数量
  setInterval(fetchPendingCount, 30000) // 30秒更新一次
})

// 组件卸载时清理事件监听
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
  
  // 移除触摸事件监听
  document.removeEventListener('touchstart', handleTouchStart)
  document.removeEventListener('touchmove', handleTouchMove)
  document.removeEventListener('touchend', handleTouchEnd)
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
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              background 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  position: relative;
  z-index: 100;
  overflow-x: hidden;
  overflow-y: auto;
  will-change: width;
}

/* 浅色模式侧边栏渐变 */
html.light .sidebar {
  background: linear-gradient(180deg, 
    rgba(255, 255, 255, 0.95) 0%, 
    rgba(249, 250, 251, 0.92) 50%,
    rgba(243, 244, 246, 0.9) 100%
  );
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.04);
}

html.light .sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, 
    rgba(99, 102, 241, 0.02) 0%, 
    transparent 50%,
    rgba(139, 92, 246, 0.02) 100%
  );
  pointer-events: none;
  z-index: -1;
}

/* 深色模式侧边栏渐变 */
html.dark .sidebar {
  background: linear-gradient(180deg, 
    rgba(10, 15, 30, 0.95) 0%, 
    rgba(20, 27, 45, 0.92) 30%,
    rgba(30, 41, 67, 0.9) 70%,
    rgba(45, 58, 90, 0.88) 100%
  );
  border-right-color: rgba(99, 102, 241, 0.15);
  box-shadow: 2px 0 20px rgba(0, 0, 0, 0.5), inset -1px 0 0 rgba(99, 102, 241, 0.1);
}

html.dark .sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(ellipse at top left, 
    rgba(99, 102, 241, 0.08) 0%, 
    transparent 50%
  ),
  radial-gradient(ellipse at bottom right, 
    rgba(139, 92, 246, 0.06) 0%, 
    transparent 50%
  );
  pointer-events: none;
  z-index: -1;
}


/* Logo容器 - 优化布局和动画，防止抖动 */
.logo-container {
  min-height: 64px;
  max-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid var(--el-border-color-light);
  position: relative;
  transition: min-height 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              padding 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              background 0.3s ease;
  background: linear-gradient(180deg, 
    rgba(255, 255, 255, 0.05) 0%, 
    transparent 100%
  );
  overflow: hidden;
}

html.dark .logo-container {
  background: linear-gradient(180deg, 
    rgba(99, 102, 241, 0.05) 0%, 
    transparent 100%
  );
  border-bottom-color: rgba(99, 102, 241, 0.15);
}

.logo-container.collapsed {
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 10px;
  padding: 16px 8px;
  min-height: 100px;
  max-height: 100px;
}

/* Logo区域 - 统一布局避免跳动 */
.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  transition: gap 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              flex 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
}

.logo-container.collapsed .logo-section {
  flex: none;
  justify-content: center;
  gap: 0;
  width: 48px;
}

.logo-icon {
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-container.collapsed .logo-icon {
  transform: scale(1);
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--xw-primary);
  white-space: nowrap;
  overflow: hidden;
  flex-shrink: 0;
}

/* 折叠按钮 - 优化动画和交互 */
.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  min-width: 32px;
  border: none;
  border-radius: var(--xw-radius);
  background: transparent;
  color: var(--xw-text-tertiary);
  cursor: pointer;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              background 0.3s ease,
              color 0.3s ease;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: var(--xw-bg-secondary);
  color: var(--xw-primary);
  transform: scale(1.05);
}

.collapse-btn:active {
  transform: scale(0.95);
}

.collapse-btn.collapsed {
  width: 32px;
  height: 32px;
  align-self: center;
  margin: 0;
}

.collapse-icon {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.collapse-btn:hover .collapse-icon {
  transform: rotate(180deg);
}

/* Logo文本淡入淡出动画 */
.logo-text-fade-enter-active,
.logo-text-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.logo-text-fade-enter-from,
.logo-text-fade-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

.logo-text-fade-enter-to,
.logo-text-fade-leave-from {
  opacity: 1;
  transform: translateX(0);
}

.nav-menu {
  flex: 1;
  border: none;
  padding: 16px 0;
  overflow-x: hidden;
  overflow-y: auto;
}

/* 导航菜单 - 优化折叠状态 */
:deep(.el-menu--collapse) {
  width: 64px;
}

:deep(.el-menu--collapse .el-menu-item),
:deep(.el-menu--collapse .el-sub-menu__title) {
  padding: 0 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 6px auto;
  border-radius: var(--xw-radius-xl);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  width: 48px;
  height: 48px;
  position: relative;
  overflow: visible;
}

:deep(.el-menu--collapse .el-menu-item .el-icon),
:deep(.el-menu--collapse .el-sub-menu__title .el-icon) {
  margin: 0 !important;
  font-size: 20px;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-menu--collapse .el-menu-item:hover) {
  background: var(--xw-gradient-highlight);
  transform: scale(1.05);
}

:deep(.el-menu--collapse .el-menu-item:hover .el-icon) {
  transform: scale(1.15) rotate(-5deg);
}

:deep(.el-menu--collapse .el-menu-item.is-active) {
  background: linear-gradient(135deg, var(--xw-primary-lightest), var(--xw-primary-200));
  box-shadow: var(--xw-shadow-sm), 0 0 0 2px rgba(99, 102, 241, 0.2);
  transform: scale(1.02);
}

html.dark :deep(.el-menu--collapse .el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(129, 140, 248, 0.15));
  box-shadow: var(--xw-shadow-md), 0 0 15px rgba(99, 102, 241, 0.3), inset 0 0 10px rgba(99, 102, 241, 0.1);
}

/* 折叠状态下的 tooltip */
:deep(.el-menu--collapse .el-tooltip__trigger) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-item {
  margin: 6px 12px;
  border-radius: var(--xw-radius-xl);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--xw-primary), var(--xw-primary-light));
  transition: height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 0 4px 4px 0;
}

.nav-item:hover::before {
  height: 70%;
}

.nav-item:hover {
  background: var(--xw-gradient-highlight);
  transform: translateX(4px);
}

html.dark .nav-item:hover {
  background: rgba(99, 102, 241, 0.12);
  box-shadow: inset 0 0 10px rgba(99, 102, 241, 0.05);
}

.nav-item.is-active {
  background: linear-gradient(135deg, var(--xw-primary-lightest), var(--xw-primary-200));
  color: var(--xw-primary);
  box-shadow: var(--xw-shadow-sm);
  font-weight: 600;
}

.nav-item.is-active::before {
  height: 80%;
}

html.dark .nav-item.is-active {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(129, 140, 248, 0.15));
  box-shadow: var(--xw-shadow-md), 0 0 15px rgba(99, 102, 241, 0.2), inset 0 0 10px rgba(99, 102, 241, 0.1);
}

/* 用户信息区域 - 优化折叠状态 */
.user-section {
  padding: 16px;
  border-top: 1px solid var(--el-border-color-light);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: linear-gradient(180deg, 
    transparent 0%, 
    rgba(99, 102, 241, 0.02) 100%
  );
}

html.dark .user-section {
  background: linear-gradient(180deg, 
    transparent 0%, 
    rgba(99, 102, 241, 0.05) 100%
  );
  border-top-color: rgba(99, 102, 241, 0.15);
}

.user-section.collapsed {
  padding: 20px 8px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 8px;
  border-radius: var(--xw-radius-xl);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-height: 48px;
  position: relative;
  background: var(--xw-gradient-highlight);
  overflow: hidden;
}

.user-info.collapsed {
  gap: 0;
  padding: 10px;
  min-height: 48px;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
}

.user-info:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(129, 140, 248, 0.08));
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--xw-shadow-md);
}

html.dark .user-info:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(129, 140, 248, 0.15));
  box-shadow: var(--xw-shadow-md), 0 0 15px rgba(99, 102, 241, 0.3);
}

.username {
  font-size: 14px;
  line-height: 1.5;
  color: var(--xw-text-primary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  max-width: 100%;
  flex: 1 1 auto;
}

/* 用户名淡入淡出动画 */
.username-fade-enter-active,
.username-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.username-fade-enter-from,
.username-fade-leave-to {
  opacity: 0;
  transform: translateX(-10px);
  max-width: 0;
}

.username-fade-enter-to,
.username-fade-leave-from {
  opacity: 1;
  transform: translateX(0);
  max-width: 200px;
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
:deep(.el-dialog__body) {
  padding-top: 24px !important;
}

:deep(.el-form .el-form-item:first-child) {
  margin-top: 0;
}

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

/* 总计时长容器样式 */
.total-duration-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
}

.duration-tag {
  font-weight: 600;
  letter-spacing: 0.5px;
}

.time-hint {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding-left: 2px;
  line-height: 1.5;
}

.time-hint .expiry-at {
  color: var(--el-text-color-secondary);
  margin-left: 4px;
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

/* 移动端适配 - 优化动画效果和触摸体验 */
.sidebar.mobile {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1000;
  height: 100vh;
  box-shadow: var(--xw-shadow-xl);
  transform: translateX(0);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-right: none;
  touch-action: pan-y; /* 允许垂直滚动 */
  -webkit-overflow-scrolling: touch; /* iOS 平滑滚动 */
}

.sidebar.mobile::before {
  display: none;
}

.sidebar.mobile-hidden {
  transform: translateX(-100%);
  box-shadow: none;
}

.sidebar.mobile:not(.mobile-hidden) {
  animation: slideInFromLeft 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes slideInFromLeft {
  from {
    transform: translateX(-100%);
    opacity: 0.8;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 移动端菜单按钮优化 - 增强触摸反馈 */
.mobile-menu-btn {
  color: var(--xw-text-primary);
  font-size: 22px;
  padding: 10px;
  border-radius: var(--xw-radius-lg);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  min-width: 44px; /* iOS 推荐的最小触摸目标 */
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent; /* 移除 iOS 点击高亮 */
}

.mobile-menu-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: var(--xw-primary-lightest);
  transition: all 0.2s ease;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 0;
}

.mobile-menu-btn:active::before {
  width: 100%;
  height: 100%;
  transition: all 0.1s ease;
}

.mobile-menu-btn:active {
  color: var(--xw-primary);
  transform: scale(0.92);
  background: var(--xw-bg-secondary);
}

/* 通知按钮样式优化 */
.notification-btn {
  color: var(--xw-text-secondary);
  border: 1px solid var(--xw-border-primary);
  background: var(--xw-bg-primary);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.notification-btn::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  background: var(--xw-primary-lightest);
  transition: all 0.3s ease;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.notification-btn:hover::before {
  width: 40px;
  height: 40px;
}

.notification-btn:hover {
  color: var(--xw-primary);
  border-color: var(--xw-primary);
  background: var(--xw-bg-secondary);
  transform: scale(1.05);
  box-shadow: var(--xw-shadow-md);
}

.notification-btn:active {
  transform: scale(0.95);
}

/* 有通知时的高亮状态 */
.notification-btn.has-notification {
  color: var(--xw-primary);
  border-color: var(--xw-primary);
  background: var(--xw-primary-lightest);
  animation: notification-pulse 2s infinite;
}

@keyframes notification-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(99, 102, 241, 0);
  }
}

/* 深色模式下的通知按钮优化 */
html.dark .notification-btn {
  color: var(--xw-text-primary);
  border-color: var(--xw-border-secondary);
  background: var(--xw-bg-tertiary);
}

html.dark .notification-btn:hover {
  color: var(--xw-primary-light);
  border-color: var(--xw-primary-light);
  background: var(--xw-bg-quaternary);
  box-shadow: var(--xw-shadow-lg);
}

html.dark .notification-btn.has-notification {
  color: var(--xw-primary-light);
  border-color: var(--xw-primary-light);
  background: rgba(99, 102, 241, 0.2);
}

/* 移动端遮罩层 - 优化触摸交互 */
.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  z-index: 999;
  animation: fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  touch-action: none; /* 防止遮罩层下的内容滚动 */
  -webkit-tap-highlight-color: transparent;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 通用触摸优化 */
* {
  -webkit-tap-highlight-color: transparent;
}

button, a, .clickable {
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
}

/* 响应式设计 - 平板和移动设备 */
@media (max-width: 768px) {
  .layout-container {
    position: relative;
    overflow-x: hidden; /* 防止横向滚动 */
  }
  
  .main-container {
    margin-left: 0 !important;
    width: 100%;
  }
  
  .header {
    padding: 0 16px;
    height: 56px; /* 移动端减小高度 */
  }
  
  .header-actions {
    gap: 12px; /* 减小按钮间距 */
  }
  
  .breadcrumb {
    font-size: 14px;
  }
  
  .content {
    padding: 16px;
    min-height: calc(100vh - 56px); /* 调整最小高度 */
  }
  
  .user-section {
    padding: 12px;
  }
  
  .user-info {
    padding: 10px 8px;
    min-height: 44px; /* iOS 推荐的最小触摸目标 */
  }
  
  .username {
    font-size: 13px;
    line-height: 1.5;
    max-width: calc(100% - 40px); /* 预留头像和间隔空间 */
  }
  
  /* 导航菜单项移动端优化 */
  .nav-item {
    margin: 8px 12px;
    min-height: 48px; /* 增大触摸目标 */
    font-size: 15px;
  }
  
  :deep(.el-menu-item) {
    min-height: 48px !important;
    line-height: 48px !important;
  }
  
  /* 邀请对话框移动端适配 */
  :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
    border-radius: var(--xw-radius-xl) !important;
  }
  
  :deep(.el-dialog__header) {
    padding: 20px 16px 16px 16px;
  }
  
  :deep(.el-dialog__body) {
    padding: 20px 16px !important;
  }
  
  :deep(.el-dialog__footer) {
    padding: 12px 16px;
  }
  
  .quick-time-buttons {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
  
  .quick-time-buttons .el-button {
    padding: 12px 16px;
    min-height: 44px; /* 增大触摸目标 */
    font-size: 15px;
    font-weight: 500;
    border-radius: var(--xw-radius-lg) !important;
  }
  
  .time-setting .el-row {
    gap: 8px;
  }
  
  .time-label {
    font-size: 11px;
    margin-top: 6px;
  }
  
  /* 表单元素移动端优化 */
  :deep(.el-input-number) {
    width: 100% !important;
  }
  
  :deep(.el-input__wrapper) {
    min-height: 44px; /* iOS 推荐的最小触摸目标 */
    font-size: 16px; /* 防止 iOS 自动缩放 */
  }
  
  :deep(.el-input__inner) {
    font-size: 16px; /* 防止 iOS 自动缩放 */
  }
  
  /* 按钮移动端优化 - 增强触摸体验 */
  :deep(.el-button) {
    min-height: 44px;
    padding: 12px 20px;
    font-size: 15px;
    border-radius: var(--xw-radius-lg) !important;
    font-weight: 500;
    letter-spacing: 0.3px;
  }
  
  :deep(.el-button--small) {
    min-height: 36px;
    padding: 8px 14px;
    font-size: 14px;
  }
  
  :deep(.el-button--large) {
    min-height: 48px;
    padding: 14px 24px;
    font-size: 16px;
  }
  
  /* 对话框底部按钮优化 - 堆叠布局 */
  :deep(.el-dialog__footer) {
    display: flex;
    flex-direction: column-reverse;
    gap: 12px;
    padding: 16px !important;
  }
  
  :deep(.el-dialog__footer .el-button) {
    width: 100%;
    margin: 0 !important;
  }
  
  /* 按钮组移动端优化 */
  :deep(.el-button-group) {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  
  :deep(.el-button-group .el-button) {
    width: 100%;
    margin: 0 !important;
    border-radius: var(--xw-radius-lg) !important;
  }
  
  :deep(.el-button-group .el-button:first-child) {
    border-radius: var(--xw-radius-lg) !important;
  }
  
  :deep(.el-button-group .el-button:last-child) {
    border-radius: var(--xw-radius-lg) !important;
  }
  
  /* 表单项按钮优化 */
  :deep(.el-form-item__content .el-button + .el-button) {
    margin-left: 0 !important;
    margin-top: 10px;
  }
  
  /* 通知按钮移动端优化 */
  .notification-btn {
    min-width: 44px;
    min-height: 44px;
  }
}

/* 超小屏幕适配 - 手机竖屏 */
@media (max-width: 480px) {
  .header {
    padding: 0 12px;
  }
  
  .header-left {
    gap: 8px;
    min-width: 0;
    flex: 1;
  }
  
  .content {
    padding: 12px;
    min-height: calc(100vh - 56px);
  }
  
  .breadcrumb {
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 2vh auto;
    max-height: 96vh;
    display: flex;
    flex-direction: column;
  }
  
  :deep(.el-dialog__header) {
    padding: 18px 12px 14px 12px;
  }
  
  :deep(.el-dialog__body) {
    overflow-y: auto;
    max-height: calc(96vh - 120px);
    padding: 20px 12px !important;
  }
  
  .quick-time-buttons {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  
  .quick-time-buttons .el-button {
    width: 100%;
    min-height: 48px;
    font-size: 15px;
    font-weight: 500;
  }
  
  .header-actions .el-button {
    padding: 8px;
  }
  
  /* 对话框底部按钮超小屏优化 */
  :deep(.el-dialog__footer) {
    padding: 12px !important;
  }
  
  :deep(.el-dialog__footer .el-button) {
    min-height: 48px;
    font-size: 15px;
  }
  
  /* 表单标签移动端优化 */
  :deep(.el-form-item__label) {
    font-size: 14px;
    min-width: 80px !important;
  }
  
  /* Logo 移动端优化 */
  .logo-text {
    font-size: 16px;
  }
  
  /* 用户头像移动端优化 */
  .user-info {
    padding: 8px 6px;
  }
  
  .username {
    font-size: 12px;
    max-width: calc(100% - 36px); /* 预留头像和间隔空间 */
  }
}

/* 横屏手机优化 */
@media (max-width: 768px) and (orientation: landscape) {
  .header {
    height: 48px;
  }
  
  .content {
    padding: 12px;
    min-height: calc(100vh - 48px);
  }
  
  :deep(.el-dialog) {
    max-height: 90vh;
  }
  
  :deep(.el-dialog__body) {
    max-height: calc(90vh - 100px);
  }
}

/* 支持安全区域（刘海屏、Home Indicator 等） */
@supports (padding: max(0px)) {
  .sidebar.mobile {
    padding-top: max(0px, env(safe-area-inset-top));
    padding-bottom: max(0px, env(safe-area-inset-bottom));
  }
  
  .header {
    padding-left: max(16px, env(safe-area-inset-left));
    padding-right: max(16px, env(safe-area-inset-right));
  }
  
  .content {
    padding-left: max(16px, env(safe-area-inset-left));
    padding-right: max(16px, env(safe-area-inset-right));
    padding-bottom: max(16px, env(safe-area-inset-bottom));
  }
}
</style>
