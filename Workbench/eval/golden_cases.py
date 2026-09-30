"""Golden case 数据集：资料形态覆盖 + 流水线语义（归一化/校验/自愈/入库）。

每个 case 包含三部分：
1. ``assets``：在临时 assets 目录里生成真实文件（xlsx/docx/csv/md/txt），用于覆盖读取器；
2. ``raw``：**模型第一次**给出的候选（在 live 模式下由真实模型产生，被忽略）；
3. ``expected_*``：经过 reconcile → validate →（必要时自愈）→ apply 之后**期望落库**的结果。

``corrected`` 是触发校验失败后模型给出的修复结果；为 None 表示模型重复给出同样的错误
（用于验证「3 次自愈后必须失败并整体回滚」）。

注意：scripted 模式下模型输出是固定的，因此该模式衡量的是**流水线正确性**
（读取器可用性、引用归一化、服务端校验、合并入库），而不是模型抽取质量；
抽取质量需要用 ``--provider live`` 在真实模型上跑同一份数据集。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class GoldenCase:
    key: str
    title: str
    assets: Callable[[Path], None]
    raw: dict
    expected_products: list[dict] = field(default_factory=list)
    expected_packages: list[dict] = field(default_factory=list)
    expected_bindings: list[tuple[str, str]] = field(default_factory=list)
    corrected: dict | None = None
    expect_status: str = "succeeded"
    expect_issue_keywords: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# 构造与素材工具
# --------------------------------------------------------------------------


def product(sku: str, name: str, category: str = "device", **kwargs) -> dict:
    data = {"sku_id": sku, "category": category, "name": name}
    data.update(kwargs)
    return data


def package(pid: str, name: str, sku_ids: list[str], quantities: list, **kwargs) -> dict:
    data = {"package_id": pid, "name": name, "sku_ids": list(sku_ids), "quantities": list(quantities)}
    data.update(kwargs)
    return data


def binding(device_sku: str, consumable_sku: str) -> dict:
    return {"device_sku_id": device_sku, "consumable_sku_id": consumable_sku}


def xlsx(root: Path, filename: str, sheets: dict[str, list[list]]) -> None:
    import openpyxl

    workbook = openpyxl.Workbook()
    default = workbook.active
    for index, (title, rows) in enumerate(sheets.items()):
        sheet = default if index == 0 else workbook.create_sheet()
        sheet.title = title
        for row in rows:
            sheet.append(row)
    workbook.save(root / filename)


def md(root: Path, filename: str, text: str) -> None:
    (root / filename).write_text(text, encoding="utf-8")


def txt(root: Path, filename: str, text: str) -> None:
    (root / filename).write_text(text, encoding="utf-8")


def csv(root: Path, filename: str, rows: list[list]) -> None:
    text = "\n".join(",".join(str(cell) for cell in row) for row in rows)
    (root / filename).write_text(text + "\n", encoding="utf-8")


def docx(root: Path, filename: str, blocks: list[tuple]) -> None:
    from docx import Document

    document = Document()
    for block in blocks:
        kind = block[0]
        if kind == "h":
            document.add_heading(block[1], level=1)
        elif kind == "p":
            document.add_paragraph(block[1])
        elif kind == "t":
            rows = block[1]
            table = document.add_table(rows=len(rows), cols=len(rows[0]))
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    table.rows[r].cells[c].text = str(value)
    document.save(root / filename)


SKU_HEADER = ["sku_id", "产品名称", "最低价", "单位", "适用设备", "包装规格", "备注"]
PACKAGE_HEADER = ["套餐编号", "套餐名称", "商品组合", "套餐售价", "备注"]

P001 = product("P001", "超声波治疗仪CSY-200（台式）", "device", min_price=2500, unit="台")
C001 = product("C001", "超声贴片", "consumable", min_price=2, unit="袋")
C002 = product("C002", "耦合剂", "consumable", min_price=15, unit="瓶")

SKU_ROWS = [SKU_HEADER, ["P001", "超声波治疗仪CSY-200（台式）", 2500, "台", "C001", "", ""],
            ["C001", "超声贴片", 2, "袋", "", "", ""],
            ["C002", "耦合剂", 15, "瓶", "", "", ""]]
PKG_ROWS = [PACKAGE_HEADER, ["PKG001", "超声治疗（台式）推广套餐", "P001*1,C001*2", 6000, "促销买赠"]]


# --------------------------------------------------------------------------
# 数据集
# --------------------------------------------------------------------------

# 文档事实（ground truth）：SKU_ROWS 里三行商品 + P001 的「适用设备」列声明了 C001
SKU_DOC_PRODUCTS = [P001, C001, C002]
SKU_DOC_BINDING = ("P001", "C001")

# 覆盖多种资料形态的兼容表：C001 / C002 均声明适用 P001
BINDING_ROWS = [
    SKU_HEADER,
    ["P001", "超声波治疗仪CSY-200（台式）", 2500, "台", "", "", ""],
    ["C001", "超声贴片", 2, "袋", "P001", "", ""],
    ["C002", "耦合剂", 15, "瓶", "P001", "", ""],
]

CASES: list[GoldenCase] = [
    GoldenCase(
        key="excel_basic",
        title="标准 Excel：SKU主表 + 套餐定义表",
        assets=lambda root: xlsx(root, "产品最低价格.xlsx", {"SKU主表": SKU_ROWS, "套餐定义表": PKG_ROWS}),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [package("PKG001", "超声治疗（台式）推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_packages=[package("PKG001", "超声治疗（台式）推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
        expected_bindings=[SKU_DOC_BINDING],
        tags=("excel", "happy-path"),
    ),
    GoldenCase(
        key="excel_header_offset",
        title="Excel：首行是标题、表头在第 3 行、多工作表",
        assets=lambda root: xlsx(
            root,
            "报价资料.xlsx",
            {
                "说明": [["本表为 2026 年价目表"], ["制表：销售部"]],
                "商品明细": [
                    ["序号"],
                    SKU_HEADER,
                    ["1", "P001", "超声波治疗仪CSY-200（台式）", 2500, "台", "C001", "", ""],
                    ["2", "C001", "超声贴片", 2, "袋", "", "", ""],
                ],
                "套餐": [["套餐说明"], PACKAGE_HEADER, ["1", "PKG001", "推广套餐", "P001*1", 6000, "买赠"]],
            },
        ),
        raw={
            "products": [P001, C001],
            "packages": [package("PKG001", "推广套餐", ["P001"], [1], std_price=6000)],
            "bindings": [binding("P001", "C001")],
        },
        expected_products=[P001, C001],
        expected_packages=[package("PKG001", "推广套餐", ["P001"], [1], std_price=6000)],
        expected_bindings=[("P001", "C001")],
        tags=("excel", "reader"),
    ),
    GoldenCase(
        key="excel_price_text",
        title="Excel：价格是文本口径（≥2500 / 面议）",
        assets=lambda root: xlsx(
            root,
            "文本价格.xlsx",
            {
                "SKU主表": [
                    SKU_HEADER,
                    ["P001", "超声波治疗仪CSY-200（台式）", "≥2500", "台", "C001", "", "底价面议"],
                    ["C001", "超声贴片", "2", "袋", "", "100片/盒", ""],
                ]
            },
        ),
        raw={
            "products": [
                product("P001", "超声波治疗仪CSY-200（台式）", "device", min_price=2500, unit="台", raw_price_desc="≥2500"),
                product("C001", "超声贴片", "consumable", min_price=2, unit="袋", units_per_box=100),
            ],
            "packages": [],
            "bindings": [binding("P001", "C001")],
        },
        expected_products=[
            product("P001", "超声波治疗仪CSY-200（台式）", "device", min_price=2500, unit="台"),
            product("C001", "超声贴片", "consumable", min_price=2, unit="袋"),
        ],
        expected_bindings=[("P001", "C001")],
        tags=("excel", "price"),
    ),
    GoldenCase(
        key="markdown_table",
        title="Markdown：表格 + 章节套餐说明",
        assets=lambda root: md(
            root,
            "价目说明.md",
            "# 商品清单\n"
            "| sku_id | category | name | min_price | unit |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| P001 | device | 超声波治疗仪CSY-200（台式） | 2500 | 台 |\n"
            "| C001 | consumable | 超声贴片 | 2 | 袋 |\n"
            "\n## 套餐说明\n"
            "PKG001 台式超声推广套餐：P001 一台 + C001 两袋，售价 6000。\n",
        ),
        raw={
            "products": [P001, C001],
            "packages": [package("PKG001", "台式超声推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
            "bindings": [binding("P001", "C001")],
        },
        expected_products=[P001, C001],
        expected_packages=[package("PKG001", "台式超声推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
        # 套餐说明声明了设备+耗材组合：按系统提示，套餐定义可作为绑定依据
        expected_bindings=[("P001", "C001")],
        tags=("markdown", "reader"),
    ),
    GoldenCase(
        key="csv_products",
        title="CSV：商品与适用设备",
        assets=lambda root: csv(
            root,
            "商品.csv",
            [["sku_id", "category", "name", "min_price", "unit", "适用设备"],
             ["P001", "device", "超声波治疗仪CSY-200（台式）", 2500, "台", "C001"],
             ["C001", "consumable", "超声贴片", 2, "袋", ""]],
        ),
        raw={"products": [P001, C001], "packages": [], "bindings": [binding("P001", "C001")]},
        expected_products=[P001, C001],
        expected_bindings=[("P001", "C001")],
        tags=("csv", "reader"),
    ),
    GoldenCase(
        key="txt_plain",
        title="纯文本：自然语言描述的商品与兼容关系",
        assets=lambda root: txt(
            root,
            "业务说明.txt",
            "设备 P001 超声波治疗仪CSY-200（台式），最低价 2500 元/台。\n"
            "耗材 C001 超声贴片，最低价 2 元/袋，适用设备 P001。\n",
        ),
        raw={"products": [P001, C001], "packages": [], "bindings": [binding("P001", "C001")]},
        expected_products=[P001, C001],
        expected_bindings=[("P001", "C001")],
        tags=("text", "reader"),
    ),
    GoldenCase(
        key="docx_headings_table",
        title="Word：标题层级 + 表格 + 促销段落",
        assets=lambda root: docx(
            root,
            "业务资料.docx",
            [
                ("h", "商品清单"),
                ("t", [["sku_id", "category", "name", "最低价", "单位"],
                       ["P001", "device", "超声波治疗仪CSY-200（台式）", "2500", "台"],
                       ["C001", "consumable", "超声贴片", "2", "袋"]]),
                ("h", "套餐说明"),
                ("p", "PKG001 台式超声推广套餐：P001 一台 + C001 两袋，售价 6000。"),
            ],
        ),
        raw={
            "products": [P001, C001],
            "packages": [package("PKG001", "台式超声推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
            "bindings": [binding("P001", "C001")],
        },
        expected_products=[P001, C001],
        expected_packages=[package("PKG001", "台式超声推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
        expected_bindings=[("P001", "C001")],
        tags=("docx", "reader"),
    ),
    GoldenCase(
        key="mixed_formats",
        title="混合资料：Excel + Markdown + Word 同目录",
        assets=lambda root: (
            xlsx(root, "主数据.xlsx", {"SKU主表": SKU_ROWS}),
            md(root, "套餐.md", "# 套餐\nPKG001 台式套餐：P001*1 + C001*2，6000 元。\n"),
            docx(root, "兼容性.docx", [("h", "兼容说明"), ("p", "C001 超声贴片适用于 P001 台式机。")]),
        ),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [package("PKG001", "台式套餐", ["P001", "C001"], [1, 2], std_price=6000)],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_packages=[package("PKG001", "台式套餐", ["P001", "C001"], [1, 2], std_price=6000)],
        expected_bindings=[SKU_DOC_BINDING],
        tags=("mixed", "reader"),
    ),
    GoldenCase(
        key="binding_pairs",
        title="设备-耗材绑定：一个设备对应多个耗材",
        assets=lambda root: xlsx(root, "兼容表.xlsx", {"SKU主表": BINDING_ROWS}),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [],
            "bindings": [binding("P001", "C001"), binding("P001", "C002")],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_bindings=[("P001", "C001"), ("P001", "C002")],
        tags=("binding",),
    ),
    GoldenCase(
        key="package_natural_language_ref",
        title="套餐引用是自然语言商品名（需归一化为 SKU）",
        assets=lambda root: xlsx(root, "产品最低价格.xlsx", {"SKU主表": SKU_ROWS, "套餐定义表": PKG_ROWS}),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [
                package("PKG001", "台式超声推广套餐", ["超声波治疗仪CSY-200（台式）", "超声贴片"], [1, 2], std_price=6000)
            ],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_packages=[package("PKG001", "台式超声推广套餐", ["P001", "C001"], [1, 2], std_price=6000)],
        expected_bindings=[SKU_DOC_BINDING],
        tags=("reconcile",),
    ),
    GoldenCase(
        key="package_ambiguous_ref",
        title="套餐引用有歧义（同时匹配多个 SKU）应被丢弃并记录",
        assets=lambda root: xlsx(
            root,
            "歧义.xlsx",
            {
                "SKU主表": [
                    SKU_HEADER,
                    ["P001", "超声波治疗仪CSY-200（台式）", 2500, "台", "", "", ""],
                    ["P002", "超声波治疗仪CSY-200A（便携）", 2600, "台", "", "", ""],
                ],
                "套餐定义表": [
                    PACKAGE_HEADER,
                    ["PKG001", "歧义套餐", "CSY-200*1", 2500, "组合装"],
                ],
            },
        ),
        raw={
            "products": [
                product("P001", "超声波治疗仪CSY-200（台式）", min_price=2500, unit="台"),
                product("P002", "超声波治疗仪CSY-200A（便携）", min_price=2600, unit="台"),
            ],
            "packages": [package("PKG001", "歧义套餐", ["CSY-200"], [1], std_price=2500)],
            "bindings": [],
        },
        expected_products=[
            product("P001", "超声波治疗仪CSY-200（台式）", min_price=2500, unit="台"),
            product("P002", "超声波治疗仪CSY-200A（便携）", min_price=2600, unit="台"),
        ],
        expected_packages=[],
        expect_issue_keywords=("同时匹配",),
        tags=("reconcile", "guardrail"),
    ),
    GoldenCase(
        key="package_unknown_sku_dropped",
        title="套餐引用了资料中不存在的 SKU → 对账阶段直接剔除（不浪费模型自愈）",
        assets=lambda root: xlsx(root, "产品最低价格.xlsx", {"SKU主表": SKU_ROWS, "套餐定义表": PKG_ROWS}),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [package("PKG001", "台式套餐", ["P001", "P999"], [1, 2], std_price=6000)],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_packages=[],
        expected_bindings=[SKU_DOC_BINDING],
        expect_issue_keywords=("无法在商品中唯一定位",),
        tags=("reconcile", "guardrail"),
    ),
    GoldenCase(
        key="package_qty_mismatch_selfheal",
        title="quantities 与 sku_ids 长度不一致 → 自愈修复",
        assets=lambda root: xlsx(root, "产品最低价格.xlsx", {"SKU主表": SKU_ROWS, "套餐定义表": PKG_ROWS}),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [package("PKG001", "台式套餐", ["P001", "C001"], [1], std_price=6000)],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        corrected={
            "products": SKU_DOC_PRODUCTS,
            "packages": [package("PKG001", "台式套餐", ["P001", "C001"], [1, 2], std_price=6000)],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_packages=[package("PKG001", "台式套餐", ["P001", "C001"], [1, 2], std_price=6000)],
        expected_bindings=[SKU_DOC_BINDING],
        tags=("self-heal",),
    ),
    GoldenCase(
        key="binding_wrong_category_selfheal",
        title="绑定左右类别颠倒 → 自愈修复",
        assets=lambda root: xlsx(root, "兼容表.xlsx", {"SKU主表": SKU_ROWS}),
        raw={
            "products": SKU_DOC_PRODUCTS,
            "packages": [],
            "bindings": [binding("C001", "P001")],
        },
        corrected={
            "products": SKU_DOC_PRODUCTS,
            "packages": [],
            "bindings": [binding("P001", "C001")],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_bindings=[("P001", "C001")],
        tags=("self-heal", "binding"),
    ),
    GoldenCase(
        key="extra_field_rejected",
        title="模型多返回字段（含成本价）→ 白名单拒绝并自愈",
        assets=lambda root: xlsx(root, "产品最低价格.xlsx", {"SKU主表": SKU_ROWS}),
        raw={
            "products": [{**P001, "cost": 1800, "stock": 12}, C001, C002],
            "packages": [],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        corrected={
            "products": SKU_DOC_PRODUCTS,
            "packages": [],
            "bindings": [binding(*SKU_DOC_BINDING)],
        },
        expected_products=SKU_DOC_PRODUCTS,
        expected_bindings=[SKU_DOC_BINDING],
        tags=("guardrail", "self-heal"),
    ),
    GoldenCase(
        key="no_package_evidence",
        title="资料没有套餐依据 → 不生成套餐",
        assets=lambda root: txt(
            root,
            "设备清单.txt",
            "设备 P001 超声波治疗仪CSY-200（台式），最低价 2500 元/台。\n耗材 C001 超声贴片，最低价 2 元/袋。\n",
        ),
        raw={"products": [P001, C001], "packages": [], "bindings": []},
        expected_products=[P001, C001],
        expected_packages=[],
        tags=("guardrail",),
    ),
    GoldenCase(
        key="duplicate_sku_unrecoverable",
        title="批次内 SKU 重复且模型无法修复 → 3 次自愈后失败回滚",
        assets=lambda root: xlsx(root, "重复.xlsx", {"SKU主表": SKU_ROWS}),
        raw={"products": [P001, P001, C001], "packages": [], "bindings": []},
        corrected=None,
        expected_products=[],
        expect_status="failed",
        expect_issue_keywords=("重复出现",),
        tags=("guardrail", "failure-path"),
    ),
    GoldenCase(
        key="selfheal_cannot_invent_products",
        title="护栏：没有商品来源时，自愈节点不得凭空新增商品",
        assets=lambda root: txt(
            root,
            "套餐说明.txt",
            "套餐 PKG001 台式超声推广套餐：售价 6000 元，买赠方案待定。\n",
        ),
        raw={"products": [], "packages": [], "bindings": []},
        corrected={"products": [P001], "packages": [], "bindings": []},
        expected_products=[],
        expect_status="failed",
        expect_issue_keywords=("拒绝自愈节点新增商品",),
        tags=("guardrail", "failure-path"),
    ),
    GoldenCase(
        key="scale_50_products",
        title="规模：一次导入 50 个商品",
        assets=lambda root: xlsx(
            root,
            "批量.xlsx",
            {
                "SKU主表": [SKU_HEADER]
                + [[f"P{i:03d}", f"设备型号{i}", 1000 + i, "台", "", "", ""] for i in range(1, 51)]
            },
        ),
        raw={
            "products": [product(f"P{i:03d}", f"设备型号{i}", "device", min_price=1000 + i, unit="台") for i in range(1, 51)],
            "packages": [],
            "bindings": [],
        },
        expected_products=[product(f"P{i:03d}", f"设备型号{i}", "device", min_price=1000 + i, unit="台") for i in range(1, 51)],
        tags=("scale",),
    ),
]


def case_by_key(key: str) -> GoldenCase:
    for case in CASES:
        if case.key == key:
            return case
    raise KeyError(key)
