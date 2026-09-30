import { defineStore } from 'pinia'
import { getPlan1UnitPrice } from '../../shared/data/pricing'
import { packagesForSelection } from '../../shared/data/packages'
import { clamp, today } from '../../shared/utils/format'
import { useCatalogStore } from '../../shared/stores/catalog'
import { useSettingsStore } from '../../shared/stores/settings'

// 报价草稿本机持久化键：独立命名空间，仅存本设备；支持与服务器单号联动
const LOCAL_QUOTES_KEY = 'quote_local_quotes_v1'
const LEGACY_LOCAL_QUOTES_KEY = 'hhz_local_quotes_v1'

function toNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function boxCount(quantity, unitsPerBox) {
  const qty = toNumber(quantity)
  const upb = toNumber(unitsPerBox)
  if (qty === null || qty <= 0 || upb === null || upb <= 0) return null
  return qty / upb
}

/**
 * 按套餐类型计算“单套”设备台数/耗材单位数/耗材箱数。
 * 固定整购套餐包含全部耗材行；赠机/推广套餐的耗材行视为任选其一，
 * 因此只取当前选中耗材那一行，避免把多款可选耗材重复相加。
 */
function packageUnitMetrics(pkg, selectedDeviceId, selectedConsumableId) {
  const fixedBundle = Boolean(pkg.fixedBundle)
  const isDevice = (cat) => cat === 'device' || cat === 'hardware'
  const deviceItems = items.filter((item) => isDevice(item.category))
  const consumableItems = fixedBundle
    ? items.filter((item) => !isDevice(item.category))
    : items.filter(
        (item) =>
          !isDevice(item.category) &&
          toNumber(item.productId ?? item.id) === toNumber(selectedConsumableId)
      )

  const deviceQty = toNumber(pkg.deviceQty) ?? null
  const consumableQty = toNumber(pkg.consumableQty) ?? null
  const consumableBoxes = toNumber(pkg.consumableBoxes) ?? null

  let deviceQtyPerSet = deviceQty
  if (deviceItems.length > 0) {
    const deviceItem =
      deviceItems.find(
        (item) => toNumber(item.productId ?? item.id) === toNumber(selectedDeviceId)
      ) || deviceItems[0]
    const qty = toNumber(deviceItem?.quantity)
    if (qty !== null && qty > 0) deviceQtyPerSet = qty
  }

  let consumableQtyPerSet = consumableQty
  let consumableBoxesPerSet = consumableBoxes
  if (consumableItems.length > 0) {
    const quantities = consumableItems
      .map((item) => toNumber(item.quantity))
      .filter((qty) => qty !== null && qty > 0)
    if (quantities.length > 0) consumableQtyPerSet = quantities.reduce((a, b) => a + b, 0)

    const boxes = consumableItems
      .map((item) => boxCount(item.quantity, item.bagsPerBox))
      .filter((value) => value !== null)
    if (boxes.length > 0) consumableBoxesPerSet = Math.round(boxes.reduce((a, b) => a + b, 0))
  }

  return {
    deviceQtyPerSet: deviceQtyPerSet && deviceQtyPerSet > 0 ? deviceQtyPerSet : null,
    consumableQtyPerSet:
      consumableQtyPerSet && consumableQtyPerSet > 0 ? consumableQtyPerSet : null,
    consumableBoxesPerSet:
      consumableBoxesPerSet && consumableBoxesPerSet > 0 ? consumableBoxesPerSet : null
  }
}

/** 从本机读取已保存报价草稿；缺失/损坏时返回 null（静默降级为无草稿） */
function loadLocalQuotes() {
  try {
    const raw =
      localStorage.getItem(LOCAL_QUOTES_KEY) ||
      localStorage.getItem(LEGACY_LOCAL_QUOTES_KEY) ||
      'null'
    const data = JSON.parse(raw)
    return data && Array.isArray(data.savedQuotes) ? data : null
  } catch {
    return null
  }
}

export const useQuoteStore = defineStore('quote', {
  state: () => {
    // 恢复本机草稿（localStorage 中保存的仅是员工自己的报价记录）
    const local = loadLocalQuotes()
    return {
      boxes: 10,
      devices: 2,
      purchaseMode: 'both',
      // “套餐整购”模式：直接按 Workbench 固定整购套餐的套数购买
      packageSetId: null,
      packageSets: 1,
      savedQuotes: local?.savedQuotes ?? [],
      lastSaved: local?.lastSaved ?? null
    }
  },
  getters: {
    settings() {
      return useSettingsStore()
    },
    catalog() {
      return useCatalogStore()
    },
    plan1UnitPrice(state) {
      const tiers = this.catalog.plan1Tiers.length
        ? this.catalog.plan1Tiers
        : this.settings.plan1Tiers
      return getPlan1UnitPrice(state.boxes, tiers)
    },
    plan1DeviceCost(state) {
      return state.devices * (this.catalog.devicePrice || this.settings.devicePrice)
    },
    plan1ConsumablesCost(state) {
      return (
        state.boxes * this.plan1UnitPrice * (this.catalog.bagsPerBox || this.settings.bagsPerBox)
      )
    },
    plan1Total() {
      return this.plan1DeviceCost + this.plan1ConsumablesCost
    },
    /**
     * 当前所选设备 + 耗材在「套餐定义表」中命中的套餐列表。
     * 只有命中套餐的组合才有方案二及以上，其余组合仅支持单独采购。
     */
    matchedPackages() {
      return packagesForSelection(this.catalog.selectedDeviceId, this.catalog.selectedConsumableId)
    },
    hasPackage() {
      return this.matchedPackages.length > 0
    },
    /**
     * 当前所选设备 + 耗材命中的固定整购套餐。
     * “套餐整购”只在当前组合命中 Workbench 固定整购套餐时出现，
     * 避免把妇科套餐展示给其它设备/耗材组合。
     */
    packageOptions() {
      const deviceId = this.catalog.selectedDeviceId
      const consumableId = this.catalog.selectedConsumableId
      if (
        deviceId === null ||
        deviceId === undefined ||
        consumableId === null ||
        consumableId === undefined
      ) {
        return []
      }
      return this.catalog.packages.filter(
        (pkg) =>
          Boolean(pkg.fixedBundle) &&
          pkg.deviceIds.includes(deviceId) &&
          pkg.consumableIds.includes(consumableId)
      )
    },
    activePackage() {
      const options = this.packageOptions
      return options.find((pkg) => pkg.id === this.packageSetId) || null
    },
    packageModeRows() {
      const pkg = this.activePackage
      if (!pkg) return []
      const items = Array.isArray(pkg.items) && pkg.items.length > 0 ? pkg.items : []
      if (items.length > 0) return items
      // 兼容旧同步缓存：固定整购套餐没有 items 时按一对 SKU 恢复单套组成。
      if (pkg.deviceIds.length === 1 && pkg.consumableIds.length === 1) {
        const consumable = this.catalog.productById(pkg.consumableIds[0])
        return [
          { productId: pkg.deviceIds[0], category: 'device', quantity: pkg.deviceQty || 1 },
          {
            productId: pkg.consumableIds[0],
            category: 'consumable',
            quantity: pkg.consumableQty || 0,
            bagsPerBox: consumable?.bagsPerBox ?? null
          }
        ]
      }
      return []
    },
    packageModeTotal(state) {
      return (Number(this.activePackage?.price) || 0) * state.packageSets
    },
    /**
     * 命中的套餐展开为方案卡片（方案二、方案三…按套餐顺序编号）。
     * - 固定整购套餐（fixedBundle，如妇科市代/县代）：整套固定价，按所选台数/箱数
     *   向上取整到整数套数计价，价格不随手动出价或数量变动；
     * - 赠机型套餐（如超声）：按箱数线性折算赠机。
     * 每个方案独立计算套餐费用、含/赠设备价值（套餐固定设备价优先）。
     * 明细优先取自后端同步的 items，因此新增 SKU/修改数量后无需再维护前端逻辑。
     */
    packagePlans(state) {
      const fallbackDevicePrice = this.catalog.devicePrice || this.settings.devicePrice
      return this.matchedPackages.map((pkg, index) => {
        const planNo = index + 2 // 方案二起
        const { deviceQtyPerSet, consumableQtyPerSet, consumableBoxesPerSet } = packageUnitMetrics(
          pkg,
          this.catalog.selectedDeviceId,
          this.catalog.selectedConsumableId
        )
        const unitPrice = Number(pkg.price || 0)
        const valid = unitPrice > 0 && deviceQtyPerSet !== null && consumableBoxesPerSet !== null

        // 固定整购套餐：一套包含 Workbench 填写的全部 SKU，按整套向上取整。
        if (pkg.fixedBundle) {
          const deviceQty = deviceQtyPerSet || 1
          const consumableBoxes = consumableBoxesPerSet || 1
          const packagesNeeded =
            Math.max(
              Math.ceil(state.devices / deviceQty),
              Math.ceil(state.boxes / consumableBoxes)
            ) || 1
          const coveredDevices = packagesNeeded * deviceQty
          const coveredBoxes = packagesNeeded * consumableBoxes
          const total = packagesNeeded * unitPrice
          const perUnitPrice = consumableQtyPerSet ? unitPrice / consumableQtyPerSet : 0
          const deviceValue = coveredDevices * (pkg.devicePrice ?? fallbackDevicePrice)
          const saving = valid ? this.plan1Total - total : 0
          return {
            planNo,
            id: pkg.id,
            pkg,
            fixedBundle: true,
            valid,
            packagesNeeded,
            coveredDevices,
            coveredBoxes,
            deviceQtyPerSet: deviceQty,
            consumableBoxesPerSet: consumableBoxes,
            consumableQtyPerSet,
            minBoxes: consumableBoxesPerSet,
            eligible: valid,
            boxesPerGift: 0,
            gifted: coveredDevices,
            unitPrice: perUnitPrice,
            consumablesCost: total,
            deviceValue,
            total,
            saving,
            better: valid && saving > 0
          }
        }

        // 赠机/推广套餐：每套 = 当前选中耗材单套箱数，赠 deviceQtyPerSet 台设备。
        const minBoxes = consumableBoxesPerSet || 1
        const eligible = valid && state.boxes >= minBoxes
        const packagesNeeded = valid ? Math.ceil(state.boxes / minBoxes) || 1 : 0
        const gifted = packagesNeeded * (deviceQtyPerSet || 0)
        const perUnitPrice = consumableQtyPerSet ? unitPrice / consumableQtyPerSet : 0
        const consumablesCost = packagesNeeded * unitPrice
        const devicePrice = pkg.devicePrice ?? fallbackDevicePrice
        const extraDevices = Math.max(0, state.devices - gifted)
        const deviceCost = extraDevices * devicePrice
        const deviceValue = gifted * devicePrice
        const total = consumablesCost + deviceCost
        const saving = valid ? this.plan1Total - total : 0
        return {
          planNo,
          id: pkg.id,
          pkg,
          valid,
          minBoxes,
          eligible,
          packagesNeeded,
          deviceQtyPerSet: deviceQtyPerSet || 0,
          consumableBoxesPerSet: consumableBoxesPerSet || 0,
          consumableQtyPerSet,
          gifted,
          extraDevices,
          deviceCost,
          boxesPerGift: deviceQtyPerSet ? minBoxes / deviceQtyPerSet : 0,
          unitPrice: perUnitPrice,
          consumablesCost,
          deviceValue,
          total,
          saving,
          better: eligible && saving > 0
        }
      })
    },
    /** 最省钱的套餐方案（需满足起购箱数且优于方案1；无则 null） */
    bestPackagePlan() {
      const winners = this.packagePlans.filter((plan) => plan.better)
      if (winners.length === 0) return null
      return winners.reduce((best, plan) => (plan.saving > best.saving ? plan : best))
    },
    /** 最优方案标识：'plan1' 或 'plan2'/'plan3'…（无套餐或套餐未达标时为方案1） */
    betterPlan() {
      if (!this.hasPackage) return 'plan1'
      const best = this.bestPackagePlan
      return best ? `plan${best.planNo}` : 'plan1'
    },
    /** 最优套餐方案较方案1的节省金额（元） */
    saving() {
      return this.bestPackagePlan?.saving ?? 0
    },
    currentBestTotal() {
      if (this.purchaseMode === 'package') {
        return this.packageModeTotal
      }
      if (this.purchaseMode === 'consumables') {
        return this.plan1ConsumablesCost
      }
      if (this.purchaseMode === 'equipment') {
        return this.plan1DeviceCost
      }
      if (this.betterPlan !== 'plan1') {
        return this.bestPackagePlan.total
      }
      return this.plan1Total
    },
    boxVolume(state) {
      return state.boxes * (this.catalog.bagsPerBox || this.settings.bagsPerBox)
    }
  },
  actions: {
    changeBoxes(delta) {
      this.boxes = clamp(Number(this.boxes) + delta, 1, 500)
    },
    changeDevices(delta) {
      this.devices = clamp(Number(this.devices) + delta, 0, 50)
    },
    setBoxes(value) {
      this.boxes = clamp(Number(value) || 1, 1, 500)
    },
    setDevices(value) {
      this.devices = clamp(Number(value) || 0, 0, 50)
    },
    setPurchaseMode(mode) {
      if (['both', 'consumables', 'equipment', 'package'].includes(mode)) {
        this.purchaseMode = mode
      }
    },
    selectPackage(id) {
      const pkg = this.packageOptions.find((item) => item.id === id)
      if (!pkg) return
      this.packageSetId = pkg.id
      this.packageSets = 1
    },
    changePackageSets(delta) {
      this.packageSets = clamp(Number(this.packageSets) + delta, 1, 1000)
    },
    setPackageSets(value) {
      this.packageSets = clamp(Number(value) || 1, 1, 1000)
    },
    /** 保存到本机。仅存 localStorage，不调用任何后端写接口，不影响服务器数据库 */
    persistLocalQuotes() {
      try {
        localStorage.setItem(
          LOCAL_QUOTES_KEY,
          JSON.stringify({ savedQuotes: this.savedQuotes, lastSaved: this.lastSaved })
        )
      } catch {
        // 本机存储不可用（隐私模式/磁盘满）时静默降级，不影响本次报价
      }
    },
    saveQuote(extra = {}) {
      const directPackage = this.purchaseMode === 'package' ? this.activePackage : null
      const chosen =
        (directPackage ? { pkg: directPackage } : null) ||
        this.bestPackagePlan ||
        this.packagePlans[0] ||
        null
      const serverQuoteNo = extra?.quote_no || extra?.id || null
      const quote = {
        id: serverQuoteNo || `${this.settings.quotePrefix}${String(Date.now()).slice(-6)}`,
        quoteNo: serverQuoteNo,
        customerName: extra?.customer_name || extra?.customerName || '',
        contactPerson: extra?.customer_contact || extra?.contactPerson || '',
        date: today(),
        boxes: this.boxes,
        devices: this.devices,
        unitPrice: this.plan1UnitPrice,
        plan1Total: this.plan1Total,
        plan2Total: directPackage
          ? this.packageModeTotal
          : (this.bestPackagePlan?.total ?? this.packagePlans[0]?.total ?? 0),
        giftedDevices: directPackage
          ? 0
          : (this.bestPackagePlan?.gifted ?? this.packagePlans[0]?.gifted ?? 0),
        betterPlan: directPackage ? 'package' : this.betterPlan,
        mode: this.purchaseMode,
        total: extra?.final_quote_price || this.currentBestTotal,
        hasPackage: directPackage ? Boolean(directPackage) : this.hasPackage,
        packageId: chosen?.pkg.id || null,
        packageName: chosen?.pkg.name || null,
        packageNote: chosen?.pkg.note || '',
        packageSets: directPackage ? this.packageSets : null,
        syncedToServer: Boolean(serverQuoteNo)
      }
      this.savedQuotes.unshift(quote)
      this.lastSaved = quote
      this.persistLocalQuotes()
      return quote
    },
    deleteQuote(id) {
      this.savedQuotes = this.savedQuotes.filter((item) => item.id !== id)
      if (this.lastSaved?.id === id) {
        this.lastSaved = this.savedQuotes[0] || null
      }
      this.persistLocalQuotes()
    },
    restoreQuote(saved) {
      if (!saved) return
      if (saved.mode) this.setPurchaseMode(saved.mode)
      if (saved.devices !== undefined) this.setDevices(saved.devices)
      if (saved.boxes !== undefined) this.setBoxes(saved.boxes)
      if (saved.packageSets !== undefined && saved.packageSets !== null) {
        this.setPackageSets(saved.packageSets)
      }
      if (saved.packageId && this.packageOptions.some((p) => p.id === saved.packageId)) {
        this.selectPackage(saved.packageId)
      }
    }
  }
})
