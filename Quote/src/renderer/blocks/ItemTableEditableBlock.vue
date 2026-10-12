<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  items: { type: Array, default: () => [] },
});

const emit = defineEmits(['update-qty', 'remove-item']);
</script>

<template>
  <div class="qs-card overflow-hidden flex flex-col">
    <div class="p-3 bg-[var(--color-bg)] border-b border-[var(--color-border)] font-semibold text-sm">
      报价清单明细
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-left text-xs border-collapse">
        <thead>
          <tr class="border-b border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]" style="height: var(--table-row-h);">
            <th class="p-2 pl-4">品名与型号</th>
            <th class="p-2">单价</th>
            <th class="p-2">数量</th>
            <th class="p-2">小计</th>
            <th class="p-2">底价合规</th>
            <th class="p-2 pr-4 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, idx) in items"
            :key="item.sku_id || idx"
            class="border-b border-[var(--color-border)] hover:bg-[var(--color-surface)] transition"
            :class="{ 'bg-[var(--color-surface)]': item.zebra }"
            style="height: var(--table-row-h);"
          >
            <td class="p-2 pl-4 font-medium text-[var(--color-text)] truncate max-w-[200px]">{{ item.name }}</td>
            <td class="p-2 qs-numeric font-semibold">¥{{ (item.unit_price || 0).toLocaleString() }}</td>
            <td class="p-2">
              <input
                type="number"
                min="1"
                :value="item.qty || 1"
                class="w-16 px-1.5 py-0.5 border border-[var(--color-border)] rounded text-xs text-center bg-[var(--color-bg)]"
                @input="emit('update-qty', { index: idx, qty: Number($event.target.value) })"
              />
            </td>
            <td class="p-2 qs-numeric font-bold text-[var(--color-primary)]">
              ¥{{ ((item.unit_price || 0) * (item.qty || 1)).toLocaleString() }}
            </td>
            <td class="p-2">
              <span
                v-if="item.floor_status === 'warn'"
                class="inline-flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200"
              >
                ⚠ 破底价
              </span>
              <span
                v-else
                class="inline-flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200"
              >
                ✓ 合规
              </span>
            </td>
            <td class="p-2 pr-4 text-right">
              <button
                class="text-red-500 hover:text-red-700 text-xs"
                @click="emit('remove-item', idx)"
              >
                移除
              </button>
            </td>
          </tr>
          <tr v-if="items.length === 0">
            <td colspan="6" class="p-8 text-center text-xs text-[var(--color-text-muted)]">
              请从左侧商品目录选择商品加入清单
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
