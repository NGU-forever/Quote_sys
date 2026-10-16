/**
 * 运行时导航解析（纯函数，可直接单测）。
 *
 * 背景：Spec 里的 `nav` 此前**没有任何消费方**，运行时只渲染 `screens[0]`，
 * 于是「老板生成的多模块系统」在员工端退化成一个单屏，nav 里的
 * /quotes、/catalog 全是点了没反应的死链。
 *
 * 这里负责把 Spec 解析成可点的导航项，并守住与后端 `navigation.py` 相同的不变量：
 * 每个导航项都必须有对应的屏幕（不产生死链），且只保留已启用模块。
 */

/** 后端未给标签时的兜底（与 app/designer/schema.py 的 MODULE_NAV 对齐）。 */
export const NAV_LABELS = {
  quote_editor: '开单',
  quotes: '报价单',
  approval: '审批',
  catalog: '商品目录',
  customers: '客户',
  settings: '设置',
  employees: '员工',
};

export function getScreens(spec) {
  const screens = Array.isArray(spec?.screens) ? spec.screens : [];
  return screens.filter((screen) => screen && typeof screen.id === 'string' && screen.id);
}

export function getScreenById(spec, screenId) {
  const screens = getScreens(spec);
  if (screenId) {
    const hit = screens.find((screen) => screen.id === screenId);
    if (hit) return hit;
  }
  return screens[0] || null;
}

function deriveNavFromScreens(screens) {
  return screens.map((screen) => ({
    id: screen.id,
    label: NAV_LABELS[screen.id] || screen.id,
    route: `/${screen.id}`,
    icon: '',
  }));
}

/**
 * 解析可用的导航项。
 *
 * - 优先采用 Spec 声明的 `nav`；缺失或为空时由 `screens` 派生
 * - 剔除没有对应屏幕的项（死链）
 * - 剔除未在 `modules` 中启用的项（模块开关生效）
 */
export function getNavItems(spec) {
  const screens = getScreens(spec);
  const screenIds = new Set(screens.map((screen) => screen.id));
  const modules = Array.isArray(spec?.modules) ? spec.modules : [];
  const moduleSet = new Set(modules);

  const raw =
    Array.isArray(spec?.nav) && spec.nav.length > 0 ? spec.nav : deriveNavFromScreens(screens);

  const items = [];
  const seen = new Set();
  raw.forEach((item) => {
    const id = item && item.id;
    if (!id || seen.has(id)) return;
    if (!screenIds.has(id)) return;
    if (moduleSet.size > 0 && !moduleSet.has(id)) return;
    seen.add(id);
    items.push({
      id,
      label: String(item.label || NAV_LABELS[id] || id),
      route: String(item.route || `/${id}`),
      icon: String(item.icon || ''),
    });
  });
  return items;
}

/** 解析当前激活屏幕；传入的偏好无效时回退到第一屏。 */
export function resolveActiveScreenId(spec, preferred) {
  const screens = getScreens(spec);
  if (screens.length === 0) return null;
  if (preferred && screens.some((screen) => screen.id === preferred)) return preferred;
  return screens[0].id;
}
