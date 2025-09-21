<template>
  <div class="container">
    <h2>登录</h2>
    <div class="card">
      <div class="grid">
        <input v-model="username" placeholder="用户名" />
        <input v-model="password" type="password" placeholder="密码" />
        <button @click="doLogin">登录</button>
        <router-link to="/register">使用邀请注册</router-link>
      </div>
    </div>
    <div class="card" v-if="!superadminExists">
      <h3>初始化超级管理员</h3>
      <div class="grid">
        <input v-model="initName" placeholder="用户名" />
        <input v-model="initPass" type="password" placeholder="密码" />
        <input v-model="initDisplay" placeholder="显示名称（可选）" />
        <button class="secondary" @click="initSuper">创建超级管理员</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import api from '../api'
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const username = ref('')
const password = ref('')
const superadminExists = ref(true)
const initName = ref('')
const initPass = ref('')
const initDisplay = ref('')

async function doLogin(){
  const params = new URLSearchParams()
  params.set('username', username.value)
  params.set('password', password.value)
  const { data } = await api.post('/auth/login', params, { headers:{'Content-Type':'application/x-www-form-urlencoded'} })
  localStorage.setItem('token', data.access_token)
  router.push('/audit')
}

async function initSuper(){
  await api.post('/auth/init-superadmin', {
    username: initName.value,
    password: initPass.value,
    display_name: initDisplay.value
  })
  alert('超级管理员已创建，去登录')
}

onMounted(async ()=>{
  try{
    const { data } = await api.get('/auth/has-superadmin')
    superadminExists.value = !!data?.exists
  }catch{ superadminExists.value = true }
})
</script>

<style scoped>
.container{max-width:720px;margin:24px auto;padding:0 16px}
.card{background:#111827;color:#e5e7eb;border:1px solid #1f2937;border-radius:12px;padding:16px;margin-bottom:16px}
input,button{padding:10px 12px;border-radius:8px;border:1px solid #374151;background:#0b1020;color:#e5e7eb}
input{width:100%}
.grid{display:grid;gap:12px}
.secondary{background:#0b1020}
button{cursor:pointer;background:linear-gradient(135deg,#4f46e5,#7c3aed);border:none}
</style>

