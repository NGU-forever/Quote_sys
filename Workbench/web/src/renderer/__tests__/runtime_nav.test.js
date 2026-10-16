import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getNavItems,
  getScreenById,
  getScreens,
  resolveActiveScreenId,
} from '../runtimeNav.js';
import { loadAndNormalizeSpec } from '../SpecLoader.js';

const SPEC = {
  spec_version: 1,
  modules: ['catalog', 'quote_editor', 'quotes'],
  nav: [
    { id: 'quote_editor', label: '开单', route: '/quote/new', icon: 'edit' },
    { id: 'quotes', label: '报价单', route: '/quotes', icon: 'file' },
    { id: 'catalog', label: '商品目录', route: '/catalog', icon: 'box' },
  ],
  screens: [
    { id: 'quote_editor', skeleton: 'catalog-left-form-right', blocks: [] },
    { id: 'quotes', skeleton: 'dashboard-grid', blocks: [] },
    { id: 'catalog', skeleton: 'list-detail-split', blocks: [] },
  ],
};

test('getNavItems 采用 Spec 声明的 nav（保持顺序）', () => {
  const items = getNavItems(SPEC);
  assert.deepEqual(
    items.map((item) => item.id),
    ['quote_editor', 'quotes', 'catalog']
  );
  assert.equal(items[0].label, '开单');
  assert.equal(items[0].route, '/quote/new');
});

test('getNavItems 剔除没有目标屏幕的死链', () => {
  const spec = {
    ...SPEC,
    nav: [
      { id: 'quote_editor', label: '开单' },
      { id: 'ghost_screen', label: '不存在的屏' },
    ],
  };
  assert.deepEqual(
    getNavItems(spec).map((item) => item.id),
    ['quote_editor']
  );
});

test('getNavItems 生效 modules 开关：未启用模块的屏幕不进导航', () => {
  const spec = { ...SPEC, modules: ['quote_editor'] };
  assert.deepEqual(
    getNavItems(spec).map((item) => item.id),
    ['quote_editor']
  );
});

test('getNavItems 在缺少 nav 时由 screens 派生', () => {
  const spec = { ...SPEC, nav: undefined };
  const items = getNavItems(spec);
  assert.deepEqual(
    items.map((item) => item.id),
    ['quote_editor', 'quotes', 'catalog']
  );
  // 由屏幕派生时用兜底标签，不再是裸露的 id
  assert.equal(items[1].label, '报价单');
});

test('getNavItems 在缺少 modules 时不做过滤（不误关屏幕）', () => {
  const spec = { ...SPEC, modules: undefined };
  assert.equal(getNavItems(spec).length, 3);
});

test('getNavItems 对空 Spec 安全降级', () => {
  assert.deepEqual(getNavItems(null), []);
  assert.deepEqual(getNavItems({}), []);
});

test('resolveActiveScreenId 回退到第一屏', () => {
  assert.equal(resolveActiveScreenId(SPEC, 'quotes'), 'quotes');
  assert.equal(resolveActiveScreenId(SPEC, 'ghost'), 'quote_editor');
  assert.equal(resolveActiveScreenId(SPEC), 'quote_editor');
  assert.equal(resolveActiveScreenId({ screens: [] }), null);
});

test('getScreens / getScreenById 过滤非法屏幕', () => {
  const spec = { screens: [{ id: 'a' }, null, { skeleton: 'x' }, { id: 'b' }] };
  assert.deepEqual(
    getScreens(spec).map((screen) => screen.id),
    ['a', 'b']
  );
  assert.equal(getScreenById(spec, 'b').id, 'b');
  assert.equal(getScreenById(spec, 'ghost').id, 'a');
});

test('loadAndNormalizeSpec 归一化 nav 与 modules', () => {
  const spec = loadAndNormalizeSpec({
    screens: [
      { id: 'quote_editor', skeleton: 'catalog-left-form-right', blocks: [] },
      { id: 'quotes', skeleton: 'dashboard-grid', blocks: [] },
    ],
  });
  // 没声明 modules 时以屏幕为准，而不是被默认模块列表误关
  assert.deepEqual(spec.modules, ['quote_editor', 'quotes']);
  assert.deepEqual(
    spec.nav.map((item) => item.id),
    ['quote_editor', 'quotes']
  );
});

test('loadAndNormalizeSpec 剔除 nav 里的死链', () => {
  const spec = loadAndNormalizeSpec({
    modules: ['quote_editor', 'quotes'],
    nav: [
      { id: 'quote_editor', label: '开单' },
      { id: 'quotes', label: '报价单' },
      { id: 'settings', label: '系统设置' },
    ],
    screens: [{ id: 'quote_editor', skeleton: 'catalog-left-form-right', blocks: [] }],
  });
  assert.deepEqual(
    spec.nav.map((item) => item.id),
    ['quote_editor']
  );
});
