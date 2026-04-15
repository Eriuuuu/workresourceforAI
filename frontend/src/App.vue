<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

// 应用启动时检查认证状态（忽略 Promise，由路由守卫统一管理）
const authStore = useAuthStore()
authStore.checkAuth().catch(() => {})
</script>

<style lang="scss">
#app {
  min-height: 100vh;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 
               'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
</style>