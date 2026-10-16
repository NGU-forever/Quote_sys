/**
 * 黄金屏种子数据：固定不变，保证截图基准可复现。
 * 覆盖排版极端情况：超长名称、无图、无价格、破底价明细。
 */

export const SEED_PRODUCTS = [
  {
    sku_id: 'P001',
    name: '超声波治疗仪CSY-200（台式）',
    category: 'device',
    unit: '台',
    min_price: 2500,
    price_display: '¥2,500.00',
    has_image: false,
  },
  {
    sku_id: 'P002',
    name: '医用高频电刀多功能手术切割主机配备双脚踏开关与多组一次性电极接口的加强型设备',
    category: 'device',
    unit: '套',
    min_price: 42800,
    price_display: '¥42,800.00',
    has_image: false,
  },
  {
    sku_id: 'C001',
    name: '超声贴片',
    category: 'consumable',
    unit: '袋',
    min_price: 2,
    price_display: '¥2.00',
    has_image: false,
  },
  {
    sku_id: 'C002',
    name: '耦合剂',
    category: 'consumable',
    unit: '瓶',
    min_price: null,
    price_display: '面议',
    has_image: false,
  },
  {
    sku_id: 'C003',
    name: '一次性医用高分子导丝耗材',
    category: 'consumable',
    unit: '根',
    min_price: 25,
    price_display: '¥25.00',
    has_image: false,
  },
  {
    sku_id: 'P003',
    name: '便携式心电监护仪(八导联)',
    category: 'device',
    unit: '台',
    min_price: 12800,
    price_display: '¥12,800.00',
    has_image: false,
  },
];

export const SEED_ITEMS = [
  {
    sku_id: 'P001',
    name: '超声波治疗仪CSY-200（台式）',
    unit: '台',
    unit_price: 2875,
    floor_price: 2500,
    qty: 1,
    floor_status: 'ok',
  },
  {
    sku_id: 'C001',
    name: '超声贴片',
    unit: '袋',
    unit_price: 1.7,
    floor_price: 2,
    qty: 100,
    floor_status: 'warn',
  },
];

export const SEED_BUNDLE = {
  package_id: 'PKG001',
  name: '台式超声推广套餐',
  std_price: 6000,
  discount_price: 5480,
  saving_amount: 520,
  note: '含主机 1 台 + 耗材 2 袋',
};

export const SEED_QUOTE = {
  quote_no: 'QT-20261013-0001',
  customer_name: '某某医院',
  sales_name: '销售A',
};

export const SEED_COMPANY = { name: '某某医疗科技有限公司', logo: '' };

export const SKELETONS = [
  'catalog-left-form-right',
  'form-first-wizard',
  'list-detail-split',
  'dashboard-grid',
  'mobile-single-column',
];

export const PRESETS = ['medical-clean', 'industrial-dense', 'brand-premium'];

const BLOCKS_BY_SKELETON = {
  'catalog-left-form-right': [
    { type: 'customer_info', props: { fields: ['customer_name', 'customer_phone'] } },
    { type: 'quote_meta', props: { valid_days: 30 } },
    { type: 'item_picker', props: {} },
    { type: 'item_table_editable', props: {} },
    { type: 'bundle_suggestion', props: { max_items: 1, show_saving: true } },
    { type: 'floor_price_alert', props: {} },
    { type: 'price_summary', props: { show_tax: false } },
    { type: 'export_actions', props: { actions: ['save_draft', 'print_a4'] } },
  ],
  'form-first-wizard': [
    { type: 'quote_meta', props: { valid_days: 30 } },
    { type: 'customer_info', props: {} },
    { type: 'item_picker', props: {} },
    { type: 'item_table_editable', props: {} },
    { type: 'discount_panel', props: { max_discount: 0.95 } },
    { type: 'notes_and_terms', props: {} },
    { type: 'approval_status', props: {} },
    { type: 'floor_price_alert', props: {} },
    { type: 'price_summary', props: {} },
    { type: 'export_actions', props: {} },
  ],
  'list-detail-split': [
    { type: 'customer_info', props: {} },
    { type: 'item_table_readonly', props: {} },
    { type: 'quote_meta', props: {} },
    { type: 'approval_status', props: {} },
    { type: 'activity_timeline', props: { max_items: 3 } },
    { type: 'price_summary', props: {} },
    { type: 'export_actions', props: {} },
  ],
  'dashboard-grid': [
    { type: 'stats_cards', props: {} },
    { type: 'recent_quotes', props: { max_items: 3 } },
    { type: 'approval_status', props: {} },
    { type: 'activity_timeline', props: { max_items: 3 } },
  ],
  'mobile-single-column': [
    { type: 'customer_info', props: {} },
    { type: 'item_picker', props: {} },
    { type: 'item_table_editable', props: {} },
    { type: 'floor_price_alert', props: {} },
    { type: 'price_summary', props: { sticky: true } },
  ],
};

const DENSITY_BY_PRESET = {
  'medical-clean': 'comfortable',
  'industrial-dense': 'compact',
  'brand-premium': 'spacious',
};

const TABLE_BY_PRESET = {
  'medical-clean': 'bordered',
  'industrial-dense': 'striped',
  'brand-premium': 'minimal',
};

export function buildSpec(skeleton, presetId) {
  return {
    spec_version: 1,
    meta: { generator: 'visual-harness', source_level: 'sample' },
    profile: {
      industry: 'medical',
      sell_mode: 'device_with_consumable',
      scene: 'on_site',
      roles: ['admin', 'sales'],
      pricing_mode: 'floor_price',
      output_targets: ['print_a4'],
    },
    style: { preset_id: presetId, density: DENSITY_BY_PRESET[presetId] || 'comfortable' },
    modules: ['catalog', 'quote_editor', 'quotes', 'employees', 'settings'],
    nav: [
      { id: 'quote_editor', label: '开单', route: '/quote/new', icon: 'edit' },
      { id: 'quotes', label: '报价单', route: '/quotes', icon: 'file' },
    ],
    screens: [
      {
        id: 'quote_editor',
        skeleton,
        blocks: BLOCKS_BY_SKELETON[skeleton] || BLOCKS_BY_SKELETON['catalog-left-form-right'],
      },
    ],
    entities: {
      product: {
        list_columns: ['sku_id', 'name', 'category', 'min_price', 'unit'],
        filters: ['category', 'keyword'],
        labels: { min_price: '最低底价' },
      },
      quote: {
        list_columns: ['quote_no', 'customer_name', 'final_quote_price', 'created_at'],
        labels: { quote_no: '单号', customer_name: '客户' },
      },
    },
    output: {
      quote_pdf: {
        paper: 'A4',
        header_style: 'logo_left_company_right',
        table_style: TABLE_BY_PRESET[presetId] || 'bordered',
        show_floor_price: false,
        terms_block: 'company_default',
      },
    },
    rules: {
      price_floor_guard: true,
      bundle_validation: true,
      quote_no_pattern: 'QT-{YYYYMMDD}-{0001}',
      price_visibility: 'internal',
      approval_required: skeleton === 'form-first-wizard',
    },
  };
}

export const SEED_DATA = {
  products: SEED_PRODUCTS,
  items: SEED_ITEMS,
  bundle: SEED_BUNDLE,
  quote: SEED_QUOTE,
  company: SEED_COMPANY,
};
