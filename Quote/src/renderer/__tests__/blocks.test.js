import test from 'node:test';
import assert from 'node:assert/strict';

import { ALL_BLOCK_TYPES, isBlockTypeAllowed } from '../BlockTypes.js';

test('ALL_BLOCK_TYPES contains exactly 16 types', () => {
  assert.equal(ALL_BLOCK_TYPES.length, 16);
  assert.ok(isBlockTypeAllowed('customer_info'));
  assert.ok(isBlockTypeAllowed('item_picker'));
  assert.ok(isBlockTypeAllowed('item_table_editable'));
  assert.ok(isBlockTypeAllowed('price_summary'));
  assert.ok(isBlockTypeAllowed('stats_cards'));
  assert.equal(isBlockTypeAllowed('unsupported_block_abc'), false);
});
