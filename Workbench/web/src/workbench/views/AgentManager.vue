<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Copy,
  DatabaseZap,
  FileSpreadsheet,
  Folder,
  History,
  Layers,
  Link2,
  Package,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
  Upload,
  XCircle
} from 'lucide-vue-next'
import WbModal from '../components/WbModal.vue'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'

const toast = useToast()
const assets = ref([])
const assetsRootPath = ref('')
const runs = ref([])
const activeRun = ref(null)
const detailRun = ref(null)
const loading = ref(false)
const starting = ref(false)
const applying = ref(false)
const uploading = ref(false)
const isDragging = ref(false)
const fileInputRef = ref(null)
const reviewTab = ref('summary')
const mode = ref('dry-run')
let pollTimer = null

const supportedCount = computed(() => assets.value.filter((f) => f.supported).length)
const isRunning = computed(() => ['pending', 'running'].includes(activeRun.value?.status))
const isReviewEditable = computed(
  () => detailRun.value?.mode === 'dry-run' && detailRun.value?.status === 'succeeded'
)
const recentEvents = computed(() => {
  const run = activeRun.value || detailRun.value
  return run ? (run.events || []).slice(-8).reverse() : []
})
const candidateProducts = computed(() => detailRun.value?.candidates?.products || [])
const candidatePackages = computed(() => detailRun.value?.candidates?.packages || [])
const candidateBindings = computed(() => detailRun.value?.candidates?.bindings || [])

const detailModalTitle = computed(() => {
  if (!detailRun.value) return ''
  if (detailRun.value.mode === 'dry-run' && detailRun.value.status === 'succeeded') {
    return `人工审核与落库确认 · 任务 #${detailRun.value.id}`
  }
  return `运行报告 #${detailRun.value.id}`
})

function formatPackageSkus(pkg) {
  const ids = pkg.sku_ids || []
  const qtys = pkg.quantities || []
  return ids.map((id, idx) => `${id} × ${qtys[idx] ?? 1}`).join('、') || '—'
}

function prepareDetailRun(data) {
  if (!data) return null
  if (!data.candidates) {
    data.candidates = { products: [], packages: [], bindings: [], issues: [] }
  }
  if (!data.candidates.products) data.candidates.products = []
  if (!data.candidates.packages) data.candidates.packages = []
  if (!data.candidates.bindings) data.candidates.bindings = []
  if (!data.candidates.issues) data.candidates.issues = []

  for (const pkg of data.candidates.packages) {
    if (pkg.sku_ids_text == null) {
      pkg.sku_ids_text = (pkg.sku_ids || []).join(', ')
    }
    if (pkg.quantities_text == null) {
      pkg.quantities_text = (pkg.quantities || []).join(', ')
    }
  }
  return data
}

function sanitizeCandidatesForSubmit(candidates) {
  if (!candidates) return null
  const products = (candidates.products || []).map((p) => {
    const item = {
      sku_id: String(p.sku_id || '').trim(),
      category: p.category === 'device' ? 'device' : 'consumable',
      name: String(p.name || '').trim(),
    }
    if (p.min_price !== '' && p.min_price != null) item.min_price = Number(p.min_price)
    if (p.max_price !== '' && p.max_price != null) item.max_price = Number(p.max_price)
    if (p.unit) item.unit = String(p.unit).trim()
    if (p.pieces_per_unit !== '' && p.pieces_per_unit != null) item.pieces_per_unit = parseInt(p.pieces_per_unit, 10)
    if (p.units_per_box !== '' && p.units_per_box != null) item.units_per_box = parseInt(p.units_per_box, 10)
    if (p.box_price !== '' && p.box_price != null) item.box_price = Number(p.box_price)
    if (p.applicable_devices) item.applicable_devices = String(p.applicable_devices).trim()
    if (p.raw_price_desc) item.raw_price_desc = String(p.raw_price_desc).trim()
    if (p.remark) item.remark = String(p.remark).trim()
    if (p.image) item.image = String(p.image).trim()
    return item
  })

  const packages = (candidates.packages || []).map((pkg) => {
    let skuIds = Array.isArray(pkg.sku_ids) ? [...pkg.sku_ids] : []
    let qtys = Array.isArray(pkg.quantities) ? [...pkg.quantities] : []
    if (typeof pkg.sku_ids_text === 'string') {
      skuIds = pkg.sku_ids_text.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
    }
    if (typeof pkg.quantities_text === 'string') {
      qtys = pkg.quantities_text.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean).map(Number)
    }
    if (qtys.length < skuIds.length) {
      while (qtys.length < skuIds.length) qtys.push(1)
    } else if (qtys.length > skuIds.length) {
      qtys = qtys.slice(0, skuIds.length)
    }

    const item = {
      package_id: String(pkg.package_id || '').trim(),
      name: String(pkg.name || '').trim(),
      sku_ids: skuIds,
      quantities: qtys,
      fixed_bundle: Boolean(pkg.fixed_bundle),
    }
    if (pkg.std_price !== '' && pkg.std_price != null) item.std_price = Number(pkg.std_price)
    if (pkg.discount_price !== '' && pkg.discount_price != null) item.discount_price = Number(pkg.discount_price)
    if (pkg.discount_rate) item.discount_rate = String(pkg.discount_rate).trim()
    if (pkg.device_qty !== '' && pkg.device_qty != null) item.device_qty = parseInt(pkg.device_qty, 10)
    if (pkg.consumable_qty !== '' && pkg.consumable_qty != null) item.consumable_qty = parseInt(pkg.consumable_qty, 10)
    if (pkg.consumable_boxes !== '' && pkg.consumable_boxes != null) item.consumable_boxes = parseInt(pkg.consumable_boxes, 10)
    if (pkg.device_price !== '' && pkg.device_price != null) item.device_price = Number(pkg.device_price)
    if (pkg.note) item.note = String(pkg.note).trim()
    return item
  })

  const bindings = (candidates.bindings || []).map((b) => ({
    device_sku_id: String(b.device_sku_id || '').trim(),
    consumable_sku_id: String(b.consumable_sku_id || '').trim(),
  }))

  const issues = Array.isArray(candidates.issues) ? [...candidates.issues] : []

  return {
    products,
    packages,
    bindings,
    issues,
  }
}

function addCandidateProduct() {
  if (!detailRun.value) return
  if (!detailRun.value.candidates) {
    detailRun.value.candidates = { products: [], packages: [], bindings: [], issues: [] }
  }
  detailRun.value.candidates.products.push({
    sku_id: `SKU-NEW-${Date.now().toString().slice(-4)}`,
    category: 'device',
    name: '新录入商品',
    min_price: null,
    unit: '台',
    units_per_box: null,
    box_price: null,
    applicable_devices: '',
    raw_price_desc: ''
  })
}

function removeCandidateProduct(idx) {
  if (!detailRun.value?.candidates?.products) return
  detailRun.value.candidates.products.splice(idx, 1)
}

function addCandidatePackage() {
  if (!detailRun.value) return
  if (!detailRun.value.candidates) {
    detailRun.value.candidates = { products: [], packages: [], bindings: [], issues: [] }
  }
  detailRun.value.candidates.packages.push({
    package_id: `PKG-NEW-${Date.now().toString().slice(-4)}`,
    name: '新录入套餐',
    std_price: null,
    fixed_bundle: true,
    sku_ids: [],
    quantities: [],
    sku_ids_text: '',
    quantities_text: '',
    note: ''
  })
}

function removeCandidatePackage(idx) {
  if (!detailRun.value?.candidates?.packages) return
  detailRun.value.candidates.packages.splice(idx, 1)
}

async function copyAssetsPath() {
  if (!assetsRootPath.value) return
  try {
    await navigator.clipboard.writeText(assetsRootPath.value)
    toast.push('已复制资料目录路径到剪贴板', 'success')
  } catch {
    toast.push(assetsRootPath.value, 'info')
  }
}

function triggerUpload() {
  fileInputRef.value?.click()
}

async function handleFileSelected(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  await uploadFiles(files)
  if (fileInputRef.value) fileInputRef.value.value = ''
}

async function handleDrop(event) {
  isDragging.value = false
  const files = Array.from(event.dataTransfer?.files || [])
  if (!files.length) return
  await uploadFiles(files)
}

async function uploadFiles(files) {
  uploading.value = true
  let successCount = 0
  for (const file of files) {
    try {
      await api.agentUploadAsset(file)
      successCount++
    } catch (err) {
      toast.push(`上传 ${file.name} 失败: ${err.message || '未知错误'}`, 'danger')
    }
  }
  if (successCount > 0) {
    toast.push(`成功上传 ${successCount} 个文件到 assets 目录`, 'success')
    await refreshAssets(false)
  }
  uploading.value = false
}

async function deleteAssetFile(file) {
  if (!window.confirm(`确定要从 assets 目录删除文件 "${file.path}" 吗？`)) return
  try {
    await api.agentDeleteAsset(file.path)
    toast.push(`已删除文件 ${file.path}`, 'info')
    await refreshAssets(false)
  } catch (err) {
    toast.push(err.message || '删除文件失败', 'danger')
  }
}

async function confirmApply() {
  if (!detailRun.value || applying.value) return
  applying.value = true
  try {
    const payloadCandidates = sanitizeCandidatesForSubmit(detailRun.value.candidates)
    const { data } = await api.agentApplyRun(detailRun.value.id, payloadCandidates)
    detailRun.value = prepareDetailRun(data)
    toast.push(`任务 #${data.id} 候选数据已成功写入数据库！`, 'success')
    await Promise.all([loadRuns(), refreshAssets(false)])
  } catch (err) {
    toast.push(err.message || '写入数据库失败', 'danger')
  } finally {
    applying.value = false
  }
}

const statusMeta = {
  running: { label: '运行中', className: 'blue' },
  pending: { label: '排队中', className: 'blue' },
  succeeded: { label: '成功', className: 'green' },
  failed: { label: '失败', className: 'rose' },
  cancelled: { label: '已取消', className: 'amber' }
}

function runStatus(run) {
  return statusMeta[run?.status] || { label: run?.status || '未知', className: 'muted' }
}

function fmtTime(value) {
  if (!value) return '—'
  return String(value).slice(5, 19)
}

function fmtSize(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function shortHash(hash) {
  return hash ? hash.slice(0, 8) : '—'
}

function summaryOf(run) {
  return run
    ? `商品 ${run.products_added}+${run.products_updated}/${run.products_skipped} · 套餐 ${run.packages_added}+${run.packages_updated}/${run.packages_skipped} · 绑定 ${run.bindings_added}/${run.bindings_skipped}`
    : '—'
}

async function load() {
  loading.value = true
  try {
    const [assetRes, runRes] = await Promise.all([api.agentAssets(), api.agentRuns()])
    assets.value = assetRes.data.files || []
    assetsRootPath.value = assetRes.data.root_path || ''
    runs.value = runRes.data || []
    const active = runs.value.find((r) => ['pending', 'running'].includes(r.status))
    if (active && !isRunning.value) {
      activeRun.value = active
      startPolling()
    } else if (!active) {
      activeRun.value = null
      stopPolling()
    }
  } catch (err) {
    toast.push(err.message || '加载数据生成页面失败', 'info')
  } finally {
    loading.value = false
  }
}

async function startRun() {
  if (isRunning.value || supportedCount.value === 0) return
  starting.value = true
  try {
    const { data } = await api.agentStartRun({ mode: mode.value, note: '工作台一键生成' })
    activeRun.value = data
    startPolling()
  } catch (err) {
    toast.push(err.message || '启动失败', 'info')
  } finally {
    starting.value = false
  }
}

async function retryRun(run) {
  if (isRunning.value) {
    toast.push('当前已有任务运行中', 'info')
    return
  }
  try {
    const { data } = await api.agentRetryRun(run.id)
    activeRun.value = data
    startPolling()
  } catch (err) {
    toast.push(err.message || '重试失败', 'info')
  }
}

async function cancelRun() {
  if (!activeRun.value) return
  try {
    await api.agentCancelRun(activeRun.value.id)
    toast.push('正在取消任务', 'info')
  } catch (err) {
    toast.push(err.message || '取消失败', 'info')
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(pollTick, 1500)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function pollTick() {
  if (!activeRun.value) return
  try {
    const { data } = await api.agentGetRun(activeRun.value.id)
    activeRun.value = data
    if (!['pending', 'running'].includes(data.status)) {
      stopPolling()
      const finished = prepareDetailRun(data)
      activeRun.value = null
      await Promise.all([loadRuns(), refreshAssets(false)])
      detailRun.value = finished
      reviewTab.value = 'summary'
      if (finished.status === 'succeeded') {
        if (finished.mode === 'dry-run') {
          toast.push(`预演 #${finished.id} 完成，请人工审核候选数据`, 'info')
        } else {
          toast.push(`任务 #${finished.id} 执行成功并已入库`, 'success')
        }
      } else if (finished.status === 'failed') {
        toast.push(`任务 #${finished.id} 失败，请查看报告`, 'danger')
      }
    }
  } catch {
    /* 后端短暂不可用时下一轮继续 */
  }
}

async function loadRuns() {
  try {
    const { data } = await api.agentRuns()
    runs.value = data || []
  } catch (err) {
    toast.push(err.message || '读取运行历史失败', 'info')
  }
}

async function refreshAssets(showToast = true) {
  try {
    const { data } = await api.agentAssets()
    assets.value = data.files || []
    assetsRootPath.value = data.root_path || ''
    if (showToast) toast.push('已刷新源文件清单', 'info')
  } catch (err) {
    toast.push(err.message || '刷新源文件失败', 'info')
  }
}

async function openDetail(run) {
  try {
    const { data } = await api.agentGetRun(run.id)
    detailRun.value = prepareDetailRun(data)
    reviewTab.value = 'summary'
  } catch (err) {
    toast.push(err.message || '读取报告失败', 'info')
  }
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="wb-page">
    <div class="wb-page-head">
      <div class="wb-page-title-row">
        <div class="wb-head-chip agent">
          <DatabaseZap :size="18" />
        </div>
        <div>
          <h1 class="wb-page-title">数据生成</h1>
          <p class="wb-page-sub">源资料目录 assets，后台 ReAct Agent 自动整理为 Workbench 数据</p>
        </div>
      </div>
      <button class="btn btn-soft btn-sm" :disabled="loading" @click="load">
        <RefreshCw :size="15" />
        刷新
      </button>
    </div>

    <div class="agent-overview">
      <section class="agent-panel">
        <div class="agent-panel-head">
          <div class="agent-panel-title">
            <FileSpreadsheet :size="16" />
            源文件
            <span class="agent-count">支持 {{ supportedCount }} / {{ assets.length }}</span>
          </div>
          <div class="agent-panel-ops">
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept=".xlsx,.docx,.csv,.md,.txt"
              style="display: none"
              @change="handleFileSelected"
            />
            <button
              class="btn btn-primary btn-sm"
              :disabled="uploading"
              @click="triggerUpload"
            >
              <Upload :size="14" />
              {{ uploading ? '上传中…' : '上传资料' }}
            </button>
          </div>
        </div>

        <div v-if="assetsRootPath" class="agent-path-bar">
          <div class="agent-path-info">
            <Folder :size="14" class="agent-path-icon" />
            <span class="agent-path-label">资料目录：</span>
            <span class="agent-path-text" :title="assetsRootPath">{{ assetsRootPath }}</span>
          </div>
          <button class="btn btn-outline btn-xs" title="复制路径" @click="copyAssetsPath">
            <Copy :size="12" />
            复制
          </button>
        </div>

        <div
          class="agent-table-wrap"
          :class="{ 'drop-active': isDragging }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <div v-if="isDragging" class="agent-drop-overlay">
            <Upload :size="30" />
            <span>释放文件立即上传至 assets 目录</span>
          </div>
          <table class="agent-table">
            <thead>
              <tr>
                <th>文件</th>
                <th>类型</th>
                <th>大小</th>
                <th>修改时间</th>
                <th>SHA-256</th>
                <th class="ops">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="6" class="agent-empty">加载中…</td>
              </tr>
              <tr v-else-if="assets.length === 0">
                <td colspan="6" class="agent-empty">
                  assets 目录为空，可点击右上角「上传资料」或直接拖拽文件至此
                </td>
              </tr>
              <tr v-for="file in assets" v-else :key="file.path">
                <td>
                  <div class="agent-file-cell">
                    <span>{{ file.path }}</span>
                    <span v-if="!file.supported" class="agent-badge amber">不支持</span>
                  </div>
                </td>
                <td>
                  <span class="agent-badge" :class="file.supported ? 'blue' : 'muted'">
                    {{ file.type }}
                  </span>
                </td>
                <td class="num">{{ fmtSize(file.size) }}</td>
                <td>{{ fmtTime(file.mtime) }}</td>
                <td><code class="agent-hash">{{ shortHash(file.sha256) }}</code></td>
                <td class="ops">
                  <button
                    class="wb-row-btn danger"
                    title="删除文件"
                    @click="deleteAssetFile(file)"
                  >
                    <Trash2 :size="14" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="agent-panel action">
        <div class="agent-panel-head">
          <div class="agent-panel-title">
            <Bot :size="16" />
            Agent 运行
          </div>
          <span
            v-if="activeRun"
            class="agent-badge"
            :class="runStatus(activeRun).className"
          >
            {{ runStatus(activeRun).label }}
          </span>
        </div>

        <div v-if="activeRun" class="agent-run-state">
          <div class="agent-state-grid">
            <div>
              <span class="agent-label">任务</span>
              <strong>#{{ activeRun.id }}</strong>
            </div>
            <div>
              <span class="agent-label">阶段</span>
              <strong>{{ activeRun.stage || 'inventory' }}</strong>
            </div>
            <div>
              <span class="agent-label">Provider</span>
              <strong>{{ activeRun.provider || 'mock' }}</strong>
            </div>
            <div>
              <span class="agent-label">模式</span>
              <strong>{{ activeRun.mode }}</strong>
            </div>
          </div>

          <div class="agent-events">
            <div v-for="event in recentEvents" :key="`${event.id}-${event.step}`" class="agent-event">
              <span class="agent-event-role" :class="event.role">{{ event.role }}</span>
              <span class="agent-event-text">
                <template v-if="event.tool">{{ event.tool }} · </template>{{ event.summary }}
              </span>
            </div>
            <p v-if="recentEvents.length === 0" class="agent-empty">等待 Agent 输出…</p>
          </div>

          <div class="agent-actions">
            <button v-if="isRunning" class="btn btn-outline btn-sm" @click="cancelRun">
              <Square :size="14" />
              取消任务
            </button>
            <button v-else class="btn btn-soft btn-sm" @click="openDetail(activeRun)">
              <History :size="14" />
              查看报告
            </button>
          </div>
        </div>

        <div v-else class="agent-run-start">
          <div class="agent-mode-row">
            <label class="agent-label">模式</label>
            <select v-model="mode" class="select">
              <option value="dry-run">dry-run（只出候选与报告）</option>
              <option value="apply">apply（事务写入正式表）</option>
            </select>
          </div>
          <button
            class="btn btn-primary agent-start"
            :disabled="starting || supportedCount === 0"
            @click="startRun"
          >
            <Play :size="16" />
            {{ starting ? '启动中…' : '一键生成数据库' }}
          </button>
        </div>
      </section>
    </div>

    <section class="agent-panel">
      <div class="agent-panel-head">
        <div class="agent-panel-title">
          <History :size="16" />
          运行历史
        </div>
        <span class="agent-count">共 {{ runs.length }} 次</span>
      </div>
      <div class="agent-table-wrap">
        <table class="agent-table">
          <thead>
            <tr>
              <th>#</th>
              <th>模式</th>
              <th>状态</th>
              <th>结果摘要</th>
              <th>Provider</th>
              <th>完成时间</th>
              <th class="ops">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="runs.length === 0">
              <td colspan="7" class="agent-empty">暂无运行记录</td>
            </tr>
            <tr v-for="run in runs" v-else :key="run.id">
              <td><span class="agent-id">#{{ run.id }}</span></td>
              <td><span class="agent-badge violet">{{ run.mode }}</span></td>
              <td><span class="agent-badge" :class="runStatus(run).className">{{ runStatus(run).label }}</span></td>
              <td class="agent-summary">{{ summaryOf(run) }}</td>
              <td>{{ run.provider || '—' }}</td>
              <td>{{ fmtTime(run.finished_at) }}</td>
              <td class="ops">
                <button class="wb-row-btn" title="查看报告" @click="openDetail(run)">
                  <History :size="15" />
                </button>
                <button
                  class="wb-row-btn"
                  title="再次运行"
                  :disabled="isRunning"
                  @click="retryRun(run)"
                >
                  <RotateCcw :size="15" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <WbModal
      :open="Boolean(detailRun)"
      :title="detailModalTitle"
      width="1000px"
      @close="detailRun = null"
    >
      <template v-if="detailRun">
        <!-- 顶部审核状态提示条 -->
        <div
          v-if="detailRun.mode === 'dry-run' && detailRun.status === 'succeeded'"
          class="agent-banner review"
        >
          <AlertTriangle :size="18" />
          <div>
            <strong>待人工审核入库</strong>
            <p>本次任务为预演模式（dry-run），数据尚未写入正式数据库。请审阅下方候选明细与存疑清单，核实无误后可点击底部「确认写入数据库」。</p>
          </div>
        </div>
        <div
          v-else-if="detailRun.mode === 'apply' && detailRun.status === 'succeeded'"
          class="agent-banner applied"
        >
          <CheckCircle2 :size="18" />
          <div>
            <strong>已正式写入数据库</strong>
            <p>候选商品、商业套餐与设备耗材兼容绑定已成功提交并写入正式业务表。</p>
          </div>
        </div>
        <div v-else-if="detailRun.status === 'failed'" class="agent-banner failed">
          <XCircle :size="18" />
          <div>
            <strong>任务未通过质检或已终止</strong>
            <p>{{ detailRun.error || '提取数据或服务端纯代码质检未通过，请查看轨迹' }}</p>
          </div>
        </div>

        <!-- 审核 Tabs 导航 -->
        <div class="agent-modal-tabs">
          <button
            class="agent-modal-tab"
            :class="{ active: reviewTab === 'summary' }"
            @click="reviewTab = 'summary'"
          >
            <Layers :size="14" />
            概览与轨迹
          </button>
          <button
            class="agent-modal-tab"
            :class="{ active: reviewTab === 'products' }"
            @click="reviewTab = 'products'"
          >
            <Bot :size="14" />
            候选商品 ({{ candidateProducts.length }})
          </button>
          <button
            class="agent-modal-tab"
            :class="{ active: reviewTab === 'packages' }"
            @click="reviewTab = 'packages'"
          >
            <Package :size="14" />
            候选套餐 ({{ candidatePackages.length }})
          </button>
          <button
            class="agent-modal-tab"
            :class="{ active: reviewTab === 'bindings' }"
            @click="reviewTab = 'bindings'"
          >
            <Link2 :size="14" />
            候选绑定 ({{ candidateBindings.length }})
          </button>
        </div>

        <!-- Tab 1: 概览与轨迹 -->
        <div v-if="reviewTab === 'summary'" class="agent-tab-pane">
          <div class="agent-state-grid detail">
            <div>
              <span class="agent-label">状态</span>
              <strong>{{ runStatus(detailRun).label }}</strong>
            </div>
            <div>
              <span class="agent-label">模式</span>
              <strong>{{ detailRun.mode }}</strong>
            </div>
            <div>
              <span class="agent-label">Provider</span>
              <strong>{{ detailRun.provider }}</strong>
            </div>
            <div>
              <span class="agent-label">文件数</span>
              <strong>{{ detailRun.file_count }}</strong>
            </div>
            <div>
              <span class="agent-label">候选商品</span>
              <strong>{{ detailRun.products_candidates }}</strong>
            </div>
            <div>
              <span class="agent-label">候选套餐</span>
              <strong>{{ detailRun.packages_candidates }}</strong>
            </div>
            <div>
              <span class="agent-label">候选绑定</span>
              <strong>{{ detailRun.bindings_candidates }}</strong>
            </div>
            <div>
              <span class="agent-label">耗时</span>
              <strong>{{ detailRun.finished_at ? '已结束' : '进行中' }}</strong>
            </div>
          </div>

          <div v-if="detailRun.report?.issues?.length" class="agent-issues">
            <h3 class="agent-sub-title">⚠️ 问题与存疑清单（{{ detailRun.report.issues.length }} 项）</h3>
            <div v-for="(issue, i) in detailRun.report.issues" :key="i" class="agent-issue">
              <AlertTriangle :size="14" />
              <span>{{ issue }}</span>
            </div>
          </div>

          <div v-if="detailRun.status === 'succeeded'" class="agent-success-tip">
            <CheckCircle2 :size="15" />
            {{ summaryOf(detailRun) }}
          </div>

          <h3 class="agent-sub-title">步骤轨迹与审计日志</h3>
          <div class="agent-events detail">
            <div v-for="event in detailRun.events || []" :key="event.id" class="agent-event">
              <span class="agent-event-role" :class="event.role">
                {{ event.step }} · {{ event.role }}
              </span>
              <span class="agent-event-text">
                <template v-if="event.tool">{{ event.tool }} · </template>{{ event.summary }}
              </span>
            </div>
            <p v-if="!(detailRun.events || []).length" class="agent-empty">暂无步骤</p>
          </div>
        </div>

        <!-- Tab 2: 候选商品 -->
        <div v-else-if="reviewTab === 'products'" class="agent-tab-pane">
          <div v-if="isReviewEditable" class="agent-table-toolbar">
            <div class="agent-toolbar-hint">
              💡 提示：可直接在线修改商品底价、规格或增删行，确认入库时以此处内容为准。
            </div>
            <button class="btn btn-soft btn-sm" @click="addCandidateProduct">
              <Plus :size="14" />
              添加商品
            </button>
          </div>

          <div v-if="candidateProducts.length === 0" class="agent-empty">
            本次未提取到候选商品<template v-if="isReviewEditable">，可点击上方「添加商品」手动录入</template>
          </div>
          <div v-else class="agent-table-wrap">
            <table class="agent-table mini" :class="{ editable: isReviewEditable }">
              <thead>
                <tr>
                  <th style="min-width: 110px">SKU ID</th>
                  <th style="min-width: 85px">类别</th>
                  <th style="min-width: 140px">产品名称</th>
                  <th style="min-width: 95px">最低底价</th>
                  <th style="min-width: 65px">单位</th>
                  <th style="min-width: 85px">每箱件数</th>
                  <th style="min-width: 90px">整箱底价</th>
                  <th style="min-width: 110px">适用设备</th>
                  <th v-if="!isReviewEditable">原始口径说明</th>
                  <th v-if="isReviewEditable" class="ops" style="width: 48px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(prod, idx) in candidateProducts" :key="idx">
                  <template v-if="isReviewEditable">
                    <td><input v-model="prod.sku_id" class="input input-sm code-font" placeholder="SKU" /></td>
                    <td>
                      <select v-model="prod.category" class="select input-sm">
                        <option value="device">设备</option>
                        <option value="consumable">耗材</option>
                      </select>
                    </td>
                    <td><input v-model="prod.name" class="input input-sm" placeholder="商品名称" /></td>
                    <td><input v-model.number="prod.min_price" type="number" step="0.01" min="0" class="input input-sm num" placeholder="底价" /></td>
                    <td><input v-model="prod.unit" class="input input-sm" placeholder="台/盒" /></td>
                    <td><input v-model.number="prod.units_per_box" type="number" min="1" class="input input-sm num" placeholder="箱规" /></td>
                    <td><input v-model.number="prod.box_price" type="number" step="0.01" min="0" class="input input-sm num" placeholder="箱价" /></td>
                    <td><input v-model="prod.applicable_devices" class="input input-sm" placeholder="适用设备" /></td>
                    <td class="ops">
                      <button class="wb-row-btn danger" title="删除此行" @click="removeCandidateProduct(idx)">
                        <Trash2 :size="14" />
                      </button>
                    </td>
                  </template>
                  <template v-else>
                    <td><code>{{ prod.sku_id }}</code></td>
                    <td>
                      <span class="agent-badge" :class="prod.category === 'device' ? 'blue' : 'violet'">
                        {{ prod.category === 'device' ? '设备' : '耗材' }}
                      </span>
                    </td>
                    <td><strong>{{ prod.name }}</strong></td>
                    <td class="num font-bold">
                      {{ prod.min_price != null ? `¥${prod.min_price}` : '—' }}
                    </td>
                    <td>{{ prod.unit || '—' }}</td>
                    <td>
                      {{ prod.units_per_box ? `${prod.units_per_box}${prod.unit || '件'}/箱 (¥${prod.box_price || '—'})` : '—' }}
                    </td>
                    <td>{{ prod.applicable_devices || '—' }}</td>
                    <td class="text-muted">{{ prod.raw_price_desc || '—' }}</td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Tab 3: 候选套餐 -->
        <div v-else-if="reviewTab === 'packages'" class="agent-tab-pane">
          <div v-if="isReviewEditable" class="agent-table-toolbar">
            <div class="agent-toolbar-hint">
              💡 提示：可直接在线修改套餐价格、包含 SKU 及数量，多个 SKU / 数量用逗号或空格分隔。
            </div>
            <button class="btn btn-soft btn-sm" @click="addCandidatePackage">
              <Plus :size="14" />
              添加套餐
            </button>
          </div>

          <div v-if="candidatePackages.length === 0" class="agent-empty">
            本次未提取到商业套餐<template v-if="isReviewEditable">，可点击上方「添加套餐」手动录入</template>
          </div>
          <div v-else class="agent-table-wrap">
            <table class="agent-table mini" :class="{ editable: isReviewEditable }">
              <thead>
                <tr>
                  <th style="min-width: 100px">套餐编号</th>
                  <th style="min-width: 130px">套餐名称</th>
                  <th style="min-width: 150px">包含 SKU (逗号隔开)</th>
                  <th style="min-width: 90px">对应数量</th>
                  <th style="min-width: 95px">标准售价</th>
                  <th style="min-width: 95px">形态</th>
                  <th style="min-width: 120px">依据与备注</th>
                  <th v-if="isReviewEditable" class="ops" style="width: 48px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(pkg, idx) in candidatePackages" :key="idx">
                  <template v-if="isReviewEditable">
                    <td><input v-model="pkg.package_id" class="input input-sm code-font" placeholder="编号" /></td>
                    <td><input v-model="pkg.name" class="input input-sm" placeholder="套餐名称" /></td>
                    <td><input v-model="pkg.sku_ids_text" class="input input-sm code-font" placeholder="SKU-1, SKU-2" /></td>
                    <td><input v-model="pkg.quantities_text" class="input input-sm code-font" placeholder="1, 10" /></td>
                    <td><input v-model.number="pkg.std_price" type="number" step="0.01" min="0" class="input input-sm num" placeholder="标准价" /></td>
                    <td>
                      <select v-model="pkg.fixed_bundle" class="select input-sm">
                        <option :value="true">固定整购</option>
                        <option :value="false">买赠/促销</option>
                      </select>
                    </td>
                    <td><input v-model="pkg.note" class="input input-sm" placeholder="备注依据" /></td>
                    <td class="ops">
                      <button class="wb-row-btn danger" title="删除此行" @click="removeCandidatePackage(idx)">
                        <Trash2 :size="14" />
                      </button>
                    </td>
                  </template>
                  <template v-else>
                    <td><code>{{ pkg.package_id }}</code></td>
                    <td><strong>{{ pkg.name }}</strong></td>
                    <td>{{ formatPackageSkus(pkg) }}</td>
                    <td class="num font-bold">
                      {{ pkg.std_price != null ? `¥${pkg.std_price}` : '—' }}
                    </td>
                    <td>
                      <span class="agent-badge" :class="pkg.fixed_bundle ? 'blue' : 'amber'">
                        {{ pkg.fixed_bundle ? '固定整购' : '买赠/促销' }}
                      </span>
                    </td>
                    <td class="text-muted">{{ pkg.note || '—' }}</td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Tab 4: 候选绑定 -->
        <div v-else-if="reviewTab === 'bindings'" class="agent-tab-pane">
          <div v-if="candidateBindings.length === 0" class="agent-empty">
            本次未提取到机型适配绑定
          </div>
          <div v-else class="agent-table-wrap">
            <table class="agent-table mini">
              <thead>
                <tr>
                  <th>设备 SKU</th>
                  <th>耗材 SKU</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(b, idx) in candidateBindings" :key="idx">
                  <td><code>{{ b.device_sku_id }}</code></td>
                  <td><code>{{ b.consumable_sku_id }}</code></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>

      <template #footer>
        <button class="btn btn-soft btn-sm" @click="detailRun = null">
          {{ detailRun?.mode === 'dry-run' && detailRun?.status === 'succeeded' ? '暂不入库' : '关闭' }}
        </button>
        <button
          v-if="detailRun?.mode === 'dry-run' && detailRun?.status === 'succeeded'"
          class="btn btn-primary btn-sm"
          :disabled="applying"
          @click="confirmApply"
        >
          <Check :size="15" />
          {{ applying ? '正在写入数据库…' : '确认写入数据库' }}
        </button>
      </template>
    </WbModal>
  </div>
</template>

<style scoped>
.wb-page {
  display: grid;
  gap: 18px;
  min-width: 0;
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

.wb-head-chip.agent {
  background: var(--teal-light);
  color: var(--teal);
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

.agent-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.85fr);
  gap: 18px;
  align-items: start;
}

.agent-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.agent-panel.action {
  position: sticky;
  top: 16px;
}

.agent-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--border);
}

.agent-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 800;
}

.agent-count {
  color: var(--muted);
  font-size: 12px;
  font-weight: 600;
}

.agent-table-wrap {
  overflow-x: auto;
}

.agent-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 760px;
}

.agent-table th,
.agent-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: middle;
}

.agent-table th {
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.agent-table tbody tr:last-child td {
  border-bottom: none;
}

.agent-table .num {
  text-align: right;
  white-space: nowrap;
}

.agent-table .ops {
  text-align: right;
  white-space: nowrap;
}

.agent-empty {
  color: var(--muted);
  font-size: 13px;
  text-align: center;
  padding: 24px 14px;
}

.agent-file-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 340px;
  overflow-wrap: anywhere;
}

.agent-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  white-space: nowrap;
}

.agent-badge.blue {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.agent-badge.green {
  background: var(--success-light);
  color: var(--success);
}

.agent-badge.rose {
  background: var(--rose-light);
  color: var(--rose);
}

.agent-badge.amber {
  background: var(--amber-light);
  color: var(--amber);
}

.agent-badge.violet {
  background: var(--violet-light);
  color: var(--violet);
}

.agent-badge.muted {
  background: var(--bg-alt);
  color: var(--muted);
}

.agent-hash {
  color: var(--muted);
  font-size: 11px;
}

.agent-run-state,
.agent-run-start {
  display: grid;
  gap: 16px;
  padding: 16px;
}

.agent-mode-row {
  display: grid;
  gap: 7px;
}

.agent-start {
  justify-content: center;
}

.agent-state-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.agent-state-grid.detail {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 18px;
}

.agent-state-grid > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.agent-state-grid strong {
  font-size: 13px;
  overflow-wrap: anywhere;
}

.agent-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}

.agent-events {
  display: grid;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
  background: var(--bg-alt);
  border-radius: 8px;
  padding: 10px;
}

.agent-events.detail {
  max-height: 260px;
}

.agent-event {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  font-size: 12px;
  line-height: 1.45;
}

.agent-event-role {
  font-size: 10.5px;
  font-weight: 800;
  text-transform: uppercase;
}

.agent-event-role.assistant {
  color: var(--primary-dark);
}

.agent-event-role.tool {
  color: var(--teal);
}

.agent-event-role.system,
.agent-event-role.report {
  color: var(--violet);
}

.agent-event-text {
  color: var(--muted);
  min-width: 0;
}

.agent-actions {
  display: flex;
  justify-content: flex-end;
}

.agent-summary {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}

.agent-id {
  font-weight: 800;
  color: var(--primary-dark);
}

.wb-row-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
  color: var(--muted);
}

.wb-row-btn:hover {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-row-btn.danger:hover {
  background: var(--rose-light);
  color: var(--rose);
}

.wb-row-btn[disabled] {
  opacity: 0.45;
  cursor: default;
}

.agent-panel-ops {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-path-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 16px;
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}

.agent-path-info {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.agent-path-icon {
  color: var(--teal);
  flex-shrink: 0;
}

.agent-path-label {
  color: var(--muted);
  font-weight: 700;
  flex-shrink: 0;
}

.agent-path-text {
  font-family: var(--font-mono, monospace);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-xs {
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.agent-table-wrap.drop-active {
  background: var(--primary-light);
  outline: 2px dashed var(--primary);
  outline-offset: -2px;
}

.agent-drop-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.92);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  z-index: 10;
  color: var(--primary-dark);
  font-size: 13px;
  font-weight: 700;
  pointer-events: none;
}

.agent-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 12px;
}

.agent-toolbar-hint {
  font-size: 12px;
  color: var(--muted);
}

.agent-table.mini.editable th,
.agent-table.mini.editable td {
  padding: 5px 6px;
}

.agent-table.mini.editable input.input-sm,
.agent-table.mini.editable select.input-sm {
  width: 100%;
  height: 28px;
  padding: 0 6px;
  font-size: 12px;
  border-radius: 5px;
  border: 1px solid var(--border);
  background: #fff;
  box-sizing: border-box;
}

.agent-table.mini.editable input.input-sm:focus,
.agent-table.mini.editable select.input-sm:focus {
  border-color: var(--primary);
  outline: none;
}

.code-font {
  font-family: var(--font-mono, monospace);
  font-size: 11px !important;
}

.agent-sub-title {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  margin: 16px 0 8px;
}

.agent-issues {
  display: grid;
  gap: 7px;
  margin-bottom: 6px;
}

.agent-issue,
.agent-error,
.agent-success-tip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 9px 11px;
  border-radius: 8px;
  font-size: 12.5px;
  line-height: 1.5;
}

.agent-issue {
  background: var(--amber-light);
  color: var(--amber);
}

.agent-error {
  background: var(--rose-light);
  color: var(--rose);
  margin-top: 12px;
}

.agent-success-tip {
  background: var(--success-light);
  color: var(--success);
  margin-top: 16px;
  font-weight: 700;
}

.agent-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 9px;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.5;
}

.agent-banner strong {
  display: block;
  font-size: 13.5px;
  margin-bottom: 2px;
}

.agent-banner p {
  margin: 0;
  opacity: 0.9;
}

.agent-banner.review {
  background: var(--amber-light);
  color: var(--amber);
  border: 1px solid rgba(217, 119, 6, 0.25);
}

.agent-banner.applied {
  background: var(--success-light);
  color: var(--success);
  border: 1px solid rgba(16, 185, 129, 0.25);
}

.agent-banner.failed {
  background: var(--rose-light);
  color: var(--rose);
  border: 1px solid rgba(244, 63, 94, 0.25);
}

.agent-modal-tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
  margin-bottom: 16px;
  overflow-x: auto;
}

.agent-modal-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 8px;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--muted);
  transition: all 0.15s ease;
  white-space: nowrap;
}

.agent-modal-tab:hover {
  background: var(--bg-alt);
  color: var(--text);
}

.agent-modal-tab.active {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.agent-tab-pane {
  min-height: 200px;
}

.agent-table.mini {
  min-width: 580px;
  font-size: 12.5px;
}

.agent-table.mini th,
.agent-table.mini td {
  padding: 8px 10px;
}

.text-muted {
  color: var(--muted);
  font-size: 12px;
}

.font-bold {
  font-weight: 700;
}

@media (max-width: 1080px) {
  .agent-overview {
    grid-template-columns: 1fr;
  }

  .agent-panel.action {
    position: static;
  }
}

@media (max-width: 640px) {
  .agent-state-grid,
  .agent-state-grid.detail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .agent-event {
    grid-template-columns: 1fr;
  }
}
</style>
