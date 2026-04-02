<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">  //初始化逻辑
import { useAuthStore } from '@/stores/auth'

// 应用启动时检查认证状态
const authStore = useAuthStore()
authStore.checkAuth()
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