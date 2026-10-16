<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  stats: {
    type: Object,
    default: () => ({
      todaySales: 168000,
      quoteCount: 18,
      pendingApproval: 2,
    }),
  },
});
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <div class="qs-card p-4 flex flex-col gap-1">
      <span class="text-xs text-[var(--color-text-muted)]">今日报价总额</span>
      <span class="text-2xl font-bold text-[var(--color-primary)] qs-numeric">
        ¥{{ stats.todaySales.toLocaleString() }}
      </span>
    </div>
    <div class="qs-card p-4 flex flex-col gap-1">
      <span class="text-xs text-[var(--color-text-muted)]">本月活跃单据</span>
      <span class="text-2xl font-bold text-[var(--color-text)] qs-numeric">
        {{ stats.quoteCount }} <span class="text-xs font-normal text-[var(--color-text-muted)]">单</span>
      </span>
    </div>
    <div class="qs-card p-4 flex flex-col gap-1">
      <span class="text-xs text-[var(--color-text-muted)]">待审批破价单</span>
      <span class="text-2xl font-bold text-amber-600 qs-numeric">
        {{ stats.pendingApproval }} <span class="text-xs font-normal text-[var(--color-text-muted)]">单待核</span>
      </span>
    </div>
  </div>
</template>
