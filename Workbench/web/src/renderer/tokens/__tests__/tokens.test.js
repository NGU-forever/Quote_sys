import test from 'node:test';
import assert from 'node:assert/strict';

import {
  PRESETS,
  resolveTokens,
  adjustColorContrast,
} from '../presets.js';

test('PRESETS contains 3 builtin presets', () => {
  assert.ok(PRESETS['medical-clean']);
  assert.ok(PRESETS['industrial-dense']);
  assert.ok(PRESETS['brand-premium']);
  assert.equal(PRESETS['medical-clean'].tableRowHeight, '44px');
  assert.equal(PRESETS['industrial-dense'].tableRowHeight, '34px');
  assert.equal(PRESETS['brand-premium'].tableRowHeight, '52px');
});

test('resolveTokens handles custom primary color', () => {
  const tokens = resolveTokens('medical-clean', { 'color.primary': '#ff0000' });
  assert.equal(tokens['--color-primary'], '#ff0000');
  assert.equal(tokens['--radius-base'], '8px');
  assert.equal(tokens['--table-row-h'], '44px');
});

test('adjustColorContrast darkens low contrast color', () => {
  // 极浅黄色在白底上对比度不足 3:1，应自动加深
  const lightColor = '#FFF5B8';
  const adjusted = adjustColorContrast(lightColor, '#FFFFFF');
  assert.notEqual(adjusted, lightColor);
});
