<template>
  <div class="user-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="page-title">
          <h1>用户管理</h1>
          <div class="title-stats">
            <el-tag type="danger" size="large">黑名单 {{ filteredBlacklist.length }} 人</el-tag>
            <el-tag type="primary" size="large">管理员 {{ filteredAdmins.length }} 人</el-tag>
          </div>
        </div>
        
        <div class="header-actions">
          <el-button 
            type="primary" 
            :icon="Refresh"
            @click="refreshCurrentTab"
            :loading="blacklistState.loading || adminState.loading"
            round
          >
            刷新
          </el-button>
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <el-card class="main-card" shadow="hover">
      <el-tabs v-model="activeTab" class="management-tabs">
        <!-- 黑名单管理 -->
        <el-tab-pane label="黑名单管理" name="blacklist">
          <div class="tab-content">
            <div class="tab-header">
              <div class="tab-title">
                <h3>黑名单用户</h3>
                <el-tag type="info">{{ filteredBlacklist.length }} 条记录</el-tag>
              </div>
              <div class="tab-actions">
                <el-input
                  v-model="blacklistState.searchText"
                  placeholder="搜索用户ID或群组"
                  :prefix-icon="Search"
                  style="width: 200px; margin-right: 12px;"
                  @input="handleBlacklistSearch"
                  clearable
                />
                <el-button 
                  type="primary" 
                  :icon="Plus"
                  @click="showAddDialog = true"
                >
                  添加黑名单
                </el-button>
              </div>
            </div>

            <!-- 黑名单表格 -->
            <div class="table-container">
              <el-table 
                :data="paginatedBlacklist" 
                v-loading="blacklistState.loading"
                class="blacklist-table"
                stripe
                :header-cell-style="headerCellStyle"
              >
        <el-table-column prop="user_id" label="用户ID" width="150">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="32" style="background-color: #ef4444;">
                {{ row.user_id[0] }}
              </el-avatar>
              <span class="user-id">{{ row.user_id }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="group_name" label="群组" width="120">
          <template #default="{ row }">
            <el-tag type="info">{{ row.group_name }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="reason" label="拉黑原因" min-width="200">
          <template #default="{ row }">
            <span v-if="row.reason">{{ row.reason }}</span>
            <span v-else class="no-reason">未填写原因</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="operator_id" label="操作员" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="warning" v-if="row.operator_id">
              {{ row.operator_id }}
            </el-tag>
            <span v-else class="no-operator">系统</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="拉黑时间" width="160">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="过期时间" width="160">
          <template #default="{ row }">
            <span v-if="row.expires_at">{{ formatTime(row.expires_at) }}</span>
            <el-tag v-else type="danger" size="small">永久</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag 
              :type="row.is_active ? 'danger' : 'success'" 
              size="small"
            >
              {{ row.is_active ? '有效' : '已过期' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button 
                type="primary" 
                size="small"
                :icon="View"
                @click="viewUserDetail(row.user_id)"
              >
                详情
              </el-button>
              <el-button 
                type="success" 
                size="small"
                :icon="CircleCheck"
                @click="removeFromBlacklist(row.id)"
                v-if="row.is_active"
              >
                解禁
              </el-button>
              <el-button 
                type="danger" 
                size="small"
                :icon="Delete"
                @click="deleteBlacklistEntry(row.id)"
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
                v-model:current-page="blacklistState.currentPage"
                :page-size="blacklistState.pageSize"
                :total="filteredBlacklist.length"
                layout="prev, pager, next"
                @current-change="handleBlacklistPageChange"
                background
              />
              <div class="pagination-info">
                共 {{ filteredBlacklist.length }} 条记录，当前第 {{ blacklistState.currentPage }} 页
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 管理员管理 -->
        <el-tab-pane label="管理员管理" name="admins" v-if="currentUser.isAdmin">
          <div class="tab-content">
            <div class="tab-header">
              <div class="tab-title">
                <h3>管理员列表</h3>
                <el-tag type="primary">{{ filteredAdmins.length }} 条记录</el-tag>
              </div>
              <div class="tab-actions">
                <el-input
                  v-model="adminState.searchText"
                  placeholder="搜索用户ID或昵称"
                  :prefix-icon="Search"
                  style="width: 200px; margin-right: 12px;"
                  @input="handleAdminSearch"
                  clearable
                />
                <el-button 
                  type="primary" 
                  :icon="Plus"
                  @click="showAddAdminDialog = true"
                >
                  添加管理员
                </el-button>
              </div>
            </div>

            <!-- 管理员表格 -->
            <div class="table-container">
              <el-table 
                :data="paginatedAdmins" 
                v-loading="adminState.loading"
                class="admin-table"
                stripe
                :header-cell-style="headerCellStyle"
              >
              <el-table-column prop="user_id" label="用户ID" width="150">
                <template #default="{ row }">
                  <div class="user-cell">
                    <el-avatar :size="32" :style="{ backgroundColor: '#3498db' }">
                      {{ row.nickname ? row.nickname[0] : row.user_id[0] }}
                    </el-avatar>
                    <span class="user-id">{{ row.user_id }}</span>
                  </div>
                </template>
              </el-table-column>
              
              <el-table-column prop="nickname" label="昵称" width="120">
                <template #default="{ row }">
                  <span v-if="row.nickname">{{ row.nickname }}</span>
                  <span v-else class="no-nickname">未设置</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="last_login" label="最后登录" width="160">
                <template #default="{ row }">
                  <span v-if="row.last_login">{{ formatTime(row.last_login) }}</span>
                  <span v-else class="no-login">从未登录</span>
                </template>
              </el-table-column>
              
              <el-table-column prop="created_at" label="创建时间" width="160">
                <template #default="{ row }">
                  {{ formatTime(row.created_at) }}
                </template>
              </el-table-column>
              
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag 
                    :type="row.is_active ? 'success' : 'info'" 
                    size="small"
                  >
                    {{ row.is_active ? '激活' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <div class="action-buttons">
                    <el-button 
                      type="primary" 
                      size="small"
                      :icon="Edit"
                      @click="editAdmin(row)"
                      :disabled="false"
                    >
                      编辑
                    </el-button>
                    <el-button 
                      :type="row.is_active ? 'warning' : 'success'" 
                      size="small"
                      :icon="row.is_active ? 'Lock' : 'Unlock'"
                      @click="toggleAdminStatus(row)"
                      :disabled="row.user_id === currentUser.id"
                    >
                      {{ row.is_active ? '禁用' : '启用' }}
                    </el-button>
                    <el-button 
                      type="danger" 
                      size="small"
                      :icon="Delete"
                      @click="deleteAdmin(row.id)"
                      :disabled="row.user_id === currentUser.id"
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
                v-model:current-page="adminState.currentPage"
                :page-size="adminState.pageSize"
                :total="filteredAdmins.length"
                layout="prev, pager, next"
                @current-change="handleAdminPageChange"
                background
              />
              <div class="pagination-info">
                共 {{ filteredAdmins.length }} 条记录，当前第 {{ adminState.currentPage }} 页
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 系统状态（管理员可见） -->
        <el-tab-pane label="系统状态" name="system" v-if="currentUser.isAdmin">
          <div class="tab-content">
            <div class="tab-header">
              <div class="tab-title">
                <h3>系统状态</h3>
                <el-tag type="success" v-if="systemState.data">
                  更新于 {{ formatTime(systemState.data.timestamp) }}
                </el-tag>
              </div>
              <div class="tab-actions">
                <el-switch
                  v-model="systemState.autoRefresh"
                  active-text="自动刷新"
                  @change="handleAutoRefreshChange"
                />
                <el-button 
                  type="primary" 
                  :icon="Refresh"
                  @click="loadSystemStatus"
                  :loading="systemState.loading"
                >
                  刷新
                </el-button>
              </div>
            </div>

            <el-row :gutter="16">
              <el-col :span="6">
                <div class="stat-item">
                  <div class="stat-number">{{ formatPercent(systemState.data?.cpu?.cpu_percent) }}</div>
                  <div class="stat-label">CPU 使用率</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-item">
                  <div class="stat-number">{{ formatPercent(systemState.data?.memory?.percent) }}</div>
                  <div class="stat-label">内存占用</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-item">
                  <div class="stat-number">{{ formatPercent(systemState.data?.swap?.percent) }}</div>
                  <div class="stat-label">交换分区</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="stat-item">
                  <div class="stat-number">{{ formatDuration(systemState.data?.system?.uptime_seconds) }}</div>
                  <div class="stat-label">已运行</div>
                </div>
              </el-col>
            </el-row>

            <el-card class="system-section-card" shadow="hover">
              <template #header>
                <div class="section-header">
                  <div class="section-title">
                    <el-icon class="section-icon"><Monitor /></el-icon>
                    <span>CPU 详情</span>
                  </div>
                  <div v-if="systemState.data?.cpu?.load_avg" class="section-meta">
                    负载: {{ systemState.data.cpu.load_avg.join(', ') }}
                  </div>
                </div>
              </template>
              <div v-if="systemState.data" class="section-content">
                <div class="progress-container">
                  <el-progress :percentage="Math.round(systemState.data.cpu.cpu_percent || 0)" 
                              :color="getProgressColor(systemState.data.cpu.cpu_percent)"
                              :stroke-width="20" />
                </div>
                <div v-if="systemState.data.cpu.per_cpu_percent && systemState.data.cpu.per_cpu_percent.length" class="cpu-cores">
                  <div v-for="(p, idx) in systemState.data.cpu.per_cpu_percent" :key="idx" class="cpu-core-item">
                    <div class="cpu-core-label">CPU {{ idx }}</div>
                    <el-progress :percentage="Math.round(p)" 
                                :color="getProgressColor(p)"
                                :stroke-width="16" />
                  </div>
                </div>
              </div>
              <div v-else v-loading="systemState.loading" class="loading-placeholder"></div>
            </el-card>

            <el-card class="system-section-card" shadow="hover">
              <template #header>
                <div class="section-header">
                  <div class="section-title">
                    <el-icon class="section-icon"><Cpu /></el-icon>
                    <span>内存使用</span>
                  </div>
                </div>
              </template>
              <div v-if="systemState.data" class="section-content">
                <div class="memory-info">
                  <el-progress :percentage="Math.round(systemState.data.memory.percent || 0)" 
                              :color="getProgressColor(systemState.data.memory.percent)"
                              :stroke-width="24"
                              :text-inside="true" />
                  <div class="memory-details">
                    <span class="memory-used">已用: {{ formatBytes(systemState.data.memory.used) }}</span>
                    <span class="memory-total">总计: {{ formatBytes(systemState.data.memory.total) }}</span>
                  </div>
                </div>
              </div>
              <div v-else v-loading="systemState.loading" class="loading-placeholder"></div>
            </el-card>

            <el-card class="system-section-card" shadow="hover">
              <template #header>
                <div class="section-header">
                  <div class="section-title">
                    <el-icon class="section-icon"><FolderOpened /></el-icon>
                    <span>磁盘状态</span>
                  </div>
                </div>
              </template>
              <div class="section-content">
                <el-table :data="systemState.data?.disks || []" 
                         v-loading="systemState.loading" 
                         stripe 
                         class="system-table">
                  <el-table-column prop="device" label="设备" width="140" />
                  <el-table-column prop="mountpoint" label="挂载点" width="120" />
                  <el-table-column label="总容量" width="120">
                    <template #default="{ row }">{{ formatBytes(row.total) }}</template>
                  </el-table-column>
                  <el-table-column label="使用情况" min-width="360">
                    <template #default="{ row }">
                      <div class="disk-usage">
                        <div class="disk-progress-wrapper">
                          <el-progress :percentage="Math.round(row.percent || 0)" 
                                      :color="getProgressColor(row.percent)"
                                      :stroke-width="32"
                                      :text-inside="true" />
                        </div>
                        <div class="disk-details">
                          <span>已用: {{ formatBytes(row.used) }}</span>
                          <span>可用: {{ formatBytes(row.free) }}</span>
                        </div>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </el-card>

            <el-card class="system-section-card" shadow="hover">
              <template #header>
                <div class="section-header">
                  <div class="section-title">
                    <el-icon class="section-icon"><Connection /></el-icon>
                    <span>网络状态</span>
                  </div>
                </div>
              </template>
              <div v-if="systemState.data" class="section-content">
                <div class="network-grid">
                  <div class="network-item">
                    <div class="network-label">发送流量</div>
                    <div class="network-value">{{ formatBytes(systemState.data.network.bytes_sent) }}</div>
                  </div>
                  <div class="network-item">
                    <div class="network-label">接收流量</div>
                    <div class="network-value">{{ formatBytes(systemState.data.network.bytes_recv) }}</div>
                  </div>
                  <div class="network-item">
                    <div class="network-label">发送包数</div>
                    <div class="network-value">{{ systemState.data.network.packets_sent.toLocaleString() }}</div>
                  </div>
                  <div class="network-item">
                    <div class="network-label">接收包数</div>
                    <div class="network-value">{{ systemState.data.network.packets_recv.toLocaleString() }}</div>
                  </div>
                </div>
              </div>
              <div v-else v-loading="systemState.loading" class="loading-placeholder"></div>
            </el-card>

            <el-card class="system-section-card" shadow="hover">
              <template #header>
                <div class="section-header">
                  <div class="section-title">
                    <el-icon class="section-icon"><Setting /></el-icon>
                    <span>进程信息</span>
                  </div>
                </div>
              </template>
              <div v-if="systemState.data" class="section-content">
                <div class="process-grid">
                  <div class="process-item">
                    <div class="process-label">进程ID</div>
                    <div class="process-value">{{ systemState.data.process.pid }}</div>
                  </div>
                  <div class="process-item">
                    <div class="process-label">CPU占用</div>
                    <div class="process-value">{{ formatPercent(systemState.data.process.cpu_percent) }}</div>
                  </div>
                  <div class="process-item">
                    <div class="process-label">物理内存</div>
                    <div class="process-value">{{ formatBytes(systemState.data.process.memory_rss) }}</div>
                  </div>
                  <div class="process-item">
                    <div class="process-label">虚拟内存</div>
                    <div class="process-value">{{ formatBytes(systemState.data.process.memory_vms) }}</div>
                  </div>
                  <div class="process-item">
                    <div class="process-label">线程数</div>
                    <div class="process-value">{{ systemState.data.process.num_threads }}</div>
                  </div>
                  <div class="process-item">
                    <div class="process-label">打开文件</div>
                    <div class="process-value">{{ systemState.data.process.open_files }}</div>
                  </div>
                </div>
              </div>
              <div v-else v-loading="systemState.loading" class="loading-placeholder"></div>
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加黑名单对话框 -->
    <el-dialog v-model="showAddDialog" title="添加黑名单" width="500px">
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="用户ID" required>
          <el-input 
            v-model="addForm.user_id" 
            placeholder="请输入用户QQ号"
          />
        </el-form-item>
        <el-form-item label="群组" required>
          <el-select 
            v-model="addForm.group_name" 
            placeholder="请选择群组"
            style="width: 100%"
          >
            <el-option 
              v-for="group in activeGroups" 
              :key="group"
              :label="group" 
              :value="group"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="拉黑原因">
          <el-input 
            v-model="addForm.reason" 
            type="textarea"
            :rows="3"
            placeholder="请输入拉黑原因（可选）"
          />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-radio-group v-model="addForm.expire_type">
            <el-radio label="permanent">永久</el-radio>
            <el-radio label="temporary">临时</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="addForm.expire_type === 'temporary'" label="有效期（小时）">
          <el-input-number 
            v-model="addForm.expires_hours" 
            :min="1" 
            :max="8760"
            placeholder="1-8760小时"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="addToBlacklist" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 用户详情对话框 -->
    <el-dialog v-model="showUserDialog" title="用户详情" width="600px">
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
          <el-descriptions-item label="空间状态">
            {{ selectedUser.qzone_status || '未知' }}
          </el-descriptions-item>
        </el-descriptions>
        
        <div class="user-stats" v-if="selectedUser.stats">
          <h4>投稿统计</h4>
          <el-row :gutter="16">
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ selectedUser.stats.total || 0 }}</div>
                <div class="stat-label">总投稿</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ selectedUser.stats.published || 0 }}</div>
                <div class="stat-label">已发布</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ selectedUser.stats.rejected || 0 }}</div>
                <div class="stat-label">被拒绝</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-item">
                <div class="stat-number">{{ selectedUser.stats.pending || 0 }}</div>
                <div class="stat-label">待审核</div>
              </div>
            </el-col>
          </el-row>
        </div>
      </div>
      <div v-loading="loadingUser" style="min-height: 200px;"></div>
    </el-dialog>

    <!-- 添加管理员对话框 -->
    <el-dialog v-model="showAddAdminDialog" title="添加管理员" width="600px">
      <el-form :model="addAdminForm" :rules="adminFormRules" ref="addAdminFormRef" label-width="100px">
        <el-form-item label="用户ID" prop="user_id">
          <el-input 
            v-model="addAdminForm.user_id" 
            placeholder="请输入用户QQ号"
          />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input 
            v-model="addAdminForm.nickname" 
            placeholder="请输入管理员昵称（可选）"
          />
        </el-form-item>
        <!-- 简化：不再选择角色与权限，默认赋予管理员 -->
        <el-form-item label="备注">
          <el-input 
            v-model="addAdminForm.notes" 
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddAdminDialog = false">取消</el-button>
        <el-button type="primary" @click="addAdmin" :loading="adminState.submitting">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑管理员对话框 -->
    <el-dialog v-model="showEditAdminDialog" title="编辑管理员" width="600px">
      <el-form :model="editAdminForm" :rules="adminFormRules" ref="editAdminFormRef" label-width="100px">
        <el-form-item label="用户ID" prop="user_id">
          <el-input 
            v-model="editAdminForm.user_id" 
            placeholder="请输入用户QQ号"
            :disabled="true"
          />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input 
            v-model="editAdminForm.nickname" 
            placeholder="请输入管理员昵称（可选）"
          />
        </el-form-item>
        <!-- 简化：不再编辑角色与权限 -->
        <el-form-item label="备注">
          <el-input 
            v-model="editAdminForm.notes" 
            type="textarea"
            :rows="3"
            placeholder="请输入备注信息（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditAdminDialog = false">取消</el-button>
        <el-button type="primary" @click="updateAdmin" :loading="adminState.submitting">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick, reactive, watch, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Plus, Refresh, Search, View, CircleCheck, Delete, Edit, Lock, Unlock,
  Monitor, Cpu, FolderOpened, Connection, Setting
} from '@element-plus/icons-vue'
import moment from 'moment'
import api from '../api'

// --- 辅助函数与组合式函数 ---

/**
 * 封装API调用，自动处理加载状态和错误提示
 * @param {Function} apiCall - 要执行的API调用函数
 * @param {object} options - 配置项
 * @param {string} [options.loadingState] - 控制加载状态的ref
 * @param {string} [options.successMessage] - 成功后的提示信息
 * @param {string} [options.errorMessage] - 失败时的默认提示信息
 */
const callApi = async (apiCall, { loadingState, successMessage, errorMessage = '操作失败' } = {}) => {
  if (loadingState) loadingState.value = true
  try {
    const response = await apiCall()
    if (successMessage) ElMessage.success(response.data.message || successMessage)
    return response.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || errorMessage)
    console.error(error)
    throw error
  } finally {
    if (loadingState) loadingState.value = false
  }
}

/**
 * 创建一个管理表格数据的组合式函数
 * @param {Array<string>} searchKeys - 用于客户端搜索的字段名数组
 * @param {number} initialPageSize - 初始每页条目数
 */
function useDataTable(searchKeys = [], initialPageSize = 20) {
  const state = reactive({
    data: [],
    loading: false,
    searchText: '',
    currentPage: 1,
    pageSize: initialPageSize,
  })

  const filteredData = computed(() => {
    if (!state.searchText) {
      return state.data
    }
    const search = state.searchText.toLowerCase()
    return state.data.filter(item =>
      searchKeys.some(key => {
        const value = item[key]
        return value && String(value).toLowerCase().includes(search)
      })
    )
  })

  const paginatedData = computed(() => {
    const start = (state.currentPage - 1) * state.pageSize
    const end = start + state.pageSize
    return filteredData.value.slice(start, end)
  })

  const handleSearch = () => {
    state.currentPage = 1
  }

  const handlePageChange = (page) => {
    state.currentPage = page
  }
  
  const setData = (data) => {
    state.data = data
  }

  return {
    state,
    filteredData,
    paginatedData,
    handleSearch,
    handlePageChange,
    setData,
  }
}

// --- 组件状态定义 ---

// 基础状态
const submitting = ref(false)
const loadingUser = ref(false)
const activeTab = ref('blacklist')
const activeGroups = ref([])

// 当前用户信息
const currentUser = reactive({
  id: '',
  role: '',
  isAdmin: computed(() => currentUser.role === 'admin')
})

// 表格状态管理
const { 
  state: blacklistState, 
  filteredData: filteredBlacklist,
  paginatedData: paginatedBlacklist,
  handleSearch: handleBlacklistSearch, 
  handlePageChange: handleBlacklistPageChange,
  setData: setBlacklistData
} = useDataTable(['user_id', 'group_name'])

const { 
  state: adminState, 
  filteredData: filteredAdmins,
  paginatedData: paginatedAdmins,
  handleSearch: handleAdminSearch, 
  handlePageChange: handleAdminPageChange,
  setData: setAdminsData
} = useDataTable(['user_id', 'nickname'])


// 系统状态
const systemState = reactive({
  data: null,
  loading: false,
  autoRefresh: true,
  intervalMs: 5000,
  lastUpdated: null,
})
let systemTimer = null

const loadSystemStatus = async () => {
  const data = await callApi(() => api.get('/management/system/status'), {
    loadingState: systemState.loading,
    errorMessage: '加载系统状态失败'
  })
  if (data) {
    systemState.data = data
    systemState.lastUpdated = data.timestamp || new Date().toISOString()
  }
}

const startAutoRefresh = () => {
  stopAutoRefresh()
  if (!systemState.autoRefresh) return
  systemTimer = setInterval(() => {
    if (activeTab.value === 'system') {
      loadSystemStatus()
    }
  }, systemState.intervalMs)
}

const stopAutoRefresh = () => {
  if (systemTimer) {
    clearInterval(systemTimer)
    systemTimer = null
  }
}

const handleAutoRefreshChange = () => {
  if (systemState.autoRefresh) startAutoRefresh()
  else stopAutoRefresh()
}

const formatBytes = (bytes) => {
  if (bytes === null || bytes === undefined) return '-'
  let val = Number(bytes)
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (val >= 1024 && i < units.length - 1) {
    val = val / 1024
    i++
  }
  const fixed = val >= 10 || i === 0 ? 0 : 1
  return `${val.toFixed(fixed)} ${units[i]}`
}

const formatPercent = (p) => {
  return typeof p === 'number' ? `${Math.round(p)}%` : '-'
}

const formatDuration = (seconds) => {
  if (seconds === null || seconds === undefined) return '-'
  const s = Number(seconds)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  const parts = []
  if (d) parts.push(`${d}天`)
  if (h) parts.push(`${h}小时`)
  if (m) parts.push(`${m}分钟`)
  return parts.join(' ') || `${s}秒`
}

const getProgressColor = (percent) => {
  const p = Number(percent) || 0
  if (p < 50) return '#67c23a'  // 绿色
  if (p < 80) return '#e6a23c'  // 橙色
  return '#f56c6c'              // 红色
}

watch(activeTab, async (val) => {
  if (val === 'system' && currentUser.isAdmin) {
    await loadSystemStatus()
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})

// 对话框相关
const showAddDialog = ref(false)
const showUserDialog = ref(false)
const showAddAdminDialog = ref(false)
const showEditAdminDialog = ref(false)
const selectedUser = ref(null)

// 表单引用
const addAdminFormRef = ref(null)
const editAdminFormRef = ref(null)

// 添加黑名单表单
const addForm = ref({
  user_id: '',
  group_name: '',
  reason: '',
  expire_type: 'permanent',
  expires_hours: 24
})

// 添加管理员表单（简化）
const addAdminForm = ref({
  user_id: '',
  nickname: '',
  notes: ''
})

// 编辑管理员表单（简化）
const editAdminForm = ref({
  id: '',
  user_id: '',
  nickname: '',
  notes: ''
})

// 表单验证规则
const adminFormRules = {
  user_id: [
    { required: true, message: '请输入用户ID', trigger: 'blur' },
    { pattern: /^\d+$/, message: '用户ID必须是数字', trigger: 'blur' }
  ]
}

// --- 计算属性与样式 ---

const headerCellStyle = computed(() => ({
  background: 'var(--el-bg-color-page)',
  color: 'var(--el-text-color-primary)',
  fontWeight: '600'
}))

// --- 数据加载方法 ---

const loadBlacklist = async () => {
  const data = await callApi(() => api.get('/management/blacklist'), { 
    loadingState: blacklistState.loading, 
    errorMessage: '加载黑名单失败' 
  })
  if (data) setBlacklistData(data)
}

const loadAdmins = async () => {
  const data = await callApi(() => api.get('/management/admins'), {
    loadingState: adminState.loading,
    errorMessage: '加载管理员列表失败'
  })
  if (data) setAdminsData(data)
}

const loadActiveGroups = async () => {
  const data = await callApi(() => api.get('/management/stats'), {
    errorMessage: '加载活跃群组失败'
  })
  if (data) activeGroups.value = data.active_groups
}

const loadCurrentUser = async () => {
  const data = await callApi(() => api.get('/auth/me'), {
    errorMessage: '获取用户信息失败'
  })
  if (data) {
    currentUser.id = data.user_id
    currentUser.role = data.role
  }
}

// --- 通用操作方法 ---

const handleActionWithConfirmation = async ({ title, message, type = 'warning', confirmButtonText = '确定', apiCall, onSuccess, successMessage }) => {
  try {
    await ElMessageBox.confirm(message, title, { type, confirmButtonText, cancelButtonText: '取消' })
    await callApi(apiCall, { successMessage })
    if (onSuccess) await onSuccess()
  } catch (error) {
    // ElMessageBox.confirm throws on cancel, which we can ignore.
    // callApi handles and logs other errors.
  }
}

// --- 黑名单管理方法 ---

const addToBlacklist = async () => {
  if (!addForm.value.user_id || !addForm.value.group_name) {
    ElMessage.warning('请填写用户ID和群组')
    return
  }
  
  const payload = {
    user_id: addForm.value.user_id,
    group_name: addForm.value.group_name,
    reason: addForm.value.reason,
    expires_hours: addForm.value.expire_type === 'temporary' ? addForm.value.expires_hours : null
  }
  
  await callApi(() => api.post('/management/blacklist', payload), {
    loadingState: submitting,
    successMessage: '添加成功',
    errorMessage: '添加失败'
  })

  showAddDialog.value = false
  resetAddForm()
  await loadBlacklist()
}

const removeFromBlacklist = (blacklistId) => {
  handleActionWithConfirmation({
    title: '确认操作',
    message: '确定要解禁该用户吗？',
    apiCall: () => api.delete(`/management/blacklist/${blacklistId}`),
    onSuccess: loadBlacklist,
    successMessage: '解禁成功'
  })
}

const deleteBlacklistEntry = (blacklistId) => {
  handleActionWithConfirmation({
    title: '确认删除',
    message: '确定要删除该黑名单记录吗？此操作不可撤销。',
    type: 'error',
    apiCall: () => api.delete(`/management/blacklist/${blacklistId}`),
    onSuccess: loadBlacklist,
    successMessage: '删除成功'
  })
}

const viewUserDetail = async (userId) => {
  showUserDialog.value = true
  selectedUser.value = null
  loadingUser.value = true
  try {
    // TODO: 待后端实现用户详情API
    await new Promise(resolve => setTimeout(resolve, 500)); // 模拟网络延迟
    selectedUser.value = {
      user_id: userId,
      nickname: '模拟用户昵称',
      qq_level: 'VIP 7',
      qzone_status: '正常',
      stats: { total: 25, published: 20, rejected: 3, pending: 2 }
    };
  } catch (error) {
    ElMessage.error('加载用户详情失败');
  } finally {
    loadingUser.value = false;
  }
}


const resetAddForm = () => {
  addForm.value = {
    user_id: '',
    group_name: '',
    reason: '',
    expire_type: 'permanent',
    expires_hours: 24
  }
}

// --- 管理员管理方法 ---

const submitAdminForm = async (formRef, apiCall) => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return // Validation failed
  }
  
  await callApi(apiCall, {
    loadingState: adminState.submitting,
    successMessage: '操作成功'
  })
  
  return true
}

const addAdmin = async () => {
  const success = await submitAdminForm(addAdminFormRef, () => api.post('/management/admins', addAdminForm.value))
  if (success) {
    showAddAdminDialog.value = false
    resetAddAdminForm()
    await loadAdmins()
  }
}

const editAdmin = (admin) => {
  editAdminForm.value = {
    id: admin.id,
    user_id: admin.user_id,
    nickname: admin.nickname || '',
    notes: admin.notes || ''
  }
  showEditAdminDialog.value = true
}

const updateAdmin = async () => {
  const success = await submitAdminForm(editAdminFormRef, () => api.put(`/management/admins/${editAdminForm.value.id}`, editAdminForm.value))
  if (success) {
    showEditAdminDialog.value = false
    await loadAdmins()
  }
}

const toggleAdminStatus = (admin) => {
  const action = admin.is_active ? '禁用' : '启用'
  handleActionWithConfirmation({
    title: '确认操作',
    message: `确定要${action}该管理员吗？`,
    apiCall: () => api.patch(`/management/admins/${admin.id}/status`, { is_active: !admin.is_active }),
    onSuccess: loadAdmins,
    successMessage: `${action}成功`
  })
}

const deleteAdmin = (adminId) => {
  handleActionWithConfirmation({
    title: '确认删除',
    message: '确定要删除该管理员吗？此操作不可撤销！',
    type: 'error',
    confirmButtonText: '确定删除',
    apiCall: () => api.delete(`/management/admins/${adminId}`),
    onSuccess: loadAdmins,
    successMessage: '删除成功'
  })
}

const resetAddAdminForm = () => {
  if (addAdminFormRef.value) {
    addAdminFormRef.value.resetFields()
  }
  addAdminForm.value = {
    user_id: '',
    nickname: '',
    notes: ''
  }
}

// --- 工具与格式化方法 ---

const formatTime = (timeStr) => {
  return timeStr ? moment(timeStr).format('YYYY-MM-DD HH:mm') : '-'
}

// 简化后不再需要角色/权限文案

const refreshCurrentTab = async () => {
  if (activeTab.value === 'blacklist') {
    await loadBlacklist()
  } else if (activeTab.value === 'admins') {
    await loadAdmins()
  } else if (activeTab.value === 'system') {
    await loadSystemStatus()
  }
}

// --- 生命周期钩子 ---

onMounted(async () => {
  await loadCurrentUser()
  await loadBlacklist()
  await loadActiveGroups()
  if (currentUser.isAdmin) {
    await loadAdmins()
  }
})
</script>

<style scoped>
.user-management {
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
  padding: 0;
}

/* 标签页样式 */
.management-tabs {
  min-height: 600px;
}

.management-tabs :deep(.el-tabs__header) {
  margin: 0;
  background: var(--xw-bg-primary);
  border-bottom: none;
  padding: 0 var(--xw-space-6);
  position: relative;
}

.management-tabs :deep(.el-tabs__header)::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--xw-space-6);
  right: var(--xw-space-6);
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--xw-border-tertiary), transparent);
}

.management-tabs :deep(.el-tabs__nav) {
  border: none;
}

.management-tabs :deep(.el-tabs__item) {
  font-size: var(--xw-text-base);
  font-weight: 500;
  padding: 0 var(--xw-space-6);
  height: 56px;
  line-height: 56px;
  color: var(--xw-text-secondary);
  transition: var(--xw-transition);
}

.management-tabs :deep(.el-tabs__item:hover) {
  color: var(--xw-primary);
}

.management-tabs :deep(.el-tabs__item.is-active) {
  color: var(--xw-primary);
  font-weight: 600;
}

.management-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  background: var(--xw-primary);
}

.management-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.management-tabs :deep(.el-tab-pane) {
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
.blacklist-table,
.admin-table {
  background: var(--xw-bg-primary);
  border-radius: var(--xw-radius-lg);
  overflow: hidden;
  border: none;
  margin: 0;
  box-shadow: none;
  min-width: 1200px; /* 设置最小宽度确保表格完整显示 */
}

.blacklist-table :deep(.el-table__header),
.admin-table :deep(.el-table__header) {
  background: linear-gradient(135deg, var(--xw-bg-tertiary), var(--xw-bg-secondary));
}

.blacklist-table :deep(.el-table__header th),
.admin-table :deep(.el-table__header th) {
  font-weight: 600;
  color: var(--xw-text-primary);
  border: none;
  position: relative;
}

.blacklist-table :deep(.el-table__header th):not(:last-child)::after,
.admin-table :deep(.el-table__header th):not(:last-child)::after {
  content: '';
  position: absolute;
  right: 0;
  top: 25%;
  bottom: 25%;
  width: 1px;
  background: var(--xw-border-quaternary);
}

.blacklist-table :deep(.el-table__row):hover,
.admin-table :deep(.el-table__row):hover {
  background: var(--xw-bg-secondary);
}

.blacklist-table :deep(.el-table__row.el-table__row--striped),
.admin-table :deep(.el-table__row.el-table__row--striped) {
  background: var(--xw-bg-secondary);
}

.blacklist-table :deep(.el-table__row.el-table__row--striped):hover,
.admin-table :deep(.el-table__row.el-table__row--striped):hover {
  background: var(--xw-bg-tertiary);
}

/* 用户单元格样式 */
.user-cell {
  display: flex;
  align-items: center;
  gap: var(--xw-space-3);
}

.user-id {
  font-weight: 500;
  color: var(--xw-text-primary);
  font-size: var(--xw-text-sm);
}

/* 权限标签样式 */
.permissions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xw-space-1);
}

/* 状态样式 */
.no-reason,
.no-operator,
.no-nickname,
.no-login {
  color: var(--xw-text-quaternary);
  font-style: italic;
  font-size: var(--xw-text-sm);
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

:deep(.el-button--warning) {
  background: linear-gradient(135deg, #e6a23c, #cf9236);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, #f56c6c, #e85656);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
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

/* 用户详情样式 */
.user-detail {
  padding: var(--xw-space-4) 0;
}

.user-stats {
  margin-top: var(--xw-space-6);
}

.user-stats h4 {
  margin: 0 0 var(--xw-space-4) 0;
  color: var(--xw-text-primary);
  font-size: var(--xw-text-base);
  font-weight: 600;
}

.stat-item {
  text-align: center;
  padding: var(--xw-space-5) var(--xw-space-4);
  background: linear-gradient(135deg, var(--xw-bg-secondary), var(--xw-bg-tertiary));
  border-radius: var(--xw-radius-lg);
  border: 1px solid var(--xw-border-tertiary);
  transition: var(--xw-transition);
}

.stat-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--xw-shadow-md);
}

.stat-number {
  font-size: var(--xw-text-2xl);
  font-weight: 700;
  color: var(--xw-primary);
  line-height: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stat-label {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  margin-top: var(--xw-space-2);
  font-weight: 500;
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

:deep(.el-checkbox-group) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--xw-space-3);
}

:deep(.el-checkbox) {
  margin-right: 0;
}

:deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: var(--xw-primary);
  border-color: var(--xw-primary);
}

:deep(.el-radio__input.is-checked .el-radio__inner) {
  background-color: var(--xw-primary);
  border-color: var(--xw-primary);
}

/* 标签样式优化 */
:deep(.el-tag) {
  border: none;
  border-radius: var(--xw-radius);
  font-weight: 500;
}

/* 选择器下拉菜单优化 */
:deep(.el-select-dropdown) {
  border: none;
  border-radius: var(--xw-radius-lg);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
}

:deep(.el-select-dropdown__item:hover) {
  background-color: var(--xw-bg-tertiary);
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

html.dark .stat-item {
  background: linear-gradient(135deg, var(--xw-bg-secondary), var(--xw-bg-tertiary));
  border: 1px solid var(--xw-border-primary);
}

html.dark .blacklist-table,
html.dark .admin-table {
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
  .user-management {
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
  .user-management {
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
  
  .management-tabs :deep(.el-tab-pane) {
    padding: var(--xw-space-4);
  }
  
  .management-tabs :deep(.el-tabs__item) {
    padding: 0 var(--xw-space-4);
    font-size: var(--xw-text-sm);
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
  
  /* 表格容器移动端适配 */
  .table-container {
    margin: 0 var(--xw-space-2);
    border-radius: var(--xw-radius);
  }

  /* 表格移动端适配 */
  .blacklist-table,
  .admin-table {
    font-size: var(--xw-text-sm);
    border-radius: var(--xw-radius);
    min-width: 800px; /* 移动端减小最小宽度 */
  }
  
  .blacklist-table :deep(.el-table__cell),
  .admin-table :deep(.el-table__cell) {
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
  
  /* 对话框移动端适配 */
  :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
    border-radius: var(--xw-radius-lg);
  }
  
  :deep(.el-dialog__header) {
    padding: var(--xw-space-4) var(--xw-space-5);
    border-radius: var(--xw-radius-lg) var(--xw-radius-lg) 0 0;
  }
  
  :deep(.el-dialog__body) {
    padding: var(--xw-space-4);
  }
  
  :deep(.el-dialog__footer) {
    padding: var(--xw-space-3) var(--xw-space-4) var(--xw-space-4);
    border-radius: 0 0 var(--xw-radius-lg) var(--xw-radius-lg);
  }
  
  .user-stats .el-row {
    gap: var(--xw-space-2);
  }
  
  .stat-item {
    padding: var(--xw-space-3) var(--xw-space-2);
    border-radius: var(--xw-radius);
  }
  
  .stat-number {
    font-size: var(--xw-text-xl);
  }
  
  .stat-label {
    font-size: var(--xw-text-xs);
  }
  
  /* 分页器移动端适配 */
  .pagination-container {
    margin-top: var(--xw-space-6);
    padding-top: var(--xw-space-4);
  }
  
  .pagination-info {
    font-size: var(--xw-text-xs);
  }
  
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .user-management {
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
  
  .main-card {
    border-radius: var(--xw-radius);
    box-shadow: var(--xw-shadow-sm);
  }
  
  .management-tabs :deep(.el-tabs__item) {
    font-size: var(--xw-text-sm);
    padding: 0 var(--xw-space-3);
    height: 48px;
    line-height: 48px;
  }
  
  .management-tabs :deep(.el-tab-pane) {
    padding: var(--xw-space-3);
  }
  
  .tab-header {
    margin-bottom: var(--xw-space-3);
    padding-bottom: var(--xw-space-3);
  }
  
  .tab-title h3 {
    font-size: var(--xw-text-base);
  }
  
  .tab-actions {
    flex-direction: column;
    width: 100%;
  }
  
  .tab-actions .el-input {
    width: 100% !important;
  }
  
  .tab-actions .el-button {
    width: 100%;
  }
  
  /* 表格容器超小屏幕适配 */
  .table-container {
    margin: 0 var(--xw-space-1);
    border-radius: var(--xw-radius-sm);
  }

  /* 表格内容更紧凑 */
  .blacklist-table :deep(.el-table__cell),
  .admin-table :deep(.el-table__cell) {
    padding: var(--xw-space-1) 2px;
    font-size: var(--xw-text-xs);
  }
  
  .blacklist-table,
  .admin-table {
    font-size: var(--xw-text-xs);
    margin: 0;
    min-width: 600px; /* 超小屏幕进一步减小最小宽度 */
  }
  
  .action-buttons .el-button {
    font-size: 10px;
    padding: 3px var(--xw-space-2);
  }
  
  .permissions {
    gap: 2px;
  }
  
  .permissions .el-tag {
    font-size: 10px;
    padding: 2px 4px;
  }
  
  /* 对话框超小屏适配 */
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 3vh auto;
    border-radius: var(--xw-radius);
  }
  
  :deep(.el-dialog__header) {
    padding: var(--xw-space-3);
    border-radius: var(--xw-radius) var(--xw-radius) 0 0;
  }
  
  :deep(.el-dialog__title) {
    font-size: var(--xw-text-base);
  }
  
  :deep(.el-dialog__body) {
    padding: var(--xw-space-3);
  }
  
  :deep(.el-dialog__footer) {
    padding: var(--xw-space-2) var(--xw-space-3) var(--xw-space-3);
    border-radius: 0 0 var(--xw-radius) var(--xw-radius);
  }
  
  :deep(.el-form-item) {
    margin-bottom: var(--xw-space-3);
  }
  
  :deep(.el-form-item__label) {
    font-size: var(--xw-text-xs);
  }
  
  :deep(.el-checkbox-group) {
    grid-template-columns: 1fr;
    gap: var(--xw-space-2);
  }
  
  .user-stats .el-col {
    margin-bottom: var(--xw-space-2);
  }
  
  .stat-item {
    padding: var(--xw-space-2);
  }
  
  .stat-number {
    font-size: var(--xw-text-lg);
  }
  
  .stat-label {
    font-size: 10px;
  }
  
  /* 分页器更紧凑 */
  .pagination-container {
    margin-top: var(--xw-space-4);
    padding-top: var(--xw-space-3);
  }
  
  .pagination-info {
    font-size: 10px;
  }
}

/* 动画效果 */
.blacklist-table,
.admin-table,
.main-card,
.page-header,
.tab-content {
  transition: var(--xw-transition-slow);
}

.stat-item,
.action-buttons .el-button,
.tab-header,
:deep(.el-tag),
:deep(.el-button) {
  transition: var(--xw-transition);
}

/* 微交互优化 */
.main-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.12);
}

.tab-content:hover .blacklist-table,
.tab-content:hover .admin-table {
  transform: translateY(-1px);
}

html.dark .main-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.35);
}

/* 系统状态面板样式 */
.system-section-card {
  background: var(--xw-bg-primary);
  border: 1px solid var(--xw-border-quaternary);
  border-radius: var(--xw-radius-xl);
  margin: var(--xw-space-4);
  overflow: hidden;
  transition: var(--xw-transition);
}

.system-section-card:hover {
  border-color: var(--xw-primary-lighter);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
}

.system-section-card :deep(.el-card__header) {
  background: linear-gradient(135deg, var(--xw-bg-secondary), var(--xw-bg-tertiary));
  border-bottom: 1px solid var(--xw-border-quaternary);
  padding: var(--xw-space-4) var(--xw-space-5);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--xw-space-2);
  font-weight: 600;
  color: var(--xw-text-primary);
  font-size: var(--xw-text-base);
}

.section-icon {
  color: var(--xw-primary);
  font-size: var(--xw-text-lg);
}

.section-meta {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
}

.section-content {
  padding: var(--xw-space-5);
}

.loading-placeholder {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* CPU 详情样式 */
.progress-container {
  margin-bottom: var(--xw-space-4);
}

.progress-container :deep(.el-progress-bar__outer) {
  height: 20px !important;
}

.progress-container :deep(.el-progress__text) {
  font-size: 14px !important;
  line-height: 20px !important;
}

.cpu-cores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xw-space-3);
  margin-top: var(--xw-space-4);
}

.cpu-core-item {
  padding: var(--xw-space-3);
  background: var(--xw-bg-secondary);
  border-radius: var(--xw-radius);
  border: 1px solid var(--xw-border-quaternary);
}

.cpu-core-label {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  margin-bottom: var(--xw-space-2);
  font-weight: 500;
}

.cpu-core-item :deep(.el-progress-bar__outer) {
  height: 16px !important;
}

.cpu-core-item :deep(.el-progress__text) {
  font-size: 12px !important;
  line-height: 16px !important;
}

/* 内存使用样式 */
.memory-info {
  text-align: center;
}

.memory-info :deep(.el-progress-bar__outer) {
  height: 24px !important;
}

.memory-info :deep(.el-progress__text) {
  font-size: 14px !important;
  line-height: 24px !important;
}

.memory-details {
  display: flex;
  justify-content: space-between;
  margin-top: var(--xw-space-3);
  padding: var(--xw-space-3);
  background: var(--xw-bg-secondary);
  border-radius: var(--xw-radius);
  border: 1px solid var(--xw-border-quaternary);
}

.memory-used,
.memory-total {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  font-weight: 500;
}

/* 磁盘状态样式 */
.system-table {
  background: transparent;
  border: none;
}

.system-table :deep(.el-table__header) {
  background: var(--xw-bg-tertiary);
}

.system-table :deep(.el-table__row:hover) {
  background: var(--xw-bg-secondary);
}

.disk-usage {
  display: flex;
  flex-direction: column;
  gap: var(--xw-space-3);
}

.disk-progress-wrapper {
  width: 100%;
  min-width: 300px;
}

.disk-progress-wrapper :deep(.el-progress) {
  width: 100%;
}

.disk-progress-wrapper :deep(.el-progress-bar) {
  padding-right: 0;
}

.disk-progress-wrapper :deep(.el-progress-bar__outer) {
  background-color: var(--xw-bg-tertiary);
  border: 1px solid var(--xw-border-quaternary);
  border-radius: var(--xw-radius);
  height: 32px;
}

.disk-progress-wrapper :deep(.el-progress-bar__inner) {
  border-radius: var(--xw-radius);
  transition: var(--xw-transition);
}

.disk-progress-wrapper :deep(.el-progress__text) {
  font-size: 14px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  line-height: 32px;
}

.disk-details {
  display: flex;
  justify-content: space-between;
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  padding: var(--xw-space-2);
  background: var(--xw-bg-secondary);
  border-radius: var(--xw-radius);
  border: 1px solid var(--xw-border-quaternary);
}

/* 网络状态样式 */
.network-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xw-space-4);
}

.network-item {
  padding: var(--xw-space-4);
  background: linear-gradient(135deg, var(--xw-bg-secondary), var(--xw-bg-tertiary));
  border-radius: var(--xw-radius-lg);
  border: 1px solid var(--xw-border-quaternary);
  text-align: center;
  transition: var(--xw-transition);
}

.network-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

.network-label {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  margin-bottom: var(--xw-space-2);
  font-weight: 500;
}

.network-value {
  font-size: var(--xw-text-lg);
  font-weight: 600;
  color: var(--xw-primary);
}

/* 进程信息样式 */
.process-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--xw-space-4);
}

.process-item {
  padding: var(--xw-space-4);
  background: linear-gradient(135deg, var(--xw-bg-secondary), var(--xw-bg-tertiary));
  border-radius: var(--xw-radius-lg);
  border: 1px solid var(--xw-border-quaternary);
  text-align: center;
  transition: var(--xw-transition);
}

.process-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

.process-label {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-secondary);
  margin-bottom: var(--xw-space-2);
  font-weight: 500;
}

.process-value {
  font-size: var(--xw-text-base);
  font-weight: 600;
  color: var(--xw-text-primary);
}

/* 深色模式优化 */
html.dark .system-section-card {
  background: var(--xw-bg-secondary);
  border-color: var(--xw-border-primary);
}

html.dark .system-section-card:hover {
  border-color: var(--xw-primary);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

html.dark .system-section-card :deep(.el-card__header) {
  background: linear-gradient(135deg, var(--xw-bg-tertiary), var(--xw-bg-quaternary));
  border-bottom-color: var(--xw-border-primary);
}

html.dark .cpu-core-item,
html.dark .memory-details,
html.dark .network-item,
html.dark .process-item {
  background: linear-gradient(135deg, var(--xw-bg-tertiary), var(--xw-bg-quaternary));
  border-color: var(--xw-border-primary);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .system-section-card {
    margin: var(--xw-space-3);
  }
  
  .section-content {
    padding: var(--xw-space-3);
  }
  
  .cpu-cores,
  .network-grid,
  .process-grid {
    grid-template-columns: 1fr;
    gap: var(--xw-space-2);
  }
  
  .memory-details {
    flex-direction: column;
    gap: var(--xw-space-2);
    text-align: center;
  }
  
  .disk-details {
    flex-direction: column;
    gap: var(--xw-space-1);
    text-align: center;
  }
  
  .disk-progress-wrapper {
    min-width: 200px;
  }
  
  .disk-progress-wrapper :deep(.el-progress-bar__outer) {
    height: 28px;
  }
  
  .disk-progress-wrapper :deep(.el-progress__text) {
    font-size: 12px;
    line-height: 28px;
  }
}

/* 打印样式优化 */
@media print {
  .page-header {
    background: none;
    color: var(--xw-text-primary);
    border: 1px solid var(--xw-border-primary);
  }
  
  .page-title h1 {
    color: var(--xw-text-primary);
  }
  
  .header-actions,
  .action-buttons,
  .pagination-container {
    display: none;
  }
  
  .blacklist-table,
  .admin-table,
  .system-table {
    box-shadow: none;
    border: 1px solid var(--xw-border-primary);
  }
  
  .system-section-card {
    box-shadow: none;
    border: 1px solid var(--xw-border-primary);
    break-inside: avoid;
    margin-bottom: var(--xw-space-4);
  }
}
</style>
