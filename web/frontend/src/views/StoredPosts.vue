<template>
  <div class="stored-posts">
    <!-- 页面头部 -->
    <el-card class="header-card" shadow="hover">
      <div class="header-content">
        <div class="page-title">
          <h2>暂存区管理</h2>
          <el-tag type="primary">{{ storedPosts.length }} 条待发布</el-tag>
        </div>
        
        <div class="header-actions">
          <el-select 
            v-model="selectedGroup" 
            placeholder="选择群组"
            @change="handleGroupChange"
            style="width: 150px"
          >
            <el-option label="全部群组" value="" />
            <el-option 
              v-for="group in activeGroups" 
              :key="group"
              :label="group" 
              :value="group"
            />
          </el-select>
          
          <el-button 
            type="success" 
            :icon="Position"
            @click="publishAll"
            :disabled="!selectedGroup || storedPosts.length === 0"
            :loading="publishing"
          >
            发布
          </el-button>
          
          <el-button 
            type="danger" 
            :icon="Delete"
            @click="clearAll"
            :disabled="!selectedGroup || storedPosts.length === 0"
          >
            清空
          </el-button>
          
          <el-button 
            type="default" 
            :icon="Refresh"
            @click="loadStoredPosts"
            :loading="loading"
          >
            刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 统计信息 -->
    <el-row :gutter="20" class="stats-row" v-if="selectedGroup">
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" style="color: #6366f1;">
              <el-icon :size="24"><Box /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ storedPosts.length }}</div>
              <div class="stat-label">待发布投稿</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" style="color: #10b981;">
              <el-icon :size="24"><User /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ uniqueUsers }}</div>
              <div class="stat-label">投稿用户</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" style="color: #f59e0b;">
              <el-icon :size="24"><Clock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ earliestPost }}</div>
              <div class="stat-label">最早投稿</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" style="color: #8b5cf6;">
              <el-icon :size="24"><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ nextPublishId }}</div>
              <div class="stat-label">下个编号</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 暂存投稿列表 -->
    <el-card class="posts-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">暂存投稿列表</span>
          <div class="sort-controls">
            <el-text type="info">排序：</el-text>
            <el-radio-group v-model="sortBy" size="small" @change="handleSortChange">
              <el-radio-button label="priority">优先级</el-radio-button>
              <el-radio-button label="time">时间</el-radio-button>
              <el-radio-button label="publish_id">编号</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </template>
      
      <el-table 
        :data="sortedStoredPosts" 
        v-loading="loading"
        :header-cell-style="{ background: 'transparent' }"
        :row-class-name="getRowClassName"
      >
        <el-table-column prop="publish_id" label="发布编号" width="100">
          <template #default="{ row }">
            <el-tag type="primary">#{{ row.publish_id }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="投稿信息" min-width="200">
          <template #default="{ row }">
            <div v-if="row.submission" class="submission-info">
              <div class="submitter">
                <el-avatar :size="24" style="background-color: #6366f1;">
                  {{ (row.submission.sender_nickname || row.submission.sender_id)[0] }}
                </el-avatar>
                <span class="submitter-name">
                  {{ row.submission.sender_nickname || row.submission.sender_id }}
                </span>
              </div>
              <div class="submission-meta">
                <el-tag size="mini" type="info">ID: {{ row.submission.id }}</el-tag>
                <el-tag 
                  v-if="row.submission.is_anonymous" 
                  size="mini" 
                  type="warning"
                >
                  匿名
                </el-tag>
                <el-tag 
                  v-if="row.submission.processed_by" 
                  size="mini" 
                  type="success"
                >
                  处理人: {{ row.submission.processed_by }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag 
              :type="getPriorityType(row.priority)" 
              size="small"
            >
              {{ getPriorityText(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="加入时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="300" :fixed="isMobile ? false : 'right'" class-name="action-column">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button 
                type="primary" 
                size="small"
                :icon="View"
                @click="$router.push(`/submission/${row.submission_id}`)"
              >
                查看详情
              </el-button>
              
              <el-dropdown @command="(cmd) => handleAction(row, cmd)">
                <el-button size="small" :icon="More">
                  操作 <el-icon class="el-icon--right"><arrow-down /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="set-priority">
                      <el-icon><Sort /></el-icon>
                      设置优先级
                    </el-dropdown-item>
                    <el-dropdown-item command="publish-single">
                      <el-icon><Position /></el-icon>
                      单独发布
                    </el-dropdown-item>
                    <el-dropdown-item command="remove" divided style="color: #f56c6c">
                      <el-icon><Delete /></el-icon>
                      移出暂存区
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div v-if="storedPosts.length === 0" class="empty-state">
        <el-empty description="暂存区为空">
          <el-button type="primary" @click="$router.push('/audit')">
            去审核投稿
          </el-button>
        </el-empty>
      </div>
    </el-card>

    <!-- 设置优先级对话框 -->
    <el-dialog v-model="showPriorityDialog" title="设置优先级" width="400px">
      <el-form>
        <el-form-item label="优先级">
          <el-slider
            v-model="priorityValue"
            :min="0"
            :max="10"
            :marks="priorityMarks"
            show-tooltip
          />
        </el-form-item>
        <el-form-item>
          <el-text type="info">
            优先级越高，发布时越靠前
          </el-text>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPriorityDialog = false">取消</el-button>
        <el-button type="primary" @click="updatePriority">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Position, Delete, Refresh, Box, User, Clock, TrendCharts,
  View, More, Sort
} from '@element-plus/icons-vue'
import moment from 'moment'
import 'moment/dist/locale/zh-cn'
import api from '../api'

// 设置 moment 为中文
moment.locale('zh-cn')

const loading = ref(false)
const publishing = ref(false)
const storedPosts = ref([])
const activeGroups = ref([])
const selectedGroup = ref('')
const sortBy = ref('priority')
const isMobile = ref(false)

// 检测移动端
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

const handleResize = () => {
  checkMobile()
}

// 对话框相关
const showPriorityDialog = ref(false)
const priorityValue = ref(0)
const currentPost = ref(null)

const priorityMarks = {
  0: '低',
  5: '中',
  10: '高'
}

// 计算属性
const sortedStoredPosts = computed(() => {
  const posts = [...storedPosts.value]
  
  switch (sortBy.value) {
    case 'priority':
      return posts.sort((a, b) => b.priority - a.priority || new Date(a.created_at) - new Date(b.created_at))
    case 'time':
      return posts.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    case 'publish_id':
      return posts.sort((a, b) => a.publish_id - b.publish_id)
    default:
      return posts
  }
})

const uniqueUsers = computed(() => {
  const users = new Set()
  storedPosts.value.forEach(post => {
    if (post.submission) {
      users.add(post.submission.sender_id)
    }
  })
  return users.size
})

const earliestPost = computed(() => {
  if (storedPosts.value.length === 0) return '-'
  
  const earliest = storedPosts.value.reduce((earliest, post) => 
    new Date(post.created_at) < new Date(earliest.created_at) ? post : earliest
  )
  
  return moment(earliest.created_at).fromNow()
})

const nextPublishId = computed(() => {
  if (storedPosts.value.length === 0) return '-'
  
  const maxId = Math.max(...storedPosts.value.map(post => post.publish_id))
  return maxId + 1
})

// 方法
const loadStoredPosts = async () => {
  loading.value = true
  try {
    const params = selectedGroup.value ? { group_name: selectedGroup.value } : {}
    const { data } = await api.get('/management/stored-posts', { params })
    storedPosts.value = data
  } catch (error) {
    ElMessage.error('加载暂存区失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const loadActiveGroups = async () => {
  try {
    const { data } = await api.get('/management/stats')
    activeGroups.value = data.active_groups
  } catch (error) {
    console.error('加载活跃群组失败:', error)
  }
}

const handleGroupChange = () => {
  loadStoredPosts()
}

const handleSortChange = () => {
  // 排序逻辑在计算属性中处理
}

const publishAll = async () => {
  if (!selectedGroup.value) {
    ElMessage.warning('请先选择群组')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要发布群组 "${selectedGroup.value}" 的所有暂存投稿吗？`,
      '确认发布',
      { type: 'warning' }
    )
    
    publishing.value = true
    const result = await api.post('/management/stored-posts/publish', null, {
      params: { group_name: selectedGroup.value }
    })
    
    ElMessage.success(result.data.message || '发布成功')
    await loadStoredPosts()
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '发布失败')
    }
  } finally {
    publishing.value = false
  }
}

const clearAll = async () => {
  if (!selectedGroup.value) {
    ElMessage.warning('请先选择群组')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要清空群组 "${selectedGroup.value}" 的暂存区吗？此操作不可恢复！`,
      '确认清空',
      { type: 'warning' }
    )
    
    const result = await api.delete('/management/stored-posts/clear', {
      params: { group_name: selectedGroup.value }
    })
    
    ElMessage.success(result.data.message || '清空成功')
    await loadStoredPosts()
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '清空失败')
    }
  }
}

const handleAction = (post, action) => {
  currentPost.value = post
  
  switch (action) {
    case 'set-priority':
      priorityValue.value = post.priority
      showPriorityDialog.value = true
      break
    case 'publish-single':
      publishSingle(post)
      break
    case 'remove':
      removeFromStored(post)
      break
  }
}

const publishSingle = async (post) => {
  try {
    await ElMessageBox.confirm(
      `确定要单独发布投稿 #${post.publish_id} 吗？`,
      '确认发布',
      { type: 'warning' }
    )
    
    // 这里可以实现单独发布的逻辑
    ElMessage.info('功能开发中...')
  } catch (error) {
    // 用户取消
  }
}

const removeFromStored = async (post) => {
  try {
    await ElMessageBox.confirm(
      `确定要将投稿 #${post.publish_id} 移出暂存区吗？`,
      '确认移除',
      { type: 'warning' }
    )
    
    // 这里可以实现移出暂存区的逻辑
    ElMessage.info('功能开发中...')
  } catch (error) {
    // 用户取消
  }
}

const updatePriority = async () => {
  try {
    // 这里可以实现更新优先级的逻辑
    ElMessage.success('优先级更新成功')
    showPriorityDialog.value = false
    await loadStoredPosts()
  } catch (error) {
    ElMessage.error('更新优先级失败')
  }
}

const getPriorityType = (priority) => {
  if (priority >= 8) return 'danger'
  if (priority >= 5) return 'warning'
  if (priority >= 2) return 'primary'
  return 'info'
}

const getPriorityText = (priority) => {
  if (priority >= 8) return '高'
  if (priority >= 5) return '中'
  if (priority >= 2) return '普通'
  return '低'
}

const getRowClassName = ({ row }) => {
  if (row.priority >= 8) return 'high-priority-row'
  if (row.priority >= 5) return 'medium-priority-row'
  return ''
}

const formatTime = (timeStr) => {
  return moment(timeStr).format('YYYY-MM-DD HH:mm')
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', handleResize)
  await loadActiveGroups()
  if (activeGroups.value.length > 0) {
    selectedGroup.value = activeGroups.value[0]
    await loadStoredPosts()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.stored-posts {
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

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  margin-bottom: 20px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  padding: 12px;
  border-radius: 12px;
  background: rgba(99, 102, 241, 0.1);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.posts-card {
  margin-bottom: 20px;
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

.sort-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.submission-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.submitter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.submitter-name {
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.submission-meta {
  display: flex;
  gap: 6px;
}

.action-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-state {
  padding: 40px 0;
}

/* 行样式 */
:deep(.high-priority-row) {
  background: rgba(239, 68, 68, 0.05);
}

:deep(.medium-priority-row) {
  background: rgba(245, 158, 11, 0.05);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .stored-posts {
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
    display: flex;
    flex-wrap: nowrap;
    gap: 8px;
    align-items: center;
  }
  
  .header-actions .el-select {
    flex: 1 1 auto;
    min-width: 100px;
  }
  
  .header-actions .el-button {
    flex: 0 0 auto;
    min-width: 60px;
    max-width: 70px;
    height: 56px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    padding: 6px 4px;
    font-size: 11px;
    white-space: nowrap;
  }
  
  .header-actions .el-button .el-icon {
    font-size: 20px;
    margin: 0;
  }
  
  .header-actions .el-button > span {
    line-height: 1.1;
    text-align: center;
    width: 100%;
  }
  
  .card-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
  
  .card-title {
    font-size: 16px;
  }
  
  /* 表格移动端适配 */
  :deep(.el-table) {
    font-size: 13px;
  }
  
  :deep(.el-table .el-table__cell) {
    padding: 8px 4px;
  }
  
  .submission-info {
    gap: 6px;
  }
  
  .submitter {
    gap: 6px;
  }
  
  .submitter-name {
    font-size: 13px;
  }
  
  .submission-meta .el-tag {
    font-size: 10px;
    padding: 2px 4px;
    height: auto;
    line-height: 1.2;
  }
  
  .action-buttons {
    display: flex;
    flex-direction: row;
    gap: 6px;
    justify-content: flex-start;
    flex-wrap: nowrap;
  }
  
  .action-buttons .el-button {
    flex: 0 0 auto;
    min-width: 54px;
    max-width: 64px;
    height: 52px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    padding: 6px 3px;
    font-size: 11px;
  }
  
  .action-buttons .el-button .el-icon {
    font-size: 18px;
    margin: 0;
  }
  
  .action-buttons .el-button > span {
    white-space: nowrap;
    text-align: center;
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .action-buttons .el-dropdown {
    flex: 0 0 auto;
  }
  
  .action-buttons .el-dropdown .el-button {
    min-width: 50px;
    max-width: 60px;
  }
  
  /* 空状态移动端适配 */
  .empty-state {
    padding: 30px 16px;
  }
  
  .empty-state .el-empty {
    padding: 20px 0;
  }
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .page-title h2 {
    font-size: 18px;
  }
  
  .header-actions {
    gap: 6px;
  }
  
  .header-actions .el-button {
    min-width: 56px;
    max-width: 64px;
    height: 52px;
    padding: 5px 3px;
    font-size: 10px;
    gap: 2px;
  }
  
  .header-actions .el-button .el-icon {
    font-size: 18px;
  }
  
  .card-header {
    gap: 8px;
  }
  
  /* 表格内容更紧凑 */
  :deep(.el-table .el-table__cell) {
    padding: 6px 2px;
  }
  
  :deep(.el-table) {
    font-size: 12px;
  }
  
  .submitter-name {
    font-size: 12px;
  }
  
  .submission-meta .el-tag {
    font-size: 9px;
    padding: 1px 3px;
  }
  
  .action-buttons {
    gap: 5px;
  }
  
  .action-buttons .el-button {
    min-width: 50px;
    max-width: 58px;
    height: 48px;
    padding: 5px 2px;
    font-size: 10px;
    gap: 2px;
  }
  
  .action-buttons .el-button .el-icon {
    font-size: 16px;
  }
  
  .action-buttons .el-button > span {
    white-space: nowrap;
  }
  
  .action-buttons .el-dropdown .el-button {
    min-width: 50px;
    max-width: 58px;
  }
  
  /* 隐藏不重要的列 */
  :deep(.el-table .priority-col) {
    display: none;
  }
  
  .empty-state {
    padding: 20px 12px;
  }
}
</style>
