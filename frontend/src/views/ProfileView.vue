<template>
  <div class="profile-page">
    <div class="page-header">
      <h2>个人资料</h2>
      <button v-if="!isEditing" @click="isEditing = true" class="btn btn-primary">编辑</button>
      <div v-else class="btn-group">
        <button @click="handleSave" class="btn btn-primary" :disabled="saving">保存</button>
        <button @click="handleCancel" class="btn btn-secondary">取消</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="error" class="error-card">
      <p>{{ error }}</p>
      <button @click="loadUser" class="btn btn-primary">重试</button>
    </div>

    <div v-else-if="user" class="profile-card">
      <div class="avatar-section">
        <div class="avatar">{{ user.username?.charAt(0).toUpperCase() }}</div>
      </div>

      <div class="info-section">
        <div class="info-row" v-for="field in displayFields" :key="field.key">
          <label>{{ field.label }}</label>
          <template v-if="isEditing && field.editable">
            <input v-model="editForm[field.key]" :type="field.type || 'text'" />
          </template>
          <span v-else class="info-value">{{ formatField(field.key, user[field.key]) }}</span>
        </div>
      </div>

      <div class="meta-section">
        <div class="meta-item">
          <span class="meta-label">注册时间</span>
          <span class="meta-value">{{ formatDate(user.created_at) }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">更新时间</span>
          <span class="meta-value">{{ formatDate(user.updated_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { authApi, type User } from '@/api/auth'

const user = ref<User | null>(null)
const loading = ref(true)
const error = ref('')
const isEditing = ref(false)
const saving = ref(false)

const editForm = reactive({
  username: '',
  full_name: ''
})

const displayFields = [
  { key: 'username', label: '用户名', editable: true },
  { key: 'email', label: '邮箱', editable: false },
  { key: 'full_name', label: '姓名', editable: true },
  { key: 'role', label: '角色', editable: false },
  { key: 'disabled', label: '状态', editable: false }
]

const loadUser = async () => {
  loading.value = true
  error.value = ''
  try {
    user.value = await authApi.getCurrentUser()
  } catch {
    error.value = '获取用户信息失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}

const formatDate = (dateString?: string) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const formatField = (key: string, value: any) => {
  if (key === 'disabled') return value ? '已禁用' : '正常'
  if (key === 'role') {
    const roleMap: Record<string, string> = { admin: '管理员', moderator: '协管员', user: '普通用户' }
    return roleMap[value] || value
  }
  return value ?? '-'
}

const handleSave = async () => {
  if (!user.value) return
  saving.value = true
  try {
    // 优先使用 auth store 中的用户数据，避免额外 API 请求
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (authStore.user) {
      authStore.user.username = editForm.username
      authStore.user.full_name = editForm.full_name
    }
    user.value = { ...user.value, username: editForm.username, full_name: editForm.full_name }
    isEditing.value = false
  } catch {
    error.value = '保存失败'
  } finally {
    saving.value = false
  }
}

const handleCancel = () => {
  if (user.value) {
    editForm.username = user.value.username
    editForm.full_name = user.value.full_name || ''
  }
  isEditing.value = false
}

onMounted(async () => {
  await loadUser()
  if (user.value) {
    editForm.username = user.value.username
    editForm.full_name = user.value.full_name || ''
  }
})
</script>

<style scoped>
.profile-page {
  max-width: 700px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.page-header h2 {
  font-size: 1.5rem;
  color: #1a1a2e;
}

.btn-group {
  display: flex;
  gap: 0.5rem;
}

.btn {
  padding: 0.5rem 1.2rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: opacity 0.2s;
}

.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background-color: #4361ee; color: white; }
.btn-secondary { background-color: #e9ecef; color: #495057; }

.loading, .error-card {
  text-align: center;
  padding: 3rem;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.error-card p { color: #dc3545; margin-bottom: 1rem; }

.profile-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  overflow: hidden;
}

.avatar-section {
  background: linear-gradient(135deg, #4361ee, #3a0ca3);
  padding: 2rem;
  text-align: center;
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255,255,255,0.2);
  color: white;
  font-size: 2rem;
  font-weight: bold;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.info-section {
  padding: 1.5rem 2rem;
}

.info-row {
  display: flex;
  align-items: center;
  padding: 0.8rem 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-row:last-child { border-bottom: none; }

.info-row label {
  width: 100px;
  font-weight: 600;
  color: #6c757d;
  font-size: 0.9rem;
}

.info-value {
  color: #1a1a2e;
  font-size: 0.95rem;
}

.info-row input {
  flex: 1;
  padding: 0.4rem 0.6rem;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  font-size: 0.95rem;
}

.info-row input:focus {
  outline: none;
  border-color: #4361ee;
  box-shadow: 0 0 0 2px rgba(67,97,238,0.15);
}

.meta-section {
  display: flex;
  border-top: 1px solid #f0f0f0;
}

.meta-item {
  flex: 1;
  padding: 1rem 2rem;
  text-align: center;
}

.meta-label {
  display: block;
  font-size: 0.8rem;
  color: #adb5bd;
  margin-bottom: 0.25rem;
}

.meta-value {
  font-size: 0.85rem;
  color: #495057;
}
</style>
