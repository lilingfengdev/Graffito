/**
 * 安全图片加载 Composable
 * 使用 fetch + Authorization header 方式加载受保护的图片资源
 */
import { ref, onUnmounted } from 'vue'
import axios from 'axios'

/**
 * 创建一个安全的图片 URL
 * @param {string} url - 原始图片 URL
 * @returns {Promise<string>} Blob URL
 */
async function createSecureImageUrl(url) {
  if (!url) return ''
  
  // data URI 直接返回
  if (url.startsWith('data:')) {
    return url
  }
  
  // 判断是否需要认证的资源（包含 /data/ 路径）
  const isDataPath = url.includes('/data/')
  
  // 外部链接（不包含 /data/ 路径）直接返回
  if (url.startsWith('http') && !isDataPath) {
    return url
  }
  
  // 不需要认证的资源直接返回
  if (!isDataPath) {
    return url
  }
  
  try {
    const token = localStorage.getItem('token')
    if (!token) {
      console.warn('[SecureImage] No token found, fallback to direct URL')
      return url
    }
    
    // 使用 fetch + Authorization header 请求图片
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (!response.ok) {
      throw new Error(`Failed to fetch image: ${response.status}`)
    }
    
    // 转换为 Blob
    const blob = await response.blob()
    
    // 创建 Blob URL
    const blobUrl = URL.createObjectURL(blob)
    return blobUrl
    
  } catch (error) {
    console.error('[SecureImage] Failed to load image:', url, error)
    // 降级到 URL 参数方式（兼容性）
    const sep = url.includes('?') ? '&' : '?'
    const token = localStorage.getItem('token')
    return token ? `${url}${sep}access_token=${encodeURIComponent(token)}` : url
  }
}

/**
 * 使用安全图片 URL 的 Composable
 * @param {string|Ref<string>} imageUrl - 图片 URL（可以是 ref 或普通字符串）
 * @returns {{ secureUrl: Ref<string>, loading: Ref<boolean>, error: Ref<Error|null>, refresh: Function }}
 */
export function useSecureImage(imageUrl) {
  const secureUrl = ref('')
  const loading = ref(false)
  const error = ref(null)
  const blobUrls = ref([]) // 追踪创建的 Blob URLs，用于清理
  
  const loadImage = async (url) => {
    if (!url) {
      secureUrl.value = ''
      return
    }
    
    loading.value = true
    error.value = null
    
    try {
      const resolvedUrl = await createSecureImageUrl(url)
      
      // 如果是新创建的 Blob URL，记录下来用于后续清理
      if (resolvedUrl.startsWith('blob:')) {
        blobUrls.value.push(resolvedUrl)
      }
      
      secureUrl.value = resolvedUrl
    } catch (err) {
      error.value = err
      console.error('[useSecureImage] Error:', err)
    } finally {
      loading.value = false
    }
  }
  
  // 刷新图片
  const refresh = () => {
    const url = typeof imageUrl === 'object' ? imageUrl.value : imageUrl
    return loadImage(url)
  }
  
  // 初始加载
  if (imageUrl) {
    const url = typeof imageUrl === 'object' ? imageUrl.value : imageUrl
    loadImage(url)
  }
  
  // 清理 Blob URLs
  onUnmounted(() => {
    blobUrls.value.forEach(url => {
      try {
        URL.revokeObjectURL(url)
      } catch (e) {
        // ignore
      }
    })
    blobUrls.value = []
  })
  
  return {
    secureUrl,
    loading,
    error,
    refresh
  }
}

/**
 * 批量加载安全图片 URLs
 * @param {Array<string>} urls - 图片 URL 数组
 * @returns {{ secureUrls: Ref<Array<string>>, loading: Ref<boolean>, refresh: Function }}
 */
export function useSecureImages(urls) {
  const secureUrls = ref([])
  const loading = ref(false)
  const blobUrls = ref([])
  
  const loadImages = async (imageUrls) => {
    if (!imageUrls || imageUrls.length === 0) {
      secureUrls.value = []
      return
    }
    
    loading.value = true
    
    try {
      // 并发加载所有图片
      const promises = imageUrls.map(url => createSecureImageUrl(url))
      const results = await Promise.all(promises)
      
      // 记录 Blob URLs
      results.forEach(url => {
        if (url && url.startsWith('blob:')) {
          blobUrls.value.push(url)
        }
      })
      
      secureUrls.value = results
    } catch (err) {
      console.error('[useSecureImages] Error:', err)
    } finally {
      loading.value = false
    }
  }
  
  // 刷新所有图片
  const refresh = () => {
    return loadImages(urls)
  }
  
  // 初始加载
  if (urls && urls.length > 0) {
    loadImages(urls)
  }
  
  // 清理 Blob URLs
  onUnmounted(() => {
    blobUrls.value.forEach(url => {
      try {
        URL.revokeObjectURL(url)
      } catch (e) {
        // ignore
      }
    })
    blobUrls.value = []
  })
  
  return {
    secureUrls,
    loading,
    refresh
  }
}

/**
 * 创建单个安全图片 URL（不带响应式）
 * @param {string} url - 图片 URL
 * @returns {Promise<string>} 安全的图片 URL
 */
export async function getSecureImageUrl(url) {
  return await createSecureImageUrl(url)
}

export default {
  useSecureImage,
  useSecureImages,
  getSecureImageUrl
}

