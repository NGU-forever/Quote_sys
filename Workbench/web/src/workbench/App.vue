<script setup>
// 工作台根组件：仅渲染路由视图 + 全局 toast，不触发目录水合/图片同步（那是报价版职责）。
import { CheckCircle2, Info } from 'lucide-vue-next'
import { toastState } from '../shared/composables/useToast'
</script>

<template>
  <RouterView />
  <div class="toast-stack">
    <div v-for="toast in toastState.items" :key="toast.id" class="toast" :class="toast.type">
      <CheckCircle2 v-if="toast.type === 'success'" :size="16" />
      <Info v-else :size="16" />
      <span>{{ toast.message }}</span>
    </div>
  </div>
</template>
