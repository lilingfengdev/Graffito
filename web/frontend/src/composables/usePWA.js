/**
 * PWA Composable
 * 
 * 管理 PWA 安装提示和更新
 */

import { ref, onMounted, onUnmounted } from 'vue'
import { ElNotification, ElMessageBox } from 'element-plus'

export function usePWA() {
  const deferredPrompt = ref(null)
  const isInstallable = ref(false)
  const isInstalled = ref(false)
  const needsUpdate = ref(false)
  const updateRegistration = ref(null)

  /**
   * 检查是否已安装为 PWA
   */
  const checkInstalled = () => {
    // 检查是否在独立模式运行（已安装）
    if (window.matchMedia('(display-mode: standalone)').matches) {
      isInstalled.value = true
      return true
    }
    
    // iOS Safari
    if (window.navigator.standalone === true) {
      isInstalled.value = true
      return true
    }
    
    return false
  }

  /**
   * 监听安装提示事件
   */
  const handleBeforeInstallPrompt = (e) => {
    console.log('[PWA] beforeinstallprompt event fired')
    
    // 阻止默认的安装提示
    e.preventDefault()
    
    // 保存事件以便稍后触发
    deferredPrompt.value = e
    isInstallable.value = true
    
    // 显示自定义安装提示
    showInstallPrompt()
  }

  /**
   * 显示安装提示
   */
  const showInstallPrompt = () => {
    // 检查是否已经显示过（使用 localStorage）
    const hasShownPrompt = localStorage.getItem('pwa-install-prompt-shown')
    if (hasShownPrompt) {
      return
    }

    setTimeout(() => {
      ElNotification({
        title: '安装应用',
        message: '将 Graffito 添加到主屏幕，获得更好的使用体验',
        type: 'info',
        duration: 0,
        position: 'bottom-right',
        customClass: 'pwa-install-notification',
        showClose: true,
        dangerouslyUseHTMLString: true,
        message: `
          <div style="margin-bottom: 12px;">将 Graffito 添加到主屏幕，获得更好的使用体验</div>
          <div style="display: flex; gap: 8px;">
            <button class="el-button el-button--primary el-button--small" onclick="window.installPWA()">
              <span>立即安装</span>
            </button>
            <button class="el-button el-button--default el-button--small" onclick="window.dismissPWAPrompt()">
              <span>暂不安装</span>
            </button>
          </div>
        `,
        onClose: () => {
          localStorage.setItem('pwa-install-prompt-shown', 'true')
        }
      })
    }, 3000)
  }

  /**
   * 触发安装
   */
  const install = async () => {
    if (!deferredPrompt.value) {
      console.log('[PWA] No install prompt available')
      return
    }

    // 显示安装提示
    deferredPrompt.value.prompt()
    
    // 等待用户响应
    const { outcome } = await deferredPrompt.value.userChoice
    
    console.log(`[PWA] User choice: ${outcome}`)
    
    if (outcome === 'accepted') {
      ElNotification({
        title: '安装成功',
        message: '应用已添加到主屏幕',
        type: 'success',
        duration: 3000
      })
      isInstalled.value = true
    }
    
    // 清除 deferred prompt
    deferredPrompt.value = null
    isInstallable.value = false
    
    // 标记已显示过提示
    localStorage.setItem('pwa-install-prompt-shown', 'true')
  }

  /**
   * 关闭安装提示
   */
  const dismissPrompt = () => {
    localStorage.setItem('pwa-install-prompt-shown', 'true')
    deferredPrompt.value = null
    isInstallable.value = false
  }

  /**
   * 监听 Service Worker 更新
   */
  const handleServiceWorkerUpdate = (registration) => {
    console.log('[PWA] Service Worker update available')
    updateRegistration.value = registration
    needsUpdate.value = true
    
    // 显示更新提示
    ElNotification({
      title: '发现新版本',
      message: '应用有新版本可用，是否立即更新？',
      type: 'info',
      duration: 0,
      position: 'bottom-right',
      showClose: true,
      dangerouslyUseHTMLString: true,
      message: `
        <div style="margin-bottom: 12px;">应用有新版本可用</div>
        <div style="display: flex; gap: 8px;">
          <button class="el-button el-button--primary el-button--small" onclick="window.updatePWA()">
            <span>立即更新</span>
          </button>
          <button class="el-button el-button--default el-button--small" onclick="window.dismissPWAUpdate()">
            <span>稍后更新</span>
          </button>
        </div>
      `
    })
  }

  /**
   * 执行更新
   */
  const update = async () => {
    if (!updateRegistration.value) {
      return
    }

    const registration = updateRegistration.value
    
    // 如果有等待中的 Service Worker，则激活它
    if (registration.waiting) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' })
      
      // 监听控制器变化
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        // 重新加载页面以使用新版本
        window.location.reload()
      })
    }
  }

  /**
   * 关闭更新提示
   */
  const dismissUpdate = () => {
    needsUpdate.value = false
    updateRegistration.value = null
  }

  /**
   * 初始化
   */
  const initialize = () => {
    // 检查是否已安装
    checkInstalled()

    // 监听安装提示事件
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)

    // 监听应用已安装事件
    window.addEventListener('appinstalled', () => {
      console.log('[PWA] App installed')
      isInstalled.value = true
      isInstallable.value = false
      deferredPrompt.value = null
      
      ElNotification({
        title: '安装成功',
        message: '应用已成功安装到设备',
        type: 'success',
        duration: 3000
      })
    })

    // 注册 Service Worker 并监听更新
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.ready.then((registration) => {
        // 检查更新
        registration.update()
        
        // 监听更新
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing
          
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              handleServiceWorkerUpdate(registration)
            }
          })
        })
      })
    }

    // 暴露全局方法供 HTML 字符串调用
    window.installPWA = install
    window.dismissPWAPrompt = dismissPrompt
    window.updatePWA = update
    window.dismissPWAUpdate = dismissUpdate
  }

  /**
   * 清理
   */
  const cleanup = () => {
    window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    
    // 清理全局方法
    delete window.installPWA
    delete window.dismissPWAPrompt
    delete window.updatePWA
    delete window.dismissPWAUpdate
  }

  // 生命周期钩子
  onMounted(() => {
    initialize()
  })

  onUnmounted(() => {
    cleanup()
  })

  return {
    // 状态
    isInstallable,
    isInstalled,
    needsUpdate,
    
    // 方法
    install,
    dismissPrompt,
    update,
    dismissUpdate,
    checkInstalled
  }
}

