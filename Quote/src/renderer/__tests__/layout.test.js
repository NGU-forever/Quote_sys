import test from 'node:test';
import assert from 'node:assert/strict';

import { loadAndNormalizeSpec, getSkeletonSlots } from '../SpecLoader.js';

test('loadAndNormalizeSpec handles valid spec', () => {
  const spec = {
    spec_version: 1,
    style: { preset_id: 'medical-clean' },
    screens: [
      {
        id: 'quote_editor',
        skeleton: 'catalog-left-form-right',
        blocks: [{ type: 'item_picker', props: {} }],
      },
    ],
  };

  const normalized = loadAndNormalizeSpec(spec);
  assert.equal(normalized.spec_version, 1);
  assert.equal(normalized.screens[0].skeleton, 'catalog-left-form-right');
});

test('loadAndNormalizeSpec falls back on null/malformed spec', () => {
  const normalized = loadAndNormalizeSpec(null);
  assert.ok(normalized.screens.length > 0);
  assert.equal(normalized.screens[0].skeleton, 'catalog-left-form-right');
});

test('getSkeletonSlots returns correct slot names for 5 skeletons', () => {
  const s1 = getSkeletonSlots('catalog-left-form-right');
  assert.ok(s1.includes('left_rail'));
  assert.ok(s1.includes('main_body'));

  const s2 = getSkeletonSlots('form-first-wizard');
  assert.ok(s2.includes('step_body'));

  const s3 = getSkeletonSlots('list-detail-split');
  assert.ok(s3.includes('list'));
  assert.ok(s3.includes('detail_body'));

  const s4 = getSkeletonSlots('dashboard-grid');
  assert.ok(s4.includes('stats_row'));

  const s5 = getSkeletonSlots('mobile-single-column');
  assert.ok(s5.includes('content'));
});
