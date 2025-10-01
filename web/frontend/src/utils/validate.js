/**
 * 验证工具函数
 * 提供各种数据验证方法
 */

/**
 * 验证邮箱
 * @param {String} email - 邮箱地址
 */
export function isEmail(email) {
  const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
  return regex.test(email)
}

/**
 * 验证手机号（中国大陆）
 * @param {String} phone - 手机号
 */
export function isPhone(phone) {
  const regex = /^1[3-9]\d{9}$/
  return regex.test(phone)
}

/**
 * 验证URL
 * @param {String} url - URL地址
 */
export function isURL(url) {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

/**
 * 验证身份证号（中国大陆）
 * @param {String} idCard - 身份证号
 */
export function isIDCard(idCard) {
  const regex = /(^\d{15}$)|(^\d{18}$)|(^\d{17}(\d|X|x)$)/
  return regex.test(idCard)
}

/**
 * 验证IP地址
 * @param {String} ip - IP地址
 */
export function isIP(ip) {
  const regex = /^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$/
  return regex.test(ip)
}

/**
 * 验证IPv6地址
 * @param {String} ip - IPv6地址
 */
export function isIPv6(ip) {
  const regex = /^([\da-fA-F]{1,4}:){7}[\da-fA-F]{1,4}$/
  return regex.test(ip)
}

/**
 * 验证用户名（字母、数字、下划线，3-20位）
 * @param {String} username - 用户名
 */
export function isUsername(username) {
  const regex = /^[a-zA-Z0-9_]{3,20}$/
  return regex.test(username)
}

/**
 * 验证密码强度
 * @param {String} password - 密码
 * @returns {Number} 0-弱 1-中 2-强
 */
export function checkPasswordStrength(password) {
  if (!password) return 0
  
  let strength = 0
  
  // 长度检查
  if (password.length >= 8) strength++
  if (password.length >= 12) strength++
  
  // 包含小写字母
  if (/[a-z]/.test(password)) strength++
  
  // 包含大写字母
  if (/[A-Z]/.test(password)) strength++
  
  // 包含数字
  if (/\d/.test(password)) strength++
  
  // 包含特殊字符
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) strength++
  
  if (strength <= 2) return 0 // 弱
  if (strength <= 4) return 1 // 中
  return 2 // 强
}

/**
 * 验证是否为空
 * @param {Any} value - 值
 */
export function isEmpty(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string' && value.trim() === '') return true
  if (Array.isArray(value) && value.length === 0) return true
  if (typeof value === 'object' && Object.keys(value).length === 0) return true
  return false
}

/**
 * 验证是否为数字
 * @param {Any} value - 值
 */
export function isNumber(value) {
  return !isNaN(parseFloat(value)) && isFinite(value)
}

/**
 * 验证是否为整数
 * @param {Any} value - 值
 */
export function isInteger(value) {
  return Number.isInteger(Number(value))
}

/**
 * 验证范围
 * @param {Number} value - 值
 * @param {Number} min - 最小值
 * @param {Number} max - 最大值
 */
export function isInRange(value, min, max) {
  const num = Number(value)
  return num >= min && num <= max
}

/**
 * 验证长度范围
 * @param {String} str - 字符串
 * @param {Number} min - 最小长度
 * @param {Number} max - 最大长度
 */
export function isLengthInRange(str, min, max) {
  const length = str ? str.length : 0
  return length >= min && length <= max
}

/**
 * 验证JSON字符串
 * @param {String} str - JSON字符串
 */
export function isJSON(str) {
  try {
    JSON.parse(str)
    return true
  } catch {
    return false
  }
}

/**
 * 验证日期格式（YYYY-MM-DD）
 * @param {String} dateStr - 日期字符串
 */
export function isDateString(dateStr) {
  const regex = /^\d{4}-\d{2}-\d{2}$/
  return regex.test(dateStr)
}

/**
 * 验证时间格式（HH:mm:ss）
 * @param {String} timeStr - 时间字符串
 */
export function isTimeString(timeStr) {
  const regex = /^([01]\d|2[0-3]):([0-5]\d):([0-5]\d)$/
  return regex.test(timeStr)
}

/**
 * 验证颜色值（十六进制）
 * @param {String} color - 颜色值
 */
export function isHexColor(color) {
  const regex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/
  return regex.test(color)
}

/**
 * Element Plus 表单验证规则生成器
 */
export const rules = {
  required: (message = '此项为必填项') => ({
    required: true,
    message,
    trigger: ['blur', 'change']
  }),
  
  email: (message = '请输入有效的邮箱地址') => ({
    validator: (rule, value, callback) => {
      if (!value) {
        callback()
      } else if (!isEmail(value)) {
        callback(new Error(message))
      } else {
        callback()
      }
    },
    trigger: 'blur'
  }),
  
  phone: (message = '请输入有效的手机号') => ({
    validator: (rule, value, callback) => {
      if (!value) {
        callback()
      } else if (!isPhone(value)) {
        callback(new Error(message))
      } else {
        callback()
      }
    },
    trigger: 'blur'
  }),
  
  username: (message = '用户名应为3-20位字母、数字或下划线') => ({
    validator: (rule, value, callback) => {
      if (!value) {
        callback()
      } else if (!isUsername(value)) {
        callback(new Error(message))
      } else {
        callback()
      }
    },
    trigger: 'blur'
  }),
  
  length: (min, max, message) => ({
    min,
    max,
    message: message || `长度应在 ${min} 到 ${max} 个字符之间`,
    trigger: ['blur', 'change']
  }),
  
  range: (min, max, message) => ({
    validator: (rule, value, callback) => {
      if (value === '' || value === null || value === undefined) {
        callback()
      } else if (!isInRange(value, min, max)) {
        callback(new Error(message || `值应在 ${min} 到 ${max} 之间`))
      } else {
        callback()
      }
    },
    trigger: 'blur'
  }),
  
  pattern: (regex, message = '格式不正确') => ({
    pattern: regex,
    message,
    trigger: 'blur'
  })
}
