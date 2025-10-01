/**
 * 剪贴板 Composable
 * 处理复制、粘贴操作
 */

import { ref } from 'vue'
import { useNotification } from './useNotification'

export function useClipboard(options = {}) {
  const {
    showSuccessMessage = true,
    showErrorMessage = true,
    successMessage = '已复制到剪贴板',
    errorMessage = '复制失败'
  } = options

  const { success, error } = useNotification()
  
  const copied = ref(false)
  const copiedText = ref('')

  /**
   * 复制文本到剪贴板
   */
  const copy = async (text) => {
    try {
      if (!text) {
        throw new Error('没有可复制的内容')
      }

      // 优先使用现代 Clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        // 降级方案：使用 execCommand
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        document.body.appendChild(textarea)
        textarea.select()
        
        const successful = document.execCommand('copy')
        document.body.removeChild(textarea)
        
        if (!successful) {
          throw new Error('execCommand failed')
        }
      }

      copied.value = true
      copiedText.value = text

      if (showSuccessMessage) {
        success(successMessage)
      }

      // 3秒后重置状态
      setTimeout(() => {
        copied.value = false
      }, 3000)

      return true
    } catch (err) {
      console.error('Copy failed:', err)
      copied.value = false
      
      if (showErrorMessage) {
        error(errorMessage)
      }

      return false
    }
  }

  /**
   * 从剪贴板读取文本
   */
  const read = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText()
        return text
      } else {
        throw new Error('Clipboard API not supported')
      }
    } catch (err) {
      console.error('Read clipboard failed:', err)
      return null
    }
  }

  /**
   * 检查剪贴板权限
   */
  const checkPermission = async () => {
    try {
      if (navigator.permissions && navigator.permissions.query) {
        const result = await navigator.permissions.query({ name: 'clipboard-read' })
        return result.state === 'granted'
      }
      return false
    } catch (err) {
      return false
    }
  }

  return {
    copied,
    copiedText,
    copy,
    read,
    checkPermission
  }
}
