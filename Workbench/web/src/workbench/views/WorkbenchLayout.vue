<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FileText, Layers, LogOut, Package, Settings, ShieldCheck, Users } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const navItems = [
  { to: '/workbench/products', label: '商品中心', icon: Package },
  { to: '/workbench/quotes', label: '报价中心', icon: FileText },
  { to: '/workbench/employees', label: '员工管理', icon: Users },
  { to: '/workbench/packages', label: '套餐管理', icon: ShieldCheck },
  { to: '/workbench/settings', label: '基本设置', icon: Settings }
]

onMounted(() => {
  auth.fetchMe()
  refreshCatalog()
})

// 进入工作台时再拉一次服务器「母版目录」，保证管理/报价基于最新价目。
// 工作台属于主系统，直接用完整 client 拉取同步负载；只读拉取，不向服务器写入任何本地状态。
async function refreshCatalog() {
  try {
    const { data } = await api.getSync()
    if (data) toast.push('已同步服务器最新目录', 'info')
  } catch {
    /* 后端暂不可用时保持现有目录 */
  }
}

function logout() {
  auth.logout()
  toast.push('已退出登录', 'info')
  router.push('/')
}
</script>

<template>
  <div class="wb-shell">
    <aside class="wb-sidebar">
      <div class="wb-brand">
        <div class="wb-brand-mark"><ShieldCheck :size="18" /></div>
        <div>
          <div class="wb-brand-title-row">
            <div class="wb-brand-name">QuoteSys</div>
            <span class="wb-version-badge">v2.0.0</span>
          </div>
          <div class="wb-brand-sub">商业报价管理平台</div>
        </div>
      </div>

      <nav class="wb-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="wb-nav-item"
          :class="{ active: route.path.startsWith(item.to) }"
        >
          <component :is="item.icon" :size="17" />
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="wb-sidebar-foot">
        <div class="wb-user">
          <div class="wb-user-avatar">{{ (auth.user?.username || 'A')[0].toUpperCase() }}</div>
          <div class="wb-user-copy">
            <div class="wb-user-name">{{ auth.user?.username || '…' }}</div>
            <div class="wb-user-role">管理员</div>
          </div>
          <button class="wb-logout" aria-label="退出登录" @click="logout">
            <LogOut :size="16" />
          </button>
        </div>
      </div>
    </aside>

    <main class="wb-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.wb-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
  background: var(--bg-alt);
}

.wb-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 14px;
  background: #fff;
  border-right: 1px solid var(--border);
}

.wb-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 18px;
  border-bottom: 1px solid var(--border);
}

.wb-brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  box-shadow: 0 10px 20px -12px rgba(30, 136, 229, 0.9);
  flex: none;
}

.wb-brand-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wb-brand-name {
  font-size: 15px;
  font-weight: 800;
  line-height: 1.2;
}

.wb-version-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: #e0f2fe;
  color: #0369a1;
  line-height: 1.3;
}

.wb-brand-sub {
  color: var(--muted);
  font-size: 11px;
}

.wb-nav {
  display: grid;
  gap: 4px;
  margin-top: 8px;
  flex: 1;
  align-content: start;
}

.wb-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 9px;
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.wb-nav-item:hover {
  background: var(--bg-alt);
  color: var(--text);
}

.wb-nav-item.active {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-sidebar-foot {
  display: grid;
  gap: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.wb-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 10px;
  background: var(--bg-alt);
}

.wb-user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  font-size: 14px;
  font-weight: 800;
  flex: none;
}

.wb-user-copy {
  flex: 1;
  line-height: 1.2;
}

.wb-user-name {
  font-size: 13px;
  font-weight: 700;
}

.wb-user-role {
  color: var(--muted);
  font-size: 11px;
}

.wb-logout {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: var(--muted);
}

.wb-logout:hover {
  background: var(--rose-light);
  color: var(--rose);
}

.wb-main {
  min-width: 0;
  padding: 28px 32px 48px;
}

@media (max-width: 800px) {
  .wb-shell {
    grid-template-columns: 1fr;
  }

  .wb-sidebar {
    position: static;
    height: auto;
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 1px solid var(--border);
  }

  .wb-brand {
    border-bottom: none;
    padding: 0 8px 0 0;
  }

  .wb-nav {
    flex-direction: row;
    flex: none;
    margin-top: 0;
  }

  .wb-sidebar-foot {
    flex-direction: row;
    align-items: center;
    border-top: none;
    padding-top: 0;
    margin-left: auto;
  }

  .wb-main {
    padding: 20px 16px 40px;
  }
}
</style>
