<script setup>
/**
 * 议价与折扣：最大折让来自块级 props，是否允许发起特批由 rules.approval_required 决定。
 */
import { computed } from 'vue';

import { useSpecContext } from '../SpecProvider.js';

const props = defineProps({
  props: { type: Object, default: () => ({}) },
  discountRate: { type: Number, default: 0 },
});

const ctx = useSpecContext();

const maxDiscount = computed(() => {
  const configured = props.props?.max_discount;
  if (configured === undefined || configured === null) return '95 折';
  const value = Number(configured);
  if (Number.isNaN(value)) return String(configured);
  return `${(value * 10).toFixed(1).replace(/\.0$/, '')} 折`;
});

const canRequestApproval = computed(() => ctx.rule('approval_required', false));
</script>

<template>
  <div class="qs-card p-3 flex items-center justify-between text-xs">
    <div class="flex items-center gap-2">
      <span class="font-medium">议价与折扣:</span>
      <span class="text-[var(--color-text-muted)]">当前授权最大折让: {{ maxDiscount }}</span>
    </div>
    <div class="flex items-center gap-2">
      <template v-if="canRequestApproval">
        <span class="text-[var(--color-text-muted)]">申请特批:</span>
        <button
          class="px-2 py-1 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)]"
        >
          发起价格特批申请
        </button>
      </template>
      <span v-else class="text-[var(--color-text-muted)]">本方案未启用价格特批流程</span>
    </div>
  </div>
</template>
