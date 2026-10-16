<script setup>
/**
 * 审批状态：是否走审批由 rules.approval_required 决定。
 */
import { computed } from 'vue';

import { useSpecContext } from '../SpecProvider.js';

defineProps({
  props: { type: Object, default: () => ({}) },
  status: { type: String, default: '' },
});

const ctx = useSpecContext();

const needApproval = computed(() => ctx.rule('approval_required', false));
const statusText = computed(() => {
  if (needApproval.value) return '待主管审批 (存在破价或特批申请)';
  return '已自动核准通过 (无违规)';
});
</script>

<template>
  <div class="qs-card p-3 flex items-center justify-between text-xs">
    <div class="flex items-center gap-2">
      <span class="font-medium text-[var(--color-text)]">内部审批状态:</span>
      <span
        class="px-2 py-0.5 rounded border font-semibold"
        :class="
          needApproval
            ? 'text-amber-700 bg-amber-50 border-amber-200'
            : 'text-emerald-700 bg-emerald-50 border-emerald-200'
        "
      >
        {{ statusText }}
      </span>
    </div>
    <span class="text-[var(--color-text-muted)] text-[11px]">
      审批人: {{ needApproval ? '待指派主管' : '系统自动' }}
    </span>
  </div>
</template>
