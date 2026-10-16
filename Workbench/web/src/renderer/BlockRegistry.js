/**
 * Block 注册表与解析中心
 *
 * 负责 16 种 Block 到 Vue SFC 组件的确定性映射与未知组件降级
 */
import CustomerInfoBlock from './blocks/CustomerInfoBlock.vue';
import ItemPickerBlock from './blocks/ItemPickerBlock.vue';
import ItemTableEditableBlock from './blocks/ItemTableEditableBlock.vue';
import ItemTableReadonlyBlock from './blocks/ItemTableReadonlyBlock.vue';
import PriceSummaryBlock from './blocks/PriceSummaryBlock.vue';
import FloorPriceAlertBlock from './blocks/FloorPriceAlertBlock.vue';
import BundleSuggestionBlock from './blocks/BundleSuggestionBlock.vue';
import DiscountPanelBlock from './blocks/DiscountPanelBlock.vue';
import QuoteMetaBlock from './blocks/QuoteMetaBlock.vue';
import NotesAndTermsBlock from './blocks/NotesAndTermsBlock.vue';
import AttachmentUploadBlock from './blocks/AttachmentUploadBlock.vue';
import ApprovalStatusBlock from './blocks/ApprovalStatusBlock.vue';
import ActivityTimelineBlock from './blocks/ActivityTimelineBlock.vue';
import ExportActionsBlock from './blocks/ExportActionsBlock.vue';
import StatsCardsBlock from './blocks/StatsCardsBlock.vue';
import RecentQuotesBlock from './blocks/RecentQuotesBlock.vue';
import FallbackBlock from './blocks/FallbackBlock.vue';

import { ALL_BLOCK_TYPES, isBlockTypeAllowed } from './BlockTypes.js';
export { ALL_BLOCK_TYPES, isBlockTypeAllowed };

export const BLOCK_REGISTRY = {
  customer_info: CustomerInfoBlock,
  item_picker: ItemPickerBlock,
  item_table_editable: ItemTableEditableBlock,
  item_table_readonly: ItemTableReadonlyBlock,
  price_summary: PriceSummaryBlock,
  floor_price_alert: FloorPriceAlertBlock,
  bundle_suggestion: BundleSuggestionBlock,
  discount_panel: DiscountPanelBlock,
  quote_meta: QuoteMetaBlock,
  notes_and_terms: NotesAndTermsBlock,
  attachment_upload: AttachmentUploadBlock,
  approval_status: ApprovalStatusBlock,
  activity_timeline: ActivityTimelineBlock,
  export_actions: ExportActionsBlock,
  stats_cards: StatsCardsBlock,
  recent_quotes: RecentQuotesBlock,
};

export function getBlockComponent(type) {
  return BLOCK_REGISTRY[type] || FallbackBlock;
}
