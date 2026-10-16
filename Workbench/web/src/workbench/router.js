import { createWebHashHistory, createRouter } from 'vue-router'
import { hasToken } from './api/workbenchClient'

// 工作台路由（由后端托管在浏览器，hash history 免服务端 fallback 重写）。
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/workbench/products' },
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
        { path: '', redirect: '/workbench/products' },
        {
          path: 'products',
          name: 'workbench-products',
          component: () => import('./views/ProductsManager.vue'),
          meta: { title: '商品中心', requiresAuth: true }
        },
        {
          path: 'quotes',
          name: 'workbench-quotes',
          component: () => import('./views/QuotesCenter.vue'),
          meta: { title: '报价中心', requiresAuth: true }
        },
        {
          path: 'employees',
          name: 'workbench-employees',
          component: () => import('./views/EmployeesManager.vue'),
          meta: { title: '员工管理', requiresAuth: true }
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
          path: 'designer',
          name: 'workbench-designer',
          component: () => import('../designer/DesignerContainer.vue'),
          meta: { title: '系统设计', requiresAuth: true }
        },
        {
          path: 'settings',
          name: 'workbench-settings',
          component: () => import('./views/SettingsManager.vue'),
          meta: { title: '基本设置', requiresAuth: true }
        },
        // 兼容重定向
        { path: 'devices', redirect: '/workbench/products' },
        { path: 'consumables', redirect: '/workbench/products' }
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
    return { name: 'workbench-products' }
  }
})

router.afterEach((to) => {
  document.title = `${to.meta.title || 'QuoteSys'} - QuoteSys 通用商业报价系统`
})

export default router
