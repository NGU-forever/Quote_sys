<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  AlertTriangle, Bot, Building2, CheckCircle2, Copy, KeyRound,
  Plus, RefreshCw, Save, Settings, Trash2, Wifi, XCircle
} from 'lucide-vue-next'
import { api } from '../api/workbenchClient'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../../shared/composables/useToast'

const auth = useAuthStore()
const toast = useToast()
const loading = ref(false)
const saving = ref(false)
const adminMode = ref(false)
const accountUsers = ref([])
const accountsLoading = ref(false)
const passwordLoading = ref(false)
const passwordForm = reactive({ username: '', newPassword: '', confirmPassword: '' })
const netLoading = ref(false)
const netData = ref(null)
const aiSaving = ref(false)
const aiForm = reactive({
  provider: 'auto',
  base_url: '',
  model: '',
  api_key: '',
  max_steps: 20,
  default_mode: 'apply',
  has_api_key: false,
  api_key_masked: '',
  clear_api_key: false
})

const form = reactive({
  company: { name: '', phone: '', email: '', address: '' },
  pricing: {
    devicePrice: 0,
    bagsPerBox: 0,
    giftRatio: 0,
    plan2UnitPrice: 0,
    plan2MinBoxes: 0,
    quoteValidityDays: 0,
    quotePrefix: 'Q',
    plan1Tiers: []
  }
})

onMounted(async () => {
  await Promise.all([load(), loadAccountPanel(), loadAgentConfig(), loadNetworkDiagnostics()])
})

async function loadNetworkDiagnostics() {
  netLoading.value = true
  try {
    const data = await api.getNetworkDiagnostics()
    netData.value = data
  } catch {
    /* 网络诊断非关键路径，静默失败 */
  } finally {
    netLoading.value = false
  }
}

async function copyUrl(url) {
  try {
    await navigator.clipboard.writeText(url)
    toast.push('已复制到剪贴板', 'success')
  } catch {
    toast.push('复制失败，请手动复制', 'info')
  }
}

async function loadAccountPanel() {
  accountsLoading.value = true
  try {
    await auth.fetchMe()
    adminMode.value = auth.user?.username === 'admin'
    if (!adminMode.value) return
    const { users } = await api.accounts()
    accountUsers.value = users || []
    passwordForm.username = accountUsers.value[0]?.username || ''
  } catch (err) {
    toast.push(err.message || '读取账号信息失败', 'info')
  } finally {
    accountsLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.getSettings()
    if (data) {
      form.company = { ...form.company, ...(data.company || {}) }
      form.pricing = { ...form.pricing, ...(data.pricing || {}) }
      form.pricing.plan1Tiers = (data.pricing?.plan1Tiers || []).map((t) => ({ ...t }))
    }
  } catch (err) {
    toast.push(err.message || '读取设置失败', 'info')
  } finally {
    loading.value = false
  }
}

async function loadAgentConfig() {
  try {
    const { data } = await api.getAgentConfig()
    Object.assign(aiForm, {
      provider: data.provider || 'auto',
      base_url: data.base_url || '',
      model: data.model || '',
      max_steps: data.max_steps || 20,
      default_mode: data.default_mode || 'apply',
      has_api_key: Boolean(data.has_api_key),
      api_key_masked: data.api_key_masked || '',
      api_key: '',
      clear_api_key: false
    })
  } catch (err) {
    toast.push(err.message || '读取 AI 配置失败', 'info')
  }
}

async function saveAgentConfig() {
  if (!aiForm.base_url.trim() && aiForm.provider !== 'mock') {
    toast.push('请填写 API 接口地址', 'info')
    return
  }
  if (!aiForm.model.trim() && aiForm.provider !== 'mock') {
    toast.push('请填写模型名称', 'info')
    return
  }
  const payload = {
    provider: aiForm.provider,
    base_url: aiForm.base_url.trim(),
    model: aiForm.model.trim(),
    max_steps: Number(aiForm.max_steps) || 20,
    default_mode: aiForm.default_mode
  }
  if (aiForm.clear_api_key) {
    payload.api_key = ''
  } else if (aiForm.api_key.trim()) {
    payload.api_key = aiForm.api_key.trim()
  }
  aiSaving.value = true
  try {
    await api.saveAgentConfig(payload)
    toast.push('AI 模型配置已保存', 'success')
    await loadAgentConfig()
  } catch (err) {
    toast.push(err.message || '保存 AI 配置失败', 'info')
  } finally {
    aiSaving.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const pricing = {
      ...form.pricing,
      devicePrice: Number(form.pricing.devicePrice) || 0,
      bagsPerBox: Number(form.pricing.bagsPerBox) || 0,
      giftRatio: Number(form.pricing.giftRatio) || 0,
      plan2UnitPrice: Number(form.pricing.plan2UnitPrice) || 0,
      plan2MinBoxes: Number(form.pricing.plan2MinBoxes) || 0,
      quoteValidityDays: Number(form.pricing.quoteValidityDays) || 0,
      plan1Tiers: form.pricing.plan1Tiers
        .filter((t) => t.minBoxes !== '' && t.minBoxes !== null)
        .map((t) => ({
          minBoxes: Number(t.minBoxes) || 0,
          price: Number(t.price) || 0,
          label: t.label || ''
        }))
    }
    await api.updateSettings({ company: form.company, pricing })
    toast.push('设置已保存', 'success')
  } catch (err) {
    toast.push(err.message || '保存失败', 'info')
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  if (!passwordForm.username) {
    toast.push('请先选择需要重置的正式账号', 'info')
    return
  }
  if (passwordForm.newPassword.length < 6) {
    toast.push('新密码至少 6 位', 'info')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    toast.push('两次输入的密码不一致', 'info')
    return
  }
  passwordLoading.value = true
  try {
    await api.resetPassword(passwordForm.username, passwordForm.newPassword)
    toast.push('正式账号密码已重置', 'success')
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch (err) {
    toast.push(err.message || '重置密码失败', 'info')
  } finally {
    passwordLoading.value = false
  }
}

function addTier() {
  form.pricing.plan1Tiers.push({ minBoxes: 1, price: 0, label: '' })
}

function removeTier(index) {
  form.pricing.plan1Tiers.splice(index, 1)
}
</script>

<template>
  <div class="wb-page">
    <div class="wb-page-head">
      <div class="wb-page-title-row">
        <div class="wb-head-chip settings">
          <Settings :size="18" />
        </div>
        <div>
          <h1 class="wb-page-title">基本设置</h1>
          <p class="wb-page-sub">公司信息、报价参数与 AI 模型接口</p>
        </div>
      </div>
      <button class="btn btn-primary" :disabled="saving || loading" @click="save">
        <Save :size="16" />
        {{ saving ? '保存中…' : '保存设置' }}
      </button>
    </div>

    <div v-if="loading" class="wb-empty">加载中…</div>

    <div v-else class="settings-cards">
      <section class="settings-card">
        <div class="settings-card-head">
          <div class="settings-card-icon network"><Wifi :size="16" /></div>
          <h2>网络与连接</h2>
          <button
            class="btn btn-soft btn-sm net-refresh"
            type="button"
            :disabled="netLoading"
            @click="loadNetworkDiagnostics"
          >
            <RefreshCw :size="14" :class="{ spinning: netLoading }" />
            {{ netLoading ? '检测中…' : '刷新' }}
          </button>
        </div>

        <div v-if="netLoading && !netData" class="wb-empty">正在检测网络状态…</div>
        <template v-else-if="netData">
          <!-- 防火墙状态 -->
          <div v-if="netData.firewall?.supported" class="net-status-row">
            <div class="net-status-indicator" :class="netData.firewall.status">
              <CheckCircle2 v-if="netData.firewall.status === 'ok' || netData.firewall.status === 'off'" :size="16" />
              <AlertTriangle v-else-if="netData.firewall.status === 'warning'" :size="16" />
              <XCircle v-else :size="16" />
            </div>
            <div class="net-status-text">
              <strong>防火墙</strong>
              <span>{{ netData.firewall.message }}</span>
            </div>
          </div>

          <!-- 本机局域网 IP -->
          <div class="net-ip-section">
            <label>客户端连接地址（复制给报价设备使用）</label>
            <div v-if="netData.server.connect_urls.length" class="net-url-list">
              <div v-for="url in netData.server.connect_urls" :key="url" class="net-url-chip">
                <code>{{ url }}</code>
                <button class="net-copy-btn" type="button" title="复制" @click="copyUrl(url)">
                  <Copy :size="13" />
                </button>
              </div>
            </div>
            <p v-else class="wb-empty">未检测到局域网 IP 地址</p>
          </div>

          <!-- 所有接口列表 -->
          <details class="net-details">
            <summary>所有网络接口（{{ netData.interfaces.length }}）</summary>
            <div class="net-iface-list">
              <div v-for="iface in netData.interfaces" :key="iface.ip" class="net-iface-row">
                <span class="net-iface-name">{{ iface.name || '未知' }}</span>
                <code class="net-iface-ip" :class="{ lan: iface.is_lan }">{{ iface.ip }}</code>
                <span v-if="iface.netmask" class="net-iface-mask">/ {{ iface.netmask }}</span>
                <span v-if="iface.is_lan" class="net-lan-badge">局域网</span>
              </div>
            </div>
          </details>

          <p class="host-note">
            客户端（报价设备）通过上述地址连接主设备。若客户端找不到主设备，请确认两台设备在同一 Wi-Fi 下，
            且防火墙状态为绿色。也可在客户端手动填写上方地址。
          </p>
        </template>
        <div v-else class="wb-empty">网络诊断暂不可用</div>
      </section>

      <section class="settings-card">
        <div class="settings-card-head">
          <div class="settings-card-icon"><Building2 :size="16" /></div>
          <h2>公司信息</h2>
        </div>
        <div class="wb-form">
          <div class="wb-form-row full">
            <label>公司名称</label>
            <input v-model="form.company.name" class="input" type="text" />
          </div>
          <div class="wb-form-row">
            <label>电话</label>
            <input v-model="form.company.phone" class="input" type="text" />
          </div>
          <div class="wb-form-row">
            <label>邮箱</label>
            <input v-model="form.company.email" class="input" type="text" />
          </div>
          <div class="wb-form-row full">
            <label>地址</label>
            <input v-model="form.company.address" class="input" type="text" />
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="settings-card-head">
          <div class="settings-card-icon"><Settings :size="16" /></div>
          <h2>报价参数</h2>
        </div>
        <div class="wb-form">
          <div class="wb-form-row">
            <label>设备价（元）</label>
            <input v-model="form.pricing.devicePrice" class="input" type="number" min="0" step="0.01" />
          </div>
          <div class="wb-form-row">
            <label>每盒袋数</label>
            <input v-model="form.pricing.bagsPerBox" class="input" type="number" min="0" />
          </div>
          <div class="wb-form-row">
            <label>赠送比例（%）</label>
            <input v-model="form.pricing.giftRatio" class="input" type="number" min="0" step="0.01" />
          </div>
          <div class="wb-form-row">
            <label>方案二单价（元）</label>
            <input v-model="form.pricing.plan2UnitPrice" class="input" type="number" min="0" step="0.01" />
          </div>
          <div class="wb-form-row">
            <label>方案二最低箱数</label>
            <input v-model="form.pricing.plan2MinBoxes" class="input" type="number" min="0" />
          </div>
          <div class="wb-form-row">
            <label>报价有效期（天）</label>
            <input v-model="form.pricing.quoteValidityDays" class="input" type="number" min="0" />
          </div>
          <div class="wb-form-row">
            <label>报价单号前缀</label>
            <input v-model="form.pricing.quotePrefix" class="input" type="text" />
          </div>
        </div>

        <div class="tiers-block">
          <div class="tiers-head">
            <label>方案一档位（按箱数分档计价）</label>
            <button class="btn btn-soft btn-sm" type="button" @click="addTier">
              <Plus :size="14" />
              新增档位
            </button>
          </div>
          <div v-for="(tier, i) in form.pricing.plan1Tiers" :key="i" class="tier-row">
            <input v-model="tier.minBoxes" class="input" type="number" min="1" placeholder="起订箱数" />
            <input v-model="tier.price" class="input" type="number" min="0" step="0.01" placeholder="单价" />
            <input v-model="tier.label" class="input" type="text" placeholder="标签（如 1箱起订）" />
            <button class="wb-row-btn danger" type="button" title="删除" @click="removeTier(i)">
              <Trash2 :size="15" />
            </button>
          </div>
          <p v-if="form.pricing.plan1Tiers.length === 0" class="wb-empty">暂无档位，可点击「新增档位」</p>
        </div>
      </section>

      <section class="settings-card">
        <div class="settings-card-head">
          <div class="settings-card-icon ai"><Bot :size="16" /></div>
          <h2>AI 模型接口</h2>
        </div>
        <div class="wb-form">
          <div class="wb-form-row full">
            <label>接口模式</label>
            <select v-model="aiForm.provider" class="select">
              <option value="auto">auto（有接口地址+模型即用真实模型，否则 Mock）</option>
              <option value="openai">openai（OpenAI 兼容接口，支持 Ollama / LM Studio 本地模型）</option>
              <option value="mock">mock（离线演示）</option>
            </select>
          </div>
          <div class="wb-form-row full">
            <label>接口地址</label>
            <input
              v-model="aiForm.base_url"
              class="input"
              type="text"
              placeholder="例如 https://api.openai.com/v1 或 http://127.0.0.1:11434/v1"
              :disabled="aiForm.provider === 'mock'"
            />
          </div>
          <div class="wb-form-row">
            <label>模型名称</label>
            <input
              v-model="aiForm.model"
              class="input"
              type="text"
              placeholder="例如 gpt-4o-mini / qwen2.5 / llama3"
              :disabled="aiForm.provider === 'mock'"
            />
          </div>
          <div class="wb-form-row">
            <label>最大运行步骤</label>
            <input v-model="aiForm.max_steps" class="input" type="number" min="1" max="100" />
          </div>
          <div class="wb-form-row">
            <label>默认运行模式</label>
            <select v-model="aiForm.default_mode" class="select">
              <option value="dry-run">dry-run</option>
              <option value="apply">apply</option>
            </select>
          </div>
          <div class="wb-form-row full">
            <label>API Key</label>
            <input
              v-model="aiForm.api_key"
              class="input"
              type="password"
              autocomplete="new-password"
              :placeholder="
                aiForm.has_api_key ? '已配置，留空保持不变' : '云端接口填写，本地模型可留空'
              "
              :disabled="aiForm.provider === 'mock'"
            />
            <p v-if="aiForm.has_api_key" class="ai-key-note">
              当前已配置：{{ aiForm.api_key_masked }}
            </p>
            <label class="ai-clear">
              <input
                v-model="aiForm.clear_api_key"
                type="checkbox"
              />
              清除已保存的 API Key
            </label>
          </div>
        </div>
        <div class="password-actions">
          <button
            class="btn btn-primary"
            type="button"
            :disabled="aiSaving"
            @click="saveAgentConfig"
          >
            <Save :size="16" />
            {{ aiSaving ? '保存中…' : '保存 AI 配置' }}
          </button>
        </div>
      </section>

      <section v-if="adminMode && !accountsLoading" class="settings-card">
        <div class="settings-card-head">
          <div class="settings-card-icon account"><KeyRound :size="16" /></div>
          <h2>正式账号密码</h2>
        </div>
        <p v-if="accountUsers.length === 0" class="wb-empty">暂无正式账号，请先退出并完成首次注册</p>
        <template v-else>
          <div class="wb-form">
            <div class="wb-form-row full">
              <label>正式账号</label>
              <select v-model="passwordForm.username" class="select">
                <option v-for="user in accountUsers" :key="user.id" :value="user.username">
                  {{ user.username }}
                </option>
              </select>
            </div>
            <div class="wb-form-row">
              <label>新密码</label>
              <input v-model="passwordForm.newPassword" class="input" type="password" autocomplete="new-password" />
            </div>
            <div class="wb-form-row">
              <label>确认新密码</label>
              <input v-model="passwordForm.confirmPassword" class="input" type="password" autocomplete="new-password" />
            </div>
          </div>
          <div class="password-actions">
            <button class="btn btn-primary" type="button" :disabled="passwordLoading" @click="savePassword">
              <Save :size="16" />
              {{ passwordLoading ? '重置中…' : '重置正式账号密码' }}
            </button>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.wb-page {
  display: grid;
  gap: 18px;
}

.wb-page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.wb-page-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wb-head-chip {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: none;
}

.wb-head-chip.settings {
  background: var(--violet-light);
  color: var(--violet);
}

.wb-page-title {
  font-size: 24px;
  font-weight: 800;
}

.wb-page-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}

.wb-empty {
  color: var(--muted);
  font-size: 13px;
  padding: 14px;
  background: var(--bg-alt);
  border-radius: 8px;
}

.settings-cards {
  display: grid;
  gap: 18px;
  max-width: 760px;
}

.settings-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 22px;
}

.settings-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.settings-card-icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  background: var(--primary-light);
  color: var(--primary-dark);
}

.settings-card-icon.account {
  background: var(--rose-light);
  color: var(--rose);
}

.settings-card-icon.ai {
  background: var(--teal-light);
  color: var(--teal);
}

.settings-card-head h2 {
  font-size: 16px;
  font-weight: 800;
}

.ai-key-note {
  color: var(--muted);
  font-size: 12px;
  margin-top: 6px;
}

.ai-clear {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
  margin-top: 8px;
  cursor: pointer;
}

.password-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.wb-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.wb-form-row {
  display: grid;
  gap: 7px;
}

.wb-form-row.full {
  grid-column: 1 / -1;
}

.wb-form-row label,
.tiers-head label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.tiers-block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
  display: grid;
  gap: 10px;
}

.tiers-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tier-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr 40px;
  gap: 8px;
  align-items: center;
}

.wb-row-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--muted);
}

.wb-row-btn.danger:hover {
  background: var(--rose-light);
  color: var(--rose);
}

@media (max-width: 640px) {
  .wb-form {
    grid-template-columns: 1fr;
  }

  .tier-row {
    grid-template-columns: 1fr 1fr;
  }
}

/* ── 网络与连接诊断卡片 ── */
.settings-card-icon.network {
  background: var(--amber-light, #fef3c7);
  color: var(--amber, #d97706);
}

.settings-card-head .net-refresh {
  margin-left: auto;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
.spinning {
  animation: spin 0.8s linear infinite;
}

.net-status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-alt);
  border-radius: 10px;
  margin-bottom: 14px;
}

.net-status-indicator {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  flex: none;
}

.net-status-indicator.ok,
.net-status-indicator.off {
  background: #ecfdf5;
  color: #047857;
}

.net-status-indicator.warning {
  background: #fefce8;
  color: #a16207;
}

.net-status-indicator.error {
  background: #fef2f2;
  color: #dc2626;
}

.net-status-text {
  display: grid;
  gap: 2px;
}

.net-status-text strong {
  font-size: 13px;
  font-weight: 700;
}

.net-status-text span {
  color: var(--muted);
  font-size: 12px;
}

.net-ip-section {
  margin-bottom: 14px;
}

.net-ip-section > label {
  display: block;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 8px;
}

.net-url-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.net-url-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--primary-light, #e3f2fd);
  border: 1px solid rgba(30, 136, 229, 0.2);
  border-radius: 8px;
}

.net-url-chip code {
  font-size: 13px;
  font-weight: 600;
  color: var(--primary-dark, #0d47a1);
  user-select: all;
}

.net-copy-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  color: var(--primary-dark, #0d47a1);
  opacity: 0.6;
  transition: all 0.15s;
}

.net-copy-btn:hover {
  opacity: 1;
  background: rgba(30, 136, 229, 0.12);
}

.net-details {
  margin-bottom: 10px;
}

.net-details summary {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  padding: 6px 0;
  user-select: none;
}

.net-iface-list {
  display: grid;
  gap: 6px;
  margin-top: 8px;
}

.net-iface-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--bg-alt);
  border-radius: 6px;
  font-size: 12px;
}

.net-iface-name {
  color: var(--muted);
  min-width: 80px;
  font-weight: 600;
}

.net-iface-ip {
  font-weight: 600;
}

.net-iface-ip.lan {
  color: var(--primary-dark, #0d47a1);
}

.net-iface-mask {
  color: var(--muted);
  font-size: 11px;
}

.net-lan-badge {
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.host-note {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}
</style>
