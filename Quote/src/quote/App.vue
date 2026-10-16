<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { CheckCircle2, Info } from 'lucide-vue-next'
import { toastState, useToast } from '../shared/composables/useToast'
import { useCatalogStore } from '../shared/stores/catalog'
import { useAuthStore } from './stores/auth'
import { syncImages } from '../shared/utils/imageSync'
import { discoverAndSetHost } from '../shared/utils/discovery'

const router = useRouter()
const auth = useAuthStore()
const catalog = useCatalogStore()
const { push: pushToast } = useToast()

// App 启动：先自动发现主设备（Electron）→ 再同步目录（服务器→缓存→内置逐级兜底）→ 同步图片。
// 只拉不推，绝不反向覆盖服务器数据；主设备不在线时静默降级，不打扰用户。
// 最后校验登录令牌：过期就送回登录页，避免"看似已登录、开单却静默失败"。
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

  if ((await auth.verify()) === 'expired') {
    pushToast('登录已过期，请重新登录', 'info')
    router.replace({ name: 'login' })
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
