/**
 * XWall 组件系统
 * ===============
 * 统一的组件库，配合设计系统使用
 */

// Vue 单文件组件导入
import SecureImage from './SecureImage.vue'
import SecureAvatar from './SecureAvatar.vue'
import XwImageViewer from './XwImageViewer.vue'
import XwUpload from './XwUpload.vue'

// 基础组件
const XwButton = {
  name: 'XwButton',
  props: {
    variant: {
      type: String,
      default: 'primary',
      validator: (value) => ['primary', 'secondary', 'success', 'warning', 'danger', 'info'].includes(value)
    },
    size: {
      type: String,
      default: 'md',
      validator: (value) => ['xs', 'sm', 'md', 'lg', 'xl'].includes(value)
    },
    disabled: Boolean,
    loading: Boolean,
    block: Boolean,
    icon: String,
    iconPosition: {
      type: String,
      default: 'left'
    },
    gradient: Boolean
  },
  template: `
    <button 
      :class="buttonClasses" 
      :disabled="disabled || loading"
      @click="$emit('click', $event)"
    >
      <el-icon v-if="loading" class="xw-btn-loading">
        <Loading />
      </el-icon>
      <template v-else>
        <el-icon v-if="icon && iconPosition === 'left'" :class="iconClasses">
          <component :is="icon" />
        </el-icon>
        <span v-if="$slots.default" class="xw-btn-text">
          <slot />
        </span>
        <el-icon v-if="icon && iconPosition === 'right'" :class="iconClasses">
          <component :is="icon" />
        </el-icon>
      </template>
    </button>
  `,
  computed: {
    buttonClasses() {
      return [
        'xw-btn',
        `xw-btn-${this.variant}`,
        `xw-btn-${this.size}`,
        {
          'xw-btn-disabled': this.disabled,
          'xw-btn-loading': this.loading,
          'xw-btn-block': this.block,
          'xw-btn-gradient': this.gradient
        }
      ]
    },
    iconClasses() {
      return [
        'xw-btn-icon',
        {
          'xw-btn-icon-only': !this.$slots.default
        }
      ]
    }
  },
  emits: ['click']
}

// 卡片组件
const XwCard = {
  name: 'XwCard',
  props: {
    shadow: {
      type: String,
      default: 'sm',
      validator: (value) => ['none', 'xs', 'sm', 'md', 'lg', 'xl', '2xl'].includes(value)
    },
    padding: {
      type: String,
      default: '6'
    },
    hoverable: Boolean,
    glass: Boolean
  },
  template: `
    <div :class="cardClasses">
      <div v-if="$slots.header" class="xw-card-header">
        <slot name="header" />
      </div>
      <div class="xw-card-body" :style="bodyStyle">
        <slot />
      </div>
      <div v-if="$slots.footer" class="xw-card-footer">
        <slot name="footer" />
      </div>
    </div>
  `,
  computed: {
    cardClasses() {
      return [
        'xw-card',
        `xw-shadow-${this.shadow}`,
        {
          'xw-hover-lift': this.hoverable,
          'xw-glass': this.glass
        }
      ]
    },
    bodyStyle() {
      return {
        padding: `var(--xw-space-${this.padding})`
      }
    }
  }
}

// 统计卡片组件
const XwStatCard = {
  name: 'XwStatCard',
  props: {
    title: String,
    value: [String, Number],
    icon: String,
    color: String,
    trend: String,
    trendValue: [String, Number]
  },
  template: `
    <div class="xw-stat-card xw-hover-lift">
      <div class="xw-stat-icon" :style="{ color }">
        <el-icon :size="32">
          <component :is="icon" />
        </el-icon>
      </div>
      <div class="xw-stat-content">
        <div class="xw-stat-value">{{ value }}</div>
        <div class="xw-stat-label">{{ title }}</div>
        <div v-if="trend" class="xw-stat-trend" :class="trendClass">
          <el-icon class="xw-stat-trend-icon">
            <component :is="trendIcon" />
          </el-icon>
          <span>{{ trendValue }}</span>
        </div>
      </div>
    </div>
  `,
  computed: {
    trendClass() {
      return {
        'xw-trend-up': this.trend === 'up',
        'xw-trend-down': this.trend === 'down',
        'xw-trend-stable': this.trend === 'stable'
      }
    },
    trendIcon() {
      switch (this.trend) {
        case 'up': return 'TrendCharts'
        case 'down': return 'Bottom'
        case 'stable': return 'Minus'
        default: return ''
      }
    }
  }
}

// 状态标签组件
const XwStatusTag = {
  name: 'XwStatusTag',
  props: {
    status: String,
    size: {
      type: String,
      default: 'small'
    }
  },
  template: `
    <el-tag :type="tagType" :size="size" class="xw-status-tag">
      <div class="xw-status-dot" :class="dotClass"></div>
      <span>{{ statusText }}</span>
    </el-tag>
  `,
  computed: {
    tagType() {
      const typeMap = {
        'pending': 'warning',
        'processing': 'warning', 
        'waiting': 'warning',
        'approved': 'success',
        'published': 'primary',
        'rejected': 'danger',
        'draft': 'info'
      }
      return typeMap[this.status] || 'info'
    },
    statusText() {
      const textMap = {
        'pending': '待处理',
        'processing': '处理中',
        'waiting': '等待审核',
        'approved': '已通过',
        'published': '已发布',
        'rejected': '已拒绝',
        'draft': '草稿'
      }
      return textMap[this.status] || this.status
    },
    dotClass() {
      return `xw-status-dot-${this.tagType}`
    }
  }
}

// 用户头像组件
const XwUserAvatar = {
  name: 'XwUserAvatar',
  props: {
    user: Object,
    size: {
      type: String,
      default: 'md'
    },
    showName: Boolean,
    showStatus: Boolean
  },
  template: `
    <div class="xw-user-avatar" :class="avatarClasses">
      <div class="xw-avatar" :class="sizeClass">
        <img v-if="user?.avatar" :src="user.avatar" :alt="displayName" />
        <span v-else>{{ userInitial }}</span>
        <div v-if="showStatus && user?.online" class="xw-user-status"></div>
      </div>
      <div v-if="showName" class="xw-user-info">
        <div class="xw-user-name">{{ displayName }}</div>
        <div v-if="user?.role" class="xw-user-role">{{ user.role }}</div>
      </div>
    </div>
  `,
  computed: {
    avatarClasses() {
      return [
        'xw-flex',
        'xw-items-center',
        'xw-gap-3',
        {
          'xw-flex-col': this.showName && this.size === 'xl'
        }
      ]
    },
    sizeClass() {
      return `xw-avatar-${this.size}`
    },
    displayName() {
      return this.user?.display_name || this.user?.nickname || this.user?.username || this.user?.user_id || '用户'
    },
    userInitial() {
      return this.displayName[0]?.toUpperCase() || 'U'
    }
  }
}

// 空状态组件
const XwEmpty = {
  name: 'XwEmpty',
  props: {
    icon: String,
    title: String,
    description: String,
    actionText: String
  },
  template: `
    <div class="xw-empty">
      <div class="xw-empty-icon">
        <el-icon :size="48" color="var(--xw-text-quaternary)">
          <component :is="icon || 'Box'" />
        </el-icon>
      </div>
      <div class="xw-empty-content">
        <h3 class="xw-empty-title">{{ title || '暂无数据' }}</h3>
        <p v-if="description" class="xw-empty-description">{{ description }}</p>
      </div>
      <div v-if="$slots.action || actionText" class="xw-empty-action">
        <slot name="action">
          <xw-button v-if="actionText" variant="primary" @click="$emit('action')">
            {{ actionText }}
          </xw-button>
        </slot>
      </div>
    </div>
  `,
  emits: ['action']
}

// 加载骨架组件
const XwSkeleton = {
  name: 'XwSkeleton',
  props: {
    rows: {
      type: Number,
      default: 3
    },
    avatar: Boolean,
    loading: {
      type: Boolean,
      default: true
    }
  },
  template: `
    <div v-if="loading" class="xw-skeleton-container">
      <div v-if="avatar" class="xw-skeleton xw-skeleton-avatar"></div>
      <div class="xw-skeleton-content">
        <div 
          v-for="row in rows" 
          :key="row"
          class="xw-skeleton xw-skeleton-row"
          :style="{ width: getRowWidth(row) }"
        ></div>
      </div>
    </div>
    <slot v-else />
  `,
  methods: {
    getRowWidth(row) {
      const widths = ['100%', '85%', '70%', '90%', '60%']
      return widths[(row - 1) % widths.length]
    }
  }
}

// 确认对话框组件
const XwConfirm = {
  name: 'XwConfirm',
  props: {
    modelValue: Boolean,
    title: String,
    message: String,
    type: {
      type: String,
      default: 'warning'
    },
    confirmText: {
      type: String,
      default: '确定'
    },
    cancelText: {
      type: String,
      default: '取消'
    }
  },
  template: `
    <el-dialog 
      :model-value="modelValue"
      :title="title"
      width="400px"
      class="xw-confirm-dialog"
      @update:model-value="$emit('update:modelValue', $event)"
    >
      <div class="xw-confirm-content">
        <div class="xw-confirm-icon">
          <el-icon :size="32" :color="iconColor">
            <component :is="iconComponent" />
          </el-icon>
        </div>
        <div class="xw-confirm-message">
          {{ message }}
        </div>
      </div>
      <template #footer>
        <div class="xw-confirm-actions">
          <xw-button variant="secondary" @click="handleCancel">
            {{ cancelText }}
          </xw-button>
          <xw-button :variant="type" @click="handleConfirm">
            {{ confirmText }}
          </xw-button>
        </div>
      </template>
    </el-dialog>
  `,
  computed: {
    iconComponent() {
      const iconMap = {
        'warning': 'Warning',
        'danger': 'Delete',
        'success': 'Check',
        'info': 'InfoFilled'
      }
      return iconMap[this.type] || 'Warning'
    },
    iconColor() {
      const colorMap = {
        'warning': 'var(--xw-warning)',
        'danger': 'var(--xw-danger)',
        'success': 'var(--xw-success)',
        'info': 'var(--xw-info)'
      }
      return colorMap[this.type] || 'var(--xw-warning)'
    }
  },
  methods: {
    handleConfirm() {
      this.$emit('confirm')
      this.$emit('update:modelValue', false)
    },
    handleCancel() {
      this.$emit('cancel')
      this.$emit('update:modelValue', false)
    }
  },
  emits: ['update:modelValue', 'confirm', 'cancel']
}

// 工具提示组件
const XwTooltip = {
  name: 'XwTooltip',
  props: {
    content: String,
    placement: {
      type: String,
      default: 'top'
    },
    disabled: Boolean
  },
  template: `
    <el-tooltip 
      :content="content"
      :placement="placement"
      :disabled="disabled"
      effect="dark"
      :popper-class="'xw-tooltip'"
    >
      <slot />
    </el-tooltip>
  `
}

// 面包屑组件
const XwBreadcrumb = {
  name: 'XwBreadcrumb',
  props: {
    items: Array,
    separator: {
      type: String,
      default: '>'
    }
  },
  template: `
    <nav class="xw-breadcrumb">
      <template v-for="(item, index) in items" :key="index">
        <div class="xw-breadcrumb-item">
          <router-link 
            v-if="item.to && index < items.length - 1"
            :to="item.to"
            class="xw-breadcrumb-link"
          >
            {{ item.text }}
          </router-link>
          <span v-else class="xw-breadcrumb-current">
            {{ item.text }}
          </span>
        </div>
        <span 
          v-if="index < items.length - 1" 
          class="xw-breadcrumb-separator"
        >
          {{ separator }}
        </span>
      </template>
    </nav>
  `
}

// 页面头部组件
const XwPageHeader = {
  name: 'XwPageHeader',
  props: {
    title: String,
    subtitle: String,
    showBack: Boolean,
    breadcrumbs: Array
  },
  template: `
    <div class="xw-page-header">
      <div class="xw-page-header-content">
        <div class="xw-page-header-main">
          <div v-if="showBack" class="xw-page-header-back">
            <xw-button 
              variant="secondary" 
              icon="ArrowLeft"
              @click="$router.back()"
            >
              返回
            </xw-button>
          </div>
          <div class="xw-page-header-text">
            <h1 class="xw-page-title">{{ title }}</h1>
            <p v-if="subtitle" class="xw-page-subtitle">{{ subtitle }}</p>
          </div>
        </div>
        <div v-if="$slots.actions" class="xw-page-header-actions">
          <slot name="actions" />
        </div>
      </div>
      <xw-breadcrumb 
        v-if="breadcrumbs && breadcrumbs.length" 
        :items="breadcrumbs"
      />
    </div>
  `
}

// 搜索输入框组件
const XwSearchInput = {
  name: 'XwSearchInput',
  props: {
    modelValue: String,
    placeholder: {
      type: String,
      default: '搜索...'
    },
    size: {
      type: String,
      default: 'md'
    },
    clearable: {
      type: Boolean,
      default: true
    }
  },
  template: `
    <div class="xw-search-input" :class="sizeClass">
      <el-input
        :model-value="modelValue"
        :placeholder="placeholder"
        :clearable="clearable"
        prefix-icon="Search"
        class="xw-input"
        @update:model-value="$emit('update:modelValue', $event)"
        @input="handleInput"
        @clear="handleClear"
      />
    </div>
  `,
  computed: {
    sizeClass() {
      return `xw-search-${this.size}`
    }
  },
  methods: {
    handleInput(value) {
      this.$emit('input', value)
      this.$emit('search', value)
    },
    handleClear() {
      this.$emit('clear')
      this.$emit('search', '')
    }
  },
  emits: ['update:modelValue', 'input', 'search', 'clear']
}

// 操作按钮组组件
const XwActionGroup = {
  name: 'XwActionGroup',
  props: {
    actions: Array,
    size: {
      type: String,
      default: 'sm'
    },
    direction: {
      type: String,
      default: 'horizontal',
      validator: (value) => ['horizontal', 'vertical'].includes(value)
    }
  },
  template: `
    <div class="xw-action-group" :class="groupClasses">
      <template v-for="action in actions" :key="action.key">
        <xw-button
          v-if="action.type === 'button'"
          :variant="action.variant || 'primary'"
          :size="size"
          :icon="action.icon"
          :disabled="action.disabled"
          :loading="action.loading"
          @click="$emit('action', action.key, action)"
        >
          {{ action.text }}
        </xw-button>
        <el-dropdown
          v-else-if="action.type === 'dropdown'"
          @command="(cmd) => $emit('action', cmd, action)"
        >
          <xw-button
            :variant="action.variant || 'primary'"
            :size="size"
            :icon="action.icon"
          >
            {{ action.text }}
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </xw-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item
                v-for="item in action.items"
                :key="item.key"
                :command="item.key"
                :disabled="item.disabled"
                :divided="item.divided"
                :style="item.danger ? 'color: var(--xw-danger)' : ''"
              >
                <el-icon v-if="item.icon">
                  <component :is="item.icon" />
                </el-icon>
                {{ item.text }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </div>
  `,
  computed: {
    groupClasses() {
      return [
        'xw-flex',
        'xw-gap-2',
        {
          'xw-flex-col': this.direction === 'vertical',
          'xw-flex-row': this.direction === 'horizontal'
        }
      ]
    }
  },
  emits: ['action']
}

// 图表容器组件
const XwChart = {
  name: 'XwChart',
  props: {
    title: String,
    height: {
      type: [String, Number],
      default: 300
    },
    loading: Boolean
  },
  template: `
    <div class="xw-chart-container">
      <div v-if="title" class="xw-chart-header">
        <h3 class="xw-chart-title">{{ title }}</h3>
        <slot name="actions" />
      </div>
      <div 
        class="xw-chart-wrapper" 
        :style="{ height: chartHeight }"
        v-loading="loading"
      >
        <slot />
      </div>
    </div>
  `,
  computed: {
    chartHeight() {
      return typeof this.height === 'number' ? `${this.height}px` : this.height
    }
  }
}

// 数据表格组件
const XwDataTable = {
  name: 'XwDataTable',
  props: {
    data: Array,
    columns: Array,
    loading: Boolean,
    pagination: Object,
    selection: Boolean,
    stripe: {
      type: Boolean,
      default: true
    }
  },
  template: `
    <div class="xw-data-table">
      <el-table
        :data="data"
        v-loading="loading"
        :stripe="stripe"
        class="xw-table"
        :header-cell-style="headerCellStyle"
        @selection-change="$emit('selection-change', $event)"
        @row-click="$emit('row-click', $event)"
      >
        <el-table-column
          v-if="selection"
          type="selection"
          width="55"
        />
        <el-table-column
          v-for="column in columns"
          :key="column.prop"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          :min-width="column.minWidth"
          :fixed="column.fixed"
          :sortable="column.sortable"
        >
          <template v-if="column.slot" #default="scope">
            <slot :name="column.slot" :row="scope.row" :column="column" :$index="scope.$index" />
          </template>
        </el-table-column>
      </el-table>
      
      <div v-if="pagination" class="xw-table-pagination">
        <el-pagination
          :current-page="pagination.current"
          :page-size="pagination.size"
          :total="pagination.total"
          :layout="paginationLayout"
          @current-change="$emit('page-change', $event)"
          @size-change="$emit('size-change', $event)"
          background
        />
      </div>
    </div>
  `,
  computed: {
    headerCellStyle() {
      return {
        background: 'var(--xw-bg-secondary)',
        color: 'var(--xw-text-primary)',
        fontWeight: '600'
      }
    },
    paginationLayout() {
      // 移动端简化分页布局
      return window.innerWidth <= 768 
        ? 'prev, pager, next'
        : 'total, sizes, prev, pager, next, jumper'
    }
  },
  emits: ['selection-change', 'row-click', 'page-change', 'size-change']
}

// 过滤器组件
const XwFilter = {
  name: 'XwFilter',
  props: {
    filters: Array,
    modelValue: Object
  },
  template: `
    <div class="xw-filter">
      <div class="xw-filter-items">
        <template v-for="filter in filters" :key="filter.key">
          <div class="xw-filter-item">
            <label class="xw-filter-label">{{ filter.label }}</label>
            
            <!-- 选择器 -->
            <el-select
              v-if="filter.type === 'select'"
              :model-value="modelValue[filter.key]"
              :placeholder="filter.placeholder"
              :clearable="filter.clearable"
              @update:model-value="updateFilter(filter.key, $event)"
            >
              <el-option
                v-for="option in filter.options"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            
            <!-- 日期选择器 -->
            <el-date-picker
              v-else-if="filter.type === 'date'"
              :model-value="modelValue[filter.key]"
              type="daterange"
              :placeholder="filter.placeholder"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @update:model-value="updateFilter(filter.key, $event)"
            />
            
            <!-- 输入框 -->
            <el-input
              v-else-if="filter.type === 'input'"
              :model-value="modelValue[filter.key]"
              :placeholder="filter.placeholder"
              :clearable="filter.clearable"
              @update:model-value="updateFilter(filter.key, $event)"
            />
          </div>
        </template>
      </div>
      
      <div class="xw-filter-actions">
        <xw-button variant="primary" icon="Search" @click="$emit('search')">
          搜索
        </xw-button>
        <xw-button variant="secondary" icon="Refresh" @click="handleReset">
          重置
        </xw-button>
      </div>
    </div>
  `,
  methods: {
    updateFilter(key, value) {
      const newValue = { ...this.modelValue, [key]: value }
      this.$emit('update:modelValue', newValue)
    },
    handleReset() {
      const resetValue = {}
      this.filters.forEach(filter => {
        resetValue[filter.key] = filter.default || ''
      })
      this.$emit('update:modelValue', resetValue)
      this.$emit('reset')
    }
  },
  emits: ['update:modelValue', 'search', 'reset']
}

// 通知工具函数
const createNotificationMethods = () => {
  return {
    success(message, options = {}) {
      import('element-plus').then(({ ElMessage }) => {
        ElMessage.success({
          message,
          duration: 3000,
          showClose: true,
          customClass: 'xw-message xw-message-success',
          ...options
        })
      })
    },
    error(message, options = {}) {
      import('element-plus').then(({ ElMessage }) => {
        ElMessage.error({
          message,
          duration: 5000,
          showClose: true,
          customClass: 'xw-message xw-message-error',
          ...options
        })
      })
    },
    warning(message, options = {}) {
      import('element-plus').then(({ ElMessage }) => {
        ElMessage.warning({
          message,
          duration: 4000,
          showClose: true,
          customClass: 'xw-message xw-message-warning',
          ...options
        })
      })
    },
    info(message, options = {}) {
      import('element-plus').then(({ ElMessage }) => {
        ElMessage.info({
          message,
          duration: 3000,
          showClose: true,
          customClass: 'xw-message xw-message-info',
          ...options
        })
      })
    }
  }
}

// 组件样式
const componentStyles = `
/* ===== 组件特定样式 ===== */

/* 按钮组件样式 */
.xw-btn-loading {
  animation: xw-spin 1s linear infinite;
}

.xw-btn-block {
  width: 100%;
}

.xw-btn-gradient {
  background: linear-gradient(135deg, var(--xw-primary), var(--xw-primary-light));
  background-size: 200% 200%;
  animation: xw-gradient-shift 3s ease infinite;
}

@keyframes xw-gradient-shift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

/* 状态标签样式 */
.xw-status-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--xw-space-1);
}

.xw-status-tag .xw-status-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--xw-radius-full);
  margin-right: 0;
}

/* 用户头像样式 */
.xw-user-avatar .xw-avatar {
  position: relative;
}

.xw-user-status {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 8px;
  height: 8px;
  background: var(--xw-success);
  border: 2px solid var(--xw-bg-primary);
  border-radius: var(--xw-radius-full);
}

.xw-user-info {
  flex: 1;
  min-width: 0;
}

.xw-user-name {
  font-weight: var(--xw-font-medium);
  color: var(--xw-text-primary);
  font-size: var(--xw-text-sm);
}

.xw-user-role {
  font-size: var(--xw-text-xs);
  color: var(--xw-text-tertiary);
}

/* 空状态样式 */
.xw-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--xw-space-16) var(--xw-space-8);
  text-align: center;
}

.xw-empty-icon {
  margin-bottom: var(--xw-space-6);
  opacity: 0.6;
}

.xw-empty-title {
  margin: 0 0 var(--xw-space-3) 0;
  font-size: var(--xw-text-lg);
  font-weight: var(--xw-font-semibold);
  color: var(--xw-text-primary);
}

.xw-empty-description {
  margin: 0 0 var(--xw-space-6) 0;
  color: var(--xw-text-secondary);
  font-size: var(--xw-text-sm);
  line-height: var(--xw-leading-relaxed);
}

.xw-empty-action {
  margin-top: var(--xw-space-4);
}

/* 骨架屏样式 */
.xw-skeleton-container {
  display: flex;
  gap: var(--xw-space-4);
  padding: var(--xw-space-4);
}

.xw-skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--xw-radius-full);
  flex-shrink: 0;
}

.xw-skeleton-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--xw-space-3);
}

.xw-skeleton-row {
  height: 16px;
  border-radius: var(--xw-radius);
}

/* 确认对话框样式 */
.xw-confirm-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--xw-space-6);
}

.xw-confirm-icon {
  margin-bottom: var(--xw-space-4);
}

.xw-confirm-message {
  font-size: var(--xw-text-base);
  color: var(--xw-text-primary);
  line-height: var(--xw-leading-relaxed);
}

.xw-confirm-actions {
  display: flex;
  gap: var(--xw-space-3);
  justify-content: center;
}

/* 页面头部样式 */
.xw-page-header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--xw-space-4);
}

.xw-page-header-main {
  display: flex;
  align-items: center;
  gap: var(--xw-space-4);
  flex: 1;
}

.xw-page-header-text {
  flex: 1;
}

.xw-page-header-actions {
  display: flex;
  gap: var(--xw-space-3);
  flex-wrap: wrap;
}

/* 过滤器样式 */
.xw-filter {
  background: var(--xw-card-bg);
  border: 1px solid var(--xw-card-border);
  border-radius: var(--xw-radius-xl);
  padding: var(--xw-space-5);
  margin-bottom: var(--xw-space-6);
}

.xw-filter-items {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xw-space-4);
  margin-bottom: var(--xw-space-5);
}

.xw-filter-item {
  display: flex;
  flex-direction: column;
  gap: var(--xw-space-2);
}

.xw-filter-label {
  font-size: var(--xw-text-sm);
  font-weight: var(--xw-font-medium);
  color: var(--xw-text-primary);
}

.xw-filter-actions {
  display: flex;
  gap: var(--xw-space-3);
  justify-content: flex-end;
}

/* 图表容器样式 */
.xw-chart-container {
  background: var(--xw-card-bg);
  border: 1px solid var(--xw-card-border);
  border-radius: var(--xw-radius-xl);
  padding: var(--xw-space-6);
  box-shadow: var(--xw-shadow-sm);
}

.xw-chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--xw-space-5);
  padding-bottom: var(--xw-space-4);
  border-bottom: 1px solid var(--xw-border-primary);
}

.xw-chart-title {
  margin: 0;
  font-size: var(--xw-text-lg);
  font-weight: var(--xw-font-semibold);
  color: var(--xw-text-primary);
}

.xw-chart-wrapper {
  position: relative;
  width: 100%;
}

/* 数据表格样式 */
.xw-data-table .xw-table {
  border-radius: var(--xw-radius-lg);
  overflow: hidden;
}

.xw-table-pagination {
  display: flex;
  justify-content: center;
  margin-top: var(--xw-space-6);
  padding-top: var(--xw-space-4);
  border-top: 1px solid var(--xw-border-primary);
}

/* 搜索输入框样式 */
.xw-search-input {
  position: relative;
}

.xw-search-sm .xw-input {
  padding: var(--xw-space-2) var(--xw-space-3);
  font-size: var(--xw-text-sm);
}

.xw-search-lg .xw-input {
  padding: var(--xw-space-4) var(--xw-space-5);
  font-size: var(--xw-text-lg);
}

/* 工具提示样式 */
.xw-tooltip {
  background: var(--xw-bg-primary);
  color: var(--xw-text-primary);
  border: 1px solid var(--xw-border-primary);
  border-radius: var(--xw-radius-lg);
  box-shadow: var(--xw-shadow-lg);
  backdrop-filter: blur(10px);
}

/* 消息通知样式 */
.xw-message {
  border-radius: var(--xw-radius-lg);
  backdrop-filter: blur(10px);
  border: 1px solid transparent;
  box-shadow: var(--xw-shadow-lg);
}

.xw-message-success {
  background: var(--xw-success);
  border-color: var(--xw-success-light);
}

.xw-message-error {
  background: var(--xw-danger);
  border-color: var(--xw-danger-light);
}

.xw-message-warning {
  background: var(--xw-warning);
  border-color: var(--xw-warning-light);
}

.xw-message-info {
  background: var(--xw-info);
  border-color: var(--xw-info-light);
}

/* ===== 响应式适配 ===== */
@media (max-width: 768px) {
  .xw-filter-items {
    grid-template-columns: 1fr;
  }
  
  .xw-filter-actions {
    justify-content: stretch;
  }
  
  .xw-filter-actions .xw-btn {
    flex: 1;
  }
  
  .xw-page-header-content {
    flex-direction: column;
    gap: var(--xw-space-4);
    align-items: stretch;
  }
  
  .xw-page-header-actions {
    justify-content: stretch;
  }
  
  .xw-chart-header {
    flex-direction: column;
    gap: var(--xw-space-3);
    align-items: stretch;
  }
  
  .xw-confirm-actions {
    flex-direction: column;
  }
  
  .xw-confirm-actions .xw-btn {
    width: 100%;
  }
}
`

// 将样式注入到页面
if (typeof document !== 'undefined') {
  const styleElement = document.createElement('style')
  styleElement.textContent = componentStyles
  document.head.appendChild(styleElement)
}

// 导出所有组件
const components = {
  XwButton,
  XwCard,
  XwStatCard,
  XwStatusTag,
  XwUserAvatar,
  XwEmpty,
  XwSkeleton,
  XwConfirm,
  XwTooltip,
  XwBreadcrumb,
  XwPageHeader,
  XwSearchInput,
  XwActionGroup,
  XwChart,
  XwDataTable,
  XwFilter
}

// Vue 插件安装函数
export default {
  install(app) {
    // 注册所有组件
    Object.entries(components).forEach(([name, component]) => {
      app.component(name, component)
    })
    
    // 提供全局通知方法
    app.config.globalProperties.$xwNotify = createNotificationMethods()
    
    // 提供全局工具函数
    app.config.globalProperties.$xwUtils = {
      formatTime: (time) => {
        if (!time) return '-'
        return new Date(time).toLocaleString('zh-CN')
      },
      formatBytes: (bytes) => {
        if (!bytes) return '0 B'
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(1024))
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
      },
      truncate: (text, length = 50) => {
        if (!text || text.length <= length) return text
        return text.substring(0, length) + '...'
      },
      debounce: (func, wait) => {
        let timeout
        return function executedFunction(...args) {
          const later = () => {
            clearTimeout(timeout)
            func(...args)
          }
          clearTimeout(timeout)
          timeout = setTimeout(later, wait)
        }
      }
    }
  }
}

// 同时导出单个组件供按需引入
export {
  XwButton,
  XwCard,
  XwStatCard,
  XwStatusTag,
  XwUserAvatar,
  XwEmpty,
  XwSkeleton,
  XwConfirm,
  XwTooltip,
  XwBreadcrumb,
  XwPageHeader,
  XwSearchInput,
  XwActionGroup,
  XwChart,
  XwDataTable,
  XwFilter,
  createNotificationMethods,
  // Vue 单文件组件
  SecureImage,
  SecureAvatar,
  XwImageViewer,
  XwUpload
}
