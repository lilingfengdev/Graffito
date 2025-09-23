<template>
  <div class="audit-page">
    <!-- 顶部操作栏 -->
    <el-card class="header-card" shadow="hover">
      <div class="header-content">
        <div class="page-title">
          <h2>审核管理</h2>
          <el-tag :type="getStatusTagType(statusFilter)">
            {{ getStatusText(statusFilter) || '全部状态' }}
          </el-tag>
        </div>
        
        <div class="header-actions">
          <el-select 
            v-model="statusFilter" 
            placeholder="选择状态" 
            @change="handleFilterChange"
            style="width: 150px"
          >
            <el-option label="全部状态" value="" />
            <el-option label="等待审核" value="waiting" />
            <el-option label="已通过" value="approved" />
            <el-option label="已发布" value="published" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
          
          <el-button 
            type="primary" 
            :icon="Refresh" 
            @click="loadSubmissions"
            :loading="loading"
          >
            刷新
          </el-button>
          
        </div>
      </div>
    </el-card>

    <!-- 投稿列表 -->
    <el-card class="submissions-card" shadow="hover">
      <el-table 
        :data="submissions" 
        v-loading="loading"
        :header-cell-style="{ background: 'transparent' }"
        @row-click="handleRowClick"
        style="cursor: pointer"
      >
        <el-table-column prop="id" label="ID" width="80" />
        
        <el-table-column label="投稿者" width="150">
          <template #default="{ row }">
            <div class="submitter-info">
              <el-avatar :size="32" style="background-color: #6366f1;">
                {{ (row.sender_nickname || row.sender_id)[0] }}
              </el-avatar>
              <div class="submitter-text">
                <div class="nickname">{{ row.sender_nickname || row.sender_id }}</div>
                <div class="user-id">{{ row.sender_id }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="group_name" label="群组" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.group_name }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag 
              :type="getSubmissionStatusType(row.status)" 
              size="small"
            >
              {{ getSubmissionStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="属性" width="120">
          <template #default="{ row }">
            <div class="attributes">
              <el-tag v-if="row.is_anonymous" size="mini" type="warning">匿名</el-tag>
              <el-tag v-if="!row.is_safe" size="mini" type="danger">不安全</el-tag>
              <el-tag v-if="!row.is_complete" size="mini" type="info">不完整</el-tag>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons" @click.stop>
              <!-- 基础审核操作 -->
              <el-button 
                type="success" 
                size="small"
                :icon="Check"
                @click="handleAction(row.id, 'approve')"
                v-if="['waiting', 'pending'].includes(row.status)"
              >
                通过
              </el-button>
              
              <el-dropdown @command="(cmd) => handleAction(row.id, cmd)" v-if="['waiting', 'pending'].includes(row.status)">
                <el-button type="danger" size="small" :icon="Close">
                  拒绝 <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="reject">普通拒绝</el-dropdown-item>
                    <el-dropdown-item command="reject-with-reason">拒绝并说明</el-dropdown-item>
                    <el-dropdown-item command="blacklist" divided>拒绝并拉黑</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              
              <!-- 更多操作 -->
              <el-dropdown @command="(cmd) => handleAction(row.id, cmd)">
                <el-button size="small" :icon="More">
                  更多 <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="toggle-anon">
                      <el-icon><View /></el-icon>
                      {{ row.is_anonymous ? '取消匿名' : '设为匿名' }}
                    </el-dropdown-item>
                    <el-dropdown-item command="hold">
                      <el-icon><Clock /></el-icon>
                      暂缓处理
                    </el-dropdown-item>
                    <el-dropdown-item command="comment">
                      <el-icon><ChatDotRound /></el-icon>
                      添加评论
                    </el-dropdown-item>
                    <el-dropdown-item command="reply">
                      <el-icon><Message /></el-icon>
                      回复投稿者
                    </el-dropdown-item>
                    <el-dropdown-item command="rerender" divided>
                      <el-icon><Refresh /></el-icon>
                      重新渲染
                    </el-dropdown-item>
                    <el-dropdown-item command="refresh">
                      <el-icon><RefreshRight /></el-icon>
                      重新处理
                    </el-dropdown-item>
                    <el-dropdown-item command="approve-immediate" v-if="row.status === 'approved'">
                      <el-icon><Lightning /></el-icon>
                      立即发布
                    </el-dropdown-item>
                    <el-dropdown-item command="delete" divided style="color: #f56c6c">
                      <el-icon><Delete /></el-icon>
                      删除投稿
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              
              <el-button 
                type="primary" 
                size="small" 
                :icon="View"
                @click="$router.push(`/submission/${row.id}`)"
              >
                详情
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next, jumper"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>


    <!-- 评论/回复对话框 -->
    <el-dialog v-model="showCommentDialog" :title="commentDialogTitle" width="500px">
      <el-form>
        <el-form-item label="内容">
          <el-input 
            v-model="commentText" 
            type="textarea" 
            :rows="4" 
            placeholder="请输入内容..."
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, Check, Close, More, View, Clock, 
  ChatDotRound, Message, RefreshRight, Lightning, Delete
} from '@element-plus/icons-vue'
import moment from 'moment'
import api from '../api'

const loading = ref(false)
const statusFilter = ref('waiting')
const submissions = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const me = ref(null)

// 对话框相关
const showCommentDialog = ref(false)
const commentDialogTitle = ref('')
const commentText = ref('')
const currentSubmissionId = ref(null)
const currentAction = ref('')

const isSuperadmin = computed(() => me.value?.is_superadmin)

// 方法
const loadSubmissions = async () => {
  loading.value = true
  try {
    const params = { limit: pageSize.value }
    if (statusFilter.value) {
      params.status_filter = statusFilter.value
    }
    
    const { data } = await api.get('/audit/submissions', { params })
    submissions.value = data
    total.value = data.length // 简化版本，实际可能需要后端支持总数查询
  } catch (error) {
    ElMessage.error('加载投稿列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  currentPage.value = 1
  loadSubmissions()
}

const handlePageChange = (page) => {
  currentPage.value = page
  loadSubmissions()
}

const handleRowClick = (row) => {
  // 点击行跳转到详情页
  // $router.push(`/submission/${row.id}`)
}

const handleAction = async (submissionId, action) => {
  currentSubmissionId.value = submissionId
  currentAction.value = action
  
  switch (action) {
    case 'approve':
      await performAction(`/audit/${submissionId}/approve`, 'POST')
      break
    case 'reject':
      await performAction(`/audit/${submissionId}/reject`, 'POST', { comment: '不符合规范' })
      break
    case 'reject-with-reason':
      showCommentDialog.value = true
      commentDialogTitle.value = '拒绝原因'
      commentText.value = ''
      break
    case 'blacklist':
      try {
        await ElMessageBox.confirm('确定要拒绝并拉黑该用户吗？', '确认操作', {
          type: 'warning'
        })
        await performAction(`/audit/${submissionId}/blacklist`, 'POST', { comment: '违规内容' })
      } catch {}
      break
    case 'toggle-anon':
      await performAction(`/audit/${submissionId}/toggle-anon`, 'POST')
      break
    case 'hold':
      await performAction(`/audit/${submissionId}/hold`, 'POST')
      break
    case 'comment':
      showCommentDialog.value = true
      commentDialogTitle.value = '添加评论'
      commentText.value = ''
      break
    case 'reply':
      showCommentDialog.value = true
      commentDialogTitle.value = '回复投稿者'
      commentText.value = ''
      break
    case 'rerender':
      await performAction(`/audit/${submissionId}/rerender`, 'POST')
      break
    case 'refresh':
      await performAction(`/audit/${submissionId}/refresh`, 'POST')
      break
    case 'approve-immediate':
      await performAction(`/audit/${submissionId}/approve-immediate`, 'POST')
      break
    case 'delete':
      try {
        await ElMessageBox.confirm('确定要删除该投稿吗？此操作不可恢复！', '确认删除', {
          type: 'warning'
        })
        await performAction(`/audit/${submissionId}/delete`, 'POST')
      } catch {}
      break
  }
}

const performAction = async (url, method, data = {}) => {
  try {
    const result = await api[method.toLowerCase()](url, data)
    ElMessage.success(result.data.message || '操作成功')
    await loadSubmissions()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const submitComment = async () => {
  if (!commentText.value.trim()) {
    ElMessage.warning('请输入内容')
    return
  }
  
  const actionMap = {
    'reject-with-reason': `/audit/${currentSubmissionId.value}/reject`,
    'comment': `/audit/${currentSubmissionId.value}/comment`,
    'reply': `/audit/${currentSubmissionId.value}/reply`
  }
  
  const url = actionMap[currentAction.value]
  if (url) {
    await performAction(url, 'POST', { comment: commentText.value })
  }
  
  showCommentDialog.value = false
  commentText.value = ''
}

const fetchMe = async () => {
  try {
    const { data } = await api.get('/auth/me')
    me.value = data
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

// 工具函数
const getStatusTagType = (status) => {
  const typeMap = {
    'waiting': 'warning',
    'approved': 'success',
    'published': 'primary',
    'rejected': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'waiting': '等待审核',
    'approved': '已通过',
    'published': '已发布',
    'rejected': '已拒绝'
  }
  return textMap[status]
}

const getSubmissionStatusType = (status) => {
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

const getSubmissionStatusText = (status) => {
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

const formatTime = (timeStr) => {
  return moment(timeStr).format('YYYY-MM-DD HH:mm')
}

onMounted(async () => {
  await fetchMe()
  await loadSubmissions()
})
</script>

<style scoped>
.audit-page {
  max-width: 1400px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title h2 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 24px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.submissions-card {
  margin-bottom: 20px;
}

.submitter-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.submitter-text {
  flex: 1;
}

.nickname {
  font-weight: 500;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.user-id {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.attributes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .audit-page {
    padding: 0;
  }
  
  .page-header {
    margin-bottom: 16px;
  }
  
  .header-content {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .page-title h2 {
    font-size: 20px;
  }
  
  .header-actions {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px;
    align-items: center;
  }
  
  /* 表格移动端适配 */
  :deep(.el-table) {
    font-size: 13px;
  }
  
  :deep(.el-table .el-table__cell) {
    padding: 8px 4px;
  }
  
  :deep(.el-table .submitter-info) {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  :deep(.el-table .nickname) {
    font-size: 13px;
  }
  
  :deep(.el-table .user-id) {
    font-size: 11px;
  }
  
  :deep(.el-table .attributes) {
    gap: 2px;
  }
  
  :deep(.el-table .attributes .el-tag) {
    font-size: 10px;
    padding: 2px 4px;
    height: auto;
    line-height: 1.2;
  }
  
  .action-buttons {
    flex-direction: column;
    gap: 4px;
  }
  
  .action-buttons .el-button {
    font-size: 12px;
    padding: 6px 12px;
  }
  
  .action-buttons .el-dropdown {
    width: 100%;
  }
  
  .action-buttons .el-dropdown .el-button {
    width: 100%;
  }
  
  /* 分页器移动端适配 */
  :deep(.el-pagination) {
    justify-content: center;
  }
  
  :deep(.el-pagination .el-pagination__total),
  :deep(.el-pagination .el-pagination__jump) {
    display: none;
  }
  
  :deep(.el-pagination .el-pager) {
    display: flex;
    gap: 4px;
  }
  
  :deep(.el-pagination .el-pager .number) {
    min-width: 28px;
    height: 28px;
    line-height: 26px;
    font-size: 13px;
  }
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .page-title h2 {
    font-size: 18px;
  }
  
  .header-actions {
    grid-template-columns: 1fr;
    gap: 8px;
  }
  
  /* 表格内容更紧凑 */
  :deep(.el-table .el-table__cell) {
    padding: 6px 2px;
  }
  
  :deep(.el-table) {
    font-size: 12px;
  }
  
  .submitter-info {
    gap: 8px;
  }
  
  .action-buttons .el-button {
    font-size: 11px;
    padding: 4px 8px;
  }
  
  /* 隐藏不重要的列 */
  :deep(.el-table .status-col) {
    display: none;
  }
  
  /* 分页器更紧凑 */
  :deep(.el-pagination .el-pager .number) {
    min-width: 24px;
    height: 24px;
    line-height: 22px;
    font-size: 12px;
  }
  
  :deep(.el-pagination .btn-prev),
  :deep(.el-pagination .btn-next) {
    width: 24px;
    height: 24px;
    font-size: 12px;
  }
}
</style>

