<template>
  <el-container class="layout-container">
    <!-- 侧边栏（桌面端） / 底部导航栏（移动端） -->
    <el-aside 
      v-if="!isMobile"
      :width="collapsed ? '64px' : '250px'" 
      class="sidebar xw-sidebar"
      :class="{ 'collapsed': collapsed }"
    >
      <div class="logo-container" :class="{ 'collapsed': collapsed }">
        <!-- Logo区域 - 统一容器，避免跳动 -->
        <div class="logo-section">
          <el-icon size="28" color="#6366f1" class="logo-icon">
            <Document />
          </el-icon>
          <transition name="logo-text-fade">
            <span v-if="!collapsed" class="logo-text">Graffito</span>
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
                <el-dropdown-item command="invite" v-if="user?.is_superadmin">
                  <el-icon><Plus /></el-icon>
                  创建邀请链接
                </el-dropdown-item>
                <el-dropdown-item command="theme" :divided="user?.is_superadmin">
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
      <el-header class="header xw-header xw-header-glass">
        <div class="header-left">
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
          
          <!-- 移动端用户菜单 -->
          <el-dropdown 
            v-if="isMobile"
            placement="bottom-end" 
            @command="handleUserCommand"
            trigger="click"
          >
            <el-avatar :size="32" style="background-color: #6366f1; cursor: pointer;">
              {{ userInitial }}
            </el-avatar>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="invite" v-if="user?.is_superadmin">
                  <el-icon><Plus /></el-icon>
                  创建邀请链接
                </el-dropdown-item>
                <el-dropdown-item command="theme" :divided="user?.is_superadmin">
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
      </el-header>

      <!-- 主要内容 -->
      <el-main class="content" :class="{ 'mobile-content': isMobile }">
        <transition name="page-fade" mode="out-in">
          <router-view />
        </transition>
      </el-main>
    </el-container>

    <!-- 移动端底部导航栏 -->
    <nav v-if="isMobile" class="mobile-bottom-nav xw-glass">
      <div 
        v-for="route in menuRoutes" 
        :key="route.path" 
        class="nav-item-mobile"
        :class="{ 'active': activeMenu === '/' + route.path }"
        @click="router.push('/' + route.path)"
      >
        <el-icon :size="20">
          <component :is="route.meta.icon" />
        </el-icon>
        <span class="nav-label">{{ route.meta.title }}</span>
      </div>
    </nav>

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
          <div class="invite-link-container">
            <el-input v-model="inviteLink" readonly class="invite-link-input" />
            <el-button @click="copyInviteLink" class="copy-button">
              <el-icon><DocumentCopy /></el-icon>
              复制
            </el-button>
          </div>
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
  Odometer, Box, Plus, DocumentCopy
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
  localStorage.removeItem('access_token')
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
  // Ctrl/Cmd + B 切换侧边栏（仅桌面端）
  if ((event.ctrlKey || event.metaKey) && event.key === 'b' && !isMobile.value) {
    event.preventDefault()
    toggleCollapse()
  }
}

onMounted(async () => {
  // 初始化移动端检测
  checkMobile()
  window.addEventListener('resize', handleResize)
  
  // 添加键盘快捷键
  window.addEventListener('keydown', handleKeydown)
  
  await fetchUserInfo()
  await fetchPendingCount()
  
  // 定期更新待审核数量
  setInterval(fetchPendingCount, 30000) // 30秒更新一次
})

// 组件卸载时清理事件监听
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('keydown', handleKeydown)
})
</script>
