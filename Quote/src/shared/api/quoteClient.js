// src/shared/api/quoteClient.js
// 报价端 client —— 暴露公开目录读取（/catalog, /sync）以及报价单持久化提交（/quotes）
import { createHttp } from './http'

const request = createHttp({ withToken: false })
const requestWithAuth = createHttp({ withToken: true })

export const api = {
  /** 公开目录（报价计算器/产品展示读取） */
  getCatalog: () => request('/catalog'),
  /** 主从同步：一次返回目录 + 公司信息 + 报价参数 + rev */
  getSync: () => request('/sync'),
  /** 保存并提交报价单至服务器持久化入库，返回 QuoteOut（含 quote_no 等） */
  createQuote: (payload) =>
    requestWithAuth('/quotes', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
}
