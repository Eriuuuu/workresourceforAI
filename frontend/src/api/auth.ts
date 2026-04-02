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

export const authApi = {
    async login(credentials: LoginRequest): Promise<LoginResponse> {
        const formData = new FormData()
        formData.append('username', credentials.username)
        formData.append('password', credentials.password)
        
        return apiClient.post<LoginResponse>('/auth/login', formData, {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        })
    },

    async register(userData: RegisterRequest): Promise<User> {
        return apiClient.post<User>('/auth/register', userData)
    },

    async getCurrentUser(): Promise<User> {
        return apiClient.get<User>('/users/me')
    }
}