import { createMemoryHistory, createRouter } from 'vue-router'

// 报价版路由（前端 exe / Electron）：仅落地页，memory history（file:// 协议下无 URL 路径）。
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('./views/LandingView.vue'),
      meta: { title: '商业报价方案' }
    }
  ],
  scrollBehavior: () => ({ top: 0 })
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '商业报价'} - QuoteSys 通用商业报价系统`
})

export default router
