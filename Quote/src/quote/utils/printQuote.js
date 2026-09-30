/**
 * 报价单打印纯函数模块：负责 A4 报价单 HTML 拼装与 Iframe 打印唤起
 */

export function moneyText(value, precision) {
  const num = Number(value) || 0
  const dec = precision != null ? precision : Math.abs(num % 1) > 1e-9 ? 2 : 0
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec
  })
}

export function escHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function buildPrintRows(data) {
  if (data.mode === 'package' && data.packageChosen) {
    return data.directItems.map((item) => ({
      name: item.name,
      spec: item.spec,
      unit: item.unit,
      qty: item.qty,
      price: '—',
      amount: '—',
      note: item.note
    }))
  }
  if (data.mode === 'both' && data.packageChosen) {
    return [
      {
        name: data.deviceName,
        spec: data.deviceSpec,
        unit: '台',
        qty: data.devices,
        price: data.deviceUnit,
        amount: '—',
        note: '套餐内设备'
      },
      {
        name: data.consumableName,
        spec: data.consumableSpec,
        unit: '箱',
        qty: data.boxes,
        price: data.consumableUnit * data.bagsPerBox,
        amount: '—',
        note: `含${data.bagsPerBox}${data.consumableUnitName}/箱`
      }
    ]
  }
  if (data.mode === 'both') {
    return [
      {
        name: data.deviceName,
        spec: data.deviceSpec,
        unit: '台',
        qty: data.devices,
        price: data.devicePrice,
        amount: data.plan1DeviceCost,
        note: ''
      },
      {
        name: data.consumableName,
        spec: data.consumableSpec,
        unit: '箱',
        qty: data.boxes,
        price: data.plan1UnitPrice * data.bagsPerBox,
        amount: data.plan1ConsumablesCost,
        note: `含${data.bagsPerBox}${data.consumableUnitName}/箱`
      }
    ]
  }
  if (data.mode === 'consumables') {
    return [
      {
        name: data.consumableName,
        spec: data.consumableSpec,
        unit: '箱',
        qty: data.boxes,
        price: data.plan1UnitPrice * data.bagsPerBox,
        amount: data.plan1ConsumablesCost,
        note: `含${data.bagsPerBox}${data.consumableUnitName}/箱`
      }
    ]
  }
  return [
    {
      name: data.deviceName,
      spec: data.deviceSpec,
      unit: '台',
      qty: data.devices,
      price: data.devicePrice,
      amount: data.plan1DeviceCost,
      note: ''
    }
  ]
}

export function buildPrintDocument(data) {
  const rows = buildPrintRows(data)
  const logoHref = data.logoUrl ? new URL(data.logoUrl, window.location.href).href : ''
  const cell = (value) => (typeof value === 'number' ? moneyText(value) : String(value ?? ''))
  const rowHtml = rows
    .map(
      (row, index) =>
        `<tr><td>${index + 1}</td><td>${escHtml(row.name)}</td><td>${escHtml(row.spec)}</td><td>${escHtml(
          row.unit
        )}</td><td>${cell(row.qty)}</td><td>${cell(row.price)}</td><td>${cell(
          row.amount
        )}</td><td>${escHtml(row.note) || '-'}</td></tr>`
    )
    .join('')
  const company = data.company || {}

  const packageLine = data.packageChosen
    ? `<div class="pkg-line">结算方式：按套餐「${escHtml(data.packageName || '')}」整购结算${
        data.planCoverText ? `（${escHtml(data.planCoverText)}）` : ''
      }</div>`
    : ''
  const discountLine =
    data.discount > 0
      ? `<div class="discount-line">标准价合计 ${moneyText(data.standardTotal)} 元，本单优惠 ${moneyText(
          data.discount
        )} 元，实收合计 ${moneyText(data.total)} 元。</div>`
      : ''

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>医疗器械报价单</title>
  <style>
    @page { size: A4; margin: 12mm; }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; }
    body {
      font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
      color: #172033;
      font-size: 12px;
      line-height: 1.55;
    }
    .sheet { padding: 2px 6px; }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding-bottom: 12px;
      border-bottom: 2px solid #0d47a1;
      margin-bottom: 14px;
    }
    .logo-img { height: 44px; width: auto; object-fit: contain; }
    .brand-name { font-size: 18px; font-weight: 800; color: #0d47a1; }
    .contact-info { font-size: 11px; color: #475569; text-align: right; line-height: 1.6; }
    h1 { text-align: center; font-size: 18px; margin: 10px 0 12px; letter-spacing: 2px; color: #0f172a; }
    .meta { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 11px; color: #334155; }
    .party {
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
      padding: 10px 12px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
    }
    .mode-line { margin: 12px 0 4px; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border: 1px solid #94a3b8; padding: 8px 6px; text-align: center; vertical-align: middle; }
    th { background: #e3f2fd; color: #0d47a1; font-weight: 800; }
    .total {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-top: 12px;
      padding: 10px 12px;
      background: #e3f2fd;
      border: 1px solid #64b5f6;
      border-radius: 4px;
      font-weight: 800;
    }
    .pkg-line { margin-top: 10px; color: #0d47a1; font-weight: 700; }
    .discount-line { margin-top: 8px; color: #b71c1c; font-weight: 700; text-align: right; }
    .notes { margin-top: 14px; color: #334155; font-size: 11px; line-height: 1.8; }
    .sign { display: flex; justify-content: space-between; margin-top: 44px; font-size: 12px; }
    .sign span { width: 24%; }
    .footer {
      margin-top: 22px;
      padding-top: 8px;
      border-top: 1px solid #e2e8f0;
      text-align: center;
      color: #64748b;
      font-size: 10px;
    }
  </style>
</head>
<body>
  <div class="sheet">
    <div class="header">
      <div>
        ${logoHref ? `<img src="${logoHref}" class="logo-img" alt="商标" />` : `<div class="brand-name">${company.name || 'QuoteSys 通用商业报价系统'}</div>`}
      </div>
      <div class="contact-info">
        <div>咨询热线：${company.phone || ''}</div>
        <div>电子邮箱：${company.email || ''}</div>
        <div>公司地址：${company.address || ''}</div>
      </div>
    </div>
    <h1>正式商业报价单</h1>
    <div class="meta">
      <span>报价单号：<strong>${data.id}</strong></span>
      <span>报价日期：<strong>${data.date}</strong></span>
      <span>采购方式：<strong>${data.modeLabel}</strong></span>
    </div>
    <div class="party">
      <span>客户名称：${escHtml(data.customerName) || '____________________'}</span>
      <span>联系人：${escHtml(data.contactPerson) || '____________'}</span>
      <span>联系电话：${escHtml(data.contactPhone) || '____________'}</span>
    </div>
    <div class="mode-line">产品明细</div>
    <table>
      <thead>
        <tr><th>序号</th><th>产品名称</th><th>规格型号</th><th>单位</th><th>数量</th><th>单价</th><th>金额</th><th>备注</th></tr>
      </thead>
      <tbody>${rowHtml}</tbody>
    </table>
    ${packageLine}
    <div class="total">
      <span>合计金额（人民币）：<strong>${moneyText(data.total)}</strong> 元</span>
    </div>
    ${discountLine}
    <div class="notes">
      <strong>报价说明：</strong><br />
      1. 本报价单有效期 30 天；<br />
      2. 报价为人民币含税价，最终以双方签订合同为准；<br />
      3. 确认订单后 7 个工作日内安排发货；<br />
      4. 赠机设备与正品享有同等质保。
    </div>
    <div class="sign">
      <span>报价人：${escHtml(data.quoter) || '____________'}</span>
      <span>联系电话：${escHtml(data.quoterPhone) || '____________'}</span>
    </div>
  </div>
</body>
</html>`
}

export function printQuoteDocument(data, iframeEl) {
  if (!iframeEl) return
  iframeEl.onload = () => {
    iframeEl.contentWindow?.focus()
    iframeEl.contentWindow?.print()
  }
  iframeEl.srcdoc = buildPrintDocument(data)
}
