<script setup>
/**
 * 单据头信息：单号由 rules.quote_no_pattern 生成（SpecRenderer 传入），
 * 字段标签来自 entities.quote.labels。
 */
import { computed } from 'vue';

import { useSpecContext } from '../SpecProvider.js';

const props = defineProps({
  props: { type: Object, default: () => ({}) },
  quoteNo: { type: String, default: '' },
  salesName: { type: String, default: '' },
});

const ctx = useSpecContext();

const validDays = computed(() => Number(props.props?.valid_days || 30));
const createdAt = computed(() => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(
    now.getDate()
  ).padStart(2, '0')}`;
});
</script>

<template>
  <div class="flex items-center justify-between text-xs text-[var(--color-text-muted)] py-1">
    <div class="flex items-center gap-3">
      <span>
        {{ ctx.label('quote', 'quote_no') }}:
        <strong class="font-mono text-[var(--color-text)]">{{ quoteNo || '—' }}</strong>
      </span>
      <span>
        {{ ctx.label('quote', 'sales_name') }}:
        <span class="text-[var(--color-text)]">{{ salesName || '—' }}</span>
      </span>
    </div>
    <div class="flex items-center gap-2">
      <span>有效期: {{ validDays }}天</span>
      <span>{{ ctx.label('quote', 'created_at') }}: {{ createdAt }}</span>
    </div>
  </div>
</template>
