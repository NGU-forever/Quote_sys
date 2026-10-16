/**
 * useSpecRuntime：Spec 运行时外壳的宿主适配器。
 *
 * 把「设计器生成的界面」接到真实的报价单 store 上：
 * - 下行：store 的设备/耗材/台数/箱数 → RuntimeShell 需要的 data（含行项目、套餐、业务员）
 * - 上行：区块事件（加货/改数量/移除/选用套餐/保存草稿/打印） → store 动作
 *
 * 有了它，定制屏才是「能成交的界面」，而不只是观感层。
 */
import { computed } from 'vue'

import { useCatalogStore } from '../../shared/stores/catalog'
import { useToast } from '../../shared/composables/useToast'
import { useAuthStore } from '../stores/auth'
import { useQuoteStore } from '../stores/quote'
import { applyIntent, buildRuntimeBundle, buildRuntimeItems, resolveBlockIntent } from '../specRuntime.js'

export function useSpecRuntime({ onExport } = {}) {
  const store = useQuoteStore()
  const catalog = useCatalogStore()
  const auth = useAuthStore()
  const toast = useToast()

  /** 每箱耗材价 = 单袋阶梯价 × 每箱袋数（与 store 的 plan1ConsumablesCost 同口径） */
  const consumableBoxPrice = computed(
    () => (Number(store.plan1UnitPrice) || 0) * (Number(catalog.bagsPerBox) || 0)
  )

  const items = computed(() =>
    buildRuntimeItems({
      device: catalog.selectedDevice,
      devicePrice: catalog.devicePrice,
      devices: store.devices,
      consumable: catalog.selectedConsumable,
      consumableBoxPrice: consumableBoxPrice.value,
      boxes: store.boxes,
      purchaseMode: store.purchaseMode,
    })
  )

  const bundle = computed(() => buildRuntimeBundle(store.bestPackagePlan))

  /**
   * RuntimeShell 的 data。
   * totalAmount 用 store 的有效总价（含最优套餐），而不是行项目简单相加 ——
   * 否则有套餐优惠时，定制屏的价格合计会比经典视图偏高。
   */
  const data = computed(() => ({
    products: catalog.allProducts || [],
    items: items.value,
    bundle: bundle.value,
    totalAmount: store.currentBestTotal,
    customer: {},
    quote: {
      sales_name: auth.username || auth.displayName || '',
    },
  }))

  function saveDraft() {
    const saved = store.saveQuote()
    toast.push(`已保存当前报价草稿（单号 ${saved.id}）`, 'success')
  }

  /** 统一入口：区块事件 → store 动作 */
  function dispatch(name, payload) {
    if (name === 'save-draft') return saveDraft()
    if (name === 'print-a4' || name === 'export-pdf') return onExport?.()

    const intent = resolveBlockIntent(name, payload, items.value)
    if (!intent) return
    applyIntent(intent, {
      store,
      catalog,
      notify: (message, type = 'info') => toast.push(message, type),
    })
  }

  return { data, items, bundle, dispatch, saveDraft }
}
