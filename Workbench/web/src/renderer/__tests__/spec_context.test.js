import test from 'node:test';
import assert from 'node:assert/strict';

import { DEFAULT_FIELD_LABELS, createSpecContext, formatCell, formatMoney, formatQuoteNo } from '../SpecContext.js';

const SPEC = {
  spec_version: 1,
  profile: { industry: 'industrial' },
  style: { preset_id: 'industrial-dense', density: 'compact' },
  entities: {
    product: {
      list_columns: ['sku_id', 'name', 'min_price'],
      labels: { min_price: '供货价' },
      filters: ['category', 'keyword'],
    },
  },
  output: {
    quote_pdf: { paper: 'A5', table_style: 'minimal', show_floor_price: false, terms_block: 'custom terms' },
  },
  rules: { price_floor_guard: false, approval_required: true, price_visibility: 'customer' },
};

test('entities 驱动列集合与术语', () => {
  const ctx = createSpecContext(SPEC);
  const cols = ctx.listColumns('product', ['name']);
  assert.deepEqual(
    cols.map((c) => c.key),
    ['sku_id', 'name', 'min_price']
  );
  // 行业术语覆盖内置默认
  assert.equal(cols[2].label, '供货价');
  assert.equal(cols[2].money, true);
  // 未配置的实体回退到 fallback 与内置标签
  assert.equal(ctx.label('quote', 'quote_no'), DEFAULT_FIELD_LABELS.quote_no);
  assert.deepEqual(ctx.filters('product'), ['category', 'keyword']);
  assert.deepEqual(ctx.filters('quote', ['keyword']), ['keyword']);
});

test('rules 驱动底价保护、审批与价格可见性', () => {
  const ctx = createSpecContext(SPEC);
  assert.equal(ctx.rule('price_floor_guard'), false);
  assert.equal(ctx.rule('approval_required'), true);
  assert.equal(ctx.rule('bundle_validation'), true, '未配置的规则回退默认值');
  // price_visibility = customer 且 output.show_floor_price = false → 不展示底价
  assert.equal(ctx.showsFloorPrice(), false);

  const internal = createSpecContext({ rules: { price_visibility: 'internal' } });
  assert.equal(internal.showsFloorPrice(), true);

  const customerWithPublicFloor = createSpecContext({
    rules: { price_visibility: 'customer' },
    output: { quote_pdf: { show_floor_price: true } },
  });
  assert.equal(customerWithPublicFloor.showsFloorPrice(), true);
});

test('output.quote_pdf 与默认值合并', () => {
  const ctx = createSpecContext(SPEC);
  assert.equal(ctx.printConfig.paper, 'A5');
  assert.equal(ctx.printConfig.table_style, 'minimal');
  assert.equal(ctx.printConfig.header_style, 'logo_left_company_right', '未配置项走默认');
  const empty = createSpecContext({});
  assert.equal(empty.printConfig.paper, 'A4');
  assert.equal(empty.rule('quote_no_pattern'), 'QT-{YYYYMMDD}-{0001}');
});

test('报价单号按 rules.quote_no_pattern 生成', () => {
  const day = new Date(2026, 9, 13);
  assert.equal(formatQuoteNo('QT-{YYYYMMDD}-{0001}', { date: day, seq: 7 }), 'QT-20261013-0007');
  assert.equal(formatQuoteNo('Q-{YYYY}-{MM}-{DD}-{0001}', { date: day, seq: 12 }), 'Q-2026-10-13-0012');
  assert.equal(formatQuoteNo(undefined, { date: day, seq: 1 }), 'QT-20261013-0001');
});

test('单元格格式化：面议与空值都有明确降级', () => {
  assert.equal(formatMoney(1234.5), '¥1,234.50');
  assert.equal(formatMoney(null), '面议');
  assert.equal(formatMoney('面议'), '面议');
  const priceCol = { key: 'min_price', money: true };
  const nameCol = { key: 'name' };
  assert.equal(formatCell(priceCol, { min_price: null }), '面议');
  assert.equal(formatCell(priceCol, { min_price: 2500 }), '¥2,500.00');
  assert.equal(formatCell(nameCol, { name: '' }), '—');
  assert.equal(formatCell(nameCol, {}), '—');
  assert.equal(formatCell(nameCol, { name: '超声仪' }), '超声仪');
});

test('空 spec 不抛异常（防御性降级）', () => {
  const ctx = createSpecContext(null);
  assert.equal(ctx.label('product', 'min_price'), DEFAULT_FIELD_LABELS.min_price);
  assert.deepEqual(ctx.listColumns('product', ['name']).map((c) => c.key), ['name']);
  assert.equal(ctx.rule('price_floor_guard'), true);
  assert.equal(ctx.profile.industry, undefined);
});
