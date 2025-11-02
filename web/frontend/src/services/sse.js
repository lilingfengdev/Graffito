/**
 * SSE (Server-Sent Events) 服务
 * 
 * 提供与后端实时推送的连接管理
 */

import { ref, computed } from 'vue'
import api from '../api'

class SSEService {
  constructor() {
    this.eventSource = null
    this.reconnectTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 3000 // 3 seconds
    this.listeners = new Map()
    
    // 状态管理
    this.connected = ref(false)
    this.connecting = ref(false)
    this.error = ref(null)
  }

  /**
   * 连接到 SSE 流
   * 注意：EventSource API 原生不支持自定义 headers，因此通过 URL 参数传递 token
   */
  async connect() {
    // 如果已连接或正在连接，则不重复连接
    if (this.connected.value || this.connecting.value) {
      console.log('[SSE] Already connected or connecting')
      return
    }

    try {
      this.connecting.value = true
      this.error.value = null

      // 获取认证 token
      const token = localStorage.getItem('access_token') || localStorage.getItem('token')
      if (!token) {
        throw new Error('No authentication token found')
      }

      // 构建 SSE URL
      // 注意：EventSource API 不支持自定义 headers，只能通过 URL 参数传递 token
      // 这是 EventSource 的限制，无法使用 Authorization header
      const baseURL = api.defaults.baseURL || '/api'
      const url = `${baseURL}/events/stream?token=${encodeURIComponent(token)}`

      console.log('[SSE] Connecting to:', url)

      // 创建 EventSource
      this.eventSource = new EventSource(url, {
        withCredentials: true
      })

      // 连接成功
      this.eventSource.onopen = () => {
        console.log('[SSE] Connection established')
        this.connected.value = true
        this.connecting.value = false
        this.reconnectAttempts = 0
        this.error.value = null
      }

      // 接收消息
      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('[SSE] Message received:', data)
          this.handleMessage(data)
        } catch (err) {
          console.error('[SSE] Failed to parse message:', err)
        }
      }

      // 连接错误
      this.eventSource.onerror = (error) => {
        console.error('[SSE] Connection error:', error)
        this.connected.value = false
        this.connecting.value = false
        this.error.value = 'Connection failed'
        
        // 关闭当前连接
        if (this.eventSource) {
          this.eventSource.close()
          this.eventSource = null
        }

        // 尝试重连
        this.scheduleReconnect()
      }

    } catch (err) {
      console.error('[SSE] Failed to connect:', err)
      this.connecting.value = false
      this.error.value = err.message
      this.scheduleReconnect()
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    console.log('[SSE] Disconnecting...')
    
    // 清除重连定时器
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    // 关闭连接
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }

    this.connected.value = false
    this.connecting.value = false
    this.reconnectAttempts = 0
  }

  /**
   * 安排重连
   */
  scheduleReconnect() {
    // 清除现有的重连定时器
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }

    // 检查重连次数
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SSE] Max reconnect attempts reached')
      this.error.value = 'Failed to reconnect after multiple attempts'
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1)
    
    console.log(`[SSE] Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)
    
    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }

  /**
   * 处理收到的消息
   */
  handleMessage(message) {
    const { type, data, timestamp } = message

    // 触发对应类型的监听器
    if (this.listeners.has(type)) {
      const callbacks = this.listeners.get(type)
      callbacks.forEach(callback => {
        try {
          callback(data, timestamp)
        } catch (err) {
          console.error(`[SSE] Error in listener for ${type}:`, err)
        }
      })
    }

    // 触发通用监听器
    if (this.listeners.has('*')) {
      const callbacks = this.listeners.get('*')
      callbacks.forEach(callback => {
        try {
          callback({ type, data, timestamp })
        } catch (err) {
          console.error('[SSE] Error in universal listener:', err)
        }
      })
    }
  }

  /**
   * 添加事件监听器
   * @param {string} eventType - 事件类型，使用 '*' 监听所有事件
   * @param {Function} callback - 回调函数
   * @returns {Function} 取消监听的函数
   */
  on(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set())
    }
    
    this.listeners.get(eventType).add(callback)

    // 返回取消监听的函数
    return () => {
      const callbacks = this.listeners.get(eventType)
      if (callbacks) {
        callbacks.delete(callback)
        if (callbacks.size === 0) {
          this.listeners.delete(eventType)
        }
      }
    }
  }

  /**
   * 移除事件监听器
   */
  off(eventType, callback) {
    const callbacks = this.listeners.get(eventType)
    if (callbacks) {
      callbacks.delete(callback)
      if (callbacks.size === 0) {
        this.listeners.delete(eventType)
      }
    }
  }

  /**
   * 移除所有监听器
   */
  removeAllListeners() {
    this.listeners.clear()
  }

  /**
   * 获取连接状态
   */
  get isConnected() {
    return computed(() => this.connected.value)
  }

  get isConnecting() {
    return computed(() => this.connecting.value)
  }

  get lastError() {
    return computed(() => this.error.value)
  }
}

// 创建单例
const sseService = new SSEService()

export default sseService

