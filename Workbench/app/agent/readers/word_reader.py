"""python-docx 只读 Word 工具：标题树/表格概览与段落预览。"""
from pathlib import Path

from docx import Document


def _is_heading(style_name: str | None) -> bool:
    name = (style_name or "").lower()
    return name.startswith("heading") or "标题" in name


def _safe_table_columns(table) -> int:
    """安全获取表格列数，杜绝合并单元格或不规则网格触发 IndexError。"""
    try:
        return len(table.columns)
    except Exception:
        return max((len(row.cells) for row in table.rows), default=0)


def read_word(path: Path, headings_only: bool = False, max_paragraphs: int = 30) -> dict:
    max_paragraphs = max(1, min(int(max_paragraphs or 30), 200))
    doc = Document(str(path))
    paragraphs = [p for p in doc.paragraphs if p.text and p.text.strip()]
    selected = []
    for p in paragraphs:
        style_name = p.style.name if getattr(p, "style", None) else "Normal"
        if headings_only and not _is_heading(style_name):
            continue
        if len(selected) >= max_paragraphs:
            break
        selected.append(
            {
                "style": style_name,
                "text": p.text.strip(),
            }
        )
    tables = []
    for i, table in enumerate(doc.tables[:20]):
        rows = list(table.rows)
        tables.append(
            {
                "index": i,
                "rows": len(rows),
                "columns": _safe_table_columns(table),
                "preview": [
                    [cell.text.strip()[:60] for cell in row.cells[:8]] for row in rows[:3]
                ],
            }
        )
    return {
        "ok": True,
        "paragraph_count": len(paragraphs),
        "heading_tree": selected if headings_only else [s["text"] for s in selected[:15]],
        "paragraph_preview": None if headings_only else selected,
        "tables": tables,
        "truncated": len(paragraphs) > max_paragraphs or len(doc.tables) > len(tables),
    }


def search_word(path: Path, keyword: str, max_hits: int = 6) -> dict:
    doc = Document(str(path))
    hits = []
    for i, p in enumerate(doc.paragraphs, start=1):
        if p.text and keyword.lower() in p.text.lower():
            hits.append({"kind": "paragraph", "index": i, "text": p.text.strip()[:160]})
            if len(hits) >= max_hits:
                return {"ok": True, "keyword": keyword, "hits": hits, "truncated": True}
    for table in doc.tables:
        seen_cells = set()
        for row in table.rows:
            for cell in row.cells:
                # 利用底层的 xml element 内存 id 避免跨行跨列合并单元格重复搜索
                cell_id = id(cell._tc)
                if cell_id in seen_cells:
                    continue
                seen_cells.add(cell_id)
                if keyword.lower() in cell.text.lower():
                    hits.append({"kind": "table", "text": cell.text.strip()[:160]})
                    if len(hits) >= max_hits:
                        return {"ok": True, "keyword": keyword, "hits": hits, "truncated": True}
    return {"ok": True, "keyword": keyword, "hits": hits, "truncated": False}
