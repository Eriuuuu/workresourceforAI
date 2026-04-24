import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
      path: '/',
      component: () => import('@/layouts/DefaultLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/TextcasesGen'
        },
        {
          path: 'TextcasesGen',
          name: 'TextcasesGen',
          component: () => import('@/views/TextcasesGen.vue'),
          meta: { requiresAuth: true }
        },
        {
          path: 'ai-chat',
          name: 'ai-chat',
          component: () => import('@/views/AiChatView.vue'),
          meta: { requiresAuth: true, fullBleed: true }
        },
        {
          path: 'profile',
          name: 'profile',
          component: () => import('@/views/ProfileView.vue'),
          meta: { requiresAuth: true }
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/UserManagementView.vue'),
          meta: { requiresAuth: true }
        }
      ]
    }
  ]
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth) {
    if (!authStore.isAuthenticated) {
      const isAuthenticated = await authStore.checkAuth()
      if (!isAuthenticated) {
        next({ name: 'login', query: { redirect: to.fullPath } })
        return
      }
    }
  }

  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    next({ path: '/TextcasesGen' })
    return
  }

  next()
})

export default router