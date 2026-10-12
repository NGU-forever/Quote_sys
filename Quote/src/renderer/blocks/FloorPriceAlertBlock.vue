<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  hasViolation: { type: Boolean, default: false },
});
</script>

<template>
  <div
    v-if="hasViolation"
    class="p-3 rounded border border-amber-300 bg-amber-50 text-amber-800 text-xs flex items-center justify-between"
  >
    <div class="flex items-center gap-2">
      <span class="font-bold text-sm">⚠ 底价拦截提醒:</span>
      <span>当前清单中存在低于公司底价的商品，保存或导出将触发管理员审批流程。</span>
    </div>
    <span class="text-[10px] bg-amber-200 text-amber-900 px-2 py-0.5 rounded font-medium">需主管确认</span>
  </div>
</template>
