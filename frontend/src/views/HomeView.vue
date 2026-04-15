<template>
  <div class="home">
    <header class="header">
      <h1>企业级应用</h1>
      <nav>
        <span class="health-badge" :class="healthStatus">
          {{ healthText }}
        </span>
        <button @click="handleLogout" class="logout-button">退出登录</button>
      </nav>
    </header>
    
    <main class="main-content">
      <div class="welcome">
        <h2>欢迎回来, {{ authStore.user?.username }}!</h2>
        <p>这是一个企业级全栈应用示例</p>
        
        <div class="stats">
          <div class="stat-card">
            <h3>用户角色</h3>
            <p>{{ authStore.user?.role }}</p>
          </div>
          <div class="stat-card">
            <h3>注册时间</h3>
            <p>{{ formatDate(authStore.user?.created_at) }}</p>
          </div>
          <div class="stat-card">
            <h3>邮箱</h3>
            <p>{{ authStore.user?.email }}</p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { authApi, type HealthResponse } from '@/api/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

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

const checkHealth = async () => {
  try {
    healthInfo.value = await authApi.healthCheck()
    healthError.value = false
  } catch {
    healthError.value = true
  }
}

onMounted(() => {
  checkHealth()
})

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}

const formatDate = (dateString?: string) => {
  if (!dateString) return '未知'
  return new Date(dateString).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.home {
  min-height: 100vh;
}

.header {
  background: white;
  padding: 1rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header nav {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.health-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 500;
}

.health-badge.healthy {
  background-color: #d4edda;
  color: #155724;
}

.health-badge.unhealthy {
  background-color: #f8d7da;
  color: #721c24;
}

.health-badge.checking {
  background-color: #fff3cd;
  color: #856404;
}

.logout-button {
  background: #dc3545;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

.main-content {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.welcome {
  text-align: center;
}

.stats {
  display: flex;
  justify-content: center;
  gap: 2rem;
  margin-top: 2rem;
  flex-wrap: wrap;
}

.stat-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  min-width: 200px;
}
</style>