import { defineStore } from 'pinia'
import { productCatalog as staticProducts } from '../data/productCatalog'
import {
  consumableIdsForDevice,
  deviceConsumablesRestricted,
  getActivePackages,
  setPackages,
  STATIC_DEVICE_BINDINGS
} from '../data/packages'
import { loadRemoteCatalog } from '../data/catalogService'
import { useSettingsStore } from './settings'
import { loadCatalogCache, saveCatalogCache } from '../utils/catalogCache'

// 目录同步中的共用请求：App 启动/落地页/工作台可能同时触发 hydrate，只发一次
let inflightHydrate = null

const staticDeviceList = staticProducts.filter((product) => product.category === 'device')
const staticConsumableList = staticProducts.filter((product) => product.category === 'consumable')

/** 默认选中第一台设备，并默认搭配其适用耗材（使默认组合在套餐定义表内） */
function defaultSelection(deviceList, consumableList, bindingMap = {}) {
  const deviceId = deviceList[0]?.id ?? null
  const bound = bindingMap[deviceId]
  const ids = bound && bound.length > 0 ? bound : consumableList.map((c) => c.id)
  const consumableId =
    consumableList.find((c) => ids.includes(c.id))?.id ?? consumableList[0]?.id ?? null
  return { deviceId, consumableId }
}

const initial = defaultSelection(staticDeviceList, staticConsumableList, STATIC_DEVICE_BINDINGS)

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    selectedDeviceId: initial.deviceId,
    selectedConsumableId: initial.consumableId,
    // 目录列表默认使用内置静态数据；hydrateFromRemote 成功后替换为后端数据库数据
    allProducts: [...staticProducts],
    deviceList: [...staticDeviceList],
    consumableList: [...staticConsumableList],
    accessoryList: [],
    serviceList: [],
    // 生效套餐列表（远程在线/缓存时以后端为准；空目录也保持为空）
    packages: getActivePackages(),
    prices: Object.fromEntries(
      staticProducts.map((product) => [product.id, Number(product.price) || 0])
    ),
    // 设备-耗材绑定（远程模式）：deviceId → 绑定耗材 id 列表；空/缺失 = 未绑定（自由搭配）
    bindings: {},
    source: 'static', // 'static' | 'remote' | 'cache'
    lastSyncAt: null // 最近一次成功同步时间
  }),
  getters: {
    priceOf(state) {
      return (id) => Number(state.prices[id]) || 0
    },
    selectedDevice(state) {
      return state.deviceList.find((product) => product.id === state.selectedDeviceId) || null
    },
    selectedConsumable(state) {
      return (
        state.consumableList.find((product) => product.id === state.selectedConsumableId) || null
      )
    },
    /** 按 id 查询任一目录产品（设备或耗材），供方案等区块展示名称/参数 */
    productById(state) {
      return (id) => {
        const num = Number(id)
        return (
          (state.allProducts && state.allProducts.find((product) => product.id === num)) ||
          state.deviceList.find((product) => product.id === num) ||
          state.consumableList.find((product) => product.id === num) ||
          (state.accessoryList && state.accessoryList.find((product) => product.id === num)) ||
          (state.serviceList && state.serviceList.find((product) => product.id === num)) ||
          null
        )
      }
    },
    /**
     * 当前设备可搭配的耗材 id 列表（设备-耗材绑定）：
     * 绑定了耗材的设备仅限绑定列表内的耗材，未绑定耗材的设备可自由搭配全部耗材。
     * 未选设备时返回全部耗材（支持仅购耗材）。
     */
    applicableConsumableIds(state) {
      if (this.source !== 'static') {
        const id = this.selectedDeviceId
        if (id === null || id === undefined) return state.consumableList.map((c) => c.id)
        const bound = state.bindings[id]
        return bound && bound.length > 0 ? [...bound] : state.consumableList.map((c) => c.id)
      }
      return consumableIdsForDevice(this.selectedDeviceId)
    },
    applicableConsumables() {
      return this.consumableList.filter((product) =>
        this.applicableConsumableIds.includes(product.id)
      )
    },
    /** 当前所选设备是否受限搭配耗材（绑定了耗材即受限，决定耗材是否置灰） */
    selectedDeviceConsumablesRestricted(state) {
      if (this.source !== 'static') {
        const bound = state.bindings[this.selectedDeviceId]
        return Boolean(bound && bound.length > 0)
      }
      return deviceConsumablesRestricted(this.selectedDeviceId)
    },
    devicePrice() {
      return this.priceOf(this.selectedDeviceId)
    },
    plan1Tiers() {
      const price = this.priceOf(this.selectedConsumableId)
      return price > 0 ? [{ minBoxes: 1, price, label: '手动报价' }] : []
    },
    plan2UnitPrice() {
      const fixed = Number(this.selectedConsumable?.plan2Price)
      return fixed > 0 ? fixed : this.priceOf(this.selectedConsumableId)
    },
    bagsPerBox() {
      return Number(this.selectedConsumable?.bagsPerBox) || 0
    },
    selectionLabel() {
      return `${this.selectedDevice?.name || '未选择设备'} + ${this.selectedConsumable?.name || '未选择耗材'}`
    }
  },
  actions: {
    selectDevice(id) {
      const value = id === null || id === undefined || id === '' ? null : Number(id)
      if (value !== null && !this.deviceList.some((product) => product.id === value)) return
      this.selectedDeviceId = value
      // 设备切换后，若当前耗材不适用于新设备，则自动清空（设备-耗材绑定）
      if (value !== null && !this.applicableConsumableIds.includes(this.selectedConsumableId)) {
        this.selectedConsumableId = null
      }
    },
    selectConsumable(id) {
      const value = id === null || id === undefined || id === '' ? null : Number(id)
      if (value !== null && !this.consumableList.some((product) => product.id === value)) return
      this.selectedConsumableId = value
    },
    toggleDevice(id) {
      this.selectDevice(this.selectedDeviceId === id ? null : id)
    },
    toggleConsumable(id) {
      this.selectConsumable(this.selectedConsumableId === id ? null : id)
    },
    setPrice(id, value) {
      const price = Number(value)
      this.prices[id] = Number.isFinite(price) && price >= 0 ? price : 0
    },
    /**
     * 把「同步负载」（产品 + 套餐 + 绑定 + 公司信息 + 报价参数）应用到本地状态。
     * 只拉取覆盖，绝不把本地改动写回服务器（母版单向同步）。
     */
    applyRemote(remote) {
      const isDevice = (p) => p.category === 'device' || p.category === 'hardware'
      const isConsumable = (p) => p.category === 'consumable'
      const isAccessory = (p) => p.category === 'accessory'
      const isService = (p) => p.category === 'service'
      const products = Array.isArray(remote.products) ? remote.products : []
      this.allProducts = products
      this.deviceList = products.filter(isDevice)
      this.consumableList = products.filter(isConsumable)
      this.accessoryList = products.filter(isAccessory)
      this.serviceList = products.filter(isService)
      this.prices = Object.fromEntries(
        products.map((product) => [product.id, Number(product.price) || 0])
      )
      // 设备-耗材绑定：取自后端 device_bindings（设备接口附带 boundConsumables）
      this.bindings = Object.fromEntries(
        products
          .filter(isDevice)
          .map((device) => [device.id, (device.boundConsumables || []).map(Number)])
      )
      setPackages(remote.packages)
      this.packages = getActivePackages()
      if (remote.settings) useSettingsStore().applyRemote(remote.settings)
      // 目录替换后重置默认选择，保证选中项在远程目录中有效
      const next = defaultSelection(this.deviceList, this.consumableList, this.bindings)
      this.selectedDeviceId = next.deviceId
      this.selectedConsumableId = next.consumableId
    },
    /**
     * 同步「主设备目录」：优先拉服务器 → 成功写本地缓存；失败读本地缓存；
     * 从没缓存过才回退内置静态数据。
     * - 返回 'remote'（服务器同步）| 'cache'（离线，用本地缓存）| 'static'（内置演示）；
     * - 并发去重：App 启动 / 落地页可能同时触发，只发一次请求、共用结果；
     * - 手动改价能力不受影响：prices 以目录最低价初始化，用户仍可随时调整（仅本机）。
     */
    async hydrateFromRemote() {
      if (inflightHydrate) return inflightHydrate
      inflightHydrate = (async () => {
        const remote = await loadRemoteCatalog()
        if (remote) {
          await saveCatalogCache(remote)
          this.applyRemote(remote)
          this.source = 'remote'
          this.lastSyncAt = remote.updated_at || new Date().toISOString()
          return 'remote'
        }
        const cached = await loadCatalogCache()
        if (cached && Array.isArray(cached.products) && Array.isArray(cached.packages)) {
          this.applyRemote(cached)
          this.source = 'cache'
          this.lastSyncAt = cached.updated_at || null
          return 'cache'
        }
        this.source = 'static'
        return 'static'
      })()
      try {
        return await inflightHydrate
      } finally {
        inflightHydrate = null
      }
    },
    /**
     * 用户主动重新同步：等待当前进行中的同步结束后立即再拉一次，
     * 用于 Workbench 修改套餐/价格后无需重启 Quote 即可看到最新数据。
     */
    async syncNow() {
      if (inflightHydrate) {
        try {
          await inflightHydrate
        } catch {
          // 忽略进行中请求的失败，下面仍会发起一次新同步
        }
      }
      return this.hydrateFromRemote()
    }
  }
})
