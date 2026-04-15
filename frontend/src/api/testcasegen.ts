import { apiClient } from './client'
import type { ApiResponse, PaginatedResponse, PaginationParams } from '@/types/api'


export const AIApi = {

    async generateTestCases(requirement_string: string): Promise<void> {
        return apiClient.post('/aiagent/initialize3', requirement_string)
    },

    async loaddocxfile(formData: FormData): Promise<any> {
        return apiClient.post('/aiagent/getdocx', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            timeout: 30000,
        })
    }

}