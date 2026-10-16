<script setup>
/**
 * 打印版式独立渲染：只挂载 QuotePrintArea，产出与真实打印一致的版面。
 * 用于黄金屏中的"打印基准"，避免把屏幕界面混进截图。
 */
import QuotePrintArea from '../src/renderer/QuotePrintArea.vue';
import { provideSpecContext } from '../src/renderer/SpecProvider.js';
import ThemeProvider from '../src/renderer/tokens/ThemeProvider.vue';

const props = defineProps({
  spec: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
});

provideSpecContext(props.spec);
</script>

<template>
  <ThemeProvider :preset-id="spec.style?.preset_id" :tokens="spec.style?.tokens">
    <div class="qs-print-standalone">
      <QuotePrintArea
        :items="data.items"
        :company="data.company"
        :customer="{ customer_name: data.quote?.customer_name }"
        :quote-no="data.quote?.quote_no"
        :sales-name="data.quote?.sales_name"
      />
    </div>
  </ThemeProvider>
</template>
