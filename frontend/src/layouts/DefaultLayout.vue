<template>
  <div class="default-layout">
    <header class="layout-header">
      <div class="container">
        <div class="header-content">
          <h1 class="logo">
            <router-link to="/">{{ appName }}</router-link>
          </h1>
          <nav class="nav-menu">
            <router-link to="/users" class="nav-link">用户管理</router-link>
            <router-link to="/profile" class="nav-link">个人资料</router-link>
            <button @click="handleLogout" class="logout-button">退出登录</button>
          </nav>
        </div>
      </div>
    </header>
    
    <main class="layout-main">
      <div class="container">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const appName = computed(() => import.meta.env.VITE_APP_NAME)

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped lang="scss">
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
    background-color: darken($error-color, 10%);
  }
}

.layout-main {
  flex: 1;
  padding: 2rem 0;
  background-color: $background-color;
}
</style>