/**
 * 设计器向导状态管理模块
 */

export function createWizardState() {
  return {
    currentStep: 0,
    selectedPreset: null,
    sourceLevel: 'sample',
    sourceLabel: '以下用行业样例演示，导入数据后会替换',
    answers: {
      industry: '医疗设备',
      category_name: '主要设备与配件',
      has_consumables: true,
      sell_mode: 'device_with_consumable',
      roles: ['admin', 'sales'],
      scene: 'on_site',
      pricing_mode: 'floor_price',
      require_approval: true,
      output_target: 'print_a4',
      brand_color: '#0B5FA5',
      brand_color_name: '品牌科技蓝',
      preset_id: 'medical-clean',
    },
    signals: {},
    sampleData: null,
    activeSpec: null,
  };
}

export function applyPresetToWizard(state, presetId) {
  state.selectedPreset = presetId;
  if (presetId === 'order-entry') {
    state.answers.sell_mode = 'device_with_consumable';
    state.answers.scene = 'on_site';
    state.answers.pricing_mode = 'floor_price';
    state.answers.preset_id = 'medical-clean';
  } else if (presetId === 'wholesale') {
    state.answers.sell_mode = 'consumable_only';
    state.answers.scene = 'office';
    state.answers.pricing_mode = 'tiered';
    state.answers.preset_id = 'industrial-dense';
  } else if (presetId === 'management') {
    state.answers.sell_mode = 'mixed';
    state.answers.scene = 'office';
    state.answers.pricing_mode = 'negotiable';
    state.answers.preset_id = 'brand-premium';
  }
}
