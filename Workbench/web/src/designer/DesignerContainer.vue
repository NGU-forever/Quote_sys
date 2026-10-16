<script setup>
import { ref, onMounted, computed } from 'vue';
import { createWizardState, applyPresetToWizard } from './wizardState.js';
import { designerApi } from './designerClient.js';
import {
  buildLocalSummary,
  describeDesignerError,
  interpretProfileResponse,
} from './profileSummary.js';

import Screen0PreviewCards from './Screen0PreviewCards.vue';
import ScreenWizard from './ScreenWizard.vue';
import Screen8SummaryConfirm from './Screen8SummaryConfirm.vue';
import RuntimeShell from '../renderer/RuntimeShell.vue';

const state = ref(createWizardState());
const isFinalizing = ref(false);
const finalized = ref(false);
const ranking = ref(['order-entry', 'wholesale', 'management']);
const loadError = ref('');

// 第 8 屏摘要：后端画像为准，本地兜底
const profile = ref({
  summaryText: '',
  source: 'local',
  llmEnabled: false,
  issues: [],
  terminologyHint: '',
});

// 获取 signals 与样本数据
async function loadSignals() {
  try {
    const data = await designerApi.signals();
    ranking.value = data.ranking || ranking.value;
    state.value.sourceLevel = data.source_level;
    state.value.sourceLabel = data.sample_data?.source_label || state.value.sourceLabel;
    state.value.sampleData = data.sample_data;
    state.value.signals = data.signals;
    loadError.value = '';
  } catch (e) {
    // 后端不可达/未登录：保留内置离线默认值，但把原因显式告诉用户
    loadError.value = describeDesignerError(e);
  }
}

/**
 * 拉取业务画像与人话摘要。
 *
 * 摘要必须来自后端 —— 它会把库内画像、资料术语口径（底价/供货价/同行价）
 * 与可选的模型判断一起带进来；前端不再自己维护一份硬编码文案。
 * 失败时退回本地同构模板并标记 source='local'。
 */
async function loadProfile() {
  try {
    const payload = await designerApi.profile(state.value.answers);
    profile.value = interpretProfileResponse(payload, state.value.answers);
    loadError.value = '';
  } catch (e) {
    profile.value = interpretProfileResponse(null, state.value.answers);
    loadError.value = describeDesignerError(e);
  }
}

// 检查是否已有 active spec
async function checkActiveSpec() {
  try {
    const data = await designerApi.activeSpec();
    if (data && data.payload) {
      state.value.activeSpec = data.payload;
      finalized.value = true;
    }
  } catch (e) {
    // 未登录或尚未定稿：保持未定稿状态
    if (!loadError.value) loadError.value = describeDesignerError(e);
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
  loadProfile();
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
    loadProfile();
  }
}

function handlePrevStep() {
  if (state.value.currentStep > 1) {
    state.value.currentStep--;
  } else {
    state.value.currentStep = 0;
  }
}

// 第 8 步摘要：后端摘要优先，未取到时用本地同构模板兜底（不出现空白）
const summaryText = computed(
  () => profile.value.summaryText || buildLocalSummary(state.value.answers)
);

// 定稿
async function handleFinalize() {
  isFinalizing.value = true;
  try {
    const compiled = await designerApi.compile(state.value.answers);
    // 后端编译时会重算画像与摘要，用它刷新第 8 屏文案，保证"所见即所定"。
    if (compiled.summary_text) {
      profile.value = { ...profile.value, summaryText: compiled.summary_text, source: 'backend' };
    }
    await designerApi.finalize(compiled.spec);
    state.value.activeSpec = compiled.spec;
    finalized.value = true;
  } catch (e) {
    alert(`定稿提交失败：${describeDesignerError(e)}`);
  } finally {
    isFinalizing.value = false;
  }
}

// 逃生舱：重新走向导
async function handleResetEscape() {
  if (confirm('确定要重新走向导吗？这只会换一套界面设计，不会删除任何真实的商品与报价单。')) {
    try {
      await designerApi.reset();
    } catch {
      // 重置失败不阻塞本地退回向导
    }
    finalized.value = false;
    state.value.currentStep = 0;
    state.value.activeSpec = null;
    state.value.selectedPreset = null;
    profile.value = interpretProfileResponse(null, state.value.answers);
  }
}
</script>

<template>
  <div class="designer-main-container w-full min-h-screen bg-gray-50 flex flex-col">
    <!-- 如果已定稿：按当前生效的 UiSpec 进行运行时渲染（与员工端同一套外壳） -->
    <template v-if="finalized && state.activeSpec">
      <RuntimeShell
        v-if="state.activeSpec"
        :spec="state.activeSpec"
        :data="{
          products: state.sampleData?.products,
          items: state.sampleData?.demo_items,
          bundle: state.sampleData?.featured_package,
          quote: state.sampleData?.recent_quote,
        }"
      >
        <template #chrome>
          <div
            class="flex items-center justify-between px-4 py-2 bg-white border-b border-[var(--color-border)]"
          >
            <div class="flex items-center gap-3">
              <span class="font-bold text-sm text-[var(--color-text)]">QuoteSys 报价系统</span>
              <span
                class="text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold"
              >
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
        </template>
      </RuntimeShell>
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
        :llm-enabled="profile.llmEnabled"
        :issues="profile.issues"
        :terminology-hint="profile.terminologyHint"
        :summary-source="profile.source"
        :error="loadError"
        @confirm-finalize="handleFinalize"
        @modify-answers="state.currentStep = 1"
      />
    </template>
  </div>
</template>
