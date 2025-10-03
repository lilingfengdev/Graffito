<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :xs="12" :sm="6" v-for="stat in stats" :key="stat.key">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon" :style="{ color: stat.color }">
              <el-icon :size="32"><component :is="stat.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="charts-row">
      <!-- 最近投稿趋势 -->
      <el-col :xs="24" :lg="16">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span class="card-title">最近投稿趋势</span>
              <el-radio-group v-model="trendRange" size="small">
                <el-radio-button label="7">7天</el-radio-button>
                <el-radio-button label="30">30天</el-radio-button>
              </el-radio-group>
              <el-button 
                type="primary" 
                :icon="Refresh" 
                circle 
                size="small"
                @click="loadStats"
              />
            </div>
          </template>
          <div class="chart-container">
            <canvas ref="chartCanvas" width="400" height="200"></canvas>
          </div>
        </el-card>
      </el-col>

      <!-- 状态分布 -->
      <el-col :xs="24" :lg="8">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <span class="card-title">投稿状态分布</span>
          </template>
          <div class="status-distribution">
            <div 
              v-for="item in statusDistribution" 
              :key="item.status"
              class="status-item"
            >
              <div class="status-indicator" :style="{ backgroundColor: item.color }"></div>
              <span class="status-label">{{ item.label }}</span>
              <span class="status-count">{{ item.count }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 活跃群组和快速操作 -->
    <el-row :gutter="20" class="bottom-row">
      <!-- 活跃群组 -->
      <el-col :xs="24" :lg="12">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <span class="card-title">活跃群组</span>
          </template>
          <div class="groups-list">
            <el-tag 
              v-for="group in activeGroups" 
              :key="group"
              type="info"
              class="group-tag"
            >
              {{ group }}
            </el-tag>
            <el-tag v-if="activeGroups.length === 0" type="info">
              暂无活跃群组
            </el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- 快速操作 -->
      <el-col :xs="24" :lg="12" class="quick-actions-col">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <span class="card-title">快速操作</span>
          </template>
          <div class="quick-actions">
            <el-button 
              type="primary" 
              :icon="Document"
              @click="$router.push('/audit')"
            >
              审核管理
            </el-button>
            <el-button 
              type="success" 
              :icon="Box"
              @click="$router.push('/stored')"
            >
              暂存区
            </el-button>
            <el-button 
              type="warning" 
              :icon="User"
              @click="$router.push('/users')"
            >
              用户管理
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最新投稿 -->
    <el-card class="recent-submissions" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">最新投稿</span>
          <el-button 
            type="primary" 
            size="small"
            plain
            @click="$router.push('/audit')"
          >
            查看全部
          </el-button>
        </div>
      </template>
      <el-table 
        :data="recentSubmissions" 
        style="width: 100%"
        :header-cell-style="{ background: 'transparent' }"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="sender_nickname" label="投稿者" width="120" />
        <el-table-column prop="group_name" label="群组" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.group_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag 
              :type="getStatusType(row.status)" 
              size="small"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button 
              type="primary" 
              size="small" 
              text
              @click="$router.push(`/submission/${row.id}`)"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { 
  Document, User, Box, TrendCharts, 
  DataAnalysis, Refresh, Warning
} from '@element-plus/icons-vue'
import { Chart, registerables } from 'chart.js'
import moment from 'moment'
import api from '../api'

// 注册Chart.js组件
Chart.register(...registerables)

const loading = ref(false)
const statsData = ref({})
const recentSubmissions = ref([])
const chartCanvas = ref(null)
let chart = null
const trendRange = ref('30')

// 计算属性
const stats = computed(() => [
  {
    key: 'total',
    label: '总投稿数',
    value: statsData.value.total_submissions || 0,
    icon: Document,
    color: '#6366f1'
  },
  {
    key: 'pending',
    label: '待审核',
    value: statsData.value.pending_submissions || 0,
    icon: Warning,
    color: '#f59e0b'
  },
  {
    key: 'published',
    label: '已发布',
    value: statsData.value.published_submissions || 0,
    icon: TrendCharts,
    color: '#10b981'
  },
  {
    key: 'stored',
    label: '暂存区',
    value: statsData.value.stored_posts_count || 0,
    icon: Box,
    color: '#8b5cf6'
  }
])

const statusDistribution = computed(() => [
  {
    status: 'pending',
    label: '待审核',
    count: statsData.value.pending_submissions || 0,
    color: '#f59e0b'
  },
  {
    status: 'approved',
    label: '已通过',
    count: statsData.value.approved_submissions || 0,
    color: '#10b981'
  },
  {
    status: 'published',
    label: '已发布',
    count: statsData.value.published_submissions || 0,
    color: '#6366f1'
  },
  {
    status: 'rejected',
    label: '已拒绝',
    count: statsData.value.rejected_submissions || 0,
    color: '#ef4444'
  }
])

const activeGroups = computed(() => {
  return statsData.value.active_groups || []
})

// 方法
const loadStats = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/management/stats')
    statsData.value = data
    updateChart()
  } catch (error) {
    console.error('加载统计数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadRecentSubmissions = async () => {
  try {
    const { data } = await api.get('/audit/submissions', { 
      params: { limit: 10 } 
    })
    recentSubmissions.value = data
  } catch (error) {
    console.error('加载最新投稿失败:', error)
  }
}

const updateChart = () => {
  if (!chartCanvas.value || !statsData.value) return
  
  const ctx = chartCanvas.value.getContext('2d')
  
  if (chart) {
    chart.destroy()
  }
  
  const recentData = trendRange.value === '30' 
    ? (statsData.value.recent_30d_submissions || {})
    : (statsData.value.recent_submissions || {})
  const dates = Object.keys(recentData).sort()
  const values = dates.map(date => recentData[date])
  
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: dates.map(date => moment(date).format('MM/DD')),
      datasets: [{
        label: '投稿数量',
        data: values,
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        tension: 0.4,
        fill: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(71, 85, 105, 0.3)'
          },
          ticks: {
            color: '#94a3b8',
            stepSize: 1
          }
        },
        x: {
          grid: {
            color: 'rgba(71, 85, 105, 0.3)'
          },
          ticks: {
            color: '#94a3b8'
          }
        }
      }
    }
  })
}

watch(trendRange, () => {
  updateChart()
})

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

const formatTime = (timeStr) => {
  return moment(timeStr).format('YYYY-MM-DD HH:mm')
}

onMounted(async () => {
  await loadStats()
  await loadRecentSubmissions()
  // 定时刷新统计与列表
  setInterval(() => {
    loadStats()
    loadRecentSubmissions()
  }, 30000)
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
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

.charts-row {
  margin-bottom: 20px;
}

.chart-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 32px;
  gap: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.chart-container {
  height: 300px;
  position: relative;
}

.status-distribution {
  padding: 20px 0;
}

.status-item {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status-label {
  flex: 1;
  color: var(--el-text-color-regular);
}

.status-count {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.bottom-row {
  margin-bottom: 20px;
}

.info-card {
  margin-bottom: 20px;
}

.groups-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 0;
}

.group-tag {
  margin: 0;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 0;
}

.recent-submissions {
  margin-bottom: 20px;
}

/* 默认隐藏快速操作（移动端） */
.quick-actions-col {
  display: none !important;
}

/* 桌面端显示快速操作 */
@media (min-width: 769px) {
  .quick-actions-col {
    display: block !important;
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .dashboard {
    padding: 0;
  }
  
  .stats-row,
  .charts-row,
  .bottom-row {
    margin: 0 0 16px 0;
  }
  
  .stat-card {
    margin-bottom: 12px;
  }
  
  .stat-content {
    flex-direction: column;
    text-align: center;
    gap: 8px;
    padding: 16px 12px;
  }
  
  .stat-value {
    font-size: 20px;
  }
  
  .stat-label {
    font-size: 12px;
  }
  
  .chart-container {
    height: 250px;
    padding: 10px;
  }
  
  .card-header {
    flex-wrap: wrap;
    gap: 12px;
  }
  
  .card-title {
    font-size: 14px;
  }
  
  .status-item {
    margin-bottom: 12px;
    padding: 8px 0;
  }
  
  .status-label {
    font-size: 13px;
  }
  
  .groups-list {
    gap: 6px;
  }
  
  .group-tag {
    font-size: 12px;
    padding: 4px 8px;
  }
  
  /* 表格适配 */
  :deep(.el-table) {
    font-size: 13px;
  }
  
  :deep(.el-table .el-button) {
    padding: 4px 8px;
    font-size: 12px;
  }
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .stat-content {
    padding: 12px 8px;
  }
  
  .stat-value {
    font-size: 18px;
  }
  
  .stat-icon :deep(.el-icon) {
    font-size: 24px !important;
  }
  
  .card-title {
    font-size: 13px;
  }
  
  .chart-container {
    height: 200px;
    padding: 8px;
  }
  
  .status-distribution {
    padding: 10px;
  }
  
  .groups-list {
    padding: 8px 0;
  }
}
</style>
