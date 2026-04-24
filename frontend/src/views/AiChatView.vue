<template>
  <div class="chat-page">
    <!-- 顶部栏 -->
    <header class="chat-topbar">
      <div class="topbar-left">
        <h2 class="topbar-title">智能问答</h2>
        <span class="status-dot" :class="systemStatus" :title="systemReady ? '系统已就绪' : '系统未初始化'"></span>
      </div>
      <div class="topbar-actions">
        <button
          v-if="systemReady && messages.length > 0"
          class="icon-btn"
          title="清空对话"
          @click="handleClear"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>
        </button>
        <button class="icon-btn" title="重新初始化" @click="handleInit" :disabled="initializing">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>
        </button>
      </div>
    </header>

    <!-- 消息区域 -->
    <div class="chat-body" ref="scrollEl">
      <!-- 空状态 -->
      <div v-if="messages.length === 0 && !loading && !initializing" class="empty-state">
        <div class="empty-icon">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 3c-1.2 0-2.4.6-3 1.7A3.6 3.6 0 007.5 3C5 3 3 5 3 7.5c0 3.5 4.5 7.5 9 12 4.5-4.5 9-8.5 9-12C21 5 19 3 16.5 3c-1.2 0-2.4.6-3 1.7h0A3.6 3.6 0 0012 3z"/>
          </svg>
        </div>
        <h3 class="empty-title">AI 智能问答助手</h3>
        <p class="empty-desc">基于代码库的智能问答系统，可以回答关于代码的问题</p>
        <div v-if="!systemReady" class="empty-action">
          <button class="init-btn" @click="handleInit" :disabled="initializing">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            初始化系统开始使用
          </button>
        </div>
        <div v-else class="suggestions">
          <button
            v-for="s in suggestions" :key="s" class="suggestion-chip"
            @click="inputText = s; handleSend()"
          >{{ s }}</button>
        </div>
      </div>

      <!-- 初始化中 -->
      <div v-if="initializing" class="init-overlay">
        <div class="init-card">
          <div class="init-spinner"></div>
          <p class="init-text">{{ initStatus }}</p>
          <p class="init-elapsed">已等待 {{ initElapsed }}s</p>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-if="messages.length > 0" class="messages">
        <div
          v-for="(msg, idx) in messages" :key="idx"
          class="msg" :class="msg.role"
        >
          <!-- AI 消息 -->
          <template v-if="msg.role === 'assistant'">
            <div class="msg-avatar ai">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/><path d="M16 14H8a6 6 0 00-6 6v1h20v-1a6 6 0 00-6-6z"/></svg>
            </div>
            <div class="msg-content">
              <div v-if="msg.meta?.agent_name" class="agent-tag">{{ msg.meta.agent_name }}</div>
              <div class="msg-text" v-html="renderMd(msg.content)"></div>
              <!-- 执行步骤 -->
              <div v-if="msg.meta?.steps?.length" class="step-chain">
                <div v-for="(s, si) in msg.meta.steps" :key="si" class="step-item" :class="s.status">
                  <span class="step-dot"></span>
                  <span class="step-name">{{ s.step_name }}</span>
                  <span class="step-detail">{{ s.detail }}</span>
                </div>
              </div>
              <div v-if="msg.meta" class="msg-footer">
                <span v-if="msg.meta.processing_time" class="meta-tag">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                  {{ msg.meta.processing_time.toFixed(1) }}s
                </span>
                <span v-if="msg.meta.source_files?.length" class="meta-tag">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  {{ msg.meta.source_files.length }} 个文件
                </span>
              </div>
              <details v-if="msg.meta?.source_files?.length" class="ref-files">
                <summary>查看引用文件</summary>
                <div class="ref-list">
                  <code v-for="f in msg.meta.source_files" :key="f">{{ f }}</code>
                </div>
              </details>
            </div>
          </template>

          <!-- 用户消息 -->
          <template v-else-if="msg.role === 'user'">
            <div class="msg-content">
              <div class="msg-text">{{ msg.content }}</div>
            </div>
            <div class="msg-avatar user">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
          </template>

          <!-- 系统消息 -->
          <template v-else>
            <div class="system-msg" :class="msg.type || 'info'">
              {{ msg.content }}
            </div>
          </template>
        </div>

        <!-- AI 正在思考 -->
        <div v-if="loading" class="msg assistant">
          <div class="msg-avatar ai">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z"/><path d="M16 14H8a6 6 0 00-6 6v1h20v-1a6 6 0 00-6-6z"/></svg>
          </div>
          <div class="msg-content">
            <div class="thinking-block">
              <div class="thinking-dots">
                <span></span><span></span><span></span>
              </div>
              <div class="thinking-info">
                <span class="thinking-text">{{ thinkingTip }}</span>
                <!-- Agent 链路 -->
                <div v-if="chatStore.currentAgentChain.length > 0" class="thinking-chain">
                  <div
                    v-for="(chain, ci) in chatStore.currentAgentChain" :key="ci"
                    class="chain-item" :class="chain.status"
                  >
                    <span class="chain-dot"></span>
                    <span>{{ chain.name }}</span>
                    <svg v-if="ci < chatStore.currentAgentChain.length - 1" class="chain-arrow" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                  </div>
                </div>
                <!-- 步骤详情 -->
                <div v-if="chatStore.currentSteps.length > 0" class="thinking-steps">
                  <div v-for="(s, si) in chatStore.currentSteps" :key="si" class="thinking-step" :class="s.status">
                    <span class="step-dot-sm"></span>
                    <span class="step-text">{{ s.step_name }}</span>
                    <span v-if="s.detail" class="step-detail-inline">{{ s.detail }}</span>
                  </div>
                </div>
              </div>
              <span class="thinking-timer">{{ waitElapsed }}s</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="chat-input-area">
      <div class="input-wrapper">
        <textarea
          ref="inputEl"
          v-model="inputText"
          :placeholder="inputPlaceholder"
          rows="1"
          :disabled="loading || initializing || !systemReady"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.enter.shift.exact.prevent
          @input="autoGrow"
        ></textarea>
        <button
          class="send-btn"
          :class="{ active: canSend }"
          :disabled="!canSend"
          @click="handleSend"
          title="发送 (Enter)"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
      <p class="input-hint">AI 可能会生成不准确的信息，请注意甄别</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { aiApi, type ChatStatusResponse } from '@/api/ai'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const inputText = ref('')
const messages = computed(() => chatStore.messages)
const loading = computed(() => chatStore.loading)
const initializing = computed(() => chatStore.initializing)
const systemReady = computed(() => chatStore.systemReady)

const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

let initPollTimer: ReturnType<typeof setInterval> | null = null
let chatPollTimer: ReturnType<typeof setInterval> | null = null
let _timerHandle: ReturnType<typeof setInterval> | null = null

// 响应式计时器：通过 tick 驱动 computed 重新计算
const _timerTick = ref(0)

const waitElapsed = computed(() => {
  // _timerTick 作为响应式依赖，每秒 tick++ 会触发重新计算
  const _t = _timerTick.value
  if (!chatStore.waitStartTime) return 0
  return Math.floor((Date.now() - chatStore.waitStartTime) / 1000)
})

const initElapsed = computed(() => {
  const _t = _timerTick.value
  if (!chatStore.initStartTime) return 0
  return Math.floor((Date.now() - chatStore.initStartTime) / 1000)
})

const initStatus = ref('正在初始化 AI 系统，加载代码库并构建索引...')

const systemStatus = computed(() => {
  if (systemReady.value) return 'ready'
  if (initializing.value) return 'loading'
  return 'idle'
})

// 多 Agent 系统始终可用（LlmAgent 和 ModelingAgent 不需要初始化）
// systemReady 仅控制 QA Agent
const canSend = computed(() => !!inputText.value.trim() && !chatStore.loading && !chatStore.initializing)

const inputPlaceholder = computed(() => {
  if (chatStore.loading) return '等待 AI 回复中...'
  return '输入你的问题，按 Enter 发送（自动识别意图）...'
})

const suggestions = [
  '这个项目的整体架构是什么？',
  '帮我建一个两层框架结构，4根柱子2根梁',
  '帮我写一首关于编程的诗',
  '用户认证是如何实现的？',
]

// --- 工具函数 ---

const thinkingTip = computed(() => {
  const agentName = chatStore.currentAgentName
  if (agentName) return `${agentName} 正在处理...`
  return '正在识别意图...'
})

const scrollBottom = async () => {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTo({ top: scrollEl.value.scrollHeight, behavior: 'smooth' })
  }
}

const autoGrow = () => {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

const renderMd = (text: string) => {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      `<pre class="code-block"><div class="code-header"><span>${lang || 'code'}</span></div><code>${code.trim()}</code></pre>`
    )
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

// --- 计时器（computed + tick 驱动，保证响应式） ---

const _ensureTimer = () => {
  if (!_timerHandle) {
    _timerHandle = setInterval(() => { _timerTick.value++ }, 1000)
  }
}

const startWaitTimer = () => {
  chatStore.waitStartTime = Date.now()
  _ensureTimer()
}

const startInitTimer = () => {
  chatStore.initStartTime = Date.now()
  _ensureTimer()
}

const stopWaitTimer = () => {
  chatStore.waitStartTime = 0
  if (!chatStore.initStartTime && _timerHandle) {
    clearInterval(_timerHandle)
    _timerHandle = null
  }
}

const stopInitTimer = () => {
  chatStore.initStartTime = 0
  if (!chatStore.waitStartTime && _timerHandle) {
    clearInterval(_timerHandle)
    _timerHandle = null
  }
}

// --- 初始化（QA Agent 专用） ---

const handleInit = async () => {
  chatStore.initializing = true
  chatStore.initTaskId = ''
  initStatus.value = '正在提交初始化任务...'
  startInitTimer()

  try {
    const res = await aiApi.initialize({ force_rebuild:false})
    chatStore.initTaskId = res.task_id
    initStatus.value = '正在初始化知识库，加载代码库并构建索引...'
    startInitPolling(res.task_id)
  } catch (err: any) {
    const detail = err.response?.data?.detail || err.message || '提交初始化任务失败'
    chatStore.messages.push({ role: 'system', content: `初始化异常：${detail}`, type: 'error' })
    chatStore.initializing = false
    chatStore.initTaskId = ''
    stopInitTimer()
    scrollBottom()
  }
}

const POLL_INTERVAL = 3000

const startInitPolling = (taskId: string) => {
  stopInitPolling()
  pollInitStatus(taskId)
  initPollTimer = setInterval(() => pollInitStatus(taskId), POLL_INTERVAL)
}

const pollInitStatus = async (taskId: string) => {
  try {
    const status = await aiApi.getInitializeStatus(taskId)
    if (status.status === 'processing') {
      initStatus.value = '正在加载代码库并构建索引，请耐心等待...'
    } else if (status.status === 'completed') {
      stopInitPolling()
      chatStore.initializing = false
      chatStore.initTaskId = ''
      chatStore.systemReady = true
      if (status.result?.message) {
        chatStore.messages.push({ role: 'system', content: `知识库初始化完成 — ${status.result.message}`, type: 'success' })
      }
      scrollBottom()
    } else if (status.status === 'failed') {
      stopInitPolling()
      chatStore.initializing = false
      chatStore.initTaskId = ''
      chatStore.messages.push({ role: 'system', content: `初始化失败：${status.error || '未知错误'}`, type: 'error' })
      scrollBottom()
    }
  } catch {
    stopInitPolling()
    chatStore.initializing = false
    chatStore.initTaskId = ''
    chatStore.messages.push({ role: 'system', content: '初始化任务已丢失，请重新初始化。', type: 'error' })
    scrollBottom()
  }
}

const stopInitPolling = () => {
  if (initPollTimer) { clearInterval(initPollTimer); initPollTimer = null }
  stopInitTimer()
}

// --- 发送消息（多 Agent） ---

const handleSend = async () => {
  const message = inputText.value.trim()
  if (!message || chatStore.loading) return

  chatStore.messages.push({ role: 'user', content: message })
  inputText.value = ''
  if (inputEl.value) inputEl.value.style.height = 'auto'
  chatStore.loading = true
  chatStore.chatTaskId = ''
  chatStore.currentAgentName = ''
  chatStore.currentAgentChain = []
  chatStore.currentSteps = []
  startWaitTimer()
  scrollBottom()

  try {
    const res = await aiApi.chat({
      message,
      session_id: chatStore.sessionId || undefined,
    })
    chatStore.chatTaskId = res.task_id
    startChatPolling(res.task_id)
  } catch (err: any) {
    const detail = err.response?.data?.detail || err.message || '网络错误'
    chatStore.messages.push({ role: 'system', content: `发送失败：${detail}`, type: 'error' })
    chatStore.loading = false
    chatStore.chatTaskId = ''
    stopWaitTimer()
    scrollBottom()
  }
}

// --- 聊天轮询 ---

const startChatPolling = (taskId: string) => {
  stopChatPolling()
  pollChatStatus(taskId)
  chatPollTimer = setInterval(() => pollChatStatus(taskId), POLL_INTERVAL)
}

const pollChatStatus = async (taskId: string) => {
  try {
    const status: ChatStatusResponse = await aiApi.getChatStatus(taskId)

    // 更新中间状态（实时进度）
    if (status.status === 'processing') {
      const progress = status.progress as any
      if (progress) {
        if (progress.agent_chain?.length) {
          chatStore.currentAgentChain = progress.agent_chain
          const lastChain = progress.agent_chain[progress.agent_chain.length - 1]
          chatStore.currentAgentName = lastChain.name || ''
        }
        if (progress.steps?.length) {
          chatStore.currentSteps = progress.steps
        }
      } else {
        const result = status.result as any
        if (result?.agent_chain?.length) {
          chatStore.currentAgentChain = result.agent_chain
          const lastChain = result.agent_chain[result.agent_chain.length - 1]
          chatStore.currentAgentName = lastChain.name || ''
        }
        if (result?.steps?.length) {
          chatStore.currentSteps = result.steps
        }
      }
    }

    if (status.status === 'completed' && status.result) {
      stopChatPolling()
      chatStore.loading = false
      chatStore.chatTaskId = ''
      chatStore.currentAgentName = ''
      chatStore.currentAgentChain = []
      chatStore.currentSteps = []
      chatStore.sessionId = status.result.session_id

      if (status.result.success) {
        chatStore.messages.push({
          role: 'assistant',
          content: status.result.answer || '（未生成回答）',
          meta: {
            processing_time: status.result.processing_time,
            agent_name: status.result.agent_name,
            agent_role: status.result.agent_role,
            steps: status.result.steps,
            agent_chain: status.result.agent_chain,
            source_files: status.result.meta?.source_files,
            files_count: status.result.meta?.files_count,
          },
        })
      } else {
        chatStore.messages.push({
          role: 'assistant',
          content: status.result.error || '处理失败，请重试',
          meta: {
            processing_time: status.result.processing_time,
            agent_name: status.result.agent_name,
            agent_role: status.result.agent_role,
            error: status.result.error,
          },
        })
      }
      scrollBottom()
    } else if (status.status === 'failed') {
      stopChatPolling()
      chatStore.loading = false
      chatStore.chatTaskId = ''
      chatStore.currentAgentName = ''
      chatStore.currentAgentChain = []
      chatStore.currentSteps = []
      chatStore.messages.push({ role: 'system', content: `处理失败：${status.error || '未知错误'}`, type: 'error' })
      scrollBottom()
    }
  } catch {
    stopChatPolling()
    chatStore.loading = false
    chatStore.chatTaskId = ''
    chatStore.currentAgentName = ''
    chatStore.currentAgentChain = []
    chatStore.currentSteps = []
    chatStore.messages.push({ role: 'system', content: '任务已丢失（服务可能已重启），请重新发送。', type: 'error' })
    scrollBottom()
  }
}

const stopChatPolling = () => {
  if (chatPollTimer) { clearInterval(chatPollTimer); chatPollTimer = null }
  stopWaitTimer()
}

const handleClear = () => {
  chatStore.reset()
}

onMounted(() => {
  // 恢复计时器（时间戳在 store 中保留，重启 interval 即可）
  if (chatStore.waitStartTime || chatStore.initStartTime) {
    _ensureTimer()
  }

  // 恢复聊天轮询
  if (chatStore.loading && chatStore.chatTaskId) {
    startChatPolling(chatStore.chatTaskId)
  }

  // 恢复初始化轮询
  if (chatStore.initializing && chatStore.initTaskId) {
    startInitPolling(chatStore.initTaskId)
  }

  nextTick(() => scrollBottom())
})

onUnmounted(() => {
  stopInitPolling()
  stopChatPolling()
  if (_timerHandle) { clearInterval(_timerHandle); _timerHandle = null }
})
</script>

<style scoped>
/* ========== 整体布局 ========== */
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f7f7f8;
}

/* ========== 顶部栏 ========== */
.chat-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  background: #fff;
  border-bottom: 1px solid #e5e5e5;
  flex-shrink: 0;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.topbar-title {
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-dot.ready { background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.4); }
.status-dot.loading { background: #f59e0b; animation: pulse-dot 1.5s infinite; }
.status-dot.idle { background: #d1d5db; }

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.topbar-actions {
  display: flex;
  gap: 0.25rem;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.15s;
}

.icon-btn:hover:not(:disabled) { background: #f3f4f6; color: #374151; }
.icon-btn:disabled { opacity: 0.35; cursor: not-allowed; }

/* ========== 消息区域 ========== */
.chat-body {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}

/* --- 空状态 --- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 0.75rem;
  padding: 2rem;
  text-align: center;
}

.empty-icon { color: #d1d5db; }
.empty-title { font-size: 1.25rem; font-weight: 600; color: #1a1a1a; margin: 0.5rem 0 0; }
.empty-desc { color: #6b7280; font-size: 0.9rem; margin: 0; max-width: 400px; }

.empty-action { margin-top: 0.5rem; }

.init-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.5rem;
  background: #1a1a1a;
  color: white;
  border: none;
  border-radius: 24px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s;
}
.init-btn:hover:not(:disabled) { background: #333; }
.init-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: center;
  margin-top: 1rem;
  max-width: 600px;
}

.suggestion-chip {
  padding: 0.45rem 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  background: white;
  color: #374151;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}
.suggestion-chip:hover { border-color: #1a1a1a; background: #f9fafb; }

/* --- 初始化中覆盖层 --- */
.init-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
}

.init-card {
  text-align: center;
  padding: 2.5rem;
  background: white;
  border-radius: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.init-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #1a1a1a;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin { to { transform: rotate(360deg); } }

.init-text { color: #374151; font-size: 0.9rem; margin: 0; }
.init-elapsed { color: #9ca3af; font-size: 0.8rem; margin: 0.5rem 0 0; }

/* --- 消息列表 --- */
.messages {
  max-width: 768px;
  margin: 0 auto;
  padding: 1.5rem 1rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.msg {
  display: flex;
  gap: 0.75rem;
}

.msg.user { flex-direction: row-reverse; }

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.msg-avatar.ai { background: #e8e8ec; color: #5b5b6e; }
.msg-avatar.user { background: #1a1a1a; color: white; }

.msg-content {
  max-width: 85%;
  min-width: 0;
}

.msg.user .msg-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.msg-text {
  font-size: 0.9rem;
  line-height: 1.7;
  color: #1a1a1a;
  word-break: break-word;
}

.msg.user .msg-text {
  background: #1a1a1a;
  color: #f0f0f0;
  padding: 0.65rem 1rem;
  border-radius: 18px 18px 4px 18px;
}

/* --- 系统消息 --- */
.system-msg {
  width: 100%;
  text-align: center;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  font-size: 0.82rem;
}

.system-msg.info { color: #6b7280; background: #f3f4f6; }
.system-msg.success { color: #15803d; background: #dcfce7; }
.system-msg.error { color: #b91c1c; background: #fee2e2; }

/* --- 消息元信息 --- */
.msg-footer {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.4rem;
  padding-left: 0.25rem;
}

.meta-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  color: #9ca3af;
}

.ref-files {
  margin-top: 0.5rem;
}

.ref-files summary {
  font-size: 0.78rem;
  color: #6b7280;
  cursor: pointer;
  user-select: none;
  outline: none;
}

.ref-files summary:hover { color: #374151; }

.ref-list {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  margin-top: 0.3rem;
  padding: 0.5rem;
  background: #f9fafb;
  border-radius: 6px;
}

.ref-list code {
  font-size: 0.75rem;
  color: #6b7280;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
}

/* --- 代码块 --- */
.msg-text :deep(.code-block) {
  margin: 0.75rem 0;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e2e;
}

.msg-text :deep(.code-header) {
  padding: 0.35rem 0.75rem;
  background: #181825;
  font-size: 0.72rem;
  color: #a6adc8;
}

.msg-text :deep(.code-block code) {
  display: block;
  padding: 0.75rem 1rem;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #cdd6f4;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  overflow-x: auto;
  background: transparent;
  padding: revert;
}

.msg-text :deep(.inline-code) {
  background: #f0f0f2;
  padding: 0.15rem 0.35rem;
  border-radius: 4px;
  font-size: 0.84em;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  color: #c7254e;
}

.msg-text :deep(strong) { font-weight: 600; }

/* --- 思考中 --- */
.thinking-block {
  display: flex;
  align-items: flex-start;
  gap: 0.6rem;
  padding: 0.5rem 0;
  min-height: 40px;
}

.thinking-dots {
  display: flex;
  gap: 3px;
  padding-top: 4px;
}

.thinking-info {
  flex: 1;
  min-width: 0;
}

.thinking-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9ca3af;
  animation: dot-bounce 1.4s ease-in-out infinite both;
}

.thinking-dots span:nth-child(1) { animation-delay: 0s; }
.thinking-dots span:nth-child(2) { animation-delay: 0.16s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.thinking-text {
  font-size: 0.85rem;
  color: #9ca3af;
  display: block;
}

/* --- Agent 链路 --- */
.thinking-chain {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.3rem;
  flex-wrap: wrap;
}

.chain-item {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.72rem;
  padding: 0.1rem 0.45rem;
  border-radius: 6px;
  background: #f3f4f6;
  color: #6b7280;
}

.chain-item.completed {
  background: #dcfce7;
  color: #15803d;
}

.chain-item.running {
  background: #fef3c7;
  color: #92400e;
  animation: pulse-bg 1.5s infinite;
}

.chain-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
}

.chain-arrow {
  color: #d1d5db;
  flex-shrink: 0;
}

@keyframes pulse-bg {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.thinking-steps {
  margin-top: 0.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.thinking-step {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.75rem;
  color: #9ca3af;
}

.thinking-step.running { color: #6b7280; }
.thinking-step.completed { color: #15803d; }
.thinking-step.failed { color: #b91c1c; }

.step-dot-sm {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.step-text {
  flex-shrink: 0;
  font-weight: 500;
}

.step-detail-inline {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #b0b0b8;
  font-size: 0.7rem;
}

.thinking-step.running .step-dot-sm { animation: pulse-dot 1s infinite; }

.thinking-timer {
  font-size: 0.75rem;
  color: #d1d5db;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  padding-top: 4px;
}

/* --- Agent 标签 --- */
.agent-tag {
  display: inline-block;
  font-size: 0.7rem;
  color: #6366f1;
  background: #eef2ff;
  padding: 0.1rem 0.5rem;
  border-radius: 10px;
  margin-bottom: 0.3rem;
  font-weight: 500;
}

/* --- 步骤链路 --- */
.step-chain {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #f9fafb;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: #6b7280;
}

.step-item.completed { color: #15803d; }
.step-item.failed { color: #b91c1c; }

.step-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d1d5db;
  flex-shrink: 0;
}

.step-item.completed .step-dot { background: #22c55e; }
.step-item.failed .step-dot { background: #ef4444; }

.step-name {
  font-weight: 500;
  min-width: 70px;
}

.step-detail {
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== 输入区 ========== */
.chat-input-area {
  padding: 0.75rem 1rem 1rem;
  background: #f7f7f8;
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 0.5rem 0.5rem 0.5rem 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-wrapper:focus-within {
  border-color: #1a1a1a;
  box-shadow: 0 0 0 2px rgba(26,26,26,0.08);
}

.input-wrapper textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 0.9rem;
  font-family: inherit;
  line-height: 1.5;
  padding: 0.35rem 0;
  max-height: 200px;
  background: transparent;
  color: #1a1a1a;
}

.input-wrapper textarea::placeholder { color: #9ca3af; }
.input-wrapper textarea:disabled { opacity: 0.5; cursor: not-allowed; }

.send-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: #e5e7eb;
  color: #9ca3af;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.send-btn.active { background: #1a1a1a; color: white; }
.send-btn.active:hover { background: #333; }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.input-hint {
  text-align: center;
  font-size: 0.72rem;
  color: #9ca3af;
  margin: 0.5rem 0 0;
}
</style>
