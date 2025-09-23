import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './api'

// Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// Progress bar
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

const app = createApp(App)

// Register all Element Plus icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// Configure progress bar
NProgress.configure({ showSpinner: false })

app.use(router)
app.use(ElementPlus)
app.mount('#app')

