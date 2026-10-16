<script setup>
/**
 * 商务条款：条款文案由 output.quote_pdf.terms_block 驱动
 * （'company_default' 或空 = 内置默认条款；其他字符串按字面渲染）。
 */
import { computed } from 'vue';

import { useSpecContext } from '../SpecProvider.js';

const props = defineProps({
  props: { type: Object, default: () => ({}) },
  terms: { type: String, default: '' },
});

const ctx = useSpecContext();

const DEFAULT_TERMS =
  '1. 本报价含标准送货与安装调试；\n2. 付款方式：签订合同预付 30%，验收合格付清余款；\n3. 质保期：验收合格之日起一年。';

const termsText = computed(() => {
  if (props.terms) return props.terms;
  const configured = ctx.printConfig?.terms_block;
  if (configured && configured !== 'company_default') return String(configured);
  return DEFAULT_TERMS;
});
</script>

<template>
  <div class="qs-card p-3 flex flex-col gap-1.5 text-xs">
    <span class="font-semibold text-[var(--color-text)]">商务条款与交付说明</span>
    <p class="text-[var(--color-text-muted)] whitespace-pre-line leading-relaxed">
      {{ termsText }}
    </p>
  </div>
</template>
