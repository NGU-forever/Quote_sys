<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Pencil, Plus, Trash2 } from 'lucide-vue-next'
import WbModal from '../components/WbModal.vue'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'
import { formatMoney } from '../../shared/utils/format'

const toast = useToast()

const packages = ref([])
const products = ref([])
const loading = ref(false)
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)

const form = reactive({
  name: '',
  package_id: '',
  std_price: '',
  discount_price: '',
  discount_rate: '',
  device_qty: '',
  consumable_qty: '',
  consumable_boxes: '',
  fixed_bundle: false,
  device_price: '',
  note: ''
})

const items = ref([{ sku_id: '', quantity: '' }])

const skuNameMap = computed(() => {
  const map = {}
  products.value.forEach((p) => {
    map[p.sku_id] = p.name
  })
  return map
})

// ---- 设备-耗材绑定：绑定了耗材的设备在前端选耗材时受限，未绑定设备可自由搭配 ----

/** 设备 sku → 绑定耗材 sku 列表（来自后端 device_bindings，随产品接口返回） */
const deviceBindings = computed(() => {
  const map = {}
  products.value.forEach((p) => {
    if (p.category === 'device') map[p.sku_id] = p.bound_consumables || []
  })
  return map
})

/** 表单中已选中的设备 sku */
const selectedDeviceSkus = computed(() =>
  items.value
    .filter((r) => {
      const p = products.value.find((x) => x.sku_id === r.sku_id)
      return p?.category === 'device'
    })
    .map((r) => r.sku_id)
)

/**
 * 当前可选的耗材 sku 列表；null 表示无限制（全部可选）：
 * - 未选设备 → 全部耗材；
 * - 存在未绑定耗材的设备 → 该设备可自由搭配，全部耗材可选；
 * - 全部设备均已绑定 → 仅限各设备绑定耗材的并集。
 */
const allowedConsumableSkus = computed(() => {
  const devices = selectedDeviceSkus.value
  if (devices.length === 0) return null
  const boundLists = devices.map((sku) => deviceBindings.value[sku] || [])
  if (boundLists.some((list) => list.length === 0)) return null
  return [...new Set(boundLists.flat())]
})

/** 是否处于绑定受限状态（已选设备且全部有绑定） */
const restricted = computed(
  () => selectedDeviceSkus.value.length > 0 && allowedConsumableSkus.value !== null
)

/** 耗材下拉选项：受限时仅显示绑定并集；同时保留已选中但已失配的项（编辑历史套餐时避免选项丢失） */
const consumableOptions = computed(() => {
  const all = products.value.filter((x) => x.category === 'consumable')
  const allowed = allowedConsumableSkus.value
  if (!allowed) return all
  const selected = new Set(items.value.filter((r) => r.sku_id).map((r) => r.sku_id))
  return all.filter((x) => allowed.includes(x.sku_id) || selected.has(x.sku_id))
})

const allowedConsumableNames = computed(() =>
  (allowedConsumableSkus.value || []).map((sku) => skuNameMap.value[sku] || sku).join('、')
)

/** SKU 变更后清理失配的耗材行（设备切换导致其绑定的耗材变化时） */
function onSkuChange() {
  const allowed = allowedConsumableSkus.value
  if (!allowed) return
  items.value.forEach((r) => {
    const p = products.value.find((x) => x.sku_id === r.sku_id)
    if (p?.category === 'consumable' && r.sku_id && !allowed.includes(r.sku_id)) {
      r.sku_id = ''
    }
  })
}

async function load() {
  loading.value = true
  try {
    const [pkgRes, prodRes] = await Promise.all([api.listPackages(), api.listProducts()])
    packages.value = pkgRes.data
    products.value = prodRes.data
  } catch (err) {
    toast.push(err.message || '加载失败', 'info')
  } finally {
    loading.value = false
  }
}

function resetItems() {
  items.value = [{ sku_id: '', quantity: '' }]
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    package_id: '',
    std_price: '',
    discount_price: '',
    discount_rate: '',
    device_qty: '',
    consumable_qty: '',
    consumable_boxes: '',
    fixed_bundle: false,
    device_price: '',
    note: ''
  })
  resetItems()
  applyDerivedParams()
  showForm.value = true
}

function openEdit(pkg) {
  editingId.value = pkg.id
  Object.assign(form, {
    name: pkg.name || '',
    package_id: pkg.package_id || '',
    std_price: pkg.std_price ?? '',
    discount_price: pkg.discount_price ?? '',
    discount_rate: pkg.discount_rate || '',
    device_qty: '',
    consumable_qty: '',
    consumable_boxes: '',
    fixed_bundle: Boolean(pkg.fixed_bundle),
    device_price: pkg.device_price ?? '',
    note: pkg.note || ''
  })
  items.value = pkg.sku_ids.map((sku, i) => ({
    sku_id: sku,
    quantity: pkg.quantities[i] == null ? '' : pkg.quantities[i]
  }))
  applyDerivedParams()
  showForm.value = true
}

function addRow() {
  items.value.push({ sku_id: '', quantity: '' })
}

function removeRow(index) {
  if (items.value.length === 1) return
  items.value.splice(index, 1)
}

/**
 * 根据当前 SKU 明细 + 产品目录自动推导套餐报价参数。
 * 与后端保持一致：
 * - 固定整购：所有设备/耗材 SKU 都计入同一套；
 * - 赠机/推广：耗材行为“任选其一”，只按首个耗材行计算单套数量/箱数。
 */
function derivePackageParams() {
  const fixedBundle = form.fixed_bundle
  const rows = items.value.filter((r) => r.sku_id)
  let deviceQty = ''
  let consumableQty = ''
  let consumableBoxes = ''
  let boxTotal = 0
  let sawBox = false
  for (const row of rows) {
    const p = products.value.find((x) => x.sku_id === row.sku_id)
    const qty = row.quantity === '' ? null : Number(row.quantity)
    if (!p) continue
    if (p.category === 'device') {
      if (fixedBundle) {
        deviceQty = (deviceQty === '' ? 0 : deviceQty) + (qty ?? 1)
      } else if (deviceQty === '') {
        deviceQty = qty ?? 1
      }
    } else {
      const unitQty = qty ?? 0
      if (fixedBundle) {
        consumableQty = (consumableQty === '' ? 0 : consumableQty) + unitQty
        if (Number(p.units_per_box) > 0) {
          sawBox = true
          boxTotal += unitQty / Number(p.units_per_box)
        }
      } else if (consumableQty === '') {
        consumableQty = unitQty
        if (Number(p.units_per_box) > 0) {
          sawBox = true
          boxTotal += unitQty / Number(p.units_per_box)
        }
      }
    }
  }
  if (sawBox) consumableBoxes = Math.round(boxTotal)
  return { device_qty: deviceQty, consumable_qty: consumableQty, consumable_boxes: consumableBoxes }
}

function applyDerivedParams() {
  Object.assign(form, derivePackageParams())
}

// SKU 明细或套餐类型变化时自动重推报价参数，避免旧参数带到 Quote。
watch(items, applyDerivedParams, { deep: true })
watch(() => form.fixed_bundle, applyDerivedParams)

function toNum(value) {
  if (value === '' || value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

async function submit() {
  if (!form.name.trim()) {
    toast.push('请填写套餐名称', 'info')
    return
  }
  const rows = items.value.filter((r) => r.sku_id)
  if (rows.length === 0) {
    toast.push('请至少选择一个 SKU', 'info')
    return
  }
  saving.value = true
  const payload = {
    name: form.name.trim(),
    package_id: form.package_id.trim(),
    sku_ids: rows.map((r) => r.sku_id),
    quantities: rows.map((r) => (r.quantity === '' ? null : Number(r.quantity))),
    std_price: toNum(form.std_price),
    discount_price: toNum(form.discount_price),
    discount_rate: form.discount_rate.trim(),
    device_qty: toNum(form.device_qty),
    consumable_qty: toNum(form.consumable_qty),
    consumable_boxes: toNum(form.consumable_boxes),
    fixed_bundle: form.fixed_bundle,
    device_price: toNum(form.device_price),
    note: form.note.trim()
  }
  try {
    if (editingId.value) {
      await api.updatePackage(editingId.value, payload)
      toast.push('已保存修改')
    } else {
      await api.createPackage(payload)
      toast.push('已新增套餐')
    }
    showForm.value = false
    await load()
  } catch (err) {
    toast.push(err.message || '保存失败', 'info')
  } finally {
    saving.value = false
  }
}

async function remove(pkg) {
  if (!window.confirm(`确定删除套餐「${pkg.name}」？`)) return
  try {
    await api.deletePackage(pkg.id)
    toast.push('已删除')
    await load()
  } catch (err) {
    toast.push(err.message || '删除失败', 'info')
  }
}

function skuLabel(skuIds) {
  return skuIds
    .map((sku) => (skuNameMap.value[sku] ? skuNameMap.value[sku].slice(0, 8) : sku))
    .join('、')
}

onMounted(load)
</script>

<template>
  <div class="wb-page">
    <div class="wb-page-head">
      <div>
        <h1 class="wb-page-title">套餐管理</h1>
        <p class="wb-page-sub">维护设备 + 耗材的组合套餐与套餐价格</p>
      </div>
      <button class="btn btn-primary" @click="openCreate">
        <Plus :size="16" />
        新增套餐
      </button>
    </div>

    <div class="wb-table-wrap">
      <table class="wb-table">
        <thead>
          <tr>
            <th>套餐ID</th>
            <th>名称</th>
            <th>包含 SKU</th>
            <th class="num">标准价</th>
            <th class="num">折扣价</th>
            <th>备注</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="empty">加载中…</td>
          </tr>
          <tr v-else-if="packages.length === 0">
            <td colspan="7" class="empty">暂无套餐，点击右上角「新增套餐」开始录入</td>
          </tr>
          <tr v-for="pkg in packages" v-else :key="pkg.id">
            <td>
              <span class="wb-sku">{{ pkg.package_id }}</span>
            </td>
            <td>
              <strong>{{ pkg.name }}</strong>
            </td>
            <td class="wb-sku-list">{{ skuLabel(pkg.sku_ids) }}</td>
            <td class="num price">
              {{ pkg.std_price != null ? formatMoney(pkg.std_price) : '—' }}
            </td>
            <td class="num">
              {{ pkg.discount_price != null ? formatMoney(pkg.discount_price) : '—' }}
            </td>
            <td class="wb-note">{{ pkg.note || '—' }}</td>
            <td class="ops">
              <button class="wb-row-btn" title="编辑" @click="openEdit(pkg)">
                <Pencil :size="15" />
              </button>
              <button class="wb-row-btn danger" title="删除" @click="remove(pkg)">
                <Trash2 :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <WbModal
      :open="showForm"
      :title="`${editingId ? '编辑' : '新增'}套餐`"
      @close="showForm = false"
    >
      <div class="wb-form">
        <div class="wb-form-row full">
          <label>套餐名称</label>
          <input
            v-model="form.name"
            class="input"
            type="text"
            placeholder="例如：超声治疗（台式）推广套餐"
          />
        </div>
        <div class="wb-form-row">
          <label>套餐ID</label>
          <input
            v-model="form.package_id"
            class="input"
            type="text"
            placeholder="留空自动生成（PKG***）"
          />
        </div>
        <div class="wb-form-row">
          <label>折扣率</label>
          <input
            v-model="form.discount_rate"
            class="input"
            type="text"
            placeholder="可选，如 0.9"
          />
        </div>
        <div class="wb-form-row">
          <label>标准价（元）</label>
          <input
            v-model="form.std_price"
            class="input"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
          />
        </div>
        <div class="wb-form-row">
          <label>折扣价（元）</label>
          <input
            v-model="form.discount_price"
            class="input"
            type="number"
            min="0"
            step="0.01"
            placeholder="可留空"
          />
        </div>

        <div class="wb-form-row full">
          <label>包含 SKU 明细</label>
          <div class="wb-sku-rows">
            <div v-for="(row, index) in items" :key="index" class="wb-sku-row">
              <select v-model="row.sku_id" class="select" @change="onSkuChange">
                <option value="" disabled>选择 SKU</option>
                <optgroup label="设备">
                  <option
                    v-for="p in products.filter((x) => x.category === 'device')"
                    :key="p.sku_id"
                    :value="p.sku_id"
                  >
                    {{ p.sku_id }} · {{ p.name }}
                  </option>
                </optgroup>
                <optgroup label="耗材">
                  <option v-for="p in consumableOptions" :key="p.sku_id" :value="p.sku_id">
                    {{ p.sku_id }} · {{ p.name }}
                  </option>
                </optgroup>
              </select>
              <input
                v-model="row.quantity"
                class="input wb-qty"
                type="number"
                min="0"
                placeholder="数量"
              />
              <button class="wb-row-btn danger" title="移除" @click="removeRow(index)">
                <Trash2 :size="15" />
              </button>
            </div>
            <button class="btn btn-soft btn-sm" @click="addRow">
              <Plus :size="14" />
              添加一行
            </button>
            <p v-if="restricted" class="wb-bind-hint">
              所选设备均已绑定耗材，耗材仅限：<strong>{{ allowedConsumableNames }}</strong>
            </p>
            <p v-else-if="selectedDeviceSkus.length > 0" class="wb-bind-hint free">
              所选设备未绑定耗材，耗材可自由搭配任意一款
            </p>
          </div>
        </div>

        <div class="wb-form-row full">
          <div class="wb-params-head">
            <label>套餐报价参数（客户报价计算用）</label>
            <button class="btn btn-soft btn-sm" type="button" @click="applyDerivedParams">
              <Plus :size="13" />
              按明细推导
            </button>
          </div>
          <div class="wb-pkg-params">
            <div class="wb-form-row">
              <label>设备台数/套</label>
              <input
                v-model="form.device_qty"
                class="input"
                type="number"
                min="0"
                placeholder="留空自动推导"
              />
            </div>
            <div class="wb-form-row">
              <label>耗材总数量/套</label>
              <input
                v-model="form.consumable_qty"
                class="input"
                type="number"
                min="0"
                placeholder="留空自动推导"
              />
            </div>
            <div class="wb-form-row">
              <label>耗材箱数/套</label>
              <input
                v-model="form.consumable_boxes"
                class="input"
                type="number"
                min="0"
                placeholder="留空自动推导"
              />
            </div>
          </div>
          <label class="wb-check">
            <input v-model="form.fixed_bundle" type="checkbox" @change="applyDerivedParams" />
            固定整购套餐（整套固定价；SKU 明细均计入同一套）
          </label>
          <p class="wb-bind-note">
            未勾选时按赠机/推广方案处理：填写一台设备与适配耗材，多款耗材视为“任选其一”。
          </p>
          <div v-if="form.fixed_bundle" class="wb-form-row wb-device-price">
            <label>套餐内固定设备单价（元/台）</label>
            <input
              v-model="form.device_price"
              class="input"
              type="number"
              min="0"
              step="0.01"
              placeholder="如 9000"
            />
          </div>
        </div>

        <div class="wb-form-row full">
          <label>备注</label>
          <textarea
            v-model="form.note"
            class="textarea"
            placeholder="例如：买2箱送1台设备，设备为赠送"
          ></textarea>
        </div>
      </div>
      <template #footer>
        <button class="btn" @click="showForm = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </WbModal>
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

.wb-page-title {
  font-size: 24px;
  font-weight: 800;
}

.wb-page-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}

.wb-table-wrap {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow-x: auto;
}

.wb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
  min-width: 720px;
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
  padding: 36px 14px;
}

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

.wb-sku-list {
  color: var(--muted);
  font-size: 12px;
  max-width: 240px;
}

.wb-note {
  color: var(--muted);
  font-size: 12px;
  max-width: 260px;
}

.wb-row-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  margin-left: 4px;
}

.wb-row-btn:hover {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-row-btn.danger:hover {
  background: var(--rose-light);
  color: var(--rose);
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

.wb-form-row label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.wb-sku-rows {
  display: grid;
  gap: 10px;
}

.wb-sku-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px 32px;
  gap: 8px;
  align-items: center;
}

.wb-bind-hint {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--primary-light);
  color: var(--primary-dark);
  font-size: 12px;
  line-height: 1.6;
}

.wb-bind-hint.free {
  background: var(--bg-alt);
  color: var(--muted);
}

.wb-bind-hint strong {
  font-weight: 800;
}

.wb-qty {
  text-align: right;
}

.wb-params-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.wb-pkg-params {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 8px;
}

.wb-check {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.wb-check input {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
}

.wb-device-price {
  margin-top: 10px;
}
</style>
