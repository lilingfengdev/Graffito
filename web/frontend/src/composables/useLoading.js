/**
 * 加载状态 Composable
 * 管理加载状态和全屏加载遮罩
 */

import { ref, watch } from 'vue'
import { ElLoading } from 'element-plus'

export function useLoading(initialValue = false) {
  const loading = ref(initialValue)
  let loadingInstance = null

  /**
   * 开始加载
   */
  const startLoading = (options = {}) => {
    loading.value = true
    
    if (options.fullscreen) {
      loadingInstance = ElLoading.service({
        lock: true,
        text: options.text || '加载中...',
        background: 'rgba(0, 0, 0, 0.7)',
        customClass: 'xw-loading-fullscreen',
        ...options
      })
    }
  }

  /**
   * 停止加载
   */
  const stopLoading = () => {
    loading.value = false
    
    if (loadingInstance) {
      loadingInstance.close()
      loadingInstance = null
    }
  }

  /**
   * 切换加载状态
   */
  const toggleLoading = () => {
    if (loading.value) {
      stopLoading()
    } else {
      startLoading()
    }
  }

  /**
   * 异步操作包装器
   * @param {Function} fn - 异步函数
   * @param {Object} options - 加载选项
   */
  const withLoading = async (fn, options = {}) => {
    try {
      startLoading(options)
      const result = await fn()
      return result
    } finally {
      stopLoading()
    }
  }

  // 监听loading状态，自动管理全屏加载
  watch(loading, (newVal, oldVal) => {
    if (newVal && !loadingInstance) {
      // 如果设置了loading为true但没有实例，可能需要创建
      // 这里不自动创建，避免意外的全屏遮罩
    } else if (!newVal && loadingInstance) {
      loadingInstance.close()
      loadingInstance = null
    }
  })

  return {
    loading,
    startLoading,
    stopLoading,
    toggleLoading,
    withLoading
  }
}

/**
 * 批量加载状态管理
 */
export function useMultipleLoading() {
  const loadingStates = ref({})

  const setLoading = (key, value) => {
    loadingStates.value[key] = value
  }

  const isLoading = (key) => {
    return loadingStates.value[key] || false
  }

  const isAnyLoading = () => {
    return Object.values(loadingStates.value).some(v => v === true)
  }

  const resetAll = () => {
    loadingStates.value = {}
  }

  return {
    loadingStates,
    setLoading,
    isLoading,
    isAnyLoading,
    resetAll
  }
}
