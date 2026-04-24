import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatStepInfo } from '@/api/ai'

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  type?: 'info' | 'success' | 'error'
  meta?: {
    processing_time?: number
    source_files?: string[]
    files_count?: number
    token_usage?: Record<string, number>
    error?: string
    agent_name?: string
    agent_role?: string
    steps?: ChatStepInfo[]
    agent_chain?: Array<{ role: string; name: string; status: string }>
  }
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const sessionId = ref('')
  const loading = ref(false)
  const systemReady = ref(false)
  const initializing = ref(false)
  const initTaskId = ref('')
  const askTaskId = ref('')
  const chatTaskId = ref('')  // 多 Agent 聊天任务 ID
  const currentAgentName = ref('')  // 当前执行中的 Agent 名称
  const currentAgentChain = ref<Array<{ role: string; name: string; status: string }>>([])  // Agent 链路
  const currentSteps = ref<ChatStepInfo[]>([])  // 当前执行的步骤
  const waitStartTime = ref(0)  // 等待开始时间戳（用于计时器连续性）
  const initStartTime = ref(0)  // 初始化开始时间戳

  function reset() {
    messages.value = []
    sessionId.value = ''
    loading.value = false
    systemReady.value = false
    initializing.value = false
    initTaskId.value = ''
    askTaskId.value = ''
    chatTaskId.value = ''
    currentAgentName.value = ''
    currentAgentChain.value = []
    currentSteps.value = []
    waitStartTime.value = 0
    initStartTime.value = 0
  }

  return {
    messages,
    sessionId,
    loading,
    systemReady,
    initializing,
    initTaskId,
    askTaskId,
    chatTaskId,
    currentAgentName,
    currentAgentChain,
    currentSteps,
    waitStartTime,
    initStartTime,
    reset,
  }
})
