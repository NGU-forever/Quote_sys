<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  status: { type: String, default: 'approved' },
});
</script>

<template>
  <div class="qs-card p-3 flex items-center justify-between text-xs">
    <div class="flex items-center gap-2">
      <span class="font-medium text-[var(--color-text)]">内部审批状态:</span>
      <span class="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-semibold">
        已自动核准通过 (无违规)
      </span>
    </div>
    <span class="text-[var(--color-text-muted)] text-[11px]">审批人: 系统自动</span>
  </div>
</template>
