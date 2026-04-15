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
              <div class="msg-text" v-html="renderMd(msg.content)"></div>
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
              <span class="thinking-text">{{ thinkingTip }}</span>
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
import { aiApi, type QuestionResponse } from '@/api/ai'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

// 组件本地状态
const inputText = ref('')

// 从 store 读取全局状态（切换页面后保留）
const messages = computed(() => chatStore.messages)
const loading = computed(() => chatStore.loading)
const initializing = computed(() => chatStore.initializing)
const systemReady = computed(() => chatStore.systemReady)

const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

// 等待计时
const waitElapsed = ref(0)
const initElapsed = ref(0)
let waitTimer: ReturnType<typeof setInterval> | null = null
let initTimer: ReturnType<typeof setInterval> | null = null

// 思考提示语循环
const thinkingTips = [
  '正在分析你的问题...',
  '正在检索代码库...',
  '正在构建上下文...',
  'AI 正在思考中...',
  '即将生成回答...',
]
const tipIdx = ref(0)
let tipInterval: ReturnType<typeof setInterval> | null = null

const thinkingTip = computed(() => thinkingTips[tipIdx.value % thinkingTips.length])

const initStatus = ref('正在初始化 AI 系统，加载代码库并构建索引...')

const systemStatus = computed(() => {
  if (systemReady.value) return 'ready'
  if (initializing.value) return 'loading'
  return 'idle'
})

const canSend = computed(() => !!inputText.value.trim() && !chatStore.loading && !chatStore.initializing && chatStore.systemReady)

const inputPlaceholder = computed(() => {
  if (chatStore.initializing) return '系统初始化中，请稍候...'
  if (!chatStore.systemReady) return '请先初始化系统'
  if (chatStore.loading) return '等待 AI 回复中...'
  return '输入你的问题，按 Enter 发送...'
})

const suggestions = [
  '这个项目的整体架构是什么？',
  '用户认证是如何实现的？',
  '数据库连接的配置方式？',
  'API 接口的认证机制是什么？',
]

// --- 工具函数 ---

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

// --- 计时器 ---

const startWaitTimer = () => {
  waitElapsed.value = 0
  tipIdx.value = 0
  waitTimer = setInterval(() => { waitElapsed.value++ }, 1000)
  tipInterval = setInterval(() => { tipIdx.value++ }, 4000)
}

const stopWaitTimer = () => {
  if (waitTimer) { clearInterval(waitTimer); waitTimer = null }
  if (tipInterval) { clearInterval(tipInterval); tipInterval = null }
}

const startInitTimer = () => {
  initElapsed.value = 0
  initTimer = setInterval(() => { initElapsed.value++ }, 1000)
}

const stopInitTimer = () => {
  if (initTimer) { clearInterval(initTimer); initTimer = null }
}

// --- 核心操作 ---

const checkSystem = async () => {
  try {
    const res = await aiApi.healthCheck()
    chatStore.systemReady = res.system_initialized
  } catch {
    chatStore.systemReady = false
  }
}

const handleInit = async () => {
  chatStore.initializing = true
  initStatus.value = '正在初始化 AI 系统，加载代码库并构建索引...'
  startInitTimer()

  try {
    const res = await aiApi.initialize({ force_rebuild: true })
    if (res.success) {
      chatStore.systemReady = true
      chatStore.messages.push({ role: 'system', content: `系统初始化完成 — ${res.message}`, type: 'success' })
    } else {
      chatStore.messages.push({ role: 'system', content: `初始化失败：${res.message}`, type: 'error' })
    }
  } catch (err: any) {
    const detail = err.response?.data?.detail || err.code === 'ECONNABORTED'
      ? '请求超时，服务端响应时间过长，请检查后端日志'
      : err.message || '未知错误'
    chatStore.messages.push({ role: 'system', content: `初始化异常：${detail}`, type: 'error' })
    chatStore.systemReady = false
  } finally {
    chatStore.initializing = false
    stopInitTimer()
    scrollBottom()
  }
}

const handleSend = async () => {
  const question = inputText.value.trim()
  if (!question || chatStore.loading || !chatStore.systemReady) return

  chatStore.messages.push({ role: 'user', content: question })
  inputText.value = ''
  if (inputEl.value) inputEl.value.style.height = 'auto'
  chatStore.loading = true
  startWaitTimer()
  scrollBottom()

  const requestPromise = (async () => {
    try {
      const res: QuestionResponse = await aiApi.ask({
        question,
        session_id: chatStore.sessionId || undefined,
      })
      chatStore.sessionId = res.session_id

      if (res.success) {
        chatStore.messages.push({
          role: 'assistant',
          content: res.answer || '（未生成回答内容）',
          meta: {
            processing_time: res.processing_time,
            source_files: res.source_files,
            files_count: res.files_count,
            token_usage: res.token_usage,
          },
        })
      } else {
        chatStore.messages.push({
          role: 'assistant',
          content: res.error || '回答失败，请重试',
          meta: { processing_time: res.processing_time, error: res.error },
        })
      }
    } catch (err: any) {
      const code = err.code || err.response?.status
      const detail = err.response?.data?.detail || ''

      if (code === 'ECONNABORTED') {
        chatStore.messages.push({
          role: 'system',
          content: '请求超时（5 分钟），大模型生成时间过长，请尝试简化问题或稍后重试。',
          type: 'error',
        })
      } else if (code === 503 || detail.includes('未初始化')) {
        chatStore.systemReady = false
        chatStore.messages.push({ role: 'system', content: 'AI 系统已离线，请重新初始化。', type: 'error' })
      } else {
        chatStore.messages.push({
          role: 'assistant',
          content: `请求失败：${detail || err.message || '网络错误'}`,
        })
      }
    } finally {
      chatStore.loading = false
      chatStore.setPendingRequest(null)
      stopWaitTimer()
      scrollBottom()
    }
  })()

  chatStore.setPendingRequest(requestPromise)
  await requestPromise
}

const handleClear = async () => {
  try { await aiApi.clearHistory() } catch { /* ignore */ }
  chatStore.reset()
}

onMounted(() => {
  // 仅首次挂载时检查系统状态
  if (!chatStore.systemReady) {
    checkSystem()
  }

  // 如果切回来时仍在等待回复，恢复计时器
  if (chatStore.loading) {
    startWaitTimer()
  }
  if (chatStore.initializing) {
    startInitTimer()
  }

  // 恢复滚动位置
  nextTick(() => scrollBottom())
})

onUnmounted(() => {
  // 导航离开时只停计时器，不停止请求（请求继续在后台运行）
  stopWaitTimer()
  stopInitTimer()
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
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0;
}

.thinking-dots {
  display: flex;
  gap: 3px;
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
}

.thinking-timer {
  margin-left: auto;
  font-size: 0.75rem;
  color: #d1d5db;
  font-variant-numeric: tabular-nums;
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
