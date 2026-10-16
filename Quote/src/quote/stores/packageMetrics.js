/**
 * 套餐明细与「单套用量」计算。
 *
 * 从 quote store 中抽出：全部是纯函数，不依赖 pinia / localStorage / 浏览器 API，
 * 因此可以在 `node --test` 下直接单测（store 本身因 Vite 无扩展名导入无法在 node 里加载）。
 *
 * 背景：`packageUnitMetrics` 原先在 store 内直接引用了未定义的 `items`
 * （既不是参数也不是局部变量），只要选中组合命中套餐就抛 ReferenceError，
 * 导致方案二/方案三的套餐卡片全部渲染不出来。这里把明细行显式传入。
 */

export function toNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function boxCount(quantity, unitsPerBox) {
  const qty = toNumber(quantity)
  const upb = toNumber(unitsPerBox)
  if (qty === null || qty <= 0 || upb === null || upb <= 0) return null
  return qty / upb
}

/**
 * 套餐的明细行：优先取后端同步的 items；兼容旧同步缓存时按一对 SKU 恢复单套组成。
 * 与 `packageModeRows` 原先的内联逻辑保持一致。
 */
export function packageItems(pkg, catalog) {
  const items = Array.isArray(pkg?.items) && pkg.items.length > 0 ? pkg.items : []
  if (items.length > 0) return items
  if (pkg?.deviceIds?.length === 1 && pkg?.consumableIds?.length === 1) {
    const consumable = catalog?.productById?.(pkg.consumableIds[0])
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
}

/**
 * 按套餐类型计算「单套」设备台数/耗材单位数/耗材箱数。
 * 固定整购套餐包含全部耗材行；赠机/推广套餐的耗材行视为任选其一，
 * 因此只取当前选中耗材那一行，避免把多款可选耗材重复相加。
 */
export function packageUnitMetrics(pkg, items, selectedDeviceId, selectedConsumableId) {
  const rows = Array.isArray(items) ? items : []
  const fixedBundle = Boolean(pkg?.fixedBundle)
  const isDevice = (cat) => cat === 'device' || cat === 'hardware'
  const deviceItems = rows.filter((item) => isDevice(item.category))
  const consumableItems = fixedBundle
    ? rows.filter((item) => !isDevice(item.category))
    : rows.filter(
        (item) =>
          !isDevice(item.category) &&
          toNumber(item.productId ?? item.id) === toNumber(selectedConsumableId)
      )

  const deviceQty = toNumber(pkg?.deviceQty) ?? null
  const consumableQty = toNumber(pkg?.consumableQty) ?? null
  const consumableBoxes = toNumber(pkg?.consumableBoxes) ?? null

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
