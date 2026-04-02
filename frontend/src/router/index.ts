import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresGuest: true }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { requiresGuest: true }
    },
    {
      path: '/layout',
      name: 'layout',
      component: () => import('@/layouts/DefaultLayout.vue'),
      meta: { requiresGuest: true }
    },
    {
      path: '/test11',
      name: 'test11',
      component: () => import('@/views/interpolation.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/TextcasesGen',
      name: 'TextcasesGen',
      component: () => import('@/views/TextcasesGen.vue'),
      meta: { requiresAuth: false }
    }
    // {
    //   path: '/profile',
    //   name: 'profile',
    //   component: () => import('@/views/ProfileView.vue'),
    //   meta: { requiresAuth: true }
    // }
  ]
})

// 路由守卫，用于权限控制
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // 检查是否需要认证
  if (to.meta.requiresAuth) {
    if (!authStore.isAuthenticated) {
      const isAuthenticated = await authStore.checkAuth()
      if (!isAuthenticated) {
        next({ name: 'login', query: { redirect: to.fullPath } })
        return
      }
    }
  }
  
  // 检查是否要求未认证（如登录页）
  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    next({ name: 'home' })
    return
  }
  
  next()
})

export default router