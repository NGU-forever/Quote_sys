<script setup>
/**
 * 商品选择器：列标签、筛选项、价格口径全部由 Spec 的 entities.product 驱动。
 * 术语（例如 min_price 叫"最低底价"还是"供货价"）来自 entities.product.labels。
 */
import { computed } from 'vue';

import { formatCell } from '../SpecContext.js';
import { useSpecContext } from '../SpecProvider.js';

const props = defineProps({
  props: { type: Object, default: () => ({}) },
  products: { type: Array, default: () => [] },
});

const emit = defineEmits(['add-item']);

const ctx = useSpecContext();

const DEFAULT_KEYS = ['name', 'sku_id', 'category', 'min_price'];
const columns = computed(() => {
  const blockKeys = props.props?.columns;
  if (Array.isArray(blockKeys) && blockKeys.length > 0) {
    return blockKeys.map((key) => ctx.column('product', key));
  }
  return ctx.listColumns('product', DEFAULT_KEYS);
});

const titleColumn = computed(
  () => columns.value.find((c) => c.key === 'name') || columns.value[0]
);
const metaColumns = computed(() =>
  columns.value.filter((c) => c.key !== titleColumn.value?.key && !c.money)
);
const priceColumn = computed(
  () => columns.value.find((c) => c.money) || ctx.column('product', 'min_price')
);
const filterKeys = computed(() => ctx.filters('product', ['keyword']));
</script>

<template>
  <div class="qs-card p-4 flex flex-col gap-3 h-full">
    <div class="flex items-center justify-between pb-2 border-b border-[var(--color-border)]">
      <span class="font-semibold text-sm text-[var(--color-text)]">商品目录</span>
      <span class="text-xs text-[var(--color-text-muted)]">{{ products.length }} 个商品</span>
    </div>

    <div v-if="filterKeys.length" class="flex flex-wrap items-center gap-1.5">
      <span
        v-for="key in filterKeys"
        :key="key"
        class="text-[10px] px-2 py-0.5 rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)]"
      >
        {{ ctx.label('product', key) }}
      </span>
    </div>

    <div class="flex-1 overflow-y-auto flex flex-col gap-2 pr-1">
      <div
        v-for="p in products"
        :key="p.sku_id"
        class="p-2.5 rounded border border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-primary)] cursor-pointer transition flex items-center justify-between"
        @click="emit('add-item', p)"
      >
        <div class="flex flex-col min-w-0 pr-2">
          <span class="text-xs font-medium text-[var(--color-text)] truncate">
            {{ formatCell(titleColumn, p) }}
          </span>
          <span class="text-[10px] text-[var(--color-text-muted)] truncate">
            <template v-for="(col, i) in metaColumns" :key="col.key">
              <template v-if="i > 0"> · </template>{{ formatCell(col, p) }}
            </template>
          </span>
        </div>
        <div class="flex flex-col items-end flex-shrink-0">
          <span class="text-xs font-semibold text-[var(--color-primary)] qs-numeric">
            {{ formatCell(priceColumn, p) }}
          </span>
          <span class="text-[10px] text-[var(--color-text-muted)]">点击添加 +</span>
        </div>
      </div>
      <p v-if="products.length === 0" class="text-xs text-[var(--color-text-muted)] py-6 text-center">
        暂无商品，请先在商品管理中维护数据
      </p>
    </div>
  </div>
</template>
