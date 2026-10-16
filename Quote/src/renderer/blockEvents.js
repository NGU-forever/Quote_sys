/**
 * 区块事件 → 组件监听的映射（纯函数，可直接单测）。
 *
 * 区块用 kebab-case 声明事件（`add-item`），而动态 `<component>` 需要
 * camelCase 的 `onXxx` 监听（`onAddItem`）。`print-a4` / `export-pdf` 这种
 * 带数字后缀的名字最容易写错，所以单独抽出来测。
 *
 * 只给"确实支持该事件"的区块挂监听，避免给所有区块挂上无关事件。
 */

export const BLOCK_EVENT_MAP = {
  item_picker: ['add-item'],
  item_table_editable: ['update-qty', 'remove-item'],
  bundle_suggestion: ['apply-bundle'],
  export_actions: ['save-draft', 'print-a4', 'export-pdf'],
};

export function blockEventsFor(blockType) {
  return BLOCK_EVENT_MAP[blockType] || [];
}

/** 'add-item' → 'onAddItem'；'print-a4' → 'onPrintA4'；'export-pdf' → 'onExportPdf' */
export function toHandlerName(eventName) {
  const camel = String(eventName)
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
  return `on${camel}`;
}

/** 组装某个区块的动态监听对象；emit 由调用方传入（便于单测） */
export function listenersFor(blockType, emit) {
  const handlers = {};
  blockEventsFor(blockType).forEach((eventName) => {
    handlers[toHandlerName(eventName)] = (payload) => emit(eventName, payload);
  });
  return handlers;
}
