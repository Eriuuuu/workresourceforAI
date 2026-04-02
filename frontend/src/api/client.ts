import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios'

//AxiosInstance: axios 实例的类型，包含所有 HTTP 方法
//AxiosRequestConfig: 请求配置对象的类型
//AxiosResponse: 响应对象的类型

class ApiClient {
    private client: AxiosInstance

    constructor(baseURL: string) {
        // 创建 axios 实例
        this.client = axios.create({
        baseURL,            //所有请求的基础路径
        timeout: 10000,     //10秒后请求超时
        headers: {
            'Content-Type': 'application/json',
        },
        })

        // 设置拦截器
        this.setupInterceptors()
    }

    private setupInterceptors() {
        // 请求拦截器：自动添加Token
        // 1. 每次发送请求前自动执行
        // 2. 从 localStorage 获取 token
        // 3. 如果 token 存在，自动添加到请求头
        // 4. 请求头格式：Authorization: Bearer your-token-here
        this.client.interceptors.request.use(
        (config) => {
            const token = localStorage.getItem('access_token')
            if (token) {
            config.headers.Authorization = `Bearer ${token}`
            }
            return config
        },
        (error) => {
            return Promise.reject(error)
        }
        )

        // 响应拦截器：统一错误处理
        this.client.interceptors.response.use(
        (response) => response,         // 成功响应直接返回
        async (error) => {
            if (error.response?.status === 401) {
            // Token过期，清除本地存储并跳转到登录页
            localStorage.removeItem('access_token')
            window.location.href = '/login'
            }
            return Promise.reject(error)
        }
        )
    }

    // HTTP 方法封装
    public async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
        const response: AxiosResponse<T> = await this.client.get(url, config)
        return response.data
    }

    public async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        const response: AxiosResponse<T> = await this.client.post(url, data, config)
        return response.data
    }

    public async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
        const response: AxiosResponse<T> = await this.client.put(url, data, config)
        return response.data
    }

    public async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
        const response: AxiosResponse<T> = await this.client.delete(url, config)
        return response.data
    }
}

// 创建API客户端实例
export const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL)