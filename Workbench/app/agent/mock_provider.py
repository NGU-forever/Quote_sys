"""离线 Mock provider：节点级确定性响应 + 旧协议兼容回放。"""
import json
import threading

from app.agent.llm_client import LLMResponse, ToolCall


def _device(sku: str, name: str, min_price, raw: str, applicable: str | None = None) -> dict:
    max_p = None
    if "-" in raw:
        try:
            parts = raw.split("-")
            max_p = float(parts[1]) if "." in parts[1] else int(parts[1])
        except Exception:
            pass
    return {
        "sku_id": sku,
        "category": "device",
        "name": name,
        "min_price": min_price,
        "max_price": max_p,
        "unit": "台",
        "pieces_per_unit": None,
        "units_per_box": None,
        "box_price": None,
        "applicable_devices": applicable,
        "raw_price_desc": raw,
        "remark": None,
        "image": None,
    }


def _consumable(
    sku: str,
    name: str,
    min_price,
    pieces: int | None,
    units: int | None,
    box_price,
    applicable: str,
    raw: str,
    remark: str | None = None,
) -> dict:
    return {
        "sku_id": sku,
        "category": "consumable",
        "name": name,
        "min_price": min_price,
        "max_price": None,
        "unit": "袋" if units else "瓶" if "瓶" in raw else "盒" if "盒" in raw else "袋",
        "pieces_per_unit": pieces,
        "units_per_box": units,
        "box_price": box_price,
        "applicable_devices": applicable,
        "raw_price_desc": raw,
        "remark": remark,
        "image": None,
    }


DEMO_XLSX = "产品最低价格.xlsx"

DEMO_PRODUCTS = [
    _device("P001", "超声波治疗仪CSY-200（台式）", 2500, "≥2500"),
    _device("P002", "超声波治疗仪CSY-300（立式）", 8000, "≥8000"),
    _device("P003", "经颅磁BW-6911A", 2800, "≥2800", "经颅磁系列"),
    _device("P004", "经颅磁BW-6910C", 10000, "≥10000", "经颅磁系列"),
    _device("P005", "经颅磁BW-6911C(豪华）", 13800, "≥13800", "经颅磁系列"),
    _device("P006", "经颅磁BW-6911C（至尊）", 18000, "≥18000", "经颅磁系列"),
    _device("P007", "中医定向透药治疗仪YX-TYY-300", 8000, "≥8000"),
    _device("P008", "中医定向透药治疗仪YX-TYY-100", 2000, "≥2000"),
    _device("P009", "胃肠生物反馈治疗仪", 4000, "≥4000"),
    _device("P010", "体外冲击波治疗仪", 30000, "≥30000"),
    _device("P011", "电脑中频治疗仪（YKX-Y21D)", 1500, "≥1500"),
    _device("P012", "电脑中频治疗仪（YKX-Y80)", 600, "≥600"),
    _device("P013", "妇科臭氧治疗仪", 6000, "6000-9800"),
    _consumable("C001", "理疗用体表电极（经颅磁用）", 2.3, 1, 600, 1380, "经颅磁系列", "≥2.3/袋（1贴/袋。600袋/箱）"),
    _consumable("C002", "耳后电极片（经颅磁用）", 0.8, 2, None, None, "经颅磁系列", "≥0.8/袋（2贴/袋）"),
    _consumable("C003", "4x4肢体尾巴线电极片（经颅磁用）", 2, 2, None, None, "经颅磁系列", "≥2/袋（2贴/袋）"),
    _consumable("C004", "超声耦合贴片（肤色布平面易撕口）", 2.3, 2, 600, 1380, "超声波治疗仪系列", "≥2.3/袋（2贴/袋。600袋/箱）", "套餐价5元/袋"),
    _consumable("C005", "理疗电极片（7x10单孔）", 2.3, 2, 600, 1380, "中频/透药通用", "≥2.3/袋（2贴/袋。600袋/箱）"),
    _consumable("C006", "理疗电极片（8x8铁碗、8x8凝胶按扣、8x8按扣黄棉）", 2.3, 2, 600, 1380, "中频/透药通用", "≥2.3/袋（2贴/袋。600袋/箱）"),
    _consumable("C007", "理疗电极片（6x9黄棉）", 2.3, 2, 600, 1380, "中频/透药通用", "≥2.3/袋（2贴/袋。600袋/箱）"),
    _consumable("C008", "理疗电极片（8x8尾巴线黄棉）", 2.3, 2, 600, 1380, "中频/透药通用", "≥2.3/袋（2贴/袋。600袋/箱）"),
    _consumable("C009", "理疗电极片（10x10尾巴线黄棉）", 2.5, 2, 600, 1500, "中频/透药通用", "≥2.5/袋（2贴/袋。600袋/箱）"),
    _consumable("C010", "妇科医用阻菌凝胶", 12, None, 400, 4800, "妇科臭氧治疗仪", "12/瓶（400瓶/箱）"),
    _consumable("C011", "灸疗装置", 20, 12, 60, 1200, "中医定向透药/通用", "≥20/盒（12柱/盒。60盒/箱）"),
    _consumable("C012", "超声治疗固定贴", 2.3, 2, 600, 1380, "超声波治疗仪系列", "≥2.3/袋（2贴/袋。600袋/箱）", "套餐价5元/袋"),
]

DEMO_PACKAGES = [
    {
        "package_id": "PKG001",
        "name": "超声治疗（台式）推广套餐",
        "sku_ids": ["P001", "C004", "C012"],
        "quantities": [1, 1200, 1200],
        "std_price": 6000,
        "discount_price": None,
        "discount_rate": None,
        "device_qty": 1,
        "consumable_qty": 1200,
        "consumable_boxes": 2,
        "fixed_bundle": False,
        "device_price": None,
        "note": "买2箱（超声耦合贴片，5元/袋）送1台台式超声波治疗仪CSY-200；设备为赠送，单买价≥2500",
    },
    {
        "package_id": "PKG003",
        "name": "妇科推广套餐（市代）",
        "sku_ids": ["P013", "C010"],
        "quantities": [10, 4000],
        "std_price": 138000,
        "discount_price": None,
        "discount_rate": None,
        "device_qty": 10,
        "consumable_qty": 4000,
        "consumable_boxes": 10,
        "fixed_bundle": True,
        "device_price": 9000,
        "note": "10台设备，10箱耗材（妇科医用阻菌凝胶按箱计，1箱=400瓶；设备价格固定9000，耗材价格固定12/瓶）",
    },
    {
        "package_id": "PKG004",
        "name": "妇科推广套餐（县代）",
        "sku_ids": ["P013", "C010"],
        "quantities": [4, 1600],
        "std_price": 53800,
        "discount_price": None,
        "discount_rate": None,
        "device_qty": 4,
        "consumable_qty": 1600,
        "consumable_boxes": 4,
        "fixed_bundle": True,
        "device_price": 9000,
        "note": "4台设备，4箱耗材（妇科医用阻菌凝胶按箱计，1箱=400瓶；设备价格固定9000，耗材价格固定12/瓶）",
    },
]

DEMO_BINDINGS = [
    ("P001", "C004"),
    ("P001", "C012"),
    ("P002", "C004"),
    ("P002", "C012"),
]
for _sku in ("P003", "P004", "P005", "P006"):
    DEMO_BINDINGS.extend((_sku, c) for c in ("C001", "C002", "C003"))
for _sku in ("P007", "P008", "P011", "P012"):
    DEMO_BINDINGS.extend((_sku, c) for c in ("C005", "C006", "C007", "C008", "C009", "C011"))
DEMO_BINDINGS.append(("P013", "C010"))

DEMO_CANDIDATES = {
    "products": DEMO_PRODUCTS,
    "packages": DEMO_PACKAGES,
    "bindings": [
        {"device_sku_id": device_sku, "consumable_sku_id": consumable_sku}
        for device_sku, consumable_sku in DEMO_BINDINGS
    ],
    "issues": [
        "套餐定义表 PKG002 备注说明立式超声波治疗仪没有赠送方案，语义自相矛盾，已跳过该套餐"
    ],
}


class MockProvider:
    """确定性开发模式：各图节点返回与参考资产一致的合法数据。"""

    def __init__(self):
        self._phase = 0
        self._lock = threading.Lock()

    def chat(self, messages: list[dict], tool_schemas: list[dict]) -> LLMResponse:
        tool_name = ""
        if tool_schemas:
            tool_name = str(
                (tool_schemas[0].get("function") or {}).get("name") or ""
            )
        if tool_name == "extract_products":
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        tool_name,
                        {"products": DEMO_PRODUCTS, "issues": []},
                        call_id="mock-extract-products",
                    )
                ],
                summary="Mock 返回确定性商品候选。",
            )
        if tool_name == "extract_packages":
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        tool_name,
                        {
                            "packages": DEMO_PACKAGES,
                            "issues": [
                                "套餐定义表 PKG002 备注说明立式超声波治疗仪没有赠送方案，"
                                "语义自相矛盾，已跳过该套餐"
                            ],
                        },
                        call_id="mock-extract-packages",
                    )
                ],
                summary="Mock 返回资料中已有的确定性套餐候选。",
            )
        if tool_name == "extract_bindings":
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        tool_name,
                        {
                            "bindings": [
                                {
                                    "device_sku_id": device_sku,
                                    "consumable_sku_id": consumable_sku,
                                }
                                for device_sku, consumable_sku in DEMO_BINDINGS
                            ],
                            "issues": [],
                        },
                        call_id="mock-extract-bindings",
                    )
                ],
                summary="Mock 返回确定性设备-耗材绑定。",
            )
        if tool_name == "correct_candidates":
            candidates = {
                "products": [],
                "packages": [],
                "bindings": [],
                "issues": [],
            }
            for message in reversed(messages):
                try:
                    payload = json.loads(message.get("content") or "{}")
                except (TypeError, ValueError):
                    continue
                if isinstance(payload.get("candidates"), dict):
                    candidates = payload["candidates"]
                    break
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        tool_name,
                        {"candidates": candidates},
                        call_id="mock-correct-candidates",
                    )
                ],
                summary="Mock 返回定向修复结果。",
            )

        with self._lock:
            phase = self._phase
            self._phase += 1
        if phase == 0:
            return LLMResponse(
                tool_calls=[ToolCall("list_assets", {}, call_id="mock-list")],
                summary="Thought：先扫描 assets，确认可读取文件。",
            )
        if phase == 1:
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        "read_excel",
                        {"path": DEMO_XLSX, "sheet": "SKU主表", "max_rows": 5},
                        call_id="mock-sku",
                    )
                ],
                summary="Thought：SKU主表包含商品明细，读取表头与示例行。",
            )
        if phase == 2:
            return LLMResponse(
                tool_calls=[
                    ToolCall(
                        "read_excel",
                        {"path": DEMO_XLSX, "sheet": "套餐定义表", "max_rows": 10},
                        call_id="mock-pkg",
                    )
                ],
                summary="Thought：读取套餐定义表确认套餐组成与备注。",
            )
        if phase == 3:
            return LLMResponse(
                tool_calls=[
                    ToolCall("propose_candidates", DEMO_CANDIDATES, call_id="mock-propose")
                ],
                summary="Thought：资料读取完成，提交规范化候选。",
            )
        return LLMResponse(
            finish_requested=True,
            summary="Thought：候选已提交并校验，执行 finish。",
        )
