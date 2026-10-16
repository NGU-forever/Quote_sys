<template>
  <div class="skeleton-list-detail-split flex w-full h-full gap-4 p-4 overflow-hidden">
    <!-- 左侧列表与过滤 -->
    <section class="left-pane w-1/2 flex flex-col gap-4 border-r border-[var(--color-border)] pr-4 overflow-y-auto">
      <div v-if="$slots.filters" class="filters-bar">
        <slot name="filters" />
      </div>
      <div class="list-container flex-1">
        <slot name="list" />
      </div>
    </section>

    <!-- 右侧详情与操作 -->
    <section class="right-pane w-1/2 flex flex-col gap-4 overflow-y-auto pl-2">
      <header v-if="$slots.detail_header">
        <slot name="detail_header" />
      </header>
      <div class="detail-body flex-1 flex flex-col gap-4">
        <slot name="detail_body" />
      </div>
      <footer v-if="$slots.detail_actions" class="sticky bottom-0 bg-[var(--color-bg)] pt-2">
        <slot name="detail_actions" />
      </footer>
    </section>
  </div>
</template>
