<script setup>
import { computed } from 'vue';
import { resolveTokens } from './presets.js';

const props = defineProps({
  presetId: {
    type: String,
    default: 'medical-clean',
  },
  tokens: {
    type: Object,
    default: () => ({}),
  },
});

const themeStyles = computed(() => {
  return resolveTokens(props.presetId, props.tokens);
});
</script>

<template>
  <div class="qs-themed-root w-full min-h-screen" :style="themeStyles">
    <slot />
  </div>
</template>

<style scoped>
@import './theme.css';
</style>
