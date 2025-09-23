/**
 * 主题管理组合式函数
 */
import { inject, computed } from 'vue'

export function useTheme() {
  // 注入主题上下文
  const themeContext = inject('theme')
  
  if (!themeContext) {
    console.warn('Theme context not found. Make sure to provide theme in the root component.')
    return {
      isDark: computed(() => true),
      theme: computed(() => 'dark'),
      toggleTheme: () => {},
      themeIcon: computed(() => 'Sunny'),
      themeText: computed(() => '浅色模式')
    }
  }
  
  const { isDark, theme, toggleTheme } = themeContext
  
  // 主题图标
  const themeIcon = computed(() => {
    return isDark.value ? 'Sunny' : 'Moon'
  })
  
  // 主题文本
  const themeText = computed(() => {
    return isDark.value ? '浅色模式' : '深色模式'
  })
  
  // 主题类名
  const themeClass = computed(() => {
    return isDark.value ? 'dark' : 'light'
  })
  
  return {
    isDark: computed(() => isDark.value),
    theme: computed(() => theme.value),
    toggleTheme,
    themeIcon,
    themeText,
    themeClass
  }
}
