/**
 * 黄金屏渲染入口：通过 query 参数选择骨架与风格，用固定种子数据渲染。
 *   ?skeleton=catalog-left-form-right&preset=medical-clean[&print=1]
 *
 * print=1 时只挂载打印区（PrintHarness），产出与真实打印一致的版面基准。
 */
import { createApp, h } from 'vue';

import SpecRenderer from '../src/renderer/SpecRenderer.vue';
import PrintHarness from './PrintHarness.vue';
import { SEED_DATA, buildSpec } from './seed.js';

import '../src/shared/assets/tailwind.css';
import '../src/shared/assets/main.css';
import './harness.css';

const params = new URLSearchParams(window.location.search);
const skeleton = params.get('skeleton') || 'catalog-left-form-right';
const preset = params.get('preset') || 'medical-clean';
const printMode = params.get('print') === '1';

const spec = buildSpec(skeleton, preset);

if (printMode) {
  document.body.classList.add('visual-print-mode');
}

const App = {
  render() {
    if (printMode) {
      return h(PrintHarness, { spec, data: SEED_DATA });
    }
    return h(SpecRenderer, { spec, data: SEED_DATA });
  },
};

createApp(App).mount('#app');
