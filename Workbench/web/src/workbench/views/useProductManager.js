// src/workbench/views/useProductManager.js
// 设备管理 / 耗材管理 共用的产品增删改查 + 照片上传 + 设备-耗材绑定逻辑。
// 两个页面各自独立（独立路由、独立列表数据），此处只抽公共逻辑避免重复。
// bindTarget：设备页传 'consumables'（绑耗材），耗材页传 'devices'（绑设备）。
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api/workbenchClient'
import { useToast } from '../../shared/composables/useToast'

export function useProductManager({ category, bindTarget }) {
  const isDevice = category === 'device'
  const toast = useToast()

  const list = ref([])
  // 供绑定选择的对侧产品（设备页 = 耗材列表；耗材页 = 设备列表）
  const bindPool = ref([])
  const loading = ref(false)
  const keyword = ref('')
  const showForm = ref(false)
  const editingId = ref(null)
  const saving = ref(false)
  const fileInput = ref(null)
  const uploading = ref(false)

  const emptyForm = () => ({
    name: '',
    sku_id: '',
    min_price: '',
    max_price: '',
    unit: isDevice ? '台' : '袋',
    pieces_per_unit: '',
    units_per_box: '',
    box_price: '',
    applicable_devices: '',
    image: '',
    remark: '',
    // 绑定列表：设备页存绑定的耗材 sku，耗材页存绑定的设备 sku
    bound: []
  })

  const form = reactive(emptyForm())

  const filteredList = computed(() => {
    const k = keyword.value.trim()
    if (!k) return list.value
    return list.value.filter((item) =>
      `${item.name}${item.sku_id}${item.applicable_devices || ''}`.includes(k)
    )
  })

  async function load() {
    loading.value = true
    try {
      const [{ data }, bindRes] = await Promise.all([
        api.listProducts({ category }),
        api.listProducts({ category: bindTarget })
      ])
      list.value = data
      bindPool.value = bindRes.data
    } catch (err) {
      toast.push(err.message || '加载失败', 'info')
    } finally {
      loading.value = false
    }
  }

  function openCreate() {
    Object.assign(form, emptyForm())
    editingId.value = null
    showForm.value = true
  }

  function openEdit(item) {
    editingId.value = item.id
    Object.assign(form, {
      name: item.name || '',
      sku_id: item.sku_id || '',
      min_price: item.min_price ?? '',
      max_price: item.max_price ?? '',
      unit: item.unit || (isDevice ? '台' : '袋'),
      pieces_per_unit: item.pieces_per_unit ?? '',
      units_per_box: item.units_per_box ?? '',
      box_price: item.box_price ?? '',
      applicable_devices: item.applicable_devices || '',
      image: item.image || '',
      remark: item.remark || '',
      bound: isDevice
        ? [...(item.bound_consumables || [])]
        : [...(item.bound_devices || [])]
    })
    showForm.value = true
  }

  function toNum(value) {
    if (value === '' || value === null || value === undefined) return null
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }

  async function submit() {
    if (!form.name.trim()) {
      toast.push('请填写产品名称', 'info')
      return
    }
    saving.value = true
    const payload = {
      category,
      name: form.name.trim(),
      sku_id: form.sku_id.trim(),
      min_price: toNum(form.min_price),
      max_price: toNum(form.max_price),
      unit: form.unit,
      pieces_per_unit: toNum(form.pieces_per_unit),
      units_per_box: toNum(form.units_per_box),
      box_price: toNum(form.box_price),
      applicable_devices: form.applicable_devices.trim(),
      image: form.image.trim(),
      remark: form.remark.trim()
    }
    try {
      let savedId = editingId.value
      if (editingId.value) {
        await api.updateProduct(editingId.value, payload)
        toast.push('已保存修改')
      } else {
        const { data } = await api.createProduct(payload)
        savedId = data.id
        toast.push('已新增')
      }
      // 保存后同步绑定（整体替换；空数组 = 解除绑定，前端可自由搭配）
      if (savedId) {
        try {
          const bindPayload = isDevice
            ? { consumable_sku_ids: [...form.bound] }
            : { device_sku_ids: [...form.bound] }
          await api.updateProductBindings(savedId, bindPayload)
        } catch (err) {
          toast.push(`产品已保存，但绑定保存失败：${err.message}`, 'info')
        }
      }
      showForm.value = false
      await load()
    } catch (err) {
      toast.push(err.message || '保存失败', 'info')
    } finally {
      saving.value = false
    }
  }

  async function remove(item) {
    if (!window.confirm(`确定删除「${item.name}」？`)) return
    try {
      await api.deleteProduct(item.id)
      toast.push('已删除')
      await load()
    } catch (err) {
      toast.push(err.message || '删除失败', 'info')
    }
  }

  // ---- 产品照片上传（预留：照片设计完成后可随时对接） ----
  function pickPhoto() {
    fileInput.value?.click()
  }

  async function onPhotoSelected(event) {
    const file = event.target.files?.[0]
    event.target.value = '' // 允许重复选择同一文件
    if (!file) return
    if (!editingId.value) {
      toast.push('请先保存产品，再上传照片', 'info')
      return
    }
    uploading.value = true
    try {
      const { data } = await api.uploadProductPhoto(editingId.value, file)
      form.image = data.image || ''
      toast.push('照片已上传')
    } catch (err) {
      toast.push(err.message || '上传失败', 'info')
    } finally {
      uploading.value = false
    }
  }

  onMounted(load)

  return {
    isDevice,
    list,
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
    load,
    openCreate,
    openEdit,
    submit,
    remove,
    pickPhoto,
    onPhotoSelected
  }
}
