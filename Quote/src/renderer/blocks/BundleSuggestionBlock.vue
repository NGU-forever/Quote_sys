<script setup>
defineProps({
  props: { type: Object, default: () => ({}) },
  bundle: { type: Object, default: () => null },
});

const emit = defineEmits(['apply-bundle']);
</script>

<template>
  <div v-if="bundle" class="p-3 rounded border border-emerald-200 bg-emerald-50 text-xs flex items-center justify-between">
    <div class="flex flex-col gap-0.5">
      <div class="flex items-center gap-2">
        <span class="font-bold text-emerald-900">推荐超值套餐: {{ bundle.name }}</span>
        <span class="bg-emerald-600 text-white text-[10px] px-1.5 py-0.2 rounded font-semibold">
          立省 ¥{{ (bundle.saving_amount || 0).toLocaleString() }}
        </span>
      </div>
      <span class="text-emerald-700 text-[11px]">{{ bundle.note || '含主机与配套耗材优惠组合' }}</span>
    </div>
    <button
      class="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-xs rounded font-medium transition"
      @click="emit('apply-bundle', bundle)"
    >
      选用套餐
    </button>
  </div>
</template>
