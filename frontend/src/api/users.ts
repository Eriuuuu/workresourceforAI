import { apiClient } from './client'
import type { ApiResponse, PaginatedResponse, PaginationParams } from '@/types/api'

export interface UpdateUserRequest {
    username?: string
    email?: string
    full_name?: string
    role?: string
    disabled?: boolean
}

export interface ChangePasswordRequest {
    current_password: string
    new_password: string
}

export const usersApi = {
    // 获取用户列表
    async getUsers(params?: PaginationParams & { search?: string }): Promise<PaginatedResponse<User>> {
        return apiClient.get<PaginatedResponse<User>>('/users', { params })
    },

    // 获取用户详情
    async getUserById(userId: string): Promise<User> {
        return apiClient.get<User>(`/users/${userId}`)
    },

    // 更新用户信息
    async updateUser(userId: string, userData: UpdateUserRequest): Promise<User> {
        return apiClient.put<User>(`/users/${userId}`, userData)
    },

    // 删除用户
    async deleteUser(userId: string): Promise<void> {
        return apiClient.delete(`/users/${userId}`)
    },

    // 修改密码
    async changePassword(passwordData: ChangePasswordRequest): Promise<void> {
        return apiClient.post('/auth/change-password', passwordData)
    }
}