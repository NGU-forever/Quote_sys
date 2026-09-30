<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Check,
  Edit2,
  KeyRound,
  Lock,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
  UserPlus,
  Users,
  UserX
} from 'lucide-vue-next'
import WbModal from '../components/WbModal.vue'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'

const toast = useToast()

const employees = ref([])
const totalCount = ref(0)
const loading = ref(false)

// 筛选控制
const filters = reactive({
  keyword: '',
  role: 'all',
  isActive: 'all'
})

// 模态框控制
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showResetPwdModal = ref(false)

const submitting = ref(false)
const targetEmployee = ref(null)

// 新增员工表单
const createForm = reactive({
  username: '',
  password: '',
  real_name: '',
  phone: '',
  role: 'sales',
  is_active: true
})

// 编辑员工表单
const editForm = reactive({
  id: null,
  username: '',
  real_name: '',
  phone: '',
  role: 'sales',
  is_active: true
})

// 重置密码表单
const resetPwdForm = reactive({
  username: '',
  new_password: '',
  confirm_password: ''
})

// 角色预设与展示映射
const ROLE_MAP = {
  admin: { label: '系统管理员', class: 'role-admin', icon: ShieldAlert },
  manager: { label: '业务经理', class: 'role-manager', icon: ShieldCheck },
  sales: { label: '销售人员', class: 'role-sales', icon: Shield }
}

function getRoleMeta(role) {
  return ROLE_MAP[role] || { label: role || '未知角色', class: 'role-sales', icon: Shield }
}

// 统计各角色与状态计数
const stats = computed(() => {
  const all = employees.value || []
  let salesCount = 0
  let managerCount = 0
  let adminCount = 0
  let activeCount = 0

  all.forEach((emp) => {
    if (emp.role === 'admin') adminCount++
    else if (emp.role === 'manager') managerCount++
    else salesCount++

    if (emp.is_active !== false) activeCount++
  })

  return {
    total: all.length,
    salesCount,
    managerCount,
    adminCount,
    activeCount
  }
})

// 加载员工账号列表
async function loadEmployees() {
  loading.value = true
  try {
    const params = {}
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    if (filters.role !== 'all') params.role = filters.role
    if (filters.isActive === 'active') params.is_active = true
    if (filters.isActive === 'inactive') params.is_active = false

    const res = await api.listEmployees(params)
    employees.value = res.items || []
    totalCount.value = res.total || 0
  } catch (err) {
    toast.push(err.message || '获取员工账号列表失败', 'info')
  } finally {
    loading.value = false
  }
}

// 打开新增窗口
function openCreate() {
  Object.assign(createForm, {
    username: '',
    password: '',
    real_name: '',
    phone: '',
    role: 'sales',
    is_active: true
  })
  showCreateModal.value = true
}

// 提交创建员工
async function submitCreate() {
  if (!createForm.username.trim()) {
    toast.push('请填写登录用户名', 'info')
    return
  }
  if (!createForm.password || createForm.password.length < 6) {
    toast.push('初始登录密码至少需要 6 个字符', 'info')
    return
  }

  submitting.value = true
  try {
    await api.createEmployee({
      username: createForm.username.trim(),
      password: createForm.password,
      real_name: createForm.real_name.trim() || null,
      phone: createForm.phone.trim() || null,
      role: createForm.role,
      is_active: Boolean(createForm.is_active)
    })
    toast.push(`已成功创建员工账号「${createForm.username}」`)
    showCreateModal.value = false
    await loadEmployees()
  } catch (err) {
    toast.push(err.message || '创建员工账号失败', 'info')
  } finally {
    submitting.value = false
  }
}

// 打开编辑窗口
function openEdit(emp) {
  targetEmployee.value = emp
  Object.assign(editForm, {
    id: emp.id,
    username: emp.username,
    real_name: emp.real_name || '',
    phone: emp.phone || '',
    role: emp.role || 'sales',
    is_active: emp.is_active !== false
  })
  showEditModal.value = true
}

// 提交编辑员工
async function submitEdit() {
  if (!editForm.id) return
  submitting.value = true
  try {
    await api.updateEmployee(editForm.id, {
      real_name: editForm.real_name.trim() || null,
      phone: editForm.phone.trim() || null,
      role: editForm.role,
      is_active: Boolean(editForm.is_active)
    })
    toast.push('员工信息更新成功')
    showEditModal.value = false
    await loadEmployees()
  } catch (err) {
    toast.push(err.message || '更新员工信息失败', 'info')
  } finally {
    submitting.value = false
  }
}

// 快速切换启停状态
async function toggleActive(emp) {
  if (emp.username === 'admin' && emp.is_active) {
    toast.push('内置应急管理员账号不可停用', 'info')
    return
  }
  const nextStatus = !emp.is_active
  try {
    await api.updateEmployee(emp.id, { is_active: nextStatus })
    emp.is_active = nextStatus
    toast.push(nextStatus ? `账号「${emp.username}」已启用` : `账号「${emp.username}」已停用`)
  } catch (err) {
    toast.push(err.message || '切换状态失败', 'info')
  }
}

// 打开重置密码弹窗
function openResetPassword(emp) {
  targetEmployee.value = emp
  resetPwdForm.username = emp.username
  resetPwdForm.new_password = ''
  resetPwdForm.confirm_password = ''
  showResetPwdModal.value = true
}

// 提交重置密码
async function submitResetPassword() {
  if (!resetPwdForm.new_password || resetPwdForm.new_password.length < 6) {
    toast.push('新密码长度至少需要 6 个字符', 'info')
    return
  }
  if (resetPwdForm.new_password !== resetPwdForm.confirm_password) {
    toast.push('两次输入的新密码不一致，请重新检查', 'info')
    return
  }

  submitting.value = true
  try {
    if (targetEmployee.value?.id) {
      await api.updateEmployee(targetEmployee.value.id, { password: resetPwdForm.new_password })
    } else {
      await api.resetPassword(resetPwdForm.username, resetPwdForm.new_password)
    }
    toast.push(`账号「${resetPwdForm.username}」密码重置成功`)
    showResetPwdModal.value = false
  } catch (err) {
    toast.push(err.message || '重置密码失败', 'info')
  } finally {
    submitting.value = false
  }
}

onMounted(loadEmployees)
</script>

<template>
  <div class="wb-page">
    <!-- 顶部横幅 -->
    <div class="wb-page-head">
      <div class="wb-page-title-row">
        <div class="wb-head-chip employee">
          <Users :size="20" />
        </div>
        <div>
          <div class="wb-head-title-wrap">
            <h1 class="wb-page-title">员工管理</h1>
            <span class="wb-pill-total">共 {{ stats.total }} 位系统成员</span>
          </div>
          <p class="wb-page-sub">销售团队与管理人员账号创建、角色权限分配、安全状态及密码管理</p>
        </div>
      </div>
      <button class="btn btn-primary" @click="openCreate">
        <UserPlus :size="16" />
        新增员工账号
      </button>
    </div>

    <!-- 成员统计概览卡片 -->
    <div class="wb-stats-grid">
      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap blue">
          <Users :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.total }}</div>
          <div class="wb-stat-label">账号总数</div>
        </div>
      </div>

      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap green">
          <Shield :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.salesCount }}</div>
          <div class="wb-stat-label">销售代表</div>
        </div>
      </div>

      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap amber">
          <ShieldCheck :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.managerCount }}</div>
          <div class="wb-stat-label">业务经理</div>
        </div>
      </div>

      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap purple">
          <ShieldAlert :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.adminCount }}</div>
          <div class="wb-stat-label">系统管理员</div>
        </div>
      </div>
    </div>

    <!-- 筛选过滤条 -->
    <div class="wb-toolbar">
      <div class="wb-toolbar-left">
        <div class="wb-search">
          <Search :size="15" />
          <input
            v-model="filters.keyword"
            class="input"
            type="text"
            placeholder="搜索用户名 / 真实姓名 / 手机号…"
            @keyup.enter="loadEmployees"
          />
        </div>
        <select v-model="filters.role" class="wb-select" @change="loadEmployees">
          <option value="all">全部角色</option>
          <option value="sales">销售人员 (sales)</option>
          <option value="manager">业务经理 (manager)</option>
          <option value="admin">系统管理员 (admin)</option>
        </select>
        <select v-model="filters.isActive" class="wb-select" @change="loadEmployees">
          <option value="all">全部状态</option>
          <option value="active">正常启用</option>
          <option value="inactive">已停用</option>
        </select>
      </div>
      <div class="wb-toolbar-right">
        <button class="wb-refresh-btn" title="刷新列表" @click="loadEmployees">
          <RefreshCw :size="14" :class="{ spin: loading }" />
        </button>
      </div>
    </div>

    <!-- 员工列表表格 -->
    <div class="wb-table-wrap">
      <table class="wb-table">
        <thead>
          <tr>
            <th style="width: 60px;">UID</th>
            <th style="width: 160px;">登录用户名</th>
            <th style="width: 140px;">真实姓名</th>
            <th style="width: 150px;">联系电话</th>
            <th style="width: 130px;">角色权限</th>
            <th style="width: 90px;">账号状态</th>
            <th style="width: 160px;">创建时间</th>
            <th class="ops" style="width: 140px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="empty">
              <RefreshCw :size="20" class="spin mb-2" />
              <div>加载员工账号列表中…</div>
            </td>
          </tr>
          <tr v-else-if="employees.length === 0">
            <td colspan="8" class="empty">
              <Users :size="28" style="opacity: 0.3; margin: 0 auto 8px;" />
              <div>暂无符合筛选条件的员工数据</div>
            </td>
          </tr>
          <tr v-for="emp in employees" v-else :key="emp.id">
            <!-- UID -->
            <td>
              <span class="wb-uid-badge">#{{ emp.id }}</span>
            </td>

            <!-- 用户名 -->
            <td>
              <div class="wb-user-cell">
                <div class="wb-user-avatar-small">
                  {{ (emp.username || 'U')[0].toUpperCase() }}
                </div>
                <div class="wb-user-uname">
                  <span>{{ emp.username }}</span>
                  <span v-if="emp.username === 'admin'" class="wb-reserved-badge">内置</span>
                </div>
              </div>
            </td>

            <!-- 姓名 -->
            <td>
              <span class="wb-real-name">{{ emp.real_name || '—' }}</span>
            </td>

            <!-- 电话 -->
            <td>
              <span class="wb-phone-cell">{{ emp.phone || '—' }}</span>
            </td>

            <!-- 角色 -->
            <td>
              <span class="wb-role-badge" :class="getRoleMeta(emp.role).class">
                <component :is="getRoleMeta(emp.role).icon" :size="12" />
                {{ getRoleMeta(emp.role).label }}
              </span>
            </td>

            <!-- 状态 -->
            <td>
              <button
                class="wb-status-toggle"
                :class="{ active: emp.is_active !== false, inactive: emp.is_active === false }"
                :title="emp.is_active !== false ? '点击停用' : '点击启用'"
                :disabled="emp.username === 'admin'"
                @click="toggleActive(emp)"
              >
                <span class="wb-dot"></span>
                <span>{{ emp.is_active !== false ? '正常' : '已停用' }}</span>
              </button>
            </td>

            <!-- 创建时间 -->
            <td>
              <span class="wb-time-cell">{{ emp.created_at || '—' }}</span>
            </td>

            <!-- 操作 -->
            <td class="ops">
              <button class="wb-row-btn" title="编辑信息" @click="openEdit(emp)">
                <Pencil :size="14" />
              </button>
              <button class="wb-row-btn warning" title="重置密码" @click="openResetPassword(emp)">
                <KeyRound :size="14" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增员工账号弹窗 -->
    <WbModal
      :open="showCreateModal"
      title="新增员工账号"
      width="540px"
      @close="showCreateModal = false"
    >
      <div class="wb-form">
        <!-- 用户名 -->
        <div class="wb-form-row">
          <label>登录用户名 <span class="required">*</span></label>
          <input
            v-model="createForm.username"
            class="input"
            type="text"
            placeholder="例如：sales_zhang"
          />
        </div>

        <!-- 初始密码 -->
        <div class="wb-form-row">
          <label>初始登录密码 <span class="required">*</span></label>
          <input
            v-model="createForm.password"
            class="input"
            type="password"
            placeholder="至少 6 位密码"
          />
        </div>

        <!-- 真实姓名 -->
        <div class="wb-form-row">
          <label>真实姓名</label>
          <input
            v-model="createForm.real_name"
            class="input"
            type="text"
            placeholder="例如：张晓明"
          />
        </div>

        <!-- 联系手机 -->
        <div class="wb-form-row">
          <label>联系手机号</label>
          <input
            v-model="createForm.phone"
            class="input"
            type="text"
            placeholder="例如：13800000000"
          />
        </div>

        <!-- 角色权限 -->
        <div class="wb-form-row full">
          <label>系统角色分配 <span class="required">*</span></label>
          <div class="wb-role-selector">
            <label class="wb-role-option" :class="{ on: createForm.role === 'sales' }">
              <input v-model="createForm.role" type="radio" value="sales" />
              <div class="wb-role-option-info">
                <div class="role-title">销售人员 (sales)</div>
                <div class="role-desc">可开具并提交报价单，仅查看个人业绩</div>
              </div>
            </label>

            <label class="wb-role-option" :class="{ on: createForm.role === 'manager' }">
              <input v-model="createForm.role" type="radio" value="manager" />
              <div class="wb-role-option-info">
                <div class="role-title">业务经理 (manager)</div>
                <div class="role-desc">查看团队报价大盘、价格配置与员工管理</div>
              </div>
            </label>

            <label class="wb-role-option" :class="{ on: createForm.role === 'admin' }">
              <input v-model="createForm.role" type="radio" value="admin" />
              <div class="wb-role-option-info">
                <div class="role-title">系统管理员 (admin)</div>
                <div class="role-desc">具备商品管理、系统核心配置与全量控制权限</div>
              </div>
            </label>
          </div>
        </div>

        <!-- 初始启用 -->
        <div class="wb-form-row full">
          <label class="wb-checkbox-label">
            <input v-model="createForm.is_active" type="checkbox" />
            <span>账号默认处于启用状态</span>
          </label>
        </div>
      </div>

      <template #footer>
        <button class="btn" @click="showCreateModal = false">取消</button>
        <button class="btn btn-primary" :disabled="submitting" @click="submitCreate">
          {{ submitting ? '创建中…' : '确认创建' }}
        </button>
      </template>
    </WbModal>

    <!-- 编辑员工信息弹窗 -->
    <WbModal
      :open="showEditModal"
      :title="`编辑员工账号：${editForm.username}`"
      width="520px"
      @close="showEditModal = false"
    >
      <div class="wb-form">
        <div class="wb-form-row full">
          <label>真实姓名</label>
          <input
            v-model="editForm.real_name"
            class="input"
            type="text"
            placeholder="真实姓名"
          />
        </div>

        <div class="wb-form-row full">
          <label>联系电话</label>
          <input
            v-model="editForm.phone"
            class="input"
            type="text"
            placeholder="手机号码"
          />
        </div>

        <div class="wb-form-row full">
          <label>角色权限</label>
          <select v-model="editForm.role" class="wb-select-full">
            <option value="sales">销售人员 (sales)</option>
            <option value="manager">业务经理 (manager)</option>
            <option value="admin">系统管理员 (admin)</option>
          </select>
        </div>

        <div class="wb-form-row full">
          <label class="wb-checkbox-label">
            <input
              v-model="editForm.is_active"
              type="checkbox"
              :disabled="editForm.username === 'admin'"
            />
            <span>账号启用状态</span>
          </label>
        </div>
      </div>

      <template #footer>
        <button class="btn" @click="showEditModal = false">取消</button>
        <button class="btn btn-primary" :disabled="submitting" @click="submitEdit">
          {{ submitting ? '保存中…' : '保存修改' }}
        </button>
      </template>
    </WbModal>

    <!-- 重置密码弹窗 -->
    <WbModal
      :open="showResetPwdModal"
      :title="`重置员工登录密码：${resetPwdForm.username}`"
      width="460px"
      @close="showResetPwdModal = false"
    >
      <div class="wb-form">
        <div class="wb-form-row full">
          <label>输入新登录密码 <span class="required">*</span></label>
          <input
            v-model="resetPwdForm.new_password"
            class="input"
            type="password"
            placeholder="至少 6 个字符"
          />
        </div>

        <div class="wb-form-row full">
          <label>确认新密码 <span class="required">*</span></label>
          <input
            v-model="resetPwdForm.confirm_password"
            class="input"
            type="password"
            placeholder="请再次输入新密码"
          />
        </div>
      </div>

      <template #footer>
        <button class="btn" @click="showResetPwdModal = false">取消</button>
        <button class="btn btn-primary" :disabled="submitting" @click="submitResetPassword">
          {{ submitting ? '提交中…' : '确认重置' }}
        </button>
      </template>
    </WbModal>
  </div>
</template>

<style scoped>
.wb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wb-page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.wb-page-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wb-head-chip.employee {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: none;
  background: #f3e8ff;
  color: #7e22ce;
}

.wb-head-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wb-page-title {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
}

.wb-pill-total {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-alt);
  color: var(--muted);
  border: 1px solid var(--border);
}

.wb-page-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}

/* 统计卡片栅格 */
.wb-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.wb-stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--border);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.wb-stat-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  flex: none;
}

.wb-stat-icon-wrap.blue {
  background: #eff6ff;
  color: #2563eb;
}

.wb-stat-icon-wrap.green {
  background: #ecfdf5;
  color: #059669;
}

.wb-stat-icon-wrap.amber {
  background: #fef3c7;
  color: #d97706;
}

.wb-stat-icon-wrap.purple {
  background: #f5f3ff;
  color: #7c3aed;
}

.wb-stat-num {
  font-size: 20px;
  font-weight: 800;
  color: var(--text);
  line-height: 1.2;
}

.wb-stat-label {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

/* 工具栏 */
.wb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.wb-toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.wb-toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wb-search {
  position: relative;
  width: min(300px, 100%);
}

.wb-search svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.wb-search .input {
  width: 100%;
  padding-left: 36px;
  height: 38px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
}

.wb-select {
  height: 38px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 13px;
  color: var(--text);
  outline: none;
}

.wb-refresh-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--muted);
  cursor: pointer;
}

.wb-refresh-btn:hover {
  border-color: var(--primary);
  color: var(--text);
}

/* 表格容器 */
.wb-table-wrap {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow-x: auto;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.wb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
  min-width: 860px;
}

.wb-table th,
.wb-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: middle;
}

.wb-table th {
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.wb-table tbody tr:last-child td {
  border-bottom: none;
}

.wb-table tbody tr:hover {
  background: #fdfdfe;
}

.wb-table .ops {
  text-align: right;
  white-space: nowrap;
}

.wb-table .empty {
  text-align: center;
  color: var(--muted);
  padding: 48px 14px;
}

/* 单元格元素 */
.wb-uid-badge {
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: var(--muted);
  font-weight: 700;
}

.wb-user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wb-user-avatar-small {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #1e88e5, #64b5f6);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex: none;
}

.wb-user-uname {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  color: var(--text);
}

.wb-reserved-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  background: #fee2e2;
  color: #dc2626;
}

.wb-real-name {
  font-weight: 600;
  color: var(--text);
}

.wb-phone-cell {
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
  color: var(--muted);
}

/* 角色标签 */
.wb-role-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 24px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  white-space: nowrap;
}

.role-sales {
  background: #ecfdf5;
  color: #047857;
}

.role-manager {
  background: #eff6ff;
  color: #1d4ed8;
}

.role-admin {
  background: #f3e8ff;
  color: #7e22ce;
}

/* 状态切换按钮 */
.wb-status-toggle {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
}

.wb-status-toggle.active {
  background: #ecfdf5;
  color: #047857;
  border-color: #a7f3d0;
}

.wb-status-toggle.inactive {
  background: #f1f5f9;
  color: #64748b;
  border-color: #e2e8f0;
}

.wb-status-toggle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.wb-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.wb-time-cell {
  font-size: 12px;
  color: var(--muted);
}

.wb-row-btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  margin-left: 2px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.wb-row-btn:hover {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-row-btn.warning:hover {
  background: #fef3c7;
  color: #b45309;
}

/* 表单内部 */
.wb-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.wb-form-row {
  display: grid;
  gap: 6px;
}

.wb-form-row.full {
  grid-column: 1 / -1;
}

.wb-form-row label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.wb-form-row label .required {
  color: var(--rose);
}

.wb-select-full {
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 13.5px;
  color: var(--text);
  outline: none;
}

.wb-role-selector {
  display: grid;
  gap: 8px;
}

.wb-role-option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: #fff;
  transition: all 0.15s ease;
}

.wb-role-option:hover {
  border-color: var(--primary);
  background: var(--bg-alt);
}

.wb-role-option.on {
  border-color: var(--primary);
  background: #eff6ff;
}

.wb-role-option input {
  margin-top: 3px;
  accent-color: var(--primary);
}

.wb-role-option-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.role-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.role-desc {
  font-size: 11.5px;
  color: var(--muted);
}

.wb-checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px !important;
  color: var(--text) !important;
  font-weight: 500 !important;
  cursor: pointer;
}

.wb-checkbox-label input {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
}

.spin {
  animation: wb-spin 1s linear infinite;
}

@keyframes wb-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .wb-stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
