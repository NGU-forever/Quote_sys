import test from 'node:test';
import assert from 'node:assert/strict';

import { createWizardState, applyPresetToWizard } from '../wizardState.js';

test('createWizardState initializes default answers', () => {
  const state = createWizardState();
  assert.equal(state.currentStep, 0);
  assert.equal(state.answers.sell_mode, 'device_with_consumable');
  assert.equal(state.answers.scene, 'on_site');
  assert.equal(state.answers.pricing_mode, 'floor_price');
  assert.equal(state.answers.output_target, 'print_a4');
});

test('applyPresetToWizard pre-fills steps 1, 3, 4, 7', () => {
  const state = createWizardState();
  applyPresetToWizard(state, 'wholesale');

  assert.equal(state.selectedPreset, 'wholesale');
  assert.equal(state.answers.sell_mode, 'consumable_only');
  assert.equal(state.answers.scene, 'office');
  assert.equal(state.answers.pricing_mode, 'tiered');
  assert.equal(state.answers.preset_id, 'industrial-dense');
});
