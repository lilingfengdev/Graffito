<template>
  <div class="logs-management">
    <!-- 页面标题 -->
    <el-card shadow="never" class="page-header">
      <div class="header-wrapper">
        <div class="header-content">
          <h2>系统日志</h2>
          <el-text type="info">查看和搜索系统运行日志</el-text>
        </div>
        <div class="header-actions">
          <el-button-group>
            <el-button 
              :type="filters.order === 'desc' ? 'primary' : ''" 
              @click="handleOrderChange('desc')"
              :disabled="loading"
            >
              倒序
            </el-button>
            <el-button 
              :type="filters.order === 'asc' ? 'primary' : ''" 
              @click="handleOrderChange('asc')"
              :disabled="loading"
            >
              正序
            </el-button>
          </el-button-group>
          <el-button :icon="Refresh" @click="handleRefresh" :loading="loading">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 过滤器 -->
    <el-card shadow="never" class="filters-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="日期">
          <el-date-picker
            v-model="filters.date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 200px"
          />
        </el-form-item>
        
        <el-form-item label="日志级别">
          <el-select v-model="filters.level" placeholder="所有级别" clearable style="width: 150px">
            <el-option label="DEBUG" value="DEBUG" />
            <el-option label="INFO" value="INFO" />
            <el-option label="WARNING" value="WARNING" />
            <el-option label="ERROR" value="ERROR" />
            <el-option label="CRITICAL" value="CRITICAL" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="关键词">
          <el-input
            v-model="filters.search"
            placeholder="搜索日志内容..."
            clearable
            style="width: 250px"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch" :loading="loading">
            搜索
          </el-button>
          <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 日志统计 -->
    <el-card shadow="never" class="stats-card" v-if="total > 0">
      <el-statistic title="日志总数" :value="total" />
      <el-divider direction="vertical" />
      <el-text>当前第 {{ currentPage }} 页，每页 {{ pageSize }} 条</el-text>
    </el-card>

    <!-- 日志列表 -->
    <el-card shadow="never" class="logs-card" v-loading="loading">
      <template v-if="logs.length > 0">
        <el-table 
          :data="logs" 
          stripe 
          style="width: 100%"
          :row-class-name="getRowClassName"
        >
          <el-table-column prop="timestamp" label="时间" width="200" />
          
          <el-table-column prop="level" label="级别" width="120">
            <template #default="{ row }">
              <el-tag 
                :type="getLevelTagType(row.level)" 
                size="small"
                effect="dark"
              >
                {{ row.level }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column prop="location" label="位置" width="280">
            <template #default="{ row }">
              <el-text type="info" size="small" style="font-family: monospace;">
                {{ row.location }}
              </el-text>
            </template>
          </el-table-column>
          
          <el-table-column prop="message" label="消息" min-width="400">
            <template #default="{ row }">
              <el-text style="word-break: break-word; font-family: monospace; font-size: 13px;">
                {{ row.message }}
              </el-text>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next, jumper"
            @current-change="handlePageChange"
            :disabled="loading"
          />
        </div>
      </template>

      <!-- 空状态 -->
      <el-empty v-else description="暂无日志数据" :image-size="120">
        <el-button type="primary" @click="handleReset">重新加载</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, RefreshLeft } from '@element-plus/icons-vue'
import api from '../api'

const logs = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(100)
const hasMore = ref(false)
const loading = ref(false)

const filters = reactive({
  date: '',
  level: '',
  search: '',
  order: 'desc'  // 默认倒序
})

// 获取日志级别对应的标签类型
const getLevelTagType = (level) => {
  const levelMap = {
    'DEBUG': 'info',
    'INFO': 'primary',
    'WARNING': 'warning',
    'ERROR': 'danger',
    'CRITICAL': 'danger'
  }
  return levelMap[level] || 'info'
}

// 获取行类名（用于高亮错误行）
const getRowClassName = ({ row }) => {
  if (row.level === 'ERROR' || row.level === 'CRITICAL') {
    return 'error-row'
  }
  if (row.level === 'WARNING') {
    return 'warning-row'
  }
  return ''
}

// 获取日志
const fetchLogs = async (page = 1) => {
  loading.value = true
  try {
    const params = {
      page,
      page_size: pageSize.value,
      date: filters.date || undefined,
      level: filters.level || undefined,
      search: filters.search || undefined,
      order: filters.order || 'desc'
    }

    // 移除 undefined 值
    Object.keys(params).forEach(key => {
      if (params[key] === undefined) {
        delete params[key]
      }
    })

    const { data } = await api.get('/management/logs', { params })
    
    logs.value = data.logs || []
    total.value = data.total || 0
    currentPage.value = data.page || 1
    hasMore.value = data.has_more || false
    
    if (logs.value.length === 0 && total.value === 0) {
      ElMessage.info('未找到日志记录')
    }
  } catch (error) {
    console.error('获取日志失败:', error)
    if (error.response?.status === 403) {
      ElMessage.error('您没有权限查看日志（需要超级管理员权限）')
    } else {
      ElMessage.error('获取日志失败: ' + (error.response?.data?.detail || error.message))
    }
    // 即使失败也清空数据
    logs.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  fetchLogs(1)
}

// 重置
const handleReset = () => {
  filters.date = ''
  filters.level = ''
  filters.search = ''
  filters.order = 'desc'
  currentPage.value = 1
  fetchLogs(1)
}

// 排序变化
const handleOrderChange = (order) => {
  filters.order = order
  currentPage.value = 1
  fetchLogs(1)
}

// 刷新
const handleRefresh = () => {
  fetchLogs(currentPage.value)
}

// 页码变化
const handlePageChange = (page) => {
  fetchLogs(page)
  // 滚动到顶部
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.logs-management {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.header-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.header-content h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.4;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
  flex-wrap: nowrap;
}

.filters-card {
  margin-bottom: 16px;
}

.filter-form {
  margin-bottom: 0;
}

.filter-form :deep(.el-form-item:last-child) {
  margin-right: 0;
}

.filter-form :deep(.el-form-item:last-child .el-form-item__content) {
  display: flex;
  gap: 12px;
}

.stats-card {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 24px;
}

.logs-card {
  min-height: 400px;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding: 16px 0;
}

/* 表格行样式 */
:deep(.error-row) {
  background-color: #fef0f0;
}

:deep(.warning-row) {
  background-color: #fdf6ec;
}

:deep(.el-table__body tr.error-row:hover > td) {
  background-color: #fde2e2 !important;
}

:deep(.el-table__body tr.warning-row:hover > td) {
  background-color: #faecd8 !important;
}

/* 深色模式适配 */
html.dark :deep(.error-row) {
  background-color: rgba(245, 108, 108, 0.1);
}

html.dark :deep(.warning-row) {
  background-color: rgba(230, 162, 60, 0.1);
}

html.dark :deep(.el-table__body tr.error-row:hover > td) {
  background-color: rgba(245, 108, 108, 0.15) !important;
}

html.dark :deep(.el-table__body tr.warning-row:hover > td) {
  background-color: rgba(230, 162, 60, 0.15) !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .logs-management {
    padding: 12px;
  }

  .header-wrapper {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .header-content h2 {
    font-size: 18px;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: nowrap !important;
    gap: 10px;
    display: flex !important;
  }
  
  .header-actions .el-button-group {
    flex-shrink: 0;
    display: inline-flex;
  }
  
  .header-actions .el-button {
    flex-shrink: 0;
  }

  .filter-form {
    display: flex;
    flex-direction: column;
  }

  :deep(.el-form-item) {
    margin-right: 0;
    margin-bottom: 16px;
  }

  :deep(.el-form-item__content) {
    width: 100%;
  }
  
  .filter-form :deep(.el-form-item:last-child) {
    margin-bottom: 0;
  }
  
  .filter-form :deep(.el-form-item:last-child .el-form-item__content) {
    display: flex;
    gap: 10px;
    width: 100%;
  }
  
  .filter-form :deep(.el-form-item:last-child .el-button) {
    flex: 1;
  }

  :deep(.el-input),
  :deep(.el-select),
  :deep(.el-date-picker) {
    width: 100% !important;
  }

  .stats-card {
    flex-direction: column;
    align-items: flex-start;
  }

  :deep(.el-divider--vertical) {
    display: none;
  }

  /* 表格响应式 */
  :deep(.el-table) {
    font-size: 12px;
  }

  :deep(.el-table th) {
    padding: 8px 0;
  }

  :deep(.el-table td) {
    padding: 8px 0;
  }
}
</style>

