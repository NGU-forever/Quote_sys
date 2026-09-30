<script setup>
import { onMounted } from 'vue'
import { CheckCircle2, Info } from 'lucide-vue-next'
import { toastState, useToast } from '../shared/composables/useToast'
import { useCatalogStore } from '../shared/stores/catalog'
import { syncImages } from '../shared/utils/imageSync'
import { discoverAndSetHost } from '../shared/utils/discovery'

const catalog = useCatalogStore()
const { push: pushToast } = useToast()

// App 启动：先自动发现主设备（Electron）→ 再同步目录（服务器→缓存→内置逐级兜底）→ 同步图片。
// 只拉不推，绝不反向覆盖服务器数据；主设备不在线时静默降级，不打扰用户。
onMounted(async () => {
  await discoverAndSetHost()
  const source = await catalog.hydrateFromRemote()
  if (source === 'remote') pushToast('已同步主设备最新目录', 'info')
  else if (source === 'cache') pushToast('主设备不在线，已使用本地缓存目录', 'info')
  else pushToast('未连接主设备，已使用内置演示数据', 'info')
  const imgSync = await syncImages()
  if (imgSync && imgSync.ok && imgSync.total > 0) {
    pushToast(
      `产品图片已同步到本机（新增/更新 ${imgSync.downloaded} 张）`,
      'info'
    )
  }
})
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
