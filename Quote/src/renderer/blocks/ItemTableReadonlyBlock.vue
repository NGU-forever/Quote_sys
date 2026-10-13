<script setup>
/**
 * 只读明细表：列集合来自块级 props.columns（其次 entities.quote.list_columns）。
 */
import { computed } from 'vue';

import { formatCell } from '../SpecContext.js';
import { useSpecContext } from '../SpecProvider.js';

const props = defineProps({
  props: { type: Object, default: () => ({}) },
  items: { type: Array, default: () => [] },
});

const ctx = useSpecContext();

const DEFAULT_KEYS = ['sku_id', 'name', 'min_price'];

const columns = computed(() => {
  const blockKeys = props.props?.columns;
  if (Array.isArray(blockKeys) && blockKeys.length > 0) {
    return blockKeys.map((key) => ctx.column('quote', key));
  }
  return ctx.listColumns('quote', DEFAULT_KEYS);
});
</script>

<template>
  <div class="qs-card overflow-hidden">
    <div class="p-3 bg-[var(--color-bg)] border-b border-[var(--color-border)] font-semibold text-sm">
      明细总览 (只读)
    </div>
    <table class="w-full text-left text-xs">
      <thead>
        <tr
          class="border-b border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]"
          style="height: var(--table-row-h)"
        >
          <th
            v-for="col in columns"
            :key="col.key"
            class="p-2 first:pl-4"
            :class="{ 'qs-numeric': col.money || col.numeric }"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in items"
          :key="item.sku_id"
          class="border-b border-[var(--color-border)]"
          style="height: var(--table-row-h)"
        >
          <td
            v-for="col in columns"
            :key="col.key"
            class="p-2 first:pl-4"
            :class="{
              'qs-numeric font-semibold': col.money,
              'font-mono text-[var(--color-text-muted)]': col.key === 'sku_id',
              'font-medium': col.key === 'name',
            }"
          >
            {{ formatCell(col, item) }}
          </td>
        </tr>
        <tr v-if="items.length === 0">
          <td
            :colspan="columns.length"
            class="p-8 text-center text-xs text-[var(--color-text-muted)]"
          >
            暂无明细
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
