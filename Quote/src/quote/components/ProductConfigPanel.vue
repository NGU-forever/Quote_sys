<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  AlertTriangle,
  Boxes,
  Gift,
  Maximize2,
  Minus,
  Plus,
  Stethoscope,
  X,
  Zap,
  Sparkles,
  Layers
} from 'lucide-vue-next'
import { useCatalogStore } from '../../shared/stores/catalog'
import { useQuoteStore } from '../stores/quote'
import { formatMoney } from '../../shared/utils/format'
import { PRICING } from '../../shared/data/pricing'
import { resolveImage } from '../../shared/utils/imageSync'

const quote = useQuoteStore()
const catalog = useCatalogStore()

// 实物大图灯箱预览状态
const previewModal = ref({
  visible: false,
  title: '',
  subtitle: '',
  src: ''
})

function openImageModal(src, title, subtitle = '') {
  if (!src) return
  previewModal.value = {
    visible: true,
    title: title || '产品实物图',
    subtitle,
    src
  }
}

function closeImageModal() {
  previewModal.value.visible = false
}

function onKeydown(e) {
  if (e.key === 'Escape' && previewModal.value.visible) {
    closeImageModal()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

const consumableOptions = computed(() => {
  const applicable = catalog.applicableConsumables
  const current = catalog.selectedConsumableId
  if (current && !applicable.some((c) => c.id === current)) {
    return [...applicable, catalog.selectedConsumable].filter(Boolean)
  }
  return applicable
})

function onDeviceChange(event) {
  catalog.selectDevice(event.target.value === '' ? null : Number(event.target.value))
  syncMode()
}

function onConsumableChange(event) {
  catalog.selectConsumable(event.target.value === '' ? null : Number(event.target.value))
  syncMode()
}

function syncMode() {
  const hasDevice = Boolean(catalog.selectedDevice)
  const hasConsumable = Boolean(catalog.selectedConsumable)
  if (hasDevice && hasConsumable) {
    quote.setPurchaseMode('both')
  } else if (hasDevice) {
    quote.setPurchaseMode('equipment')
  } else if (hasConsumable) {
    quote.setPurchaseMode('consumables')
  }
}

function pricePrecision(value) {
  return Number(value) % 1 ? 2 : 0
}

const deviceBelowMin = computed(() => {
  const min = Number(catalog.selectedDevice?.minPrice)
  const price = catalog.devicePrice
  return min > 0 && price > 0 && price < min
})

const consumableBelowMin = computed(() => {
  const min = Number(catalog.selectedConsumable?.minPrice)
  const price = catalog.priceOf(catalog.selectedConsumableId)
  return min > 0 && price > 0 && price < min
})

function onDevicePriceInput(event) {
  if (catalog.selectedDeviceId !== null && catalog.selectedDeviceId !== undefined) {
    catalog.setPrice(catalog.selectedDeviceId, event.target.value)
  }
}

function onConsumablePriceInput(event) {
  if (catalog.selectedConsumableId !== null && catalog.selectedConsumableId !== undefined) {
    catalog.setPrice(catalog.selectedConsumableId, event.target.value)
  }
}

const boxes = computed({
  get: () => quote.boxes,
  set: (value) => quote.setBoxes(value)
})

const devices = computed({
  get: () => quote.devices,
  set: (value) => quote.setDevices(value)
})

const directPackage = computed(() => quote.activePackage)
const directPackageSets = computed({
  get: () => quote.packageSets,
  set: (value) => quote.setPackageSets(value)
})
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

function onPackageChange(event) {
  quote.selectPackage(event.target.value)
}

const consumableTiers = computed(() => {
  const tiers = catalog.plan1Tiers?.length ? catalog.plan1Tiers : PRICING.plan1Tiers
  return [...tiers].sort((a, b) => a.minBoxes - b.minBoxes)
})

const currentTierIndex = computed(() => {
  const b = quote.boxes
  let matched = 0
  consumableTiers.value.forEach((tier, idx) => {
    if (b >= tier.minBoxes) matched = idx
  })
  return matched
})

const nextTier = computed(() => {
  const b = quote.boxes
  return consumableTiers.value.find((t) => t.minBoxes > b) || null
})

const nextTierDiff = computed(() => {
  return nextTier.value ? nextTier.value.minBoxes - quote.boxes : 0
})
</script>

<template>
  <div class="product-config-panel">
    <!-- 1. 同时购买模式（设备 + 耗材） -->
    <template v-if="quote.purchaseMode === 'both'">
      <!-- 设备卡片 -->
      <div class="product-config-card" :class="{ empty: !catalog.selectedDevice }">
        <div class="card-head">
          <div class="card-head-picker">
            <span class="config-tag tone-blue">硬件 / 主设备</span>
            <select
              class="card-select"
              :value="catalog.selectedDeviceId ?? ''"
              @change="onDeviceChange"
            >
              <option value="">请选择硬件 / 主设备</option>
              <option v-for="device in catalog.deviceList" :key="device.id" :value="device.id">
                {{ device.name }}
              </option>
            </select>
          </div>
        </div>
        <div v-if="catalog.selectedDevice" class="card-body">
          <!-- 设备实物大图视觉展台 -->
          <div class="product-hero-showcase tone-blue">
            <div
              class="hero-stage"
              :class="{ clickable: Boolean(catalog.selectedDevice.image) }"
              @click="catalog.selectedDevice.image && openImageModal(resolveImage(catalog.selectedDevice.image), catalog.selectedDevice.name, catalog.selectedDevice.spec)"
            >
              <div class="stage-badges">
                <span class="badge-tag">硬件 / 设备</span>
                <span v-if="catalog.selectedDevice.sku" class="badge-sku">{{ catalog.selectedDevice.sku }}</span>
              </div>
              <template v-if="catalog.selectedDevice?.image">
                <img
                  :src="resolveImage(catalog.selectedDevice.image)"
                  :alt="catalog.selectedDevice.name"
                  class="hero-img"
                />
                <button
                  type="button"
                  class="stage-zoom-btn"
                  title="点击查看实物大图细节"
                  @click.stop="openImageModal(resolveImage(catalog.selectedDevice.image), catalog.selectedDevice.name, catalog.selectedDevice.spec)"
                >
                  <Maximize2 :size="13" />
                  <span>查看大图</span>
                </button>
              </template>
              <div v-else class="stage-placeholder">
                <div class="placeholder-circle">
                  <Stethoscope :size="38" class="placeholder-icon" />
                </div>
                <span class="placeholder-title">实物照片待上传</span>
                <span class="placeholder-hint">支持展示高清硬件、探头与机身细节</span>
              </div>
            </div>

            <div class="hero-meta">
              <div class="meta-title-row">
                <strong class="hero-name">{{ catalog.selectedDevice.name }}</strong>
                <span class="hero-unit-tag">单位: {{ catalog.selectedDevice.unit || '台' }}</span>
              </div>
              <div class="meta-tags-row">
                <span class="spec-pill">{{ catalog.selectedDevice.spec || '标准硬件规格' }}</span>
                <span v-if="catalog.selectedDevice.power" class="spec-pill subtle">{{ catalog.selectedDevice.power }}</span>
              </div>
            </div>
          </div>

          <div class="config-rows">
            <div class="config-row">
              <label class="row-label">成交单价</label>
              <div class="price-input-row" :class="{ 'has-warning': deviceBelowMin }">
                <span class="currency-symbol">¥</span>
                <input
                  class="clean-price-input"
                  :value="catalog.devicePrice"
                  type="number"
                  min="0"
                  step="1"
                  @input="onDevicePriceInput"
                />
                <span class="price-unit">/{{ catalog.selectedDevice.unit || '台' }}</span>
              </div>
            </div>
            <div class="config-row">
              <label class="row-label">采购数量</label>
              <div class="stepper">
                <button
                  aria-label="减少设备"
                  type="button"
                  :disabled="devices <= 0"
                  @click="quote.changeDevices(-1)"
                >
                  <Minus :size="16" />
                </button>
                <input v-model.number="devices" type="number" min="0" max="50" />
                <button
                  aria-label="增加设备"
                  type="button"
                  :disabled="devices >= 50"
                  @click="quote.changeDevices(1)"
                >
                  <Plus :size="16" />
                </button>
              </div>
            </div>
          </div>
          <div class="card-footer-notice">
            <span class="limit-text" :class="{ 'warning-text': deviceBelowMin }">
              最低限价: ¥{{ formatMoney(catalog.selectedDevice?.minPrice, pricePrecision(catalog.selectedDevice?.minPrice)) }}
            </span>
            <span v-if="deviceBelowMin" class="price-warning">
              <AlertTriangle :size="12" />
              <span>低于最低限价</span>
            </span>
          </div>
        </div>
        <div v-else class="card-empty-placeholder">
          <Stethoscope :size="32" class="placeholder-icon" />
          <span>请在上方下拉菜单中选择适用的硬件设备</span>
        </div>
      </div>

      <!-- 耗材卡片 -->
      <div class="product-config-card" :class="{ empty: !catalog.selectedConsumable }">
        <div class="card-head">
          <div class="card-head-picker">
            <span class="config-tag tone-teal">耗材 / 消耗品</span>
            <select
              class="card-select"
              :value="catalog.selectedConsumableId ?? ''"
              @change="onConsumableChange"
            >
              <option value="">请选择耗材 / 配套商品</option>
              <option v-for="consumable in consumableOptions" :key="consumable.id" :value="consumable.id">
                {{ consumable.name }}
              </option>
            </select>
          </div>
        </div>
        <div v-if="catalog.selectedConsumable" class="card-body">
          <!-- 耗材实物大图视觉展台 -->
          <div class="product-hero-showcase tone-teal">
            <div
              class="hero-stage"
              :class="{ clickable: Boolean(catalog.selectedConsumable.image) }"
              @click="catalog.selectedConsumable.image && openImageModal(resolveImage(catalog.selectedConsumable.image), catalog.selectedConsumable.name, catalog.selectedConsumable.spec)"
            >
              <div class="stage-badges">
                <span class="badge-tag">耗材 / 消耗品</span>
                <span v-if="catalog.selectedConsumable.sku" class="badge-sku">{{ catalog.selectedConsumable.sku }}</span>
              </div>
              <template v-if="catalog.selectedConsumable?.image">
                <img
                  :src="resolveImage(catalog.selectedConsumable.image)"
                  :alt="catalog.selectedConsumable.name"
                  class="hero-img"
                />
                <button
                  type="button"
                  class="stage-zoom-btn"
                  title="点击查看实物大图细节"
                  @click.stop="openImageModal(resolveImage(catalog.selectedConsumable.image), catalog.selectedConsumable.name, catalog.selectedConsumable.spec)"
                >
                  <Maximize2 :size="13" />
                  <span>查看大图</span>
                </button>
              </template>
              <div v-else class="stage-placeholder">
                <div class="placeholder-circle">
                  <Boxes :size="38" class="placeholder-icon" />
                </div>
                <span class="placeholder-title">实物照片待上传</span>
                <span class="placeholder-hint">支持展示外箱包装与单件实物实拍</span>
              </div>
            </div>

            <div class="hero-meta">
              <div class="meta-title-row">
                <strong class="hero-name">{{ catalog.selectedConsumable.name }}</strong>
                <span class="hero-unit-tag">每箱 {{ catalog.bagsPerBox }} {{ catalog.selectedConsumable.unit || '袋' }}</span>
              </div>
              <div class="meta-tags-row">
                <span class="spec-pill">{{ catalog.selectedConsumable.spec || '标准耗材规格' }}</span>
                <span v-if="catalog.selectedConsumable.piecesPerBag" class="spec-pill subtle">
                  每袋 {{ catalog.selectedConsumable.piecesPerBag }} 片
                </span>
              </div>
            </div>
          </div>

          <div class="config-rows">
            <div class="config-row">
              <label class="row-label">成交单价</label>
              <div class="price-input-row" :class="{ 'has-warning': consumableBelowMin }">
                <span class="currency-symbol">¥</span>
                <input
                  class="clean-price-input"
                  :value="catalog.priceOf(catalog.selectedConsumableId)"
                  type="number"
                  min="0"
                  step="0.1"
                  @input="onConsumablePriceInput"
                />
                <span class="price-unit">/{{ catalog.selectedConsumable.unit || '袋' }}</span>
              </div>
            </div>
            <div class="config-row">
              <label class="row-label">采购箱数</label>
              <div class="stepper">
                <button
                  aria-label="减少箱数"
                  type="button"
                  :disabled="boxes <= 1"
                  @click="quote.changeBoxes(-1)"
                >
                  <Minus :size="16" />
                </button>
                <input v-model.number="boxes" type="number" min="1" max="500" />
                <button
                  aria-label="增加箱数"
                  type="button"
                  :disabled="boxes >= 500"
                  @click="quote.changeBoxes(1)"
                >
                  <Plus :size="16" />
                </button>
              </div>
            </div>
          </div>
          <div class="card-footer-notice">
            <span class="limit-text" :class="{ 'warning-text': consumableBelowMin }">
              最低限价: ¥{{ formatMoney(catalog.selectedConsumable?.minPrice, pricePrecision(catalog.selectedConsumable?.minPrice)) }}
              (每箱 {{ catalog.bagsPerBox }} {{ catalog.selectedConsumable.unit || '袋' }})
            </span>
            <span v-if="consumableBelowMin" class="price-warning">
              <AlertTriangle :size="12" />
              <span>低于最低限价</span>
            </span>
          </div>
        </div>
        <div v-else class="card-empty-placeholder">
          <Boxes :size="32" class="placeholder-icon" />
          <span>请在上方下拉菜单中选择适用的耗材 / 消耗品</span>
        </div>
      </div>
    </template>

    <!-- 2. 仅购耗材模式 -->
    <template v-else-if="quote.purchaseMode === 'consumables'">
      <div class="product-config-card" :class="{ empty: !catalog.selectedConsumable }">
        <div class="card-head">
          <div class="card-head-picker">
            <span class="config-tag tone-teal">采购耗材 / 消耗品</span>
            <select
              class="card-select"
              :value="catalog.selectedConsumableId ?? ''"
              @change="onConsumableChange"
            >
              <option value="" disabled>请选择耗材 / 消耗品</option>
              <option v-for="consumable in catalog.consumableList" :key="consumable.id" :value="consumable.id">
                {{ consumable.name }}
              </option>
            </select>
          </div>
        </div>
        <div v-if="catalog.selectedConsumable" class="card-body">
          <!-- 耗材大图展台 -->
          <div class="product-hero-showcase tone-teal">
            <div
              class="hero-stage"
              :class="{ clickable: Boolean(catalog.selectedConsumable.image) }"
              @click="catalog.selectedConsumable.image && openImageModal(resolveImage(catalog.selectedConsumable.image), catalog.selectedConsumable.name, catalog.selectedConsumable.spec)"
            >
              <div class="stage-badges">
                <span class="badge-tag">耗材 / 消耗品</span>
                <span v-if="catalog.selectedConsumable.sku" class="badge-sku">{{ catalog.selectedConsumable.sku }}</span>
              </div>
              <template v-if="catalog.selectedConsumable?.image">
                <img
                  :src="resolveImage(catalog.selectedConsumable.image)"
                  :alt="catalog.selectedConsumable.name"
                  class="hero-img"
                />
                <button
                  type="button"
                  class="stage-zoom-btn"
                  title="点击查看实物大图细节"
                  @click.stop="openImageModal(resolveImage(catalog.selectedConsumable.image), catalog.selectedConsumable.name, catalog.selectedConsumable.spec)"
                >
                  <Maximize2 :size="13" />
                  <span>查看大图</span>
                </button>
              </template>
              <div v-else class="stage-placeholder">
                <div class="placeholder-circle">
                  <Boxes :size="38" class="placeholder-icon" />
                </div>
                <span class="placeholder-title">实物照片待上传</span>
                <span class="placeholder-hint">支持展示外箱包装与单件实物实拍</span>
              </div>
            </div>

            <div class="hero-meta">
              <div class="meta-title-row">
                <strong class="hero-name">{{ catalog.selectedConsumable.name }}</strong>
                <span class="hero-unit-tag">每箱 {{ catalog.bagsPerBox }} {{ catalog.selectedConsumable.unit }}</span>
              </div>
              <div class="meta-tags-row">
                <span class="spec-pill">{{ catalog.selectedConsumable.spec || '标准耗材规格' }}</span>
                <span v-if="catalog.selectedConsumable.piecesPerBag" class="spec-pill subtle">
                  每袋 {{ catalog.selectedConsumable.piecesPerBag }} 片
                </span>
              </div>
            </div>
          </div>

          <div class="config-rows">
            <div class="config-row">
              <label class="row-label">阶梯单价</label>
              <div class="price-input-row" :class="{ 'has-warning': consumableBelowMin }">
                <span class="currency-symbol">¥</span>
                <input
                  class="clean-price-input"
                  :value="catalog.priceOf(catalog.selectedConsumableId)"
                  type="number"
                  min="0"
                  step="0.1"
                  @input="onConsumablePriceInput"
                />
                <span class="price-unit">/{{ catalog.selectedConsumable.unit }}</span>
              </div>
            </div>
            <div class="config-row">
              <label class="row-label">采购箱数</label>
              <div class="stepper">
                <button
                  aria-label="减少箱数"
                  type="button"
                  :disabled="boxes <= 1"
                  @click="quote.changeBoxes(-1)"
                >
                  <Minus :size="16" />
                </button>
                <input v-model.number="boxes" type="number" min="1" max="500" />
                <button
                  aria-label="增加箱数"
                  type="button"
                  :disabled="boxes >= 500"
                  @click="quote.changeBoxes(1)"
                >
                  <Plus :size="16" />
                </button>
              </div>
            </div>
          </div>
          <div class="card-footer-notice">
            <span class="limit-text" :class="{ 'warning-text': consumableBelowMin }">
              最低限价: ¥{{ formatMoney(catalog.selectedConsumable?.minPrice, pricePrecision(catalog.selectedConsumable?.minPrice)) }}
              (每箱 {{ catalog.bagsPerBox }} {{ catalog.selectedConsumable.unit || '袋' }})
            </span>
            <span v-if="consumableBelowMin" class="price-warning">
              <AlertTriangle :size="12" />
              <span>低于最低限价</span>
            </span>
          </div>

          <!-- 阶梯价规则指示条与销售增购杠杆 -->
          <div class="tier-progress-card">
            <div class="tier-progress-title">
              <Zap :size="14" class="tier-icon" />
              <span>箱数阶梯优惠规则</span>
            </div>
            <div class="tier-steps">
              <div
                v-for="(t, idx) in consumableTiers"
                :key="idx"
                class="tier-step"
                :class="{ active: currentTierIndex === idx }"
              >
                <span class="tier-step-label">{{ t.label || `${t.minBoxes}箱起` }}</span>
                <strong class="tier-step-price">¥{{ t.price }}/{{ catalog.selectedConsumable.unit }}</strong>
              </div>
            </div>
            <div v-if="nextTier" class="tier-upsell-bar">
              <span class="upsell-text">
                再订购 <strong>{{ nextTierDiff }}</strong> 箱即可享受下一档优惠单价 <strong>¥{{ nextTier.price }}</strong>/{{ catalog.selectedConsumable.unit }}
              </span>
              <button
                class="btn btn-sm btn-soft tier-upsell-btn"
                type="button"
                @click="quote.setBoxes(nextTier.minBoxes)"
              >
                +{{ nextTierDiff }}箱一键享优惠
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 3. 仅购设备模式 -->
    <template v-else-if="quote.purchaseMode === 'equipment'">
      <div class="product-config-card" :class="{ empty: !catalog.selectedDevice }">
        <div class="card-head">
          <div class="card-head-picker">
            <span class="config-tag tone-blue">采购硬件 / 设备</span>
            <select
              class="card-select"
              :value="catalog.selectedDeviceId ?? ''"
              @change="onDeviceChange"
            >
              <option value="" disabled>请选择硬件 / 设备</option>
              <option v-for="device in catalog.deviceList" :key="device.id" :value="device.id">
                {{ device.name }}
              </option>
            </select>
          </div>
        </div>
        <div v-if="catalog.selectedDevice" class="card-body">
          <!-- 设备大图展台 -->
          <div class="product-hero-showcase tone-blue">
            <div
              class="hero-stage"
              :class="{ clickable: Boolean(catalog.selectedDevice.image) }"
              @click="catalog.selectedDevice.image && openImageModal(resolveImage(catalog.selectedDevice.image), catalog.selectedDevice.name, catalog.selectedDevice.spec)"
            >
              <div class="stage-badges">
                <span class="badge-tag">硬件 / 设备</span>
                <span v-if="catalog.selectedDevice.sku" class="badge-sku">{{ catalog.selectedDevice.sku }}</span>
              </div>
              <template v-if="catalog.selectedDevice?.image">
                <img
                  :src="resolveImage(catalog.selectedDevice.image)"
                  :alt="catalog.selectedDevice.name"
                  class="hero-img"
                />
                <button
                  type="button"
                  class="stage-zoom-btn"
                  title="点击查看实物大图细节"
                  @click.stop="openImageModal(resolveImage(catalog.selectedDevice.image), catalog.selectedDevice.name, catalog.selectedDevice.spec)"
                >
                  <Maximize2 :size="13" />
                  <span>查看大图</span>
                </button>
              </template>
              <div v-else class="stage-placeholder">
                <div class="placeholder-circle">
                  <Stethoscope :size="38" class="placeholder-icon" />
                </div>
                <span class="placeholder-title">实物照片待上传</span>
                <span class="placeholder-hint">支持展示高清硬件、探头与机身细节</span>
              </div>
            </div>

            <div class="hero-meta">
              <div class="meta-title-row">
                <strong class="hero-name">{{ catalog.selectedDevice.name }}</strong>
                <span class="hero-unit-tag">单位: {{ catalog.selectedDevice.unit || '台' }}</span>
              </div>
              <div class="meta-tags-row">
                <span class="spec-pill">{{ catalog.selectedDevice.spec || '标准硬件规格' }}</span>
                <span v-if="catalog.selectedDevice.power" class="spec-pill subtle">{{ catalog.selectedDevice.power }}</span>
              </div>
            </div>
          </div>

          <div class="config-rows">
            <div class="config-row">
              <label class="row-label">成交单价</label>
              <div class="price-input-row" :class="{ 'has-warning': deviceBelowMin }">
                <span class="currency-symbol">¥</span>
                <input
                  class="clean-price-input"
                  :value="catalog.devicePrice"
                  type="number"
                  min="0"
                  step="1"
                  @input="onDevicePriceInput"
                />
                <span class="price-unit">/{{ catalog.selectedDevice.unit }}</span>
              </div>
            </div>
            <div class="config-row">
              <label class="row-label">采购数量</label>
              <div class="stepper">
                <button
                  aria-label="减少设备"
                  type="button"
                  :disabled="devices <= 1"
                  @click="quote.changeDevices(-1)"
                >
                  <Minus :size="16" />
                </button>
                <input v-model.number="devices" type="number" min="1" max="50" />
                <button
                  aria-label="增加设备"
                  type="button"
                  :disabled="devices >= 50"
                  @click="quote.changeDevices(1)"
                >
                  <Plus :size="16" />
                </button>
              </div>
            </div>
          </div>
          <div class="card-footer-notice">
            <span class="limit-text" :class="{ 'warning-text': deviceBelowMin }">
              最低限价: {{ formatMoney(catalog.selectedDevice?.minPrice, pricePrecision(catalog.selectedDevice?.minPrice)) }}
            </span>
            <span v-if="deviceBelowMin" class="price-warning">
              <AlertTriangle :size="12" />
              <span>低于最低限价</span>
            </span>
          </div>
          <div class="bundle-switch-tip">
            <Gift :size="16" class="tip-icon" />
            <div class="tip-text">
              搭配耗材或配件采购可享<strong>特惠套餐方案</strong>与更多优惠折让
            </div>
            <button
              class="btn btn-sm btn-soft"
              type="button"
              @click="quote.setPurchaseMode('both')"
            >
              去搭配耗材/配件
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 4. 套餐整购模式 -->
    <template v-else-if="quote.purchaseMode === 'package'">
      <div class="product-config-card">
        <div class="card-head">
          <span class="config-tag tone-purple">整购套餐</span>
          <span class="card-title-text">Workbench 配置整套清单</span>
        </div>
        <div class="card-body">
          <div class="config-field-block">
            <label>选择整购套餐</label>
            <select
              class="card-select full-width-select"
              :value="quote.activePackage?.id ?? ''"
              @change="onPackageChange"
            >
              <option value="" disabled>选择 Workbench 固定整购套餐</option>
              <option v-for="pkg in quote.packageOptions" :key="pkg.id" :value="pkg.id">
                {{ pkg.name }} · {{ formatMoney(pkg.price) }}/套
              </option>
            </select>
          </div>
          <div class="config-rows" style="margin-top: 14px;">
            <div class="config-row">
              <label class="row-label">单套固定价</label>
              <div class="price-display-box">
                <strong>¥{{ formatMoney(directPackage?.price || 0) }}</strong>
                <span class="price-unit">/套</span>
              </div>
            </div>
            <div class="config-row">
              <label class="row-label">购买套数</label>
              <div class="stepper">
                <button
                  aria-label="减少套餐套数"
                  type="button"
                  :disabled="directPackageSets <= 1"
                  @click="quote.changePackageSets(-1)"
                >
                  <Minus :size="16" />
                </button>
                <input v-model.number="directPackageSets" type="number" min="1" max="1000" />
                <button
                  aria-label="增加套餐套数"
                  type="button"
                  :disabled="directPackageSets >= 1000"
                  @click="quote.changePackageSets(1)"
                >
                  <Plus :size="16" />
                </button>
              </div>
            </div>
          </div>

          <!-- SKU 组成明细卡片列表 -->
          <div v-if="directPackageRows.length > 0" class="package-skus-container">
            <div class="sku-title-row">
              <span class="sku-title">每套包含 SKU 构成清单：</span>
              <span class="sku-count-hint">共 {{ directPackageRows.length }} 种标配产品</span>
            </div>
            <div class="package-sku-grid">
              <div
                v-for="item in directPackageRows"
                :key="item.productId ?? item.id"
                class="package-sku-item"
              >
                <div
                  class="sku-item-thumb"
                  :title="catalog.productById(item.productId ?? item.id)?.image ? '点击放大查看实物大图' : ''"
                  @click="catalog.productById(item.productId ?? item.id)?.image && openImageModal(resolveImage(catalog.productById(item.productId ?? item.id).image), item.name, item.spec)"
                >
                  <img
                    v-if="catalog.productById(item.productId ?? item.id)?.image"
                    :src="resolveImage(catalog.productById(item.productId ?? item.id).image)"
                    :alt="item.name"
                    class="sku-thumb-img"
                  />
                  <component
                    :is="item.category === 'device' ? Stethoscope : Boxes"
                    v-else
                    :size="20"
                    class="sku-thumb-fallback"
                  />
                </div>
                <div class="sku-item-info">
                  <div class="sku-item-name" :title="item.name">{{ item.name }}</div>
                  <div class="sku-item-sub">
                    <span class="sku-item-spec">{{ item.spec || '标配产品' }}</span>
                    <strong class="sku-item-qty">× {{ item.quantity ?? 1 }}{{ item.unit }}</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 5. 配套配件与增值服务选配区（全品类支持） -->
    <div class="addons-section">
      <div class="addons-header">
        <div class="addons-title-group">
          <Sparkles :size="16" class="addons-icon" />
          <h4 class="addons-title">配套配件与增值服务选配区</h4>
          <span class="addons-badge">全品类支持</span>
        </div>
        <span class="addons-hint">支持硬件、耗材、关联配件及上门安装/维保培训等增值类目</span>
      </div>

      <div v-if="(catalog.serviceList && catalog.serviceList.length > 0) || (catalog.accessoryList && catalog.accessoryList.length > 0)" class="addons-grid">
        <div v-for="item in [...(catalog.accessoryList || []), ...(catalog.serviceList || [])]" :key="item.id" class="addon-card">
          <div class="addon-badge" :class="item.category">
            {{ item.category === 'service' ? '增值服务' : '配套配件' }}
          </div>
          <div class="addon-info">
            <strong class="addon-name">{{ item.name }}</strong>
            <span class="addon-spec">{{ item.spec || '标准规格' }}</span>
          </div>
          <div class="addon-pricing">
            <span class="addon-price">¥{{ formatMoney(item.price || item.minPrice) }}</span>
            <span class="addon-unit">/{{ item.unit || '项' }}</span>
          </div>
        </div>
      </div>
      <div v-else class="addons-empty">
        <Layers :size="18" class="addons-empty-icon" />
        <span>支持硬件、耗材、配件与培训等全品类商品。可在管理工作台添加并实时同步。</span>
      </div>
    </div>
  </div>

  <!-- 产品高清实物图放大预览灯箱弹窗 -->
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="previewModal.visible"
        class="image-lightbox-overlay"
        role="dialog"
        aria-modal="true"
        @click.self="closeImageModal"
      >
        <div class="image-lightbox-content">
          <div class="lightbox-header">
            <div class="lightbox-title-box">
              <h3 class="lightbox-title">{{ previewModal.title }}</h3>
              <span v-if="previewModal.subtitle" class="lightbox-subtitle">{{ previewModal.subtitle }}</span>
            </div>
            <button
              type="button"
              class="lightbox-close-btn"
              aria-label="关闭预览"
              @click="closeImageModal"
            >
              <X :size="20" />
            </button>
          </div>
          <div class="lightbox-body">
            <img :src="previewModal.src" :alt="previewModal.title" class="lightbox-image" />
          </div>
          <div class="lightbox-footer">
            <span>郑州克夫尼官方正品 · 高清实物展样</span>
            <span class="esc-hint">按 ESC 键或点击空白处退出</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>


<style scoped>
.product-config-panel {
  display: flex;
  flex-direction: column;
}

.product-config-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: var(--shadow-soft);
  overflow: hidden;
  margin-bottom: 18px;
  transition: border-color 0.2s ease;
}

.product-config-card.empty {
  background: rgba(255, 255, 255, 0.7);
  border-style: dashed;
}

.card-head {
  padding: 12px 16px;
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-head-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.config-tag {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}
.config-tag.tone-blue { background: var(--primary); }
.config-tag.tone-teal { background: var(--teal); }
.config-tag.tone-purple { background: #7c3aed; }

.card-select {
  flex: 1;
  min-width: 0;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s ease;
}

.card-select:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(30, 136, 229, 0.12);
}

.full-width-select {
  width: 100%;
}

.card-title-text {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.card-body {
  padding: 16px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (min-width: 1366px) {
  .card-body {
    padding: 18px 20px 20px;
    gap: 18px;
  }
}

/* ==========================================================================
   产品实物大图视觉展台 (Product Hero Showcase)
   ========================================================================== */
.product-hero-showcase {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 4px 14px -6px rgba(15, 23, 42, 0.08);
  transition: all 0.22s ease;
}

.product-hero-showcase.tone-blue:hover {
  border-color: rgba(30, 136, 229, 0.45);
  box-shadow: 0 8px 24px -8px rgba(30, 136, 229, 0.16);
}

.product-hero-showcase.tone-teal:hover {
  border-color: rgba(15, 118, 110, 0.45);
  box-shadow: 0 8px 24px -8px rgba(15, 118, 110, 0.16);
}

.hero-stage {
  position: relative;
  width: 100%;
  height: 190px;
  border-radius: 10px;
  overflow: hidden;
  background: radial-gradient(circle at 50% 45%, #ffffff 0%, #f3f6f9 100%);
  border: 1px solid rgba(226, 232, 240, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (min-width: 1366px) {
  .hero-stage {
    height: 215px;
  }
}

@media (min-width: 1536px) {
  .hero-stage {
    height: 235px;
  }
}

.hero-stage.clickable {
  cursor: zoom-in;
}

.hero-img {
  max-width: 90%;
  max-height: 88%;
  object-fit: contain;
  filter: drop-shadow(0 8px 18px rgba(15, 23, 42, 0.12));
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.3s ease;
}

.hero-stage:hover .hero-img {
  transform: scale(1.04);
  filter: drop-shadow(0 14px 26px rgba(15, 23, 42, 0.16));
}

.stage-badges {
  position: absolute;
  top: 10px;
  left: 10px;
  right: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  pointer-events: none;
  z-index: 2;
}

.badge-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  color: #fff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.tone-blue .badge-tag { background: var(--primary); }
.tone-teal .badge-tag { background: var(--teal); }

.badge-sku {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.stage-zoom-btn {
  position: absolute;
  bottom: 10px;
  right: 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.78);
  backdrop-filter: blur(6px);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  opacity: 0;
  transform: translateY(4px);
  transition: all 0.2s ease;
  z-index: 3;
}

.hero-stage:hover .stage-zoom-btn {
  opacity: 1;
  transform: translateY(0);
}

.stage-zoom-btn:hover {
  background: var(--primary);
  transform: translateY(-1px) scale(1.04);
}

.stage-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--muted);
  text-align: center;
  padding: 16px;
}

.placeholder-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #ffffff;
  border: 1.5px dashed var(--border);
  display: grid;
  place-items: center;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}

.tone-blue .placeholder-icon { color: var(--primary); opacity: 0.85; }
.tone-teal .placeholder-icon { color: var(--teal); opacity: 0.85; }

.placeholder-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.placeholder-hint {
  font-size: 11px;
  color: var(--muted);
}

.hero-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.hero-name {
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
  line-height: 1.35;
  margin: 0;
}

@media (min-width: 1366px) {
  .hero-name {
    font-size: 18px;
  }
}

.hero-unit-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  white-space: nowrap;
}

.meta-tags-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.spec-pill {
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  background: #f1f5f9;
  padding: 3px 8px;
  border-radius: 6px;
}

.spec-pill.subtle {
  color: var(--muted);
  background: transparent;
  border: 1px solid var(--border);
}

/* 占位空态 */
.card-empty-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 44px 16px;
  color: var(--muted);
  font-size: 13px;
}

.placeholder-icon {
  opacity: 0.45;
}

/* ==========================================================================
   价格与数量配置控件
   ========================================================================== */
.config-rows {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 12px;
}

@media (min-width: 1366px) {
  .config-rows {
    padding: 16px 18px;
    gap: 14px;
  }
}

.config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.row-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
}

.price-input-row {
  display: flex;
  align-items: center;
  height: 40px;
  width: 160px;
  padding: 0 10px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 9px;
  transition: all 0.18s ease;
}

@media (min-width: 1366px) {
  .price-input-row {
    height: 42px;
    width: 172px;
  }
}

.price-input-row:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(30, 136, 229, 0.12);
}

.price-input-row.has-warning {
  border-color: var(--red);
  background: var(--red-light);
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.15);
}

.clean-price-input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  outline: none;
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
  text-align: right;
  padding: 0 4px;
}

@media (min-width: 1366px) {
  .clean-price-input {
    font-size: 18px;
  }
}

.currency-symbol {
  font-size: 14px;
  font-weight: 700;
  color: var(--muted);
}

.price-input-row.has-warning .currency-symbol {
  color: var(--red);
}

.price-unit {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}

.stepper {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 160px;
  justify-content: flex-end;
}

@media (min-width: 1366px) {
  .stepper {
    width: 172px;
    gap: 8px;
  }
}

.stepper button {
  width: 40px;
  height: 40px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

@media (min-width: 1366px) {
  .stepper button {
    width: 42px;
    height: 42px;
  }
}

.stepper button:hover:not(:disabled) {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary-dark);
}

.stepper button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  pointer-events: none;
  background: var(--bg-alt);
}

.stepper input {
  width: 68px;
  height: 40px;
  text-align: center;
  border: 1px solid var(--border);
  border-radius: 9px;
  font-size: 15px;
  font-weight: 800;
  outline: none;
  background: #fff;
  flex: none;
}

@media (min-width: 1366px) {
  .stepper input {
    width: 74px;
    height: 42px;
    font-size: 16px;
  }
}

.stepper input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(30, 136, 229, 0.12);
}

.card-footer-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: var(--muted);
}

.price-warning {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--red);
  font-weight: 700;
  font-size: 11px;
  background: var(--red-light);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid rgba(220, 38, 38, 0.2);
}

.warning-text {
  color: var(--red);
}

/* ==========================================================================
   阶梯与优惠
   ========================================================================== */
.tier-progress-card {
  padding: 14px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tier-progress-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: #166534;
}
.tier-icon { color: #16a34a; }

.tier-steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.tier-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 6px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #dcfce7;
  font-size: 11px;
}

.tier-step.active {
  background: #16a34a;
  border-color: #16a34a;
  color: #fff;
  box-shadow: 0 4px 10px rgba(22, 163, 74, 0.25);
}

.tier-step-label {
  opacity: 0.85;
}

.tier-step.active .tier-step-price {
  color: #fff;
}
.tier-step-price {
  font-weight: 800;
  font-size: 13px;
  color: #166534;
}

.tier-upsell-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed #bbf7d0;
  font-size: 12px;
  color: #166534;
}

.tier-upsell-btn {
  background: #16a34a;
  color: #fff;
  border-radius: 6px;
  font-weight: 700;
  cursor: pointer;
}
.tier-upsell-btn:hover {
  background: #15803d;
}

.bundle-switch-tip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  font-size: 13px;
  color: #1e40af;
}
.tip-icon { color: #2563eb; flex-shrink: 0; }
.tip-text { flex: 1; }

.config-field-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.config-field-block label {
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
}
.price-display-box {
  height: 40px;
  width: 160px;
  padding: 0 10px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 9px;
}
@media (min-width: 1366px) {
  .price-display-box {
    height: 42px;
    width: 172px;
  }
}
.price-display-box strong {
  font-size: 17px;
  color: var(--primary-dark);
}

/* ==========================================================================
   整购套餐 SKU 视觉清单网格
   ========================================================================== */
.package-skus-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
}

.sku-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sku-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.sku-count-hint {
  font-size: 11px;
  color: var(--muted);
}

.package-sku-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.package-sku-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 10px;
  transition: all 0.15s ease;
}

.package-sku-item:hover {
  background: #ffffff;
  border-color: rgba(30, 136, 229, 0.4);
  box-shadow: 0 4px 12px -4px rgba(0, 0, 0, 0.08);
}

.sku-item-thumb {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid var(--border);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  cursor: zoom-in;
}

.sku-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.sku-thumb-fallback {
  color: var(--primary);
  opacity: 0.7;
}

.sku-item-info {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sku-item-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sku-item-sub {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11px;
}

.sku-item-spec {
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sku-item-qty {
  color: var(--primary-dark);
  font-weight: 700;
  white-space: nowrap;
}

/* ==========================================================================
   产品实物图全屏灯箱模态框 (Image Lightbox Modal)
   ========================================================================== */
.image-lightbox-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30px;
}

.image-lightbox-content {
  background: #ffffff;
  border-radius: 18px;
  max-width: 860px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 30px 60px -15px rgba(0, 0, 0, 0.55);
  animation: modalPop 0.24s cubic-bezier(0.16, 1, 0.3, 1);
}

.lightbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 22px;
  background: #f8fafc;
  border-bottom: 1px solid var(--border);
}

.lightbox-title-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.lightbox-title {
  font-size: 18px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
}

.lightbox-subtitle {
  font-size: 12px;
  color: var(--muted);
}

.lightbox-close-btn {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #ffffff;
  border: 1px solid var(--border);
  display: grid;
  place-items: center;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.lightbox-close-btn:hover {
  background: var(--red-light);
  color: var(--red);
  border-color: var(--red);
}

.lightbox-body {
  padding: 30px;
  display: grid;
  place-items: center;
  background: radial-gradient(circle at 50% 50%, #ffffff 0%, #f1f5f9 100%);
  min-height: 360px;
  max-height: calc(85vh - 140px);
  overflow: auto;
}

.lightbox-image {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  border-radius: 10px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.15);
}

.lightbox-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 22px;
  background: #f8fafc;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--muted);
}

.esc-hint {
  font-size: 11px;
  background: #e2e8f0;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

@keyframes modalPop {
  from {
    opacity: 0;
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.addons-section {
  grid-column: 1 / -1;
  margin-top: 10px;
  padding: 16px 20px;
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 14px;
}

.addons-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.addons-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.addons-icon {
  color: #6366f1;
}

.addons-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}

.addons-badge {
  padding: 2px 7px;
  border-radius: 999px;
  background: #ede9fe;
  color: #6366f1;
  font-size: 11px;
  font-weight: 700;
}

.addons-hint {
  font-size: 12px;
  color: var(--muted);
}

.addons-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.addon-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  gap: 10px;
}

.addon-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #475569;
  white-space: nowrap;
}

.addon-badge.service {
  background: #e0e7ff;
  color: #4338ca;
}

.addon-badge.accessory {
  background: #e0f2fe;
  color: #0369a1;
}

.addon-info {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.addon-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.addon-spec {
  font-size: 11px;
  color: var(--muted);
}

.addon-pricing {
  text-align: right;
  white-space: nowrap;
}

.addon-price {
  font-size: 14px;
  font-weight: 800;
  color: var(--primary);
}

.addon-unit {
  font-size: 11px;
  color: var(--muted);
}

.addons-empty {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: #fff;
  border: 1px dashed var(--border);
  border-radius: 10px;
  color: var(--muted);
  font-size: 12px;
}

.addons-empty-icon {
  color: #94a3b8;
  flex-shrink: 0;
}


</style>
