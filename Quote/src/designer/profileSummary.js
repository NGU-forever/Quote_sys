/**
 * 第 8 屏人话摘要的取值与降级。
 *
 * 摘要的**唯一权威来源是后端** `POST /api/designer/profile`（它会带入库内画像、
 * 资料术语口径与可选的模型判断）。这里只做三件事：
 * 1. 把后端响应解释成界面需要的字段；
 * 2. 后端不可达/未登录时的**降级兜底文案**（设计文档 §2 D3：不配 Key 也必须可用）；
 * 3. 把资料术语线索翻成人话提示。
 *
 * 兜底文案必须与后端 `app/designer/compiler.py::generate_summary_text` 保持同构，
 * 否则降级时用户会看到与正式定稿不一样的描述。
 */

// 枚举码 → 人话（与后端 generate_summary_text 的映射表一一对应）
const SCENE_LABELS = {
  on_site: '客户现场',
  office: '办公室电脑',
  mobile: '手机移动端'
}

const PRICING_LABELS = {
  floor_price: '按底价卖不议价',
  negotiable: '允许折让但超限需审批',
  tiered: '按批发数量自动阶梯价',
  bundle_fixed: '按套餐一口价'
}

const OUTPUT_LABELS = {
  print_a4: '打印 A4 纸质',
  pdf: '高品质 PDF',
  screen: '屏幕演示'
}

const ROLE_LABELS = { admin: '老板', sales: '销售', manager: '主管' }

function localize(code, labels, fallback) {
  if (!code) return fallback
  return labels[String(code)] || String(code)
}

/** 后端不可达时的降级摘要；与后端模板同构。 */
export function buildLocalSummary(answers = {}) {
  const ans = answers || {}
  const roles = Array.isArray(ans.roles)
    ? ans.roles.map((role) => ROLE_LABELS[String(role)] || String(role)).join('、')
    : ans.roles
  return (
    `我理解你是：向${ans.industry || '客户'}销售${ans.category_name || '主要商品'}` +
    `${ans.has_consumables ? '、配套耗材' : ''}，` +
    `${roles || '销售'}在${localize(ans.scene, SCENE_LABELS, '客户现场')}开单，` +
    `${localize(ans.pricing_mode, PRICING_LABELS, '按底价卖不议价')}` +
    `${ans.require_approval === true ? '、破价需要审批' : ''}，` +
    `报价单${localize(ans.output_target, OUTPUT_LABELS, '打印 A4')}给客户，` +
    `主色用${ans.brand_color_name || '你的品牌蓝'}。`
  )
}

/** 资料术语线索 → 一句人话提示；没有线索时返回空串。 */
export function describeTerminologyHint(digest = {}) {
  const hints = (digest || {}).terminology_hints || {}
  const parts = []
  if (hints.price_term) {
    parts.push(`资料里用的是「${hints.price_term}」口径，界面标签会沿用你的叫法`)
  }
  if (hints.promo_tone) {
    parts.push('资料里出现促销语气，套餐区块会展示"省 ¥X"')
  }
  return parts.length ? `${parts.join('；')}。` : ''
}

/**
 * 解释 `/designer/profile` 响应。
 *
 * 后端不可用时（payload 为 null / 无 summary_text）返回降级结果，
 * 并标记 source='local'，让界面能明确告诉用户"这是本地兜底文案"。
 */
export function interpretProfileResponse(payload, answers = {}) {
  const data = payload || {}
  const hasBackendSummary = typeof data.summary_text === 'string' && data.summary_text.trim() !== ''
  return {
    summaryText: hasBackendSummary ? data.summary_text : buildLocalSummary(answers),
    source: hasBackendSummary ? 'backend' : 'local',
    llmEnabled: Boolean(data.llm_enabled),
    issues: Array.isArray(data.issues) ? data.issues : [],
    terminologyHint: describeTerminologyHint(data.digest)
  }
}

/** 把后端/网络错误翻成用户能照着做的中文。 */
export function describeDesignerError(error) {
  const message = String((error && error.message) || error || '')
  if (message.includes('401') || message.includes('未登录')) {
    return '需要以管理员身份登录工作台后，才能生成或定稿报价系统设计。'
  }
  if (message.includes('403') || message.includes('管理员')) {
    return '当前账号不是管理员，无法修改报价系统设计。'
  }
  return message || '无法连接后端服务，请确认工作台已启动。'
}
