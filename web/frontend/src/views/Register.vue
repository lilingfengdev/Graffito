<template>
  <div class="login-page">
    <div class="login-container">
      <!-- 注册表单（统一 Login 风格） -->
      <el-card class="login-card" shadow="always">
        <template #header>
          <div class="login-header">
            <div class="logo">
              <el-icon size="32" color="#6366f1"><Document /></el-icon>
              <span class="logo-text">XWall 审核后台</span>
            </div>
            <p class="subtitle">邀请注册</p>
          </div>
        </template>

        <el-form 
          :model="form" 
          :rules="rules"
          ref="registerFormRef"
          size="large"
          @submit.prevent="register"
        >
          <el-form-item prop="token">
            <el-input
              v-model="form.token"
              placeholder="请输入邀请令牌"
              :prefix-icon="Key"
              clearable
            />
          </el-form-item>

          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              :prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>

          <el-form-item prop="displayName">
            <el-input
              v-model="form.displayName"
              placeholder="请输入显示名称（可选）"
              :prefix-icon="Avatar"
              clearable
            />
          </el-form-item>

          <el-form-item>
            <el-button 
              type="primary" 
              size="large"
              style="width: 100%"
              :loading="loading"
              @click="register"
            >
              {{ loading ? '注册中...' : '立即注册' }}
            </el-button>
          </el-form-item>

          <el-form-item>
            <div class="login-footer">
              <router-link to="/login" class="register-link">返回登录</router-link>
            </div>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <!-- 主题切换按钮（统一 Login 风格） -->
    <div class="theme-toggle">
      <el-button 
        :icon="themeIconComponent" 
        circle 
        size="large"
        @click="toggleTheme"
        :title="themeText"
      />
    </div>

    <!-- 背景装饰（统一 Login 风格） -->
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Key, User, Lock, Avatar, Moon, Sunny } from '@element-plus/icons-vue'
import api from '../api'
import { useTheme } from '../composables/useTheme'

const router = useRouter()

// 主题管理（与 Login 保持一致）
const { isDark, toggleTheme, themeText } = useTheme()
const themeIconComponent = computed(() => {
  return isDark.value ? Sunny : Moon
})

// 表单引用与状态
const registerFormRef = ref(null)
const loading = ref(false)

// 表单数据
const form = ref({
  token: '',
  username: '',
  password: '',
  confirmPassword: '',
  displayName: ''
})

// 表单验证规则（保持原有逻辑）
const rules = {
  token: [
    { required: true, message: '请输入邀请令牌', trigger: 'blur' },
    { min: 10, message: '邀请令牌长度不正确', trigger: 'blur' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为3-20个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '密码长度为6-50个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== form.value.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  displayName: [
    { max: 50, message: '显示名称不能超过50个字符', trigger: 'blur' }
  ]
}

// 页面加载时处理邀请令牌
onMounted(() => {
  const url = new URL(window.location.href)
  const inviteToken = url.searchParams.get('invite') || 
    (new URLSearchParams(location.hash.replace(/^#/, ''))).get('invite')
  
  if (inviteToken) {
    form.value.token = inviteToken.trim()
    ElMessage.success('已自动填入邀请令牌')
  }
})

// 注册函数（保持原有逻辑）
const register = async () => {
  if (!registerFormRef.value) return
  
  try {
    await registerFormRef.value.validate()
  } catch (error) {
    ElMessage.warning('请检查表单填写是否正确')
    return
  }
  
  loading.value = true
  
  try {
    await api.post('/auth/register-invite', {
      token: form.value.token.trim(),
      username: form.value.username,
      password: form.value.password,
      display_name: form.value.displayName || undefined
    })
    
    await ElMessageBox.confirm(
      '账号注册成功！是否立即跳转到登录页面？',
      '注册成功',
      {
        confirmButtonText: '立即登录',
        cancelButtonText: '稍后登录',
        type: 'success'
      }
    )
    
    router.push({
      path: '/login',
      query: { username: form.value.username }
    })
    
  } catch (error) {
    console.error('注册失败:', error)
    
    let errorMessage = '注册失败，请稍后重试'
    
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail
      if (detail.includes('token')) {
        errorMessage = '邀请令牌无效或已过期，请检查链接是否正确'
      } else if (detail.includes('username')) {
        errorMessage = '用户名已被占用，请尝试其他用户名'
      } else if (detail.includes('password')) {
        errorMessage = '密码格式不正确，请检查密码要求'
      } else {
        errorMessage = detail
      }
    }
    
    ElMessage.error(errorMessage)
  } finally {
    loading.value = false
  }
}

// 重置表单（备用）
const resetForm = () => {
  if (registerFormRef.value) {
    registerFormRef.value.resetFields()
  }
}
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
  
  .login-card {
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

