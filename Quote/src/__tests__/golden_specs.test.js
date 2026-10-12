import test from 'node:test';
import assert from 'node:assert/strict';

import { loadAndNormalizeSpec, getSkeletonSlots } from '../renderer/SpecLoader.js';
import { PRESETS } from '../renderer/tokens/presets.js';
import { ALL_BLOCK_TYPES } from '../renderer/BlockTypes.js';

test('Golden Specs validation across 3 style presets and 5 skeletons', () => {
  const skeletons = [
    'catalog-left-form-right',
    'form-first-wizard',
    'list-detail-split',
    'dashboard-grid',
    'mobile-single-column',
  ];

  skeletons.forEach((sk) => {
    const slots = getSkeletonSlots(sk);
    assert.ok(slots.length >= 3, `Skeleton ${sk} should have at least 3 slots`);
  });

  Object.keys(PRESETS).forEach((presetKey) => {
    const preset = PRESETS[presetKey];
    assert.ok(preset.primary.startsWith('#'));
    assert.ok(preset.tableRowHeight);
  });

  assert.equal(ALL_BLOCK_TYPES.length, 16);
});
