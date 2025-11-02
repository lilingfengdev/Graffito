<template>
  <div class="login-page">
    <!-- 主题切换按钮 -->
    <div class="theme-toggle">
      <el-tooltip :content="themeText" placement="left">
        <el-button 
          :icon="themeIconComponent" 
          circle 
          size="large"
          @click="toggleTheme"
          class="theme-btn xw-glass"
        />
      </el-tooltip>
    </div>
    
    <!-- 登录容器 -->
    <div class="login-container">
      <!-- 品牌标题 -->
      <div class="brand-header xw-slide-up">
        <el-icon :size="48" color="#6366f1" class="brand-icon">
          <Document />
        </el-icon>
        <h1 class="brand-title">Graffito</h1>
        <p class="brand-subtitle">校园墙审核管理系统</p>
      </div>
      
      <!-- 登录卡片 -->
      <el-card class="login-card xw-glass xw-scale-in" shadow="never">
        <template #header>
          <div class="card-header">
            <h2>管理员登录</h2>
            <p>欢迎回来，请登录您的账号</p>
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
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              show-password
              clearable
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item>
            <el-button 
              type="primary" 
              size="large"
              native-type="submit"
              style="width: 100%"
              :loading="logging"
              @click="handleLogin"
            >
              <span v-if="!logging">登录</span>
              <span v-else>登录中...</span>
            </el-button>
          </el-form-item>
          
          <div class="login-footer">
            <router-link to="/register" class="register-link">
              <el-icon><Plus /></el-icon>
              <span>使用邀请注册</span>
            </router-link>
          </div>
        </el-form>
      </el-card>

      <!-- 初始化超级管理员卡片 -->
      <el-card 
        v-if="!superadminExists" 
        class="init-card xw-glass xw-scale-in" 
        shadow="never"
      >
        <template #header>
          <div class="init-header">
            <el-icon :size="24" color="#f59e0b"><Warning /></el-icon>
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
    
    <!-- 背景装饰 -->
    <div class="bg-decoration" aria-hidden="true">
      <div class="circle circle-1"></div>
      <div class="circle circle-2"></div>
      <div class="circle circle-3"></div>
      <div class="gradient-mesh"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, User, Lock, Warning, Moon, Sunny, Plus } from '@element-plus/icons-vue'
import api from '../api'
import { useTheme } from '../composables/useTheme'

const router = useRouter()

// 主题管理
const { isDark, toggleTheme, themeText } = useTheme()
const themeIconComponent = computed(() => isDark.value ? Sunny : Moon)

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
    
    localStorage.setItem('access_token', data.access_token)
    try { localStorage.setItem('token', data.access_token) } catch(_) {}
    ElMessage.success('登录成功，欢迎回来！')
    const redirect = new URLSearchParams(window.location.search).get('redirect')
    router.push(redirect || '/')
  } catch (error) {
    const message = error.response?.data?.detail || '登录失败，请检查用户名和密码'
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
  background: var(--xw-gradient-primary);
  overflow: hidden;
  padding: var(--xw-space-6);
}

.theme-toggle {
  position: fixed;
  top: var(--xw-space-6);
  right: var(--xw-space-6);
  z-index: 1000;
  animation: xw-fade-in 0.5s ease;
}

.theme-btn {
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition: var(--xw-transition);
}

.theme-btn:hover {
  transform: rotate(180deg) scale(1.1);
}

.login-container {
  width: 100%;
  max-width: 420px;
  position: relative;
  z-index: 2;
  animation-delay: 0.1s;
}

/* 品牌标题 */
.brand-header {
  text-align: center;
  margin-bottom: var(--xw-space-8);
  animation-delay: 0.2s;
}

.brand-icon {
  animation: xw-scale-in 0.5s ease;
}

.brand-title {
  margin: var(--xw-space-4) 0 var(--xw-space-2);
  font-size: var(--xw-text-4xl);
  font-weight: var(--xw-font-bold);
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-light), #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
  line-height: var(--xw-leading-tight);
}

.brand-subtitle {
  margin: 0;
  color: var(--xw-text-secondary);
  font-size: var(--xw-text-lg);
  font-weight: var(--xw-font-medium);
}

/* 登录卡片 */
.login-card {
  margin-bottom: var(--xw-space-6);
  animation-delay: 0.3s;
}

.card-header h2 {
  margin: 0 0 var(--xw-space-2);
  color: var(--xw-text-primary);
  font-size: var(--xw-text-2xl);
  font-weight: var(--xw-font-bold);
}

.card-header p {
  margin: 0;
  color: var(--xw-text-tertiary);
  font-size: var(--xw-text-sm);
}

.login-footer {
  display: flex;
  justify-content: center;
  margin-top: var(--xw-space-4);
}

.register-link {
  display: inline-flex;
  align-items: center;
  gap: var(--xw-space-2);
  color: var(--xw-primary);
  text-decoration: none;
  font-size: var(--xw-text-sm);
  font-weight: var(--xw-font-medium);
  padding: var(--xw-space-2) var(--xw-space-3);
  border-radius: var(--xw-radius-lg);
  transition: var(--xw-transition);
}

.register-link:hover {
  background: var(--xw-gradient-highlight);
  transform: translateY(-1px);
}

/* 初始化卡片 */
.init-card {
  animation-delay: 0.4s;
}

.init-header {
  display: flex;
  align-items: center;
  gap: var(--xw-space-2);
  color: var(--xw-warning);
  font-weight: var(--xw-font-semibold);
  font-size: var(--xw-text-lg);
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
  overflow: hidden;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
  filter: blur(60px);
  animation: xw-float 6s ease-in-out infinite;
}

html.light .circle {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.05));
}

.circle-1 {
  width: 400px;
  height: 400px;
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.circle-2 {
  width: 300px;
  height: 300px;
  bottom: -80px;
  right: -80px;
  animation-delay: 2s;
}

.circle-3 {
  width: 200px;
  height: 200px;
  top: 40%;
  right: 10%;
  animation-delay: 4s;
}

.gradient-mesh {
  position: absolute;
  inset: 0;
  background: 
    radial-gradient(ellipse 800px 600px at 20% 30%, rgba(99, 102, 241, 0.12), transparent),
    radial-gradient(ellipse 600px 800px at 80% 70%, rgba(139, 92, 246, 0.08), transparent);
  mix-blend-mode: normal;
  opacity: 0.6;
}

html.light .gradient-mesh {
  background: 
    radial-gradient(ellipse 800px 600px at 20% 30%, rgba(99, 102, 241, 0.08), transparent),
    radial-gradient(ellipse 600px 800px at 80% 70%, rgba(139, 92, 246, 0.05), transparent);
}

@keyframes xw-float {
  0%, 100% {
    transform: translate(0, 0);
  }
  33% {
    transform: translate(30px, -30px);
  }
  66% {
    transform: translate(-20px, 20px);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .login-page {
    padding: var(--xw-space-4);
  }
  
  .login-container {
    max-width: 100%;
  }
  
  .theme-toggle {
    top: var(--xw-space-4);
    right: var(--xw-space-4);
  }
  
  .brand-title {
    font-size: var(--xw-text-3xl);
  }
  
  .brand-subtitle {
    font-size: var(--xw-text-base);
  }
  
  .circle-1 {
    width: 250px;
    height: 250px;
  }
  
  .circle-2 {
    width: 200px;
    height: 200px;
  }
  
  .circle-3 {
    width: 150px;
    height: 150px;
  }
}

@media (max-width: 480px) {
  .brand-title {
    font-size: var(--xw-text-2xl);
  }
  
  .brand-subtitle {
    font-size: var(--xw-text-sm);
  }
  
  .card-header h2 {
    font-size: var(--xw-text-xl);
  }
  
  .circle {
    display: none;
  }
}

/* 无障碍 */
@media (prefers-reduced-motion: reduce) {
  .circle,
  .brand-icon,
  .login-card,
  .theme-btn {
    animation: none !important;
  }
}
</style>
