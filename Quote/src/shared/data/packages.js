// 套餐定义与设备-耗材绑定规则
// 数据来源：assets/产品最低价格.xlsx「套餐定义表」与「SKU主表」
// product id 与 src/data/productCatalog.js 保持一致：
//   P001=1  P002=2  P003=3  P004=4  P005=5  P006=6  P007=7  P008=8  P009=9
//   P010=10 P011=11 P012=12 P013=13
//   C001=14 C002=15 C003=16 C004=17 C005=18 C006=19 C007=20 C008=21
//   C009=22 C011=23 C010=24 C012=25

/**
 * 套餐定义（套餐定义表）
 * - deviceId:      套餐包含的设备
 * - consumableIds: 套餐绑定的耗材列表（可多款）
 * - deviceQty:     套餐含设备台数
 * - consumableQty: 套餐含耗材总数量（袋/瓶/盒，按计价单位）
 * - consumableBoxes: 套餐含耗材箱数
 * - price:         套餐标准价（元）
 * - devicePrice:   套餐内设备固定单价（元/台，可选；缺省用目录价/手动报价）
 * - fixedBundle:   固定整购套餐（如妇科市代/县代）：一套 = deviceQty 台设备 +
 *   consumableBoxes 箱耗材，价格为固定 price；按所选台数/箱数向上取整到整数套数
 *   计价，价格不随手动出价或数量变动。
 */
export const PACKAGES = [
  {
    id: 'PKG001',
    name: '超声治疗（台式）推广套餐',
    deviceId: 1, // P001 超声波治疗仪CSY-200（台式）
    consumableIds: [17, 25], // C004 超声耦合贴片（肤色布平面易撕口）+ C012 超声治疗固定贴
    deviceQty: 1,
    consumableQty: 1200, // 2箱 × 600袋
    consumableBoxes: 2,
    price: 6000,
    note: '买2箱（超声耦合贴片，5元/袋）送1台台式超声波治疗仪CSY-200；设备为赠送，单买价≥2500'
  },
  // 注：Excel「套餐定义表」中的 PKG002（超声治疗（立式）推广套餐）不生效——
  // 立式超声波治疗仪 CSY-300 不赠送设备，无方案二（仅单独采购），故不在 PACKAGES 中提供。
  {
    id: 'PKG003',
    name: '妇科推广套餐（市代）',
    deviceId: 13, // P013 妇科臭氧治疗仪
    consumableIds: [24], // C010 妇科医用阻菌凝胶
    deviceQty: 10,
    consumableQty: 4000, // 10箱 × 400瓶
    consumableBoxes: 10,
    price: 138000,
    devicePrice: 9000, // 套餐内设备价格固定 9000 元/台
    fixedBundle: true, // 固定整购：一套=10台+10箱=138000，价格固定
    note: '10台设备，10箱耗材（妇科医用阻菌凝胶按箱计，1箱=400瓶；设备价格固定9000，耗材价格固定12/瓶）'
  },
  {
    id: 'PKG004',
    name: '妇科推广套餐（县代）',
    deviceId: 13, // P013 妇科臭氧治疗仪
    consumableIds: [24], // C010 妇科医用阻菌凝胶
    deviceQty: 4,
    consumableQty: 1600, // 4箱 × 400瓶
    consumableBoxes: 4,
    price: 53800,
    devicePrice: 9000, // 套餐内设备价格固定 9000 元/台
    fixedBundle: true, // 固定整购：一套=4台+4箱=53800，价格固定
    note: '4台设备，4箱耗材（妇科医用阻菌凝胶按箱计，1箱=400瓶；设备价格固定9000，耗材价格固定12/瓶）'
  }
]

function toNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

/** 规范化套餐：统一 id、设备/耗材数组并计算实际结算价（兼容旧版同步负载）。 */
function normalizePackage(pkg) {
  if (!pkg) return null
  const id = String(pkg.id ?? pkg.packageId ?? pkg.package_id ?? '')
  const rawDeviceIds = Array.isArray(pkg.deviceIds)
    ? pkg.deviceIds
    : pkg.deviceId !== null && pkg.deviceId !== undefined
      ? [pkg.deviceId]
      : []
  const rawConsumableIds = Array.isArray(pkg.consumableIds)
    ? pkg.consumableIds
    : pkg.consumableId !== null && pkg.consumableId !== undefined
      ? [pkg.consumableId]
      : []
  const deviceIds = [...new Set(rawDeviceIds.map((n) => toNumber(n)).filter((n) => n !== null))]
  const consumableIds = [
    ...new Set(rawConsumableIds.map((n) => toNumber(n)).filter((n) => n !== null))
  ]

  const stdPrice = toNumber(pkg.stdPrice ?? pkg.std_price ?? pkg.price)
  const discountPrice = toNumber(pkg.discountPrice ?? pkg.discount_price)
  const parsedRate = toNumber(pkg.discountRate ?? pkg.discount_rate)
  const rate = parsedRate !== null && parsedRate > 0 && parsedRate < 1 ? parsedRate : null
  const effectivePrice =
    toNumber(pkg.price) ??
    discountPrice ??
    (stdPrice !== null && rate !== null ? stdPrice * rate : null) ??
    stdPrice

  return {
    ...pkg,
    id,
    packageId: id,
    deviceIds,
    consumableIds,
    deviceId: deviceIds[0] ?? null,
    price: effectivePrice,
    stdPrice,
    discountPrice,
    discountRate: rate,
    fixedBundle: Boolean(pkg.fixedBundle)
  }
}

/**
 * 耗材 → 适用设备（SKU主表「适用设备」列，映射为 product id 数组）。
 * 作为设备-耗材绑定的物理适配依据：反向推导出每个设备可绑定的耗材列表。
 * 其 key 同时作为目录中全部耗材 id 的来源。
 */
export const CONSUMABLE_DEVICE_MAP = {
  14: [3, 4, 5, 6], // C001 理疗用体表电极（经颅磁用）→ 经颅磁系列
  15: [3, 4, 5, 6], // C002 耳后电极片（经颅磁用）→ 经颅磁系列
  16: [3, 4, 5, 6], // C003 4x4肢体尾巴线电极片（经颅磁用）→ 经颅磁系列
  17: [1, 2], // C004 超声耦合贴片 → 超声波治疗仪系列
  18: [7, 8, 11, 12], // C005 理疗电极片（7x10单孔）→ 中频/透药通用
  19: [7, 8, 11, 12], // C006 理疗电极片（8x8…）→ 中频/透药通用
  20: [7, 8, 11, 12], // C007 理疗电极片（6x9黄棉）→ 中频/透药通用
  21: [7, 8, 11, 12], // C008 理疗电极片（8x8尾巴线黄棉）→ 中频/透药通用
  22: [7, 8, 11, 12], // C009 理疗电极片（10x10尾巴线黄棉）→ 中频/透药通用
  23: [7, 8, 11, 12], // C011 灸疗装置 → 中医定向透药/通用
  24: [13], // C010 妇科医用阻菌凝胶 → 妇科臭氧治疗仪
  25: [1, 2] // C012 超声治疗固定贴 → 超声波治疗仪系列
}

/** 目录中全部耗材 id */
export const ALL_CONSUMABLE_IDS = Object.keys(CONSUMABLE_DEVICE_MAP).map(Number)

/**
 * 设备 → 绑定耗材 id（设备-耗材绑定，静态内置规则）：
 * 由「适用设备」映射反向推导 + 套餐隐含绑定补充。
 * 绑定了耗材的设备在前端选耗材时受限；未绑定任何耗材的设备（如胃肠生物反馈、
 * 体外冲击波，无适用耗材）可自由搭配任意耗材。
 */
export const STATIC_DEVICE_BINDINGS = (() => {
  const map = {}
  for (const [consumableId, deviceIds] of Object.entries(CONSUMABLE_DEVICE_MAP)) {
    const cid = Number(consumableId)
    for (const deviceId of deviceIds) {
      const list = (map[deviceId] = map[deviceId] || [])
      if (!list.includes(cid)) list.push(cid)
    }
  }
  // 套餐隐含绑定（通常已涵盖在适用设备映射内，此处兜底补充）
  for (const pkg of PACKAGES) {
    const list = (map[pkg.deviceId] = map[pkg.deviceId] || [])
    for (const cid of pkg.consumableIds) {
      if (!list.includes(cid)) list.push(cid)
    }
  }
  return map
})()

/**
 * 设备可搭配的耗材 id 列表（设备-耗材绑定规则）：
 * - 未选设备：全部耗材（支持仅购耗材）；
 * - 绑定了耗材的设备：仅限绑定列表（适用设备系列绑定 + 套餐绑定）；
 * - 未绑定任何耗材的设备：与耗材自由搭配（全部可选）。
 */
export function consumableIdsForDevice(deviceId) {
  const id = Number(deviceId)
  if (!id) return [...ALL_CONSUMABLE_IDS]
  const bound = STATIC_DEVICE_BINDINGS[id]
  return bound && bound.length > 0 ? [...bound] : [...ALL_CONSUMABLE_IDS]
}

/** 某设备的耗材选择是否受限（绑定列表非空） */
export function deviceConsumablesRestricted(deviceId) {
  const id = Number(deviceId)
  if (!id) return false
  const bound = STATIC_DEVICE_BINDINGS[id]
  return Boolean(bound && bound.length > 0)
}

/**
 * 生效中的套餐列表（默认内置静态 PACKAGES）。
 * 落地页从工作台数据库水合目录时，通过 setPackages 替换为后端套餐，
 * 使管理员在后台新增/修改的套餐即时作用于报价计算器。
 */
let activePackages = PACKAGES

export function setPackages(list) {
  if (!Array.isArray(list)) return
  // 后端在线/缓存加载成功后，后端列表是唯一事实源：即使为空也清空演示套餐，
  // 避免“已删除全部套餐”后 Quote 仍展示内置示例。
  activePackages = list.map(normalizePackage).filter(Boolean)
}

export function getActivePackages() {
  return activePackages.map((pkg) => normalizePackage(pkg)).filter(Boolean)
}

/** 返回同时匹配指定设备与耗材的套餐（无匹配则为空数组） */
export function packagesForSelection(deviceId, consumableId) {
  const device = toNumber(deviceId)
  const consumable = toNumber(consumableId)
  if (!device || !consumable) return []
  return activePackages
    .map((pkg) => normalizePackage(pkg))
    .filter((pkg) => pkg.deviceIds.includes(device) && pkg.consumableIds.includes(consumable))
}

/** 返回某设备支持的全部套餐（用于提示可搭配的耗材） */
export function packagesForDevice(deviceId) {
  const id = toNumber(deviceId)
  if (!id) return []
  return activePackages
    .map((pkg) => normalizePackage(pkg))
    .filter((pkg) => pkg.deviceIds.includes(id))
}
