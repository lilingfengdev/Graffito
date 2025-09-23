import axios from 'axios'

// Prefer explicit VITE_API_BASE; fallback to '/api' in dev so SPA routes like '/audit' aren't proxied.
const resolvedBaseURL = (typeof import.meta.env.VITE_API_BASE === 'string' && import.meta.env.VITE_API_BASE !== '')
  ? import.meta.env.VITE_API_BASE
  : (import.meta.env.DEV ? '/api' : '')
const api = axios.create({ baseURL: resolvedBaseURL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// 全局响应拦截：401 时跳转登录
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      try { localStorage.removeItem('token') } catch (_) {}
      const path = window.location.pathname + window.location.search
      const isAuthPage = window.location.pathname === '/login' || window.location.pathname === '/register'
      if (!isAuthPage) {
        const redirect = encodeURIComponent(path)
        window.location.href = `/login?redirect=${redirect}`
      }
    }
    return Promise.reject(error)
  }
)

export default api

