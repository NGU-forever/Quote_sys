<script setup>
/**
 * QuotePrintArea：由 output.quote_pdf 驱动的打印 / PDF 版式。
 *
 * 屏幕上隐藏（.quote-print-area 由全局样式 display:none），打印时独占页面。
 * 与屏幕样式完全隔离：纸张、页眉、表格线、是否显示底价、条款都取自 Spec。
 */
import { computed, onBeforeUnmount, onMounted } from 'vue';

import { formatMoney } from './SpecContext.js';
import { useSpecContext } from './SpecProvider.js';

const props = defineProps({
  items: { type: Array, default: () => [] },
  company: { type: Object, default: () => ({ name: '某某医疗科技有限公司', logo: '' }) },
  customer: { type: Object, default: () => ({}) },
  quoteNo: { type: String, default: '' },
  salesName: { type: String, default: '' },
});

const ctx = useSpecContext();
const config = computed(() => ctx.printConfig);
const showFloorPrice = computed(() => ctx.showsFloorPrice());

const PAPER_SIZES = {
  A4: 'A4 portrait',
  A5: 'A5 portrait',
  Letter: 'Letter portrait',
};

const totalAmount = computed(() =>
  props.items.reduce((sum, item) => sum + Number(item.unit_price || 0) * Number(item.qty || 0), 0)
);

const termsText = computed(() => {
  const block = config.value.terms_block;
  if (!block || block === 'company_default') {
    return '1. 本报价单有效期以单据标注为准，逾期需重新确认。\n2. 报价含税不含运费，特殊条款以合同为准。\n3. 设备质保期与耗材效期以厂家标准为准。';
  }
  return String(block);
});

const headerAlign = computed(() => {
  switch (config.value.header_style) {
    case 'centered':
      return 'text-center';
    case 'company_only':
      return 'text-left';
    default:
      return 'flex items-center justify-between';
  }
});

const tableClass = computed(() => {
  switch (config.value.table_style) {
    case 'striped':
      return 'qs-print-table qs-print-table--striped';
    case 'minimal':
      return 'qs-print-table qs-print-table--minimal';
    default:
      return 'qs-print-table qs-print-table--bordered';
  }
});

// @page 尺寸必须由真实样式表驱动（CSS 变量在 @page 中不可靠）
let styleEl = null;
function applyPageStyle() {
  if (typeof document === 'undefined') return;
  if (!styleEl) {
    styleEl = document.createElement('style');
    styleEl.id = 'qs-print-page';
    document.head.appendChild(styleEl);
  }
  const size = PAPER_SIZES[config.value.paper] || PAPER_SIZES.A4;
  styleEl.textContent = `@page { size: ${size}; margin: 12mm; }`;
}

onMounted(applyPageStyle);
onBeforeUnmount(() => {
  if (styleEl && styleEl.parentNode) styleEl.parentNode.removeChild(styleEl);
  styleEl = null;
});
</script>

<template>
  <div class="quote-print-area qs-print-area">
    <header :class="headerAlign">
      <div v-if="config.header_style !== 'company_only'" class="flex items-center gap-3">
        <img v-if="company.logo" :src="company.logo" alt="logo" class="h-10" />
        <div>
          <div class="text-base font-bold">{{ company.name }}</div>
          <div class="text-xs text-[var(--color-text-muted)]">报价单 / Quotation</div>
        </div>
      </div>
      <div class="text-xs text-right leading-5">
        <div>单号：{{ quoteNo || '—' }}</div>
        <div>业务员：{{ salesName || '—' }}</div>
        <div>客户：{{ customer.customer_name || '—' }}</div>
      </div>
    </header>

    <table :class="tableClass">
      <thead>
        <tr>
          <th class="w-10">#</th>
          <th>品名</th>
          <th class="w-16">单位</th>
          <th class="w-24">数量</th>
          <th class="w-28">单价</th>
          <th class="w-28">小计</th>
          <th v-if="showFloorPrice" class="w-28">底价</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, idx) in items" :key="item.sku_id || idx">
          <td>{{ idx + 1 }}</td>
          <td>{{ item.name }}</td>
          <td>{{ item.unit || '—' }}</td>
          <td class="qs-numeric">{{ item.qty ?? '—' }}</td>
          <td class="qs-numeric">{{ formatMoney(item.unit_price) }}</td>
          <td class="qs-numeric">
            {{ formatMoney(Number(item.unit_price || 0) * Number(item.qty || 0)) }}
          </td>
          <td v-if="showFloorPrice" class="qs-numeric">{{ formatMoney(item.floor_price) }}</td>
        </tr>
        <tr v-if="items.length === 0">
          <td :colspan="showFloorPrice ? 7 : 6" class="text-center text-[var(--color-text-muted)]">
            暂无明细
          </td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td :colspan="showFloorPrice ? 5 : 4" class="text-right font-semibold">合计</td>
          <td class="qs-numeric font-bold">{{ formatMoney(totalAmount) }}</td>
          <td v-if="showFloorPrice"></td>
        </tr>
      </tfoot>
    </table>

    <section class="qs-print-terms">
      <div class="text-xs font-semibold mb-1">条款与说明</div>
      <p class="text-xs whitespace-pre-line leading-5">{{ termsText }}</p>
    </section>
  </div>
</template>

<style scoped>
.qs-print-area {
  display: none;
  color: #111;
  background: #fff;
}

@media print {
  .qs-print-area {
    display: block;
    visibility: visible;
  }

  .qs-print-area * {
    visibility: visible;
  }

  .qs-print-area header {
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #999;
  }

  .qs-print-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-bottom: 12px;
  }

  .qs-print-table th,
  .qs-print-table td {
    padding: 4px 6px;
    text-align: left;
  }

  .qs-print-table--bordered th,
  .qs-print-table--bordered td {
    border: 1px solid #999;
  }

  .qs-print-table--striped tbody tr:nth-child(even) {
    background: #f2f2f2;
  }

  .qs-print-table--minimal th {
    border-bottom: 1px solid #333;
  }

  .qs-print-table--minimal td {
    border-bottom: 1px solid #ddd;
  }

  .qs-print-terms {
    border-top: 1px solid #ccc;
    padding-top: 8px;
  }
}
</style>
