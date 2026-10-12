<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  discountRate: { type: Number, default: 0 },
});
</script>

<template>
  <div class="qs-card p-3 flex items-center justify-between text-xs">
    <div class="flex items-center gap-2">
      <span class="font-medium">议价与折扣:</span>
      <span class="text-[var(--color-text-muted)]">当前授权最大折让: 95 折</span>
    </div>
    <div class="flex items-center gap-2">
      <span class="text-[var(--color-text-muted)]">申请特批:</span>
      <button class="px-2 py-1 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)]">
        发起价格特批申请
      </button>
    </div>
  </div>
</template>
