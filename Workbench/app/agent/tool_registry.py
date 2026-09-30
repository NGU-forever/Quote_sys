"""Agent 工具注册表：只读 assets + 现有库查询；模型无任何写库工具。"""
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.readers.common import file_kind, safe_file_path
from app.agent.readers.excel_reader import read_excel, search_excel
from app.agent.readers.manifest import build_manifest
from app.agent.readers.text_reader import read_csv, read_markdown, read_text, search_text_file
from app.agent.readers.word_reader import read_word, search_word
from app.models.package import Package
from app.models.product import Product
from app.services.catalog_service import map_package, map_product


@dataclass
class ToolContext:
    run_id: int
    db: Session


def _args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _execute(name: str, raw_args, ctx: ToolContext) -> dict:
    args = _args(raw_args)
    if name == "list_assets":
        sub = str(args.get("path") or "").strip()
        if sub:
            from app.core.config import settings

            root = (settings.assets_root / sub).resolve()
            try:
                root.relative_to(settings.assets_root.resolve())
            except ValueError:
                return {"ok": False, "error": "路径超出 assets 目录边界"}
            if not root.is_dir():
                return {"ok": False, "error": "路径不是 assets 目录"}
            result = build_manifest(root)
            result["ok"] = True
            return result
        result = build_manifest()
        result["ok"] = True
        return result
    if name == "report_issue":
        return {
            "ok": True,
            "recorded": True,
            "message": "问题已记录，将在运行报告中展示",
        }
    if name == "lookup_existing":
        return _lookup_existing(ctx.db, args)

    path_text = str(args.get("path") or "").strip()
    try:
        path = safe_file_path(path_text)
    except (ValueError, FileNotFoundError) as exc:
        return {"ok": False, "error": str(exc)}
    kind = file_kind(path.suffix)
    if kind == "unsupported":
        return {"ok": False, "error": f"暂不支持 {path.suffix} 文件"}

    if name == "read_excel" and kind == "excel":
        return read_excel(
            path,
            sheet=args.get("sheet"),
            range_text=args.get("range"),
            headers_row=int(args.get("headers_row") or 1),
            max_rows=int(args.get("max_rows") or 5),
        )
    if name == "read_word" and kind == "word":
        return read_word(
            path,
            headings_only=bool(args.get("headings_only", True)),
            max_paragraphs=int(args.get("max_paragraphs") or 30),
        )
    if name == "read_word" and path.suffix.lower() == ".md":
        return read_markdown(path, max_rows=int(args.get("max_paragraphs") or 40))
    if name == "read_word" and path.suffix.lower() == ".csv":
        return read_csv(path, max_rows=int(args.get("max_paragraphs") or 5))
    if name == "read_word" and path.suffix.lower() == ".txt":
        return read_text(path, max_lines=int(args.get("max_paragraphs") or 80))
    if name == "read_excel":
        return {"ok": False, "error": "read_excel 只支持 .xlsx 文件"}
    if name == "read_word":
        return {"ok": False, "error": "read_word 只支持 .docx / .csv / .md / .txt 文件"}
    if name == "search_text":
        keyword = str(args.get("keyword") or "").strip()
        if not keyword:
            return {"ok": False, "error": "请提供搜索关键词"}
        max_hits = int(args.get("max_hits") or 6)
        if kind == "excel":
            return search_excel(path, keyword, max_hits=max_hits)
        if kind == "word":
            return search_word(path, keyword, max_hits=max_hits)
        if path.suffix.lower() in {".csv", ".md", ".txt"}:
            return search_text_file(path, keyword, max_hits=max_hits)
    return {"ok": False, "error": f"未知工具：{name}"}


def _lookup_existing(db: Session, args: dict) -> dict:
    entity = str(args.get("entity") or "products").strip()
    limit = max(1, min(int(args.get("limit") or 50), 200))
    if entity in {"products", "product"}:
        stmt = select(Product)
        sku = str(args.get("sku_id") or "").strip()
        keyword = str(args.get("keyword") or "").strip()
        if sku:
            stmt = stmt.where(Product.sku_id == sku)
        elif keyword:
            stmt = stmt.where(Product.name.like(f"%{keyword}%"))
        rows = db.scalars(stmt.order_by(Product.sku_id.asc()).limit(limit)).all()
        return {
            "ok": True,
            "entity": "products",
            "count": len(rows),
            "items": [map_product(db, p) for p in rows],
        }
    if entity in {"packages", "package"}:
        stmt = select(Package)
        pid = str(args.get("package_id") or "").strip()
        if pid:
            stmt = stmt.where(Package.package_id == pid)
        rows = db.scalars(stmt.order_by(Package.package_id.asc()).limit(limit)).all()
        return {
            "ok": True,
            "entity": "packages",
            "count": len(rows),
            "items": [map_package(p) for p in rows],
        }
    products = db.scalars(select(Product)).all()
    packages = db.scalars(select(Package)).all()
    from app.models.device_binding import DeviceBinding

    bindings = db.scalars(select(DeviceBinding)).all()
    return {
        "ok": True,
        "entity": "stats",
        "products": len(products),
        "devices": sum(1 for p in products if p.category == "device"),
        "consumables": sum(1 for p in products if p.category == "consumable"),
        "packages": len(packages),
        "bindings": len(bindings),
    }


def execute_tool(name: str, raw_args, ctx: ToolContext) -> dict:
    try:
        result = _execute(name, raw_args, ctx)
    except Exception as exc:  # 工具级错误只作为 Observation 返回，不中断整个 run
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "truncated": False}
    if "truncated" not in result:
        result["truncated"] = False
    return result


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_assets",
            "description": "列出 assets 目录内可读取的文件（path/type/size/mtime/sha256），支持传入一级子目录",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "可选的一级子目录"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_excel",
            "description": "读取 .xlsx：sheet 为空时列出工作表；提供 sheet/range/max_rows 时返回表头与示例行",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "sheet": {"type": "string"},
                    "range": {"type": "string", "description": "如 A2:D20"},
                    "headers_row": {"type": "integer"},
                    "max_rows": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_word",
            "description": "读取 .docx 标题/段落/表格概览；.csv/.md 读取表格内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "headings_only": {"type": "boolean"},
                    "max_paragraphs": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "在支持的文本/表格文件中定位关键词，返回命中位置与上下文",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "keyword": {"type": "string"},
                    "max_hits": {"type": "integer"},
                },
                "required": ["path", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_existing",
            "description": "只读现有库：查商品/套餐或统计，避免生成重复 SKU",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "enum": ["products", "packages", "stats"]},
                    "sku_id": {"type": "string"},
                    "package_id": {"type": "string"},
                    "keyword": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["entity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report_issue",
            "description": "记录资料缺失、歧义或不可消歧问题，问题会出现在最终运行报告",
            "parameters": {
                "type": "object",
                "properties": {"description": {"type": "string"}},
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_candidates",
            "description": "提交规范化候选 JSON（唯一受控写库入口；服务端校验后才可入库）",
            "parameters": {
                "type": "object",
                "properties": {
                    "products": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "sku_id": {"type": "string"},
                                "category": {"type": "string", "enum": ["device", "consumable"]},
                                "name": {"type": "string"},
                                "min_price": {"type": ["number", "null"]},
                                "max_price": {"type": ["number", "null"]},
                                "unit": {"type": ["string", "null"]},
                                "pieces_per_unit": {"type": ["integer", "null"]},
                                "units_per_box": {"type": ["integer", "null"]},
                                "box_price": {"type": ["number", "null"]},
                                "applicable_devices": {"type": ["string", "null"]},
                                "raw_price_desc": {"type": ["string", "null"]},
                                "remark": {"type": ["string", "null"]},
                                "image": {"type": ["string", "null"]},
                            },
                            "required": ["sku_id", "category", "name"],
                        },
                    },
                    "packages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "package_id": {"type": "string"},
                                "name": {"type": "string"},
                                "sku_ids": {"type": "array", "items": {"type": "string"}},
                                "quantities": {"type": "array", "items": {"type": "number"}},
                                "std_price": {"type": ["number", "null"]},
                                "discount_price": {"type": ["number", "null"]},
                                "discount_rate": {"type": ["string", "null"]},
                                "device_qty": {"type": ["integer", "null"]},
                                "consumable_qty": {"type": ["integer", "null"]},
                                "consumable_boxes": {"type": ["integer", "null"]},
                                "fixed_bundle": {"type": ["boolean", "integer"]},
                                "device_price": {"type": ["number", "null"]},
                                "note": {"type": ["string", "null"]},
                            },
                            "required": ["package_id", "name", "sku_ids", "quantities"],
                        },
                    },
                    "bindings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "device_sku_id": {"type": "string"},
                                "consumable_sku_id": {"type": "string"},
                            },
                            "required": ["device_sku_id", "consumable_sku_id"],
                        },
                    },
                    "issues": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["products", "packages", "bindings", "issues"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "候选已通过服务端校验后结束 ReAct，进入事务 apply/report",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
