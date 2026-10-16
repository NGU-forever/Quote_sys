<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  quotes: {
    type: Array,
    default: () => [
      { quoteNo: 'QT-20261012-0001', customer: '华东中心医院', amount: 86800, status: '生效中' },
      { quoteNo: 'QT-20261012-0002', customer: '仁爱康复中心', amount: 24500, status: '草稿' },
      { quoteNo: 'QT-20261011-0015', customer: '立新医疗诊所', amount: 11200, status: '已签约' },
    ],
  },
});
</script>

<template>
  <div class="qs-card overflow-hidden flex flex-col">
    <div class="p-3 bg-[var(--color-bg)] border-b border-[var(--color-border)] font-semibold text-sm">
      最近报价单动态
    </div>
    <table class="w-full text-left text-xs">
      <thead>
        <tr class="border-b border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]" style="height: var(--table-row-h);">
          <th class="p-2 pl-4">单号</th>
          <th class="p-2">客户</th>
          <th class="p-2">金额</th>
          <th class="p-2 pr-4 text-right">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="q in quotes" :key="q.quoteNo" class="border-b border-[var(--color-border)]" style="height: var(--table-row-h);">
          <td class="p-2 pl-4 font-mono text-[var(--color-text)]">{{ q.quoteNo }}</td>
          <td class="p-2">{{ q.customer }}</td>
          <td class="p-2 qs-numeric font-semibold text-[var(--color-primary)]">¥{{ q.amount.toLocaleString() }}</td>
          <td class="p-2 pr-4 text-right text-[var(--color-text-muted)]">{{ q.status }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
