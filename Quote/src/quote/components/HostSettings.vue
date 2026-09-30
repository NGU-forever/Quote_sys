<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RefreshCw, Save, Server, X } from 'lucide-vue-next'
import { getBackendBase, setBackendBase } from '../../shared/utils/backendConfig'
import { discoverAndSetHost } from '../../shared/utils/discovery'
import { useCatalogStore } from '../../shared/stores/catalog'
import { useToast } from '../../shared/composables/useToast'

const catalog = useCatalogStore()
const toast = useToast()

const open = ref(false)
const url = ref(getBackendBase())
const discovering = ref(false)
const testing = ref(false)
const syncing = ref(false)
const testResult = ref('')

const SOURCE_LABEL = { remote: '主设备', cache: '本地缓存', static: '内置演示' }
const SOURCE_SHORT_LABEL = { remote: '在线', cache: '缓存', static: '演示' }
const sourceShort = computed(() => SOURCE_SHORT_LABEL[catalog.source] || '离线')

function openPanel() {
  url.value = getBackendBase()
  testResult.value = ''
  open.value = true
}

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) {
    open.value = false
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

async function discover() {
  discovering.value = true
  testResult.value = ''
  try {
    const host = await discoverAndSetHost()
    if (host) {
      url.value = host
      await syncNow()
      toast.push(`已发现并同步主设备：${host}`, 'success')
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
  try {
    const base = url.value.trim().replace(/\/+$/, '')
    const res = await fetch(`${base}/api/health`)
    const body = await res.json().catch(() => ({}))
    if (res.ok && body.app === 'hhz-data-service') {
      testResult.value = '连接成功'
    } else if (res.ok) {
      testResult.value = '连接失败：目标不是 HHZ 数据服务'
    } else {
      testResult.value = '连接失败：服务响应异常'
    }
  } catch {
    testResult.value = '连接失败：无法访问该地址'
  } finally {
    testing.value = false
  }
}

async function save() {
  const base = setBackendBase(url.value)
  url.value = base
  await syncNow()
  toast.push('主设备地址已保存，目录已重新同步')
}

async function syncNow() {
  syncing.value = true
  testResult.value = ''
  try {
    const source = await catalog.syncNow()
    const label = SOURCE_LABEL[source] || source
    toast.push(
      source === 'remote' ? '已同步 Workbench 最新套餐与目录' : `当前使用${label}数据`,
      'info'
    )
  } catch {
    toast.push('同步失败，仍在使用当前目录', 'info')
  } finally {
    syncing.value = false
  }
}
</script>

<template>
  <button class="host-gear" type="button" aria-label="连接主设备设置" @click="openPanel">
    <Server :size="15" />
    <span class="host-gear-text">连接主设备</span>
    <span class="host-status-badge" :class="catalog.source" :title="`数据源：${SOURCE_LABEL[catalog.source] || catalog.source}`">
      <span class="status-pulse-dot" aria-hidden="true"></span>
      {{ sourceShort }}
    </span>
  </button>

  <!--
    Teleport 到 body：该组件挂在带 backdrop-filter 的 sticky header 里，
    backdrop-filter 会使 header 成为 fixed 后代的包含块，遮罩会被锁进 72px 高的
    header 内居中，面板顶部被顶出窗口（exe 中被系统边框裁掉「自动发现主设备」）。
    移到 body 后遮罩才相对视口全屏定位。
  -->
  <Teleport to="body">
    <div v-if="open" class="host-overlay" @click.self="open = false">
      <div class="host-panel" role="dialog" aria-modal="true" aria-label="连接主设备">
        <div class="host-head">
          <h2>连接主设备</h2>
          <button class="host-close" type="button" aria-label="关闭" @click="open = false">
            <X :size="16" />
          </button>
        </div>

        <div class="host-body">
          <div class="host-status">
            <span class="host-status-label">当前数据来源</span>
            <strong>{{ SOURCE_LABEL[catalog.source] || catalog.source }}</strong>
            <span v-if="catalog.lastSyncAt" class="host-status-time"
              >最后同步：{{ catalog.lastSyncAt }}</span
            >
          </div>

          <div class="host-row">
            <button
              class="btn btn-soft btn-sm"
              type="button"
              :disabled="discovering"
              @click="discover"
            >
              <RefreshCw :size="14" />
              {{ discovering ? '搜索中…' : '自动发现主设备' }}
            </button>
          </div>

          <div class="host-row">
            <button
              class="btn btn-primary btn-sm"
              type="button"
              :disabled="syncing"
              @click="syncNow"
            >
              <RefreshCw :size="14" />
              {{ syncing ? '同步中…' : '立即同步最新目录' }}
            </button>
          </div>

          <div class="host-row">
            <label>主设备地址（端口 8000）</label>
            <input
              v-model="url"
              class="input"
              type="text"
              placeholder="http://192.168.1.100:8000"
            />
          </div>

          <div class="host-actions">
            <button class="btn btn-sm" type="button" :disabled="testing" @click="test">
              {{ testing ? '测试中…' : '测试连接' }}
            </button>
            <button class="btn btn-primary btn-sm" type="button" :disabled="syncing" @click="save">
              <Save :size="14" />
              保存
            </button>
          </div>

          <p v-if="testResult" class="host-result">{{ testResult }}</p>
          <p class="host-note">
            同一局域网内，主设备（HHZ 数据服务）与客户机端口一致为
            8000。找不到主设备时会自动使用本机缓存或内置演示数据。
          </p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.host-gear {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
  transition: all 0.18s ease;
}

.host-gear:hover {
  color: var(--primary-dark);
  background: #fff;
  border-color: rgba(30, 136, 229, 0.35);
  box-shadow: 0 4px 12px rgba(30, 136, 229, 0.12);
}

.host-gear-text {
  font-size: 13px;
}

.host-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.2;
}

.host-status-badge.remote {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #a7f3d0;
}

.host-status-badge.cache {
  background: #fefce8;
  color: #a16207;
  border: 1px solid #fef08a;
}

.host-status-badge.static {
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #e2e8f0;
}

.status-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.host-status-badge.remote .status-pulse-dot {
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.3);
  animation: pulse-dot 2s infinite ease-in-out;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.85); }
}

.host-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  padding: 20px;
  overflow: auto;
  background: rgba(15, 23, 42, 0.42);
}

.host-panel {
  margin: auto;
  width: min(420px, 100%);
  background: #fff;
  border-radius: 14px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.host-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
}

.host-head h2 {
  font-size: 17px;
  font-weight: 800;
}

.host-close {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--muted);
}

.host-close:hover {
  background: var(--bg-alt);
  color: var(--text);
}

.host-body {
  display: grid;
  gap: 14px;
  padding: 18px;
}

.host-status {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 12px;
  background: var(--bg-alt);
  border-radius: 10px;
}

.host-status-label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.host-status strong {
  color: var(--primary-dark);
  font-size: 14px;
}

.host-status-time {
  color: var(--muted);
  font-size: 12px;
  margin-left: auto;
}

.host-row {
  display: grid;
  gap: 7px;
}

.host-row label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.host-actions {
  display: flex;
  gap: 8px;
}

.host-result {
  color: var(--primary-dark);
  font-size: 12px;
  font-weight: 600;
}

.host-note {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
}
</style>
