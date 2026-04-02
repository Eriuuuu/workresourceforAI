<template>
  <div class="register-container">
    <div class="register-form">
      <h2>注册账号</h2>
      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            required
            :disabled="isLoading"
            placeholder="请输入用户名"
          />
        </div>
        
        <div class="form-group">
          <label for="email">邮箱</label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            required
            :disabled="isLoading"
            placeholder="请输入邮箱"
          />
        </div>
        
        <div class="form-group">
          <label for="full_name">姓名</label>
          <input
            id="full_name"
            v-model="form.full_name"
            type="text"
            :disabled="isLoading"
            placeholder="请输入姓名（可选）"
          />
        </div>
        
        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            required
            :disabled="isLoading"
            placeholder="请输入密码"
          />
        </div>
        
        <div class="form-group">
          <label for="confirm_password">确认密码</label>
          <input
            id="confirm_password"
            v-model="form.confirm_password"
            type="password"
            required
            :disabled="isLoading"
            placeholder="请再次输入密码"
          />
        </div>
        
        <button 
          type="submit" 
          :disabled="isLoading || !isFormValid"
          class="register-button"
        >
          {{ isLoading ? '注册中...' : '注册' }}
        </button>
        
        <div v-if="error" class="error-message">
          {{ error }}
        </div>
      </form>
      
      <p class="login-link">
        已有账号？<router-link to="/login">立即登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { authApi, type RegisterRequest } from '@/api/auth'
import { formatError } from '@/utils'

const router = useRouter()

const form = reactive({
  username: '',
  email: '',
  full_name: '',
  password: '',
  confirm_password: ''
})

const isLoading = ref(false)
const error = ref('')

const isFormValid = computed(() => {
  return form.username && 
         form.email && 
         form.password && 
         form.confirm_password && 
         form.password === form.confirm_password
})

const handleRegister = async () => {
  if (form.password !== form.confirm_password) {
    error.value = '两次输入的密码不一致'
    return
  }

  try {
    isLoading.value = true
    error.value = ''
    
    const registerData: RegisterRequest = {
      username: form.username,
      email: form.email,
      full_name: form.full_name || undefined,
      password: form.password
    }
    
    await authApi.register(registerData)
    
    // 注册成功，跳转到登录页
    router.push({ 
      name: 'login', 
      query: { registered: 'true' } 
    })
  } catch (err: any) {
    error.value = formatError(err)
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: $background-color;
}

.register-form {
  background: white;
  padding: 2rem;
  border-radius: $border-radius-lg;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 450px;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
  color: $text-color;
}

input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid $border-color;
  border-radius: $border-radius;
  font-size: 1rem;
  transition: border-color 0.3s;
  
  &:focus {
    outline: none;
    border-color: $primary-color;
    box-shadow: 0 0 0 2px rgba($primary-color, 0.2);
  }
  
  &:disabled {
    background-color: $background-color;
    cursor: not-allowed;
  }
}

.register-button {
  width: 100%;
  padding: 0.75rem;
  background-color: $primary-color;
  color: white;
  border: none;
  border-radius: $border-radius;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.3s;
  
  &:hover:not(:disabled) {
    background-color: darken($primary-color, 10%);
  }
  
  &:disabled {
    background-color: $border-color;
    cursor: not-allowed;
  }
}

.error-message {
  color: $error-color;
  margin-top: 1rem;
  text-align: center;
  padding: 0.75rem;
  background-color: rgba($error-color, 0.1);
  border-radius: $border-radius;
}

.login-link {
  text-align: center;
  margin-top: 1.5rem;
  color: $text-color-secondary;
}
</style>