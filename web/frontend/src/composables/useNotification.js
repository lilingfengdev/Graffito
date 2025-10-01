/**
 * 通知提示 Composable
 * 统一的消息通知系统
 */

import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'

export function useNotification() {
  /**
   * 成功消息
   */
  const success = (message, options = {}) => {
    return ElMessage.success({
      message,
      duration: 3000,
      showClose: true,
      grouping: true,
      ...options
    })
  }

  /**
   * 错误消息
   */
  const error = (message, options = {}) => {
    return ElMessage.error({
      message,
      duration: 5000,
      showClose: true,
      grouping: true,
      ...options
    })
  }

  /**
   * 警告消息
   */
  const warning = (message, options = {}) => {
    return ElMessage.warning({
      message,
      duration: 4000,
      showClose: true,
      grouping: true,
      ...options
    })
  }

  /**
   * 信息消息
   */
  const info = (message, options = {}) => {
    return ElMessage.info({
      message,
      duration: 3000,
      showClose: true,
      grouping: true,
      ...options
    })
  }

  /**
   * 确认对话框
   */
  const confirm = (message, title = '确认操作', options = {}) => {
    return ElMessageBox.confirm(
      message,
      title,
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
        closeOnClickModal: false,
        closeOnPressEscape: true,
        ...options
      }
    )
  }

  /**
   * 提示对话框
   */
  const alert = (message, title = '提示', options = {}) => {
    return ElMessageBox.alert(
      message,
      title,
      {
        confirmButtonText: '确定',
        type: 'info',
        ...options
      }
    )
  }

  /**
   * 输入对话框
   */
  const prompt = (message, title = '请输入', options = {}) => {
    return ElMessageBox.prompt(
      message,
      title,
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /.+/,
        inputErrorMessage: '输入不能为空',
        ...options
      }
    )
  }

  /**
   * 通知
   */
  const notify = (message, title = '', options = {}) => {
    return ElNotification({
      title,
      message,
      duration: 4500,
      position: 'top-right',
      ...options
    })
  }

  /**
   * 成功通知
   */
  const notifySuccess = (message, title = '成功', options = {}) => {
    return notify(message, title, {
      type: 'success',
      ...options
    })
  }

  /**
   * 错误通知
   */
  const notifyError = (message, title = '错误', options = {}) => {
    return notify(message, title, {
      type: 'error',
      duration: 6000,
      ...options
    })
  }

  /**
   * 警告通知
   */
  const notifyWarning = (message, title = '警告', options = {}) => {
    return notify(message, title, {
      type: 'warning',
      ...options
    })
  }

  /**
   * 信息通知
   */
  const notifyInfo = (message, title = '提示', options = {}) => {
    return notify(message, title, {
      type: 'info',
      ...options
    })
  }

  return {
    // 消息
    success,
    error,
    warning,
    info,
    
    // 对话框
    confirm,
    alert,
    prompt,
    
    // 通知
    notify,
    notifySuccess,
    notifyError,
    notifyWarning,
    notifyInfo
  }
}
