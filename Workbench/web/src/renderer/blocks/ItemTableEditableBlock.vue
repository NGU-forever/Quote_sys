<script setup>
/**
 * 可编辑明细表：列集合来自块级 props.columns（其次 entities.quote_item），
 * 底价合规列的显隐同时受 rules.price_floor_guard 与 rules.price_visibility 约束。
 */
import { computed } from 'vue';

import { formatCell, formatMoney } from '../SpecContext.js';
import { useSpecContext } from '../SpecProvider.js';

const props = defineProps({
  props: { type: Object, default: () => ({}) },
  items: { type: Array, default: () => [] },
});

const emit = defineEmits(['update-qty', 'remove-item']);

const ctx = useSpecContext();

const DEFAULT_KEYS = ['name', 'unit_price', 'qty', 'subtotal', 'floor_check'];

const showFloorCheck = computed(
  () => ctx.rule('price_floor_guard', true) && ctx.showsFloorPrice()
);

const columns = computed(() => {
  const blockKeys = props.props?.columns;
  const keys =
    Array.isArray(blockKeys) && blockKeys.length > 0 ? blockKeys : DEFAULT_KEYS;
  return keys
    .map((key) => ctx.column('quote_item', key))
    .filter((col) => col.key !== 'floor_check' || showFloorCheck.value);
});

function cellKind(key) {
  if (key === 'qty') return 'qty';
  if (key === 'floor_check') return 'badge';
  return 'text';
}
</script>

<template>
  <div class="qs-card overflow-hidden flex flex-col">
    <div class="p-3 bg-[var(--color-bg)] border-b border-[var(--color-border)] font-semibold text-sm">
      报价清单明细
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-left text-xs border-collapse">
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
            <th class="p-2 pr-4 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(item, idx) in items"
            :key="item.sku_id || idx"
            class="border-b border-[var(--color-border)] hover:bg-[var(--color-surface)] transition"
            style="height: var(--table-row-h)"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              class="p-2 first:pl-4"
              :class="{
                'qs-numeric': col.money || col.numeric,
                'font-bold text-[var(--color-primary)]': col.key === 'subtotal',
              }"
            >
              <!-- 数量：可编辑 -->
              <input
                v-if="cellKind(col.key) === 'qty'"
                type="number"
                min="1"
                :value="item.qty || 1"
                class="w-16 px-1.5 py-0.5 border border-[var(--color-border)] rounded text-xs text-center bg-[var(--color-bg)]"
                @input="emit('update-qty', { index: idx, qty: Number($event.target.value) })"
              />

              <!-- 底价合规：受 rules 控制 -->
              <template v-else-if="cellKind(col.key) === 'badge'">
                <span
                  v-if="item.floor_status === 'warn'"
                  class="inline-flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200"
                  >⚠ 破底价</span
                >
                <span
                  v-else
                  class="inline-flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200"
                  >✓ 合规</span
                >
              </template>

              <!-- 小计按单价×数量实时计算 -->
              <template v-else-if="col.key === 'subtotal'">
                {{ formatMoney(Number(item.unit_price || 0) * Number(item.qty || 1)) }}
              </template>

              <template v-else>{{ formatCell(col, item) }}</template>
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
            <td
              :colspan="columns.length + 1"
              class="p-8 text-center text-xs text-[var(--color-text-muted)]"
            >
              请从商品目录选择商品加入清单
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
