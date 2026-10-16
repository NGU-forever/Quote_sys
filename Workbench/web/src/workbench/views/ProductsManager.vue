<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Check,
  ImagePlus,
  Link2,
  Package,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2
} from 'lucide-vue-next'
import WbModal from '../components/WbModal.vue'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'
import { formatMoney } from '../../shared/utils/format'
import { resolveImage } from '../../shared/utils/imageSync'

const toast = useToast()

const products = ref([])
const loading = ref(false)
const keyword = ref('')
const activeCategoryTab = ref('all')
const statusFilter = ref('all') // 'all' | 'active' | 'inactive'

// 模态框控制
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)
const fileInput = ref(null)
const uploading = ref(false)

// 绑定模态框
const showBindingsModal = ref(false)
const bindingProduct = ref(null)
const selectedBindings = ref([])
const savingBindings = ref(false)
const bindingSearch = ref('')

// 分类预设配置
const CATEGORY_TABS = [
  { key: 'all', label: '全部' },
  { key: 'device', label: '硬件设备' },
  { key: 'consumable', label: '耗材消耗品' },
  { key: 'accessory', label: '配套配件' },
  { key: 'service', label: '定制服务' },
  { key: 'other', label: '其他' }
]

const CATEGORY_PRESETS = [
  { value: 'device', label: '硬件设备' },
  { value: 'consumable', label: '耗材消耗品' },
  { value: 'accessory', label: '配套配件' },
  { value: 'service', label: '定制服务' },
  { value: 'custom', label: '自定义分类' }
]

const COMMON_UNITS = ['台', '套', '支', '袋', '箱', '盒', '个', '人天', '次']

// 表单响应式数据
const isCustomCategory = ref(false)
const customCategoryInput = ref('')

const form = reactive({
  name: '',
  sku_id: '',
  category: 'device',
  spec: '',
  unit: '台',
  min_price: '',
  max_price: '',
  is_active: true,
  pieces_per_unit: '',
  units_per_box: '',
  box_price: '',
  applicable_devices: '',
  image: '',
  remark: ''
})

function resetForm() {
  editingId.value = null
  isCustomCategory.value = false
  customCategoryInput.value = ''
  
  // 根据当前激活的 tab 默认选择分类
  let defaultCategory = 'device'
  if (['device', 'hardware', 'consumable', 'accessory', 'service'].includes(activeCategoryTab.value)) {
    defaultCategory = activeCategoryTab.value === 'hardware' ? 'device' : activeCategoryTab.value
  }

  let defaultUnit = '台'
  if (defaultCategory === 'consumable') defaultUnit = '袋'
  else if (defaultCategory === 'service') defaultUnit = '人天'
  else if (defaultCategory === 'accessory') defaultUnit = '个'

  Object.assign(form, {
    name: '',
    sku_id: '',
    category: defaultCategory,
    spec: '',
    unit: defaultUnit,
    min_price: '',
    max_price: '',
    is_active: true,
    pieces_per_unit: '',
    units_per_box: '',
    box_price: '',
    applicable_devices: '',
    image: '',
    remark: ''
  })
}

// 归一化类目判定
function matchesCategory(productCategory, tabKey) {
  const cat = (productCategory || '').toLowerCase().trim()
  if (tabKey === 'all') return true
  if (tabKey === 'device' || tabKey === 'hardware') return cat === 'device' || cat === 'hardware'
  if (tabKey === 'consumable' || tabKey === 'consumables') return cat === 'consumable' || cat === 'consumables'
  if (tabKey === 'accessory' || tabKey === 'accessories') return cat === 'accessory' || cat === 'accessories'
  if (tabKey === 'service' || tabKey === 'services') return cat === 'service' || cat === 'services'
  if (tabKey === 'other') {
    return !['device', 'hardware', 'consumable', 'consumables', 'accessory', 'accessories', 'service', 'services'].includes(cat)
  }
  return cat === tabKey
}

function getCategoryBadge(catRaw) {
  const cat = (catRaw || '').toLowerCase().trim()
  if (cat === 'device' || cat === 'hardware') return { label: '硬件设备', class: 'cat-hardware' }
  if (cat === 'consumable' || cat === 'consumables') return { label: '耗材消耗品', class: 'cat-consumable' }
  if (cat === 'accessory' || cat === 'accessories') return { label: '配套配件', class: 'cat-accessory' }
  if (cat === 'service' || cat === 'services') return { label: '定制服务', class: 'cat-service' }
  return { label: catRaw || '其他', class: 'cat-other' }
}

// 计算各分类计数
const categoryCounts = computed(() => {
  const counts = { all: products.value.length }
  CATEGORY_TABS.forEach((tab) => {
    if (tab.key !== 'all') {
      counts[tab.key] = products.value.filter((p) => matchesCategory(p.category, tab.key)).length
    }
  })
  return counts
})

// 筛选后的商品列表
const filteredProducts = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return products.value.filter((p) => {
    // 1. 分类筛选
    if (!matchesCategory(p.category, activeCategoryTab.value)) return false

    // 2. 状态筛选
    if (statusFilter.value === 'active' && p.is_active === false) return false
    if (statusFilter.value === 'inactive' && p.is_active !== false) return false

    // 3. 关键字搜索
    if (kw) {
      const matchName = (p.name || '').toLowerCase().includes(kw)
      const matchSku = (p.sku_id || '').toLowerCase().includes(kw)
      const matchSpec = (p.spec || '').toLowerCase().includes(kw)
      const matchRemark = (p.remark || '').toLowerCase().includes(kw)
      const matchApp = (p.applicable_devices || '').toLowerCase().includes(kw)
      if (!matchName && !matchSku && !matchSpec && !matchRemark && !matchApp) {
        return false
      }
    }
    return true
  })
})

async function loadProducts() {
  loading.value = true
  try {
    const res = await api.listProducts()
    products.value = res.data || []
  } catch (err) {
    toast.push(err.message || '加载商品列表失败', 'info')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  resetForm()
  showForm.value = true
}

function openEdit(item) {
  editingId.value = item.id
  let cat = item.category || 'device'
  if (cat === 'hardware') cat = 'device'
  if (cat === 'consumables') cat = 'consumable'
  const isPreset = ['device', 'consumable', 'accessory', 'service'].includes(cat)

  isCustomCategory.value = !isPreset
  customCategoryInput.value = isPreset ? '' : cat

  Object.assign(form, {
    name: item.name || '',
    sku_id: item.sku_id || '',
    category: isPreset ? cat : 'custom',
    spec: item.spec || '',
    unit: item.unit || '台',
    min_price: item.min_price != null ? item.min_price : '',
    max_price: item.max_price != null ? item.max_price : '',
    is_active: item.is_active !== false,
    pieces_per_unit: item.pieces_per_unit != null ? item.pieces_per_unit : '',
    units_per_box: item.units_per_box != null ? item.units_per_box : '',
    box_price: item.box_price != null ? item.box_price : '',
    applicable_devices: item.applicable_devices || '',
    image: item.image || '',
    remark: item.remark || ''
  })
  showForm.value = true
}

function toNum(val) {
  if (val === '' || val === null || val === undefined) return null
  const n = Number(val)
  return Number.isFinite(n) ? n : null
}

async function submitForm() {
  if (!form.name.trim()) {
    toast.push('请填写商品名称', 'info')
    return
  }

  let finalCategory = form.category
  if (form.category === 'custom') {
    finalCategory = customCategoryInput.value.trim()
    if (!finalCategory) {
      toast.push('请填写自定义分类名称', 'info')
      return
    }
  }

  saving.value = true
  const payload = {
    name: form.name.trim(),
    sku_id: form.sku_id.trim() || undefined,
    category: finalCategory,
    spec: form.spec.trim() || null,
    unit: form.unit.trim() || null,
    min_price: toNum(form.min_price),
    max_price: toNum(form.max_price),
    is_active: Boolean(form.is_active),
    pieces_per_unit: toNum(form.pieces_per_unit),
    units_per_box: toNum(form.units_per_box),
    box_price: toNum(form.box_price),
    applicable_devices: form.applicable_devices.trim() || null,
    image: form.image.trim() || null,
    remark: form.remark.trim() || null
  }

  try {
    if (editingId.value) {
      await api.updateProduct(editingId.value, payload)
      toast.push('商品信息已更新')
    } else {
      await api.createProduct(payload)
      toast.push('新商品录入成功')
    }
    showForm.value = false
    await loadProducts()
  } catch (err) {
    toast.push(err.message || '保存失败', 'info')
  } finally {
    saving.value = false
  }
}

async function toggleActiveStatus(item) {
  const newStatus = item.is_active === false ? true : false
  try {
    await api.updateProduct(item.id, { is_active: newStatus })
    item.is_active = newStatus
    toast.push(newStatus ? `已启用「${item.name}」` : `已停用「${item.name}」`)
  } catch (err) {
    toast.push(err.message || '更新状态失败', 'info')
  }
}

async function removeProduct(item) {
  if (!window.confirm(`确定要彻底删除商品「${item.name}」（SKU: ${item.sku_id}）吗？此操作不可逆。`)) {
    return
  }
  try {
    await api.deleteProduct(item.id)
    toast.push('商品已删除')
    await loadProducts()
  } catch (err) {
    toast.push(err.message || '删除失败', 'info')
  }
}

// 图片上传处理
function triggerPhotoUpload() {
  fileInput.value?.click()
}

async function onPhotoSelected(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return

  if (!editingId.value) {
    toast.push('请先保存商品基础信息后，再上传照片', 'info')
    return
  }

  uploading.value = true
  try {
    const { data } = await api.uploadProductPhoto(editingId.value, file)
    form.image = data.image || ''
    // 同时更新本地列表相应项
    const match = products.value.find((p) => p.id === editingId.value)
    if (match) match.image = data.image || ''
    toast.push('商品照片已上传并关联')
  } catch (err) {
    toast.push(err.message || '照片上传失败', 'info')
  } finally {
    uploading.value = false
  }
}

// 绑定弹窗逻辑
function openBindings(item) {
  bindingProduct.value = item
  bindingSearch.value = ''
  const isDevice = item.category === 'device' || item.category === 'hardware'
  if (isDevice) {
    selectedBindings.value = [...(item.bound_consumables || [])]
  } else {
    selectedBindings.value = [...(item.bound_devices || [])]
  }
  showBindingsModal.value = true
}

const availableBindingCandidates = computed(() => {
  if (!bindingProduct.value) return []
  const isDevice = bindingProduct.value.category === 'device' || bindingProduct.value.category === 'hardware'
  const kw = bindingSearch.value.trim().toLowerCase()

  return products.value.filter((p) => {
    if (p.id === bindingProduct.value.id) return false
    // 若当前是硬件，候选展示耗材与配件；若当前是耗材/配件，候选展示硬件
    if (isDevice) {
      const isCandidate = p.category === 'consumable' || p.category === 'accessory' || p.category === 'consumables'
      if (!isCandidate) return false
    } else {
      const isCandidate = p.category === 'hardware' || p.category === 'device'
      if (!isCandidate) return false
    }
    if (kw) {
      return (p.name || '').toLowerCase().includes(kw) || (p.sku_id || '').toLowerCase().includes(kw)
    }
    return true
  })
})

function toggleBinding(skuId) {
  const idx = selectedBindings.value.indexOf(skuId)
  if (idx >= 0) {
    selectedBindings.value.splice(idx, 1)
  } else {
    selectedBindings.value.push(skuId)
  }
}

async function saveBindings() {
  if (!bindingProduct.value) return
  savingBindings.value = true
  const isDevice = bindingProduct.value.category === 'device' || bindingProduct.value.category === 'hardware'
  const payload = isDevice
    ? { consumable_sku_ids: [...selectedBindings.value] }
    : { device_sku_ids: [...selectedBindings.value] }

  try {
    await api.updateProductBindings(bindingProduct.value.id, payload)
    toast.push('产品绑定关系已成功更新')
    showBindingsModal.value = false
    await loadProducts()
  } catch (err) {
    toast.push(err.message || '更新绑定关系失败', 'info')
  } finally {
    savingBindings.value = false
  }
}

onMounted(loadProducts)
</script>

<template>
  <div class="wb-page">
    <!-- 头部横幅 -->
    <div class="wb-page-head">
      <div class="wb-page-title-row">
        <div class="wb-head-chip product">
          <Package :size="20" />
        </div>
        <div>
          <div class="wb-head-title-wrap">
            <h1 class="wb-page-title">商品中心</h1>
            <span class="wb-pill-total">总计 {{ products.length }} 个单品</span>
          </div>
          <p class="wb-page-sub">通用商品目录、分类、规格型号、指导价格与关联绑定集中管控</p>
        </div>
      </div>
      <button class="btn btn-primary" @click="openCreate">
        <Plus :size="16" />
        新增商品
      </button>
    </div>

    <!-- 分类标签切换栏 -->
    <div class="wb-cat-tabs">
      <button
        v-for="tab in CATEGORY_TABS"
        :key="tab.key"
        class="wb-cat-tab-btn"
        :class="{ active: activeCategoryTab === tab.key }"
        @click="activeCategoryTab = tab.key"
      >
        <span>{{ tab.label }}</span>
        <span class="wb-cat-badge">{{ categoryCounts[tab.key] || 0 }}</span>
      </button>
    </div>

    <!-- 搜索与筛选工具条 -->
    <div class="wb-toolbar">
      <div class="wb-toolbar-left">
        <div class="wb-search">
          <Search :size="15" />
          <input
            v-model="keyword"
            class="input"
            type="text"
            placeholder="搜索商品名称 / SKU / 规格型号 / 备注"
          />
        </div>
        <select v-model="statusFilter" class="wb-select">
          <option value="all">全部状态</option>
          <option value="active">仅启用</option>
          <option value="inactive">仅停用</option>
        </select>
      </div>
      <div class="wb-toolbar-right">
        <span class="wb-count">当前展示 {{ filteredProducts.length }} 项</span>
        <button class="wb-refresh-btn" title="刷新列表" @click="loadProducts">
          <RefreshCw :size="14" :class="{ spin: loading }" />
        </button>
      </div>
    </div>

    <!-- 商品列表表格 -->
    <div class="wb-table-wrap">
      <table class="wb-table">
        <thead>
          <tr>
            <th style="width: 100px;">SKU 编码</th>
            <th>商品名称</th>
            <th style="width: 110px;">分类</th>
            <th style="width: 150px;">规格型号</th>
            <th class="num" style="width: 140px;">参考价格</th>
            <th style="width: 70px;">单位</th>
            <th style="width: 80px;">状态</th>
            <th style="width: 70px;">图片</th>
            <th style="width: 120px;">绑定关系</th>
            <th class="ops" style="width: 120px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="empty">
              <RefreshCw :size="20" class="spin mb-2" />
              <div>加载中…</div>
            </td>
          </tr>
          <tr v-else-if="filteredProducts.length === 0">
            <td colspan="10" class="empty">
              <Package :size="28" style="opacity: 0.3; margin: 0 auto 8px;" />
              <div>暂无符合条件的商品数据</div>
            </td>
          </tr>
          <tr v-for="item in filteredProducts" v-else :key="item.id">
            <!-- SKU -->
            <td>
              <span class="wb-sku">{{ item.sku_id }}</span>
            </td>

            <!-- 名称 -->
            <td>
              <div class="wb-name-cell">
                <span class="wb-product-name">{{ item.name }}</span>
                <span v-if="item.remark" class="wb-product-remark" :title="item.remark">{{ item.remark }}</span>
              </div>
            </td>

            <!-- 分类 -->
            <td>
              <span class="wb-cat-tag" :class="getCategoryBadge(item.category).class">
                {{ getCategoryBadge(item.category).label }}
              </span>
            </td>

            <!-- 规格型号 -->
            <td>
              <span class="wb-spec-cell">{{ item.spec || '—' }}</span>
            </td>

            <!-- 参考价格 -->
            <td class="num price">
              <div v-if="item.min_price != null && item.max_price != null && item.min_price !== item.max_price">
                {{ formatMoney(item.min_price, item.min_price % 1 ? 2 : 0) }} ~ {{ formatMoney(item.max_price, item.max_price % 1 ? 2 : 0) }}
              </div>
              <div v-else-if="item.min_price != null">
                {{ formatMoney(item.min_price, item.min_price % 1 ? 2 : 0) }}
              </div>
              <div v-else-if="item.max_price != null">
                {{ formatMoney(item.max_price, item.max_price % 1 ? 2 : 0) }}
              </div>
              <span v-else class="text-muted">—</span>
            </td>

            <!-- 单位 -->
            <td>
              <span class="wb-unit-pill">{{ item.unit || '—' }}</span>
            </td>

            <!-- 启用状态 -->
            <td>
              <button
                class="wb-status-badge"
                :class="{ active: item.is_active !== false, inactive: item.is_active === false }"
                :title="item.is_active !== false ? '点击停用' : '点击启用'"
                @click="toggleActiveStatus(item)"
              >
                <span class="wb-status-dot"></span>
                <span>{{ item.is_active !== false ? '启用' : '停用' }}</span>
              </button>
            </td>

            <!-- 图片 -->
            <td>
              <img
                v-if="item.image"
                :src="resolveImage(item.image)"
                class="wb-thumb"
                alt=""
                @error="(e) => (e.target.style.display = 'none')"
              />
              <span v-else class="wb-thumb-empty">—</span>
            </td>

            <!-- 绑定关系 -->
            <td>
              <button
                class="wb-bind-badge"
                :class="{
                  bound: (item.bound_consumables?.length || item.bound_devices?.length),
                  free: !(item.bound_consumables?.length || item.bound_devices?.length)
                }"
                title="点击管理绑定关系"
                @click="openBindings(item)"
              >
                <Link2 :size="12" />
                <span v-if="item.bound_consumables?.length">已绑耗材 ({{ item.bound_consumables.length }})</span>
                <span v-else-if="item.bound_devices?.length">已绑设备 ({{ item.bound_devices.length }})</span>
                <span v-else>自由搭配</span>
              </button>
            </td>

            <!-- 操作 -->
            <td class="ops">
              <button class="wb-row-btn" title="编辑商品" @click="openEdit(item)">
                <Pencil :size="15" />
              </button>
              <button class="wb-row-btn" title="维护绑定关系" @click="openBindings(item)">
                <Link2 :size="15" />
              </button>
              <button class="wb-row-btn danger" title="删除商品" @click="removeProduct(item)">
                <Trash2 :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增 / 编辑商品模态弹窗 -->
    <WbModal :open="showForm" :title="`${editingId ? '编辑' : '新增'}商品`" width="660px" @close="showForm = false">
      <div class="wb-form">
        <!-- 商品名称 -->
        <div class="wb-form-row full">
          <label>商品名称 <span class="required">*</span></label>
          <input
            v-model="form.name"
            class="input"
            type="text"
            placeholder="例如：超声波治疗仪 CSY-200（台式） / 医用超声耦合剂"
          />
        </div>

        <!-- SKU 编码 -->
        <div class="wb-form-row">
          <label>SKU 编码</label>
          <input
            v-model="form.sku_id"
            class="input"
            type="text"
            placeholder="留空自动根据分类生成"
          />
        </div>

        <!-- 分类选择 -->
        <div class="wb-form-row">
          <label>商品分类 <span class="required">*</span></label>
          <select v-model="form.category" class="wb-select-full">
            <option v-for="cat in CATEGORY_PRESETS" :key="cat.value" :value="cat.value">
              {{ cat.label }}
            </option>
          </select>
        </div>

        <!-- 自定义分类输入 -->
        <div v-if="form.category === 'custom'" class="wb-form-row full">
          <label>自定义分类名称 <span class="required">*</span></label>
          <input
            v-model="customCategoryInput"
            class="input"
            type="text"
            placeholder="例如：software / sensor / maintenance"
          />
        </div>

        <!-- 规格型号 -->
        <div class="wb-form-row">
          <label>规格型号</label>
          <input
            v-model="form.spec"
            class="input"
            type="text"
            placeholder="例如：4核/16G/512G、250g/支"
          />
        </div>

        <!-- 计价单位 -->
        <div class="wb-form-row">
          <label>计价单位</label>
          <div class="wb-unit-input-group">
            <input v-model="form.unit" class="input" type="text" placeholder="台 / 套 / 支 / 袋 / 人天" />
            <div class="wb-quick-units">
              <button
                v-for="u in COMMON_UNITS"
                :key="u"
                type="button"
                class="wb-quick-unit-btn"
                :class="{ on: form.unit === u }"
                @click="form.unit = u"
              >
                {{ u }}
              </button>
            </div>
          </div>
        </div>

        <!-- 最低参考价 -->
        <div class="wb-form-row">
          <label>最低参考底价（元）</label>
          <input
            v-model="form.min_price"
            class="input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
          />
        </div>

        <!-- 最高指导价 -->
        <div class="wb-form-row">
          <label>最高指导售价（元）</label>
          <input
            v-model="form.max_price"
            class="input"
            type="number"
            min="0"
            step="0.01"
            placeholder="建议零售/目录标价"
          />
        </div>

        <!-- 启用状态 -->
        <div class="wb-form-row full">
          <label class="wb-checkbox-label">
            <input v-model="form.is_active" type="checkbox" />
            <span>商品启用状态（未启用的商品在前端报价选单中默认隐藏）</span>
          </label>
        </div>

        <!-- 适用设备说明 -->
        <div class="wb-form-row full">
          <label>适用设备 / 适配机型</label>
          <input
            v-model="form.applicable_devices"
            class="input"
            type="text"
            placeholder="例如：CSY-200, CSY-300（非必填）"
          />
        </div>

        <!-- 耗材/装箱辅助参数 (仅耗材或有打包时) -->
        <div class="wb-form-row">
          <label>每箱包装数量（选填）</label>
          <input
            v-model="form.units_per_box"
            class="input"
            type="number"
            min="1"
            placeholder="例如 20 袋/箱"
          />
        </div>
        <div class="wb-form-row">
          <label>整箱特惠价格（元，选填）</label>
          <input
            v-model="form.box_price"
            class="input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
          />
        </div>

        <!-- 商品照片上传 -->
        <div class="wb-form-row full">
          <label>商品照片</label>
          <div class="wb-image-row">
            <input v-model="form.image" class="input" type="text" placeholder="/uploads/products/xxx.jpg 或远程 URL" />
            <input
              ref="fileInput"
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              style="display: none;"
              @change="onPhotoSelected"
            />
            <button
              type="button"
              class="btn btn-secondary"
              :disabled="uploading || !editingId"
              :title="!editingId ? '请先保存后上传' : '上传本地图片'"
              @click="triggerPhotoUpload"
            >
              <ImagePlus :size="15" />
              {{ uploading ? '上传中…' : '上传照片' }}
            </button>
          </div>
          <div v-if="form.image" class="wb-image-preview-wrap">
            <img :src="resolveImage(form.image)" class="wb-image-preview" alt="商品预览" />
          </div>
        </div>

        <!-- 备注信息 -->
        <div class="wb-form-row full">
          <label>商品备注 / 特性说明</label>
          <textarea
            v-model="form.remark"
            class="input wb-textarea"
            rows="2"
            placeholder="填写产品核心亮点、出厂配置或保修说明等"
          ></textarea>
        </div>
      </div>

      <template #footer>
        <button class="btn" @click="showForm = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submitForm">
          {{ saving ? '保存中…' : '保存商品' }}
        </button>
      </template>
    </WbModal>

    <!-- 绑定关系配置模态弹窗 -->
    <WbModal
      :open="showBindingsModal"
      :title="`配置绑定关系：${bindingProduct?.name || ''} (${bindingProduct?.sku_id || ''})`"
      width="640px"
      @close="showBindingsModal = false"
    >
      <div class="wb-binding-modal-body">
        <p class="wb-binding-intro">
          当前配置该商品在方案组合或报价搭配时的关联关系。未绑定的商品在报价端默认可自由组合。
        </p>

        <div class="wb-binding-search-bar">
          <Search :size="14" />
          <input
            v-model="bindingSearch"
            type="text"
            class="input"
            placeholder="搜索候选商品名称或 SKU…"
          />
        </div>

        <div class="wb-binding-chips-container">
          <div
            v-for="cand in availableBindingCandidates"
            :key="cand.sku_id"
            class="wb-binding-candidate-card"
            :class="{ selected: selectedBindings.includes(cand.sku_id) }"
            @click="toggleBinding(cand.sku_id)"
          >
            <div class="wb-candidate-check">
              <Check v-if="selectedBindings.includes(cand.sku_id)" :size="13" />
            </div>
            <div class="wb-candidate-info">
              <div class="wb-candidate-sku">{{ cand.sku_id }}</div>
              <div class="wb-candidate-name">{{ cand.name }}</div>
            </div>
          </div>
          <div v-if="availableBindingCandidates.length === 0" class="wb-binding-empty">
            暂无匹配的候选商品
          </div>
        </div>

        <div class="wb-binding-summary">
          已选中 <strong>{{ selectedBindings.length }}</strong> 项关联商品
        </div>
      </div>

      <template #footer>
        <button class="btn" @click="showBindingsModal = false">取消</button>
        <button class="btn btn-primary" :disabled="savingBindings" @click="saveBindings">
          {{ savingBindings ? '保存中…' : '保存绑定' }}
        </button>
      </template>
    </WbModal>
  </div>
</template>

<style scoped>
.wb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.wb-head-chip.product {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-head-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wb-page-title {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
}

.wb-pill-total {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-alt);
  color: var(--muted);
  border: 1px solid var(--border);
}

.wb-page-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}

/* 分类 Tab */
.wb-cat-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 0;
  border-bottom: 1px solid var(--border);
}

.wb-cat-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--muted);
  background: transparent;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.wb-cat-tab-btn:hover {
  color: var(--text);
  background: #fff;
}

.wb-cat-tab-btn.active {
  color: var(--primary-dark);
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  font-weight: 700;
}

.wb-cat-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--bg-alt);
  color: var(--muted);
}

.wb-cat-tab-btn.active .wb-cat-badge {
  background: var(--primary-light);
  color: var(--primary-dark);
}

/* 工具栏 */
.wb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.wb-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 280px;
}

.wb-toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wb-search {
  position: relative;
  width: min(340px, 100%);
}

.wb-search svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.wb-search .input {
  width: 100%;
  padding-left: 36px;
  height: 38px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
}

.wb-select {
  height: 38px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 13px;
  color: var(--text);
  outline: none;
}

.wb-count {
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}

.wb-refresh-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.wb-refresh-btn:hover {
  color: var(--text);
  border-color: var(--primary);
}

/* 表格容器 */
.wb-table-wrap {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow-x: auto;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.wb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
  min-width: 900px;
}

.wb-table th,
.wb-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: middle;
}

.wb-table th {
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.wb-table tbody tr:last-child td {
  border-bottom: none;
}

.wb-table tbody tr:hover {
  background: #fdfdfe;
}

.wb-table .num {
  text-align: right;
}

.wb-table .price {
  color: var(--primary-dark);
  font-weight: 700;
  white-space: nowrap;
}

.wb-table .ops {
  text-align: right;
  white-space: nowrap;
}

.wb-table .empty {
  text-align: center;
  color: var(--muted);
  padding: 48px 14px;
}

/* 表格单元格样式 */
.wb-sku {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.wb-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 160px;
}

.wb-product-name {
  font-weight: 600;
  color: var(--text);
}

.wb-product-remark {
  font-size: 11.5px;
  color: var(--muted);
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-cat-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.cat-hardware {
  background: #e0f2fe;
  color: #0369a1;
}

.cat-consumable {
  background: #dcfce7;
  color: #15803d;
}

.cat-accessory {
  background: #fef3c7;
  color: #b45309;
}

.cat-service {
  background: #f3e8ff;
  color: #7e22ce;
}

.cat-other {
  background: #f1f5f9;
  color: #475569;
}

.wb-spec-cell {
  color: var(--muted);
  font-size: 12.5px;
}

.wb-unit-pill {
  font-size: 12px;
  color: var(--muted);
}

/* 状态徽章 */
.wb-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}

.wb-status-badge.active {
  background: #ecfdf5;
  color: #047857;
  border-color: #a7f3d0;
}

.wb-status-badge.inactive {
  background: #f1f5f9;
  color: #64748b;
  border-color: #e2e8f0;
}

.wb-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.wb-thumb {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--border);
  background: var(--bg-alt);
}

.wb-thumb-empty {
  display: inline-grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 8px;
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
}

.wb-bind-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}

.wb-bind-badge.bound {
  background: var(--primary-light);
  color: var(--primary-dark);
  border-color: #bfdbfe;
}

.wb-bind-badge.free {
  background: var(--bg-alt);
  color: var(--muted);
  border-color: var(--border);
}

.wb-row-btn {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  margin-left: 2px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.wb-row-btn:hover {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-row-btn.danger:hover {
  background: var(--rose-light);
  color: var(--rose);
}

/* 表单样式 */
.wb-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.wb-form-row {
  display: grid;
  gap: 6px;
}

.wb-form-row.full {
  grid-column: 1 / -1;
}

.wb-form-row label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.wb-form-row label .required {
  color: var(--rose);
}

.wb-select-full {
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 13.5px;
  color: var(--text);
  outline: none;
}

.wb-unit-input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wb-quick-units {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.wb-quick-unit-btn {
  padding: 2px 7px;
  font-size: 11px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: var(--bg-alt);
  color: var(--muted);
  cursor: pointer;
}

.wb-quick-unit-btn.on {
  background: var(--primary-light);
  color: var(--primary-dark);
  border-color: var(--primary);
  font-weight: 700;
}

.wb-checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px !important;
  color: var(--text) !important;
  font-weight: 500 !important;
  cursor: pointer;
}

.wb-checkbox-label input {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

.wb-image-row {
  display: flex;
  gap: 8px;
}

.wb-image-preview-wrap {
  margin-top: 8px;
}

.wb-image-preview {
  max-width: 140px;
  max-height: 90px;
  border-radius: 8px;
  border: 1px solid var(--border);
  object-fit: cover;
}

.wb-textarea {
  resize: vertical;
  padding: 8px 12px;
}

/* 绑定关系弹窗内部 */
.wb-binding-modal-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.wb-binding-intro {
  font-size: 13px;
  color: var(--muted);
  line-height: 1.5;
}

.wb-binding-search-bar {
  position: relative;
}

.wb-binding-search-bar svg {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.wb-binding-search-bar .input {
  width: 100%;
  padding-left: 32px;
  height: 36px;
  border-radius: 6px;
}

.wb-binding-chips-container {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
}

.wb-binding-candidate-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  cursor: pointer;
  transition: all 0.15s ease;
}

.wb-binding-candidate-card:hover {
  border-color: var(--primary);
  background: var(--bg-alt);
}

.wb-binding-candidate-card.selected {
  border-color: var(--primary);
  background: var(--primary-light);
}

.wb-candidate-check {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--primary);
  flex: none;
}

.wb-binding-candidate-card.selected .wb-candidate-check {
  border-color: var(--primary);
  background: var(--primary);
  color: #fff;
}

.wb-candidate-sku {
  font-size: 11px;
  color: var(--muted);
  font-weight: 700;
}

.wb-candidate-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-binding-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--muted);
  padding: 24px;
  font-size: 13px;
}

.wb-binding-summary {
  font-size: 12.5px;
  color: var(--muted);
  border-top: 1px solid var(--border);
  padding-top: 10px;
}

.spin {
  animation: wb-spin 1s linear infinite;
}

@keyframes wb-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
