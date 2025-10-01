/**
 * 防抖 Composable
 * 处理防抖和节流逻辑
 */

import { ref, watch, onUnmounted } from 'vue'

/**
 * 防抖函数
 * @param {Function} fn - 要防抖的函数
 * @param {Number} delay - 延迟时间（毫秒）
 */
export function useDebounce(fn, delay = 300) {
  let timeoutId = null

  const debouncedFn = (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    
    timeoutId = setTimeout(() => {
      fn(...args)
      timeoutId = null
    }, delay)
  }

  const cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  const flush = (...args) => {
    cancel()
    fn(...args)
  }

  onUnmounted(() => {
    cancel()
  })

  return {
    debouncedFn,
    cancel,
    flush
  }
}

/**
 * 防抖 Ref
 * 返回一个防抖后的响应式值
 */
export function useDebouncedRef(value, delay = 300) {
  const debouncedValue = ref(value)
  let timeoutId = null

  const updateValue = (newValue) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }

    timeoutId = setTimeout(() => {
      debouncedValue.value = newValue
    }, delay)
  }

  watch(() => value, (newValue) => {
    updateValue(newValue)
  }, { immediate: true })

  onUnmounted(() => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
  })

  return debouncedValue
}

/**
 * 节流函数
 * @param {Function} fn - 要节流的函数
 * @param {Number} delay - 延迟时间（毫秒）
 */
export function useThrottle(fn, delay = 300) {
  let lastRun = 0
  let timeoutId = null

  const throttledFn = (...args) => {
    const now = Date.now()

    if (now - lastRun >= delay) {
      fn(...args)
      lastRun = now
    } else {
      if (timeoutId) {
        clearTimeout(timeoutId)
      }
      
      timeoutId = setTimeout(() => {
        fn(...args)
        lastRun = Date.now()
      }, delay - (now - lastRun))
    }
  }

  const cancel = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutId = null
    }
  }

  onUnmounted(() => {
    cancel()
  })

  return {
    throttledFn,
    cancel
  }
}

/**
 * 搜索防抖 Hook
 * 专门用于搜索输入的防抖处理
 */
export function useSearchDebounce(searchFn, delay = 500) {
  const searchText = ref('')
  const isSearching = ref(false)
  const { debouncedFn } = useDebounce(async (text) => {
    isSearching.value = true
    try {
      await searchFn(text)
    } finally {
      isSearching.value = false
    }
  }, delay)

  const handleSearch = (text) => {
    searchText.value = text
    debouncedFn(text)
  }

  return {
    searchText,
    isSearching,
    handleSearch
  }
}
