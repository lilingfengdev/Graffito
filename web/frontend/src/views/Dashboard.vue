<template>
  <div class="dashboard">
    <!-- 统计卡片网格 -->
    <div class="stats-grid">
      <div 
        v-for="stat in stats" 
        :key="stat.key"
        class="stat-card xw-glass xw-scale-in"
        :style="{ animationDelay: `${stat.key * 0.05}s` }"
      >
        <div class="stat-icon" :style="{ background: `linear-gradient(135deg, ${stat.color}, ${stat.colorDark || stat.color})` }">
          <el-icon :size="28"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-grid">
      <!-- 最近投稿趋势 -->
      <el-card class="chart-card trend-chart xw-glass" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">最近投稿趋势</span>
            <div class="header-actions">
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
          </div>
        </template>
        <div class="chart-container">
          <canvas ref="chartCanvas"></canvas>
        </div>
      </el-card>

      <!-- 状态分布 -->
      <el-card class="chart-card status-card xw-glass" shadow="never">
        <template #header>
          <span class="card-title">投稿状态分布</span>
        </template>
        <div class="status-distribution">
          <div 
            v-for="item in statusDistribution" 
            :key="item.status"
            class="status-item"
          >
            <div class="status-bar">
              <div 
                class="status-bar-fill" 
                :style="{ 
                  width: `${(item.count / totalSubmissions * 100)}%`,
                  background: `linear-gradient(90deg, ${item.color}, ${item.colorLight || item.color})`
                }"
              ></div>
            </div>
            <div class="status-info">
              <div class="status-indicator" :style="{ backgroundColor: item.color }"></div>
              <span class="status-label">{{ item.label }}</span>
              <span class="status-count">{{ item.count }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 活跃群组和快速操作 -->
    <div class="bottom-grid">
      <!-- 活跃群组 -->
      <el-card class="info-card xw-glass" shadow="never">
        <template #header>
          <span class="card-title">活跃群组</span>
        </template>
        <div class="groups-list">
          <el-tag 
            v-for="group in activeGroups" 
            :key="group"
            type="info"
            size="large"
            class="group-tag"
          >
            {{ group }}
          </el-tag>
          <el-empty 
            v-if="activeGroups.length === 0" 
            description="暂无活跃群组"
            :image-size="80"
          />
        </div>
      </el-card>

      <!-- 快速操作 -->
      <el-card class="info-card quick-actions-card xw-glass" shadow="never">
        <template #header>
          <span class="card-title">快速操作</span>
        </template>
        <div class="quick-actions">
          <button 
            class="action-btn primary"
            @click="$router.push('/audit')"
          >
            <el-icon :size="24"><Document /></el-icon>
            <span>审核管理</span>
          </button>
          <button 
            class="action-btn success"
            @click="$router.push('/stored')"
          >
            <el-icon :size="24"><Box /></el-icon>
            <span>暂存区</span>
          </button>
          <button 
            class="action-btn warning"
            @click="$router.push('/users')"
          >
            <el-icon :size="24"><User /></el-icon>
            <span>用户管理</span>
          </button>
          <button 
            class="action-btn danger"
            @click="$router.push('/feedbacks')"
          >
            <el-icon :size="24"><ChatDotRound /></el-icon>
            <span>反馈管理</span>
          </button>
        </div>
      </el-card>
    </div>

    <!-- 最新投稿 -->
    <el-card class="recent-submissions xw-glass" shadow="never">
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
  DataAnalysis, Refresh, Warning, ChatDotRound
} from '@element-plus/icons-vue'
import { Chart, registerables } from 'chart.js'
import moment from 'moment'
import api from '../api'

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
    key: 0,
    label: '总投稿数',
    value: statsData.value.total_submissions || 0,
    icon: Document,
    color: '#6366f1',
    colorDark: '#4f46e5'
  },
  {
    key: 1,
    label: '待审核',
    value: statsData.value.pending_submissions || 0,
    icon: Warning,
    color: '#f59e0b',
    colorDark: '#d97706'
  },
  {
    key: 2,
    label: '已发布',
    value: statsData.value.published_submissions || 0,
    icon: TrendCharts,
    color: '#10b981',
    colorDark: '#059669'
  },
  {
    key: 3,
    label: '暂存区',
    value: statsData.value.stored_posts_count || 0,
    icon: Box,
    color: '#8b5cf6',
    colorDark: '#7c3aed'
  },
  {
    key: 4,
    label: '待处理反馈',
    value: statsData.value.pending_feedbacks || 0,
    icon: ChatDotRound,
    color: '#ef4444',
    colorDark: '#dc2626'
  }
])

const totalSubmissions = computed(() => {
  return statusDistribution.value.reduce((sum, item) => sum + item.count, 0) || 1
})

const statusDistribution = computed(() => [
  {
    status: 'pending',
    label: '待审核',
    count: statsData.value.pending_submissions || 0,
    color: '#f59e0b',
    colorLight: '#fbbf24'
  },
  {
    status: 'approved',
    label: '已通过',
    count: statsData.value.approved_submissions || 0,
    color: '#10b981',
    colorLight: '#34d399'
  },
  {
    status: 'published',
    label: '已发布',
    count: statsData.value.published_submissions || 0,
    color: '#6366f1',
    colorLight: '#818cf8'
  },
  {
    status: 'rejected',
    label: '已拒绝',
    count: statsData.value.rejected_submissions || 0,
    color: '#ef4444',
    colorLight: '#f87171'
  }
])

const activeGroups = computed(() => statsData.value.active_groups || [])

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
        fill: true,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: '#6366f1',
        pointBorderColor: '#fff',
        pointBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: 'rgba(30, 41, 59, 0.95)',
          titleColor: '#f8fafc',
          bodyColor: '#e2e8f0',
          borderColor: '#6366f1',
          borderWidth: 1,
          cornerRadius: 8,
          padding: 12
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(148, 163, 184, 0.1)'
          },
          ticks: {
            color: '#94a3b8',
            stepSize: 1,
            font: {
              size: 12
            }
          }
        },
        x: {
          grid: {
            display: false
          },
          ticks: {
            color: '#94a3b8',
            font: {
              size: 12
            }
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
  setInterval(() => {
    loadStats()
    loadRecentSubmissions()
  }, 60000) // 60秒刷新一次
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--xw-space-6);
}

/* 统计卡片网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xw-space-4);
}

.stat-card {
  padding: var(--xw-space-5);
  display: flex;
  align-items: center;
  gap: var(--xw-space-4);
  border-radius: var(--xw-radius-xl);
  transition: var(--xw-transition);
  cursor: pointer;
}

.stat-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: var(--xw-shadow-lg);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--xw-radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: var(--xw-shadow-md);
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: var(--xw-text-3xl);
  font-weight: var(--xw-font-bold);
  color: var(--xw-text-primary);
  line-height: 1;
  margin-bottom: var(--xw-space-1);
}

.stat-label {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  font-weight: var(--xw-font-medium);
}

/* 图表网格 */
.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--xw-space-6);
}

.chart-card {
  border-radius: var(--xw-radius-xl);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--xw-space-3);
}

.card-title {
  font-size: var(--xw-text-lg);
  font-weight: var(--xw-font-semibold);
  color: var(--xw-text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--xw-space-2);
}

.chart-container {
  height: 300px;
  position: relative;
  padding: var(--xw-space-4) 0;
}

/* 状态分布 */
.status-distribution {
  padding: var(--xw-space-4) 0;
  display: flex;
  flex-direction: column;
  gap: var(--xw-space-4);
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: var(--xw-space-2);
}

.status-bar {
  height: 8px;
  background: var(--xw-bg-tertiary);
  border-radius: var(--xw-radius-full);
  overflow: hidden;
}

.status-bar-fill {
  height: 100%;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: var(--xw-radius-full);
}

.status-info {
  display: flex;
  align-items: center;
  gap: var(--xw-space-2);
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-label {
  flex: 1;
  color: var(--xw-text-secondary);
  font-size: var(--xw-text-sm);
  font-weight: var(--xw-font-medium);
}

.status-count {
  font-weight: var(--xw-font-bold);
  color: var(--xw-text-primary);
  font-size: var(--xw-text-base);
}

/* 底部网格 */
.bottom-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--xw-space-6);
}

.info-card {
  border-radius: var(--xw-radius-xl);
}

.groups-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xw-space-2);
  padding: var(--xw-space-2) 0;
  min-height: 80px;
}

.group-tag {
  font-weight: var(--xw-font-medium);
}

/* 快速操作 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--xw-space-3);
  padding: var(--xw-space-2) 0;
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--xw-space-2);
  padding: var(--xw-space-5);
  border: none;
  border-radius: var(--xw-radius-xl);
  color: white;
  font-size: var(--xw-text-sm);
  font-weight: var(--xw-font-semibold);
  cursor: pointer;
  transition: var(--xw-transition);
  box-shadow: var(--xw-shadow-sm);
}

.action-btn:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--xw-shadow-md);
}

.action-btn:active {
  transform: translateY(0) scale(0.98);
}

.action-btn.primary {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}

.action-btn.success {
  background: linear-gradient(135deg, #10b981, #059669);
}

.action-btn.warning {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.action-btn.danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
}

/* 最新投稿 */
.recent-submissions {
  border-radius: var(--xw-radius-xl);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .dashboard {
    gap: var(--xw-space-4);
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--xw-space-3);
  }
  
  .stat-card {
    flex-direction: column;
    text-align: center;
    padding: var(--xw-space-4);
  }
  
  .stat-icon {
    width: 48px;
    height: 48px;
  }
  
  .stat-value {
    font-size: var(--xw-text-2xl);
  }
  
  .chart-container {
    height: 250px;
    padding: var(--xw-space-2) 0;
  }
  
  .bottom-grid {
    grid-template-columns: 1fr;
    gap: var(--xw-space-4);
  }
  
  .quick-actions {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--xw-space-2);
  }
  
  .action-btn {
    padding: var(--xw-space-4);
    gap: var(--xw-space-1);
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .stat-card {
    flex-direction: row;
    text-align: left;
  }
  
  .quick-actions {
    grid-template-columns: 1fr;
  }
}
</style>
