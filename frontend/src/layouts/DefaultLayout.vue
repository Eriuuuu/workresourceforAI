<template>
  <div class="default-layout">
    <header class="layout-header">
      <div class="container">
        <div class="header-content">
          <h1 class="logo">
            <router-link to="/">{{ appName }}</router-link>
          </h1>
          <nav class="nav-menu">
            <router-link to="/TextcasesGen" class="nav-link">用例生成</router-link>
            <router-link to="/ai-chat" class="nav-link">智能问答</router-link>
            <router-link to="/users" class="nav-link">用户管理</router-link>
            <router-link to="/profile" class="nav-link">个人资料</router-link>
            <span class="health-badge" :class="healthStatus">{{ healthText }}</span>
            <button @click="handleLogout" class="logout-button">退出登录</button>
          </nav>
        </div>
      </div>
    </header>
    
    <main class="layout-main" :class="{ 'no-padding': $route.meta.fullBleed }">
      <div class="container" v-if="!$route.meta.fullBleed">
        <router-view :key="$route.fullPath" v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </div>
      <router-view v-else :key="$route.fullPath" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi, type HealthResponse } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()

const appName = computed(() => import.meta.env.VITE_APP_NAME)

const healthInfo = ref<HealthResponse | null>(null)
const healthError = ref(false)

const healthStatus = computed(() => {
  if (healthError.value) return 'unhealthy'
  return healthInfo.value ? 'healthy' : 'checking'
})

const healthText = computed(() => {
  if (healthError.value) return '服务异常'
  if (!healthInfo.value) return '检测中...'
  return '服务正常'
})

onMounted(async () => {
  try {
    healthInfo.value = await authApi.healthCheck()
    healthError.value = false
  } catch {
    healthError.value = true
  }
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped lang="scss">
@use "sass:color";

.default-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.layout-header {
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 0;
}

.logo {
  margin: 0;
  
  a {
    color: $primary-color;
    text-decoration: none;
    font-size: 1.5rem;
    font-weight: bold;
  }
}

.nav-menu {
  display: flex;
  gap: 2rem;
  align-items: center;
}

.nav-link {
  color: $text-color;
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: $border-radius;
  transition: background-color 0.3s;
  
  &:hover {
    background-color: $background-color;
  }
  
  &.router-link-active {
    color: $primary-color;
    background-color: rgba($primary-color, 0.1);
  }
}

.logout-button {
  background: $error-color;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: $border-radius;
  cursor: pointer;
  transition: background-color 0.3s;
  
  &:hover {
    background-color: color.adjust($error-color, $lightness: -10%);
  }
}

.health-badge {
  padding: 0.2rem 0.6rem;
  border-radius: 10px;
  font-size: 0.8rem;
  font-weight: 500;

  &.healthy { background-color: #d4edda; color: #155724; }
  &.unhealthy { background-color: #f8d7da; color: #721c24; }
  &.checking { background-color: #fff3cd; color: #856404; }
}

.layout-main {
  flex: 1;
  padding: 2rem 0;
  background-color: $background-color;

  &.no-padding {
    padding: 0;
    display: flex;
    flex-direction: column;
  }
}
</style>
