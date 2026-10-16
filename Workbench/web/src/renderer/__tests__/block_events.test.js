import test from 'node:test';
import assert from 'node:assert/strict';

import { blockEventsFor, listenersFor, toHandlerName } from '../blockEvents.js';

test('kebab-case 事件名换算成 camelCase 监听名', () => {
  assert.equal(toHandlerName('add-item'), 'onAddItem');
  assert.equal(toHandlerName('update-qty'), 'onUpdateQty');
  assert.equal(toHandlerName('remove-item'), 'onRemoveItem');
  assert.equal(toHandlerName('apply-bundle'), 'onApplyBundle');
  assert.equal(toHandlerName('save-draft'), 'onSaveDraft');
  // 带数字后缀的最容易写错
  assert.equal(toHandlerName('print-a4'), 'onPrintA4');
  assert.equal(toHandlerName('export-pdf'), 'onExportPdf');
});

test('每个区块只挂自己支持的事件', () => {
  assert.deepEqual(blockEventsFor('item_picker'), ['add-item']);
  assert.deepEqual(blockEventsFor('item_table_editable'), ['update-qty', 'remove-item']);
  assert.deepEqual(blockEventsFor('bundle_suggestion'), ['apply-bundle']);
  assert.deepEqual(blockEventsFor('export_actions'), ['save-draft', 'print-a4', 'export-pdf']);
  // 纯展示区块不挂任何监听
  assert.deepEqual(blockEventsFor('price_summary'), []);
  assert.deepEqual(blockEventsFor('stats_cards'), []);
  assert.deepEqual(blockEventsFor(undefined), []);
});

test('listenersFor 组装的监听会带回事件名与载荷', () => {
  const seen = [];
  const emit = (name, payload) => seen.push([name, payload]);
  const handlers = listenersFor('item_table_editable', emit);

  assert.deepEqual(Object.keys(handlers), ['onUpdateQty', 'onRemoveItem']);
  handlers.onUpdateQty({ index: 1, qty: 5 });
  handlers.onRemoveItem(0);

  assert.deepEqual(seen, [
    ['update-qty', { index: 1, qty: 5 }],
    ['remove-item', 0],
  ]);
});

test('listenersFor 对纯展示区块返回空监听，不误挂事件', () => {
  const handlers = listenersFor('customer_info', () => {});
  assert.deepEqual(handlers, {});
});
