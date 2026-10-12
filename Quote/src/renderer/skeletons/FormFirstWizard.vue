<template>
  <div class="skeleton-form-first-wizard max-w-4xl mx-auto flex flex-col gap-6 p-6">
    <header v-if="$slots.steps_header" class="steps-header w-full pb-4 border-b border-[var(--color-border)]">
      <slot name="steps_header" />
    </header>

    <div class="step-body flex-1 flex flex-col gap-6">
      <slot name="step_body" />
    </div>

    <footer v-if="$slots.step_footer" class="step-footer sticky bottom-0 z-10 pt-4 bg-[var(--color-bg)]">
      <slot name="step_footer" />
    </footer>
  </div>
</template>
