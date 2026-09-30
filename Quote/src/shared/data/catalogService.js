// src/data/catalogService.js
// 从主设备后端 /api/sync 加载同步负载（目录 + 公司信息 + 报价参数 + rev）。
// 后端不可用或数据异常时返回 null，由调用方（catalog store）回退到本地缓存或内置静态数据。
import { api } from '../api/quoteClient'

export async function loadRemoteCatalog() {
  try {
    const { data } = await api.getSync()
    if (!data || !data.catalog || !Array.isArray(data.catalog.products) || !Array.isArray(data.catalog.packages)) {
      return null
    }
    return {
      products: data.catalog.products,
      packages: data.catalog.packages,
      settings: data.settings || null,
      rev: data.rev || '',
      updated_at: data.updated_at || ''
    }
  } catch {
    return null
  }
}
