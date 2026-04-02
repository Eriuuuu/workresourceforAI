<template>
  <div class="home">
    <header class="header">
      <h1>企业级应用</h1>
      <nav>
        <router-link to="/users">用户管理</router-link>
        <router-link to="/profile">个人资料</router-link>
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
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

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
}

.stat-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  min-width: 200px;
}
</style>