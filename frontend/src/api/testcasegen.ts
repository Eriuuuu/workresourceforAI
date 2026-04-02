import { apiClient } from './client'
import axios from 'axios'
import type { ApiResponse, PaginatedResponse, PaginationParams } from '@/types/api'


export const AIApi = {

    async generateTestCases(requirement_string:string): Promise<void> {
        return apiClient.post('http://localhost:8000/api/v1/aiagent/initialize3', requirement_string)
    },

    // async loaddocxfile(formData: FormData): Promise<void> {
    //     console.log('调试信息');
    //     return apiClient.post('/aiagent/getdocx', formData,{
    //         headers:{
    //             'Content-Type':'multipart/form-data',
    //         }
    //     })
    // }
    async loaddocxfile(formData: FormData): Promise<any> {
        // 直接使用 axios，不使用封装的 apiClient
        const response = await axios.post(
            `${import.meta.env.VITE_API_BASE_URL}/aiagent/getdocx`,
            formData,
            {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                timeout: 30000,
            }
        )
        return response.data
    }

}