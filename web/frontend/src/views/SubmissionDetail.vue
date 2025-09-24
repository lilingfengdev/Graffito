<template>
  <div class="submission-detail" v-loading="loading">
    <!-- 返回按钮 -->
    <el-button 
      :icon="ArrowLeft" 
      @click="$router.back()" 
      style="margin-bottom: 20px"
    >
      返回
    </el-button>

    <div v-if="submission" class="detail-container">
      <!-- 基本信息卡片 -->
      <el-card class="info-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">投稿信息</span>
            <div class="header-tags">
              <el-tag 
                :type="getStatusType(submission.status)" 
                size="large"
              >
                {{ getStatusText(submission.status) }}
              </el-tag>
              <el-tag v-if="submission.is_anonymous" type="warning" size="large">匿名</el-tag>
              <el-tag v-if="!submission.is_safe" type="danger" size="large">不安全</el-tag>
            </div>
          </div>
        </template>
        
        <el-row :gutter="24">
          <el-col :xs="24" :md="12">
            <div class="info-section">
              <h3>基本信息</h3>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="投稿ID">
                  #{{ submission.id }}
                </el-descriptions-item>
                <el-descriptions-item label="投稿者">
                  <div class="submitter-info">
                    <el-avatar :size="24" style="background-color: #6366f1;">
                      {{ (submission.sender_nickname || submission.sender_id)[0] }}
                    </el-avatar>
                    <span>{{ submission.sender_nickname || submission.sender_id }}</span>
                    <el-tag size="small" type="info">{{ submission.sender_id }}</el-tag>
                  </div>
                </el-descriptions-item>
                <el-descriptions-item label="群组">
                  <el-tag type="info">{{ submission.group_name }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="发布编号" v-if="submission.publish_id">
                  #{{ submission.publish_id }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">
                  {{ formatTime(submission.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="更新时间" v-if="submission.updated_at">
                  {{ formatTime(submission.updated_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="发布时间" v-if="submission.published_at">
                  {{ formatTime(submission.published_at) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-col>
          
          <el-col :xs="24" :md="12">
            <div class="info-section">
              <h3>处理状态</h3>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="安全状态">
                  <el-tag :type="submission.is_safe ? 'success' : 'danger'">
                    {{ submission.is_safe ? '安全' : '不安全' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="完整性">
                  <el-tag :type="submission.is_complete ? 'success' : 'warning'">
                    {{ submission.is_complete ? '完整' : '不完整' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="匿名状态">
                  <el-tag :type="submission.is_anonymous ? 'warning' : 'info'">
                    {{ submission.is_anonymous ? '匿名' : '实名' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="处理时间" v-if="submission.processed_at">
                  {{ formatTime(submission.processed_at) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 原始内容 -->
      <el-card v-if="submission.raw_content" class="content-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span class="card-title">原始内容</span>
            <el-button 
              type="text" 
              size="small" 
              @click="rawContentCollapsed = !rawContentCollapsed"
              :icon="rawContentCollapsed ? ArrowDown : ArrowUp"
              class="collapse-button"
            >
              {{ rawContentCollapsed ? '展开' : '折叠' }}
            </el-button>
          </div>
        </template>
        <transition name="raw-content-collapse">
          <div v-show="!rawContentCollapsed" class="raw-content">
            <div v-for="(message, index) in rawMessages" :key="index" class="message-item">
              <div class="message-header">
                <el-tag size="small">{{ message.type }}</el-tag>
                <span class="message-time">{{ formatTime(message.time) }}</span>
              </div>
              <div class="message-content">
                <div v-if="message.text" class="message-text">{{ message.text }}</div>
                <div v-if="message.images && message.images.length" class="message-images">
                  <el-image
                    v-for="(image, imgIndex) in message.images"
                    :key="imgIndex"
                    :src="getImageUrl(image)"
                    :preview-src-list="message.images.map(img => getImageUrl(img))"
                    class="message-image"
                    fit="cover"
                  />
                </div>
              </div>
            </div>
          </div>
        </transition>
      </el-card>

      <!-- LLM分析结果 -->
      <el-card v-if="submission.llm_result" class="llm-card" shadow="hover">
        <template #header>
          <span class="card-title">AI分析结果</span>
        </template>
        <el-row :gutter="20">
          <el-col :xs="24" :lg="12">
            <div class="llm-section">
              <h4>分析结论</h4>
              <el-descriptions :column="1" size="small" border>
                <el-descriptions-item label="是否安全">
                  <el-tag :type="llmSafe ? 'success' : 'danger'">
                    {{ llmSafe ? '安全' : '不安全' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="是否完整">
                  <el-tag :type="llmComplete ? 'success' : 'warning'">
                    {{ llmComplete ? '完整' : '不完整' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="匿名建议">
                  <el-tag :type="llmAnon ? 'warning' : 'info'">
                    {{ llmAnon ? '匿名' : '非匿名' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="异常标记">
                  <el-tag :type="llmAbnormal ? 'warning' : 'info'">
                    {{ llmAbnormal ? '异常' : '正常' }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="AI选取消息数">
                  {{ llmMessageCount }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-col>
          <el-col :xs="24" :lg="12">
            <div class="llm-section">
              <h4>摘要与分析</h4>
              <div v-if="llmSegments.length">
                <ol style="padding-left: 18px; margin: 0;">
                  <li v-for="(seg, i) in llmSegments" :key="i" style="margin: 6px 0;">
                    {{ seg }}
                  </li>
                </ol>
              </div>
              <div v-else-if="submission.llm_result?.summary" class="summary">
                <h5>内容摘要</h5>
                <p>{{ submission.llm_result.summary }}</p>
              </div>
              <div v-if="llmImageDescs.length" class="summary" style="margin-top: 12px;">
                <h5>图片描述</h5>
                <ul style="padding-left: 18px; margin: 0;">
                  <li v-for="(d, i) in llmImageDescs" :key="i">{{ d }}</li>
                </ul>
              </div>
              <div v-if="submission.llm_result?.flags" class="flags-list" style="margin-top: 8px;">
                <el-tag v-for="flag in submission.llm_result.flags" :key="flag" type="warning" class="flag-tag">
                  {{ flag }}
                </el-tag>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 渲染结果 -->
      <el-card v-if="submission.rendered_images" class="render-card" shadow="hover">
        <template #header>
          <span class="card-title">渲染结果</span>
        </template>
        <div class="rendered-images">
          <el-image
            v-for="(image, index) in submission.rendered_images"
            :key="index"
            :src="getImageUrl(image)"
            :preview-src-list="submission.rendered_images.map(img => getImageUrl(img))"
            class="rendered-image"
            fit="contain"
          />
        </div>
      </el-card>

      <!-- 处理后内容 -->
      <el-card v-if="submission.processed_content" class="processed-card" shadow="hover">
        <template #header>
          <span class="card-title">处理后内容</span>
        </template>
        <div class="processed-content">
          <div v-if="processedText" class="processed-text">
            <h4>文本内容</h4>
            <div class="content-text">{{ processedText }}</div>
          </div>
          
          <div v-if="processedLinks.length" class="processed-links">
            <h4>链接列表</h4>
            <div>
              <el-link 
                v-for="(u, idx) in processedLinks" 
                :key="idx" 
                :href="u" 
                target="_blank" 
                rel="noopener noreferrer"
              >{{ u }}</el-link>
            </div>
          </div>
          <div v-if="submission.processed_content.images" class="processed-images">
            <h4>图片列表</h4>
            <el-image
              v-for="(image, index) in submission.processed_content.images"
              :key="index"
              :src="getImageUrl(image)"
              :preview-src-list="submission.processed_content.images.map(img => getImageUrl(img))"
              class="processed-image"
              fit="cover"
            />
          </div>
        </div>
      </el-card>

      <!-- 评论和拒绝原因 -->
      <el-card v-if="submission.comment || submission.rejection_reason" class="comments-card" shadow="hover">
        <template #header>
          <span class="card-title">管理员备注</span>
        </template>
        <div v-if="submission.comment" class="comment-section">
          <h4>管理员评论</h4>
          <div class="comment-content">{{ submission.comment }}</div>
        </div>
        <div v-if="submission.rejection_reason" class="rejection-section">
          <h4>拒绝原因</h4>
          <div class="rejection-content">{{ submission.rejection_reason }}</div>
        </div>
      </el-card>

      <!-- 操作区域 -->
      <el-card class="actions-card" shadow="hover">
        <template #header>
          <span class="card-title">快速操作</span>
        </template>
        <div class="action-buttons">
          <el-button 
            type="success" 
            :icon="Check"
            @click="handleAction('approve')"
            v-if="['waiting', 'pending'].includes(submission.status)"
          >
            通过审核
          </el-button>
          <el-button 
            type="danger" 
            :icon="Close"
            @click="handleAction('reject')"
            v-if="['waiting', 'pending'].includes(submission.status)"
          >
            拒绝投稿
          </el-button>
          <el-button 
            type="warning" 
            :icon="View"
            @click="handleAction('toggle-anon')"
          >
            {{ submission.is_anonymous ? '取消匿名' : '设为匿名' }}
          </el-button>
          <el-button 
            type="info" 
            :icon="ChatDotRound"
            @click="showCommentDialog = true"
          >
            添加评论
          </el-button>
          <el-button 
            type="primary" 
            :icon="Refresh"
            @click="handleAction('rerender')"
          >
            重新渲染
          </el-button>
          <el-button 
            v-if="submission.status === 'approved'"
            type="success" 
            :icon="Lightning"
            @click="handleAction('approve-immediate')"
          >
            立即发布
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 评论对话框 -->
    <el-dialog v-model="showCommentDialog" title="添加评论" width="500px">
      <el-form>
        <el-form-item label="评论内容">
          <el-input 
            v-model="commentText" 
            type="textarea" 
            :rows="4" 
            placeholder="请输入评论内容..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCommentDialog = false">取消</el-button>
        <el-button type="primary" @click="submitComment">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowLeft, Check, Close, View, ChatDotRound, 
  Refresh, Lightning, ArrowDown, ArrowUp
} from '@element-plus/icons-vue'
import moment from 'moment'
import api from '../api'

const route = useRoute()
const loading = ref(false)
const submission = ref(null)
const showCommentDialog = ref(false)
const commentText = ref('')
const rawContentCollapsed = ref(true)
const processedText = computed(() => {
  const pc = submission.value?.processed_content
  if (!pc) return ''
  if (typeof pc === 'string') return pc
  const t = pc.text
  if (Array.isArray(t)) {
    if (!t.length) return ''
    // 兼容字符串数组或片段对象数组
    if (typeof t[0] === 'string') return t.join('\n')
    return t.map((seg) => seg?.text || seg?.content || '').filter(Boolean).join('\n')
  }
  return t || ''
})

const processedLinks = computed(() => {
  const pc = submission.value?.processed_content
  if (!pc || typeof pc === 'string') return []
  const links = pc.links
  return Array.isArray(links) ? links : []
})

// 兼容不同 raw_content 结构，规范为 [{ type, time(ms/ISO), text, images[] }]
const rawMessages = computed(() => {
  const raw = submission.value?.raw_content
  if (!raw) return []
  let parsed = raw
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed) } catch { return [] }
  }
  let list = []
  if (Array.isArray(parsed)) {
    list = parsed
  } else if (Array.isArray(parsed.messages)) {
    list = parsed.messages
  } else if (parsed.message) {
    list = Array.isArray(parsed.message) ? parsed.message : [parsed.message]
  } else {
    list = [parsed]
  }
  const extractTextFromSegments = (segments) => {
    if (!Array.isArray(segments)) return ''
    return segments.filter(s => s && (s.type === 'text' || s.type === 'plain')).map(s => s.text || s.content || '').join('')
  }
  const extractImagesFromSegments = (segments) => {
    if (!Array.isArray(segments)) return []
    return segments.filter(s => s && (s.type === 'image' || s.type === 'img')).map(s => s.url || s.src || s.path).filter(Boolean)
  }
  const toMs = (t) => {
    if (!t) return undefined
    if (typeof t === 'number') {
      // 秒级或毫秒级
      return t > 1e12 ? t : t * 1000
    }
    // 字符串交给 moment 解析
    return t
  }
  return list.map((m) => ({
    type: m?.type || m?.post_type || m?.message_type || 'message',
    time: toMs(m?.time || m?.timestamp || m?.create_time || m?.date || m?.ts),
    text: m?.text || m?.content || m?.message || extractTextFromSegments(m?.segments),
    images: m?.images || m?.image_urls || extractImagesFromSegments(m?.segments) || [],
  }))
})

// LLM 结果映射与展示
const llm = computed(() => submission.value?.llm_result || {})
const normalizeBool = (v, def = false) => {
  if (typeof v === 'boolean') return v
  if (typeof v === 'string') return v.trim().toLowerCase() === 'true'
  if (typeof v === 'number') return v !== 0
  return def
}
const llmSafe = computed(() => normalizeBool(llm.value?.safemsg, !!submission.value?.is_safe))
const llmComplete = computed(() => normalizeBool(llm.value?.isover, !!submission.value?.is_complete))
const llmAnon = computed(() => normalizeBool(llm.value?.needpriv, !!submission.value?.is_anonymous))
const llmAbnormal = computed(() => normalizeBool(llm.value?.notregular, false))
const llmMessageCount = computed(() => {
  const m = llm.value?.messages
  return Array.isArray(m) ? m.length : 0
})
const llmSegments = computed(() => {
  const segs = llm.value?.segments
  if (Array.isArray(segs)) return segs.filter(s => typeof s === 'string' && s.trim()).map(s => s.trim())
  const pcText = submission.value?.processed_content?.text
  if (Array.isArray(pcText)) return pcText
  return []
})
const llmImageDescs = computed(() => {
  const out = []
  const messages = llm.value?.messages
  const walk = (node) => {
    if (!node) return
    if (Array.isArray(node)) {
      node.forEach(walk)
      return
    }
    if (typeof node !== 'object') return
    if (node.type === 'image' && typeof node.describe === 'string' && node.describe.trim()) {
      out.push(node.describe.trim())
    }
    if (Array.isArray(node.message)) walk(node.message)
    if (node.data && Array.isArray(node.data?.messages)) walk(node.data.messages)
    if (node.data && Array.isArray(node.data?.content)) walk(node.data.content)
  }
  if (Array.isArray(messages)) messages.forEach(walk)
  return out
})

const loadSubmissionDetail = async () => {
  loading.value = true
  try {
    const { data } = await api.get(`/audit/${route.params.id}/detail`)
    submission.value = data
  } catch (error) {
    ElMessage.error('加载投稿详情失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleAction = async (action) => {
  const submissionId = submission.value.id
  
  try {
    let result
    switch (action) {
      case 'approve':
        result = await api.post(`/audit/${submissionId}/approve`)
        break
      case 'reject':
        const reason = await ElMessageBox.prompt('请输入拒绝原因', '拒绝投稿', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputPlaceholder: '请输入拒绝原因...'
        })
        result = await api.post(`/audit/${submissionId}/reject`, { 
          comment: reason.value 
        })
        break
      case 'toggle-anon':
        result = await api.post(`/audit/${submissionId}/toggle-anon`)
        break
      case 'rerender':
        result = await api.post(`/audit/${submissionId}/rerender`)
        break
      case 'approve-immediate':
        result = await api.post(`/audit/${submissionId}/approve-immediate`)
        break
    }
    
    if (result) {
      ElMessage.success(result.data.message || '操作成功')
      await loadSubmissionDetail() // 重新加载数据
    }
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  }
}

const submitComment = async () => {
  if (!commentText.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  
  try {
    const result = await api.post(`/audit/${submission.value.id}/comment`, {
      comment: commentText.value
    })
    ElMessage.success(result.data.message || '评论添加成功')
    showCommentDialog.value = false
    commentText.value = ''
    await loadSubmissionDetail()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加评论失败')
  }
}

const getImageUrl = (imagePath) => {
  // 兼容字符串或对象结构
  if (!imagePath) return ''
  const API_BASE = String(api?.defaults?.baseURL || '').replace(/\/+$/, '')
  const toApiUrl = (rel) => {
    const p = rel.startsWith('/') ? rel : `/${rel}`
    return API_BASE ? `${API_BASE}${p}` : p
  }
  // 将 token 以查询参数方式附加到 /data/ 资源，适配 <img> 不带头的场景
  const withTokenIfData = (url) => {
    if (!url) return url
    // 仅对指向 /data/ 的相对或同源 URL 添加 token
    try {
      const isDataPath = /(^\/data\/)|(^.*\/data\/)/.test(url)
      if (!isDataPath) return url
      const token = localStorage.getItem('token')
      if (!token) return url
      const sep = url.includes('?') ? '&' : '?'
      return `${url}${sep}access_token=${encodeURIComponent(token)}`
    } catch {
      return url
    }
  }
  if (typeof imagePath === 'string') {
    if (imagePath.startsWith('http') || imagePath.startsWith('data:image')) return imagePath
    const normalized = imagePath.replace(/\\/g, '/')
    if (normalized.includes('data/cache/rendered')) {
      return withTokenIfData(toApiUrl(normalized))
    }
    return withTokenIfData(toApiUrl(`images/${normalized}`))
  }
  const url = imagePath.url || imagePath.src
  const path = imagePath.path || imagePath.local_path
  if (url) {
    if (typeof url === 'string' && url.includes('data/cache/rendered')) {
      return withTokenIfData(toApiUrl(url.replace(/\\/g, '/')))
    }
    return withTokenIfData(url)
  }
  if (path) {
    const normalized = String(path).replace(/\\/g, '/')
    if (normalized.includes('data/cache/rendered')) {
      return withTokenIfData(toApiUrl(normalized))
    }
    return withTokenIfData(toApiUrl(`images/${normalized}`))
  }
  return ''
}

const getStatusType = (status) => {
  const typeMap = {
    'pending': 'warning',
    'processing': 'warning',
    'waiting': 'warning',
    'approved': 'success',
    'published': 'primary',
    'rejected': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'pending': '待处理',
    'processing': '处理中',
    'waiting': '等待审核',
    'approved': '已通过',
    'published': '已发布',
    'rejected': '已拒绝'
  }
  return textMap[status] || status
}

const getRiskType = (risk) => {
  const typeMap = {
    'low': 'success',
    'medium': 'warning',
    'high': 'danger'
  }
  return typeMap[risk] || 'info'
}

const formatTime = (input) => {
  // 支持毫秒/秒/ISO字符串
  if (!input) return ''
  if (typeof input === 'number') {
    const ms = input > 1e12 ? input : input * 1000
    return moment(ms).format('YYYY-MM-DD HH:mm:ss')
  }
  return moment(input).format('YYYY-MM-DD HH:mm:ss')
}

onMounted(() => {
  loadSubmissionDetail()
})
</script>

<style scoped>
.submission-detail {
  max-width: 1200px;
  margin: 0 auto;
}

.detail-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.header-tags {
  display: flex;
  gap: 8px;
}

.info-section h3 {
  margin: 0 0 16px 0;
  color: var(--el-text-color-primary);
}

.submitter-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.raw-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 4px;
}

.message-item {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 16px;
  background: var(--el-bg-color);
  margin-bottom: 12px;
  transition: all 0.3s ease;
}

.message-item:hover {
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.message-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: var(--el-font-family);
}

.message-text {
  margin-bottom: 12px;
  line-height: 1.6;
  color: var(--el-text-color-primary);
  font-size: 14px;
  word-break: break-word;
  white-space: pre-wrap;
  background: var(--el-fill-color-extra-light);
  padding: 12px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-light);
}

.message-text:empty {
  display: none;
}

.message-images {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 8px;
}

.message-image {
  width: 100%;
  height: 120px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-light);
  transition: all 0.3s ease;
  cursor: pointer;
}

.message-image:hover {
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.llm-section h4 {
  margin: 0 0 12px 0;
  color: var(--el-text-color-primary);
}

.flags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.flag-tag {
  margin: 0;
}

.summary h5 {
  margin: 0 0 8px 0;
  color: var(--el-text-color-primary);
}

.summary p {
  margin: 0;
  line-height: 1.6;
  color: var(--el-text-color-regular);
}

.rendered-images {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.rendered-image {
  width: 100%;
  max-height: 400px;
  border-radius: 8px;
}

.processed-content h4 {
  margin: 0 0 12px 0;
  color: var(--el-text-color-primary);
}

.content-text {
  padding: 16px;
  background: var(--el-fill-color-extra-light);
  border-radius: 6px;
  line-height: 1.6;
  margin-bottom: 20px;
}

.processed-images {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.processed-image {
  width: 120px;
  height: 120px;
  border-radius: 6px;
}

.comment-section,
.rejection-section {
  margin-bottom: 16px;
}

.comment-section h4,
.rejection-section h4 {
  margin: 0 0 8px 0;
  color: var(--el-text-color-primary);
}

.comment-content,
.rejection-content {
  padding: 12px;
  background: var(--el-fill-color-extra-light);
  border-radius: 6px;
  line-height: 1.6;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* 折叠按钮动画 */
.collapse-button {
  transition: all 0.2s ease-in-out;
}

.collapse-button:hover {
  color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.collapse-button .el-icon {
  transition: transform 0.3s ease-in-out;
}

/* 折叠内容动画 */
.raw-content-collapse-enter-active,
.raw-content-collapse-leave-active {
  transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  overflow: hidden;
}

.raw-content-collapse-enter-from {
  opacity: 0;
  transform: translateY(-10px);
  max-height: 0;
}

.raw-content-collapse-enter-to {
  opacity: 1;
  transform: translateY(0);
  max-height: 2000px;
}

.raw-content-collapse-leave-from {
  opacity: 1;
  transform: translateY(0);
  max-height: 2000px;
}

.raw-content-collapse-leave-to {
  opacity: 0;
  transform: translateY(-10px);
  max-height: 0;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .submission-detail {
    max-width: 100%;
    padding: 0 16px;
  }
  
  .message-images {
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 10px;
  }
  
  .message-image {
    height: 100px;
  }
}

@media (max-width: 768px) {
  .submission-detail {
    padding: 0 12px;
  }
  
  .detail-container {
    gap: 16px;
  }
  
  .message-item {
    padding: 12px;
    margin-bottom: 10px;
  }
  
  .message-header {
    margin-bottom: 10px;
    padding-bottom: 6px;
  }
  
  .message-time {
    font-size: 11px;
  }
  
  .message-text {
    padding: 10px;
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 10px;
  }
  
  .message-images {
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  
  .message-image {
    height: 80px;
  }
  
  .rendered-images {
    grid-template-columns: 1fr;
  }
  
  .action-buttons {
    flex-direction: column;
  }
}

@media (max-width: 480px) {
  .submission-detail {
    padding: 0 8px;
  }
  
  .raw-content {
    gap: 16px;
    padding: 2px;
  }
  
  .message-item {
    padding: 10px;
    margin-bottom: 8px;
  }
  
  .message-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
    margin-bottom: 8px;
    padding-bottom: 4px;
  }
  
  .message-time {
    align-self: flex-end;
    font-size: 10px;
  }
  
  .message-text {
    padding: 8px;
    font-size: 12px;
    line-height: 1.4;
    margin-bottom: 8px;
  }
  
  .message-images {
    grid-template-columns: 1fr;
  }
  
  .message-image {
    height: 120px;
  }
}
</style>
