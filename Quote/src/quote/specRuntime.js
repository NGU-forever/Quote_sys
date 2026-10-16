/**
 * Spec 运行时适配器 —— 纯逻辑层（不依赖 Vue / pinia，可直接单测）。
 *
 * 报价单 store 的模型是「一台设备 + 一种耗材 + 台数/箱数 + 采购模式」，
 * 而 Spec 的区块（item_table_editable / price_summary / bundle_suggestion）
 * 期待的是通用行项目列表。这里负责两层翻译：
 *
 *   1. store → items：派生出可渲染的行项目（单价、数量、小计、底价校验）
 *   2. 区块事件 → store 意图：把 add-item / update-qty / remove-item / apply-bundle
 *      翻译成对 store 的动作，交回 composable 执行
 *
 * 金额口径与 store 对齐：设备行小计 = 台数 × 设备单价（plan1DeviceCost），
 * 耗材行小计 = 箱数 × 每箱价（plan1ConsumablesCost），两行合计即方案一总价。
 */

/** 设备类目判定（与 store 内 isDevice 保持一致） */
export function isDeviceCategory(category) {
  return category === 'device' || category === 'hardware';
}

function buildRow({ kind, product, unitPrice, qty, unit }) {
  const price = Number(unitPrice) || 0
  const quantity = Number(qty) || 0
  const floorPrice = Number(product?.min_price) || 0
  return {
    id: product?.id ?? null,
    sku_id: product?.sku_id ?? product?.id ?? '',
    name: product?.name || '',
    category: product?.category || (kind === 'device' ? 'device' : 'consumable'),
    unit: product?.unit || unit,
    unit_price: price,
    qty: quantity,
    subtotal: price * quantity,
    floor_price: floorPrice,
    kind,
    // 底价校验：目录里登记了底价、且当前单价低于底价时才标红
    floor_status: floorPrice > 0 && price > 0 && price < floorPrice ? 'warn' : 'ok',
  }
}

/**
 * 由报价单 store 的当前选择派生行项目。
 *
 * @param {object} input
 * @param {object|null} input.device            选中设备
 * @param {number} input.devicePrice            设备单价
 * @param {number} input.devices                设备台数
 * @param {object|null} input.consumable        选中耗材
 * @param {number} input.consumableBoxPrice     每箱耗材价（单袋价 × 每箱袋数）
 * @param {number} input.boxes                  耗材箱数
 * @param {string} input.purchaseMode           both | consumables | equipment | package
 */
export function buildRuntimeItems(input = {}) {
  const {
    device = null,
    devicePrice = 0,
    devices = 0,
    consumable = null,
    consumableBoxPrice = 0,
    boxes = 0,
    purchaseMode = 'both',
  } = input

  const rows = []
  const withDevices = purchaseMode !== 'consumables'
  const withConsumables = purchaseMode !== 'equipment'

  if (device && withDevices) {
    rows.push(buildRow({ kind: 'device', product: device, unitPrice: devicePrice, qty: devices, unit: '台' }))
  }
  if (consumable && withConsumables) {
    rows.push(
      buildRow({
        kind: 'consumable',
        product: consumable,
        unitPrice: consumableBoxPrice,
        qty: boxes,
        unit: '箱',
      })
    )
  }
  return rows
}

/** 由最优套餐方案派生 BundleSuggestionBlock 的入参；无方案时返回 null（区块自动隐藏） */
export function buildRuntimeBundle(plan) {
  if (!plan || !plan.pkg) return null
  return {
    name: plan.pkg.name,
    note: plan.pkg.note || '',
    saving_amount: Number(plan.saving) || 0,
    planNo: plan.planNo ?? null,
    pkg: plan.pkg,
  }
}

/**
 * 把区块事件翻译成对 store 的「意图」。
 *
 * 返回值是一份声明式描述（而非直接调用 store），便于脱离 pinia 单测；
 * 返回 null 表示该事件无处安放（例如没有对应行、参数非法）。
 *
 * @returns {null | {action: string, [key: string]: any}}
 */
export function resolveBlockIntent(name, payload, items = []) {
  switch (name) {
    case 'add-item': {
      const product = payload
      const id = product?.id
      if (id === null || id === undefined || id === '') return null
      return {
        action: 'selectProduct',
        kind: isDeviceCategory(product.category) ? 'device' : 'consumable',
        id,
        name: product.name || '',
      }
    }

    case 'update-qty': {
      const row = items[payload?.index]
      if (!row) return null
      const qty = Number(payload?.qty)
      if (!Number.isFinite(qty) || qty < 0) return null
      return row.kind === 'device'
        ? { action: 'setDevices', value: qty }
        : { action: 'setBoxes', value: qty }
    }

    case 'remove-item': {
      const row = items[payload]
      if (!row) return null
      // 计价模型没有「删行」，对应的语义是切换采购模式：
      // 去掉设备行 → 只买耗材；去掉耗材行 → 只买设备
      return { action: 'removeRow', kind: row.kind }
    }

    case 'apply-bundle': {
      const pkg = payload?.pkg
      if (!pkg || pkg.id === undefined || pkg.id === null) return null
      return {
        action: 'applyBundle',
        packageId: pkg.id,
        fixedBundle: Boolean(pkg.fixedBundle),
        name: pkg.name || '',
      }
    }

    default:
      return null
  }
}

/**
 * 执行意图：调用传入的 store 门面。
 *
 * 通过 deps 注入 store，便于用假对象单测"到底调了哪个动作"，
 * 也让 composable 保持极薄（只负责把真实 store 传进来）。
 *
 * @param {object} intent  resolveBlockIntent 的返回值
 * @param {{store: object, catalog: object, notify?: (message: string, type?: string) => void}} deps
 * @returns {boolean} 是否真正执行了动作
 */
export function applyIntent(intent, deps = {}) {
  const { store, catalog, notify } = deps
  if (!intent || !store || !catalog) return false

  switch (intent.action) {
    case 'selectProduct':
      if (intent.kind === 'device') {
        catalog.selectDevice(intent.id)
        notify?.(`已加入设备：${intent.name}`, 'info')
      } else {
        catalog.selectConsumable(intent.id)
        notify?.(`已加入耗材：${intent.name}`, 'info')
      }
      return true

    case 'setDevices':
      store.setDevices(intent.value)
      return true

    case 'setBoxes':
      if (intent.value < 1) {
        // 箱数下限为 1：填 0 的语义是"不买耗材"，切到纯设备模式而不是强行保留一行
        store.setPurchaseMode('equipment')
      } else {
        store.setBoxes(intent.value)
      }
      return true

    case 'removeRow':
      if (intent.kind === 'device') {
        store.setDevices(0)
        store.setPurchaseMode('consumables')
      } else {
        store.setPurchaseMode('equipment')
      }
      return true

    case 'applyBundle':
      if (intent.fixedBundle) {
        store.setPurchaseMode('package')
        store.selectPackage(intent.packageId)
        notify?.(`已选用套餐：${intent.name}`, 'success')
      } else {
        // 赠机型套餐无需"选用"：store 会自动按最优方案计价
        store.setPurchaseMode('both')
        notify?.(`已按最优套餐计价：${intent.name}`, 'success')
      }
      return true

    default:
      return false
  }
}
