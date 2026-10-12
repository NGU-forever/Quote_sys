<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  quoteNo: { type: String, default: 'QT-20261012-0001' },
  salesName: { type: String, default: '销售经理' },
});
</script>

<template>
  <div class="flex items-center justify-between text-xs text-[var(--color-text-muted)] py-1">
    <div class="flex items-center gap-3">
      <span>单号: <strong class="font-mono text-[var(--color-text)]">{{ quoteNo }}</strong></span>
      <span>业务员: <span class="text-[var(--color-text)]">{{ salesName }}</span></span>
    </div>
    <div class="flex items-center gap-2">
      <span>有效期: 30天</span>
      <span>生成时间: 2026-10-12</span>
    </div>
  </div>
</template>
