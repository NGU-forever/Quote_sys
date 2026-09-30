export function formatMoney(value, precision = 0) {
  const num = Number(value) || 0
  return `¥${num.toLocaleString('zh-CN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision
  })}`
}

export function today() {
  const date = new Date()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}
