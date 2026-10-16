<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
});
</script>

<template>
  <div class="qs-card p-3 flex items-center justify-between text-xs">
    <div class="flex items-center gap-2">
      <span class="font-medium text-[var(--color-text)]">技术参数与附件:</span>
      <span class="text-[var(--color-text-muted)]">支持上传彩页、招标文件 (PDF/ZIP, 最大 20MB)</span>
    </div>
    <button class="px-2.5 py-1 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)]">
      上传附件
    </button>
  </div>
</template>
