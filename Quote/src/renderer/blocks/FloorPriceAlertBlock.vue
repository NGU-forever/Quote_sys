<script setup>
/**
 * 底价拦截提示：受 rules.price_floor_guard 控制是否启用，
 * 仅当 rules.approval_required 为真时才显示"需主管确认"。
 */
import { computed } from 'vue';

import { useSpecContext } from '../SpecProvider.js';

defineProps({
  props: { type: Object, default: () => ({}) },
  hasViolation: { type: Boolean, default: false },
});

const ctx = useSpecContext();

const guardEnabled = computed(() => ctx.rule('price_floor_guard', true));
const needApproval = computed(() => ctx.rule('approval_required', false));
</script>

<template>
  <div
    v-if="guardEnabled"
    class="p-3 rounded border text-xs flex items-center justify-between"
    :class="
      hasViolation
        ? 'border-amber-300 bg-amber-50 text-amber-800'
        : 'border-emerald-200 bg-emerald-50 text-emerald-800'
    "
  >
    <div class="flex items-center gap-2">
      <template v-if="hasViolation">
        <span class="font-bold text-sm">⚠ 底价拦截提醒:</span>
        <span>当前清单中存在低于公司底价的商品，保存或导出将触发管理员审批流程。</span>
      </template>
      <template v-else>
        <span class="font-bold text-sm">✓ 底价校验通过:</span>
        <span>当前清单所有商品均不低于底价。</span>
      </template>
    </div>
    <span
      v-if="needApproval"
      class="text-[10px] bg-amber-200 text-amber-900 px-2 py-0.5 rounded font-medium"
      >需主管确认</span
    >
  </div>
</template>
