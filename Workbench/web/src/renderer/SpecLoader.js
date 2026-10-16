/**
 * SpecLoader: UiSpec 规范读取与防御性结构归一化
 */
import { getNavItems } from './runtimeNav.js';

export const SKELETON_SLOTS = {
  'catalog-left-form-right': ['left_rail', 'main_header', 'main_body', 'main_footer'],
  'form-first-wizard': ['steps_header', 'step_body', 'step_footer'],
  'list-detail-split': ['filters', 'list', 'detail_header', 'detail_body', 'detail_actions'],
  'dashboard-grid': ['stats_row', 'grid_left', 'grid_right'],
  'mobile-single-column': ['top_bar', 'content', 'bottom_bar'],
};

export const BLOCK_DEFAULT_SLOT = {
  // catalog-left-form-right 槽位映射
  'catalog-left-form-right': {
    item_picker: 'left_rail',
    customer_info: 'main_header',
    quote_meta: 'main_header',
    item_table_editable: 'main_body',
    bundle_suggestion: 'main_body',
    floor_price_alert: 'main_body',
    price_summary: 'main_footer',
    export_actions: 'main_footer',
  },
  // form-first-wizard 槽位映射
  'form-first-wizard': {
    quote_meta: 'steps_header',
    customer_info: 'step_body',
    item_picker: 'step_body',
    item_table_editable: 'step_body',
    bundle_suggestion: 'step_body',
    discount_panel: 'step_body',
    floor_price_alert: 'step_body',
    notes_and_terms: 'step_body',
    attachment_upload: 'step_body',
    approval_status: 'step_body',
    price_summary: 'step_footer',
    export_actions: 'step_footer',
  },
  // list-detail-split 槽位映射
  'list-detail-split': {
    customer_info: 'filters',
    item_table_readonly: 'list',
    quote_meta: 'detail_header',
    approval_status: 'detail_header',
    detail_body: 'detail_body',
    discount_panel: 'detail_body',
    activity_timeline: 'detail_body',
    notes_and_terms: 'detail_body',
    attachment_upload: 'detail_body',
    price_summary: 'detail_actions',
    export_actions: 'detail_actions',
  },
  // dashboard-grid 槽位映射
  'dashboard-grid': {
    stats_cards: 'stats_row',
    recent_quotes: 'grid_left',
    approval_status: 'grid_right',
    activity_timeline: 'grid_right',
  },
  // mobile-single-column 槽位映射
  'mobile-single-column': {
    customer_info: 'top_bar',
    item_picker: 'content',
    item_table_editable: 'content',
    floor_price_alert: 'content',
    price_summary: 'bottom_bar',
  },
};

export function getSkeletonSlots(skeletonId) {
  return SKELETON_SLOTS[skeletonId] || SKELETON_SLOTS['catalog-left-form-right'];
}

export function loadAndNormalizeSpec(rawSpec) {
  if (!rawSpec || typeof rawSpec !== 'object') {
    return {
      spec_version: 1,
      style: { preset_id: 'medical-clean', density: 'comfortable', tokens: {} },
      modules: ['catalog', 'quote_editor', 'quotes', 'settings'],
      screens: [
        {
          id: 'quote_editor',
          skeleton: 'catalog-left-form-right',
          blocks: [
            { type: 'customer_info', props: {} },
            { type: 'item_picker', props: {} },
            { type: 'item_table_editable', props: {} },
            { type: 'price_summary', props: {} },
            { type: 'export_actions', props: {} },
          ],
        },
      ],
    };
  }

  const spec = JSON.parse(JSON.stringify(rawSpec));
  spec.spec_version = spec.spec_version || 1;
  spec.style = spec.style || { preset_id: 'medical-clean', density: 'comfortable' };

  if (!Array.isArray(spec.screens) || spec.screens.length === 0) {
    spec.screens = [
      {
        id: 'quote_editor',
        skeleton: 'catalog-left-form-right',
        blocks: [{ type: 'item_picker', props: {} }, { type: 'item_table_editable', props: {} }],
      },
    ];
  }

  // modules 缺失时以「屏幕声明了什么」为准，避免用默认模块列表把屏幕误关掉。
  spec.modules =
    Array.isArray(spec.modules) && spec.modules.length > 0
      ? spec.modules
      : spec.screens.map((screen) => screen.id).filter(Boolean);

  // nav 归一化：缺失时由 screens 派生，并剔除无目标屏幕/未启用模块的项，
  // 与后端 navigation.py 的不变量保持一致（导航项永远点得到）。
  spec.nav = getNavItems(spec);

  return spec;
}
