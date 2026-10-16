<script setup>
import { computed } from 'vue';
import { BLOCK_DEFAULT_SLOT, getSkeletonSlots } from './SpecLoader.js';

import CatalogLeftFormRight from './skeletons/CatalogLeftFormRight.vue';
import FormFirstWizard from './skeletons/FormFirstWizard.vue';
import ListDetailSplit from './skeletons/ListDetailSplit.vue';
import DashboardGrid from './skeletons/DashboardGrid.vue';
import MobileSingleColumn from './skeletons/MobileSingleColumn.vue';

const props = defineProps({
  screen: {
    type: Object,
    required: true,
  },
});

const skeletonComponent = computed(() => {
  switch (props.screen.skeleton) {
    case 'form-first-wizard':
      return FormFirstWizard;
    case 'list-detail-split':
      return ListDetailSplit;
    case 'dashboard-grid':
      return DashboardGrid;
    case 'mobile-single-column':
      return MobileSingleColumn;
    case 'catalog-left-form-right':
    default:
      return CatalogLeftFormRight;
  }
});

// 计算各槽位挂载的 blocks
const slottedBlocks = computed(() => {
  const sk = props.screen.skeleton || 'catalog-left-form-right';
  const slots = getSkeletonSlots(sk);
  const mapping = BLOCK_DEFAULT_SLOT[sk] || {};
  const res = {};
  slots.forEach((s) => {
    res[s] = [];
  });

  const blocks = props.screen.blocks || [];
  blocks.forEach((block) => {
    const targetSlot = mapping[block.type] || slots[0];
    if (res[targetSlot]) {
      res[targetSlot].push(block);
    } else {
      res[slots[0]].push(block);
    }
  });

  return res;
});
</script>

<template>
  <component :is="skeletonComponent">
    <template v-for="(blocks, slotName) in slottedBlocks" :key="slotName" #[slotName]>
      <div v-for="(block, idx) in blocks" :key="idx" class="w-full">
        <!-- 提供插槽给上层 BlockRegistry 渲染具体 Block -->
        <slot name="render-block" :block="block" />
      </div>
    </template>
  </component>
</template>
