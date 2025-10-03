<template>
  <div class="report-management">
    <div class="header-section">
      <h2>举报审核管理</h2>
      <div class="filters">
        <el-select v-model="statusFilter" placeholder="状态筛选" @change="handleFilterChange" clearable>
          <el-option label="全部" value="" />
          <el-option label="待处理" value="pending" />
          <el-option label="AI处理中" value="ai_processing" />
          <el-option label="人工审核中" value="manual_review" />
          <el-option label="已处理" value="resolved" />
        </el-select>
        <el-button type="primary" @click="loadReports" :icon="Refresh">刷新</el-button>
      </div>
    </div>

    <el-table 
      :data="reports" 
      v-loading="loading"
      style="width: 100%"
      @row-click="handleRowClick"
      class="report-table"
    >
      <el-table-column prop="id" label="举报ID" width="100" />
      <el-table-column label="投稿ID" width="100">
        <template #default="{ row }">
          {{ row.submission?.publish_id || row.submission?.id || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="reporter_id" label="举报者" width="150">
        <template #default="{ row }">
          <span class="mono-text">{{ row.reporter_id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="举报理由" min-width="200">
        <template #default="{ row }">
          <div class="text-ellipsis">{{ row.reason || '无' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">
            {{ getStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ai_level" label="AI评级" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.ai_level" :type="getLevelType(row.ai_level)">
            {{ getLevelLabel(row.ai_level) }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="processed_by" label="处理人" width="120" />
      <el-table-column prop="created_at" label="举报时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button 
            v-if="row.status === 'manual_review'" 
            type="primary" 
            size="small"
            @click.stop="handleProcess(row)"
          >
            处理
          </el-button>
          <el-button 
            type="info" 
            size="small"
            @click.stop="handleViewDetail(row)"
          >
            详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handlePageChange"
      class="pagination"
    />

    <!-- 举报详情对话框 -->
    <el-dialog 
      v-model="detailDialogVisible" 
      title="举报详情"
      width="800px"
      :destroy-on-close="true"
    >
      <div v-if="currentReport" class="report-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="举报ID">{{ currentReport.id }}</el-descriptions-item>
          <el-descriptions-item label="投稿ID">
            {{ currentReport.submission?.publish_id || currentReport.submission?.id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="举报者">{{ currentReport.reporter_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentReport.status)">
              {{ getStatusLabel(currentReport.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="举报理由" :span="2">
            {{ currentReport.reason || '无' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">AI 审核结果</el-divider>
        <div v-if="currentReport.ai_level" class="ai-result">
          <div class="result-item">
            <span class="label">评级：</span>
            <el-tag :type="getLevelType(currentReport.ai_level)">
              {{ getLevelLabel(currentReport.ai_level) }}
            </el-tag>
          </div>
          <div class="result-item">
            <span class="label">理由：</span>
            <span>{{ currentReport.ai_reason }}</span>
          </div>
        </div>
        <div v-else class="no-data">暂无 AI 审核结果</div>

        <el-divider content-position="left">投稿内容</el-divider>
        <div v-if="currentReport.submission_full" class="submission-content">
          <div class="content-section">
            <h4>LLM 总结：</h4>
            <p>{{ currentReport.submission_full.llm_result?.summary || '无' }}</p>
          </div>
        </div>

        <el-divider content-position="left">平台评论 ({{ currentReport.comments?.length || 0 }})</el-divider>
        <div v-if="currentReport.comments && currentReport.comments.length > 0" class="comments-section">
          <div 
            v-for="comment in currentReport.comments" 
            :key="comment.id"
            class="comment-item"
          >
            <div class="comment-header">
              <span class="platform-tag">{{ comment.platform }}</span>
              <span class="author">{{ comment.author_name || comment.author_id }}</span>
              <span class="time">{{ formatTime(comment.created_at) }}</span>
            </div>
            <div class="comment-content">{{ comment.content }}</div>
          </div>
        </div>
        <div v-else class="no-data">暂无评论</div>

        <el-divider v-if="currentReport.processed_by" content-position="left">处理结果</el-divider>
        <div v-if="currentReport.processed_by" class="process-result">
          <div class="result-item">
            <span class="label">处理人：</span>
            <span>{{ currentReport.processed_by }}</span>
          </div>
          <div class="result-item">
            <span class="label">处理动作：</span>
            <el-tag :type="currentReport.manual_action === 'delete' ? 'danger' : 'success'">
              {{ currentReport.manual_action === 'delete' ? '删除' : '保留' }}
            </el-tag>
          </div>
          <div class="result-item">
            <span class="label">处理理由：</span>
            <span>{{ currentReport.manual_reason }}</span>
          </div>
          <div class="result-item">
            <span class="label">处理时间：</span>
            <span>{{ formatTime(currentReport.processed_at) }}</span>
          </div>
        </div>
      </div>

      <template #footer v-if="currentReport && currentReport.status === 'manual_review'">
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="success" @click="handleProcessAction('keep')">
          判定为安全
        </el-button>
        <el-button type="danger" @click="handleProcessAction('delete')">
          删除投稿
        </el-button>
      </template>
    </el-dialog>

    <!-- 处理对话框 -->
    <el-dialog 
      v-model="processDialogVisible" 
      :title="`处理举报 - ${processAction === 'delete' ? '删除投稿' : '判定安全'}`"
      width="500px"
    >
      <el-form :model="processForm" label-width="100px">
        <el-form-item label="处理动作">
          <el-tag :type="processAction === 'delete' ? 'danger' : 'success'">
            {{ processAction === 'delete' ? '删除投稿' : '判定安全' }}
          </el-tag>
        </el-form-item>
        <el-form-item label="处理理由" required>
          <el-input 
            v-model="processForm.reason" 
            type="textarea"
            :rows="4"
            placeholder="请输入处理理由"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="submitProcess"
          :loading="processing"
        >
          确认处理
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import api from '../api'
import { formatDateTime } from '../utils/format'

// 数据
const reports = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const statusFilter = ref('')

// 对话框
const detailDialogVisible = ref(false)
const currentReport = ref(null)
const processDialogVisible = ref(false)
const processAction = ref('')
const processForm = ref({
  reason: ''
})
const processing = ref(false)

// 方法
const loadReports = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/management/reports', {
      params: {
        status: statusFilter.value || undefined,
        page: currentPage.value,
        page_size: pageSize.value
      }
    })
    reports.value = data.data.items
    total.value = data.data.total
  } catch (error) {
    ElMessage.error('加载举报列表失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  currentPage.value = 1
  loadReports()
}

const handlePageChange = () => {
  loadReports()
}

const handleSizeChange = () => {
  currentPage.value = 1
  loadReports()
}

const handleRowClick = (row) => {
  handleViewDetail(row)
}

const handleViewDetail = async (row) => {
  try {
    const { data } = await api.get(`/management/reports/${row.id}`)
    currentReport.value = data.data
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载举报详情失败: ' + (error.response?.data?.detail || error.message))
  }
}

const handleProcess = (row) => {
  handleViewDetail(row)
}

const handleProcessAction = (action) => {
  processAction.value = action
  processForm.value.reason = ''
  processDialogVisible.value = true
}

const submitProcess = async () => {
  if (!processForm.value.reason) {
    ElMessage.warning('请输入处理理由')
    return
  }

  processing.value = true
  try {
    await api.post(`/management/reports/${currentReport.value.id}/process`, {
      action: processAction.value,
      reason: processForm.value.reason
    })
    
    ElMessage.success('处理成功')
    processDialogVisible.value = false
    detailDialogVisible.value = false
    loadReports()
  } catch (error) {
    ElMessage.error('处理失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    processing.value = false
  }
}

const getStatusType = (status) => {
  const types = {
    'pending': 'info',
    'ai_processing': 'warning',
    'manual_review': 'danger',
    'resolved': 'success'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'pending': '待处理',
    'ai_processing': 'AI处理中',
    'manual_review': '人工审核',
    'resolved': '已处理'
  }
  return labels[status] || status
}

const getLevelType = (level) => {
  const types = {
    'safe': 'success',
    'warning': 'warning',
    'danger': 'danger'
  }
  return types[level] || 'info'
}

const getLevelLabel = (level) => {
  const labels = {
    'safe': '安全',
    'warning': '警告',
    'danger': '危险'
  }
  return labels[level] || level
}

const formatTime = (time) => {
  return time ? formatDateTime(time) : '-'
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.report-management {
  padding: 20px;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.filters {
  display: flex;
  gap: 10px;
}

.report-table {
  margin-bottom: 20px;
}

.report-table :deep(.el-table__row) {
  cursor: pointer;
}

.report-table :deep(.el-table__row:hover) {
  background-color: var(--xw-bg-secondary);
}

.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono-text {
  font-family: 'Courier New', monospace;
}

.pagination {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.report-detail {
  max-height: 600px;
  overflow-y: auto;
}

.ai-result,
.submission-content,
.process-result {
  padding: 15px;
  background-color: var(--xw-bg-secondary);
  border-radius: 4px;
}

.result-item {
  margin-bottom: 10px;
}

.result-item .label {
  font-weight: bold;
  margin-right: 8px;
}

.content-section h4 {
  margin-top: 0;
  margin-bottom: 10px;
  color: var(--xw-text-secondary);
}

.content-section p {
  margin: 0;
  line-height: 1.6;
}

.comments-section {
  max-height: 300px;
  overflow-y: auto;
}

.comment-item {
  padding: 10px;
  margin-bottom: 10px;
  background-color: var(--xw-bg-secondary);
  border-radius: 4px;
}

.comment-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--xw-text-tertiary);
}

.platform-tag {
  padding: 2px 8px;
  background-color: #409eff;
  color: white;
  border-radius: 3px;
  font-size: 11px;
}

.author {
  font-weight: bold;
}

.comment-content {
  line-height: 1.6;
  color: var(--xw-text-primary);
}

.no-data {
  text-align: center;
  padding: 20px;
  color: var(--xw-text-tertiary);
}
</style>

