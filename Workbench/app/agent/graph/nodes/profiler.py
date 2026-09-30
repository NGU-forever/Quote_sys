"""来源定位节点：真实模型下用有界工具循环（ReAct）定位，规则引擎兜底。

- ``enable_tool_loop=True``（真实 LLM）时：模型可用 list_assets / read_excel /
  read_word / search_text / lookup_existing 自主探测，再用 submit_sources_plan 提交；
  提交内容逐条过服务端校验（文件必须来自清单、工作表必须真实存在）。
- 未启用或模型未给出有效计划时：回退到确定性规则定位，保证离线/弱模型下依然可用。
"""
from pathlib import Path

from app.agent.graph.react import run_tool_loop
from app.agent.graph.runtime import GraphRuntime
from app.agent.graph.state import AgentGraphState
from app.agent.prompts import profiler_system_prompt, profiler_user_prompt
from app.agent.readers.common import safe_file_path
from app.agent.readers.excel_reader import read_excel
from app.agent.readers.text_reader import read_csv, read_markdown, read_text
from app.agent.readers.word_reader import read_word
from app.agent.tool_registry import TOOL_SCHEMAS, ToolContext, execute_tool


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


_HEADER_PROBE_ROWS = (1, 2, 3)


def _sheet_summary(path: Path, sheet_name: str) -> dict:
    """探测工作表表头行。

    真实价目表常有「标题行 + 表头行」结构（表头落在第 2/3 行），固定按第 1 行
    取表头会漏检。这里在前 3 行里挑匹配到最多业务表头的一行。
    """
    best: dict | None = None
    best_score = -1
    for header_row in _HEADER_PROBE_ROWS:
        summary = read_excel(path, sheet=sheet_name, headers_row=header_row, max_rows=3)
        if not summary.get("ok"):
            return summary
        headers = [header for header in (summary.get("headers") or []) if header is not None]
        score = sum(
            1
            for header in headers
            if _matches(str(header), PRODUCT_HEADERS)
            or _matches(str(header), BINDING_TERMS)
            or _matches(str(header), PACKAGE_TERMS)
        )
        if score > best_score:
            best, best_score = summary, score
    return best or {}


def _profile_excel(rel_path: str, path: Path, products: list[dict], packages: list[dict], bindings: list[dict]) -> None:
    overview = read_excel(path)
    for sheet in overview.get("sheets", []):
        summary = _sheet_summary(path, sheet["name"])
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


def _deterministic_plan(state: AgentGraphState) -> dict:
    """规则定位：不依赖模型，按表头/关键词启发式圈定来源。"""
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

    # 系统提示允许依据「套餐定义」推导设备-耗材绑定，因此套餐来源同时作为绑定来源，
    # 否则只有套餐章节、没有「适用设备」列的资料会漏掉绑定提取。
    for source in packages:
        _append_source(bindings, source)

    return {
        "products": products,
        "packages": packages,
        "bindings": bindings,
    }


# --------------------------------------------------------------------------
# 工具循环（ReAct）路径
# --------------------------------------------------------------------------

_PROFILER_TOOL_NAMES = {
    "list_assets",
    "read_excel",
    "read_word",
    "search_text",
    "lookup_existing",
    "report_issue",
}

_SOURCE_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "file": {"type": "string", "description": "assets 清单中的相对路径"},
        "sheet": {"type": ["string", "null"], "description": "Excel 工作表名"},
        "table": {"type": ["integer", "null"], "description": "Word 中的表格序号（从 0 开始）"},
        "section": {"type": ["string", "null"], "description": "章节/小节标题"},
        "column": {"type": ["string", "null"], "description": "列标题"},
    },
    "required": ["file"],
}

_SUBMIT_PLAN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_sources_plan",
        "description": (
            "提交来源计划：products/packages/bindings 各自列出承载该数据的文件与定位信息，"
            "提交后服务端会逐条校验。"
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "products": {"type": "array", "items": _SOURCE_ITEM_SCHEMA},
                "packages": {"type": "array", "items": _SOURCE_ITEM_SCHEMA},
                "bindings": {"type": "array", "items": _SOURCE_ITEM_SCHEMA},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["products", "packages", "bindings"],
        },
    },
}


def _profiler_tool_schemas() -> list[dict]:
    """只暴露只读探测工具 + 提交工具（模型没有任何写库能力）。"""
    tools = [
        schema
        for schema in TOOL_SCHEMAS
        if (schema.get("function") or {}).get("name") in _PROFILER_TOOL_NAMES
    ]
    tools.append(_SUBMIT_PLAN_SCHEMA)
    return tools


def _submit_plan(arguments: dict) -> dict:
    """终止工具：把模型提交的内容规整成内部结构。"""
    return {
        "products": arguments.get("products") or [],
        "packages": arguments.get("packages") or [],
        "bindings": arguments.get("bindings") or [],
        "issues": [
            str(issue) for issue in (arguments.get("issues") or []) if str(issue).strip()
        ],
    }


def _sheet_names(rel_path: str) -> set[str]:
    try:
        overview = read_excel(safe_file_path(rel_path))
    except Exception:
        return set()
    return {
        str(sheet.get("name"))
        for sheet in (overview.get("sheets") or [])
        if sheet.get("name")
    }


def _validated_sources(
    raw: object,
    file_index: dict[str, dict],
    sheet_cache: dict[str, set[str]],
) -> tuple[list[dict], list[str]]:
    """逐条校验模型给出的来源：文件必须在清单内，工作表必须真实存在。"""
    valid: list[dict] = []
    issues: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        file = str(item.get("file") or "").strip()
        meta = file_index.get(file)
        if meta is None:
            issues.append(f"模型给出的来源「{file or '(空)'}」不在 assets 清单中，已丢弃")
            continue

        locator: dict = {}
        sheet = item.get("sheet")
        if isinstance(sheet, str) and sheet.strip():
            if meta.get("type") == "excel":
                if file not in sheet_cache:
                    sheet_cache[file] = _sheet_names(file)
                if sheet.strip() in sheet_cache[file]:
                    locator["sheet"] = sheet.strip()
                else:
                    issues.append(f"{file} 不存在工作表「{sheet.strip()}」，已忽略该定位")
            else:
                issues.append(f"{file} 不是 Excel，sheet 定位已忽略")
        for key in ("section", "column"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                locator[key] = value.strip()
        table = item.get("table")
        if isinstance(table, int) and not isinstance(table, bool):
            locator["table"] = table

        source = {"file": file, "type": meta.get("type")}
        if locator:
            source["locator"] = locator
        valid.append(source)
    return valid, issues


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    """同一文件既有精确 locator 又有文件级兜底时，只保留精确的那条。"""
    located_files = {source["file"] for source in sources if source.get("locator")}
    return [
        source
        for source in sources
        if source.get("locator") or source["file"] not in located_files
    ]


def _build_plan(terminal: dict, file_index: dict[str, dict]) -> tuple[dict, list[str]]:
    sheet_cache: dict[str, set[str]] = {}
    issues: list[str] = []
    plan: dict = {"products": [], "packages": [], "bindings": []}
    for key in ("products", "packages", "bindings"):
        sources, source_issues = _validated_sources(terminal.get(key), file_index, sheet_cache)
        issues.extend(source_issues)
        bucket = plan[key]
        for source in _dedupe_sources(sources):
            _append_source(bucket, source)
    return plan, issues


def _conflict_policy(state: AgentGraphState) -> str:
    mode = str(state.get("mode") or "dry-run")
    return (
        f"mode={mode}：名称冲突跳过并记录 issue，绝不静默改名；"
        "没有资料依据的套餐一律不生成"
    )


def profiler_node(state: AgentGraphState, runtime: GraphRuntime) -> dict:
    """定位来源：真实模型走工具循环，其余情况走确定性规则。"""
    baseline = _deterministic_plan(state)
    file_index = {
        str(item.get("path")): item
        for item in (state.get("manifest") or {}).get("files", [])
        if item.get("supported")
    }
    if not getattr(runtime, "enable_tool_loop", False) or not file_index:
        return {"sources_plan": baseline}

    outcome = run_tool_loop(
        runtime,
        node="profiler_node",
        system_prompt=profiler_system_prompt(runtime.max_steps),
        user_prompt=profiler_user_prompt(
            state.get("manifest") or {},
            state.get("db_stats") or {},
            _conflict_policy(state),
        ),
        tool_schemas=_profiler_tool_schemas(),
        execute=lambda name, args: execute_tool(
            name, args, ToolContext(run_id=int(state.get("run_id") or 0), db=runtime.db)
        ),
        terminal_tools={"submit_sources_plan": _submit_plan},
        max_steps=runtime.max_steps,
    )

    issues: list[str] = list(outcome.issues)
    if outcome.finished and isinstance(outcome.terminal, dict):
        plan, plan_issues = _build_plan(outcome.terminal, file_index)
        issues.extend(plan_issues)
        issues.extend(outcome.terminal.get("issues") or [])
        if any(plan.values()):
            return {
                "sources_plan": plan,
                "issues": issues,
                "react_trace": outcome.trace,
            }
        issues.append("模型提交的来源计划为空或全部不合法，已回退到规则定位")

    return {
        "sources_plan": baseline,
        "issues": issues,
        "react_trace": outcome.trace,
    }
