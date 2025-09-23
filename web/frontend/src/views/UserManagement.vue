<template>
  <div class="user-management">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <div class="page-title">
          <h1>用户管理</h1>
          <div class="title-stats">
            <el-tag type="danger" size="large">黑名单 {{ blacklist.length }} 人</el-tag>
            <el-tag type="primary" size="large">管理员 {{ admins.length }} 人</el-tag>
          </div>
        </div>
        
        <div class="header-actions">
          <el-button 
            type="primary" 
            :icon="Refresh"
            @click="refreshCurrentTab"
            :loading="loading"
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
                  v-model="searchText"
                  placeholder="搜索用户ID或群组"
                  :prefix-icon="Search"
                  style="width: 200px; margin-right: 12px;"
                  @input="handleSearch"
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
            <el-table 
              :data="filteredBlacklist" 
              v-loading="loading"
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
            
            <!-- 分页 -->
            <div class="pagination-container">
              <el-pagination
                v-model:current-page="currentPage"
                :page-size="pageSize"
                :total="filteredBlacklist.length"
                layout="total, prev, pager, next, jumper"
                @current-change="handlePageChange"
                background
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- 管理员管理 -->
        <el-tab-pane label="管理员管理" name="admins" v-if="isSupperAdmin">
          <div class="tab-content">
            <div class="tab-header">
              <div class="tab-title">
                <h3>管理员列表</h3>
                <el-tag type="primary">{{ filteredAdmins.length }} 条记录</el-tag>
              </div>
              <div class="tab-actions">
                <el-input
                  v-model="adminSearchText"
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
            <el-table 
              :data="filteredAdmins" 
              v-loading="adminLoading"
              class="admin-table"
              stripe
              :header-cell-style="headerCellStyle"
            >
              <el-table-column prop="user_id" label="用户ID" width="150">
                <template #default="{ row }">
                  <div class="user-cell">
                    <el-avatar :size="32" :style="{ backgroundColor: getRoleColor(row.role) }">
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
              
              <el-table-column prop="role" label="角色" width="120">
                <template #default="{ row }">
                  <el-tag :type="getRoleTagType(row.role)" size="small">
                    {{ getRoleText(row.role) }}
                  </el-tag>
                </template>
              </el-table-column>
              
              <el-table-column prop="permissions" label="权限" min-width="200">
                <template #default="{ row }">
                  <div class="permissions">
                    <el-tag 
                      v-for="permission in row.permissions" 
                      :key="permission"
                      size="small"
                      style="margin-right: 4px; margin-bottom: 4px;"
                    >
                      {{ getPermissionText(permission) }}
                    </el-tag>
                  </div>
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
                      :disabled="row.role === 'super_admin' && row.user_id !== currentUserId"
                    >
                      编辑
                    </el-button>
                    <el-button 
                      :type="row.is_active ? 'warning' : 'success'" 
                      size="small"
                      :icon="row.is_active ? 'Lock' : 'Unlock'"
                      @click="toggleAdminStatus(row)"
                      :disabled="row.role === 'super_admin'"
                    >
                      {{ row.is_active ? '禁用' : '启用' }}
                    </el-button>
                    <el-button 
                      type="danger" 
                      size="small"
                      :icon="Delete"
                      @click="deleteAdmin(row.id)"
                      :disabled="row.role === 'super_admin' || row.user_id === currentUserId"
                    >
                      删除
                    </el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
            
            <!-- 分页 -->
            <div class="pagination-container">
              <el-pagination
                v-model:current-page="adminCurrentPage"
                :page-size="adminPageSize"
                :total="filteredAdmins.length"
                layout="total, prev, pager, next, jumper"
                @current-change="handleAdminPageChange"
                background
              />
            </div>
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
        <el-form-item label="角色" prop="role">
          <el-select 
            v-model="addAdminForm.role" 
            placeholder="请选择管理员角色"
            style="width: 100%"
          >
            <el-option label="普通管理员" value="admin" />
            <el-option label="高级管理员" value="senior_admin" />
            <el-option label="超级管理员" value="super_admin" v-if="currentUserRole === 'super_admin'" />
          </el-select>
        </el-form-item>
        <el-form-item label="权限" prop="permissions">
          <el-checkbox-group v-model="addAdminForm.permissions">
            <el-checkbox label="user_management">用户管理</el-checkbox>
            <el-checkbox label="content_review">内容审核</el-checkbox>
            <el-checkbox label="system_config">系统配置</el-checkbox>
            <el-checkbox label="data_export">数据导出</el-checkbox>
            <el-checkbox label="log_view">日志查看</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
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
        <el-button type="primary" @click="addAdmin" :loading="adminSubmitting">
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
        <el-form-item label="角色" prop="role">
          <el-select 
            v-model="editAdminForm.role" 
            placeholder="请选择管理员角色"
            style="width: 100%"
            :disabled="editAdminForm.user_id === currentUserId || editAdminForm.role === 'super_admin'"
          >
            <el-option label="普通管理员" value="admin" />
            <el-option label="高级管理员" value="senior_admin" />
            <el-option label="超级管理员" value="super_admin" v-if="currentUserRole === 'super_admin'" />
          </el-select>
        </el-form-item>
        <el-form-item label="权限" prop="permissions">
          <el-checkbox-group v-model="editAdminForm.permissions" :disabled="editAdminForm.role === 'super_admin'">
            <el-checkbox label="user_management">用户管理</el-checkbox>
            <el-checkbox label="content_review">内容审核</el-checkbox>
            <el-checkbox label="system_config">系统配置</el-checkbox>
            <el-checkbox label="data_export">数据导出</el-checkbox>
            <el-checkbox label="log_view">日志查看</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
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
        <el-button type="primary" @click="updateAdmin" :loading="adminSubmitting">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Plus, Refresh, Search, View, CircleCheck, Delete, Edit, Lock, Unlock
} from '@element-plus/icons-vue'
import moment from 'moment'
import api from '../api'

// 基础状态
const loading = ref(false)
const submitting = ref(false)
const loadingUser = ref(false)
const activeTab = ref('blacklist')

// 黑名单相关
const blacklist = ref([])
const activeGroups = ref([])
const searchText = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

// 管理员相关
const admins = ref([])
const adminLoading = ref(false)
const adminSubmitting = ref(false)
const adminSearchText = ref('')
const adminCurrentPage = ref(1)
const adminPageSize = ref(20)

// 当前用户信息
const currentUserId = ref('')
const currentUserRole = ref('')
const isSupperAdmin = ref(false)

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

// 添加管理员表单
const addAdminForm = ref({
  user_id: '',
  nickname: '',
  role: 'admin',
  permissions: ['user_management'],
  notes: ''
})

// 编辑管理员表单
const editAdminForm = ref({
  id: '',
  user_id: '',
  nickname: '',
  role: '',
  permissions: [],
  notes: ''
})

// 表单验证规则
const adminFormRules = {
  user_id: [
    { required: true, message: '请输入用户ID', trigger: 'blur' },
    { pattern: /^\d+$/, message: '用户ID必须是数字', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ],
  permissions: [
    { type: 'array', min: 1, message: '请至少选择一个权限', trigger: 'change' }
  ]
}

// 计算属性
const filteredBlacklist = computed(() => {
  if (!searchText.value) {
    return blacklist.value
  }
  
  const search = searchText.value.toLowerCase()
  return blacklist.value.filter(item => 
    item.user_id.toLowerCase().includes(search) ||
    item.group_name.toLowerCase().includes(search)
  )
})

const filteredAdmins = computed(() => {
  if (!adminSearchText.value) {
    return admins.value
  }
  
  const search = adminSearchText.value.toLowerCase()
  return admins.value.filter(item => 
    item.user_id.toLowerCase().includes(search) ||
    (item.nickname && item.nickname.toLowerCase().includes(search))
  )
})

// 样式相关
const headerCellStyle = computed(() => ({
  background: 'var(--el-bg-color-page)',
  color: 'var(--el-text-color-primary)',
  fontWeight: '600'
}))

// 方法
const loadBlacklist = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/management/blacklist')
    blacklist.value = data
  } catch (error) {
    ElMessage.error('加载黑名单失败')
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

const addToBlacklist = async () => {
  if (!addForm.value.user_id || !addForm.value.group_name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  
  submitting.value = true
  try {
    const data = {
      user_id: addForm.value.user_id,
      group_name: addForm.value.group_name,
      reason: addForm.value.reason
    }
    
    if (addForm.value.expire_type === 'temporary') {
      data.expires_hours = addForm.value.expires_hours
    }
    
    const result = await api.post('/management/blacklist', data)
    ElMessage.success(result.data.message || '添加成功')
    showAddDialog.value = false
    resetAddForm()
    await loadBlacklist()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加失败')
  } finally {
    submitting.value = false
  }
}

const removeFromBlacklist = async (blacklistId) => {
  try {
    await ElMessageBox.confirm('确定要解禁该用户吗？', '确认操作', {
      type: 'warning'
    })
    
    const result = await api.delete(`/management/blacklist/${blacklistId}`)
    ElMessage.success(result.data.message || '解禁成功')
    await loadBlacklist()
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '解禁失败')
    }
  }
}

const deleteBlacklistEntry = async (blacklistId) => {
  try {
    await ElMessageBox.confirm('确定要删除该黑名单记录吗？', '确认删除', {
      type: 'warning'
    })
    
    const result = await api.delete(`/management/blacklist/${blacklistId}`)
    ElMessage.success(result.data.message || '删除成功')
    await loadBlacklist()
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const viewUserDetail = async (userId) => {
  loadingUser.value = true
  showUserDialog.value = true
  
  try {
    // 这里可以调用用户详情API，现在先模拟数据
    selectedUser.value = {
      user_id: userId,
      nickname: '用户昵称',
      qq_level: 'VIP 6',
      qzone_status: '正常',
      stats: {
        total: 15,
        published: 12,
        rejected: 2,
        pending: 1
      }
    }
  } catch (error) {
    ElMessage.error('加载用户详情失败')
  } finally {
    loadingUser.value = false
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

const handleSearch = () => {
  currentPage.value = 1
}

const handlePageChange = (page) => {
  currentPage.value = page
}

const formatTime = (timeStr) => {
  return moment(timeStr).format('YYYY-MM-DD HH:mm')
}

// 管理员相关方法
const loadAdmins = async () => {
  adminLoading.value = true
  try {
    const { data } = await api.get('/management/admins')
    admins.value = data
  } catch (error) {
    ElMessage.error('加载管理员列表失败')
    console.error(error)
  } finally {
    adminLoading.value = false
  }
}

const addAdmin = async () => {
  if (!addAdminFormRef.value) return
  
  try {
    await addAdminFormRef.value.validate()
  } catch {
    return
  }
  
  adminSubmitting.value = true
  try {
    const result = await api.post('/management/admins', addAdminForm.value)
    ElMessage.success(result.data.message || '添加管理员成功')
    showAddAdminDialog.value = false
    resetAddAdminForm()
    await loadAdmins()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '添加管理员失败')
  } finally {
    adminSubmitting.value = false
  }
}

const editAdmin = (admin) => {
  editAdminForm.value = {
    id: admin.id,
    user_id: admin.user_id,
    nickname: admin.nickname || '',
    role: admin.role,
    permissions: [...admin.permissions],
    notes: admin.notes || ''
  }
  showEditAdminDialog.value = true
}

const updateAdmin = async () => {
  if (!editAdminFormRef.value) return
  
  try {
    await editAdminFormRef.value.validate()
  } catch {
    return
  }
  
  adminSubmitting.value = true
  try {
    const result = await api.put(`/management/admins/${editAdminForm.value.id}`, editAdminForm.value)
    ElMessage.success(result.data.message || '更新管理员成功')
    showEditAdminDialog.value = false
    await loadAdmins()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '更新管理员失败')
  } finally {
    adminSubmitting.value = false
  }
}

const toggleAdminStatus = async (admin) => {
  try {
    const action = admin.is_active ? '禁用' : '启用'
    await ElMessageBox.confirm(`确定要${action}该管理员吗？`, '确认操作', {
      type: 'warning'
    })
    
    const result = await api.patch(`/management/admins/${admin.id}/status`, {
      is_active: !admin.is_active
    })
    ElMessage.success(result.data.message || `${action}成功`)
    await loadAdmins()
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '操作失败')
    }
  }
}

const deleteAdmin = async (adminId) => {
  try {
    await ElMessageBox.confirm('确定要删除该管理员吗？此操作不可撤销！', '确认删除', {
      type: 'error',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消'
    })
    
    const result = await api.delete(`/management/admins/${adminId}`)
    ElMessage.success(result.data.message || '删除成功')
    await loadAdmins()
  } catch (error) {
    if (error.dismiss !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

const resetAddAdminForm = () => {
  addAdminForm.value = {
    user_id: '',
    nickname: '',
    role: 'admin',
    permissions: ['user_management'],
    notes: ''
  }
  if (addAdminFormRef.value) {
    addAdminFormRef.value.resetFields()
  }
}

const handleAdminSearch = () => {
  adminCurrentPage.value = 1
}

const handleAdminPageChange = (page) => {
  adminCurrentPage.value = page
}

// 工具方法
const getRoleColor = (role) => {
  const colors = {
    'super_admin': '#e74c3c',
    'senior_admin': '#f39c12',
    'admin': '#3498db'
  }
  return colors[role] || '#95a5a6'
}

const getRoleTagType = (role) => {
  const types = {
    'super_admin': 'danger',
    'senior_admin': 'warning',
    'admin': 'primary'
  }
  return types[role] || 'info'
}

const getRoleText = (role) => {
  const texts = {
    'super_admin': '超级管理员',
    'senior_admin': '高级管理员',
    'admin': '普通管理员'
  }
  return texts[role] || '未知'
}

const getPermissionText = (permission) => {
  const texts = {
    'user_management': '用户管理',
    'content_review': '内容审核',
    'system_config': '系统配置',
    'data_export': '数据导出',
    'log_view': '日志查看'
  }
  return texts[permission] || permission
}

const refreshCurrentTab = async () => {
  if (activeTab.value === 'blacklist') {
    await loadBlacklist()
  } else if (activeTab.value === 'admins') {
    await loadAdmins()
  }
}

// 获取当前用户信息
const loadCurrentUser = async () => {
  try {
    const { data } = await api.get('/auth/me')
    currentUserId.value = data.user_id
    currentUserRole.value = data.role
    isSupperAdmin.value = data.role === 'super_admin'
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

onMounted(async () => {
  await loadCurrentUser()
  await loadBlacklist()
  await loadActiveGroups()
  if (isSupperAdmin.value) {
    await loadAdmins()
  }
})
</script>

<style scoped>
.user-management {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  background: var(--el-bg-color-page);
  min-height: 100vh;
}

/* 页面头部样式 */
.page-header {
  background: linear-gradient(135deg, var(--el-color-primary), var(--el-color-primary-light-5));
  border-radius: 16px;
  padding: 24px 32px;
  margin-bottom: 24px;
  color: white;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.page-title h1 {
  margin: 0;
  font-size: 32px;
  font-weight: 700;
  color: white;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.title-stats {
  display: flex;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 主卡片样式 */
.main-card {
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  border: 1px solid var(--el-border-color-light);
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
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 24px;
}

.management-tabs :deep(.el-tabs__nav) {
  border: none;
}

.management-tabs :deep(.el-tabs__item) {
  font-size: 16px;
  font-weight: 500;
  padding: 0 24px;
  height: 56px;
  line-height: 56px;
  color: var(--el-text-color-regular);
}

.management-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 600;
}

.management-tabs :deep(.el-tabs__active-bar) {
  height: 3px;
  background: var(--el-color-primary);
}

.management-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.management-tabs :deep(.el-tab-pane) {
  padding: 24px;
}

/* Tab内容样式 */
.tab-content {
  background: var(--el-bg-color);
}

.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid var(--el-border-color-extra-light);
}

.tab-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.tab-title h3 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 20px;
  font-weight: 600;
}

.tab-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 表格样式 */
.blacklist-table,
.admin-table {
  background: var(--el-bg-color);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.blacklist-table :deep(.el-table__header),
.admin-table :deep(.el-table__header) {
  background: var(--el-fill-color-light);
}

.blacklist-table :deep(.el-table__row):hover,
.admin-table :deep(.el-table__row):hover {
  background: var(--el-fill-color-extra-light);
}

.blacklist-table :deep(.el-table__row.el-table__row--striped),
.admin-table :deep(.el-table__row.el-table__row--striped) {
  background: var(--el-fill-color-blank);
}

.blacklist-table :deep(.el-table__row.el-table__row--striped):hover,
.admin-table :deep(.el-table__row.el-table__row--striped):hover {
  background: var(--el-fill-color-extra-light);
}

/* 用户单元格样式 */
.user-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-id {
  font-weight: 500;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

/* 权限标签样式 */
.permissions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* 状态样式 */
.no-reason,
.no-operator,
.no-nickname,
.no-login {
  color: var(--el-text-color-placeholder);
  font-style: italic;
  font-size: 13px;
}

/* 操作按钮样式 */
.action-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.action-buttons .el-button {
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 6px;
}

/* 分页器样式 */
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--el-border-color-extra-light);
}

/* 用户详情样式 */
.user-detail {
  padding: 16px 0;
}

.user-stats {
  margin-top: 24px;
}

.user-stats h4 {
  margin: 0 0 16px 0;
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 600;
}

.stat-item {
  text-align: center;
  padding: 20px 16px;
  background: linear-gradient(135deg, var(--el-fill-color-light), var(--el-fill-color-extra-light));
  border-radius: 12px;
  border: 1px solid var(--el-border-color-extra-light);
  transition: all 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
  color: var(--el-color-primary);
  line-height: 1;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.stat-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
  font-weight: 500;
}

/* 对话框样式优化 */
:deep(.el-dialog) {
  border-radius: 16px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
}

:deep(.el-dialog__header) {
  background: linear-gradient(135deg, var(--el-color-primary), var(--el-color-primary-light-3));
  color: white;
  padding: 20px 24px;
  border-radius: 16px 16px 0 0;
}

:deep(.el-dialog__title) {
  color: white;
  font-weight: 600;
  font-size: 18px;
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__footer) {
  padding: 16px 24px 24px;
  background: var(--el-fill-color-extra-light);
  border-radius: 0 0 16px 16px;
}

/* 表单样式优化 */
:deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
}

:deep(.el-select .el-input__wrapper) {
  border-radius: 8px;
}

:deep(.el-checkbox-group) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
}

:deep(.el-checkbox) {
  margin-right: 0;
}

/* 深色模式优化 */
:root[class*="dark"] .page-header {
  background: linear-gradient(135deg, var(--el-color-primary-dark-2), var(--el-color-primary));
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

:root[class*="dark"] .main-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

:root[class*="dark"] .stat-item {
  background: linear-gradient(135deg, var(--el-fill-color), var(--el-fill-color-light));
  border: 1px solid var(--el-border-color);
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .user-management {
    padding: 16px;
  }
  
  .page-header {
    padding: 20px 24px;
  }
  
  .page-title h1 {
    font-size: 28px;
  }
}

@media (max-width: 768px) {
  .user-management {
    padding: 12px;
  }
  
  .page-header {
    padding: 16px 20px;
    margin-bottom: 16px;
  }
  
  .header-content {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .page-title h1 {
    font-size: 24px;
  }
  
  .title-stats {
    justify-content: center;
  }
  
  .header-actions {
    justify-content: center;
  }
  
  .management-tabs :deep(.el-tab-pane) {
    padding: 16px;
  }
  
  .tab-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .tab-actions {
    justify-content: center;
  }
  
  /* 表格移动端适配 */
  .blacklist-table,
  .admin-table {
    font-size: 13px;
  }
  
  .blacklist-table :deep(.el-table__cell),
  .admin-table :deep(.el-table__cell) {
    padding: 8px 4px;
  }
  
  .user-id {
    font-size: 12px;
  }
  
  .action-buttons {
    flex-direction: column;
    gap: 4px;
  }
  
  .action-buttons .el-button {
    font-size: 11px;
    padding: 4px 8px;
  }
  
  /* 对话框移动端适配 */
  :deep(.el-dialog) {
    width: 90% !important;
    margin: 5vh auto;
  }
  
  .user-stats .el-row {
    gap: 8px;
  }
  
  .stat-item {
    padding: 12px 8px;
  }
  
  .stat-number {
    font-size: 20px;
  }
  
  .stat-label {
    font-size: 12px;
  }
  
  /* 分页器移动端适配 */
  :deep(.el-pagination .el-pagination__total),
  :deep(.el-pagination .el-pagination__jump) {
    display: none;
  }
}

/* 超小屏幕适配 */
@media (max-width: 480px) {
  .user-management {
    padding: 8px;
  }
  
  .page-header {
    padding: 12px 16px;
  }
  
  .page-title h1 {
    font-size: 20px;
  }
  
  .management-tabs :deep(.el-tabs__item) {
    font-size: 14px;
    padding: 0 12px;
  }
  
  .management-tabs :deep(.el-tab-pane) {
    padding: 12px;
  }
  
  .tab-title h3 {
    font-size: 16px;
  }
  
  /* 表格内容更紧凑 */
  .blacklist-table :deep(.el-table__cell),
  .admin-table :deep(.el-table__cell) {
    padding: 6px 2px;
  }
  
  .blacklist-table,
  .admin-table {
    font-size: 11px;
  }
  
  .action-buttons .el-button {
    font-size: 10px;
    padding: 3px 6px;
  }
  
  /* 对话框超小屏适配 */
  :deep(.el-dialog) {
    width: 95% !important;
    margin: 3vh auto;
  }
  
  :deep(.el-dialog__body) {
    padding: 16px;
  }
  
  :deep(.el-form-item) {
    margin-bottom: 16px;
  }
  
  :deep(.el-checkbox-group) {
    grid-template-columns: 1fr;
  }
  
  .user-stats .el-col {
    margin-bottom: 8px;
  }
  
  .stat-item {
    padding: 8px 6px;
  }
  
  .stat-number {
    font-size: 16px;
  }
  
  .stat-label {
    font-size: 10px;
  }
}

/* 动画效果 */
.blacklist-table,
.admin-table,
.main-card,
.page-header {
  transition: all 0.3s ease;
}

.action-buttons .el-button {
  transition: all 0.2s ease;
}

.action-buttons .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
</style>
