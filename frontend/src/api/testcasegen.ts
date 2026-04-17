import { apiClient } from './client'

// ==================== 类型定义 ====================

export interface ParseDocResult {
  success: boolean
  raw_content: string
  format: string
  metadata: {
    paragraph_count?: number
    table_count?: number
    image_count?: number
    heading_count?: number
    total_characters?: number
    total_words?: number
    file_name?: string
    file_size?: number
  }
  error?: string
}

export interface GraphNode {
  id: string
  name: string
  label: string
  type: string
  description?: string
  properties?: Record<string, any>
}

export interface GraphEdge {
  source: string
  target: string
  label: string
  properties?: Record<string, any>
}

export interface TestCaseStep {
  action: string
  expected: string
}

export interface TestCase {
  id: string
  name: string
  description: string
  priority: string
  status: string
  preconditions: string
  steps: TestCaseStep[]
  module?: string
  created_at: string
  updated_at: string
}

export interface SubmitTaskResponse {
  task_id: string
  status: string
  message: string
}

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  task_type: string
  result?: {
    success: boolean
    message: string
    test_cases?: TestCase[]
    graph_nodes?: GraphNode[]
    graph_edges?: GraphEdge[]
    processing_time?: number
    error?: string
  }
  error?: string
  created_at?: string
  updated_at?: string
}

// ==================== API 方法 ====================

export const AIApi = {
  /** 上传 DOCX 并解析为文本 */
  async loaddocxfile(formData: FormData): Promise<ParseDocResult> {
    return apiClient.post('/aiagent/getdocx', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    })
  },

  /** 提交异步任务（解析图谱或生成用例），后台执行，支持页签切换不中断 */
  async submitTask(taskType: 'parse_graph' | 'generate_cases', requirementText: string, searchKeyword?: string): Promise<SubmitTaskResponse> {
    return apiClient.post('/aiagent/submit-task', {
      task_type: taskType,
      requirement_text: requirementText,
      search_keyword: searchKeyword || '',
    }, { timeout: 10000 })
  },

  /** 查询异步任务状态 */
  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    return apiClient.get(`/aiagent/task-status/${taskId}`, { timeout: 10000 })
  },
}
