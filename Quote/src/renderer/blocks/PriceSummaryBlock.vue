<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  totalAmount: { type: Number, default: 0 },
});
</script>

<template>
  <div class="qs-card p-4 flex items-center justify-between border-t-2 border-[var(--color-primary)]">
    <div class="flex items-center gap-4 text-xs text-[var(--color-text-muted)]">
      <span>结算币种: 人民币 (CNY)</span>
      <span>税率口径: 未税指导价</span>
    </div>
    <div class="flex items-baseline gap-2">
      <span class="text-xs text-[var(--color-text-muted)]">应付总额:</span>
      <span class="text-2xl font-black text-[var(--color-primary)] qs-numeric">
        ¥{{ totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
      </span>
    </div>
  </div>
</template>
