<script setup>
/**
 * RuntimeNav：由 Spec 的 nav 段驱动的系统导航。
 *
 * 必须渲染在 ThemeProvider 内部（RuntimeShell 通过 SpecRenderer 的 #chrome 插槽注入），
 * 这样导航配色跟随 spec.style.tokens，而不是写死一套颜色。
 *
 * 只有一屏时不渲染 —— 单屏系统不需要导航条。
 */
import { FileText, Package, Pencil, Settings, ShieldCheck, Users } from 'lucide-vue-next';

defineProps({
  items: { type: Array, default: () => [] },
  active: { type: String, default: '' },
});

const emit = defineEmits(['navigate']);

const ICONS = {
  edit: Pencil,
  file: FileText,
  shield: ShieldCheck,
  box: Package,
  users: Users,
  settings: Settings,
};

function iconFor(name) {
  return ICONS[name] || FileText;
}
</script>

<template>
  <nav v-if="items.length > 1" class="runtime-nav" aria-label="系统导航">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      class="runtime-nav-item"
      :class="{ 'is-active': item.id === active }"
      :aria-current="item.id === active ? 'page' : undefined"
      @click="emit('navigate', item.id)"
    >
      <component :is="iconFor(item.icon)" :size="15" />
      <span>{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.runtime-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  padding: 8px 12px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.runtime-nav-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}

.runtime-nav-item:hover {
  background: var(--color-bg);
  color: var(--color-text);
  border-color: var(--color-border);
}

.runtime-nav-item.is-active {
  background: var(--color-bg);
  color: var(--color-primary);
  border-color: var(--color-primary);
}
</style>
