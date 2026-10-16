<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
});

const emit = defineEmits(['save-draft', 'print-a4', 'export-pdf']);
</script>

<template>
  <div class="flex items-center justify-end gap-3 p-3 bg-[var(--color-bg)] border-t border-[var(--color-border)]">
    <button
      class="px-4 py-2 border border-[var(--color-border)] rounded text-xs text-[var(--color-text)] hover:bg-[var(--color-surface)] font-medium transition"
      @click="emit('save-draft')"
    >
      保存为草稿
    </button>
    <button
      class="qs-btn-primary text-xs flex items-center gap-1.5"
      @click="emit('print-a4')"
    >
      <span>🖨 打印 A4 标准报价单</span>
    </button>
  </div>
</template>
