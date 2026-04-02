// API响应类型
export interface ApiResponse<T = any> {
        data: T
        message?: string
        code: number
    }
    
    export interface PaginatedResponse<T = any> {
        items: T[]
        total: number
        page: number
        size: number
        pages: number
    }
    
    // 分页参数
    export interface PaginationParams {
        page?: number
        size?: number
        sort_by?: string
        sort_order?: 'asc' | 'desc'
    }