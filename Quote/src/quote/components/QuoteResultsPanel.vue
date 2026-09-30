<script setup>
import { computed } from 'vue'
import {
  ArrowUpRight,
  Download,
  Gift,
  Package,
  Sparkles,
  Stethoscope
} from 'lucide-vue-next'
import { useCatalogStore } from '../../shared/stores/catalog'
import { useQuoteStore } from '../stores/quote'
import { formatMoney } from '../../shared/utils/format'

defineProps({
  bannerText: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['export', 'save-draft'])
const quote = useQuoteStore()
const catalog = useCatalogStore()

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

function packageDetailRows(plan) {
  const items = Array.isArray(plan?.pkg?.items) ? plan.pkg.items : []
  if (items.length === 0) return []
  const relevant = plan.fixedBundle
    ? items
    : items.filter((item) => {
        const productId = item.productId ?? item.id
        return (
          (item.category === 'device' && productId === catalog.selectedDeviceId) ||
          (item.category !== 'device' && productId === catalog.selectedConsumableId)
        )
      })
  return relevant.map((item) => {
    const product = catalog.productById(item.productId ?? item.id)
    return {
      ...item,
      name: item.name || product?.name || '未知产品',
      unit: item.unit || product?.unit || '套'
    }
  })
}
</script>

<template>
  <div class="results-container">
    <div class="results-head">
      <h3 class="panel-title">方案比价与结算明细</h3>
      <span v-if="quote.purchaseMode === 'both' && quote.hasPackage" class="results-counter">
        共 {{ quote.packagePlans.length + 1 }} 种方案对比
      </span>
    </div>

    <!-- 结果卡片展示区 -->
    <div class="quote-main">
      <!-- 1. 套餐整购结果 -->
      <div v-if="quote.purchaseMode === 'package'" class="quote-results single">
        <div v-if="directPackageValid" class="result-card winner">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">套餐整购</div>
              <div class="result-card-sub package-sub">{{ directPackage.name }}</div>
            </div>
            <span class="badge badge-blue">固定整购</span>
          </div>
          <div class="result-rows">
            <div
              v-for="item in directPackageRows"
              :key="item.productId ?? item.id"
              class="result-row"
            >
              <span>{{ item.name }}</span>
              <strong>{{ item.quantity ?? 1 }} {{ item.unit }} /套</strong>
            </div>
          </div>
          <div class="result-total">
            <span>{{ quote.packageSets }} 套 × {{ formatMoney(directPackage.price) }}</span>
            <strong class="primary">{{ formatMoney(quote.packageModeTotal) }}</strong>
          </div>
          <p v-if="directPackage.note" class="package-min-hint">{{ directPackage.note }}</p>
        </div>
        <div v-else-if="directPackage" class="result-card no-package-card">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">套餐参数不完整</div>
              <div class="result-card-sub">
                请先在 Workbench 补全价格与 SKU 明细后重新同步
              </div>
            </div>
          </div>
        </div>
        <div v-else class="result-card no-package-card">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">暂无整购套餐</div>
              <div class="result-card-sub">请在 Workbench 中配置固定整购套餐后重新同步</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. 同时购买模式：方案1单独采购 vs 方案2及以上套餐方案 -->
      <div v-else-if="quote.purchaseMode === 'both'" class="quote-results">
        <!-- 方案1 单独采购卡片 -->
        <div class="result-card" :class="{ winner: quote.betterPlan === 'plan1' }">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">方案1 · 单独采购</div>
              <div class="result-card-sub">
                {{ catalog.selectedDevice?.name || '未选设备' }} +
                {{ catalog.selectedConsumable?.name || '未选耗材' }}
              </div>
            </div>
            <span
              v-if="quote.betterPlan === 'plan1' && quote.hasPackage"
              class="badge badge-green"
            >更优推荐</span>
            <span v-else-if="!quote.hasPackage" class="badge badge-muted">仅单独采购</span>
          </div>
          <div class="result-rows">
            <div class="result-row">
              <span>设备费</span>
              <strong>{{ quote.devices }}台 × {{ formatMoney(catalog.devicePrice) }}</strong>
            </div>
            <div class="result-row">
              <span>耗材费</span>
              <strong
                >{{ quote.boxes }}箱 × {{ formatMoney(quote.plan1UnitPrice, 1) }} ×
                {{ catalog.bagsPerBox }}</strong
              >
            </div>
          </div>
          <div class="result-total">
            <span>总价</span>
            <strong :class="{ primary: quote.betterPlan === 'plan1' }">{{ formatMoney(quote.plan1Total) }}</strong>
          </div>
        </div>

        <!-- 方案二及以上套餐方案 -->
        <template v-if="quote.hasPackage">
          <div
            v-for="plan in quote.packagePlans"
            :key="plan.id"
            class="result-card"
            :class="{ winner: plan.better, muted: !plan.eligible }"
          >
            <div class="result-card-head">
              <div>
                <div class="result-card-name">方案{{ plan.planNo }} · 套餐方案</div>
                <div class="result-card-sub package-sub">{{ plan.pkg.name }}</div>
              </div>
              <span v-if="plan.better" class="badge badge-green">更优推荐</span>
            </div>

            <!-- 立省金额醒目标注 -->
            <div v-if="plan.better && plan.saving > 0" class="saving-highlight-tag">
              <Sparkles :size="14" />
              <span>比方案1立省 <strong>¥{{ formatMoney(plan.saving) }}</strong>（省 {{ Math.round((plan.saving / (quote.plan1Total || 1)) * 100) }}%）</span>
            </div>

            <div class="result-rows">
              <template v-if="packageDetailRows(plan).length > 0">
                <div
                  v-for="item in packageDetailRows(plan)"
                  :key="item.productId ?? item.id"
                  class="result-row"
                >
                  <span>{{ item.name }}</span>
                  <strong>{{ item.quantity ?? 1 }} {{ item.unit }} /套</strong>
                </div>
              </template>

              <!-- 固定整购套餐 -->
              <template v-if="plan.fixedBundle">
                <div class="result-row">
                  <span>套餐组成（每套）</span>
                  <strong
                    >{{ plan.deviceQtyPerSet }}台设备 +
                    {{ plan.consumableBoxesPerSet }}箱</strong
                  >
                </div>
                <div class="result-row">
                  <span>需购套数</span>
                  <strong
                    >{{ plan.packagesNeeded }} 套（含 {{ plan.coveredDevices }}台 /
                    {{ plan.coveredBoxes }}箱）</strong
                  >
                </div>
                <div class="result-row">
                  <span>套餐费用</span>
                  <strong
                    >{{ plan.packagesNeeded }}套 × {{ formatMoney(plan.pkg.price) }}</strong
                  >
                </div>
              </template>
              <!-- 赠机型套餐 -->
              <template v-else>
                <div class="result-row">
                  <span>套餐组成（每套）</span>
                  <strong
                    >{{ plan.consumableBoxesPerSet }}箱耗材，赠
                    {{ plan.deviceQtyPerSet }}台设备</strong
                  >
                </div>
                <div class="result-row">
                  <span>折算套数</span>
                  <strong>{{ plan.packagesNeeded }} 套（对应 {{ quote.boxes }} 箱耗材）</strong>
                </div>
                <div class="result-row">
                  <span>赠送设备</span>
                  <strong
                    >{{ plan.gifted }} 台（价值 {{ formatMoney(plan.deviceValue) }}）</strong
                  >
                </div>
                <div v-if="plan.extraDevices > 0" class="result-row">
                  <span>补购设备</span>
                  <strong
                    >{{ plan.extraDevices }}台 × {{ formatMoney(catalog.devicePrice) }}</strong
                  >
                </div>
              </template>
            </div>

            <div class="result-total">
              <span>实付总价</span>
              <strong class="primary">{{ formatMoney(plan.total) }}</strong>
            </div>

            <div v-if="!plan.valid" class="package-min-hint">
              套餐缺少价格或数量等报价参数，请在 Workbench 中补全后重新同步
            </div>
            <!-- 未达起购量提示 + 一键补足按钮 -->
            <div v-else-if="!plan.eligible" class="ineligible-action-box">
              <p class="ineligible-tip">
                需至少 {{ plan.minBoxes }} 箱起购（当前 {{ quote.boxes }} 箱，尚差 {{ plan.minBoxes - quote.boxes }} 箱）
              </p>
              <button
                class="btn btn-sm btn-primary qualify-btn"
                type="button"
                @click="quote.setBoxes(plan.minBoxes)"
              >
                <ArrowUpRight :size="14" />
                <span>一键补足至 {{ plan.minBoxes }} 箱</span>
              </button>
            </div>
            <p v-else-if="plan.pkg.note" class="package-min-hint">{{ plan.pkg.note }}</p>
          </div>
        </template>

        <!-- 无套餐情况 -->
        <div v-else class="result-card no-package-card">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">暂无套餐方案</div>
              <div class="result-card-sub">
                {{ catalog.selectedDevice?.name || '未选设备' }} +
                {{ catalog.selectedConsumable?.name || '未选耗材' }}
              </div>
            </div>
          </div>
          <p class="no-package-tip">
            该组合不在套餐定义表中，目前仅支持单独采购设备与耗材。
          </p>
        </div>
      </div>

      <!-- 3. 仅购耗材模式结果 -->
      <div v-else-if="quote.purchaseMode === 'consumables'" class="quote-results single">
        <div class="result-card winner">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">耗材采购结算</div>
              <div class="result-card-sub">
                按箱数自动匹配阶梯单价（每箱 {{ catalog.bagsPerBox }} {{ catalog.selectedConsumable?.unit }}）
              </div>
            </div>
            <span class="badge badge-blue">阶梯采购</span>
          </div>
          <div class="result-rows">
            <div class="result-row">
              <span>单价折算</span>
              <strong>¥{{ quote.plan1UnitPrice }}/{{ catalog.selectedConsumable?.unit }}</strong>
            </div>
            <div class="result-row">
              <span>采购箱数</span>
              <strong>{{ quote.boxes }} 箱（共 {{ quote.boxes * (catalog.bagsPerBox || 1) }} {{ catalog.selectedConsumable?.unit }}）</strong>
            </div>
          </div>
          <div class="result-total">
            <span>耗材总价</span>
            <strong class="primary">{{ formatMoney(quote.plan1ConsumablesCost) }}</strong>
          </div>
        </div>
      </div>

      <!-- 4. 仅购设备模式结果 -->
      <div v-else class="quote-results single">
        <div class="result-card winner">
          <div class="result-card-head">
            <div>
              <div class="result-card-name">单机采购结算</div>
              <div class="result-card-sub">
                {{ catalog.selectedDevice?.name || '未选设备' }}
              </div>
            </div>
            <span class="badge badge-blue">设备方案</span>
          </div>
          <div class="result-rows">
            <div class="result-row">
              <span>设备单价</span>
              <strong>{{ formatMoney(catalog.devicePrice) }}/台</strong>
            </div>
            <div class="result-row">
              <span>采购数量</span>
              <strong>{{ quote.devices }} 台</strong>
            </div>
          </div>
          <div class="result-total">
            <span>设备总价</span>
            <strong class="primary">{{ formatMoney(quote.plan1DeviceCost) }}</strong>
          </div>
        </div>
      </div>
    </div>

    <!-- 吸底操作与快捷导出工具栏 -->
    <div class="quote-actions sticky-actions">
      <div class="saving-banner" :class="{ 'has-saving': quote.saving > 0 }">
        <Stethoscope v-if="quote.purchaseMode === 'equipment'" :size="15" />
        <Package v-else-if="quote.purchaseMode === 'consumables'" :size="15" />
        <Sparkles v-else-if="quote.saving > 0" :size="15" class="sparkle-icon" />
        <Gift v-else :size="15" />
        <span class="banner-content">{{ bannerText }}</span>
      </div>
      <div class="action-buttons-group">
        <button class="btn btn-outline" type="button" @click="emit('save-draft')">
          保存为草稿
        </button>
        <button class="btn btn-primary" type="button" @click="emit('export')">
          <Download :size="15" />
          导出报价单 PDF
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.results-container {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-title::before {
  content: '';
  display: block;
  width: 4px;
  height: 16px;
  border-radius: 2px;
  background: var(--primary);
}

.results-counter {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-dark);
  background: var(--primary-light);
  padding: 2px 8px;
  border-radius: 6px;
}

.quote-main {
  min-width: 0;
}

.quote-results {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1200px) {
  .quote-results {
    grid-template-columns: 1fr;
  }
}

.quote-results.single {
  grid-template-columns: 1fr;
}

.result-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 10px 24px -16px rgba(13, 71, 161, 0.25);
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all 0.2s ease;
}

.result-card.winner {
  border: 1.5px solid var(--primary);
  background: linear-gradient(180deg, #ffffff 40%, #f0f7ff 100%);
  box-shadow: 0 14px 34px -18px rgba(30, 136, 229, 0.45);
}

.result-card.muted {
  opacity: 0.72;
  border-style: dashed;
  background: #f8fafc;
}

.result-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.result-card-name {
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
}

.result-card-sub {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.saving-highlight-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  font-size: 12px;
}
.saving-highlight-tag strong {
  font-size: 14px;
  color: #047857;
}

.result-rows {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 10px 0;
  border-top: 1px solid #f1f5f9;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
}

.result-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.result-row span {
  color: var(--muted);
}
.result-row strong {
  color: var(--text);
  font-weight: 600;
}

.result-total {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-top: 4px;
}
.result-total span {
  font-size: 13px;
  color: var(--muted);
}
.result-total strong {
  font-size: 24px;
  font-weight: 800;
  color: var(--text);
}
.result-total strong.primary {
  color: var(--primary-dark);
}

.package-min-hint {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: #f8fafc;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}

.ineligible-action-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  background: #fffbeb;
  border: 1px solid #fef3c7;
  border-radius: 8px;
}
.ineligible-tip {
  margin: 0;
  font-size: 11px;
  color: #b45309;
}
.qualify-btn {
  white-space: nowrap;
  font-size: 12px;
  padding: 4px 10px;
  min-height: 28px;
}

.no-package-card {
  border-style: dashed;
  background: var(--bg-alt);
}
.no-package-tip {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}

.sticky-actions {
  position: sticky;
  bottom: 20px;
  background: #fff;
  padding: 16px 20px;
  border: 1px solid var(--border);
  border-radius: 14px;
  box-shadow: 0 16px 36px -12px rgba(13, 71, 161, 0.28);
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

@media (max-width: 640px) {
  .sticky-actions {
    flex-direction: column;
    align-items: stretch;
  }
}

.saving-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--primary-dark);
  padding: 6px 12px;
  border-radius: 8px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  transition: all 0.25s ease;
}

.saving-banner.has-saving {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #047857;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.12);
}

.saving-banner.has-saving .sparkle-icon {
  color: #10b981;
  animation: sparkle-pulse 1.8s infinite ease-in-out;
}

@keyframes sparkle-pulse {
  0%, 100% { transform: scale(1) rotate(0deg); }
  50% { transform: scale(1.18) rotate(10deg); }
}

.banner-content {
  line-height: 1.4;
}

.action-buttons-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* 24寸显示器及大屏视觉微调 */
@media (min-width: 1366px) {
  .panel-title {
    font-size: 18px;
  }
  .result-card {
    padding: 20px 22px;
    gap: 14px;
  }
  .result-card-name {
    font-size: 17px;
  }
  .result-row {
    font-size: 14px;
  }
  .result-total strong {
    font-size: 26px;
  }
  .saving-banner {
    font-size: 14px;
    padding: 8px 14px;
  }
  .sticky-actions {
    padding: 18px 24px;
  }
}

@media (min-width: 1536px) {
  .result-total strong {
    font-size: 28px;
  }
  .result-card {
    padding: 22px 24px;
  }
}
</style>
