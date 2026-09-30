import { reactive } from 'vue'

export const toastState = reactive({ items: [] })
let nextId = 1

export function useToast() {
  function remove(id) {
    const index = toastState.items.findIndex((item) => item.id === id)
    if (index > -1) toastState.items.splice(index, 1)
  }

  function push(message, type = 'success') {
    const id = nextId++
    toastState.items.push({ id, message, type })
    setTimeout(() => remove(id), 2800)
    return id
  }

  return { push, remove }
}
