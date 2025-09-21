<template>
  <div class="container">
    <div class="card">
      <div class="row space">
        <div>
          <strong>审核列表</strong>
        </div>
        <div class="row">
          <select v-model="statusFilter">
            <option value="">全部</option>
            <option value="waiting">等待审核</option>
            <option value="approved">已通过</option>
            <option value="rejected">已拒绝</option>
          </select>
          <button class="secondary" @click="load">刷新</button>
          <button class="secondary" @click="logout">退出</button>
        </div>
      </div>
    </div>

    <div class="card" v-if="isSuperadmin">
      <div class="row">
        <input v-model.number="inviteMinutes" type="number" min="1" placeholder="邀请有效(分钟)" />
        <button @click="createInvite">创建邀请链接</button>
      </div>
      <div v-if="inviteLink" class="muted">邀请链接：{{ inviteLink }}</div>
    </div>

    <div class="list">
      <div v-for="s in submissions" :key="s.id" class="card">
        <div class="row space">
          <div>
            <div>#{{ s.id }} - {{ s.sender_nickname || s.sender_id }} <span class="badge">{{ s.group_name }}</span></div>
            <div class="muted">状态：{{ s.status }}，创建：{{ s.created_at }}</div>
          </div>
          <div class="actions">
            <button @click="approve(s.id)">通过</button>
            <button @click="reject(s.id)">拒绝</button>
            <button class="secondary" @click="toggleAnon(s.id)">切换匿名</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import api from '../api'
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const statusFilter = ref('waiting')
const submissions = ref([])
const me = ref(null)
const inviteMinutes = ref(60)
const inviteLink = ref('')

const isSuperadmin = computed(()=> me.value?.is_superadmin)

async function load(){
  const { data } = await api.get('/audit/submissions', { params: { status_filter: statusFilter.value } })
  submissions.value = data
}

async function approve(id){ await api.post(`/audit/${id}/approve`); await load() }
async function reject(id){ await api.post(`/audit/${id}/reject`, { comment: '不符合规范' }); await load() }
async function toggleAnon(id){ await api.post(`/audit/${id}/toggle-anon`); await load() }

async function createInvite(){
  const { data } = await api.post('/invites/create', { expires_in_minutes: Number(inviteMinutes.value) || 60 })
  inviteLink.value = location.origin + '/register?invite=' + data.token
}

async function fetchMe(){
  try{ const { data } = await api.get('/auth/me'); me.value = data }catch{ me.value = null }
}

function logout(){ localStorage.removeItem('token'); router.push('/login') }

onMounted(async ()=>{ await fetchMe(); await load() })
</script>

<style scoped>
.container{max-width:1000px;margin:24px auto;padding:0 16px}
.card{background:#111827;color:#e5e7eb;border:1px solid #1f2937;border-radius:12px;padding:16px;margin-bottom:16px}
input,button,select{padding:10px 12px;border-radius:8px;border:1px solid #374151;background:#0b1020;color:#e5e7eb}
input{width:100%}
.row{display:flex;gap:12px;align-items:center}
.grid{display:grid;gap:12px}
.list{display:grid;gap:12px}
.space{justify-content:space-between}
.badge{font-size:12px;padding:2px 8px;border-radius:999px;background:#1f2937;border:1px solid #374151}
.actions{display:flex;gap:8px;flex-wrap:wrap}
.muted{color:#9ca3af}
.secondary{background:#0b1020}
button{cursor:pointer;background:linear-gradient(135deg,#4f46e5,#7c3aed);border:none}
</style>

