import { createMemoryHistory, createRouter } from 'vue-router'

import { hasToken, isOfflineMode } from '../shared/auth/session'

// 报价版路由（前端 exe / Electron）：memory history（file:// 协议下无 URL 路径）。
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('./views/LandingView.vue'),
      meta: { title: '商业报价方案' }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('./views/LoginView.vue'),
      meta: { title: '销售端登录' }
    }
  ],
  scrollBehavior: () => ({ top: 0 })
})

/**
 * 员工需用自己的销售账号登录后才能开单 —— 服务端单据（官方单号、报价中心归档、
 * 行级隔离）都要求带令牌的 `POST /api/quotes`。
 *
 * 逃生通道：主设备不可达时允许「离线使用」，此时只能算价与存本地草稿。
 * 已登录用户访问 /login 时送回落地页；离线用户仍可进 /login 正式登录。
 */
router.beforeEach((to) => {
  if (to.name === 'login') {
    return hasToken() ? { name: 'landing' } : true
  }
  if (!hasToken() && !isOfflineMode()) {
    return { name: 'login' }
  }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '商业报价'} - QuoteSys 通用商业报价系统`
})

export default router
