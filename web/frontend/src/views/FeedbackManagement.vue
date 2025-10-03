<template>
  <div class="feedback-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="page-title">
          <h1>反馈管理</h1>
          <div class="title-stats">
            <el-tag type="danger" size="large">待处理 {{ pendingCount }} 条</el-tag>
            <el-tag type="info" size="large">已读 {{ readCount }} 条</el-tag>
            <el-tag type="success" size="large">已解决 {{ resolvedCount }} 条</el-tag>
          </div>
        </div>
        
        <div class="header-actions">
          <el-button 
            type="primary" 
            :icon="Refresh"
            @click="loadFeedbacks"
            :loading="loading"
            round
          >
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <!-- 主卡片 -->
    <el-card class="main-card" shadow="hover">
      <div class="tab-content">
        <div class="tab-header">
          <div class="tab-title">
            <h3>反馈列表</h3>
            <el-tag type="info">{{ filteredFeedbacks.length }} 条记录</el-tag>
          </div>
          <div class="tab-actions">
            <el-select 
              v-model="filters.status" 
              placeholder="状态筛选" 
              clearable 
              @change="handleStatusFilter"
              style="width: 150px; margin-right: 12px;"
            >
              <el-option label="待处理" value="pending" />
              <el-option label="已读" value="read" />
              <el-option label="已解决" value="resolved" />
            </el-select>
            <el-input
              v-model="searchText"
              placeholder="搜索用户ID或内容"
              :prefix-icon="Search"
              style="width: 200px;"
              @input="handleSearch"
              clearable
            />
          </div>
        </div>

        <!-- 表格容器 -->
        <div class="table-container">
          <el-table 
            :data="paginatedFeedbacks" 
            v-loading="loading" 
            class="feedback-table"
            stripe
            :header-cell-style="headerCellStyle"
          >
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="用户" width="180">
              <template #default="{ row }">
                <div class="user-cell">
                  <el-avatar :size="32" style="background-color: #6366f1;">
                    {{ row.user_id[0] }}
                  </el-avatar>
                  <div class="user-info">
                    <span class="user-id">{{ row.user_id }}</span>
                    <el-tag size="small" type="info">{{ row.group_name || '未知' }}</el-tag>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="反馈内容" min-width="300">
              <template #default="{ row }">
                <div class="content-preview">{{ row.content }}</div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="getStatusType(row.status)"
                  size="small"
                >
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button
                    type="primary"
                    size="small"
                    :icon="View"
                    @click="viewFeedback(row)"
                  >
                    查看
                  </el-button>
                  <el-button
                    v-if="row.status !== 'resolved'"
                    type="success"
                    size="small"
                    :icon="ChatDotSquare"
                    @click="openReplyDialog(row)"
                  >
                    回复
                  </el-button>
                  <el-button
                    type="danger"
                    size="small"
                    :icon="Delete"
                    @click="confirmDelete(row.id)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 分页 -->
        <div class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="filteredFeedbacks.length"
            layout="prev, pager, next"
            @current-change="handlePageChange"
            background
          />
          <div class="pagination-info">
            共 {{ filteredFeedbacks.length }} 条记录，当前第 {{ currentPage }} 页
          </div>
        </div>
      </div>
    </el-card>

    <!-- 反馈详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="反馈详情"
      width="600px"
    >
      <div v-if="currentFeedback" class="feedback-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="反馈 ID">
            {{ currentFeedback.id }}
          </el-descriptions-item>
          <el-descriptions-item label="用户 ID">
            {{ currentFeedback.user_id }}
          </el-descriptions-item>
          <el-descriptions-item label="账号组">
            {{ currentFeedback.group_name || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentFeedback.status)">
              {{ getStatusText(currentFeedback.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">
            {{ formatTime(currentFeedback.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="反馈内容">
            <div class="content-text">{{ currentFeedback.content }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentFeedback.admin_reply" label="管理员回复">
            <div class="reply-text">{{ currentFeedback.admin_reply }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="currentFeedback.replied_by" label="回复者">
            {{ currentFeedback.replied_by }}
          </el-descriptions-item>
          <el-descriptions-item v-if="currentFeedback.replied_at" label="回复时间">
            {{ formatTime(currentFeedback.replied_at) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button
          v-if="currentFeedback && currentFeedback.status !== 'resolved'"
          type="primary"
          @click="openReplyDialog(currentFeedback)"
        >
          回复
        </el-button>
      </template>
    </el-dialog>

    <!-- 回复对话框 -->
    <el-dialog
      v-model="replyDialogVisible"
      title="回复反馈"
      width="600px"
    >
      <el-form :model="replyForm" label-width="80px">
        <el-form-item label="反馈内容">
          <div class="content-text">{{ replyForm.originalContent }}</div>
        </el-form-item>
        <el-form-item label="回复内容" required>
          <el-input
            v-model="replyForm.reply"
            type="textarea"
            :rows="6"
            placeholder="请输入回复内容，将通过 QQ 私聊发送给用户"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="replyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReply" :loading="replying">
          发送回复
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, Search, View, Delete, ChatDotSquare 
} from '@element-plus/icons-vue'
import api from '../api'
import { formatDateTime } from '../utils/format'
import moment from 'moment'

const feedbacks = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const searchText = ref('')

const filters = ref({
  status: '',
  userId: '',
  groupName: ''
})

const detailDialogVisible = ref(false)
const currentFeedback = ref(null)

const replyDialogVisible = ref(false)
const replying = ref(false)
const replyForm = ref({
  feedbackId: null,
  originalContent: '',
  reply: ''
})

// 计算属性
const headerCellStyle = computed(() => ({
  background: 'var(--el-bg-color-page)',
  color: 'var(--el-text-color-primary)',
  fontWeight: '600'
}))

const filteredFeedbacks = computed(() => {
  let result = feedbacks.value

  // 状态筛选
  if (filters.value.status) {
    result = result.filter(item => item.status === filters.value.status)
  }

  // 搜索筛选
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    result = result.filter(item =>
      item.user_id.toLowerCase().includes(search) ||
      item.content.toLowerCase().includes(search)
    )
  }

  return result
})

const paginatedFeedbacks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredFeedbacks.value.slice(start, end)
})

const pendingCount = computed(() => feedbacks.value.filter(f => f.status === 'pending').length)
const readCount = computed(() => feedbacks.value.filter(f => f.status === 'read').length)
const resolvedCount = computed(() => feedbacks.value.filter(f => f.status === 'resolved').length)

const loadFeedbacks = async () => {
  loading.value = true
  try {
    const params = {
      page: 1,
      page_size: 1000 // 一次加载所有数据，客户端分页
    }

    const { data } = await api.get('/management/feedbacks', { params })
    feedbacks.value = data
  } catch (error) {
    console.error('加载反馈列表失败:', error)
    ElMessage.error('加载反馈列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
}

const handleStatusFilter = () => {
  currentPage.value = 1
}

const handlePageChange = (page) => {
  currentPage.value = page
}

const confirmDelete = async (id) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除该反馈吗？此操作不可撤销。',
      '确认删除',
      {
        type: 'error',
        confirmButtonText: '确定',
        cancelButtonText: '取消'
      }
    )
    await deleteFeedback(id)
  } catch (error) {
    // 用户取消
  }
}

const viewFeedback = async (feedback) => {
  try {
    const { data } = await api.get(`/management/feedbacks/${feedback.id}`)
    currentFeedback.value = data
    detailDialogVisible.value = true
    // 刷新列表以更新状态
    await loadFeedbacks()
  } catch (error) {
    console.error('获取反馈详情失败:', error)
    ElMessage.error('获取反馈详情失败')
  }
}

const openReplyDialog = (feedback) => {
  replyForm.value = {
    feedbackId: feedback.id,
    originalContent: feedback.content,
    reply: ''
  }
  detailDialogVisible.value = false
  replyDialogVisible.value = true
}

const submitReply = async () => {
  if (!replyForm.value.reply.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }

  replying.value = true
  try {
    await api.post(`/management/feedbacks/${replyForm.value.feedbackId}/reply`, {
      reply: replyForm.value.reply
    })
    ElMessage.success('回复成功，已通过 QQ 私聊发送给用户')
    replyDialogVisible.value = false
    await loadFeedbacks()
  } catch (error) {
    console.error('回复反馈失败:', error)
    ElMessage.error('回复反馈失败')
  } finally {
    replying.value = false
  }
}

const deleteFeedback = async (id) => {
  try {
    await api.delete(`/management/feedbacks/${id}`)
    ElMessage.success('删除成功')
    await loadFeedbacks()
  } catch (error) {
    console.error('删除反馈失败:', error)
    ElMessage.error('删除反馈失败')
  }
}

const getStatusType = (status) => {
  const types = {
    pending: 'warning',
    read: 'info',
    resolved: 'success'
  }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = {
    pending: '待处理',
    read: '已读',
    resolved: '已解决'
  }
  return texts[status] || status
}

const formatTime = (time) => {
  return time ? moment(time).format('YYYY-MM-DD HH:mm') : '-'
}

onMounted(() => {
  loadFeedbacks()
})
</script>

<style scoped>
.feedback-management {
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--xw-space-5);
  background: var(--xw-bg-secondary);
  min-height: 100vh;
}

/* 页面头部样式 */
.page-header {
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-light));
  border-radius: var(--xw-radius-xl);
  padding: var(--xw-space-6) var(--xw-space-8);
  margin-bottom: var(--xw-space-6);
  color: white;
  box-shadow: var(--xw-shadow-lg);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--xw-space-4);
}

.page-title h1 {
  margin: 0;
  font-size: var(--xw-text-3xl);
  font-weight: 700;
  color: white;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.title-stats {
  display: flex;
  gap: var(--xw-space-3);
  margin-top: var(--xw-space-2);
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--xw-space-3);
}

/* 主卡片样式 */
.main-card {
  background: var(--xw-card-bg);
  border-radius: var(--xw-radius-xl);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border: none;
  overflow: hidden;
}

.main-card :deep(.el-card__body) {
  padding: var(--xw-space-6);
}

/* Tab内容样式 */
.tab-content {
  background: var(--xw-bg-primary);
  padding: var(--xw-space-2);
  border-radius: var(--xw-radius-lg);
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: var(--xw-space-4) var(--xw-space-4) var(--xw-space-6);
  padding-bottom: var(--xw-space-4);
  border-bottom: none;
  position: relative;
}

.tab-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--xw-primary-lightest), var(--xw-primary-lighter), var(--xw-primary-lightest));
  border-radius: var(--xw-radius-sm);
}

.tab-title {
  display: flex;
  align-items: center;
  gap: var(--xw-space-4);
}

.tab-title h3 {
  margin: 0;
  color: var(--xw-text-primary);
  font-size: var(--xw-text-xl);
  font-weight: 600;
}

.tab-actions {
  display: flex;
  align-items: center;
  gap: var(--xw-space-3);
  flex-wrap: wrap;
}

/* 表格容器样式 */
.table-container {
  overflow-x: auto;
  margin: 0 var(--xw-space-4);
  border-radius: var(--xw-radius-lg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

/* 表格样式 */
.feedback-table {
  background: var(--xw-bg-primary);
  border-radius: var(--xw-radius-lg);
  overflow: hidden;
  border: none;
  margin: 0;
  box-shadow: none;
  min-width: 1200px;
}

.feedback-table :deep(.el-table__header) {
  background: linear-gradient(135deg, var(--xw-bg-tertiary), var(--xw-bg-secondary));
}

.feedback-table :deep(.el-table__header th) {
  font-weight: 600;
  color: var(--xw-text-primary);
  border: none;
  position: relative;
}

.feedback-table :deep(.el-table__header th):not(:last-child)::after {
  content: '';
  position: absolute;
  right: 0;
  top: 25%;
  bottom: 25%;
  width: 1px;
  background: var(--xw-border-quaternary);
}

.feedback-table :deep(.el-table__row):hover {
  background: var(--xw-bg-secondary);
}

.feedback-table :deep(.el-table__row.el-table__row--striped) {
  background: var(--xw-bg-secondary);
}

.feedback-table :deep(.el-table__row.el-table__row--striped):hover {
  background: var(--xw-bg-tertiary);
}

/* 用户单元格样式 */
.user-cell {
  display: flex;
  align-items: center;
  gap: var(--xw-space-3);
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.user-id {
  font-weight: 500;
  color: var(--xw-text-primary);
  font-size: var(--xw-text-sm);
}

.content-preview {
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  word-break: break-all;
  line-height: 1.5;
}

.content-text,
.reply-text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  padding: var(--xw-space-3);
  background-color: var(--xw-bg-secondary);
  border-radius: var(--xw-radius);
  border: 1px solid var(--xw-border-tertiary);
}

/* 操作按钮样式 */
.action-buttons {
  display: flex;
  gap: var(--xw-space-2);
  flex-wrap: wrap;
}

.action-buttons .el-button {
  font-size: var(--xw-text-xs);
  padding: var(--xw-space-2) var(--xw-space-3);
  border-radius: var(--xw-radius);
  border: none;
  transition: var(--xw-transition);
  box-shadow: none;
}

.action-buttons .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

/* 分页器样式 */
.pagination-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--xw-space-3);
  margin: var(--xw-space-8) var(--xw-space-4) var(--xw-space-4);
  padding-top: var(--xw-space-6);
  border-top: 1px solid var(--xw-border-tertiary);
}

.pagination-info {
  color: var(--xw-text-secondary);
  font-size: var(--xw-text-sm);
  text-align: center;
}

/* 反馈详情样式 */
.feedback-detail {
  max-height: 600px;
  overflow-y: auto;
  padding: var(--xw-space-4) 0;
}

/* 统一按钮样式 */
:deep(.el-button) {
  border-radius: var(--xw-radius-lg);
  border: none;
  font-weight: 500;
  transition: var(--xw-transition);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-dark));
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, var(--xw-primary-light), var(--xw-primary));
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.el-button--success) {
  background: linear-gradient(135deg, #67c23a, #5daf34);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, #f56c6c, #e85656);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 对话框样式优化 */
:deep(.el-dialog) {
  background: var(--xw-bg-primary);
  border-radius: var(--xw-radius-xl);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.12);
  border: none;
}

:deep(.el-dialog__header) {
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-light));
  color: white;
  padding: var(--xw-space-5) var(--xw-space-6);
  border-radius: var(--xw-radius-xl) var(--xw-radius-xl) 0 0;
}

:deep(.el-dialog__title) {
  color: white;
  font-weight: 600;
  font-size: var(--xw-text-lg);
}

:deep(.el-dialog__body) {
  padding: var(--xw-space-6);
  background: var(--xw-bg-primary);
}

:deep(.el-dialog__footer) {
  padding: var(--xw-space-4) var(--xw-space-6) var(--xw-space-6);
  background: var(--xw-bg-secondary);
  border-radius: 0 0 var(--xw-radius-xl) var(--xw-radius-xl);
}

/* 表单样式优化 */
:deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--xw-text-primary);
  font-size: var(--xw-text-sm);
}

:deep(.el-input__wrapper) {
  background: var(--xw-bg-primary);
  border: 1px solid var(--xw-border-tertiary);
  border-radius: var(--xw-radius-lg);
  box-shadow: none;
  transition: var(--xw-transition);
}

:deep(.el-input__wrapper:hover) {
  border-color: var(--xw-primary-lighter);
  background: var(--xw-bg-secondary);
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--xw-primary);
  background: var(--xw-bg-primary);
  box-shadow: 0 0 0 2px var(--xw-primary-lightest);
}

:deep(.el-select .el-input__wrapper) {
  border-radius: var(--xw-radius-lg);
}

:deep(.el-textarea__inner) {
  background: var(--xw-bg-primary);
  border: 1px solid var(--xw-border-tertiary);
  border-radius: var(--xw-radius-lg);
  box-shadow: none;
  transition: var(--xw-transition);
}

:deep(.el-textarea__inner:hover) {
  border-color: var(--xw-primary-lighter);
  background: var(--xw-bg-secondary);
}

:deep(.el-textarea__inner:focus) {
  border-color: var(--xw-primary);
  background: var(--xw-bg-primary);
  box-shadow: 0 0 0 2px var(--xw-primary-lightest);
}

/* 标签样式优化 */
:deep(.el-tag) {
  border: none;
  border-radius: var(--xw-radius);
  font-weight: 500;
}

/* 深色模式优化 */
html.dark .page-header {
  background: linear-gradient(135deg, var(--xw-primary-dark), var(--xw-primary));
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

html.dark .main-card {
  background: var(--xw-card-bg);
  border: none;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
}

html.dark .feedback-table {
  background: var(--xw-bg-secondary);
  border: none;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

html.dark :deep(.el-dialog) {
  background: var(--xw-bg-secondary);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
}

html.dark :deep(.el-dialog__body) {
  background: var(--xw-bg-secondary);
}

html.dark :deep(.el-dialog__footer) {
  background: var(--xw-bg-tertiary);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .feedback-management {
    padding: var(--xw-space-4);
  }
  
  .page-header {
    padding: var(--xw-space-5) var(--xw-space-6);
  }
  
  .page-title h1 {
    font-size: var(--xw-text-2xl);
  }
}

@media (max-width: 768px) {
  .feedback-management {
    padding: var(--xw-space-3);
  }
  
  .page-header {
    padding: var(--xw-space-4) var(--xw-space-5);
    margin-bottom: var(--xw-space-4);
    border-radius: var(--xw-radius-lg);
  }
  
  .header-content {
    flex-direction: column;
    gap: var(--xw-space-4);
    align-items: stretch;
  }
  
  .page-title h1 {
    font-size: var(--xw-text-2xl);
  }
  
  .title-stats {
    justify-content: center;
  }
  
  .header-actions {
    justify-content: center;
  }
  
  .main-card {
    border-radius: var(--xw-radius-lg);
  }
  
  .tab-header {
    flex-direction: column;
    gap: var(--xw-space-4);
    align-items: stretch;
    margin-bottom: var(--xw-space-4);
  }
  
  .tab-title h3 {
    font-size: var(--xw-text-lg);
  }
  
  .tab-actions {
    justify-content: center;
  }
  
  .table-container {
    margin: 0 var(--xw-space-2);
    border-radius: var(--xw-radius);
  }

  .feedback-table {
    font-size: var(--xw-text-sm);
    border-radius: var(--xw-radius);
    min-width: 800px;
  }
  
  .feedback-table :deep(.el-table__cell) {
    padding: var(--xw-space-2) var(--xw-space-1);
  }
  
  .user-cell {
    gap: var(--xw-space-2);
  }
  
  .user-cell .el-avatar {
    width: 24px;
    height: 24px;
    font-size: var(--xw-text-xs);
  }
  
  .user-id {
    font-size: var(--xw-text-xs);
  }
  
  .action-buttons {
    flex-direction: column;
    gap: var(--xw-space-1);
  }
  
  .action-buttons .el-button {
    font-size: 11px;
    padding: var(--xw-space-1) var(--xw-space-2);
    width: 100%;
  }
  
  :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
    border-radius: var(--xw-radius-lg);
  }
  
  .pagination-container {
    margin-top: var(--xw-space-6);
    padding-top: var(--xw-space-4);
  }
  
  .pagination-info {
    font-size: var(--xw-text-xs);
  }
}

@media (max-width: 480px) {
  .feedback-management {
    padding: var(--xw-space-2);
  }
  
  .page-header {
    padding: var(--xw-space-3) var(--xw-space-4);
    border-radius: var(--xw-radius);
  }
  
  .page-title h1 {
    font-size: var(--xw-text-xl);
  }
  
  .title-stats {
    gap: var(--xw-space-2);
  }
  
  .title-stats .el-tag {
    font-size: var(--xw-text-xs);
  }
  
  .feedback-table {
    font-size: var(--xw-text-xs);
    min-width: 600px;
  }
  
  .feedback-table :deep(.el-table__cell) {
    padding: var(--xw-space-1) 2px;
    font-size: var(--xw-text-xs);
  }
  
  .action-buttons .el-button {
    font-size: 10px;
    padding: 3px var(--xw-space-2);
  }
}
</style>

