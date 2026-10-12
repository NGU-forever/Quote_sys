"""UiSpec 三道门校验器与有界自愈/修复引擎。

门禁设计：
- 第一道门：枚举门（skeleton, density, preset_id, module, block.type）
- 第二道门：字段门（entities.*.list_columns/fields 必须在已登记字段中）
- 第三道门：结构门（screens[].blocks 必须符合该 skeleton 兼容矩阵，缺失关键块自动补齐）
"""
import copy
from typing import Any, Dict, List, Optional, Tuple

from app.designer.schema import (
    ALLOWED_BLOCKS,
    ALLOWED_DENSITIES,
    ALLOWED_MODULES,
    ALLOWED_PRESETS,
    ALLOWED_SKELETONS,
    DEFAULT_DENSITY,
    DEFAULT_PRESET,
    DEFAULT_SKELETON,
    SKELETON_BLOCK_MATRIX,
    get_db_fields_registry,
    get_fallback_spec,
)


def validate_and_repair_spec(
    spec: Dict[str, Any],
    db_fields_registry: Optional[Dict[str, List[str]]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """三道门校验并自动修复 UiSpec。

    返回:
        (repaired_spec, issues_list)
    """
    if not isinstance(spec, dict):
        return get_fallback_spec(), ["输入 Spec 非字典格式，已触发兜底规则 Spec"]

    issues: List[str] = []
    repaired = copy.deepcopy(spec)

    # 基础结构初始化
    if not repaired.get("spec_version"):
        repaired["spec_version"] = 1
        issues.append("枚举门：缺少 spec_version，已置为 1")

    # 1. 第一道门：枚举门
    # 样式与密度
    style = repaired.setdefault("style", {})
    if not isinstance(style, dict):
        repaired["style"] = style = {}

    if style.get("preset_id") not in ALLOWED_PRESETS:
        bad_preset = style.get("preset_id")
        style["preset_id"] = DEFAULT_PRESET
        issues.append(f"枚举门：非法 preset_id '{bad_preset}'，已回退为 '{DEFAULT_PRESET}'")

    if style.get("density") not in ALLOWED_DENSITIES:
        bad_density = style.get("density")
        style["density"] = DEFAULT_DENSITY
        issues.append(f"枚举门：非法 density '{bad_density}'，已回退为 '{DEFAULT_DENSITY}'")

    # 模块枚举
    raw_modules = repaired.get("modules")
    if not isinstance(raw_modules, list):
        repaired["modules"] = ["catalog", "quote_editor", "quotes", "settings"]
        issues.append("枚举门：modules 格式无效，已重置为标准模块集")
    else:
        valid_modules = []
        for m in raw_modules:
            if m in ALLOWED_MODULES:
                if m not in valid_modules:
                    valid_modules.append(m)
            else:
                issues.append(f"枚举门：非法模块 '{m}' 已被移除")
        if "quote_editor" not in valid_modules:
            valid_modules.insert(0, "quote_editor")
            issues.append("枚举门：必须包含 'quote_editor' 模块，已自动补齐")
        repaired["modules"] = valid_modules

    # 屏幕骨架与基本结构
    screens = repaired.get("screens")
    if not isinstance(screens, list) or len(screens) == 0:
        screens = get_fallback_spec()["screens"]
        repaired["screens"] = screens
        issues.append("结构门：缺失 screens 定义，已回退到默认开单屏幕")

    for screen in screens:
        sk = screen.get("skeleton")
        if sk not in ALLOWED_SKELETONS:
            issues.append(f"枚举门：屏幕 '{screen.get('id')}' 非法骨架 '{sk}'，已回退为 '{DEFAULT_SKELETON}'")
            screen["skeleton"] = DEFAULT_SKELETON

    # 2. 第二道门：字段门
    registry = db_fields_registry or get_db_fields_registry()
    entities = repaired.get("entities")
    if isinstance(entities, dict):
        for ent_name, ent_config in entities.items():
            if not isinstance(ent_config, dict):
                continue
            allowed_fields = set(registry.get(ent_name, []))
            if not allowed_fields:
                continue

            for field_list_key in ("list_columns", "fields", "filters"):
                if field_list_key in ent_config and isinstance(ent_config[field_list_key], list):
                    original_list = ent_config[field_list_key]
                    cleaned_list = [f for f in original_list if f in allowed_fields]
                    removed = set(original_list) - allowed_fields
                    if removed:
                        issues.append(f"字段门：实体 '{ent_name}' 包含非法字段 {removed}，已被过滤")
                    if not cleaned_list:
                        # 回退默认前 3 个字段
                        cleaned_list = sorted(list(allowed_fields))[:4]
                        issues.append(f"字段门：实体 '{ent_name}.{field_list_key}' 过滤后为空，已回退到默认字段 {cleaned_list}")
                    ent_config[field_list_key] = cleaned_list

    # 3. 第三道门：结构门
    for screen in screens:
        sk = screen.get("skeleton", DEFAULT_SKELETON)
        allowed_block_types = SKELETON_BLOCK_MATRIX.get(sk, set())
        raw_blocks = screen.get("blocks", [])
        if not isinstance(raw_blocks, list):
            raw_blocks = []

        valid_blocks = []
        for b in raw_blocks:
            if not isinstance(b, dict):
                continue
            b_type = b.get("type")
            if b_type not in ALLOWED_BLOCKS:
                issues.append(f"枚举门：屏幕 '{screen.get('id')}' 中包含未知 Block 类型 '{b_type}'，已被剔除")
                continue
            if b_type not in allowed_block_types:
                issues.append(f"结构门：Block '{b_type}' 不在骨架 '{sk}' 的兼容白名单内，已被剔除")
                continue
            valid_blocks.append(b)

        # quote_editor 必填项防御
        if screen.get("id") == "quote_editor":
            existing_types = {b.get("type") for b in valid_blocks}
            if not any(t in existing_types for t in ("item_picker", "item_table_editable")):
                valid_blocks.append({"type": "item_table_editable", "props": {}})
                issues.append("结构门：开单屏幕缺少明细编辑块，已自动补齐 'item_table_editable'")
            if "price_summary" not in existing_types and "price_summary" in allowed_block_types:
                valid_blocks.append({"type": "price_summary", "props": {}})
                issues.append("结构门：开单屏幕缺少价格合计块，已自动补齐 'price_summary'")

        screen["blocks"] = valid_blocks

    return repaired, issues
