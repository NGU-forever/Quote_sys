<template>
  <div class="skeleton-dashboard-grid flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full">
    <section v-if="$slots.stats_row" class="stats-row w-full">
      <slot name="stats_row" />
    </section>

    <div class="grid-content flex flex-col lg:flex-row gap-6 w-full">
      <section class="grid-left flex-1 flex flex-col gap-6">
        <slot name="grid_left" />
      </section>

      <section class="grid-right w-full lg:w-96 flex flex-col gap-6">
        <slot name="grid_right" />
      </section>
    </div>
  </div>
</template>
