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
      industry_code: 'medical',
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
      // operation = 日常开单视角；management = 老板/管理视角（决定骨架是否为看板）
      view_mode: 'operation',
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
    state.answers.require_approval = false;
    state.answers.view_mode = 'operation';
    state.answers.preset_id = 'medical-clean';
  } else if (presetId === 'wholesale') {
    state.answers.sell_mode = 'consumable_only';
    state.answers.scene = 'office';
    state.answers.pricing_mode = 'tiered';
    state.answers.require_approval = false;
    state.answers.view_mode = 'operation';
    state.answers.preset_id = 'industrial-dense';
  } else if (presetId === 'management') {
    state.answers.sell_mode = 'mixed';
    state.answers.scene = 'office';
    state.answers.pricing_mode = 'negotiable';
    state.answers.require_approval = true;
    // 管理视角：骨架走看板，与预设包 ③ 一致（避免走向导后被覆盖成开单型）
    state.answers.view_mode = 'management';
    state.answers.preset_id = 'brand-premium';
  }
}
