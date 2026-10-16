<script setup>
defineProps({
  summaryText: {
    type: String,
    required: true,
  },
  isFinalizing: {
    type: Boolean,
    default: false,
  },
  /** 摘要是否由模型参与生成（未配置模型时为 false，功能不降级） */
  llmEnabled: {
    type: Boolean,
    default: false,
  },
  /** 摘要来源：backend = 后端画像；local = 本地兜底 */
  summarySource: {
    type: String,
    default: 'local',
  },
  /** 后端给出的提示（如资料里没有套餐依据） */
  issues: {
    type: Array,
    default: () => [],
  },
  /** 资料术语口径提示（底价/供货价/同行价…） */
  terminologyHint: {
    type: String,
    default: '',
  },
  /** 后端不可达 / 未登录时的人话原因 */
  error: {
    type: String,
    default: '',
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

    <!-- 后端不可达/未登录：显式告知，不静默降级 -->
    <div
      v-if="error"
      class="w-full p-3 rounded-xl bg-amber-50 border border-amber-300 text-xs text-amber-900 text-left leading-relaxed"
    >
      <span class="font-bold">当前未能从工作台取到你的业务资料。</span>
      {{ error }}
    </div>

    <!-- 人话摘要大字展示框 -->
    <div class="p-6 rounded-2xl bg-blue-50/60 border border-blue-200 text-sm md:text-base text-gray-800 leading-relaxed text-left">
      {{ summaryText }}
    </div>

    <!-- 摘要依据：来源 / 术语口径 / 后端提示 -->
    <div class="w-full flex flex-wrap items-center justify-center gap-2 text-[11px]">
      <span
        v-if="summarySource === 'backend'"
        class="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold"
      >
        已按工作台里的真实资料生成
      </span>
      <span v-else class="px-2 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold">
        本地兜底文案（未连上工作台）
      </span>
      <span
        v-if="llmEnabled"
        class="px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 font-semibold"
      >
        已启用模型理解
      </span>
      <span v-else class="px-2 py-0.5 rounded bg-gray-100 text-gray-600">规则生成（未配模型）</span>
    </div>

    <p v-if="terminologyHint" class="text-xs text-gray-600 text-left w-full">
      {{ terminologyHint }}
    </p>

    <ul v-if="issues.length" class="text-xs text-amber-800 text-left w-full space-y-1">
      <li v-for="(issue, index) in issues" :key="index">· {{ issue }}</li>
    </ul>

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
