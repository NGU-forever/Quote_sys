<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LogIn, Lock, Server, User, UserPlus } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../../shared/composables/useToast'
import { getBackendBase, setBackendBase } from '../../shared/utils/backendConfig'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToast()

const form = reactive({ username: '', password: '', confirmPassword: '' })
const checking = ref(true)
const needsRegistration = ref(false)
const loading = ref(false)
const error = ref('')

// ---- 服务器地址设置（后端可能部署在远程服务器，桌面版启动时据此同步目录与图片） ----
const showServer = ref(false)
const serverUrl = ref(getBackendBase())
const testing = ref(false)
const testResult = ref('')

onMounted(checkSetupStatus)

async function checkSetupStatus() {
  checking.value = true
  error.value = ''
  try {
    const { registered } = await auth.fetchSetupStatus()
    needsRegistration.value = !registered
  } catch (err) {
    error.value = err.message || '无法读取账号状态，请确认后端服务已启动'
  } finally {
    checking.value = false
  }
}

function saveServer() {
  const base = setBackendBase(serverUrl.value)
  serverUrl.value = base
  toast.push('服务器地址已保存，重新打开或刷新后生效')
}

async function testServer() {
  testing.value = true
  testResult.value = ''
  try {
    const base = serverUrl.value.trim().replace(/\/+$/, '')
    const res = await fetch(`${base}/api/health`)
    const body = await res.json().catch(() => ({}))
    if (res.ok && body.ok) {
      testResult.value = `连接成功（${new Date(body.time).toLocaleString()}）`
    } else {
      testResult.value = '连接失败：服务响应异常'
    }
  } catch {
    testResult.value = '连接失败：无法访问该地址，请检查服务器地址与网络'
  } finally {
    testing.value = false
  }
}

async function submit() {
  error.value = ''
  if (checking.value) return
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  if (needsRegistration.value && form.password !== form.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    if (needsRegistration.value) {
      await auth.register(form.username, form.password)
      toast.push('账号注册成功')
    } else {
      await auth.login(form.username, form.password)
      toast.push('登录成功')
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/workbench/devices'
    router.push(redirect)
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-head">
        <div class="login-mark">
          <component :is="needsRegistration ? UserPlus : Lock" :size="22" />
        </div>
        <h1>{{ needsRegistration ? '注册工作台账号' : '工作台登录' }}</h1>
        <p>
          {{ checking ? '正在检查账号状态…' : needsRegistration ? '首次使用需先设置工作台账号' : '登录后可管理设备、耗材与套餐' }}
        </p>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <div class="field">
          <label>{{ needsRegistration ? '工作台账号' : '用户名' }}</label>
          <div class="input-wrap">
            <User :size="16" />
            <input
              v-model="form.username"
              class="input"
              type="text"
              placeholder="请输入用户名"
              :disabled="checking"
              autocomplete="username"
            />
          </div>
        </div>
        <div class="field">
          <label>密码</label>
          <div class="input-wrap">
            <Lock :size="16" />
            <input
              v-model="form.password"
              class="input"
              type="password"
              placeholder="请输入密码"
              :disabled="checking"
              :autocomplete="needsRegistration ? 'new-password' : 'current-password'"
            />
          </div>
        </div>
        <div v-if="needsRegistration" class="field">
          <label>确认密码</label>
          <div class="input-wrap">
            <Lock :size="16" />
            <input
              v-model="form.confirmPassword"
              class="input"
              type="password"
              placeholder="请再次输入密码"
              autocomplete="new-password"
            />
          </div>
        </div>

        <p v-if="error" class="login-error">{{ error }}</p>

        <button class="btn btn-primary login-submit" type="submit" :disabled="checking || loading">
          <component :is="needsRegistration ? UserPlus : LogIn" :size="16" />
          {{
            loading
              ? '处理中…'
              : checking
                ? '正在检查…'
                : needsRegistration
                  ? '注册并进入工作台'
                  : '登录'
          }}
        </button>
      </form>

      <div class="login-server">
        <button class="server-toggle" type="button" @click="showServer = !showServer">
          <Server :size="14" />
          {{ showServer ? '收起' : '服务器设置' }}（当前：{{ getBackendBase() }}）
        </button>

        <div v-if="showServer" class="server-panel">
          <label class="server-label">后端服务器地址</label>
          <div class="server-row">
            <input v-model="serverUrl" class="input" type="text" placeholder="http://192.168.1.100:8000 或 https://域名" />
          </div>
          <div class="server-actions">
            <button class="btn btn-soft btn-sm" type="button" :disabled="testing" @click="testServer">
              {{ testing ? '测试中…' : '测试连接' }}
            </button>
            <button class="btn btn-primary btn-sm" type="button" @click="saveServer">保存</button>
          </div>
          <p v-if="testResult" class="server-result">{{ testResult }}</p>
          <p class="server-note">
            后端部署在服务器时，在此填写服务器地址；启动时会自动把服务器上传的产品图片同步到本机缓存。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(227, 242, 253, 0.85)),
    var(--bg-alt);
}

.login-card {
  position: relative;
  width: min(400px, 100%);
  padding: 32px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow);
}

.login-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}

.login-back:hover {
  color: var(--primary-dark);
}

.login-head {
  text-align: center;
  margin: 18px 0 24px;
}

.login-mark {
  width: 48px;
  height: 48px;
  margin: 0 auto 14px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  box-shadow: 0 14px 26px -14px rgba(30, 136, 229, 0.8);
}

.login-head h1 {
  font-size: 22px;
  font-weight: 800;
}

.login-head p {
  color: var(--muted);
  font-size: 13px;
  margin-top: 6px;
}

.login-form {
  display: grid;
  gap: 16px;
}

.input-wrap {
  position: relative;
}

.input-wrap svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.input-wrap .input {
  padding-left: 38px;
}

.login-error {
  color: var(--rose);
  font-size: 13px;
  font-weight: 600;
}

.login-submit {
  width: 100%;
}

.login-server {
  margin-top: 18px;
  border-top: 1px dashed var(--border);
  padding-top: 14px;
}

.server-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12.5px;
  font-weight: 600;
}

.server-toggle:hover {
  color: var(--primary-dark);
}

.server-panel {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  padding: 12px;
  background: var(--bg-alt);
  border-radius: 10px;
}

.server-label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.server-row .input {
  width: 100%;
}

.server-actions {
  display: flex;
  gap: 8px;
}

.server-result {
  color: var(--primary-dark);
  font-size: 12px;
  font-weight: 600;
}

.server-note {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}
</style>
