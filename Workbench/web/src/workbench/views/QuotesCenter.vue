<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  DollarSign,
  Eye,
  FileSpreadsheet,
  FileText,
  Layers,
  Phone,
  RefreshCw,
  Search,
  User
} from 'lucide-vue-next'
import WbModal from '../components/WbModal.vue'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'
import { formatMoney } from '../../shared/utils/format'

const toast = useToast()

const quotes = ref([])
const totalCount = ref(0)
const loading = ref(false)

// 分页与筛选
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  keyword: '',
  customer: '',
  salesPerson: '',
  status: 'all'
})

// 详情模态框
const showDetailModal = ref(false)
const currentQuote = ref(null)
const loadingDetail = ref(false)

// 状态映射字典
const STATUS_MAP = {
  draft: { label: '草稿待定', class: 'status-draft' },
  submitted: { label: '已提交', class: 'status-submitted' },
  approved: { label: '已生效', class: 'status-approved' },
  rejected: { label: '已拒绝', class: 'status-rejected' },
  expired: { label: '已失效', class: 'status-expired' }
}

function getStatusBadge(status) {
  return STATUS_MAP[status] || { label: status || '未知', class: 'status-draft' }
}

// 统计数据计算
const stats = computed(() => {
  const all = quotes.value || []
  let totalAmount = 0
  let pendingCount = 0
  let approvedCount = 0

  all.forEach((q) => {
    totalAmount += Number(q.final_quote_price) || 0
    if (q.status === 'submitted') pendingCount++
    if (q.status === 'approved') approvedCount++
  })

  return {
    total: totalCount.value || all.length,
    totalAmount,
    pendingCount,
    approvedCount
  }
})

const totalPages = computed(() => {
  if (!totalCount.value) return 1
  return Math.ceil(totalCount.value / pageSize.value) || 1
})

function prevPage() {
  if (page.value > 1 && !loading.value) {
    page.value--
    loadQuotes()
  }
}

function nextPage() {
  if (page.value < totalPages.value && !loading.value) {
    page.value++
    loadQuotes()
  }
}

// 加载报价列表
async function loadQuotes() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value
    }
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    if (filters.customer.trim()) params.customer = filters.customer.trim()
    if (filters.salesPerson.trim()) params.sales_person = filters.salesPerson.trim()
    if (filters.status !== 'all') params.status = filters.status

    const res = await api.listQuotes(params)
    quotes.value = res.items || []
    totalCount.value = res.total || 0
  } catch (err) {
    toast.push(err.message || '加载报价单失败', 'info')
  } finally {
    loading.value = false
  }
}

function applySearch() {
  page.value = 1
  loadQuotes()
}

function resetSearch() {
  filters.keyword = ''
  filters.customer = ''
  filters.salesPerson = ''
  filters.status = 'all'
  page.value = 1
  loadQuotes()
}

const displayQuotes = computed(() => quotes.value)

// 查看报价详情
async function openDetail(quote) {
  loadingDetail.value = true
  showDetailModal.value = true
  currentQuote.value = quote
  try {
    const res = await api.getQuote(quote.quote_no)
    if (res) {
      currentQuote.value = res
    }
  } catch (err) {
    toast.push(err.message || '获取报价单详情失败', 'info')
  } finally {
    loadingDetail.value = false
  }
}

// 格式化折扣率
function formatDiscount(rate) {
  if (rate == null || rate === '') return '—'
  const n = Number(rate)
  if (isNaN(n)) return String(rate)
  if (n <= 1 && n > 0) {
    return `${(n * 100).toFixed(0)}%`
  }
  return `${n}%`
}

// 复制单号
function copyQuoteNo(quoteNo) {
  if (!quoteNo) return
  navigator.clipboard.writeText(quoteNo).then(() => {
    toast.push(`单号 ${quoteNo} 已复制到剪贴板`)
  }).catch(() => {
    toast.push('复制失败，请手动选择复制', 'info')
  })
}

// 计算快照列表
const snapshotItems = computed(() => {
  if (!currentQuote.value || !currentQuote.value.items_snapshot) return []
  const raw = currentQuote.value.items_snapshot
  if (Array.isArray(raw)) return raw
  try {
    return JSON.parse(raw) || []
  } catch {
    return []
  }
})

onMounted(loadQuotes)
</script>

<template>
  <div class="wb-page">
    <!-- 顶部横幅 -->
    <div class="wb-page-head">
      <div class="wb-page-title-row">
        <div class="wb-head-chip quote">
          <FileText :size="20" />
        </div>
        <div>
          <div class="wb-head-title-wrap">
            <h1 class="wb-page-title">报价中心</h1>
            <span class="wb-pill-total">全公司报价单汇总</span>
          </div>
          <p class="wb-page-sub">查看销售团队提报的正式报价单、审批状态、价格策略与商品明细快照</p>
        </div>
      </div>
      <button class="btn btn-secondary" @click="loadQuotes">
        <RefreshCw :size="15" :class="{ spin: loading }" />
        刷新列表
      </button>
    </div>

    <!-- 统计指示看板卡片 -->
    <div class="wb-stats-grid">
      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap blue">
          <FileSpreadsheet :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.total }}</div>
          <div class="wb-stat-label">报价单总数</div>
        </div>
      </div>

      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap amber">
          <Clock :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.pendingCount }}</div>
          <div class="wb-stat-label">待审核报价</div>
        </div>
      </div>

      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap green">
          <CheckCircle2 :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ stats.approvedCount }}</div>
          <div class="wb-stat-label">已通过生效</div>
        </div>
      </div>

      <div class="wb-stat-card">
        <div class="wb-stat-icon-wrap purple">
          <DollarSign :size="18" />
        </div>
        <div class="wb-stat-info">
          <div class="wb-stat-num">{{ formatMoney(stats.totalAmount, 0) }}</div>
          <div class="wb-stat-label">本页报价总额</div>
        </div>
      </div>
    </div>

    <!-- 多维检索筛选栏 -->
    <div class="wb-filter-box">
      <div class="wb-filter-grid">
        <!-- 综合关键字 -->
        <div class="wb-filter-field">
          <label>单号 / 综合检索</label>
          <div class="wb-input-with-icon">
            <Search :size="14" />
            <input
              v-model="filters.keyword"
              class="input"
              type="text"
              placeholder="单号 / 备注 / 客户"
              @keyup.enter="applySearch"
            />
          </div>
        </div>

        <!-- 客户名称 -->
        <div class="wb-filter-field">
          <label>客户单位</label>
          <input
            v-model="filters.customer"
            class="input"
            type="text"
            placeholder="客户单位全称或简称"
            @keyup.enter="applySearch"
          />
        </div>

        <!-- 经办销售 -->
        <div class="wb-filter-field">
          <label>经办销售人员</label>
          <input
            v-model="filters.salesPerson"
            class="input"
            type="text"
            placeholder="销售姓名 / 手机号"
            @keyup.enter="applySearch"
          />
        </div>

        <!-- 单据状态 -->
        <div class="wb-filter-field">
          <label>单据状态</label>
          <select v-model="filters.status" class="wb-select-field">
            <option value="all">全部状态</option>
            <option value="draft">草稿待定</option>
            <option value="submitted">已提交审核</option>
            <option value="approved">已审批生效</option>
            <option value="rejected">已拒绝退回</option>
            <option value="expired">已过期失效</option>
          </select>
        </div>
      </div>

      <div class="wb-filter-actions">
        <button class="btn btn-primary" @click="applySearch">
          <Search :size="14" />
          查询
        </button>
        <button class="btn" @click="resetSearch">
          重置
        </button>
      </div>
    </div>

    <!-- 报价单主表格 -->
    <div class="wb-table-wrap">
      <table class="wb-table">
        <thead>
          <tr>
            <th style="width: 170px;">报价单号</th>
            <th>客户单位</th>
            <th style="width: 140px;">经办销售</th>
            <th class="num" style="width: 110px;">目录原价</th>
            <th class="num" style="width: 80px;">折扣</th>
            <th class="num" style="width: 120px;">最终报价</th>
            <th style="width: 90px;">有效期</th>
            <th style="width: 95px;">状态</th>
            <th style="width: 150px;">创建时间</th>
            <th class="ops" style="width: 80px;">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="empty">
              <RefreshCw :size="20" class="spin mb-2" />
              <div>加载报价数据中…</div>
            </td>
          </tr>
          <tr v-else-if="displayQuotes.length === 0">
            <td colspan="10" class="empty">
              <FileText :size="28" style="opacity: 0.3; margin: 0 auto 8px;" />
              <div>暂无符合筛选条件的报价单</div>
            </td>
          </tr>
          <tr
            v-for="quote in displayQuotes"
            v-else
            :key="quote.id"
            class="wb-clickable-row"
            @click="openDetail(quote)"
          >
            <!-- 单号 -->
            <td>
              <div class="wb-quote-no-cell">
                <span class="wb-quote-no">{{ quote.quote_no }}</span>
                <button
                  class="wb-copy-btn"
                  title="复制单号"
                  @click.stop="copyQuoteNo(quote.quote_no)"
                >
                  <Copy :size="12" />
                </button>
              </div>
            </td>

            <!-- 客户单位 -->
            <td>
              <div class="wb-customer-cell">
                <span class="wb-customer-name">{{ quote.customer_name }}</span>
                <span v-if="quote.customer_contact" class="wb-customer-sub">
                  {{ quote.customer_contact }} {{ quote.customer_phone ? `(${quote.customer_phone})` : '' }}
                </span>
              </div>
            </td>

            <!-- 销售人员 -->
            <td>
              <div class="wb-sales-cell">
                <span class="wb-sales-name">{{ quote.sales_name || '—' }}</span>
                <span v-if="quote.sales_phone" class="wb-sales-phone">{{ quote.sales_phone }}</span>
              </div>
            </td>

            <!-- 目录总价 -->
            <td class="num">
              <span class="wb-list-price">{{ formatMoney(quote.total_list_price) }}</span>
            </td>

            <!-- 折扣率 -->
            <td class="num">
              <span class="wb-discount-badge">{{ formatDiscount(quote.discount_rate) }}</span>
            </td>

            <!-- 最终报价 -->
            <td class="num price">
              <span class="wb-final-price">{{ formatMoney(quote.final_quote_price) }}</span>
            </td>

            <!-- 有效期 -->
            <td>
              <span class="wb-valid-days">{{ quote.valid_days || 30 }} 天</span>
            </td>

            <!-- 状态 -->
            <td>
              <span class="wb-status-tag" :class="getStatusBadge(quote.status).class">
                {{ getStatusBadge(quote.status).label }}
              </span>
            </td>

            <!-- 创建时间 -->
            <td>
              <span class="wb-time-cell">{{ quote.created_at || '—' }}</span>
            </td>

            <!-- 操作 -->
            <td class="ops" @click.stop>
              <button class="btn btn-sm" title="查看明细" @click="openDetail(quote)">
                <Eye :size="14" />
                详情
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页控制器 -->
    <div class="wb-pagination-bar">
      <div class="wb-pagination-info">
        共 <span class="wb-page-highlight">{{ totalCount }}</span> 条报价单，当前第 {{ page }} / {{ totalPages }} 页
      </div>
      <div class="wb-pagination-controls">
        <button
          class="wb-page-btn"
          :disabled="page <= 1 || loading"
          title="上一页"
          @click="prevPage"
        >
          <ChevronLeft :size="15" />
          <span>上一页</span>
        </button>
        <span class="wb-page-current">{{ page }}</span>
        <button
          class="wb-page-btn"
          :disabled="page >= totalPages || loading"
          title="下一页"
          @click="nextPage"
        >
          <span>下一页</span>
          <ChevronRight :size="15" />
        </button>
      </div>
    </div>

    <!-- 报价详情模态弹窗 -->
    <WbModal
      :open="showDetailModal"
      :title="`报价单明细：${currentQuote?.quote_no || ''}`"
      width="860px"
      @close="showDetailModal = false"
    >
      <div v-if="currentQuote" class="wb-detail-body">
        <!-- 头部摘要状态条 -->
        <div class="wb-detail-summary-bar">
          <div class="wb-summary-left">
            <span class="wb-detail-quote-no">{{ currentQuote.quote_no }}</span>
            <span class="wb-status-tag" :class="getStatusBadge(currentQuote.status).class">
              {{ getStatusBadge(currentQuote.status).label }}
            </span>
          </div>
          <div class="wb-summary-right">
            <span class="wb-summary-date"><Calendar :size="13" /> 提交时间：{{ currentQuote.created_at }}</span>
            <span class="wb-summary-valid"><Clock :size="13" /> 报价有效期：{{ currentQuote.valid_days || 30 }} 天</span>
          </div>
        </div>

        <!-- 客户与经办人两列信息卡片 -->
        <div class="wb-detail-info-grid">
          <!-- 客户卡片 -->
          <div class="wb-detail-card">
            <div class="wb-detail-card-head">
              <User :size="15" />
              <span>客户单位信息</span>
            </div>
            <div class="wb-detail-card-content">
              <div class="wb-detail-item">
                <span class="label">单位名称</span>
                <span class="value strong">{{ currentQuote.customer_name }}</span>
              </div>
              <div class="wb-detail-item">
                <span class="label">联 系 人</span>
                <span class="value">{{ currentQuote.customer_contact || '—' }}</span>
              </div>
              <div class="wb-detail-item">
                <span class="label">联系电话</span>
                <span class="value">{{ currentQuote.customer_phone || '—' }}</span>
              </div>
            </div>
          </div>

          <!-- 经办销售卡片 -->
          <div class="wb-detail-card">
            <div class="wb-detail-card-head">
              <Phone :size="15" />
              <span>经办销售信息</span>
            </div>
            <div class="wb-detail-card-content">
              <div class="wb-detail-item">
                <span class="label">销售姓名</span>
                <span class="value strong">{{ currentQuote.sales_name || '—' }}</span>
              </div>
              <div class="wb-detail-item">
                <span class="label">联系电话</span>
                <span class="value">{{ currentQuote.sales_phone || '—' }}</span>
              </div>
              <div class="wb-detail-item">
                <span class="label">用户 ID</span>
                <span class="value text-muted">UID-{{ currentQuote.user_id || '—' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 价格总计看板 -->
        <div class="wb-price-dashboard">
          <div class="wb-price-metric">
            <span class="metric-label">目录原价合计</span>
            <span class="metric-val">{{ formatMoney(currentQuote.total_list_price) }}</span>
          </div>
          <div class="wb-price-metric">
            <span class="metric-label">综合折扣率</span>
            <span class="metric-val highlight">{{ formatDiscount(currentQuote.discount_rate) }}</span>
          </div>
          <div class="wb-price-metric final">
            <span class="metric-label">最终成单报价（元）</span>
            <span class="metric-val price">{{ formatMoney(currentQuote.final_quote_price) }}</span>
          </div>
        </div>

        <!-- 报价备注说明 -->
        <div v-if="currentQuote.remark" class="wb-remark-box">
          <div class="wb-remark-label">报价备注与商务条款：</div>
          <div class="wb-remark-text">{{ currentQuote.remark }}</div>
        </div>

        <!-- 结构化商品快照表格 -->
        <div class="wb-snapshot-wrap">
          <div class="wb-snapshot-head">
            <div class="wb-snapshot-title">
              <Layers :size="16" />
              <span>报价商品清单快照 (共 {{ snapshotItems.length }} 项)</span>
            </div>
            <span class="wb-snapshot-sub">持久化保存时的商品规格与单价</span>
          </div>

          <div class="wb-snapshot-table-scroll">
            <table class="wb-snapshot-table">
              <thead>
                <tr>
                  <th style="width: 40px;">#</th>
                  <th>商品名称</th>
                  <th style="width: 100px;">SKU 编码</th>
                  <th style="width: 90px;">分类</th>
                  <th style="width: 130px;">规格型号</th>
                  <th class="num" style="width: 70px;">数量</th>
                  <th style="width: 60px;">单位</th>
                  <th class="num" style="width: 100px;">报价单价</th>
                  <th class="num" style="width: 110px;">小计金额</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="snapshotItems.length === 0">
                  <td colspan="9" class="empty">单据未包含商品明细快照</td>
                </tr>
                <tr v-for="(item, idx) in snapshotItems" v-else :key="idx">
                  <td>{{ idx + 1 }}</td>
                  <td>
                    <span class="wb-item-name">{{ item.name || item.product_name || '—' }}</span>
                  </td>
                  <td>
                    <span class="wb-sku">{{ item.sku_id || item.sku || '—' }}</span>
                  </td>
                  <td>
                    <span class="wb-item-cat">{{ item.category || '—' }}</span>
                  </td>
                  <td>
                    <span class="wb-item-spec">{{ item.spec || '—' }}</span>
                  </td>
                  <td class="num">
                    <strong>{{ item.quantity ?? item.qty ?? 1 }}</strong>
                  </td>
                  <td>{{ item.unit || '—' }}</td>
                  <td class="num">
                    {{ formatMoney(item.price ?? item.unit_price ?? 0) }}
                  </td>
                  <td class="num price">
                    {{ formatMoney(item.subtotal ?? ((item.quantity ?? 1) * (item.price ?? 0))) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <template #footer>
        <button class="btn" @click="copyQuoteNo(currentQuote?.quote_no)">
          <Copy :size="14" />
          复制单号
        </button>
        <button class="btn btn-primary" @click="showDetailModal = false">
          关闭
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

.wb-head-chip.quote {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: none;
  background: #eff6ff;
  color: #2563eb;
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

.wb-stat-icon-wrap.amber {
  background: #fef3c7;
  color: #d97706;
}

.wb-stat-icon-wrap.green {
  background: #ecfdf5;
  color: #059669;
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

/* 过滤框 */
.wb-filter-box {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.wb-filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.wb-filter-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wb-filter-field label {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}

.wb-input-with-icon {
  position: relative;
}

.wb-input-with-icon svg {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.wb-input-with-icon .input {
  width: 100%;
  padding-left: 32px;
}

.wb-select-field {
  height: 38px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 13.5px;
  color: var(--text);
  outline: none;
}

.wb-filter-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
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
  min-width: 980px;
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

.wb-table tbody tr.wb-clickable-row {
  cursor: pointer;
  transition: background 0.15s ease;
}

.wb-table tbody tr.wb-clickable-row:hover {
  background: #f8fafc;
}

.wb-table tbody tr:last-child td {
  border-bottom: none;
}

.wb-table .num {
  text-align: right;
}

.wb-table .price {
  color: var(--primary-dark);
  font-weight: 700;
  white-space: nowrap;
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

/* 单元格特定样式 */
.wb-quote-no-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.wb-quote-no {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--primary-dark);
}

.wb-copy-btn {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  color: var(--muted);
  cursor: pointer;
  background: var(--bg-alt);
}

.wb-copy-btn:hover {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-customer-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wb-customer-name {
  font-weight: 700;
  color: var(--text);
}

.wb-customer-sub {
  font-size: 12px;
  color: var(--muted);
}

.wb-sales-cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.wb-sales-name {
  font-weight: 600;
  color: var(--text);
}

.wb-sales-phone {
  font-size: 11.5px;
  color: var(--muted);
}

.wb-list-price {
  color: var(--muted);
  font-size: 12.5px;
  text-decoration: line-through;
}

.wb-discount-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: #fef3c7;
  color: #b45309;
}

.wb-final-price {
  font-size: 14px;
  font-weight: 800;
  color: #1e88e5;
}

.wb-valid-days {
  font-size: 12px;
  color: var(--muted);
}

.wb-time-cell {
  font-size: 12px;
  color: var(--muted);
}

/* 状态标签 */
.wb-status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.status-draft {
  background: #f1f5f9;
  color: #475569;
}

.status-submitted {
  background: #e0f2fe;
  color: #0369a1;
}

.status-approved {
  background: #dcfce7;
  color: #15803d;
}

.status-rejected {
  background: #ffe4e6;
  color: #be123c;
}

.status-expired {
  background: #fed7aa;
  color: #c2410c;
}

.btn-sm {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
}

/* 详情弹窗内部 */
.wb-detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wb-detail-summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 10px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
}

.wb-summary-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wb-detail-quote-no {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
}

.wb-summary-right {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: var(--muted);
}

.wb-summary-date,
.wb-summary-valid {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.wb-detail-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.wb-detail-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
}

.wb-detail-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.wb-detail-card-content {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wb-detail-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.wb-detail-item .label {
  color: var(--muted);
}

.wb-detail-item .value {
  color: var(--text);
}

.wb-detail-item .value.strong {
  font-weight: 700;
}

.wb-price-dashboard {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid var(--border);
}

.wb-price-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.wb-price-metric.final {
  border-left: 1px dashed var(--border);
  padding-left: 16px;
}

.metric-label {
  font-size: 12px;
  color: var(--muted);
}

.metric-val {
  font-size: 18px;
  font-weight: 800;
  color: var(--text);
}

.metric-val.highlight {
  color: #d97706;
}

.metric-val.price {
  color: #1e88e5;
  font-size: 20px;
}

.wb-remark-box {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fefce8;
  border: 1px solid #fef08a;
  font-size: 13px;
}

.wb-remark-label {
  font-weight: 700;
  color: #854d0e;
  margin-bottom: 4px;
}

.wb-remark-text {
  color: #713f12;
  line-height: 1.5;
}

.wb-snapshot-wrap {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.wb-snapshot-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-alt);
  border-bottom: 1px solid var(--border);
}

.wb-snapshot-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  font-weight: 700;
}

.wb-snapshot-sub {
  font-size: 11px;
  color: var(--muted);
}

.wb-snapshot-table-scroll {
  max-height: 280px;
  overflow-y: auto;
}

.wb-snapshot-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}

.wb-snapshot-table th,
.wb-snapshot-table td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  text-align: left;
}

.wb-snapshot-table th {
  background: #f8fafc;
  color: var(--muted);
  font-weight: 700;
  position: sticky;
  top: 0;
}

.wb-snapshot-table .num {
  text-align: right;
}

.wb-snapshot-table .price {
  color: var(--primary-dark);
  font-weight: 700;
}

.wb-sku {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-alt);
  color: var(--muted);
  font-weight: 700;
}

.wb-item-name {
  font-weight: 600;
  color: var(--text);
}

.wb-item-cat {
  font-size: 11px;
  color: var(--muted);
}

.wb-item-spec {
  font-size: 11.5px;
  color: var(--muted);
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
  .wb-filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* 分页条样式 */
.wb-pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.wb-pagination-info {
  font-size: 13px;
  color: var(--muted);
}

.wb-page-highlight {
  font-weight: 700;
  color: var(--text);
}

.wb-pagination-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wb-page-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #fff;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.wb-page-btn:hover:not(:disabled) {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--bg-alt);
}

.wb-page-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.wb-page-current {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  background: var(--primary-light);
  color: var(--primary-dark);
  font-size: 13px;
  font-weight: 700;
}
</style>
