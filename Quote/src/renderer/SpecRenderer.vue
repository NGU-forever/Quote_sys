<script setup>
/**
 * SpecRenderer：把一个 UiSpec 渲染成完整界面。
 *
 * 职责边界（对应设计文档 §12）：
 * 1. 注入 SpecContext（entities / output / rules 供所有 block 消费）
 * 2. ThemeProvider 注入三层 token
 * 3. LayoutEngine 按骨架装配 block
 * 4. QuotePrintArea 由 output.quote_pdf 驱动打印版式
 * 5. 由 rules 派生的运行期数据：底价违规、报价单号
 *
 * 宿主（设计器预览 / 正式业务界面 / 黄金屏截图）都复用这一个组件，
 * 保证"设计器里看到的"与"客户实际用的"是同一套渲染逻辑。
 */
import { computed } from 'vue';

import LayoutEngine from './LayoutEngine.vue';
import QuotePrintArea from './QuotePrintArea.vue';
import ThemeProvider from './tokens/ThemeProvider.vue';
import { getBlockComponent } from './BlockRegistry.js';
import { listenersFor as buildListeners } from './blockEvents.js';
import { formatQuoteNo } from './SpecContext.js';
import { provideSpecContext } from './SpecProvider.js';

const props = defineProps({
  spec: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  quoteSeq: { type: Number, default: 1 },
  /**
   * 要渲染的屏幕 id。留空时渲染 screens[0]（黄金屏与单屏宿主的行为不变）。
   * 多屏切换由 RuntimeShell 负责，SpecRenderer 本身只渲染"一屏"。
   */
  activeScreenId: { type: String, default: '' },
  /**
   * 合计覆盖值。留空/null 时按行项目相加（原行为）。
   * 有套餐优惠时宿主应传入真实有效总价，避免定制屏的合计比经典视图偏高。
   */
  totalAmount: { type: Number, default: null },
});

// 区块事件 → 动态监听对象（映射逻辑见 blockEvents.js，可单测）
// 注意：defineEmits 必须用字面量（编译器宏不接受变量引用）
const emit = defineEmits([
  'add-item',
  'update-qty',
  'remove-item',
  'apply-bundle',
  'save-draft',
  'print-a4',
  'export-pdf',
]);

function listenersFor(blockType) {
  return buildListeners(blockType, emit);
}

const ctx = provideSpecContext(props.spec);

const screen = computed(() => {
  const screens = props.spec?.screens || [];
  if (props.activeScreenId) {
    return screens.find((item) => item.id === props.activeScreenId) || screens[0] || null;
  }
  return screens[0] || null;
});
const products = computed(() => props.data?.products || []);
const items = computed(() => props.data?.items || []);
const bundle = computed(() => props.data?.bundle || null);
const customer = computed(() => props.data?.customer || {});
const company = computed(
  () => props.data?.company || { name: '某某医疗科技有限公司', logo: '' }
);

const totalAmount = computed(() => {
  if (typeof props.totalAmount === 'number') return props.totalAmount;
  return items.value.reduce(
    (sum, item) => sum + Number(item.unit_price || 0) * Number(item.qty || 0),
    0
  );
});

/** 底价违规：既要有真实低价的明细，也要 rules.price_floor_guard 允许拦截 */
const hasViolation = computed(
  () => ctx.rule('price_floor_guard', true) && items.value.some((i) => i.floor_status === 'warn')
);

const quoteNo = computed(() =>
  formatQuoteNo(ctx.rule('quote_no_pattern'), { seq: props.quoteSeq })
);

const salesName = computed(
  () => props.data?.quote?.sales_name || props.data?.salesName || '销售经理'
);
</script>

<template>
  <ThemeProvider :preset-id="spec.style?.preset_id" :tokens="spec.style?.tokens">
    <slot name="chrome" :ctx="ctx" />

    <LayoutEngine v-if="screen" :screen="screen">
      <template #render-block="{ block }">
        <component
          :is="getBlockComponent(block.type)"
          v-bind="listenersFor(block.type)"
          :props="block.props"
          :products="products"
          :items="items"
          :total-amount="totalAmount"
          :has-violation="hasViolation"
          :bundle="bundle"
          :quote-no="quoteNo"
          :sales-name="salesName"
          :customer="customer"
        />
      </template>
    </LayoutEngine>

    <QuotePrintArea
      :items="items"
      :company="company"
      :customer="customer"
      :quote-no="quoteNo"
      :sales-name="salesName"
    />
  </ThemeProvider>
</template>
