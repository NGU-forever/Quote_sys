import { createMemoryHistory, createRouter } from 'vue-router'

// 报价版路由（前端 exe / Electron）：仅落地页，memory history（file:// 协议下无 URL 路径）。
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('./views/LandingView.vue'),
      meta: { title: '超声波治疗解决方案' }
    }
  ],
  scrollBehavior: () => ({ top: 0 })
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '超声医疗'} - 超声医疗报价平台`
})

export default router
