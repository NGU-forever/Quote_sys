<script setup>
/**
 * RuntimeShell：员工端/设计器预览共用的运行时外壳。
 *
 * 由 Spec 驱动整个系统：
 *   1. nav 段 → 顶部导航（RuntimeNav，渲染在 ThemeProvider 内部）
 *   2. modules 段 → 只有启用的模块才有对应屏幕与导航项
 *   3. screens 段 → 按当前激活屏切换渲染
 *   4. entities/output/rules → 由 SpecRenderer 注入 SpecContext 供各 Block 消费
 *   5. 区块事件 → 原样上抛给宿主（宿主适配器落到报价单 store）
 *
 * 此前员工端直接拼 ThemeProvider + LayoutEngine，既没有 #render-block 插槽
 * （区块根本不渲染，只剩空骨架），也没有注入 SpecContext。统一走这个外壳后，
 * 「设计器里看到的」与「员工实际用的」才是同一套渲染路径。
 */
import { computed, ref, watch } from 'vue';

import SpecRenderer from './SpecRenderer.vue';
import RuntimeNav from './RuntimeNav.vue';
import { getNavItems, resolveActiveScreenId } from './runtimeNav.js';

const props = defineProps({
  spec: { type: Object, required: true },
  data: { type: Object, default: () => ({}) },
  quoteSeq: { type: Number, default: 1 },
  /** 初始激活屏；留空取第一屏。用于深链，也让黄金屏能指定渲染某一屏。 */
  initialScreenId: { type: String, default: '' },
});

const emit = defineEmits([
  'add-item',
  'update-qty',
  'remove-item',
  'apply-bundle',
  'save-draft',
  'print-a4',
  'export-pdf',
]);

const navItems = computed(() => getNavItems(props.spec));
const activeScreenId = ref(resolveActiveScreenId(props.spec, props.initialScreenId));

// Spec 换了一套（逃生舱/重新定稿）时，把激活屏收敛回合法值，
// 否则会停留在上一套方案里不存在的屏幕 id 上。
watch(
  () => props.spec,
  (next) => {
    activeScreenId.value = resolveActiveScreenId(next, activeScreenId.value);
  }
);

function handleNavigate(screenId) {
  activeScreenId.value = resolveActiveScreenId(props.spec, screenId);
}
</script>

<template>
  <SpecRenderer
    :spec="spec"
    :data="data"
    :quote-seq="quoteSeq"
    :active-screen-id="activeScreenId"
    :total-amount="typeof data.totalAmount === 'number' ? data.totalAmount : null"
    @add-item="emit('add-item', $event)"
    @update-qty="emit('update-qty', $event)"
    @remove-item="emit('remove-item', $event)"
    @apply-bundle="emit('apply-bundle', $event)"
    @save-draft="emit('save-draft')"
    @print-a4="emit('print-a4')"
    @export-pdf="emit('export-pdf')"
  >
    <template #chrome="slotProps">
      <RuntimeNav :items="navItems" :active="activeScreenId" @navigate="handleNavigate" />
      <slot name="chrome" v-bind="slotProps" />
    </template>
  </SpecRenderer>
</template>
