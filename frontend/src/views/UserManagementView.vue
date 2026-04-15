<template>
  <div class="user-management">
    <div class="page-header">
      <h2>用户管理</h2>
      <button @click="loadUsers" class="btn btn-secondary">刷新</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="error" class="error-card">
      <p>{{ error }}</p>
      <button @click="loadUsers" class="btn btn-primary">重试</button>
    </div>

    <div v-else>
      <div class="summary">
        共 <strong>{{ users.length }}</strong> 个用户
      </div>

      <div class="table-wrapper">
        <table class="user-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>邮箱</th>
              <th>姓名</th>
              <th>角色</th>
              <th>状态</th>
              <th>注册时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u._id">
              <td>{{ u.username }}</td>
              <td>{{ u.email }}</td>
              <td>{{ u.full_name || '-' }}</td>
              <td>
                <span class="role-tag" :class="u.role">{{ formatRole(u.role) }}</span>
              </td>
              <td>
                <span class="status-dot" :class="u.disabled ? 'disabled' : 'active'"></span>
                {{ u.disabled ? '已禁用' : '正常' }}
              </td>
              <td>{{ formatDate(u.created_at) }}</td>
            </tr>
            <tr v-if="users.length === 0">
              <td colspan="6" class="empty-text">暂无用户数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usersApi } from '@/api/users'
import type { User } from '@/api/auth'

const users = ref<User[]>([])
const loading = ref(true)
const error = ref('')

const loadUsers = async () => {
  loading.value = true
  error.value = ''
  try {
    users.value = await usersApi.getUsers(0, 200)
  } catch {
    error.value = '获取用户列表失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}

const formatDate = (dateString?: string) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const formatRole = (role: string) => {
  const map: Record<string, string> = { admin: '管理员', moderator: '协管员', user: '普通用户' }
  return map[role] || role
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.user-management {
  max-width: 960px;
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

.btn {
  padding: 0.5rem 1.2rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: opacity 0.2s;
}

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

.summary {
  margin-bottom: 1rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.table-wrapper {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  overflow-x: auto;
}

.user-table {
  width: 100%;
  border-collapse: collapse;
}

.user-table th,
.user-table td {
  padding: 0.75rem 1.2rem;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
  font-size: 0.9rem;
}

.user-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
  white-space: nowrap;
}

.user-table tbody tr:hover {
  background: #f8f9fa;
}

.empty-text {
  text-align: center;
  color: #adb5bd;
  padding: 2rem !important;
}

.role-tag {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
}

.role-tag.admin { background: #f8d7da; color: #721c24; }
.role-tag.moderator { background: #fff3cd; color: #856404; }
.role-tag.user { background: #d1ecf1; color: #0c5460; }

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.3rem;
  vertical-align: middle;
}

.status-dot.active { background-color: #28a745; }
.status-dot.disabled { background-color: #dc3545; }
</style>
