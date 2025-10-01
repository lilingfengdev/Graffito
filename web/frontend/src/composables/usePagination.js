/**
 * 分页 Composable
 * 处理分页逻辑和状态管理
 */

import { ref, computed, watch } from 'vue'

export function usePagination(options = {}) {
  const {
    defaultPageSize = 20,
    defaultCurrentPage = 1,
    pageSizes = [10, 20, 50, 100],
    onPageChange,
    onSizeChange
  } = options

  // 分页状态
  const currentPage = ref(defaultCurrentPage)
  const pageSize = ref(defaultPageSize)
  const total = ref(0)

  // 计算属性
  const totalPages = computed(() => {
    return Math.ceil(total.value / pageSize.value)
  })

  const hasMore = computed(() => {
    return currentPage.value < totalPages.value
  })

  const hasPrevious = computed(() => {
    return currentPage.value > 1
  })

  const offset = computed(() => {
    return (currentPage.value - 1) * pageSize.value
  })

  const limit = computed(() => {
    return pageSize.value
  })

  // 分页信息对象
  const paginationInfo = computed(() => ({
    current: currentPage.value,
    size: pageSize.value,
    total: total.value,
    totalPages: totalPages.value,
    hasMore: hasMore.value,
    hasPrevious: hasPrevious.value,
    offset: offset.value,
    limit: limit.value
  }))

  // 方法
  const setPage = (page) => {
    if (page < 1 || page > totalPages.value) return
    currentPage.value = page
  }

  const setPageSize = (size) => {
    pageSize.value = size
    // 重置到第一页
    currentPage.value = 1
  }

  const setTotal = (t) => {
    total.value = t
  }

  const nextPage = () => {
    if (hasMore.value) {
      currentPage.value++
    }
  }

  const previousPage = () => {
    if (hasPrevious.value) {
      currentPage.value--
    }
  }

  const firstPage = () => {
    currentPage.value = 1
  }

  const lastPage = () => {
    currentPage.value = totalPages.value
  }

  const reset = () => {
    currentPage.value = defaultCurrentPage
    pageSize.value = defaultPageSize
    total.value = 0
  }

  // 监听页码变化
  watch(currentPage, (newPage, oldPage) => {
    if (onPageChange && newPage !== oldPage) {
      onPageChange(newPage)
    }
  })

  // 监听页大小变化
  watch(pageSize, (newSize, oldSize) => {
    if (onSizeChange && newSize !== oldSize) {
      onSizeChange(newSize)
    }
  })

  return {
    // 状态
    currentPage,
    pageSize,
    total,
    pageSizes,
    
    // 计算属性
    totalPages,
    hasMore,
    hasPrevious,
    offset,
    limit,
    paginationInfo,
    
    // 方法
    setPage,
    setPageSize,
    setTotal,
    nextPage,
    previousPage,
    firstPage,
    lastPage,
    reset
  }
}
