/**
 * 黄金屏渲染入口：通过 query 参数选择骨架与风格，用固定种子数据渲染。
 *   ?skeleton=catalog-left-form-right&preset=medical-clean[&print=1]
 *   ?shell=1&preset=medical-clean[&screen=quotes]
 *
 * print=1 时只挂载打印区（PrintHarness），产出与真实打印一致的版面基准。
 * shell=1 时挂载运行时外壳（RuntimeShell），覆盖「多屏 + 顶部导航」这条链路。
 */
import { createApp, h } from 'vue';

import SpecRenderer from '../src/renderer/SpecRenderer.vue';
import RuntimeShell from '../src/renderer/RuntimeShell.vue';
import PrintHarness from './PrintHarness.vue';
import { SEED_DATA, buildSpec } from './seed.js';

import '../src/shared/assets/tailwind.css';
import '../src/shared/assets/main.css';
import './harness.css';

const params = new URLSearchParams(window.location.search);
const skeleton = params.get('skeleton') || 'catalog-left-form-right';
const preset = params.get('preset') || 'medical-clean';
const printMode = params.get('print') === '1';
const shellMode = params.get('shell') === '1';
const screen = params.get('screen') || '';

const spec = buildSpec(skeleton, preset);

if (printMode) {
  document.body.classList.add('visual-print-mode');
}

const App = {
  render() {
    if (printMode) {
      return h(PrintHarness, { spec, data: SEED_DATA });
    }
    if (shellMode) {
      return h(RuntimeShell, { spec, data: SEED_DATA, initialScreenId: screen });
    }
    return h(SpecRenderer, { spec, data: SEED_DATA });
  },
};

createApp(App).mount('#app');
