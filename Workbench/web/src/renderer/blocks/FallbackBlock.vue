<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  blockType: { type: String, default: 'unknown' },
});
</script>

<template>
  <div class="p-3 rounded border border-dashed border-[var(--color-border)] text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)]">
    [区块 {{ blockType }} 暂未装载]
  </div>
</template>
