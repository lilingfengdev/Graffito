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
                    <span class="submitter-name">{{ submission.sender_nickname || submission.sender_id }}</span>
                    <el-tag size="small" type="info">{{ submission.sender_id }}</el-tag>
                    <el-button 
                      size="small" 
                      type="primary" 
                      plain
                      round
                      @click="viewUserDetail(submission.sender_id)"
                      :icon="View"
                      class="view-detail-btn"
                    >
                      详情
                    </el-button>
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
                <el-descriptions-item label="处理管理员" v-if="submission.processed_by">
                  <el-tag type="success" size="small">{{ submission.processed_by }}</el-tag>
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
                <div v-if="message.text" class="message-text">
                  <EmoticonText :content="message.text" />
                </div>
                <div v-if="message.images && message.images.length" class="message-images">
                  <SecureImage
                    v-for="(image, imgIndex) in message.images"
                    :key="imgIndex"
                    :src="getImageUrl(image)"
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
        
        <!-- AI生成的总结 - 优先显示 -->
        <div v-if="submission.llm_result?.summary" class="llm-summary-section">
          <div class="summary-header">
            <el-icon :size="18" color="var(--el-color-primary)">
              <ChatDotRound />
            </el-icon>
            <h4>内容总结</h4>
          </div>
          <div class="summary-content">
            <p>{{ submission.llm_result.summary }}</p>
          </div>
        </div>

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
              <h4>文本片段</h4>
              <div v-if="llmSegments.length">
                <ol style="padding-left: 18px; margin: 0;">
                  <li v-for="(seg, i) in llmSegments" :key="i" style="margin: 6px 0;">
                    {{ seg }}
                  </li>
                </ol>
              </div>
              <div v-else class="empty-hint">
                <el-empty description="无文本片段" :image-size="60" />
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
      <el-card v-if="submission.rendered_images && submission.status !== 'deleted'" class="render-card" shadow="hover">
        <template #header>
          <span class="card-title">渲染结果</span>
        </template>
        <div class="rendered-images">
          <SecureImage
            v-for="(image, index) in submission.rendered_images"
            :key="index"
            :src="getImageUrl(image)"
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
            <div class="content-text">
              <EmoticonText :content="processedText" />
            </div>
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
            <SecureImage
              v-for="(image, index) in submission.processed_content.images"
              :key="index"
              :src="getImageUrl(image)"
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
          <div class="comment-content">
            <EmoticonText :content="submission.comment" />
          </div>
        </div>
        <div v-if="submission.rejection_reason" class="rejection-section">
          <h4>拒绝原因</h4>
          <div class="rejection-content">
            <EmoticonText :content="submission.rejection_reason" />
          </div>
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
          <el-button 
            v-if="['approved', 'published'].includes(submission.status)"
            type="danger" 
            :icon="Delete"
            @click="handleAction('delete')"
            plain
          >
            删除投稿
          </el-button>
        </div>
      </el-card>

      <!-- 平台评论区域 -->
      <el-card 
        v-if="submission.status === 'published'" 
        class="platform-comments-card" 
        shadow="hover"
      >
        <template #header>
          <div class="card-header">
            <span class="card-title">平台评论</span>
            <el-button 
              type="primary" 
              size="small"
              :icon="Refresh"
              :loading="loadingComments"
              @click="loadPlatformComments"
            >
              刷新评论
            </el-button>
          </div>
        </template>
        
        <div v-loading="loadingComments">
          <div v-if="!platformCommentsLoaded && !loadingComments" class="empty-comments">
            <el-empty description="点击刷新按钮加载平台评论" />
          </div>
          
          <div v-else-if="platformComments.length === 0 && !loadingComments" class="empty-comments">
            <el-empty description="暂无平台评论" />
          </div>
          
          <div v-else class="platforms-list">
            <div 
              v-for="(platform, idx) in platformComments" 
              :key="idx"
              class="platform-section"
            >
              <h3 class="platform-title">
                <el-tag :type="getPlatformTagType(platform.platform)" size="large">
                  {{ getPlatformName(platform.platform) }}
                </el-tag>
                <span class="comment-count">共 {{ platform.total }} 条评论</span>
              </h3>
              
              <div class="comments-list">
                <div 
                  v-for="comment in platform.comments" 
                  :key="comment.id"
                  class="comment-item"
                >
                  <div class="comment-header">
                    <div class="user-info">
                      <SecureAvatar 
                        :size="36" 
                        :src="comment.user_avatar"
                        :placeholder="comment.user_name ? comment.user_name[0] : '?'"
                        background-color="#6366f1"
                        shape="circle"
                      />
                      <div class="user-details">
                        <span class="user-name">{{ comment.user_name }}</span>
                        <span class="user-id">{{ comment.user_id }}</span>
                      </div>
                    </div>
                    <div class="comment-time">
                      {{ formatCommentTime(comment.created_at) }}
                    </div>
                  </div>
                  
                  <div class="comment-content">
                    <EmoticonText :content="comment.content" />
                  </div>
                  
                  <!-- 评论中的图片 -->
                  <div v-if="comment.images && comment.images.length" class="comment-images">
                    <div
                      v-for="(image, imgIndex) in comment.images"
                      :key="imgIndex"
                      class="comment-image-wrapper"
                      @click="openImagePreview(comment.images, imgIndex)"
                    >
                      <img
                        :src="image"
                        class="comment-image"
                        referrerpolicy="no-referrer"
                        loading="lazy"
                        alt="评论图片"
                        @error="handleImageError"
                      />
                    </div>
                  </div>
                  
                  <!-- 图片预览器 -->
                  <el-image-viewer
                    v-if="showImageViewer"
                    :url-list="previewImages"
                    :initial-index="previewIndex"
                    @close="closeImagePreview"
                    teleported
                  />
                  
                  <div class="comment-footer">
                    <span class="comment-stat">
                      <el-icon><Star /></el-icon>
                      {{ comment.like_count }}
                    </span>
                    <span class="comment-stat" v-if="comment.reply_count > 0">
                      <el-icon><ChatDotRound /></el-icon>
                      {{ comment.reply_count }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
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

    <!-- 用户详情对话框 -->
    <el-dialog v-model="showUserDialog" title="投稿者详情" width="600px">
      <div v-loading="loadingUser">
        <div v-if="selectedUser" class="user-detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户ID">
              {{ selectedUser.user_id }}
            </el-descriptions-item>
            <el-descriptions-item label="昵称">
              {{ selectedUser.nickname || '未知' }}
            </el-descriptions-item>
            <el-descriptions-item label="QQ等级">
              {{ selectedUser.qq_level || '未知' }}
            </el-descriptions-item>
            <el-descriptions-item label="在线状态">
              {{ selectedUser.status || '未知' }}
            </el-descriptions-item>
            <el-descriptions-item label="性别" v-if="selectedUser.sex && selectedUser.sex !== '未知'">
              {{ selectedUser.sex }}
            </el-descriptions-item>
            <el-descriptions-item label="年龄" v-if="selectedUser.age && selectedUser.age !== '未知'">
              {{ selectedUser.age }}
            </el-descriptions-item>
            <el-descriptions-item label="登录天数" v-if="selectedUser.login_days && selectedUser.login_days !== '未知'">
              {{ selectedUser.login_days }}
            </el-descriptions-item>
            <el-descriptions-item label="地区" v-if="selectedUser.area">
              {{ selectedUser.area }}
            </el-descriptions-item>
            <el-descriptions-item label="群名片" v-if="selectedUser.card" :span="2">
              {{ selectedUser.card }}
            </el-descriptions-item>
            <el-descriptions-item label="头衔" v-if="selectedUser.title" :span="2">
              {{ selectedUser.title }}
            </el-descriptions-item>
          </el-descriptions>
          
          <div class="user-stats" v-if="selectedUser.stats" style="margin-top: 20px;">
            <h4 style="margin-bottom: 12px;">投稿统计</h4>
            <el-row :gutter="16">
              <el-col :span="6">
                <div class="stat-item" style="text-align: center; padding: 16px; background: var(--el-fill-color-light); border-radius: 8px;">
                  <div style="font-size: 24px; font-weight: 600; color: var(--el-color-primary);">{{ selectedUser.stats.total || 0 }}</div>
                  <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px;">总投稿</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-item" style="text-align: center; padding: 16px; background: var(--el-fill-color-light); border-radius: 8px;">
                  <div style="font-size: 24px; font-weight: 600; color: var(--el-color-success);">{{ selectedUser.stats.published || 0 }}</div>
                  <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px;">已发布</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-item" style="text-align: center; padding: 16px; background: var(--el-fill-color-light); border-radius: 8px;">
                  <div style="font-size: 24px; font-weight: 600; color: var(--el-color-danger);">{{ selectedUser.stats.rejected || 0 }}</div>
                  <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px;">被拒绝</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-item" style="text-align: center; padding: 16px; background: var(--el-fill-color-light); border-radius: 8px;">
                  <div style="font-size: 24px; font-weight: 600; color: var(--el-color-warning);">{{ selectedUser.stats.pending || 0 }}</div>
                  <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px;">待审核</div>
                </div>
              </el-col>
            </el-row>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ElImageViewer } from 'element-plus'
import { 
  ArrowLeft, Check, Close, View, ChatDotRound, 
  Refresh, Lightning, ArrowDown, ArrowUp, Delete, Star, PictureFilled
} from '@element-plus/icons-vue'
import moment from 'moment'
import api from '../api'
import SecureImage from '../components/SecureImage.vue'
import SecureAvatar from '../components/SecureAvatar.vue'
import EmoticonText from '../components/EmoticonText.vue'

const route = useRoute()
const loading = ref(false)
const submission = ref(null)
const showCommentDialog = ref(false)
const commentText = ref('')
const rawContentCollapsed = ref(true)
const platformComments = ref([])
const loadingComments = ref(false)
const platformCommentsLoaded = ref(false)
const showImageViewer = ref(false)
const previewImages = ref([])
const previewIndex = ref(0)
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

const loadPlatformComments = async () => {
  if (!submission.value || submission.value.status !== 'published') {
    ElMessage.warning('该投稿尚未发布')
    return
  }
  
  loadingComments.value = true
  try {
    const response = await api.get(`/audit/${submission.value.id}/platform-comments`)
    if (response.data.success && response.data.platforms) {
      platformComments.value = response.data.platforms
      platformCommentsLoaded.value = true
      ElMessage.success('评论加载成功')
    } else {
      ElMessage.warning(response.data.message || '未能获取评论')
      platformComments.value = []
    }
  } catch (error) {
    ElMessage.error('加载评论失败')
    console.error(error)
    platformComments.value = []
  } finally {
    loadingComments.value = false
  }
}

const getPlatformName = (platform) => {
  const nameMap = {
    'bilibili': 'B站',
    'qzone': 'QQ空间',
    'rednote': '小红书'
  }
  return nameMap[platform] || platform
}

const getPlatformTagType = (platform) => {
  const typeMap = {
    'bilibili': 'primary',
    'qzone': 'success',
    'rednote': 'danger'
  }
  return typeMap[platform] || 'info'
}

const formatCommentTime = (timestamp) => {
  if (!timestamp) return '未知时间'
  // 如果是秒级时间戳，转换为毫秒
  if (timestamp < 10000000000) {
    timestamp = timestamp * 1000
  }
  return moment(timestamp).format('YYYY-MM-DD HH:mm:ss')
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
      case 'delete':
        await ElMessageBox.confirm(
          '确定要删除该投稿吗？此操作将删除本地记录和已发布到平台的内容，不可恢复！', 
          '确认删除', 
          {
            type: 'warning',
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            confirmButtonClass: 'el-button--danger'
          }
        )
        result = await api.post(`/audit/${submissionId}/delete`)
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

// 将图片路径规范化为完整 URL（使用 Header 验证，不再添加 token 到 URL）
const getImageUrl = (imagePath) => {
  if (!imagePath) return ''
  const API_BASE = String(api?.defaults?.baseURL || '').replace(/\/+$/, '')
  const toApiUrl = (rel) => {
    const p = rel.startsWith('/') ? rel : `/${rel}`
    return API_BASE ? `${API_BASE}${p}` : p
  }
  
  if (typeof imagePath === 'string') {
    if (imagePath.startsWith('http') || imagePath.startsWith('data:image')) return imagePath
    const normalized = imagePath.replace(/\\/g, '/')
    if (normalized.includes('data/cache/rendered')) {
      return toApiUrl(normalized)
    }
    return toApiUrl(`images/${normalized}`)
  }
  
  const url = imagePath.url || imagePath.src
  const path = imagePath.path || imagePath.local_path
  if (url) {
    if (typeof url === 'string' && url.includes('data/cache/rendered')) {
      return toApiUrl(url.replace(/\\/g, '/'))
    }
    return url
  }
  if (path) {
    const normalized = String(path).replace(/\\/g, '/')
    if (normalized.includes('data/cache/rendered')) {
      return toApiUrl(normalized)
    }
    return toApiUrl(`images/${normalized}`)
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

// 用户详情相关
const showUserDialog = ref(false)
const selectedUser = ref(null)
const loadingUser = ref(false)

const viewUserDetail = async (userId) => {
  showUserDialog.value = true
  selectedUser.value = null
  loadingUser.value = true
  try {
    const response = await api.get(`/management/users/${userId}/detail`, {
      params: { submission_id: submission.value?.id }
    })
    selectedUser.value = {
      user_id: response.data.user_id,
      nickname: response.data.nickname || '未知',
      qq_level: response.data.qq_level || '未知',
      age: response.data.age,
      sex: response.data.sex,
      login_days: response.data.login_days,
      status: response.data.status,
      card: response.data.card,
      area: response.data.area,
      title: response.data.title,
      stats: response.data.stats || { total: 0, published: 0, rejected: 0, pending: 0 }
    }
  } catch (error) {
    console.error('加载用户详情失败:', error)
    ElMessage.error('加载用户详情失败')
  } finally {
    loadingUser.value = false
  }
}

// 打开图片预览
const openImagePreview = (images, index) => {
  previewImages.value = images
  previewIndex.value = index
  showImageViewer.value = true
  
  // 等待预览器渲染后设置 referrerpolicy
  nextTick(() => {
    setTimeout(() => {
      document.querySelectorAll('.el-image-viewer__img').forEach((img) => {
        if (!img.hasAttribute('referrerpolicy')) {
          img.setAttribute('referrerpolicy', 'no-referrer')
        }
      })
    }, 50)
  })
}

// 关闭图片预览
const closeImagePreview = () => {
  showImageViewer.value = false
  previewImages.value = []
  previewIndex.value = 0
}

// 图片加载错误处理
const handleImageError = (e) => {
  console.error('图片加载失败:', e.target.src)
  e.target.style.display = 'none'
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
  flex-wrap: wrap;
}

.submitter-info .submitter-name {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.submitter-info .view-detail-btn {
  margin-left: 4px;
  font-size: 12px;
  height: 24px;
  padding: 0 12px;
  transition: all 0.3s ease;
}

.submitter-info .view-detail-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
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

/* AI总结区域样式 */
.llm-summary-section {
  margin-bottom: 20px;
  padding: 16px;
  background: linear-gradient(135deg, var(--el-color-primary-light-9) 0%, var(--el-fill-color-extra-light) 100%);
  border-radius: 8px;
  border: 1px solid var(--el-color-primary-light-8);
}

.summary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.summary-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-color-primary);
}

.summary-content {
  padding: 12px;
  background: var(--el-bg-color);
  border-radius: 6px;
  border-left: 3px solid var(--el-color-primary);
}

.summary-content p {
  margin: 0;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
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

.empty-hint {
  padding: 20px 0;
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
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
  }

  .action-buttons .el-button {
    flex: 0 1 auto;
    min-width: 80px;
    max-width: 95px;
    height: auto;
    min-height: 60px;
    padding: 8px 4px;
    font-size: 11px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }
  
  .action-buttons .el-button .el-icon {
    font-size: 20px;
    margin: 0;
  }
  
  .action-buttons .el-button > span {
    white-space: nowrap;
    text-align: center;
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
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
  
  .action-buttons {
    gap: 6px;
  }
  
    .action-buttons .el-button {
      flex: 0 1 auto;
      min-width: 72px;
      max-width: 85px;
      min-height: 56px;
    padding: 6px 3px;
    font-size: 10px;
    gap: 3px;
  }
  
  .action-buttons .el-button .el-icon {
    font-size: 18px;
  }
  
  .action-buttons .el-button > span {
    white-space: nowrap;
  }
}

/* 平台评论样式 */
.platform-comments-card {
  margin-bottom: 24px;
}

.platforms-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.platform-section {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 16px;
  background: var(--el-fill-color-extra-light);
}

.platform-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.comment-count {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  font-weight: normal;
}

.comments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.comment-item {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s;
}

.comment-item:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
  border-color: var(--el-border-color-darker);
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.user-id {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.comment-time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.comment-content {
  padding: 8px 12px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  word-wrap: break-word;
}

.comment-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.comment-image-wrapper {
  width: 120px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}

.comment-image-wrapper:hover {
  transform: scale(1.05);
}

.comment-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.image-error {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: var(--el-fill-color-light);
  color: var(--el-text-color-placeholder);
  font-size: 24px;
}

.comment-footer {
  display: flex;
  gap: 16px;
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.comment-stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.comment-stat .el-icon {
  font-size: 14px;
}

.empty-comments {
  padding: 40px 20px;
}
</style>
