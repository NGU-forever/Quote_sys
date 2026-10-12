<template>
  <div class="skeleton-mobile-single-column max-w-md mx-auto min-h-screen flex flex-col bg-[var(--color-bg)]">
    <header v-if="$slots.top_bar" class="top-bar sticky top-0 z-20 bg-[var(--color-surface)] border-b border-[var(--color-border)] p-3">
      <slot name="top_bar" />
    </header>

    <main class="content flex-1 p-3 flex flex-col gap-4 overflow-y-auto">
      <slot name="content" />
    </main>

    <footer v-if="$slots.bottom_bar" class="bottom-bar sticky bottom-0 z-20 bg-[var(--color-surface)] border-t border-[var(--color-border)] p-3 shadow-lg">
      <slot name="bottom_bar" />
    </footer>
  </div>
</template>
