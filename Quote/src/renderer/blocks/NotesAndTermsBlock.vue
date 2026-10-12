<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  terms: { type: String, default: '1. 本报价含标准送货与安装调试；\n2. 付款方式：签订合同预付 30%，验收合格付清余款；\n3. 质保期：验收合格之日起一年。' },
});
</script>

<template>
  <div class="qs-card p-3 flex flex-col gap-1.5 text-xs">
    <span class="font-semibold text-[var(--color-text)]">商务条款与交付说明</span>
    <p class="text-[var(--color-text-muted)] whitespace-pre-line leading-relaxed">{{ terms }}</p>
  </div>
</template>
