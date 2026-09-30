export const PRICING = {
  devicePrice: 3200,
  bagsPerBox: 600,
  giftRatio: 2,
  plan2UnitPrice: 5.5,
  plan2MinBoxes: 2,
  quoteValidityDays: 30,
  plan1Tiers: [
    { minBoxes: 1, price: 3.5, label: '1箱起订' },
    { minBoxes: 5, price: 3.0, label: '5箱起订' },
    { minBoxes: 10, price: 2.5, label: '10箱起订' }
  ]
}

export function getPlan1UnitPrice(boxes, tiers = PRICING.plan1Tiers) {
  const sorted = [...tiers].sort((a, b) => b.minBoxes - a.minBoxes)
  const matched = sorted.find((tier) => boxes >= tier.minBoxes)
  return matched ? matched.price : tiers[0].price
}
