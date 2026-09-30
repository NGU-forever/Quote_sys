"""Lightweight content profiler that locates product/package/binding sources."""
from pathlib import Path

from app.agent.graph.state import AgentGraphState
from app.agent.readers.common import safe_file_path
from app.agent.readers.excel_reader import read_excel
from app.agent.readers.text_reader import read_csv, read_markdown, read_text
from app.agent.readers.word_reader import read_word


PRODUCT_HEADERS = {
    "sku_id",
    "sku",
    "编号",
    "规格",
    "最低价",
    "底价",
    "单位",
    "每箱",
    "产品名称",
    "计价单位",
}
PACKAGE_TERMS = {
    "套餐",
    "促销",
    "赠机",
    "满赠",
    "买x赠y",
    "买",
    "送",
    "整购",
}
BINDING_TERMS = {"适用设备", "适用机型", "搭配", "专用", "兼容"}


def _blob(*values) -> str:
    return " ".join(str(value) for value in values if value is not None).lower()


def _matches(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _append_source(target: list[dict], source: dict) -> None:
    key = (
        source["file"],
        source.get("locator", {}).get("sheet"),
        source.get("locator", {}).get("section"),
        source.get("locator", {}).get("column"),
    )
    existing = {
        (
            item["file"],
            item.get("locator", {}).get("sheet"),
            item.get("locator", {}).get("section"),
            item.get("locator", {}).get("column"),
        )
        for item in target
    }
    if key not in existing:
        target.append(source)


def _matching_section(text: str, terms: set[str]) -> str | None:
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            current = line.lstrip("#").strip()
            continue
        if _matches(line, terms):
            return current or line[:80]
    return None


def _profile_excel(rel_path: str, path: Path, products: list[dict], packages: list[dict], bindings: list[dict]) -> None:
    overview = read_excel(path)
    for sheet in overview.get("sheets", []):
        summary = read_excel(path, sheet=sheet["name"], max_rows=3)
        if not summary.get("ok"):
            continue
        headers = summary.get("headers") or []
        rows = summary.get("sample_rows") or []
        header_text = _blob(*headers)
        content_text = _blob(header_text, *[cell for row in rows for cell in row])
        base = {"file": rel_path, "type": "excel"}
        if _matches(header_text, PRODUCT_HEADERS):
            locator = {"sheet": sheet["name"], "headers": headers}
            _append_source(products, {**base, "locator": locator})
        if _matches(content_text, PACKAGE_TERMS):
            _append_source(
                packages,
                {**base, "locator": {"sheet": sheet["name"], "is_table": True}},
            )
        binding_columns = [
            str(header)
            for header in headers
            if header is not None and _matches(str(header), BINDING_TERMS)
        ]
        for column in binding_columns:
            _append_source(
                bindings,
                {
                    **base,
                    "locator": {
                        "sheet": sheet["name"],
                        "column": column,
                    },
                },
            )


def _profile_text(rel_path: str, path: Path, products: list[dict], packages: list[dict], bindings: list[dict]) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        summary = read_csv(path, max_rows=100)
        headers = summary.get("headers") or []
        rows = summary.get("sample_rows") or []
        header_text = _blob(*headers)
        content_text = _blob(header_text, *[cell for row in rows for cell in row])
        if _matches(header_text, PRODUCT_HEADERS):
            _append_source(
                products,
                {"file": rel_path, "type": "text", "locator": {"headers": headers}},
            )
        if _matches(content_text, PACKAGE_TERMS):
            _append_source(
                packages,
                {"file": rel_path, "type": "text", "locator": {"section": "document", "is_table": True}},
            )
        if _matches(header_text, BINDING_TERMS):
            _append_source(
                bindings,
                {"file": rel_path, "type": "text", "locator": {"column": "适用设备"}},
            )
        return

    summary = read_markdown(path, max_rows=200) if suffix == ".md" else read_text(path, max_lines=200)
    raw_text = path.read_text(encoding="utf-8-sig", errors="replace")
    table_text = _blob(
        *[
            value
            for table in summary.get("tables", [])
            for value in [table.get("headers"), table.get("rows")]
        ]
    )
    paragraphs = _blob(*summary.get("paragraph_preview", []))
    base = {"file": rel_path, "type": "text"}
    if _matches(table_text, PRODUCT_HEADERS) or _matches(paragraphs, PRODUCT_HEADERS):
        section = _matching_section(raw_text, PRODUCT_HEADERS)
        _append_source(
            products,
            {**base, "locator": {"section": section or "document"}},
        )
    package_section = _matching_section(raw_text, PACKAGE_TERMS)
    if package_section:
        _append_source(
            packages,
            {**base, "locator": {"section": package_section, "is_table": False}},
        )
    binding_section = _matching_section(raw_text, BINDING_TERMS)
    if binding_section:
        _append_source(
            bindings,
            {**base, "locator": {"section": binding_section}},
        )


def _profile_word(rel_path: str, path: Path, products: list[dict], packages: list[dict], bindings: list[dict]) -> None:
    summary = read_word(path, headings_only=False, max_paragraphs=200)
    base = {"file": rel_path, "type": "word"}
    for table in summary.get("tables", []):
        preview = table.get("preview") or []
        headers = preview[0] if preview else []
        table_text = _blob(*preview)
        if _matches(_blob(*headers), PRODUCT_HEADERS):
            _append_source(products, {**base, "locator": {"table": table["index"]}})
        if _matches(table_text, PACKAGE_TERMS):
            _append_source(
                packages,
                {**base, "locator": {"table": table["index"], "is_table": True}},
            )
        if _matches(_blob(*headers), BINDING_TERMS):
            _append_source(
                bindings,
                {**base, "locator": {"table": table["index"], "column": "适用设备"}},
            )

    current_section = None
    for paragraph in summary.get("paragraph_preview") or []:
        text = str(paragraph.get("text") or "").strip()
        style = str(paragraph.get("style") or "")
        if not text:
            continue
        if style.lower().startswith("heading") or "标题" in style:
            current_section = text
            continue
        if _matches(text, PACKAGE_TERMS):
            _append_source(
                packages,
                {**base, "locator": {"section": current_section or text[:80], "is_table": False}},
            )
        if _matches(text, PRODUCT_HEADERS):
            _append_source(
                products,
                {**base, "locator": {"section": current_section or text[:80]}},
            )
        if _matches(text, BINDING_TERMS):
            _append_source(
                bindings,
                {**base, "locator": {"section": current_section or text[:80]}},
            )


def profiler_node(state: AgentGraphState) -> dict:
    """Locate relevant data blocks without asking a model to infer content."""
    products: list[dict] = []
    packages: list[dict] = []
    bindings: list[dict] = []
    for item in state.get("manifest", {}).get("files", []):
        if not item.get("supported"):
            continue
        try:
            path = safe_file_path(item["path"])
        except (ValueError, FileNotFoundError):
            continue
        kind = item.get("type")
        if kind == "excel":
            _profile_excel(item["path"], path, products, packages, bindings)
        elif kind == "word":
            _profile_word(item["path"], path, products, packages, bindings)
        elif kind == "text":
            _profile_text(item["path"], path, products, packages, bindings)

    return {
        "sources_plan": {
            "products": products,
            "packages": packages,
            "bindings": bindings,
        }
    }
