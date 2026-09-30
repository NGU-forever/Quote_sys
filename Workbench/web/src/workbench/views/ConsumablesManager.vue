<script setup>
import { ImagePlus, Package, Pencil, Plus, Search, Trash2 } from 'lucide-vue-next'
import WbModal from '../components/WbModal.vue'
import { useProductManager } from './useProductManager'
import { formatMoney } from '../../shared/utils/format'
import { resolveImage } from '../../shared/utils/imageSync'

const {
  bindPool,
  loading,
  keyword,
  showForm,
  editingId,
  saving,
  fileInput,
  uploading,
  form,
  filteredList,
  openCreate,
  openEdit,
  submit,
  remove,
  pickPhoto,
  onPhotoSelected
} = useProductManager({ category: 'consumable', bindTarget: 'devices' })
</script>

<template>
  <div class="wb-page">
    <div class="wb-page-head">
      <div class="wb-page-title-row">
        <div class="wb-head-chip consumable">
          <Package :size="18" />
        </div>
        <div>
          <h1 class="wb-page-title">耗材管理</h1>
          <p class="wb-page-sub">医用耗材的目录、计价单位与绑定设备维护</p>
        </div>
      </div>
      <button class="btn btn-primary" @click="openCreate">
        <Plus :size="16" />
        新增耗材
      </button>
    </div>

    <div class="wb-toolbar">
      <div class="wb-search">
        <Search :size="15" />
        <input v-model="keyword" class="input" type="text" placeholder="搜索名称 / SKU / 适用设备" />
      </div>
      <span class="wb-count">共 {{ filteredList.length }} 项</span>
    </div>

    <div class="wb-table-wrap">
      <table class="wb-table">
        <thead>
          <tr>
            <th>SKU</th>
            <th>名称</th>
            <th>图片</th>
            <th class="num">最低价</th>
            <th class="num">最高价</th>
            <th>计价单位</th>
            <th class="num">每箱数量</th>
            <th>绑定设备</th>
            <th>适用设备</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="10" class="empty">加载中…</td>
          </tr>
          <tr v-else-if="filteredList.length === 0">
            <td colspan="10" class="empty">暂无耗材，点击右上角「新增耗材」开始录入</td>
          </tr>
          <tr v-for="item in filteredList" v-else :key="item.id">
            <td>
              <span class="wb-sku">{{ item.sku_id }}</span>
            </td>
            <td>
              <div class="wb-name-cell">
                <Package :size="15" class="wb-type-icon consumable" />
                <span>{{ item.name }}</span>
              </div>
            </td>
            <td>
              <img v-if="item.image" :src="resolveImage(item.image)" class="wb-thumb" alt="" @error="(e) => (e.target.style.display = 'none')" />
              <span v-else class="wb-thumb-empty">—</span>
            </td>
            <td class="num price">{{ item.min_price != null ? formatMoney(item.min_price, item.min_price % 1 ? 1 : 0) : '—' }}</td>
            <td class="num">{{ item.max_price != null ? formatMoney(item.max_price, item.max_price % 1 ? 1 : 0) : '—' }}</td>
            <td>{{ item.unit || '—' }}</td>
            <td class="num">{{ item.units_per_box ?? '—' }}</td>
            <td>
              <span v-if="item.bound_devices?.length" class="wb-bind-badge bound" title="该耗材已绑定设备，仅可在这些设备下搭配">
                已绑定 {{ item.bound_devices.length }} 款
              </span>
              <span v-else class="wb-bind-badge free" title="该耗材未绑定设备，可自由搭配任意设备">自由搭配</span>
            </td>
            <td>{{ item.applicable_devices || '—' }}</td>
            <td class="ops">
              <button class="wb-row-btn" title="编辑" @click="openEdit(item)">
                <Pencil :size="15" />
              </button>
              <button class="wb-row-btn danger" title="删除" @click="remove(item)">
                <Trash2 :size="15" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <WbModal :open="showForm" :title="`${editingId ? '编辑' : '新增'}耗材`" @close="showForm = false">
      <div class="wb-form">
        <div class="wb-form-row full">
          <label>名称</label>
          <input v-model="form.name" class="input" type="text" placeholder="例如：理疗电极片（7x10单孔）" />
        </div>
        <div class="wb-form-row">
          <label>SKU</label>
          <input v-model="form.sku_id" class="input" type="text" placeholder="留空自动生成" />
        </div>
        <div class="wb-form-row">
          <label>计价单位</label>
          <input v-model="form.unit" class="input" type="text" placeholder="袋/瓶/盒" />
        </div>
        <div class="wb-form-row">
          <label>最低价（元）</label>
          <input v-model="form.min_price" class="input" type="number" min="0" step="0.01" placeholder="0.00" />
        </div>
        <div class="wb-form-row">
          <label>最高价（元）</label>
          <input v-model="form.max_price" class="input" type="number" min="0" step="0.01" placeholder="可留空" />
        </div>
        <div class="wb-form-row">
          <label>每单位含量</label>
          <input v-model="form.pieces_per_unit" class="input" type="number" min="0" placeholder="如 2 贴/袋" />
        </div>
        <div class="wb-form-row">
          <label>每箱数量</label>
          <input v-model="form.units_per_box" class="input" type="number" min="0" placeholder="如 600 袋/箱" />
        </div>
        <div class="wb-form-row">
          <label>箱价（元）</label>
          <input v-model="form.box_price" class="input" type="number" min="0" step="0.01" placeholder="可留空" />
        </div>
        <div class="wb-form-row full">
          <label>绑定设备（多选；不选 = 不绑定，可在任意设备下搭配）</label>
          <div class="wb-bind-grid">
            <label
              v-for="d in bindPool"
              :key="d.sku_id"
              class="wb-bind-chip"
              :class="{ on: form.bound.includes(d.sku_id) }"
            >
              <input v-model="form.bound" type="checkbox" :value="d.sku_id" />
              <span>{{ d.sku_id }} · {{ d.name }}</span>
            </label>
            <p v-if="bindPool.length === 0" class="wb-bind-empty">
              暂无设备，请先到「设备管理」录入设备后再绑定
            </p>
          </div>
          <p class="wb-bind-note">
            绑定后，该耗材在套餐管理 / 报价计算器中只能在这些设备下搭配；未绑定的耗材可随意搭配。
          </p>
        </div>
        <div class="wb-form-row full">
          <label>适用设备（文本说明）</label>
          <input v-model="form.applicable_devices" class="input" type="text" placeholder="例如：经颅磁系列 / 中频、透药通用" />
        </div>
        <div class="wb-form-row full">
          <label>产品图片（照片预留：可填 URL 或上传本地图片）</label>
          <div class="wb-image-row">
            <input v-model="form.image" class="input" type="text" placeholder="图片 URL（如 /uploads/products/xxx.jpg）" />
            <button
              v-if="editingId"
              class="btn btn-soft btn-sm"
              type="button"
              :disabled="uploading"
              @click="pickPhoto"
            >
              <ImagePlus :size="14" />
              {{ uploading ? '上传中…' : '上传图片' }}
            </button>
            <input ref="fileInput" type="file" accept="image/*" hidden @change="onPhotoSelected" />
          </div>
          <img v-if="form.image" :src="resolveImage(form.image)" class="wb-image-preview" alt="图片预览" @error="(e) => (e.target.style.display = 'none')" />
          <span v-if="!editingId" class="wb-image-hint">保存后可在编辑中上传本地图片</span>
        </div>
        <div class="wb-form-row full">
          <label>备注</label>
          <textarea v-model="form.remark" class="textarea" placeholder="可选"></textarea>
        </div>
      </div>
      <template #footer>
        <button class="btn" @click="showForm = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="submit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </WbModal>
  </div>
</template>

<style scoped>
.wb-page {
  display: grid;
  gap: 18px;
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

.wb-head-chip {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: none;
}

.wb-head-chip.consumable {
  background: var(--teal-light);
  color: var(--teal);
}

.wb-page-title {
  font-size: 24px;
  font-weight: 800;
}

.wb-page-sub {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}

.wb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.wb-search {
  position: relative;
  width: min(320px, 100%);
}

.wb-search svg {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.wb-search .input {
  padding-left: 36px;
}

.wb-count {
  color: var(--muted);
  font-size: 13px;
  font-weight: 600;
}

.wb-table-wrap {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow-x: auto;
}

.wb-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
  min-width: 820px;
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
  padding: 36px 14px;
}

.wb-sku {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.wb-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 180px;
}

.wb-type-icon.consumable {
  color: var(--teal);
}

.wb-row-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
  color: var(--muted);
  margin-left: 4px;
}

.wb-row-btn:hover {
  background: var(--primary-light);
  color: var(--primary-dark);
}

.wb-row-btn.danger:hover {
  background: var(--rose-light);
  color: var(--rose);
}

.wb-thumb {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--border);
  background: var(--bg-alt);
  display: block;
}

.wb-thumb-empty {
  display: inline-grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--bg-alt);
  color: var(--muted);
  font-size: 13px;
}

.wb-bind-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  white-space: nowrap;
}

.wb-bind-badge.bound {
  background: var(--teal-light);
  color: var(--teal);
}

.wb-bind-badge.free {
  background: var(--bg-alt);
  color: var(--muted);
}

.wb-image-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wb-image-row .input {
  flex: 1;
}

.wb-image-preview {
  max-width: 140px;
  max-height: 90px;
  margin-top: 8px;
  border-radius: 10px;
  border: 1px solid var(--border);
  object-fit: cover;
}

.wb-image-hint {
  color: var(--muted);
  font-size: 12px;
  margin-top: 6px;
}

.wb-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.wb-form-row {
  display: grid;
  gap: 7px;
}

.wb-form-row.full {
  grid-column: 1 / -1;
}

.wb-form-row label {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.wb-bind-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
  padding: 4px;
}

.wb-bind-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  color: var(--text);
  font-size: 12.5px;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.wb-bind-chip:hover {
  border-color: var(--primary);
}

.wb-bind-chip.on {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary-dark);
  font-weight: 700;
}

.wb-bind-chip input {
  width: 15px;
  height: 15px;
  accent-color: var(--primary);
  flex: none;
}

.wb-bind-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wb-bind-empty {
  grid-column: 1 / -1;
  color: var(--muted);
  font-size: 12px;
  padding: 10px;
  background: var(--bg-alt);
  border-radius: 8px;
}

.wb-bind-note {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.6;
  margin-top: 4px;
}
</style>
