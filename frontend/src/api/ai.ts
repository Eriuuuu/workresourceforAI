import axios from 'axios'
import type { AxiosRequestConfig } from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL as string

// AI 接口专用客户端：5 分钟超时，独立于通用 apiClient
const aiClient = axios.create({
    baseURL,
    timeout: 300000,
    headers: { 'Content-Type': 'application/json' },
})

// 注入 token（与 apiClient 保持一致）
aiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
})

// 401 统一处理（与 apiClient 保持一致）
aiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token')
        }
        return Promise.reject(error)
    }
)

// 包装响应
async function request<T>(method: 'get' | 'post', url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const res = await aiClient({ method, url, data, ...config })
    return res.data
}

export interface InitializeRequest {
    force_rebuild?: boolean
    codebase_path?: string
}

export interface InitializeResponse {
    success: boolean
    message: string
    system_id?: string
    initialization_time?: string
    stats?: Record<string, any>
}

export interface QuestionRequest {
    question: string
    session_id?: string
    stream?: boolean
}

export interface QuestionResponse {
    success: boolean
    answer?: string
    question: string
    session_id: string
    source_files: string[]
    files_count: number
    token_usage?: Record<string, number>
    processing_time: number
    error?: string
}

export interface AiHealthResponse {
    status: string
    service: string
    timestamp: string
    system_initialized: boolean
    active_sessions: number
    version: string
}

export const aiApi = {
    initialize(data?: InitializeRequest): Promise<InitializeResponse> {
        return request('post', '/aiagent/initialize', data || { force_rebuild: false })
    },

    ask(data: QuestionRequest): Promise<QuestionResponse> {
        return request('post', '/aiagent/ask', data)
    },

    healthCheck(): Promise<AiHealthResponse> {
        return request('get', '/aiagent/health')
    },

    clearHistory(): Promise<{ success: boolean; message: string }> {
        return request('post', '/aiagent/clear')
    }
}
