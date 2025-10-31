<template>
  <div class="login-page">
    <div class="login-container">
      <!-- 登录表单 -->
      <el-card class="login-card xw-card" shadow="always">
        <template #header>
          <div class="login-header">
            <div class="logo">
              <el-icon size="32" color="#6366f1"><Document /></el-icon>
              <span class="logo-text">Graffito 审核后台</span>
            </div>
            <p class="subtitle">管理员登录</p>
          </div>
        </template>
        
        <el-form 
          :model="loginForm" 
          :rules="loginRules"
          ref="loginFormRef"
          size="large"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              clearable
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          
          <el-form-item>
            <el-button 
              type="primary" 
              size="large"
              style="width: 100%"
              :loading="logging"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>
          
          <el-form-item>
            <div class="login-footer">
              <router-link to="/register" class="register-link">
                使用邀请注册
              </router-link>
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 初始化超级管理员 -->
      <el-card 
        v-if="!superadminExists" 
        class="init-card xw-card" 
        shadow="hover"
      >
        <template #header>
          <div class="init-header">
            <el-icon size="24" color="#f59e0b"><Warning /></el-icon>
            <span>系统初始化</span>
          </div>
        </template>
        
        <el-alert
          title="检测到系统尚未初始化"
          description="请创建第一个超级管理员账号来完成系统初始化"
          type="warning"
          :closable="false"
          style="margin-bottom: 20px"
        />
        
        <el-form 
          :model="initForm" 
          :rules="initRules"
          ref="initFormRef"
          size="large"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="initForm.username"
              placeholder="请输入管理员用户名"
              clearable
            />
          </el-form-item>
          
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="initForm.password"
              type="password"
              placeholder="请输入密码"
              show-password
              clearable
            />
          </el-form-item>
          
          <el-form-item label="显示名称">
            <el-input
              v-model="initForm.display_name"
              placeholder="请输入显示名称（可选）"
              clearable
            />
          </el-form-item>
          
          <el-form-item>
            <el-button 
              type="warning" 
              size="large"
              style="width: 100%"
              :loading="initializing"
              @click="handleInitSuperadmin"
            >
              创建超级管理员
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
    
    <!-- 主题切换按钮 -->
    <div class="theme-toggle">
      <el-button 
        :icon="themeIconComponent" 
        circle 
        size="large"
        @click="toggleTheme"
        :title="themeText"
      />
    </div>
    
    <!-- 背景装饰 -->
    <div class="bg-decoration">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, User, Lock, Warning, Moon, Sunny } from '@element-plus/icons-vue'
import api from '../api'
import { useTheme } from '../composables/useTheme'

const router = useRouter()

// 主题管理
const { isDark, toggleTheme, themeText } = useTheme()
const themeIconComponent = computed(() => {
  return isDark.value ? Sunny : Moon
})

// 表单引用
const loginFormRef = ref()
const initFormRef = ref()

// 状态
const logging = ref(false)
const initializing = ref(false)
const superadminExists = ref(true)

// 登录表单
const loginForm = ref({
  username: '',
  password: ''
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' }
  ]
}

// 初始化表单
const initForm = ref({
  username: '',
  password: '',
  display_name: ''
})

const initRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 个字符', trigger: 'blur' }
  ]
}

// 方法
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  try {
    await loginFormRef.value.validate()
    
    logging.value = true
    const params = new URLSearchParams()
    params.set('username', loginForm.value.username)
    params.set('password', loginForm.value.password)
    
    const { data } = await api.post('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    
    // 统一使用 access_token，兼容旧 key
    localStorage.setItem('access_token', data.access_token)
    try { localStorage.setItem('token', data.access_token) } catch(_) {}
    ElMessage.success('登录成功')
    const redirect = new URLSearchParams(window.location.search).get('redirect')
    router.push(redirect || '/')
  } catch (error) {
    const message = error.response?.data?.detail || '登录失败'
    ElMessage.error(message)
  } finally {
    logging.value = false
  }
}

const handleInitSuperadmin = async () => {
  if (!initFormRef.value) return
  
  try {
    await initFormRef.value.validate()
    
    initializing.value = true
    await api.post('/auth/init-superadmin', {
      username: initForm.value.username,
      password: initForm.value.password,
      display_name: initForm.value.display_name
    })
    
    ElMessage.success('超级管理员创建成功，请使用该账号登录')
    superadminExists.value = true
    
    // 自动填充登录表单
    loginForm.value.username = initForm.value.username
    loginForm.value.password = ''
    
    // 重置初始化表单
    initForm.value = {
      username: '',
      password: '',
      display_name: ''
    }
  } catch (error) {
    const message = error.response?.data?.detail || '创建超级管理员失败'
    ElMessage.error(message)
  } finally {
    initializing.value = false
  }
}

const checkSuperadminExists = async () => {
  try {
    const { data } = await api.get('/auth/has-superadmin')
    superadminExists.value = !!data?.exists
  } catch (error) {
    superadminExists.value = true
  }
}

onMounted(() => {
  checkSuperadminExists()
  
  // 处理从注册页面传递的用户名参数
  const urlParams = new URLSearchParams(window.location.search)
  const usernameFromQuery = urlParams.get('username')
  if (usernameFromQuery) {
    loginForm.value.username = usernameFromQuery
    ElMessage.success('已为您预填写用户名，请输入密码登录')
  }
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: var(--app-bg-gradient);
  overflow: hidden;
  transition: background 0.3s ease;
}

.login-container {
  width: 100%;
  max-width: 400px;
  padding: 20px;
  position: relative;
  z-index: 2;
}

.theme-toggle {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 1000;
}

.login-card {
  margin-bottom: 20px;
  backdrop-filter: blur(10px);
  background: var(--card-bg) !important;
  transition: background 0.3s ease;
}

.login-header {
  text-align: center;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}

.logo-text {
  font-size: 24px;
  font-weight: 600;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 16px;
}

.login-footer {
  text-align: center;
  width: 100%;
}

.register-link {
  color: var(--el-color-primary);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.3s ease;
}

.register-link:hover {
  color: var(--el-color-primary-light-3);
}

.init-card {
  backdrop-filter: blur(10px);
  background: var(--card-bg) !important;
  transition: background 0.3s ease;
}

.init-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-color-warning);
  font-weight: 600;
}

/* 背景装饰 */
.bg-decoration {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
  pointer-events: none;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1));
  animation: float 6s ease-in-out infinite;
}

.circle-1 {
  width: 200px;
  height: 200px;
  top: 10%;
  left: 10%;
  animation-delay: 0s;
}

.circle-2 {
  width: 150px;
  height: 150px;
  top: 60%;
  right: 10%;
  animation-delay: 2s;
}

.circle-3 {
  width: 100px;
  height: 100px;
  bottom: 20%;
  left: 60%;
  animation-delay: 4s;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-20px);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-page {
    padding: 16px;
  }
  
  .login-container {
    max-width: 90%;
    padding: 16px;
  }
  
  .theme-toggle {
    top: 16px;
    right: 16px;
  }
  
  .login-card,
  .init-card {
    margin-bottom: 16px;
  }
  
  .logo-text {
    font-size: 22px;
  }
  
  .subtitle {
    font-size: 15px;
  }
  
  /* 表单移动端适配 */
  :deep(.el-form-item) {
    margin-bottom: 20px;
  }
  
  :deep(.el-input) {
    font-size: 16px; /* 防止iOS缩放 */
  }
  
  :deep(.el-button) {
    font-size: 15px;
    padding: 12px 20px;
  }
  
  /* 背景装饰移动端调整 */
  .circle-1 {
    width: 120px;
    height: 120px;
    top: 5%;
    left: 5%;
  }
  
  .circle-2 {
    width: 100px;
    height: 100px;
    top: 70%;
    right: 5%;
  }
  
  .circle-3 {
    width: 80px;
    height: 80px;
    bottom: 15%;
    left: 50%;
  }
}

@media (max-width: 480px) {
  .login-container {
    max-width: 95%;
    padding: 12px;
  }
  
  .logo-text {
    font-size: 20px;
  }
  
  .subtitle {
    font-size: 14px;
  }
  
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }
  
  :deep(.el-button) {
    font-size: 14px;
    padding: 10px 16px;
  }
  
  .register-link {
    font-size: 13px;
  }
  
  /* 超小屏幕背景装饰 */
  .circle-1 {
    width: 80px;
    height: 80px;
  }
  
  .circle-2 {
    width: 60px;
    height: 60px;
  }
  
  .circle-3 {
    width: 50px;
    height: 50px;
  }
  
  .circle {
    display: none; /* 在小屏幕上隐藏装饰元素 */
  }
}

/* 深色主题适配 */
:deep(.el-card__header) {
  background: transparent;
  border-bottom: 1px solid var(--el-border-color-light);
}

:deep(.el-form-item__label) {
  color: var(--el-text-color-primary);
}
</style>

