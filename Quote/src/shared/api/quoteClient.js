// src/shared/api/quoteClient.js
// 报价版（副系统）专用只读 client —— 只暴露公开只读接口，不携带 token，也没有任何管理/写接口。
//
// 这是客户机单向同步的合法通道：
//   - /catalog：公开目录（落地页报价计算器读取，无需登录）
//   - /sync：  主从同步负载（目录 + 公司信息 + 报价参数 + rev，客户机单向拉取）
//
// 管理接口（products/packages/settings 的增删改）只存在于 src/workbench/api/workbenchClient.js，
// 报价侧代码树中不可见 ——「客户机只读、绝不回写」由此在结构上强制成立。
import { createHttp } from './http'

const request = createHttp({ withToken: false })

export const api = {
  /** 公开目录（报价计算器/产品展示读取） */
  getCatalog: () => request('/catalog'),
  /** 主从同步：一次返回目录 + 公司信息 + 报价参数 + rev */
  getSync: () => request('/sync')
}
