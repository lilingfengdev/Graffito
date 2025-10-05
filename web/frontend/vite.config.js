import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || 'http://localhost:8083'
  
  return {
    // 插件配置
    plugins: [
      vue({
        script: {
          defineModel: true,
          propsDestructure: true
        }
      }),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['logo.png', 'dark_logo.png', 'apple-touch-icon.png', 'favicon.ico'],
        manifest: {
          name: 'Graffito 审核后台',
          short_name: 'Graffito',
          description: 'Graffito 校园墙审核管理系统',
          theme_color: '#6366f1',
          background_color: '#0f172a',
          display: 'standalone',
          orientation: 'portrait',
          start_url: '/',
          scope: '/',
          icons: [
            {
              src: '/pwa-192x192.png',
              sizes: '192x192',
              type: 'image/png'
            },
            {
              src: '/pwa-512x512.png',
              sizes: '512x512',
              type: 'image/png'
            },
            {
              src: '/pwa-512x512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'any maskable'
            }
          ]
        },
        workbox: {
          globPatterns: ['**/*.{js,css,html,ico,png,svg,woff,woff2}'],
          runtimeCaching: [
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'google-fonts-cache',
                expiration: {
                  maxEntries: 10,
                  maxAgeSeconds: 60 * 60 * 24 * 365 // 1 year
                },
                cacheableResponse: {
                  statuses: [0, 200]
                }
              }
            },
            {
              urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'gstatic-fonts-cache',
                expiration: {
                  maxEntries: 10,
                  maxAgeSeconds: 60 * 60 * 24 * 365 // 1 year
                },
                cacheableResponse: {
                  statuses: [0, 200]
                }
              }
            },
            {
              urlPattern: /\/api\/.*/i,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-cache',
                networkTimeoutSeconds: 10,
                expiration: {
                  maxEntries: 50,
                  maxAgeSeconds: 5 * 60 // 5 minutes
                },
                cacheableResponse: {
                  statuses: [0, 200]
                }
              }
            }
          ]
        },
        devOptions: {
          enabled: true,
          type: 'module'
        }
      })
    ],
    
    // 路径别名
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@views': path.resolve(__dirname, 'src/views'),
        '@utils': path.resolve(__dirname, 'src/utils'),
        '@composables': path.resolve(__dirname, 'src/composables'),
        '@styles': path.resolve(__dirname, 'src/styles')
      },
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue']
    },
    
    // 开发服务器配置
    server: {
      port: 5173,
      strictPort: true,
      host: true, // 监听所有地址，支持网络访问
      open: false, // 不自动打开浏览器
      cors: true, // 允许跨域
      proxy: {
        '/api': {
          target: apiBase,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
          // 开发环境下的日志
          configure: (proxy, options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('proxy error', err)
            })
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('Sending Request:', req.method, req.url)
            })
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('Received Response:', proxyRes.statusCode, req.url)
            })
          }
        }
      }
    },
    
    // 构建配置
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: mode === 'development',
      // 代码分割
      rollupOptions: {
        output: {
          // 分包策略
          manualChunks: {
            // Vue 核心
            'vue-vendor': ['vue', 'vue-router'],
            // Element Plus
            'element-plus': ['element-plus', '@element-plus/icons-vue'],
            // 图表库
            'charts': ['chart.js'],
            // 工具库
            'utils': ['axios', 'moment', 'nprogress']
          },
          // 资源文件命名
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
        }
      },
      // 压缩配置
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: mode === 'production', // 生产环境删除 console
          drop_debugger: true
        }
      },
      // 提高构建性能
      chunkSizeWarningLimit: 1500,
      reportCompressedSize: false
    },
    
    // CSS 配置
    css: {
      preprocessorOptions: {
        css: {
          charset: false
        }
      },
      devSourcemap: true
    },
    
    // 优化配置
    optimizeDeps: {
      include: [
        'vue',
        'vue-router',
        'element-plus',
        '@element-plus/icons-vue',
        'axios',
        'chart.js',
        'moment',
        'nprogress'
      ]
    },
    
    // 全局变量定义
    define: {
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
      __APP_BUILD_TIME__: JSON.stringify(new Date().toISOString())
    },
    
    // 性能相关
    esbuild: {
      drop: mode === 'production' ? ['console', 'debugger'] : []
    }
  }
})

