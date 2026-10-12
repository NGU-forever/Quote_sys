<script setup>
const props = defineProps({
  props: { type: Object, default: () => ({}) },
  products: { type: Array, default: () => [] },
});

const emit = defineEmits(['add-item']);
</script>

<template>
  <div class="qs-card p-4 flex flex-col gap-3 h-full">
    <div class="flex items-center justify-between pb-2 border-b border-[var(--color-border)]">
      <span class="font-semibold text-sm text-[var(--color-text)]">商品目录</span>
      <span class="text-xs text-[var(--color-text-muted)]">{{ products.length }} 个商品</span>
    </div>

    <div class="flex-1 overflow-y-auto flex flex-col gap-2 pr-1">
      <div
        v-for="p in products"
        :key="p.sku_id"
        class="p-2.5 rounded border border-[var(--color-border)] bg-[var(--color-bg)] hover:border-[var(--color-primary)] cursor-pointer transition flex items-center justify-between"
        @click="emit('add-item', p)"
      >
        <div class="flex flex-col min-w-0 pr-2">
          <span class="text-xs font-medium text-[var(--color-text)] truncate">{{ p.name }}</span>
          <span class="text-[10px] text-[var(--color-text-muted)]">{{ p.sku_id }} · {{ p.category }}</span>
        </div>
        <div class="flex flex-col items-end flex-shrink-0">
          <span class="text-xs font-semibold text-[var(--color-primary)] qs-numeric">
            {{ p.price_display || `¥${p.min_price || 0}` }}
          </span>
          <span class="text-[10px] text-[var(--color-text-muted)]">点击添加 +</span>
        </div>
      </div>
    </div>
  </div>
</template>
