import { createWebHashHistory, createRouter } from 'vue-router'
import { hasToken } from './api/workbenchClient'

// 工作台路由（由后端 exe 托管在浏览器，hash history 免服务端 fallback 重写）。
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/workbench/devices' },
    {
      path: '/workbench/login',
      name: 'workbench-login',
      component: () => import('./views/LoginView.vue'),
      meta: { title: '工作台登录' }
    },
    {
      path: '/workbench',
      component: () => import('./views/WorkbenchLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/workbench/devices' },
        {
          path: 'devices',
          name: 'workbench-devices',
          component: () => import('./views/DevicesManager.vue'),
          meta: { title: '设备管理', requiresAuth: true }
        },
        {
          path: 'consumables',
          name: 'workbench-consumables',
          component: () => import('./views/ConsumablesManager.vue'),
          meta: { title: '耗材管理', requiresAuth: true }
        },
        {
          path: 'packages',
          name: 'workbench-packages',
          component: () => import('./views/PackagesManager.vue'),
          meta: { title: '套餐管理', requiresAuth: true }
        },
        {
          path: 'agent',
          name: 'workbench-agent',
          component: () => import('./views/AgentManager.vue'),
          meta: { title: '数据生成', requiresAuth: true }
        },
        {
          path: 'settings',
          name: 'workbench-settings',
          component: () => import('./views/SettingsManager.vue'),
          meta: { title: '基本设置', requiresAuth: true }
        }
      ]
    }
  ],
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  if (to.matched.some((record) => record.meta.requiresAuth) && !hasToken()) {
    return { name: 'workbench-login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'workbench-login' && hasToken()) {
    return { name: 'workbench-devices' }
  }
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '超声医疗'} - 超声医疗报价平台`
})

export default router
