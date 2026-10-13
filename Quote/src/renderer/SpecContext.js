/**
 * SpecContext：把 UiSpec 的 entities / output / rules 注入整棵渲染树。
 *
 * 本文件是纯逻辑（不依赖 vue）；provide/inject 适配层见 SpecProvider.js。
 * 之所以用 provide/inject 而不是逐层传 props：
 * block 是通过通用 `<component :is>` 渲染的，若靠 props 穿透，每个 block 都会
 * 收到一份与自己无关的属性，既容易泄漏到 DOM，也会让 16 个组件全部耦合到宿主。
 *
 * 三块配置的消费口径（对应设计文档 §4.2 / §12）：
 * - entities：列表列集合、筛选项、字段标签（术语本地化结果）
 * - output  ：quote_pdf 打印版式（纸张 / 页眉 / 表格 / 是否显示底价 / 条款）
 * - rules   ：底价保护、报价单号规则、价格可见性、审批要求
 */
/** 字段缺省中文标签；后端 entities.*.labels（术语本地化）优先于它 */
export const DEFAULT_FIELD_LABELS = {
  sku_id: '产品编号',
  name: '名称',
  category: '类别',
  unit: '单位',
  spec: '规格',
  min_price: '最低底价',
  max_price: '最高价',
  box_price: '整箱价',
  price_display: '报价',
  pieces_per_unit: '每箱件数',
  units_per_box: '每箱数量',
  applicable_devices: '适用设备',
  raw_price_desc: '原始口径',
  qty: '数量',
  unit_price: '单价',
  subtotal: '小计',
  floor_check: '底价校验',
  customer_name: '客户名称',
  customer_phone: '联系电话',
  quote_no: '单号',
  sales_name: '业务员',
  created_at: '创建时间',
  total_amount: '合计金额',
};

/** 金额类字段：空值显示"面议"，有值加 ¥ 与千分位 */
const MONEY_FIELDS = new Set([
  'min_price',
  'max_price',
  'box_price',
  'unit_price',
  'subtotal',
  'total_amount',
  'total_list_price',
  'final_quote_price',
  'std_price',
  'discount_price',
]);

/** 数值类字段：右对齐 + 等宽数字 */
const NUMERIC_FIELDS = new Set(['qty', 'pieces_per_unit', 'units_per_box', 'consumable_boxes']);

export const DEFAULT_OUTPUT = {
  paper: 'A4',
  header_style: 'logo_left_company_right',
  table_style: 'bordered',
  show_floor_price: false,
  terms_block: 'company_default',
};

export const DEFAULT_RULES = {
  price_floor_guard: true,
  bundle_validation: true,
  quote_no_pattern: 'QT-{YYYYMMDD}-{0001}',
  price_visibility: 'internal',
  approval_required: false,
};

export function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '面议';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return `¥${num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** 按列定义格式化单元格；面议/空值有明确降级，不出现 null 或空白 */
export function formatCell(column, row) {
  if (!column || !row) return '—';
  const value = row[column.key];
  if (column.money) return formatMoney(value);
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
}

export function formatQuoteNo(pattern, { date = new Date(), seq = 1 } = {}) {
  const text = pattern || DEFAULT_RULES.quote_no_pattern;
  const yyyy = String(date.getFullYear());
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return text
    .replace(/\{YYYYMMDD\}/g, `${yyyy}${mm}${dd}`)
    .replace(/\{YYYY-MM-DD\}/g, `${yyyy}-${mm}-${dd}`)
    .replace(/\{YYYY\}/g, yyyy)
    .replace(/\{MM\}/g, mm)
    .replace(/\{DD\}/g, dd)
    .replace(/\{0*1\}/g, (token) => String(seq).padStart(token.length - 2, '0'))
    .replace(/\{0\d*\}/g, (token) => String(seq).padStart(token.length - 2, '0'));
}

export function createSpecContext(spec) {
  const safeSpec = spec && typeof spec === 'object' ? spec : {};
  const entities = safeSpec.entities && typeof safeSpec.entities === 'object' ? safeSpec.entities : {};
  const rules = { ...DEFAULT_RULES, ...(safeSpec.rules || {}) };
  const output = { quote_pdf: { ...DEFAULT_OUTPUT, ...((safeSpec.output || {}).quote_pdf || {}) } };

  function label(entityName, field) {
    const fromSpec = entities?.[entityName]?.labels?.[field];
    if (fromSpec) return fromSpec;
    return DEFAULT_FIELD_LABELS[field] || field;
  }

  /** 把 entities.<entity>.list_columns 解析成可渲染的列定义 */
  function listColumns(entityName, fallbackKeys = []) {
    const configured = entities?.[entityName]?.list_columns;
    const keys = Array.isArray(configured) && configured.length > 0 ? configured : fallbackKeys;
    return keys.map((key) => column(entityName, key));
  }

  /** 单个字段的列定义（块级 props.columns 走这里拿标签/格式） */
  function column(entityName, key) {
    return {
      key,
      label: label(entityName, key),
      money: MONEY_FIELDS.has(key),
      numeric: NUMERIC_FIELDS.has(key),
    };
  }

  function filters(entityName, fallback = ['keyword']) {
    const configured = entities?.[entityName]?.filters;
    return Array.isArray(configured) && configured.length > 0 ? configured : fallback;
  }

  function rule(name, fallback) {
    const value = rules[name];
    if (value === undefined || value === null) {
      return fallback !== undefined ? fallback : DEFAULT_RULES[name];
    }
    return value;
  }

  return {
    spec: safeSpec,
    entities,
    rules,
    output,
    profile: safeSpec.profile || {},
    label,
    listColumns,
    column,
    filters,
    rule,
    printConfig: output.quote_pdf,
    /** 客户可见的报价单不应展示底价（rules.price_visibility = customer） */
    showsFloorPrice() {
      if (output.quote_pdf.show_floor_price) return true;
      return rule('price_visibility', 'internal') === 'internal';
    },
  };
}
