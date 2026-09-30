import { defineStore } from 'pinia'
import { PRICING } from '../data/pricing'

const DEFAULT_COMPANY = {
  name: 'QuoteSys 通用商业报价系统',
  phone: '400-800-8888',
  email: 'service@quotesys.com',
  address: '高新技术产业开发区创新科技园'
}

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    devicePrice: PRICING.devicePrice,
    bagsPerBox: PRICING.bagsPerBox,
    giftRatio: PRICING.giftRatio,
    plan2UnitPrice: PRICING.plan2UnitPrice,
    plan2MinBoxes: PRICING.plan2MinBoxes,
    quoteValidityDays: PRICING.quoteValidityDays,
    quotePrefix: 'Q',
    plan1Tiers: PRICING.plan1Tiers.map((tier) => ({ ...tier })),
    company: { ...DEFAULT_COMPANY }
  }),
  actions: {
    /** 用主设备同步来的 settings 覆盖公司信息与报价参数（缺失字段保留默认值） */
    applyRemote(settings) {
      if (!settings) return
      const c = settings.company
      const p = settings.pricing
      if (c) this.company = { ...this.company, ...c }
      if (p) {
        const num = (v, fallback) => {
          const n = Number(v)
          return Number.isFinite(n) ? n : fallback
        }
        this.devicePrice = num(p.devicePrice, this.devicePrice)
        this.bagsPerBox = num(p.bagsPerBox, this.bagsPerBox)
        this.giftRatio = num(p.giftRatio, this.giftRatio)
        this.plan2UnitPrice = num(p.plan2UnitPrice, this.plan2UnitPrice)
        this.plan2MinBoxes = num(p.plan2MinBoxes, this.plan2MinBoxes)
        this.quoteValidityDays = num(p.quoteValidityDays, this.quoteValidityDays)
        this.quotePrefix = p.quotePrefix ?? this.quotePrefix
        if (Array.isArray(p.plan1Tiers) && p.plan1Tiers.length) {
          this.plan1Tiers = p.plan1Tiers.map((t) => ({ ...t }))
        }
      }
    }
  }
})
