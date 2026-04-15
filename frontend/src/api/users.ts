import { apiClient } from './client'
import type { User } from './auth'

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
    async getUsers(skip: number = 0, limit: number = 100): Promise<User[]> {
        return apiClient.get<User[]>('/user/', { params: { skip, limit } })
    },

    async getUserById(userId: string): Promise<User> {
        return apiClient.get<User>(`/user/${userId}`)
    },

    async updateUser(userId: string, userData: UpdateUserRequest): Promise<User> {
        return apiClient.put<User>(`/user/${userId}`, userData)
    },

    async deleteUser(userId: string): Promise<void> {
        return apiClient.delete(`/user/${userId}`)
    },

    async changePassword(passwordData: ChangePasswordRequest): Promise<void> {
        return apiClient.post('/auth/change-password', passwordData)
    }
}