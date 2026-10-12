<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  items: { type: Array, default: () => [] },
});
</script>

<template>
  <div class="qs-card overflow-hidden">
    <div class="p-3 bg-[var(--color-bg)] border-b border-[var(--color-border)] font-semibold text-sm">
      明细总览 (只读)
    </div>
    <table class="w-full text-left text-xs">
      <thead>
        <tr class="border-b border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]" style="height: var(--table-row-h);">
          <th class="p-2 pl-4">编号</th>
          <th class="p-2">品名</th>
          <th class="p-2">指导单价</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.sku_id" class="border-b border-[var(--color-border)]" style="height: var(--table-row-h);">
          <td class="p-2 pl-4 font-mono text-[var(--color-text-muted)]">{{ item.sku_id }}</td>
          <td class="p-2 font-medium">{{ item.name }}</td>
          <td class="p-2 qs-numeric font-semibold">¥{{ (item.min_price || item.unit_price || 0).toLocaleString() }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
