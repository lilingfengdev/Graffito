/**
 * SSE 通知 Composable
 * 
 * 管理 SSE 实时通知的接收和处理
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { ElNotification, ElMessage } from 'element-plus'
import sseService from '../services/sse'

export function useSSENotifications() {
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const lastError = ref(null)
  
  // 存储取消监听的函数
  const unsubscribers = []

  /**
   * 初始化 SSE 连接和通知监听
   */
  const initialize = () => {
    // 连接 SSE
    sseService.connect()
    
    // 同步状态
    isConnected.value = sseService.connected.value
    isConnecting.value = sseService.connecting.value
    lastError.value = sseService.error.value

    // 监听连接事件
    const unsubConnected = sseService.on('connected', () => {
      isConnected.value = true
      isConnecting.value = false
      console.log('[Notifications] SSE connected')
    })
    unsubscribers.push(unsubConnected)

    // 监听投稿审批通知
    const unsubApproved = sseService.on('submission_approved', (data) => {
      ElNotification({
        title: '投稿已通过',
        message: `投稿 #${data.submission_id} 已通过审核`,
        type: 'success',
        duration: 4000
      })
      
      // 触发自定义事件，让页面可以刷新数据
      window.dispatchEvent(new CustomEvent('submission-updated', { 
        detail: { 
          submissionId: data.submission_id,
          action: 'approved'
        }
      }))
    })
    unsubscribers.push(unsubApproved)

    // 监听投稿拒绝通知
    const unsubRejected = sseService.on('submission_rejected', (data) => {
      ElNotification({
        title: '投稿已拒绝',
        message: `投稿 #${data.submission_id} 已被拒绝`,
        type: 'warning',
        duration: 4000
      })
      
      window.dispatchEvent(new CustomEvent('submission-updated', { 
        detail: { 
          submissionId: data.submission_id,
          action: 'rejected'
        }
      }))
    })
    unsubscribers.push(unsubRejected)

    // 监听投稿发布通知
    const unsubPublished = sseService.on('submission_published', (data) => {
      ElNotification({
        title: '投稿已发布',
        message: `投稿 #${data.submission_id} 已成功发布`,
        type: 'success',
        duration: 4000
      })
      
      window.dispatchEvent(new CustomEvent('submission-updated', { 
        detail: { 
          submissionId: data.submission_id,
          action: 'published'
        }
      }))
    })
    unsubscribers.push(unsubPublished)

    // 监听新投稿通知
    const unsubNew = sseService.on('new_submission', (data) => {
      ElNotification({
        title: '新投稿',
        message: `收到新的投稿 #${data.submission_id}`,
        type: 'info',
        duration: 5000
      })
      
      window.dispatchEvent(new CustomEvent('new-submission', { 
        detail: { 
          submissionId: data.submission_id
        }
      }))
    })
    unsubscribers.push(unsubNew)

    // 监听系统通知
    const unsubSystem = sseService.on('system_notification', (data) => {
      const notifType = data.level || 'info'
      ElNotification({
        title: data.title || '系统通知',
        message: data.message || '',
        type: notifType,
        duration: data.duration || 5000
      })
    })
    unsubscribers.push(unsubSystem)
  }

  /**
   * 清理资源
   */
  const cleanup = () => {
    // 取消所有监听
    unsubscribers.forEach(unsub => unsub())
    unsubscribers.length = 0
    
    // 断开 SSE 连接
    sseService.disconnect()
  }

  /**
   * 手动重连
   */
  const reconnect = () => {
    cleanup()
    initialize()
  }

  return {
    // 状态
    isConnected,
    isConnecting,
    lastError,
    
    // 方法
    initialize,
    cleanup,
    reconnect
  }
}

