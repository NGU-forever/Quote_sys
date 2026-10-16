import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildLocalSummary,
  describeDesignerError,
  describeTerminologyHint,
  interpretProfileResponse,
} from '../profileSummary.js';

const ANSWERS = {
  industry: '医疗设备',
  category_name: '主要设备与配件',
  has_consumables: true,
  roles: ['admin', 'sales'],
  scene: 'on_site',
  pricing_mode: 'floor_price',
  require_approval: false,
  output_target: 'print_a4',
  brand_color_name: '品牌科技蓝',
};

test('buildLocalSummary 输出人话，不含枚举码', () => {
  const summary = buildLocalSummary(ANSWERS);
  assert.match(summary, /^我理解你是：/);
  assert.ok(summary.includes('医疗设备'));
  assert.ok(summary.includes('老板、销售'));
  assert.ok(summary.includes('客户现场'));
  assert.ok(summary.includes('按底价卖不议价'));
  assert.ok(summary.includes('打印 A4'));
  assert.ok(!summary.includes('破价需要审批'));
  for (const code of ['on_site', 'floor_price', 'print_a4', 'admin', 'sales']) {
    assert.ok(!summary.includes(code), `不应出现枚举码 ${code}`);
  }
});

test('buildLocalSummary 在答案缺项时仍给出完整句子', () => {
  const summary = buildLocalSummary({});
  assert.match(summary, /^我理解你是：向客户销售主要商品/);
  assert.ok(!summary.includes('undefined'));
});

test('interpretProfileResponse 优先采用后端摘要', () => {
  const result = interpretProfileResponse(
    {
      summary_text: '我理解你是：向医疗机构销售影像设备。',
      llm_enabled: true,
      issues: ['资料里没有套餐依据'],
      digest: { terminology_hints: { price_term: '供货价', promo_tone: true } },
    },
    ANSWERS
  );
  assert.equal(result.source, 'backend');
  assert.equal(result.summaryText, '我理解你是：向医疗机构销售影像设备。');
  assert.equal(result.llmEnabled, true);
  assert.deepEqual(result.issues, ['资料里没有套餐依据']);
  assert.ok(result.terminologyHint.includes('供货价'));
  assert.ok(result.terminologyHint.includes('省 ¥X'));
});

test('interpretProfileResponse 后端不可用时退回本地兜底', () => {
  const result = interpretProfileResponse(null, ANSWERS);
  assert.equal(result.source, 'local');
  assert.equal(result.llmEnabled, false);
  assert.deepEqual(result.issues, []);
  assert.equal(result.terminologyHint, '');
  assert.ok(result.summaryText.includes('客户现场'));
});

test('interpretProfileResponse 空 summary_text 视为未取到', () => {
  const result = interpretProfileResponse({ summary_text: '   ' }, ANSWERS);
  assert.equal(result.source, 'local');
  assert.ok(result.summaryText.includes('医疗设备'));
});

test('describeTerminologyHint 无线索时返回空串', () => {
  assert.equal(describeTerminologyHint({}), '');
  assert.equal(describeTerminologyHint({ terminology_hints: {} }), '');
  assert.ok(describeTerminologyHint({ terminology_hints: { price_term: '同行价' } }).includes('同行价'));
});

test('describeDesignerError 把鉴权失败翻成可照做的中文', () => {
  assert.ok(describeDesignerError(new Error('未登录或登录已过期')).includes('管理员身份登录'));
  assert.ok(describeDesignerError(new Error('需要管理员权限')).includes('不是管理员'));
  assert.ok(describeDesignerError(new Error('无法连接后端服务')).includes('无法连接后端服务'));
  assert.ok(describeDesignerError(null).length > 0);
});
