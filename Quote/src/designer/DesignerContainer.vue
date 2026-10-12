<script setup>
import { ref, onMounted, computed } from 'vue';
import { createWizardState, applyPresetToWizard } from './wizardState.js';

import Screen0PreviewCards from './Screen0PreviewCards.vue';
import ScreenWizard from './ScreenWizard.vue';
import Screen8SummaryConfirm from './Screen8SummaryConfirm.vue';
import ThemeProvider from '../renderer/tokens/ThemeProvider.vue';
import LayoutEngine from '../renderer/LayoutEngine.vue';
import { getBlockComponent } from '../renderer/BlockRegistry.js';

const state = ref(createWizardState());
const isFinalizing = ref(false);
const finalized = ref(false);
const ranking = ref(['order-entry', 'wholesale', 'management']);

// 获取 signals 与样本数据
async function loadSignals() {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/designer/signals', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      ranking.value = data.ranking || ranking.value;
      state.value.sourceLevel = data.source_level;
      state.value.sourceLabel = data.sample_data?.source_label || state.value.sourceLabel;
      state.value.sampleData = data.sample_data;
      state.value.signals = data.signals;
    }
  } catch (e) {
    // 降级使用内置离线默认值
  }
}

// 检查是否已有 active spec
async function checkActiveSpec() {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/designer/spec');
    if (res.ok) {
      const data = await res.json();
      state.value.activeSpec = data.payload;
      finalized.value = true;
    }
  } catch (e) {
    // 尚未定稿
  }
}

onMounted(() => {
  loadSignals();
  checkActiveSpec();
});

// 第 0 屏选中预设
function handleSelectPreset(presetId) {
  applyPresetToWizard(state.value, presetId);
  // 直接前往第 8 步一键定稿确认
  state.value.currentStep = 8;
}

// 开启 8 步向导
function handleStartWizard() {
  state.value.currentStep = 1;
}

// 更新问卷答案
function handleUpdateAnswer({ key, value }) {
  state.value.answers[key] = value;
}

function handleNextStep() {
  if (state.value.currentStep < 7) {
    state.value.currentStep++;
  } else {
    state.value.currentStep = 8;
  }
}

function handlePrevStep() {
  if (state.value.currentStep > 1) {
    state.value.currentStep--;
  } else {
    state.value.currentStep = 0;
  }
}

// 生成第 8 步摘要
const summaryText = computed(() => {
  const ans = state.value.answers;
  const sellModeMap = {
    device_with_consumable: '设备与配套耗材',
    consumable_only: '高频耗材配件',
    service: '技术与解决方案服务',
    mixed: '综合软硬件品类',
  };
  const sceneMap = {
    on_site: '客户现场笔记本',
    office: '办公室电脑',
    mobile: '手机移动端',
  };
  const pricingMap = {
    floor_price: '按底价卖严禁议价',
    negotiable: '允许折让但超限需审批',
    tiered: '按批发数量自动阶梯价',
  };

  return (
    `我理解你是：向${ans.industry}销售${sellModeMap[ans.sell_mode] || '主要商品'}，` +
    `销售在${sceneMap[ans.scene] || '现场'}开单，` +
    `${pricingMap[ans.pricing_mode] || '底价模式'}，` +
    `报价单以${ans.output_target === 'print_a4' ? '打印 A4 纸质' : '高品质 PDF'}交付客户，` +
    `主色使用你的${ans.brand_color_name}。`
  );
});

// 定稿
async function handleFinalize() {
  isFinalizing.value = true;
  try {
    const compileRes = await fetch('http://127.0.0.1:8000/api/designer/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: state.value.answers }),
    });
    const compiled = await compileRes.json();

    const finalizeRes = await fetch('http://127.0.0.1:8000/api/designer/finalize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec: compiled.spec }),
    });

    if (finalizeRes.ok) {
      state.value.activeSpec = compiled.spec;
      finalized.value = true;
    }
  } catch (e) {
    alert('定稿提交失败，请重试');
  } finally {
    isFinalizing.value = false;
  }
}

// 逃生舱：重新走向导
async function handleResetEscape() {
  if (confirm('确定要重新走向导吗？这只会换一套界面设计，不会删除任何真实的商品与报价单。')) {
    try {
      await fetch('http://127.0.0.1:8000/api/designer/reset', { method: 'POST' });
    } catch (e) {}
    finalized.value = false;
    state.value.currentStep = 0;
    state.value.activeSpec = null;
  }
}
</script>

<template>
  <div class="designer-main-container w-full min-h-screen bg-gray-50 flex flex-col">
    <!-- 如果已定稿：按当前生效的 UiSpec 进行运行时渲染 -->
    <template v-if="finalized && state.activeSpec">
      <ThemeProvider
        :preset-id="state.activeSpec.style?.preset_id"
        :tokens="state.activeSpec.style?.tokens"
      >
        <div class="flex items-center justify-between px-4 py-2 bg-white border-b border-[var(--color-border)]">
          <div class="flex items-center gap-3">
            <span class="font-bold text-sm text-[var(--color-text)]">QuoteSys 报价系统</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">
              当前 Spec 已定稿冻结 (v{{ state.activeSpec.spec_version }})
            </span>
          </div>
          <button
            class="text-xs text-gray-500 hover:text-red-600 underline"
            @click="handleResetEscape"
          >
            换一套方案 (逃生舱)
          </button>
        </div>

        <LayoutEngine
          v-if="state.activeSpec.screens?.[0]"
          :screen="state.activeSpec.screens[0]"
        >
          <template #render-block="{ block }">
            <component
              :is="getBlockComponent(block.type)"
              :props="block.props"
              :products="state.sampleData?.products"
              :items="state.sampleData?.demo_items"
              :total-amount="98500"
              :has-violation="true"
              :bundle="state.sampleData?.featured_package"
            />
          </template>
        </LayoutEngine>
      </ThemeProvider>
    </template>

    <!-- 尚未定稿：显示设计器向导流程 -->
    <template v-else>
      <!-- 第 0 屏：三张可点原型 -->
      <Screen0PreviewCards
        v-if="state.currentStep === 0"
        :ranking="ranking"
        :source-label="state.sourceLabel"
        :sample-data="state.sampleData"
        @select-preset="handleSelectPreset"
        @start-wizard="handleStartWizard"
      />

      <!-- 步骤 1 ~ 7：向导问答 -->
      <ScreenWizard
        v-else-if="state.currentStep >= 1 && state.currentStep <= 7"
        :step="state.currentStep"
        :answers="state.answers"
        @update-answer="handleUpdateAnswer"
        @next-step="handleNextStep"
        @prev-step="handlePrevStep"
      />

      <!-- 步骤 8：人话确认定稿 -->
      <Screen8SummaryConfirm
        v-else-if="state.currentStep === 8"
        :summary-text="summaryText"
        :is-finalizing="isFinalizing"
        @confirm-finalize="handleFinalize"
        @modify-answers="state.currentStep = 1"
      />
    </template>
  </div>
</template>
