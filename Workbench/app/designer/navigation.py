"""模块 → 屏幕 → 导航的确定性映射（规则优先，见设计文档 §5.1 / §8）。

背景：此前 `nav` 是一段写在兜底 Spec 里的字面量，三道门**完全没有校验它**，
运行时也从不消费 —— 结果是 Spec 声明了一套多模块系统，实际只渲染
`screens[0]` 一屏，`nav` 里的 /quotes、/catalog 全是点了没反应的死链。

这里把它变成可测试的纯函数，并保证一条不变量：

    nav[].id  与  screens[].id  一一对应（不存在没有目标的导航项，
                                也不存在点不到的屏幕）

`settings` / `employees` 属管理工作台范畴，没有对应的员工端业务屏幕，
因此不会出现在 screens 与 nav 里。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

from app.designer.schema import MODULE_NAV, MODULE_SCREEN_BLUEPRINTS


def build_module_screens(
    modules: Iterable[str],
    primary_screen: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """按启用的模块产出屏幕列表。

    - 开单屏（quote_editor）始终在首位，其骨架与区块由向导答案决定
    - 其余模块按 `MODULE_NAV` 的登记顺序追加蓝图屏（顺序稳定，不随模块列表顺序漂移）
    - 无蓝图的模块（settings / employees）不产屏
    """
    enabled = set(modules or [])
    screens: List[Dict[str, Any]] = []

    if primary_screen:
        screens.append(primary_screen)

    for module in MODULE_NAV:
        if module not in enabled:
            continue
        blueprint = MODULE_SCREEN_BLUEPRINTS.get(module)
        if not blueprint:
            continue
        if any(s.get("id") == module for s in screens):
            continue
        screens.append(
            {
                "id": module,
                "skeleton": blueprint["skeleton"],
                "blocks": [
                    {"type": block_type, "props": dict(props)}
                    for block_type, props in blueprint["blocks"]
                ],
            }
        )

    return screens


def build_nav(screens: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    """由屏幕列表派生导航项，保证不出现死链。"""
    nav: List[Dict[str, str]] = []
    seen: set[str] = set()
    for screen in screens or []:
        screen_id = screen.get("id") if isinstance(screen, dict) else None
        if not screen_id or screen_id in seen:
            continue
        meta = MODULE_NAV.get(screen_id)
        if not meta:
            continue
        seen.add(screen_id)
        nav.append(
            {
                "id": screen_id,
                "label": meta["label"],
                "route": meta["route"],
                "icon": meta["icon"],
            }
        )
    return nav


def rebuild_navigation(spec: Dict[str, Any], primary_screen: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """就地重建 spec 的 screens 与 nav，使两者始终一致（供编译器与预览共用）。"""
    modules = spec.get("modules") or []
    screens = build_module_screens(modules, primary_screen=primary_screen)
    if not screens:
        screens = spec.get("screens") or []
    spec["screens"] = screens
    spec["nav"] = build_nav(screens)
    return spec
