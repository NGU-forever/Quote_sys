<script setup>
const props = defineProps({
  summaryText: {
    type: String,
    required: true,
  },
  isFinalizing: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['confirm-finalize', 'modify-answers']);
</script>

<template>
  <div class="max-w-xl mx-auto w-full py-12 px-4 flex flex-col items-center text-center gap-6">
    <div class="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-xl font-bold">
      ✓
    </div>

    <div>
      <h2 class="text-2xl font-bold text-gray-900">确认一下，我理解得对不对？</h2>
      <p class="text-xs text-gray-500 mt-1">定稿后系统布局和规则将被永久冻结，业务数据不受影响</p>
    </div>

    <!-- 人话摘要大字展示框 -->
    <div class="p-6 rounded-2xl bg-blue-50/60 border border-blue-200 text-sm md:text-base text-gray-800 leading-relaxed text-left">
      {{ summaryText }}
    </div>

    <!-- 确认与修改按钮 -->
    <div class="flex flex-col sm:flex-row gap-3 w-full max-w-md mt-2">
      <button
        class="flex-1 py-3 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm shadow-sm transition disabled:opacity-50"
        :disabled="isFinalizing"
        @click="emit('confirm-finalize')"
      >
        {{ isFinalizing ? '正在定稿落库...' : '理解完全正确，一键定稿开工 ✓' }}
      </button>
      <button
        class="py-3 px-5 rounded-xl border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium text-xs transition"
        :disabled="isFinalizing"
        @click="emit('modify-answers')"
      >
        我想再改改
      </button>
    </div>
  </div>
</template>
