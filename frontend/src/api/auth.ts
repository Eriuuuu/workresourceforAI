import { apiClient } from './client'

export interface LoginRequest {
    username: string
    password: string
}

export interface LoginResponse {
    access_token: string
    token_type: string
    user: User
}

export interface User {
    _id: string
    username: string
    email: string
    full_name?: string
    role: string
    disabled: boolean
    created_at: string
    updated_at: string
}

export interface RegisterRequest {
    username: string
    email: string
    full_name?: string
    password: string
}

export interface HealthResponse {
    status: string
    timestamp: number
    service: string
    version: string
}

export const authApi = {
    async login(credentials: LoginRequest): Promise<LoginResponse> {
        const params = new URLSearchParams()
        params.append('username', credentials.username)
        params.append('password', credentials.password)

        return apiClient.post<LoginResponse>('/auth/login', params, {
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        })
    },

    async register(userData: RegisterRequest): Promise<User> {
        return apiClient.post<User>('/auth/register', userData)
    },

    async getCurrentUser(): Promise<User> {
        return apiClient.get<User>('/user/me')
    },

    async healthCheck(): Promise<HealthResponse> {
        return apiClient.get<HealthResponse>('/health')
    }
}