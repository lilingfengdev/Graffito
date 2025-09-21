<template>
  <div class="container">
    <h2>使用邀请注册管理员</h2>
    <div class="card">
      <div class="grid">
        <input v-model="token" placeholder="邀请令牌" />
        <input v-model="username" placeholder="用户名" />
        <input v-model="password" type="password" placeholder="密码" />
        <input v-model="displayName" placeholder="显示名称（可选）" />
        <button class="secondary" @click="register">注册</button>
      </div>
    </div>
    <router-link to="/login">返回登录</router-link>
  </div>
</template>

<script setup>
import api from '../api'
import { ref, onMounted } from 'vue'

const token = ref('')
const username = ref('')
const password = ref('')
const displayName = ref('')

onMounted(()=>{
  const url = new URL(window.location.href)
  const inv = url.searchParams.get('invite') || (new URLSearchParams(location.hash.replace(/^#/,''))).get('invite')
  if(inv) token.value = inv
})

async function register(){
  await api.post('/auth/register-invite', {
    token: token.value,
    username: username.value,
    password: password.value,
    display_name: displayName.value
  })
  alert('注册成功，请登录')
}
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

