<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  logs: {
    type: Array,
    default: () => [
      { time: '10:00', title: '创建草稿单', operator: '张销售' },
      { time: '10:15', title: '修改耗材数量为 100', operator: '张销售' },
      { time: '10:20', title: '通过底价校验', operator: '系统' },
    ],
  },
});
</script>

<template>
  <div class="qs-card p-3 flex flex-col gap-2 text-xs">
    <span class="font-semibold text-[var(--color-text)]">操作记录与流转日志</span>
    <div class="flex flex-col gap-1.5 border-l-2 border-[var(--color-border)] pl-3 ml-1">
      <div v-for="(log, idx) in logs" :key="idx" class="flex items-center justify-between text-[11px]">
        <div class="flex items-center gap-2">
          <span class="text-[var(--color-text-muted)] font-mono">{{ log.time }}</span>
          <span class="text-[var(--color-text)]">{{ log.title }}</span>
        </div>
        <span class="text-[var(--color-text-muted)]">{{ log.operator }}</span>
      </div>
    </div>
  </div>
</template>
