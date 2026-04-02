import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  
  return {
    plugins: [
      vue(),
      AutoImport({
        imports: [
          'vue',
          'vue-router',
          'pinia',
          '@vueuse/core'
        ],
        dts: 'auto-imports.d.ts',       // 生成类型声明文件
        resolvers: [ElementPlusResolver()],     // Element Plus 自动导入
      }),
      Components({
        resolvers: [ElementPlusResolver()],   // Element Plus 组件自动注册
        dts: 'components.d.ts',                // 生成组件类型声明
      }),
    ],
    resolve: {                
      alias: {              //配置路径别名
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        '#': fileURLToPath(new URL('./types', import.meta.url))
      }
    },
    server: {               //开发服务器配置：
      port: 3000,
      host: true,           //表示监听所有地址（包括局域网和本地）
      proxy: {              //设置代理，将 /api 开头的请求代理到 env.VITE_API_BASE_URL
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, '/api/v1')
        }
      }
    },
    build: {                //构建配置
      outDir: 'dist',
      sourcemap: mode !== 'production',       //在生产环境下不生成 source map，其他环境下生成
      chunkSizeWarningLimit: 1600,
      rollupOptions: {
        output: {
          manualChunks: {                    //手动配置代码分割
            'vue-vendor': ['vue', 'vue-router', 'pinia'],
            'element-plus': ['element-plus'],
            'axios-vendor': ['axios']
          }
        }
      }
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: `@use "@/styles/variables.scss" as *;`  //在每个 SCSS 文件的开头自动注入 @use "@/styles/variables.scss" as *;
                                                                  // ，这样在每个 SCSS 文件中都可以使用 variables.scss 中定义的变量，而无需手动导入。
        }
      }
    }
  }
})