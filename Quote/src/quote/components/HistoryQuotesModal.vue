<script setup>
import { History, RotateCcw, Trash, X } from 'lucide-vue-next'
import { useQuoteStore } from '../stores/quote'
import { formatMoney } from '../../shared/utils/format'

defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'restore'])
const quote = useQuoteStore()

function close() {
  emit('update:modelValue', false)
}

function handleRestore(item) {
  emit('restore', item)
}
</script>

<template>
  <div v-if="modelValue" class="modal-overlay" @click.self="close">
    <div class="modal-card history-modal" role="dialog" aria-modal="true" aria-label="本地历史报价草稿">
      <header class="modal-head">
        <div class="history-head-title">
          <History :size="18" />
          <h3 class="modal-title">本地历史报价草稿</h3>
          <span class="badge badge-blue">{{ quote.savedQuotes.length }} 条</span>
        </div>
        <button class="modal-close" type="button" aria-label="关闭" @click="close">
          <X :size="16" />
        </button>
      </header>

      <div class="modal-body">
        <div v-if="quote.savedQuotes.length === 0" class="history-empty">
          <p>暂无保存的报价草稿。导出报价单或点击“保存为草稿”后，记录会自动沉淀在这里。</p>
        </div>
        <div v-else class="history-list">
          <div v-for="item in quote.savedQuotes" :key="item.id" class="history-item-card">
            <div class="history-card-top">
              <div>
                <strong class="history-id">{{ item.id }}</strong>
                <span class="history-date">{{ item.date }}</span>
              </div>
              <span class="badge" :class="item.betterPlan === 'plan1' ? 'badge-blue' : 'badge-green'">
                {{ item.packageName || (item.mode === 'consumables' ? '仅购耗材' : item.mode === 'equipment' ? '仅购设备' : '方案1单独采购') }}
              </span>
            </div>

            <div class="history-card-body">
              <div class="history-specs">
                <span v-if="item.mode !== 'consumables'">设备: {{ item.devices }}台</span>
                <span v-if="item.mode !== 'equipment'">耗材: {{ item.boxes }}箱</span>
                <span v-if="item.packageSets">套餐: {{ item.packageSets }}套</span>
              </div>
              <div class="history-total">
                <span class="history-total-label">测算总额:</span>
                <strong class="history-total-price">¥{{ formatMoney(item.total) }}</strong>
              </div>
            </div>

            <div class="history-card-actions">
              <button class="btn btn-sm btn-soft" type="button" @click="handleRestore(item)">
                <RotateCcw :size="13" /> 载入选配参数
              </button>
              <button class="btn btn-sm btn-light text-danger" type="button" @click="quote.deleteQuote(item.id)">
                <Trash :size="13" /> 删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  padding: 20px;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(4px);
  overflow-y: auto;
}

.modal-card {
  display: flex;
  flex-direction: column;
  width: min(640px, 100%);
  max-height: calc(100vh - 40px);
  margin: auto;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 28px 70px -24px rgba(13, 71, 161, 0.55);
  overflow: hidden;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #fbfdff, #fff);
}

.history-head-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary-dark);
}

.modal-title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  color: var(--primary-dark);
}

.modal-close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: #fff;
  color: var(--muted);
  font-size: 14px;
  cursor: pointer;
}
.modal-close:hover {
  color: var(--text);
  background: var(--bg-alt);
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  overflow-y: auto;
}

.history-empty {
  text-align: center;
  padding: 40px 16px;
  color: var(--muted);
  font-size: 13px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item-card {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.15s ease;
}
.history-item-card:hover {
  border-color: var(--accent);
}

.history-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-id {
  font-size: 13px;
  color: var(--primary-dark);
  margin-right: 8px;
}
.history-date {
  font-size: 11px;
  color: var(--muted);
}

.history-card-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--muted);
}
.history-specs {
  display: flex;
  align-items: center;
  gap: 12px;
}
.history-total-price {
  font-size: 15px;
  font-weight: 800;
  color: var(--text);
  margin-left: 4px;
}

.history-card-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 6px;
  border-top: 1px dashed #f1f5f9;
}

.text-danger {
  color: var(--red);
}
</style>
