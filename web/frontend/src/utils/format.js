/**
 * 格式化工具函数
 * 处理各种数据格式化需求
 */

import moment from 'moment'

/**
 * 格式化时间
 * @param {String|Date} time - 时间
 * @param {String} format - 格式
 */
export function formatTime(time, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!time) return '-'
  return moment(time).format(format)
}

/**
 * 格式化相对时间
 * @param {String|Date} time - 时间
 */
export function formatRelativeTime(time) {
  if (!time) return '-'
  return moment(time).fromNow()
}

/**
 * 格式化文件大小
 * @param {Number} bytes - 字节数
 * @param {Number} decimals - 小数位数
 */
export function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B'
  
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

/**
 * 格式化数字
 * @param {Number} num - 数字
 * @param {Number} decimals - 小数位数
 */
export function formatNumber(num, decimals = 0) {
  if (num === null || num === undefined) return '-'
  
  const n = parseFloat(num)
  if (isNaN(n)) return '-'
  
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

/**
 * 格式化百分比
 * @param {Number} num - 数字（0-1）
 * @param {Number} decimals - 小数位数
 */
export function formatPercent(num, decimals = 1) {
  if (num === null || num === undefined) return '-'
  
  const n = parseFloat(num)
  if (isNaN(n)) return '-'
  
  return (n * 100).toFixed(decimals) + '%'
}

/**
 * 格式化货币
 * @param {Number} amount - 金额
 * @param {String} currency - 货币符号
 * @param {Number} decimals - 小数位数
 */
export function formatCurrency(amount, currency = '¥', decimals = 2) {
  if (amount === null || amount === undefined) return '-'
  
  const n = parseFloat(amount)
  if (isNaN(n)) return '-'
  
  return currency + n.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

/**
 * 截断文本
 * @param {String} text - 文本
 * @param {Number} length - 长度
 * @param {String} suffix - 后缀
 */
export function truncate(text, length = 50, suffix = '...') {
  if (!text) return ''
  if (text.length <= length) return text
  
  return text.substring(0, length) + suffix
}

/**
 * 高亮文本
 * @param {String} text - 文本
 * @param {String} keyword - 关键词
 */
export function highlightText(text, keyword) {
  if (!text || !keyword) return text
  
  const regex = new RegExp(`(${keyword})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

/**
 * 驼峰转下划线
 * @param {String} str - 字符串
 */
export function camelToSnake(str) {
  return str.replace(/([A-Z])/g, '_$1').toLowerCase()
}

/**
 * 下划线转驼峰
 * @param {String} str - 字符串
 */
export function snakeToCamel(str) {
  return str.replace(/_([a-z])/g, (match, letter) => letter.toUpperCase())
}

/**
 * 首字母大写
 * @param {String} str - 字符串
 */
export function capitalize(str) {
  if (!str) return ''
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase()
}

/**
 * 隐藏手机号中间4位
 * @param {String} phone - 手机号
 */
export function maskPhone(phone) {
  if (!phone) return ''
  return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
}

/**
 * 隐藏邮箱部分字符
 * @param {String} email - 邮箱
 */
export function maskEmail(email) {
  if (!email) return ''
  
  const [name, domain] = email.split('@')
  if (!name || !domain) return email
  
  const maskedName = name.substring(0, 2) + '***'
  return maskedName + '@' + domain
}

/**
 * 格式化状态文本
 * @param {String} status - 状态
 */
export function formatStatus(status) {
  const statusMap = {
    'pending': '待处理',
    'processing': '处理中',
    'waiting': '等待审核',
    'approved': '已通过',
    'published': '已发布',
    'rejected': '已拒绝',
    'draft': '草稿',
    'deleted': '已删除'
  }
  
  return statusMap[status] || status
}

/**
 * 获取状态类型（用于Element Plus Tag）
 * @param {String} status - 状态
 */
export function getStatusType(status) {
  const typeMap = {
    'pending': 'warning',
    'processing': 'warning',
    'waiting': 'warning',
    'approved': 'success',
    'published': 'primary',
    'rejected': 'danger',
    'draft': 'info',
    'deleted': 'info'
  }
  
  return typeMap[status] || 'info'
}

/**
 * 解析查询参数
 * @param {String} search - search字符串
 */
export function parseQueryString(search) {
  if (!search) return {}
  
  const params = new URLSearchParams(search)
  const result = {}
  
  for (const [key, value] of params.entries()) {
    result[key] = value
  }
  
  return result
}

/**
 * 构建查询参数
 * @param {Object} params - 参数对象
 */
export function buildQueryString(params) {
  if (!params || typeof params !== 'object') return ''
  
  const searchParams = new URLSearchParams()
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.append(key, value)
    }
  })
  
  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ''
}

/**
 * 解析表情包标记为HTML
 * @param {String} text - 包含 [em]xxx[/em] 标记的文本
 * @returns {String} 包含 <img> 标签的 HTML 字符串
 */
export function parseEmoticons(text) {
  if (!text || typeof text !== 'string') return text
  
  // 匹配 [em]xxx[/em] 格式的表情标记
  const emoticonRegex = /\[em\]([^[\]]+)\[\/em\]/g
  
  return text.replace(emoticonRegex, (match, code) => {
    const url = `https://qzonestyle.gtimg.cn/qzone/em/${code}.gif`
    return `<img class="qzone-emoticon" src="${url}" alt="${code}" title="${code}" referrerpolicy="no-referrer" />`
  })
}

// 别名导出，保持兼容性
export const formatDateTime = formatTime