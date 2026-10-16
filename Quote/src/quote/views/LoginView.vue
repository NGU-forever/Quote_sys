<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { LogIn, Lock, RefreshCw, Server, User, WifiOff } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { describeLoginError } from '../../shared/auth/session'
import { getBackendBase, setBackendBase } from '../../shared/utils/backendConfig'
import { discoverAndSetHost } from '../../shared/utils/discovery'
import { useToast } from '../../shared/composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

// 主设备可能不在默认地址：支持自动发现或手填，否则员工在第一屏就卡住。
const showServer = ref(false)
const serverUrl = ref(getBackendBase())
const discovering = ref(false)
const testing = ref(false)
const testResult = ref('')

async function submit() {
  error.value = ''
  if (!form.username.trim() || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    const name = await auth.login(form.username.trim(), form.password)
    toast.push(`欢迎回来，${name}`, 'success')
    router.replace({ name: 'landing' })
  } catch (err) {
    error.value = describeLoginError(err)
  } finally {
    loading.value = false
  }
}

function useOffline() {
  const ok = confirm(
    '离线使用将不连接主设备：可以正常算价、打印和保存本地草稿，' +
      '但拿不到官方单号，报价单也不会进入工作台的报价中心。确定继续吗？'
  )
  if (!ok) return
  auth.continueOffline()
  toast.push('已切换为离线使用（本地草稿模式）', 'info')
  router.replace({ name: 'landing' })
}

async function discover() {
  discovering.value = true
  testResult.value = ''
  try {
    const host = await discoverAndSetHost()
    if (host) {
      serverUrl.value = host
      testResult.value = `已发现主设备：${host}`
    } else {
      testResult.value = '未发现主设备，请确认主设备已开机，或手动填写地址'
    }
  } finally {
    discovering.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = ''
  const base = serverUrl.value.trim().replace(/\/+$/, '')
  try {
    const res = await fetch(`${base}/api/health`)
    const body = await res.json().catch(() => ({}))
    if (res.ok && body.ok) {
      testResult.value = '连接成功'
    } else {
      testResult.value = '连接失败：服务响应异常'
    }
  } catch {
    testResult.value = '连接失败：无法访问该地址，请检查地址与网络'
  } finally {
    testing.value = false
  }
}

function saveServer() {
  serverUrl.value = setBackendBase(serverUrl.value)
  toast.push('主设备地址已保存', 'success')
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-head">
        <div class="login-mark"><Lock :size="22" /></div>
        <h1>销售端登录</h1>
        <p>使用管理员为你开通的员工账号登录，开单后可取得官方单号</p>
      </div>

      <form class="login-form" @submit.prevent="submit">
        <div class="field">
          <label for="login-username">用户名</label>
          <div class="input-wrap">
            <User :size="16" />
            <input
              id="login-username"
              v-model="form.username"
              class="input"
              type="text"
              placeholder="请输入员工账号"
              autocomplete="username"
            />
          </div>
        </div>

        <div class="field">
          <label for="login-password">密码</label>
          <div class="input-wrap">
            <Lock :size="16" />
            <input
              id="login-password"
              v-model="form.password"
              class="input"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
          </div>
        </div>

        <p v-if="error" class="login-error" role="alert">{{ error }}</p>

        <button class="btn btn-primary login-submit" type="submit" :disabled="loading">
          <LogIn :size="16" />
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <div class="login-server">
        <button class="server-toggle" type="button" @click="showServer = !showServer">
          <Server :size="14" />
          {{ showServer ? '收起' : '主设备地址' }}（当前：{{ getBackendBase() }}）
        </button>

        <div v-if="showServer" class="server-panel">
          <button
            class="btn btn-soft btn-sm"
            type="button"
            :disabled="discovering"
            @click="discover"
          >
            <RefreshCw :size="14" />
            {{ discovering ? '搜索中…' : '自动发现主设备' }}
          </button>
          <input
            v-model="serverUrl"
            class="input"
            type="text"
            placeholder="http://192.168.1.100:8000"
            aria-label="主设备地址"
          />
          <div class="server-actions">
            <button class="btn btn-sm" type="button" :disabled="testing" @click="test">
              {{ testing ? '测试中…' : '测试连接' }}
            </button>
            <button class="btn btn-primary btn-sm" type="button" @click="saveServer">保存</button>
          </div>
          <p v-if="testResult" class="server-result">{{ testResult }}</p>
        </div>
      </div>

      <div class="login-foot">
        <button class="offline-link" type="button" @click="useOffline">
          <WifiOff :size="14" />
          主设备不在线？离线使用（无官方单号）
        </button>
        <p class="login-hint">还没有账号？请让管理员在工作台「员工管理」中开通。</p>
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
    var(--bg-alt, #f8fafc);
}

.login-card {
  width: min(400px, 100%);
  padding: 32px;
  background: #fff;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 16px;
  box-shadow: var(--shadow, 0 18px 50px -30px rgba(13, 71, 161, 0.35));
}

.login-head {
  text-align: center;
  margin-bottom: 24px;
}

.login-mark {
  width: 48px;
  height: 48px;
  margin: 0 auto 14px;
  border-radius: 13px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, var(--primary, #1e88e5), var(--accent, #64b5f6));
  box-shadow: 0 14px 26px -14px rgba(30, 136, 229, 0.8);
}

.login-head h1 {
  font-size: 22px;
  font-weight: 800;
  color: var(--text, #1a1a2e);
}

.login-head p {
  color: var(--muted, #64748b);
  font-size: 13px;
  margin-top: 6px;
  line-height: 1.6;
}

.login-form {
  display: grid;
  gap: 16px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label {
  color: var(--muted, #64748b);
  font-size: 12px;
  font-weight: 700;
}

.input-wrap {
  position: relative;
}

.input-wrap svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted, #64748b);
}

.input-wrap .input {
  padding-left: 38px;
}

.login-error {
  color: var(--rose, #be123c);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.6;
}

.login-submit {
  width: 100%;
}

.login-server {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed var(--border, #e2e8f0);
}

.server-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted, #64748b);
  font-size: 12.5px;
  font-weight: 600;
  background: none;
  border: none;
  cursor: pointer;
}

.server-toggle:hover {
  color: var(--primary-dark, #0d47a1);
}

.server-panel {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  padding: 12px;
  background: var(--bg-alt, #f8fafc);
  border-radius: 10px;
}

.server-actions {
  display: flex;
  gap: 8px;
}

.server-result {
  color: var(--primary-dark, #0d47a1);
  font-size: 12px;
  font-weight: 600;
}

.login-foot {
  margin-top: 18px;
  text-align: center;
}

.offline-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted, #64748b);
  font-size: 12.5px;
  font-weight: 600;
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

.offline-link:hover {
  color: var(--amber, #b45309);
}

.login-hint {
  color: var(--muted, #64748b);
  font-size: 11.5px;
  margin-top: 10px;
  line-height: 1.6;
}
</style>
