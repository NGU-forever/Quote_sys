/**
 * 16 种标准化 Block 的类型白名单定义
 */
export const ALL_BLOCK_TYPES = [
  'customer_info',
  'item_picker',
  'item_table_editable',
  'item_table_readonly',
  'price_summary',
  'floor_price_alert',
  'bundle_suggestion',
  'discount_panel',
  'quote_meta',
  'notes_and_terms',
  'attachment_upload',
  'approval_status',
  'activity_timeline',
  'export_actions',
  'stats_cards',
  'recent_quotes',
];

export function isBlockTypeAllowed(type) {
  return ALL_BLOCK_TYPES.includes(type);
}
