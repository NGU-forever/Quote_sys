<script setup>
import { X } from 'lucide-vue-next'

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '' }
})

const emit = defineEmits(['close'])
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="wb-modal-overlay" @click.self="emit('close')">
      <div class="wb-modal" :style="width ? { width: `min(${width}, 100%)` } : undefined" role="dialog" aria-modal="true">
        <div class="wb-modal-head">
          <h2 class="wb-modal-title">{{ title }}</h2>
          <button class="wb-icon-btn" aria-label="关闭" @click="emit('close')">
            <X :size="18" />
          </button>
        </div>
        <div class="wb-modal-body">
          <slot />
        </div>
        <div v-if="$slots.footer" class="wb-modal-foot">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.wb-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.44);
  backdrop-filter: blur(2px);
}

.wb-modal {
  width: min(560px, 100%);
  max-height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 30px 80px -30px rgba(15, 23, 42, 0.6);
  overflow: hidden;
}

.wb-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.wb-modal-title {
  font-size: 16px;
  font-weight: 800;
}

.wb-icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  display: grid;
  place-items: center;
  color: var(--muted);
}

.wb-icon-btn:hover {
  background: var(--bg-alt);
  color: var(--text);
}

.wb-modal-body {
  padding: 20px;
  overflow-y: auto;
}

.wb-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: var(--bg-alt);
}
</style>
