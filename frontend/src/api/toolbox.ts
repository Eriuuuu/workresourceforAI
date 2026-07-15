import { apiClient } from './client'

export interface ToolboxEvent {
    _id: string
    event_id: string
    client_time: string
    server_time: string
    hostname: string
    source: 'gui' | 'cli'
    feature: string
    feature_id: string
    action: string
    status: 'success' | 'failed' | 'cancelled'
    input?: Record<string, unknown> | null
    result?: Record<string, unknown> | null
    error?: string | null
    duration_ms?: number | null
    tool_version?: string | null
}

export interface ToolboxEventListResponse {
    items: ToolboxEvent[]
    total: number
    skip: number
    limit: number
}

export interface ToolboxStatsResponse {
    total_events: number
    today_events: number
    success_count: number
    failed_count: number
    cancelled_count: number
    active_hostnames: number
    by_feature: Array<{
        feature_id: string
        feature: string
        count: number
        success_count: number
        failed_count: number
        success_rate: number
    }>
    daily_trend: Array<{
        date: string
        count: number
    }>
}

export interface ToolboxEventQuery {
    skip?: number
    limit?: number
    hostname?: string
    feature_id?: string
    status?: string
    start_time?: string
    end_time?: string
    error_keyword?: string
}

export interface ToolboxStatsQuery {
    days?: number
    hostname?: string
    feature_id?: string
}

export const toolboxApi = {
    async getEvents(params: ToolboxEventQuery = {}): Promise<ToolboxEventListResponse> {
        return apiClient.get<ToolboxEventListResponse>('/toolbox/events', { params })
    },

    async getEventById(eventId: string): Promise<ToolboxEvent> {
        return apiClient.get<ToolboxEvent>(`/toolbox/events/${eventId}`)
    },

    async getHostnames(): Promise<string[]> {
        return apiClient.get<string[]>('/toolbox/hostnames')
    },

    async getStats(params: ToolboxStatsQuery = {}): Promise<ToolboxStatsResponse> {
        return apiClient.get<ToolboxStatsResponse>('/toolbox/stats', { params })
    },
}
