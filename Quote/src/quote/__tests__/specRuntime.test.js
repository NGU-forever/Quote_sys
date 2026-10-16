import test from 'node:test';
import assert from 'node:assert/strict';

import {
  applyIntent,
  buildRuntimeBundle,
  buildRuntimeItems,
  isDeviceCategory,
  resolveBlockIntent,
} from '../specRuntime.js';

const DEVICE = { id: 1, sku_id: 'P001', name: '超声诊断仪', category: 'device', min_price: 2500 };
const CONSUMABLE = { id: 2, sku_id: 'C001', name: '超声贴片', category: 'consumable', min_price: 2 };

const BASE = {
  device: DEVICE,
  devicePrice: 2500,
  devices: 2,
  consumable: CONSUMABLE,
  consumableBoxPrice: 100,
  boxes: 10,
  purchaseMode: 'both',
};

// --------------------------------------------------------------------------
// store → items
// --------------------------------------------------------------------------

test('buildRuntimeItems 派生设备行与耗材行，金额口径与 store 一致', () => {
  const items = buildRuntimeItems(BASE);
  assert.equal(items.length, 2);

  const [device, consumable] = items;
  assert.equal(device.kind, 'device');
  assert.equal(device.name, '超声诊断仪');
  assert.equal(device.unit, '台');
  assert.equal(device.qty, 2);
  assert.equal(device.subtotal, 5000); // 2 台 × 2500

  assert.equal(consumable.kind, 'consumable');
  assert.equal(consumable.unit, '箱');
  assert.equal(consumable.qty, 10);
  assert.equal(consumable.subtotal, 1000); // 10 箱 × 100

  // 两行合计即方案一总价
  assert.equal(
    items.reduce((sum, item) => sum + item.subtotal, 0),
    device.subtotal + consumable.subtotal
  );
});

test('buildRuntimeItems 尊重采购模式', () => {
  assert.equal(buildRuntimeItems({ ...BASE, purchaseMode: 'consumables' }).length, 1);
  assert.equal(buildRuntimeItems({ ...BASE, purchaseMode: 'consumables' })[0].kind, 'consumable');
  assert.equal(buildRuntimeItems({ ...BASE, purchaseMode: 'equipment' }).length, 1);
  assert.equal(buildRuntimeItems({ ...BASE, purchaseMode: 'equipment' })[0].kind, 'device');
});

test('buildRuntimeItems 底价校验：低于底价才标 warn', () => {
  const ok = buildRuntimeItems({ ...BASE, consumableBoxPrice: 3 })[1];
  assert.equal(ok.floor_status, 'ok');

  const warn = buildRuntimeItems({ ...BASE, consumableBoxPrice: 1 })[1];
  assert.equal(warn.floor_status, 'warn');
  assert.equal(warn.floor_price, 2);

  // 未登记底价时不做判定
  const noFloor = buildRuntimeItems({
    ...BASE,
    device: { ...DEVICE, min_price: null },
  })[0];
  assert.equal(noFloor.floor_status, 'ok');
});

test('buildRuntimeItems 未选设备/耗材时返回空清单', () => {
  assert.deepEqual(buildRuntimeItems({}), []);
  assert.deepEqual(buildRuntimeItems({ device: null, consumable: null, purchaseMode: 'both' }), []);
});

// --------------------------------------------------------------------------
// store → bundle
// --------------------------------------------------------------------------

test('buildRuntimeBundle 无方案时返回 null（区块自动隐藏）', () => {
  assert.equal(buildRuntimeBundle(null), null);
  assert.equal(buildRuntimeBundle({}), null);
  assert.equal(buildRuntimeBundle({ pkg: null }), null);
});

test('buildRuntimeBundle 映射套餐名称、备注与节省额', () => {
  const bundle = buildRuntimeBundle({
    planNo: 2,
    saving: 520,
    pkg: { id: 'pkg-1', name: '台式超声推广套餐', note: '含主机 1 台 + 耗材 2 袋', fixedBundle: false },
  });
  assert.equal(bundle.name, '台式超声推广套餐');
  assert.equal(bundle.note, '含主机 1 台 + 耗材 2 袋');
  assert.equal(bundle.saving_amount, 520);
  assert.equal(bundle.planNo, 2);
  assert.equal(bundle.pkg.id, 'pkg-1');
});

// --------------------------------------------------------------------------
// 区块事件 → store 意图
// --------------------------------------------------------------------------

test('add-item 按类目分流到设备/耗材；参数非法返回 null', () => {
  assert.deepEqual(resolveBlockIntent('add-item', DEVICE, []), {
    action: 'selectProduct',
    kind: 'device',
    id: 1,
    name: '超声诊断仪',
  });
  assert.equal(resolveBlockIntent('add-item', CONSUMABLE, []).kind, 'consumable');
  // hardware 视同设备
  assert.equal(
    resolveBlockIntent('add-item', { id: 9, category: 'hardware', name: '工控机' }, []).kind,
    'device'
  );
  assert.equal(resolveBlockIntent('add-item', null, []), null);
  assert.equal(resolveBlockIntent('add-item', { name: '没有 id' }, []), null);
});

test('update-qty 按行类型落到 setDevices / setBoxes', () => {
  const items = buildRuntimeItems(BASE);

  assert.deepEqual(resolveBlockIntent('update-qty', { index: 0, qty: 3 }, items), {
    action: 'setDevices',
    value: 3,
  });
  assert.deepEqual(resolveBlockIntent('update-qty', { index: 1, qty: 25 }, items), {
    action: 'setBoxes',
    value: 25,
  });
});

test('update-qty 对越界行与非法数量返回 null', () => {
  const items = buildRuntimeItems(BASE);
  assert.equal(resolveBlockIntent('update-qty', { index: 9, qty: 3 }, items), null);
  assert.equal(resolveBlockIntent('update-qty', { index: -1, qty: 3 }, items), null);
  assert.equal(resolveBlockIntent('update-qty', { index: 0, qty: -1 }, items), null);
  assert.equal(resolveBlockIntent('update-qty', { index: 0, qty: 'abc' }, items), null);
});

test('remove-item 翻译成采购模式切换（计价模型没有删行）', () => {
  const items = buildRuntimeItems(BASE);
  assert.deepEqual(resolveBlockIntent('remove-item', 0, items), {
    action: 'removeRow',
    kind: 'device',
  });
  assert.deepEqual(resolveBlockIntent('remove-item', 1, items), {
    action: 'removeRow',
    kind: 'consumable',
  });
  assert.equal(resolveBlockIntent('remove-item', 5, items), null);
});

test('apply-bundle 带出套餐 id 与是否固定整购', () => {
  assert.deepEqual(
    resolveBlockIntent('apply-bundle', { pkg: { id: 'pkg-1', name: '整购套餐', fixedBundle: true } }),
    { action: 'applyBundle', packageId: 'pkg-1', fixedBundle: true, name: '整购套餐' }
  );
  assert.deepEqual(
    resolveBlockIntent('apply-bundle', { pkg: { id: 'pkg-2', name: '赠机套餐' } }),
    { action: 'applyBundle', packageId: 'pkg-2', fixedBundle: false, name: '赠机套餐' }
  );
  assert.equal(resolveBlockIntent('apply-bundle', {}, []), null);
  assert.equal(resolveBlockIntent('apply-bundle', null, []), null);
});

test('未知事件返回 null，不误触发任何 store 动作', () => {
  assert.equal(resolveBlockIntent('print-a4', null, []), null);
  assert.equal(resolveBlockIntent('save-draft', null, []), null);
  assert.equal(resolveBlockIntent('不存在的动作', {}, []), null);
});

test('isDeviceCategory 覆盖 device 与 hardware', () => {
  assert.equal(isDeviceCategory('device'), true);
  assert.equal(isDeviceCategory('hardware'), true);
  assert.equal(isDeviceCategory('consumable'), false);
  assert.equal(isDeviceCategory(undefined), false);
});

// --------------------------------------------------------------------------
// 意图 → store 调用（用假 store 断言"到底调了哪个动作"）
// --------------------------------------------------------------------------

function fakeDeps() {
  const calls = [];
  const record =
    (name) =>
    (...args) =>
      calls.push([name, ...args]);
  return {
    calls,
    store: {
      setDevices: record('setDevices'),
      setBoxes: record('setBoxes'),
      setPurchaseMode: record('setPurchaseMode'),
      selectPackage: record('selectPackage'),
    },
    catalog: {
      selectDevice: record('selectDevice'),
      selectConsumable: record('selectConsumable'),
    },
  };
}

test('applyIntent: add-item 落到目录的选中动作', () => {
  const device = fakeDeps();
  applyIntent(resolveBlockIntent('add-item', DEVICE, []), device);
  assert.deepEqual(device.calls, [['selectDevice', 1]]);

  const consumable = fakeDeps();
  applyIntent(resolveBlockIntent('add-item', CONSUMABLE, []), consumable);
  assert.deepEqual(consumable.calls, [['selectConsumable', 2]]);
});

test('applyIntent: update-qty 落到 setDevices / setBoxes', () => {
  const items = buildRuntimeItems(BASE);

  const device = fakeDeps();
  applyIntent(resolveBlockIntent('update-qty', { index: 0, qty: 3 }, items), device);
  assert.deepEqual(device.calls, [['setDevices', 3]]);

  const consumable = fakeDeps();
  applyIntent(resolveBlockIntent('update-qty', { index: 1, qty: 25 }, items), consumable);
  assert.deepEqual(consumable.calls, [['setBoxes', 25]]);
});

test('applyIntent: 耗材数量填 0 时切纯设备模式，而不是调 setBoxes', () => {
  const items = buildRuntimeItems(BASE);
  const deps = fakeDeps();
  applyIntent(resolveBlockIntent('update-qty', { index: 1, qty: 0 }, items), deps);
  assert.deepEqual(deps.calls, [['setPurchaseMode', 'equipment']]);
});

test('applyIntent: remove-item 切换采购模式', () => {
  const items = buildRuntimeItems(BASE);

  const device = fakeDeps();
  applyIntent(resolveBlockIntent('remove-item', 0, items), device);
  assert.deepEqual(device.calls, [
    ['setDevices', 0],
    ['setPurchaseMode', 'consumables'],
  ]);

  const consumable = fakeDeps();
  applyIntent(resolveBlockIntent('remove-item', 1, items), consumable);
  assert.deepEqual(consumable.calls, [['setPurchaseMode', 'equipment']]);
});

test('applyIntent: 固定整购套餐才切 package 模式并选套餐', () => {
  const fixed = fakeDeps();
  applyIntent(
    resolveBlockIntent('apply-bundle', { pkg: { id: 'pkg-1', name: '整购套餐', fixedBundle: true } }),
    fixed
  );
  assert.deepEqual(fixed.calls, [
    ['setPurchaseMode', 'package'],
    ['selectPackage', 'pkg-1'],
  ]);

  const gift = fakeDeps();
  applyIntent(
    resolveBlockIntent('apply-bundle', { pkg: { id: 'pkg-2', name: '赠机套餐' } }),
    gift
  );
  assert.deepEqual(gift.calls, [['setPurchaseMode', 'both']]);
});

test('applyIntent: 通知文案带上商品/套餐名', () => {
  const messages = [];
  const deps = { ...fakeDeps(), notify: (message, type) => messages.push([message, type]) };

  applyIntent(resolveBlockIntent('add-item', DEVICE, []), deps);
  applyIntent(
    resolveBlockIntent('apply-bundle', { pkg: { id: 'pkg-1', name: '整购套餐', fixedBundle: true } }),
    deps
  );

  assert.deepEqual(messages, [
    ['已加入设备：超声诊断仪', 'info'],
    ['已选用套餐：整购套餐', 'success'],
  ]);
});

test('applyIntent: 缺 store/catalog 或 intent 为 null 时安全返回 false', () => {
  assert.equal(applyIntent(null, fakeDeps()), false);
  assert.equal(applyIntent({ action: 'setDevices', value: 1 }, {}), false);
  assert.equal(applyIntent({ action: 'setDevices', value: 1 }, { store: {} }), false);
  assert.equal(applyIntent({ action: '未知动作' }, fakeDeps()), false);
  assert.doesNotThrow(() => applyIntent({ action: 'setDevices', value: 1 }, { store: null }));
});
