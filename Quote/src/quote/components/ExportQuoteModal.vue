<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { Download, X } from 'lucide-vue-next'
import { useCatalogStore } from '../../shared/stores/catalog'
import { useQuoteStore } from '../stores/quote'
import { formatMoney, today } from '../../shared/utils/format'
import { moneyText, printQuoteDocument } from '../utils/printQuote'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  logoUrl: {
    type: String,
    default: ''
  },
  iframeEl: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'exported'])
const quote = useQuoteStore()
const catalog = useCatalogStore()
const customerInputRef = ref(null)

const exportForm = reactive({
  customerName: '',
  contactPerson: '',
  contactPhone: '',
  quoter: '',
  quoterPhone: '',
  scheme: 'plan1',
  planKey: null,
  deviceUnit: 0,
  consumableUnit: 0,
  paidTotal: 0
})

const directPackage = computed(() => quote.activePackage)
const directPackageRows = computed(() =>
  quote.packageModeRows.map((item) => {
    const product = catalog.productById(item.productId ?? item.id)
    return {
      ...item,
      category: item.category || product?.category || 'consumable',
      name: item.name || product?.name || '未知产品',
      unit: item.unit || product?.unit || '套',
      spec: product?.spec || ''
    }
  })
)
const directPackageValid = computed(() => {
  const price = Number(directPackage.value?.price) || 0
  return Boolean(directPackage.value && price > 0 && directPackageRows.value.length > 0)
})

const packageChoices = computed(() => quote.packagePlans.filter((plan) => plan.eligible))
const canPickPackage = computed(
  () => quote.purchaseMode === 'both' && quote.hasPackage && packageChoices.value.length > 0
)

const chosenPackagePlan = computed(() => {
  if (exportForm.scheme !== 'package' || !exportForm.planKey) return null
  return quote.packagePlans.find((plan) => plan.pkg.id === exportForm.planKey) || null
})

const exportStandardTotal = computed(() => {
  if (quote.purchaseMode === 'package') {
    return directPackageValid.value ? quote.packageModeTotal : 0
  }
  if (quote.purchaseMode === 'consumables') return quote.plan1ConsumablesCost
  if (quote.purchaseMode === 'equipment') return quote.plan1DeviceCost
  const plan = chosenPackagePlan.value
  const deviceUnit = Math.max(
    plan ? Number(exportForm.deviceUnit) || 0 : catalog.devicePrice || 0,
    0
  )
  const bags = catalog.bagsPerBox || 1
  const perUnit = Math.max(
    plan ? Number(exportForm.consumableUnit) || 0 : quote.plan1UnitPrice || 0,
    0
  )
  const deviceMoney = quote.devices * deviceUnit
  const consumableMoney = quote.boxes * perUnit * bags
  return Math.round((deviceMoney + consumableMoney) * 100) / 100
})

const exportDiscount = computed(() => {
  if (exportForm.scheme !== 'package') return 0
  const paid = Math.max(Number(exportForm.paidTotal) || 0, 0)
  const diff = exportStandardTotal.value - paid
  return diff > 0 ? diff : 0
})

const exportPaidTotal = computed(() => {
  if (quote.purchaseMode === 'package') {
    return directPackageValid.value ? quote.packageModeTotal : 0
  }
  if (exportForm.scheme === 'package') return Math.max(Number(exportForm.paidTotal) || 0, 0)
  if (quote.purchaseMode === 'consumables') return quote.plan1ConsumablesCost
  if (quote.purchaseMode === 'equipment') return quote.plan1DeviceCost
  return quote.plan1Total
})

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      initForm()
      nextTick(() => {
        customerInputRef.value?.focus()
      })
    }
  }
)

function initForm() {
  const savedQuoter = localStorage.getItem('hhz_quoter_name') || ''
  const savedPhone = localStorage.getItem('hhz_quoter_phone') || ''
  Object.assign(exportForm, {
    customerName: '',
    contactPerson: '',
    contactPhone: '',
    quoter: savedQuoter,
    quoterPhone: savedPhone
  })
  if (quote.purchaseMode === 'package') {
    exportForm.scheme = directPackageValid.value ? 'package' : 'plan1'
    exportForm.planKey = directPackageValid.value ? directPackage.value?.id || null : null
    exportForm.deviceUnit = 0
    exportForm.consumableUnit = 0
    exportForm.paidTotal = directPackageValid.value ? quote.packageModeTotal : 0
    return
  }
  const best = quote.bestPackagePlan
  const canPick =
    canPickPackage.value && best && packageChoices.value.some((p) => p.id === best.pkg.id)
  exportForm.scheme = canPick ? 'package' : 'plan1'
  exportForm.planKey = canPick ? best.pkg.id : null
  syncPlanPricing()
}

function syncPlanPricing() {
  const plan = chosenPackagePlan.value
  if (!plan) {
    exportForm.deviceUnit = 0
    exportForm.consumableUnit = 0
    exportForm.paidTotal = 0
    return
  }
  exportForm.deviceUnit = plan.pkg.devicePrice || catalog.devicePrice || 0
  exportForm.consumableUnit = catalog.priceOf(catalog.selectedConsumableId) || 0
  exportForm.paidTotal = plan.total
}

function onPickScheme(scheme, planKey) {
  exportForm.scheme = scheme
  exportForm.planKey = scheme === 'package' ? planKey : null
  syncPlanPricing()
}

function onDiscountInput(event) {
  const standard = exportStandardTotal.value
  const value = Math.min(Math.max(Number(event.target.value) || 0, 0), Math.max(standard, 0))
  exportForm.paidTotal = Math.round((standard - value) * 100) / 100
}

function applyDiscountPreset(type) {
  const std = exportStandardTotal.value
  if (type === 'reset') {
    exportForm.paidTotal = std
  } else if (type === 'round100') {
    exportForm.paidTotal = Math.max(0, Math.floor(std / 100) * 100)
  } else if (type === 'round1000') {
    exportForm.paidTotal = Math.max(0, Math.floor(std / 1000) * 1000)
  } else if (type === 'p98') {
    exportForm.paidTotal = Math.round(std * 0.98)
  } else if (type === 'p95') {
    exportForm.paidTotal = Math.round(std * 0.95)
  }
}

function schemeSummary(plan) {
  if (!plan) return ''
  if (!plan.valid) return '套餐缺少价格或组成数量，请先在 Workbench 补全'
  if (plan.fixedBundle) {
    return `每套 ${plan.deviceQtyPerSet} 台设备 + ${plan.consumableBoxesPerSet} 箱耗材，本单 ${plan.packagesNeeded} 套`
  }
  return `每套 ${plan.consumableBoxesPerSet} 箱耗材赠 ${plan.deviceQtyPerSet} 台设备，本单 ${plan.packagesNeeded} 套（赠 ${plan.gifted} 台）`
}

function close() {
  emit('update:modelValue', false)
}

function buildExportData() {
  const mode = quote.purchaseMode
  const plan = chosenPackagePlan.value
  const bags = catalog.bagsPerBox || 1
  const directMode = mode === 'package'
  const packageChosen =
    exportForm.scheme === 'package' &&
    (directMode ? Boolean(directPackage.value && directPackageValid.value) : Boolean(plan))

  let planCoverText = ''
  if (directMode && packageChosen && directPackage.value) {
    planCoverText = `${quote.packageSets} 套 × ${formatMoney(
      directPackage.value.price
    )} = ${formatMoney(quote.packageModeTotal)}，按 Workbench 套餐 SKU 明细整购`
  } else if (packageChosen && plan) {
    planCoverText = plan.fixedBundle
      ? `共 ${plan.packagesNeeded} 套（覆盖设备 ${plan.coveredDevices} 台、耗材 ${plan.coveredBoxes} 箱）`
      : `共 ${plan.packagesNeeded} 套（每套 ${plan.consumableBoxesPerSet} 箱耗材、赠 ${plan.deviceQtyPerSet} 台设备；本单 ${quote.boxes} 箱，赠 ${plan.gifted} 台${
          plan.extraDevices > 0 ? `，另补购 ${plan.extraDevices} 台设备` : ''
        }）`
  }

  const modeLabels = {
    both: '同时购买',
    consumables: '仅购耗材',
    equipment: '仅购设备',
    package: '套餐整购'
  }

  return {
    id: `Q${String(Date.now()).slice(-6)}`,
    date: today(),
    mode,
    modeLabel: modeLabels[mode] || '同时购买',
    customerName: exportForm.customerName.trim(),
    contactPerson: exportForm.contactPerson.trim(),
    contactPhone: exportForm.contactPhone.trim(),
    quoter: exportForm.quoter.trim(),
    quoterPhone: exportForm.quoterPhone.trim(),
    deviceName: catalog.selectedDevice?.name || '未选择设备',
    deviceSpec: catalog.selectedDevice?.spec || '-',
    devicePrice: catalog.devicePrice,
    devices: quote.devices,
    consumableName: catalog.selectedConsumable?.name || '未选择耗材',
    consumableSpec: catalog.selectedConsumable?.spec || '-',
    consumableUnitName: catalog.selectedConsumable?.unit || '袋',
    bagsPerBox: bags,
    boxes: quote.boxes,
    plan1UnitPrice: quote.plan1UnitPrice,
    plan1DeviceCost: quote.plan1DeviceCost,
    plan1ConsumablesCost: quote.plan1ConsumablesCost,
    plan1Total: quote.plan1Total,
    packageChosen,
    packageName: directMode ? directPackage.value?.name || null : plan?.pkg.name || null,
    planCoverText,
    packageSets: directMode ? quote.packageSets : 0,
    directItems: directMode
      ? directPackageRows.value.map((item) => ({
          name: item.name,
          spec: item.spec || '-',
          unit: item.unit || '套',
          qty: (Number(item.quantity) || 1) * quote.packageSets,
          note: '套餐内模块'
        }))
      : [],
    deviceUnit: packageChosen ? Number(exportForm.deviceUnit) || 0 : catalog.devicePrice || 0,
    consumableUnit: packageChosen ? Number(exportForm.consumableUnit) || 0 : quote.plan1UnitPrice,
    standardTotal: exportStandardTotal.value,
    discount: exportDiscount.value,
    total: exportPaidTotal.value,
    company: quote.settings.company,
    logoUrl: props.logoUrl
  }
}

function handleGenerate() {
  if (
    quote.purchaseMode !== 'package' &&
    exportForm.scheme === 'package' &&
    !chosenPackagePlan.value
  ) {
    exportForm.scheme = 'plan1'
    exportForm.planKey = null
  }
  if (exportForm.quoter.trim()) {
    localStorage.setItem('hhz_quoter_name', exportForm.quoter.trim())
  }
  if (exportForm.quoterPhone.trim()) {
    localStorage.setItem('hhz_quoter_phone', exportForm.quoterPhone.trim())
  }

  const data = buildExportData()
  quote.saveQuote()
  close()
  if (props.iframeEl) {
    printQuoteDocument(data, props.iframeEl)
  }
  emit('exported', data)
}
</script>

<template>
  <div v-if="modelValue" class="export-overlay" @click.self="close">
    <div class="export-modal" role="dialog" aria-modal="true" aria-label="导出报价单">
      <header class="export-modal-head">
        <h3 class="export-modal-title">导出正式报价单 (PDF)</h3>
        <button class="export-modal-close" type="button" aria-label="关闭" @click="close">
          <X :size="16" />
        </button>
      </header>

      <div class="export-modal-body">
        <div class="export-section">
          <h4 class="export-section-title">客户信息</h4>
          <div class="export-grid-stack">
            <label class="export-field full-width">
              <span>客户名称 / 机构全称</span>
              <input
                ref="customerInputRef"
                v-model="exportForm.customerName"
                class="input"
                type="text"
                placeholder="请输入医院、科室或代理商机构全称"
              />
            </label>
            <div class="export-grid export-grid-2">
              <label class="export-field">
                <span>联系人</span>
                <input
                  v-model="exportForm.contactPerson"
                  class="input"
                  type="text"
                  placeholder="请输入联系人姓名"
                />
              </label>
              <label class="export-field">
                <span>联系电话</span>
                <input
                  v-model="exportForm.contactPhone"
                  class="input"
                  type="text"
                  placeholder="请输入联系电话"
                />
              </label>
            </div>
          </div>
        </div>

        <div class="export-section">
          <div class="export-section-head-row">
            <h4 class="export-section-title">报价人信息</h4>
            <span class="export-section-tag">自动记忆回填</span>
          </div>
          <div class="export-grid export-grid-2">
            <label class="export-field">
              <span>报价销售</span>
              <input
                v-model="exportForm.quoter"
                class="input"
                type="text"
                placeholder="请输入报价人姓名"
              />
            </label>
            <label class="export-field">
              <span>销售电话</span>
              <input
                v-model="exportForm.quoterPhone"
                class="input"
                type="text"
                placeholder="请输入报价人联系电话"
              />
            </label>
          </div>
        </div>

        <!-- 结算方案选择 -->
        <template v-if="quote.purchaseMode === 'both'">
          <div class="export-section">
            <h4 class="export-section-title">结算方案选择</h4>
            <div v-if="canPickPackage" class="export-schemes">
              <button
                type="button"
                class="export-scheme"
                :class="{ active: exportForm.scheme === 'plan1' }"
                @click="onPickScheme('plan1', null)"
              >
                <span class="export-scheme-name">方案1 · 单独采购</span>
                <span class="export-scheme-sub">设备、耗材分别计价</span>
                <span class="export-scheme-amount">合计 {{ formatMoney(quote.plan1Total) }}</span>
              </button>
              <button
                v-for="plan in packageChoices"
                :key="plan.id"
                type="button"
                class="export-scheme"
                :class="{
                  active: exportForm.scheme === 'package' && exportForm.planKey === plan.pkg.id
                }"
                @click="onPickScheme('package', plan.pkg.id)"
              >
                <span class="export-scheme-name"
                  >方案{{ plan.planNo }} · 套餐「{{ plan.pkg.name }}」</span
                >
                <span class="export-scheme-sub">{{ schemeSummary(plan) }}</span>
                <span class="export-scheme-amount">套餐价 {{ formatMoney(plan.total) }}</span>
              </button>
            </div>
            <p v-else class="export-hint">
              {{
                quote.hasPackage
                  ? '当前箱数未达套餐起购量，本单按方案1（单独采购）导出。'
                  : '当前组合暂无套餐方案，本单按方案1（单独采购）导出。'
              }}
            </p>
          </div>
        </template>

        <template v-else-if="quote.purchaseMode === 'package'">
          <div class="export-section">
            <h4 class="export-section-title">结算方案</h4>
            <div class="export-schemes">
              <button
                type="button"
                class="export-scheme"
                :class="{ active: exportForm.scheme === 'package' }"
                :disabled="!directPackageValid"
                @click="exportForm.scheme = 'package'"
              >
                <span class="export-scheme-name"
                  >套餐整购 · 「{{ directPackage?.name || '未选择套餐' }}」</span
                >
                <span class="export-scheme-sub">{{
                  directPackage
                    ? `${quote.packageSets} 套 × ${moneyText(directPackage.price)}`
                    : '请先选择固定整购套餐'
                }}</span>
                <span class="export-scheme-amount"
                  >合计 {{ moneyText(quote.packageModeTotal) }} 元</span
                >
              </button>
            </div>
          </div>
        </template>

        <!-- 产品明细与快捷调价议价工具 -->
        <div class="export-section">
          <h4 class="export-section-title">产品明细与结算金额</h4>
          <template
            v-if="
              quote.purchaseMode === 'package' &&
              exportForm.scheme === 'package' &&
              directPackageValid
            "
          >
            <div class="export-items readonly">
              <div
                v-for="item in directPackageRows"
                :key="item.productId ?? item.id"
                class="export-item"
              >
                <div class="export-item-head">
                  <strong>{{ item.name }}</strong>
                  <span class="export-item-meta"
                    >每套 {{ item.quantity ?? 1 }} {{ item.unit }} · 本单
                    {{ (Number(item.quantity) || 1) * quote.packageSets }} {{ item.unit }}</span
                  >
                </div>
                <span class="export-item-amount">套餐内</span>
              </div>
            </div>
            <div class="export-totals">
              <div class="export-total-row">
                <span>{{ quote.packageSets }} 套 × {{ moneyText(directPackage.price) }}</span>
                <strong>{{ moneyText(quote.packageModeTotal) }} 元</strong>
              </div>
            </div>
            <p class="export-tip">报价单按套餐总价结算，金额列不逐项拆分。</p>
          </template>

          <template v-else-if="exportForm.scheme === 'package' && chosenPackagePlan">
            <div class="export-items">
              <div class="export-item">
                <div class="export-item-head">
                  <strong>{{ catalog.selectedDevice?.name || '治疗设备' }}</strong>
                  <span class="export-item-meta">数量 {{ quote.devices }} 台 · 套餐内设备</span>
                </div>
                <label class="export-amount-field">
                  <span>单价（元/台）</span>
                  <input
                    v-model.number="exportForm.deviceUnit"
                    class="input"
                    type="number"
                    min="0"
                    step="0.01"
                  />
                </label>
              </div>
              <div class="export-item">
                <div class="export-item-head">
                  <strong>{{ catalog.selectedConsumable?.name || '医用耗材' }}</strong>
                  <span class="export-item-meta"
                    >数量 {{ quote.boxes }} 箱（每箱 {{ catalog.bagsPerBox }}
                    {{ catalog.selectedConsumable?.unit || '袋' }}）</span
                  >
                </div>
                <label class="export-amount-field">
                  <span>单价（元/{{ catalog.selectedConsumable?.unit || '袋' }}）</span>
                  <input
                    v-model.number="exportForm.consumableUnit"
                    class="input"
                    type="number"
                    min="0"
                    step="0.01"
                  />
                </label>
              </div>
            </div>

            <div class="export-totals">
              <div class="export-total-row">
                <span>标准价合计</span>
                <strong>{{ moneyText(exportStandardTotal) }} 元</strong>
              </div>
              <div class="export-total-row">
                <span>套餐实收合计</span>
                <label class="export-inline-input">
                  <input
                    v-model.number="exportForm.paidTotal"
                    class="input"
                    type="number"
                    min="0"
                    step="0.01"
                  />
                  <em>元</em>
                </label>
              </div>
              <div class="export-total-row">
                <span>优惠金额</span>
                <label class="export-inline-input">
                  <input
                    :value="exportDiscount"
                    class="input"
                    type="number"
                    min="0"
                    step="0.01"
                    @input="onDiscountInput"
                  />
                  <em>元</em>
                </label>
              </div>
            </div>

            <!-- 快捷抹零与折扣议价小工具 -->
            <div class="discount-quick-tools">
              <span class="quick-label">快捷议价抹零：</span>
              <div class="quick-btns">
                <button class="btn btn-sm btn-light" type="button" @click="applyDiscountPreset('round100')">整百抹零</button>
                <button class="btn btn-sm btn-light" type="button" @click="applyDiscountPreset('round1000')">整千抹零</button>
                <button class="btn btn-sm btn-light" type="button" @click="applyDiscountPreset('p98')">98折</button>
                <button class="btn btn-sm btn-light" type="button" @click="applyDiscountPreset('p95')">95折</button>
                <button class="btn btn-sm btn-light" type="button" @click="applyDiscountPreset('reset')">恢复标准价</button>
              </div>
            </div>

            <p class="export-tip">
              实收与优惠可任改一项、另一项自动联动；报价单金额列统一按套餐实收价结算。
            </p>
          </template>

          <template v-else>
            <div class="export-items readonly">
              <div v-if="quote.purchaseMode !== 'consumables'" class="export-item">
                <div class="export-item-head">
                  <strong>{{ catalog.selectedDevice?.name || '治疗设备' }}</strong>
                  <span class="export-item-meta"
                    >{{ quote.devices }} 台 × {{ moneyText(catalog.devicePrice) }} 元/台</span
                  >
                </div>
                <span class="export-item-amount">{{ moneyText(quote.plan1DeviceCost) }} 元</span>
              </div>
              <div v-if="quote.purchaseMode !== 'equipment'" class="export-item">
                <div class="export-item-head">
                  <strong>{{ catalog.selectedConsumable?.name || '医用耗材' }}</strong>
                  <span class="export-item-meta"
                    >{{ quote.boxes }} 箱 × {{ moneyText(quote.plan1UnitPrice) }} 元/{{
                      catalog.selectedConsumable?.unit || '袋'
                    }}（每箱 {{ catalog.bagsPerBox }}
                    {{ catalog.selectedConsumable?.unit || '袋' }}）</span
                  >
                </div>
                <span class="export-item-amount"
                  >{{ moneyText(quote.plan1ConsumablesCost) }} 元</span
                >
              </div>
            </div>
            <div class="export-totals">
              <div class="export-total-row">
                <span>合计金额</span>
                <strong>{{ moneyText(exportPaidTotal) }} 元</strong>
              </div>
            </div>
          </template>
        </div>
      </div>

      <footer class="export-modal-foot">
        <button type="button" class="btn" @click="close">取消</button>
        <button type="button" class="btn btn-primary" @click="handleGenerate">
          <Download :size="16" />
          生成并打印报价单
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.export-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  padding: 20px;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
  overflow-y: auto;
}

.export-modal {
  display: flex;
  flex-direction: column;
  width: min(720px, 100%);
  max-height: calc(100vh - 40px);
  margin: auto;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 28px 70px -24px rgba(13, 71, 161, 0.55);
  overflow: hidden;
}

.export-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #fbfdff, #fff);
}

.export-modal-title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  color: var(--primary-dark);
}

.export-modal-close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: #fff;
  color: var(--muted);
  font-size: 14px;
  cursor: pointer;
}
.export-modal-close:hover {
  color: var(--text);
  background: var(--bg-alt);
}

.export-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  overflow-y: auto;
}

.export-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.export-section-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.export-section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 800;
  color: var(--text);
}

.export-section-tag {
  font-size: 11px;
  color: var(--muted);
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

.export-grid-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.export-grid {
  display: grid;
  gap: 10px;
}
.export-grid-2 {
  grid-template-columns: 1fr 1fr;
}

.export-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.export-field span {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}
.export-field input {
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}
.export-field input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(30, 136, 229, 0.12);
}

.export-schemes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
}

.export-scheme {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
}
.export-scheme:hover {
  border-color: var(--accent);
}
.export-scheme.active {
  background: var(--primary-light);
  border-color: var(--primary);
  box-shadow: 0 4px 12px rgba(30, 136, 229, 0.15);
}

.export-scheme-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}
.export-scheme-sub {
  font-size: 11px;
  color: var(--muted);
}
.export-scheme-amount {
  font-size: 13px;
  font-weight: 800;
  color: var(--primary-dark);
  margin-top: 4px;
}

.export-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #f8fafc;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
}

.export-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}
.export-item:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.export-item-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.export-item-head strong {
  font-size: 13px;
  color: var(--text);
}
.export-item-meta {
  font-size: 11px;
  color: var(--muted);
}
.export-amount-field {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.export-amount-field span {
  font-size: 10px;
  color: var(--muted);
}
.export-amount-field input {
  width: 100px;
  height: 30px;
  padding: 0 8px;
  text-align: right;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
}

.export-totals {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid var(--border);
}

.export-total-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
.export-inline-input {
  display: flex;
  align-items: center;
  gap: 4px;
}
.export-inline-input input {
  width: 110px;
  height: 30px;
  padding: 0 8px;
  text-align: right;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-weight: 700;
}

.discount-quick-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f7ff;
  border-radius: 8px;
  font-size: 12px;
}
.quick-label {
  color: var(--primary-dark);
  font-weight: 700;
  white-space: nowrap;
}
.quick-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.quick-btns .btn {
  min-height: 28px;
  padding: 0 10px;
  font-size: 12px;
  background: #fff;
  border: 1px solid rgba(30, 136, 229, 0.25);
}

.export-tip {
  margin: 0;
  font-size: 11px;
  color: var(--muted);
  line-height: 1.5;
}

.export-modal-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: #f8fafc;
}
</style>
