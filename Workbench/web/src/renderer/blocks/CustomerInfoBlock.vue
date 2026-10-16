<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  data: { type: Object, default: () => ({}) },
});
</script>

<template>
  <div class="qs-card p-4 flex flex-col gap-2">
    <div class="text-xs font-semibold text-[var(--color-text-muted)] tracking-wider">客户与联系方式</div>
    <div class="grid grid-cols-2 gap-3 text-sm">
      <div class="flex items-center gap-2">
        <span class="text-[var(--color-text-muted)]">客户:</span>
        <span class="font-medium text-[var(--color-text)]">{{ data?.customer_name || '仁爱医院设备科' }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-[var(--color-text-muted)]">联系人:</span>
        <span class="font-medium text-[var(--color-text)]">{{ data?.customer_contact || '陈主任 (13800000000)' }}</span>
      </div>
    </div>
  </div>
</template>
