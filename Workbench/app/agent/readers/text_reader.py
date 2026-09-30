"""CSV / Markdown 轻量结构化读取与关键词搜索。"""
import csv
from pathlib import Path
import re


CANDIDATE_ENCODINGS = ("utf-8-sig", "gb18030", "gbk", "utf-16", "big5")
TABLE_SPLIT_REGEX = re.compile(r"^:?-+:?$")


def _decode_bytes(raw_bytes: bytes) -> str:
    for enc in CANDIDATE_ENCODINGS:
        try:
            return raw_bytes.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _is_markdown_separator_row(cells: list[str]) -> bool:
    """判断当前行是否为 | :--- | :---: | ---: | 等表头分隔行。"""
    if not cells:
        return False
    return all(bool(TABLE_SPLIT_REGEX.match(c.strip())) for c in cells if c.strip())


def read_csv(path: Path, max_rows: int = 5) -> dict:
    max_rows = max(1, min(int(max_rows), 100))
    raw_bytes = path.read_bytes()
    text = _decode_bytes(raw_bytes)

    sample_text = text[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters=[",", "\t", ";", "|"])
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    # 扩大字段上限，防御超长备注
    try:
        csv.field_size_limit(10 * 1024 * 1024)
    except Exception:
        pass

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    rows = [row for row in reader if any(str(c).strip() for c in row)]
    headers = rows[0] if rows else []
    sample = rows[1 : max_rows + 1]
    return {
        "ok": True,
        "headers": headers,
        "sample_rows": sample,
        "row_count": max(0, len(rows) - 1),
        "truncated": len(sample) < max(0, len(rows) - 1),
    }


def read_markdown(path: Path, max_rows: int = 40) -> dict:
    raw_bytes = path.read_bytes()
    text = _decode_bytes(raw_bytes)
    lines = text.splitlines()
    headings = []
    tables = []
    current: dict | None = None
    body: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append({"level": len(stripped) - len(stripped.lstrip("#")), "text": stripped.lstrip("#").strip()})
            if current and current["rows"]:
                tables.append(current)
            current = None
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if current is None:
                current = {"headers": cells, "rows": [], "start_line": i + 1}
            elif _is_markdown_separator_row(cells):
                # 过滤任何对齐分隔行（例如 | :--- | :---: | ---: |）
                pass
            else:
                current["rows"].append(cells)
        elif current:
            tables.append(current)
            current = None
        elif stripped:
            body.append(stripped)
    if current:
        tables.append(current)
    return {
        "ok": True,
        "headings": headings,
        "paragraph_preview": body[:max_rows],
        "tables": [
            {
                "index": i,
                "headers": table["headers"],
                "rows": table["rows"][:max_rows],
                "row_count": len(table["rows"]),
                "start_line": table["start_line"],
            }
            for i, table in enumerate(tables)
        ],
        "paragraph_count": len(body),
        "truncated": len(body) > max_rows,
    }


def read_text(path: Path, max_lines: int = 80) -> dict:
    """Read a plain-text note as lightweight paragraphs and lines."""
    max_lines = max(1, min(int(max_lines), 500))
    raw_bytes = path.read_bytes()
    text = _decode_bytes(raw_bytes)
    lines = text.splitlines()
    paragraphs = [line.strip() for line in lines if line.strip()]
    return {
        "ok": True,
        "headings": [],
        "paragraph_preview": paragraphs[:max_lines],
        "tables": [],
        "paragraph_count": len(paragraphs),
        "truncated": len(paragraphs) > max_lines,
    }


def search_text_file(path: Path, keyword: str, max_hits: int = 6) -> dict:
    hits = []
    raw_bytes = path.read_bytes()
    text = _decode_bytes(raw_bytes)
    for index, line in enumerate(text.splitlines(), start=1):
        if keyword.lower() in line.lower():
            hits.append({"line": index, "text": line.strip()[:160]})
            if len(hits) >= max_hits:
                return {"ok": True, "keyword": keyword, "hits": hits, "truncated": True}
    return {"ok": True, "keyword": keyword, "hits": hits, "truncated": False}
