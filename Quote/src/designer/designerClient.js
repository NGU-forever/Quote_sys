/**
 * 设计器 API client。
 *
 * 关键：`/api/designer/*` 全部是**管理员端点**（后端 `_require_admin`）。
 * 此前设计器用裸 fetch 调用、不带 Authorization，于是每次都被 401 拦下，
 * 又被各处的 try/catch 静默吞掉 —— 界面看起来正常，实则一直跑在内置默认值上。
 * 这里统一改走带 token 的 http 工厂：有令牌就带上，401 会真的抛出并清 token。
 */
import { createHttp } from '../shared/api/http.js'

const request = createHttp({ withToken: true })

export const designerApi = {
  /** 画像指标 + 排序 + 样本数据 */
  signals: () => request('/designer/signals', { method: 'POST' }),

  /** 资料 + 库内数据 → 业务画像与人话摘要（answers 可选，带上更具体） */
  profile: (answers) =>
    request('/designer/profile', {
      method: 'POST',
      body: JSON.stringify({ answers: answers || {} })
    }),

  /** 向导答案 → 正式 Spec */
  compile: (answers, { enrich = true } = {}) =>
    request('/designer/compile', {
      method: 'POST',
      body: JSON.stringify({ answers: answers || {}, enrich })
    }),

  /** 定稿冻结 */
  finalize: (spec) =>
    request('/designer/finalize', {
      method: 'POST',
      body: JSON.stringify({ spec })
    }),

  /** 当前生效 Spec（未定稿时后端返回空 payload） */
  activeSpec: () => request('/designer/spec'),

  /** 逃生舱：换一套方案 */
  reset: () => request('/designer/reset', { method: 'POST' })
}

export default designerApi
