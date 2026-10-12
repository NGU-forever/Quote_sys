/**
 * 三套风格包 Design Tokens 定义与 CSS 变量解析器
 * 
 * 1. medical-clean: 医疗洁净 / 舒适中等 / 8px 圆角 / 行高 44px
 * 2. industrial-dense: 工业紧凑 / 紧密等宽 / 4px 圆角 / 行高 34px / 斑马线
 * 3. brand-premium: 品牌轻奢 / 留白衬线 / 2px 直角 / 行高 52px
 */

export const PRESETS = {
  'medical-clean': {
    id: 'medical-clean',
    name: '医疗洁净',
    bg: '#FFFFFF',
    surface: '#F6F8FB',
    primary: '#0B5FA5',
    accent: '#2E86C1',
    text: '#1B2733',
    textMuted: '#5A6B7B',
    border: '#E3E9F0',
    radiusBase: '8px',
    radiusCard: '10px',
    radiusInput: '6px',
    shadowCard: '0 8px 24px rgba(16, 24, 40, 0.06)',
    spaceScale: '1.0',
    tableRowHeight: '44px',
    tableZebra: false,
    fontNumeric: 'normal',
  },
  'industrial-dense': {
    id: 'industrial-dense',
    name: '工业紧凑',
    bg: '#FFFFFF',
    surface: '#F2F4F7',
    primary: '#175C8C',
    accent: '#0E7490',
    text: '#111827',
    textMuted: '#6B7280',
    border: '#D7DDE5',
    radiusBase: '4px',
    radiusCard: '4px',
    radiusInput: '4px',
    shadowCard: '0 1px 0 rgba(0, 0, 0, 0.06)',
    spaceScale: '0.85',
    tableRowHeight: '34px',
    tableZebra: true,
    fontNumeric: 'tabular-nums',
  },
  'brand-premium': {
    id: 'brand-premium',
    name: '品牌轻奢',
    bg: '#FBFAF8',
    surface: '#FFFFFF',
    primary: '#14532D',
    accent: '#B08D57',
    text: '#1A1A1A',
    textMuted: '#6B6B6B',
    border: '#EAE6DF',
    radiusBase: '2px',
    radiusCard: '2px',
    radiusInput: '2px',
    shadowCard: 'none',
    spaceScale: '1.25',
    tableRowHeight: '52px',
    tableZebra: false,
    fontNumeric: 'normal',
  },
};

function hexToRgb(hex) {
  let c = hex.replace('#', '');
  if (c.length === 3) {
    c = c.split('').map((char) => char + char).join('');
  }
  const num = parseInt(c, 16);
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255,
  };
}

function getLuminance({ r, g, b }) {
  const a = [r, g, b].map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
}

export function adjustColorContrast(hexColor, bgHex = '#FFFFFF') {
  try {
    const fgRgb = hexToRgb(hexColor);
    const bgRgb = hexToRgb(bgHex);
    const l1 = getLuminance(fgRgb);
    const l2 = getLuminance(bgRgb);
    const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);

    // 若对比度低于 3:1，自动加深 25% (RGB 乘以 0.75)
    if (ratio < 3.0) {
      const darkened = {
        r: Math.round(fgRgb.r * 0.75),
        g: Math.round(fgRgb.g * 0.75),
        b: Math.round(fgRgb.b * 0.75),
      };
      return `#${((1 << 24) + (darkened.r << 16) + (darkened.g << 8) + darkened.b)
        .toString(16)
        .slice(1)}`;
    }
  } catch (e) {
    // 忽略异常，降级原色
  }
  return hexColor;
}

export function resolveTokens(presetId = 'medical-clean', customTokens = {}) {
  const preset = PRESETS[presetId] || PRESETS['medical-clean'];
  let primaryColor = customTokens['color.primary'] || preset.primary;
  primaryColor = adjustColorContrast(primaryColor, preset.bg);

  return {
    '--color-bg': preset.bg,
    '--color-surface': preset.surface,
    '--color-primary': primaryColor,
    '--color-accent': preset.accent,
    '--color-text': preset.text,
    '--color-text-muted': preset.textMuted,
    '--color-border': preset.border,
    '--radius-base': preset.radiusBase,
    '--radius-card': preset.radiusCard,
    '--radius-input': preset.radiusInput,
    '--shadow-card': preset.shadowCard,
    '--space-scale': preset.spaceScale,
    '--table-row-h': preset.tableRowHeight,
    '--table-zebra': preset.tableZebra ? '1' : '0',
    '--font-numeric': preset.fontNumeric,
  };
}
