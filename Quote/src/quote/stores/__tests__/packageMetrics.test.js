import test from 'node:test';
import assert from 'node:assert/strict';

import {
  boxCount,
  packageItems,
  packageUnitMetrics,
  toNumber,
} from '../packageMetrics.js';

const CATALOG = {
  productById: (id) => (Number(id) === 9 ? { bagsPerBox: 5 } : null),
};

const ITEMS = [
  { productId: 1, category: 'device', quantity: 2 },
  { productId: 2, category: 'consumable', quantity: 10, bagsPerBox: 5 },
  { productId: 3, category: 'consumable', quantity: 4, bagsPerBox: 4 },
];

test('packageUnitMetrics 修复了未定义 items 导致的崩溃（回归）', () => {
  // 修复前 store 内的实现引用了自由变量 items，只要命中套餐就抛 ReferenceError。
  assert.equal(packageUnitMetrics.length, 4);
  assert.doesNotThrow(() => packageUnitMetrics({}, [], null, null));
});

test('固定整购套餐：累加全部耗材行，按选中设备取台数', () => {
  const pkg = { fixedBundle: true, price: 1000, deviceQty: 1, consumableQty: 20, consumableBoxes: 2 };
  const metrics = packageUnitMetrics(pkg, ITEMS, 1, 2);
  assert.equal(metrics.deviceQtyPerSet, 2);
  assert.equal(metrics.consumableQtyPerSet, 14);
  // 10/5 + 4/4 = 3 箱
  assert.equal(metrics.consumableBoxesPerSet, 3);
});

test('赠机/推广套餐：耗材只取当前选中的那一行，避免重复相加', () => {
  const pkg = { fixedBundle: false, price: 500 };
  const metrics = packageUnitMetrics(pkg, ITEMS, 1, 3);
  assert.equal(metrics.deviceQtyPerSet, 2);
  assert.equal(metrics.consumableQtyPerSet, 4);
  assert.equal(metrics.consumableBoxesPerSet, 1);
});

test('设备未命中选中 ID 时退回第一台设备', () => {
  const pkg = { fixedBundle: false };
  const metrics = packageUnitMetrics(pkg, ITEMS, 999, 2);
  assert.equal(metrics.deviceQtyPerSet, 2);
});

test('无明细行时退回套餐自身的数量字段', () => {
  const pkg = { deviceQty: 1, consumableQty: 20, consumableBoxes: 3 };
  assert.deepEqual(packageUnitMetrics(pkg, [], null, null), {
    deviceQtyPerSet: 1,
    consumableQtyPerSet: 20,
    consumableBoxesPerSet: 3,
  });
});

test('数量全为 0/缺失时统一返回 null，交由上层判定方案无效', () => {
  const pkg = { deviceQty: 0, consumableQty: 0, consumableBoxes: 0 };
  assert.deepEqual(packageUnitMetrics(pkg, [], null, null), {
    deviceQtyPerSet: null,
    consumableQtyPerSet: null,
    consumableBoxesPerSet: null,
  });
  assert.deepEqual(packageUnitMetrics({}, [], null, null), {
    deviceQtyPerSet: null,
    consumableQtyPerSet: null,
    consumableBoxesPerSet: null,
  });
});

test('packageItems 优先使用后端同步的 items', () => {
  const pkg = { items: ITEMS, deviceIds: [1], consumableIds: [2] };
  assert.equal(packageItems(pkg, CATALOG), ITEMS);
});

test('packageItems 兼容旧缓存：无 items 时按一对 SKU 恢复单套组成', () => {
  const pkg = { deviceIds: [7], consumableIds: [9], deviceQty: 1, consumableQty: 20 };
  assert.deepEqual(packageItems(pkg, CATALOG), [
    { productId: 7, category: 'device', quantity: 1 },
    { productId: 9, category: 'consumable', quantity: 20, bagsPerBox: 5 },
  ]);
});

test('packageItems 无法恢复明细时返回空数组', () => {
  assert.deepEqual(packageItems({}, CATALOG), []);
  assert.deepEqual(packageItems({ deviceIds: [1, 2], consumableIds: [3] }, CATALOG), []);
  assert.deepEqual(packageItems(null, CATALOG), []);
});

test('toNumber / boxCount 的边界行为', () => {
  assert.equal(toNumber(''), null);
  assert.equal(toNumber(null), null);
  assert.equal(toNumber(undefined), null);
  assert.equal(toNumber('12'), 12);
  assert.equal(toNumber('abc'), null);
  assert.equal(boxCount(10, 5), 2);
  assert.equal(boxCount(10, 0), null);
  assert.equal(boxCount(0, 5), null);
  assert.equal(boxCount(null, 5), null);
});
