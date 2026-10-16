/**
 * 黄金屏渲染入口：通过 query 参数选择骨架与风格，用固定种子数据渲染。
 *   ?skeleton=catalog-left-form-right&preset=medical-clean[&print=1]
 *   ?shell=1&preset=medical-clean[&screen=quotes]
 *   ?adapter=1&preset=medical-clean[&screen=quote_editor]
 *
 * print=1   只挂载打印区（PrintHarness），产出与真实打印一致的版面基准。
 * shell=1   挂载运行时外壳（RuntimeShell），覆盖「多屏 + 顶部导航」这条链路，数据用固定种子。
 * adapter=1 挂载「真实 pinia store + 宿主适配器」的运行时外壳：金额、明细、合计
 *           全部来自报价单 store 的真实计算，用于验证定制屏是能成交的界面。
 */
import { createApp, defineComponent, h } from 'vue';
import { createPinia } from 'pinia';

import SpecRenderer from '../src/renderer/SpecRenderer.vue';
import RuntimeShell from '../src/renderer/RuntimeShell.vue';
import PrintHarness from './PrintHarness.vue';
import { SEED_DATA, buildSpec } from './seed.js';
import { useSpecRuntime } from '../src/quote/composables/useSpecRuntime.js';

import '../src/shared/assets/tailwind.css';
import '../src/shared/assets/main.css';
import './harness.css';

const params = new URLSearchParams(window.location.search);
const skeleton = params.get('skeleton') || 'catalog-left-form-right';
const preset = params.get('preset') || 'medical-clean';
const printMode = params.get('print') === '1';
const shellMode = params.get('shell') === '1';
const adapterMode = params.get('adapter') === '1';
const screen = params.get('screen') || '';

const spec = buildSpec(skeleton, preset);

if (printMode) {
  document.body.classList.add('visual-print-mode');
}

/**
 * 适配器模式：真实 store → useSpecRuntime → RuntimeShell。
 * 接线方式与 LandingView 一致，因此这一屏就是"员工实际看到的定制屏"。
 */
const AdapterApp = defineComponent({
  setup() {
    const runtime = useSpecRuntime();
    return () =>
      h(RuntimeShell, {
        spec,
        data: runtime.data.value,
        initialScreenId: screen,
        onAddItem: (payload) => runtime.dispatch('add-item', payload),
        onUpdateQty: (payload) => runtime.dispatch('update-qty', payload),
        onRemoveItem: (payload) => runtime.dispatch('remove-item', payload),
        onApplyBundle: (payload) => runtime.dispatch('apply-bundle', payload),
        onSaveDraft: () => runtime.dispatch('save-draft'),
        onPrintA4: () => runtime.dispatch('print-a4'),
        onExportPdf: () => runtime.dispatch('export-pdf')
      });
  }
});

const PlainApp = {
  render() {
    if (printMode) {
      return h(PrintHarness, { spec, data: SEED_DATA });
    }
    if (shellMode) {
      return h(RuntimeShell, { spec, data: SEED_DATA, initialScreenId: screen });
    }
    return h(SpecRenderer, { spec, data: SEED_DATA });
  }
};

const app = createApp(adapterMode ? AdapterApp : PlainApp);
// 适配器模式需要 pinia；其余模式保持无依赖的纯渲染
if (adapterMode) app.use(createPinia());
app.mount('#app');
