<script setup>
import { ref } from 'vue';

defineProps({
  ranking: {
    type: Array,
    default: () => ['order-entry', 'wholesale', 'management'],
  },
  sourceLabel: {
    type: String,
    default: '以下用行业样例演示，导入数据后会替换',
  },
  sampleData: {
    type: Object,
    default: () => null,
  },
});

const emit = defineEmits(['select-preset', 'start-wizard']);

// 演示可点原型内部的轻量联动状态
const demoCartQty = ref(1);

const PRESET_CARDS = {
  'order-entry': {
    id: 'order-entry',
    badge: '推荐 · 现场开单',
    title: '开单型',
    subtitle: '适合在客户现场开单：左边挑货，右边出单',
    accentColor: '#0B5FA5',
    skeletonDesc: 'catalog-left-form-right 骨架 / 舒适间距',
  },
  wholesale: {
    id: 'wholesale',
    badge: '批发 · 走量',
    title: '批发型',
    subtitle: '一屏看 20 个商品：适合商品多、快速录单',
    accentColor: '#175C8C',
    skeletonDesc: 'list-detail-split 骨架 / 紧凑等宽',
  },
  management: {
    id: 'management',
    badge: '管理 · 看板',
    title: '管理型',
    subtitle: '先看今天卖了多少，再点进去审批核单',
    accentColor: '#14532D',
    skeletonDesc: 'dashboard-grid 骨架 / 尊贵留白',
  },
};
</script>

<template>
  <div class="flex flex-col items-center w-full max-w-6xl mx-auto py-8 px-4 gap-6">
    <!-- 顶部来源与引导说明 -->
    <div class="text-center flex flex-col items-center gap-2">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
        <span class="w-2 h-2 rounded-full bg-blue-600 animate-pulse"></span>
        {{ sourceLabel }}
      </div>
      <h1 class="text-2xl font-bold text-gray-900 mt-1">选一套长得像你家生意的报价系统</h1>
      <p class="text-sm text-gray-500 max-w-lg">
        点击任意方案即可进入可点原型体验。选好后仅需确认几项偏好即可定稿，系统永远不会漂移。
      </p>
    </div>

    <!-- 三张可点原型卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 w-full mt-2">
      <div
        v-for="presetId in ranking"
        :key="presetId"
        class="border-2 rounded-xl p-5 bg-white shadow-sm hover:shadow-md hover:border-blue-500 cursor-pointer transition flex flex-col justify-between"
        :style="{ borderColor: PRESET_CARDS[presetId]?.accentColor || '#E5E7EB' }"
        @click="emit('select-preset', presetId)"
      >
        <div class="flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <span class="text-xs px-2.5 py-0.5 rounded-full font-semibold text-white" :style="{ backgroundColor: PRESET_CARDS[presetId]?.accentColor }">
              {{ PRESET_CARDS[presetId]?.badge }}
            </span>
            <span class="text-[11px] text-gray-400 font-mono">{{ PRESET_CARDS[presetId]?.skeletonDesc }}</span>
          </div>

          <div>
            <h3 class="text-lg font-bold text-gray-900">{{ PRESET_CARDS[presetId]?.title }}</h3>
            <p class="text-xs text-gray-600 mt-1 leading-relaxed">{{ PRESET_CARDS[presetId]?.subtitle }}</p>
          </div>

          <!-- 可点交互缩略卡片 -->
          <div class="border rounded-lg p-3 bg-gray-50 flex flex-col gap-2 text-xs">
            <div class="flex items-center justify-between text-[11px] text-gray-500 border-b pb-1.5">
              <span>真实演示数据预览</span>
              <span class="text-emerald-600 font-medium">✓ 已载入业务商品</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="font-medium text-gray-800 truncate max-w-[150px]">
                {{ sampleData?.products?.[0]?.name || '超声诊断仪主机' }}
              </span>
              <span class="font-bold text-blue-700">
                ¥{{ (sampleData?.products?.[0]?.min_price || 68000).toLocaleString() }}
              </span>
            </div>
            <div class="flex items-center justify-between text-[11px] bg-white p-1.5 rounded border">
              <span class="text-gray-500">模拟开单合计:</span>
              <span class="font-bold text-gray-900">
                ¥{{ ((sampleData?.products?.[0]?.min_price || 68000) * demoCartQty).toLocaleString() }}
              </span>
            </div>
          </div>
        </div>

        <button
          class="w-full mt-5 py-2.5 rounded-lg text-white font-medium text-xs text-center transition"
          :style="{ backgroundColor: PRESET_CARDS[presetId]?.accentColor }"
        >
          选用此套方案并继续 →
        </button>
      </div>
    </div>

    <!-- 底部逃生通道 -->
    <div class="mt-4 text-center">
      <button
        class="text-xs text-gray-500 hover:text-blue-600 underline cursor-pointer"
        @click="emit('start-wizard')"
      >
        都不太像？回答 8 个问题，我给你重新做
      </button>
    </div>
  </div>
</template>
