import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type LoginRequest, type User } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
    const user = ref<User | null>(null)
    const token = ref<string | null>(localStorage.getItem('access_token'))
    const isLoading = ref(false)
    let _checkAuthPromise: Promise<boolean> | null = null

    const isAuthenticated = computed(() => !!token.value)

    const login = async (credentials: LoginRequest) => {
        isLoading.value = true
        try {
        const response = await authApi.login(credentials)
        token.value = response.access_token
        user.value = response.user

        // 存储token
        localStorage.setItem('access_token', response.access_token)

        return response
        } catch (error) {
        throw error
        } finally {
        isLoading.value = false
        }
    }

    const logout = () => {
        token.value = null
        user.value = null
        localStorage.removeItem('access_token')
        _checkAuthPromise = null
    }

    const checkAuth = async (): Promise<boolean> => {
        if (!token.value) return false

        // 防重入：多个并行路由导航只发起一次 checkAuth 请求
        if (_checkAuthPromise) return _checkAuthPromise

        _checkAuthPromise = (async () => {
            try {
                const userData = await authApi.getCurrentUser()
                user.value = userData
                return true
            } catch (error) {
                logout()
                return false
            } finally {
                _checkAuthPromise = null
            }
        })()

        return _checkAuthPromise
    }

    return {
        user,
        token,
        isLoading,
        isAuthenticated,
        login,
        logout,
        checkAuth
    }
})