import { defineStore } from 'pinia'
import { ref } from 'vue'

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

  // 保存一个正在进行的请求 Promise，切换页面回来时复用
  let _pendingRequest: Promise<void> | null = null

  function setPendingRequest(promise: Promise<void> | null) {
    _pendingRequest = promise
  }

  function getPendingRequest(): Promise<void> | null {
    return _pendingRequest
  }

  function reset() {
    messages.value = []
    sessionId.value = ''
    loading.value = false
    systemReady.value = false
    initializing.value = false
    initTaskId.value = ''
    askTaskId.value = ''
    _pendingRequest = null
  }

  return {
    messages,
    sessionId,
    loading,
    systemReady,
    initializing,
    initTaskId,
    askTaskId,
    setPendingRequest,
    getPendingRequest,
    reset,
  }
})
