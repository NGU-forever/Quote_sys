<template>
  <div class="skeleton-catalog-left-form-right flex w-full h-full gap-4 p-4 overflow-hidden box-border">
    <!-- 左侧挑货区 -->
    <aside class="left-rail w-80 flex-shrink-0 flex flex-col gap-4 overflow-y-auto">
      <slot name="left_rail" />
    </aside>

    <!-- 右侧开单主区 -->
    <main class="main-content flex-1 flex flex-col gap-4 overflow-y-auto">
      <header v-if="$slots.main_header" class="main-header flex flex-col gap-2">
        <slot name="main_header" />
      </header>

      <div class="main-body flex-1 flex flex-col gap-4">
        <slot name="main_body" />
      </div>

      <footer v-if="$slots.main_footer" class="main-footer sticky bottom-0 z-10 pt-2">
        <slot name="main_footer" />
      </footer>
    </main>
  </div>
</template>

<style scoped>
.skeleton-catalog-left-form-right {
  min-height: calc(100vh - 64px);
}

/*
 * 左栏必须自己滚动，不能把整页撑高。
 * 骨架的 overflow-y-auto 只有在高度受限时才生效，而宿主（页面/外壳）目前不给高度约束；
 * 真实目录有几十个商品时，未约束的左栏会把底部合计与导出按钮顶到屏幕外。
 * 这里用 max-height 兜住：商品少时（基准图场景）完全不生效，商品多时左栏内部滚动。
 */
.left-rail {
  max-height: calc(100vh - 128px);
}
</style>
