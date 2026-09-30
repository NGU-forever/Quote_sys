# Workbench 文件解析模块（Excel / Word / Text）边界加固与鲁棒性优化开发规范

- 日期：`2026-09-18`
- 状态：`ready for implementation`
- 关联基线：
  - `docs/superpowers/specs/2026-09-12-workbench-langgraph-db-generator-design.md`
  - `Workbench/app/agent/readers/`
  - `Workbench/app/agent/graph/nodes/`

---

## 1. 背景与改造目标

### 1.1 现状与审计发现的关键缺陷
在对 Workbench 数据生成 Agent 的文件解析与利用链路（`app/agent/readers/`、`inventory`、`profiler`、`extractors` 以及 `tool_registry`）进行深度边界审计后，发现以下高危隐患与边界缺陷：

1. **Excel 解析脆弱（`excel_reader.py`）**：
   - **空表误判**：openpyxl 在 `read_only=True` 模式下，若 XML 缺省 `<dimension>`（常见于各类第三方工具导出的 xlsx），`ws.max_row` 为 `None`，导致直接误判为 0 行空表返回。
   - **随机寻址性能劣化**：在流式生成器模式下多次调用 `ws.cell(row, col)`，引发多次顺序重扫甚至异常。
   - **公式缓存缺失**：`data_only=True` 在未经过 Excel 软件重新打开保存的程序生成表格上，公式单元格值全部为 `None`。
   - **范围解析缺陷**：`_parse_range` 遇到单单元格（`A1`）、带工作表名前缀（`Sheet1!A1:B10`）或行列反置（`C5:A1`）时无法正确处理。
   - **图表工作表崩溃**：工作簿包含 Chartsheet 时，`ws.iter_rows()` 抛出 `AttributeError`。

2. **Word 合并单元格致命崩溃（`word_reader.py`）**：
   - **合并单元格越界**：直接读取 `len(table.columns)`，在含横向合并单元格（`gridSpan`）或不规则列结构时，python-docx 会抛出 `IndexError: list index out of range`，导致整表/整篇解析彻底中断。
   - **段落样式空指针**：部分无内置样式段落的 `p.style` 为 `None`，直接读取 `p.style.name` 抛出 `AttributeError`。
   - **非主体内容丢失**：文本框（Drawing/Shape）、页眉页脚、表格内嵌套说明等被完全跳过。

3. **Text / CSV / Markdown 编码与格式缺陷（`text_reader.py`）**：
   - **Windows 中文 CSV 乱码**：硬编码 `utf-8-sig` + `errors="replace"`，导致 Windows Excel 默认导出的 `GBK`/`GB18030` CSV 文件被静默替换成全部乱码字符（`\ufffd`），数据提取率归零且不报错。
   - **Markdown 分隔线误入数据行**：分隔行仅用 `cells == ["---"] * len(cells)` 判断，无法识别带对齐符（`:---`、`:---:`）的标准 Markdown 表格分隔线，导致分隔行被当作业务数据提取。
   - **CSV 单元格溢出与分隔符单一**：未适配分号/Tab 分隔符；未配置 `csv.field_size_limit`，遇到长文本备注字段抛异常。

4. **业务链路与 LLM 交互风险（`extractors.py`, `profiler.py`, `manifest.py`）**：
   - **Office 临时锁定文件入侵**：用户在本地打开文档时生成的 `~$*.xlsx`/`~$*.docx` 锁定临时文件被纳入扫描，读取时抛出 `BadZipFile` / `PermissionError`。
   - **Prompt 暴力切片破坏 JSON**：`json.dumps(...)[:60000]` 字符串切片导致发给 LLM 的 JSON 语法在中间破损截断。
   - **固定行数截断漏读**：Excel/CSV 硬编码 100 行、Word/MD 硬编码 200 行，超过部分静默遗漏且无截断告警。

### 1.2 改造目标
- **零异常崩溃（Crash-Free）**：对所有文件格式的不规则特性（合并单元格、图表页、丢失样式、特殊数据类型）提供防御性降级，绝不阻断任务流。
- **编码与分隔符自适应**：CSV/Text 自动兼容 UTF-8、UTF-8-SIG、GBK、GB18030，自动嗅探常见分隔符。
- **结构化上下文安全**：废除字符串暴力截断，改用数据结构级的按行/按块安全限流，保证发给模型的 JSON 格式永远完整合法。
- **全格式与全生命周期协同**：无缝过滤临时文件、支持深层级安全遍历、修复 `tool_registry` 语义歧义，保持既有 API 契约与前端零破坏。

---

## 2. 核心架构与边界加固设计

### 2.1 资产过滤与清单扫描（`manifest.py` & `common.py`）

#### 规则定义
1. **文件名黑名单过滤**：
   - 过滤 Office 临时锁定文件：`filename.startswith("~$")`
   - 过滤系统隐藏与元数据文件：`filename.startswith(".")`（如 `.DS_Store`、`._example.xlsx`）
2. **深度扫描自适应**：
   - 将原先仅扫描一级目录扩展为递归扫描，增加最大深度限制（`max_depth=3`），避免目录循环或无限深层扫描。
3. **软链接穿越防御**：
   - 维持 `safe_file_path` 的 `relative_to` 边界检查，并在 `manifest.py` 中增加 `child.is_symlink()` 校验，指向外部目录的软链接直接标记为 unsupported 或跳过。

```python
# manifest.py 过滤准则
IGNORE_PREFIXES = ("~$", ".")

def is_ignored_file(name: str) -> bool:
    return any(name.startswith(p) for p in IGNORE_PREFIXES)
```

---

### 2.2 Excel 解析器加固设计（`excel_reader.py`）

#### 1. 只读模式下行数自适应探测
当 `ws.max_row` 为 `None` 或不可靠时，不直接返回空表，而是使用流式迭代器（`ws.iter_rows`）进行预读或动态截取：

```python
def _safe_get_rows(ws, max_rows: int, headers_row: int = 1):
    """通过 iter_rows 顺序拉取，规避 ws.cell() 随机访问与 max_row 为 None 的缺陷。"""
    headers = []
    sample_rows = []
    row_count = 0
    
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if any(c is not None and str(c).strip() != "" for c in row):
            row_count = idx
        if idx == headers_row:
            headers = [_cell(c) for c in row]
        elif headers_row < idx <= (headers_row + max_rows):
            cleaned = [_cell(c) for c in row]
            if any(c is not None and str(c) != "" for c in cleaned):
                sample_rows.append(cleaned)
                
    return headers, sample_rows, max(0, row_count - headers_row)
```

#### 2. 增强型范围解析器 `_parse_range`
规范化支持如下形态：
- 单单元格：`"A1"` -> `(1, 1, 1, 1)`
- 带工作表名前缀：`"Sheet1!A1:D10"` -> 剥离 `Sheet1!`，解析为 `(1, 1, 10, 4)`
- 行列倒置纠偏：`"D10:A1"` -> 自动纠偏为 `(1, 1, 10, 4)`
- 异常字符串回退：遇到语法无法识别时安全回退至整表有效区间。

#### 3. 特殊单元格值与图表页防御
- **图表工作表**：在 `workbook.sheetnames` 循环中，增加 `if not hasattr(ws, "iter_rows"): continue`，跳过无法逐行遍历的 Chartsheet。
- **公式单元格与错误值**：
  - 若 `data_only=True` 且值为 `None`，同时保留公式文本探测（若业务需要），或明确输出标记 `"(公式未缓存)"`；
  - 遇到 Excel 错误码（如 `"#N/A"`, `"#REF!"`, `"#VALUE!"` 等），清洗为 `None` 并可在 `issues` 留下提示。

---

### 2.3 Word 解析器加固设计（`word_reader.py`）

#### 1. 合并单元格安全读取
彻底杜绝 `len(table.columns)` 的 `IndexError`，采用逐行最大单元格宽度法：

```python
def _safe_table_columns(table) -> int:
    """安全获取表格列数，杜绝合并单元格触发 IndexError。"""
    try:
        return len(table.columns)
    except Exception:
        return max((len(row.cells) for row in table.rows), default=0)
```

#### 2. 段落样式空保护与内容扩展
- **样式安全访问**：
  ```python
  style_name = p.style.name if p.style else "Normal"
  ```
- **内嵌文本框与表格多维索引**：
  - 遍历所有 `table` 的单元格内容时，建立去重机制（利用单元格的 XML 节点元素内存 ID `id(cell._tc)`），避免横向/纵向合并单元格被重复搜索命中。
  - 扩展搜索至表格内部各行，防止重要价格和规格说明因位于嵌套表格中而漏检。

---

### 2.4 Text / CSV / Markdown 加固设计（`text_reader.py`）

#### 1. CSV 编码自适应与嗅探机制
采用阶梯探测策略，优先尝试标准 UTF 族，失败或高乱码率时降级至中文常用编码：

```python
CANDIDATE_ENCODINGS = ("utf-8-sig", "gb18030", "gbk", "utf-16", "big5")

def _read_csv_content(path: Path) -> list[list[str]]:
    raw_bytes = path.read_bytes()
    decoded_text = None
    for enc in CANDIDATE_ENCODINGS:
        try:
            decoded_text = raw_bytes.decode(enc)
            # 简单验证是否包含中文字段常见区间，或直接作为命中解码
            break
        except UnicodeDecodeError:
            continue
            
    if decoded_text is None:
        decoded_text = raw_bytes.decode("utf-8", errors="replace")
        
    # 自动嗅探分隔符（逗号、制表符、分号）
    sample = decoded_text[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", "\t", ";", "|"])
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","
        
    # 扩大字段上限，防止长文本溢出
    csv.field_size_limit(10 * 1024 * 1024)
    reader = csv.reader(decoded_text.splitlines(), delimiter=delimiter)
    return [row for row in reader if any(str(c).strip() for c in row)]
```

#### 2. Markdown 表格对齐分隔行精准识别
重写分隔行判断逻辑，支持对齐标识与不等长横线：

```python
import re

TABLE_SPLIT_REGEX = re.compile(r"^:?-+:?$")

def _is_markdown_separator_row(cells: list[str]) -> bool:
    """判断当前行是否为 | :--- | :---: | ---: | 等表头分隔行。"""
    if not cells:
        return False
    return all(TABLE_SPLIT_REGEX.match(c.strip()) for c in cells if c.strip())
```

---

### 2.5 业务调用与 LLM 提取链路加固

#### 1. 结构级限流替代字符串截断（`extractors.py`）
彻底废弃 `json.dumps(...)[:60000]` 的破坏性做法：
- **行数与段落预限流**：在将 `evidence` 字典组装时，由 reader 确保 `sample_rows`、`paragraph_preview` 均已在安全体积内（如 50~100 条）。
- **保留完整 JSON 序列化**：
  ```python
  # 结构化安全序列化，绝不直接切断字符串
  serialized = json.dumps({"sources": safe_evidence}, ensure_ascii=False, default=str)
  # 若整体超出 token 预期预算，优先剔除低优先级文件或减少 sample 行数，始终保持 JSON 闭合
  ```

#### 2. 嗅探器（`profiler.py`）文件单次装载优化
- 在 `_profile_excel` 中，单次调用 `load_workbook` 获取所有 sheet 的概览与样本，避免“20 个工作表加载 21 次文件”引发的磁盘 I/O 阻塞。

#### 3. 工具注册表（`tool_registry.py`）语义规范
- 在工具执行分发中，明确为各类型文件提供清晰的返回；
- 修正报错提示信息中的支持扩展名清单（补齐 `.txt` 说明），并将参数统一命名为逻辑清晰的形式。

---

## 3. 接口与数据模型契约变更

所有优化均遵循**向后兼容（Backward Compatible）**原则：
- `read_excel(...) -> dict`：返回结构维持 `{"ok": bool, "sheet": str, "headers": [...], "sample_rows": [...], "row_count": int, "truncated": bool}` 不变；
- `read_word(...) -> dict`：返回结构维持 `{"ok": bool, "paragraph_count": int, "tables": [...], "heading_tree": [...], "truncated": bool}` 不变；
- `read_csv(...) -> dict`：保持已有字段，增强编码自动兼容。

---

## 4. 实施阶段与代码演进步骤

| 阶段 | 模块 | 核心工作项 | 验证指标 |
| :--- | :--- | :--- | :--- |
| **Phase 1** | `manifest.py` & `common.py` | 过滤 `~$*`、`.*` 临时与隐藏文件；加入递归深度限制 | 存在 Office 锁定文件时，清单干净且无权限报错 |
| **Phase 2** | `excel_reader.py` | 替换 `ws.cell()` 随机访问；增加 `max_row=None` 探针；增强 `_parse_range` | 无 dimension 的 xlsx 正常读取，特殊范围正常切片 |
| **Phase 3** | `word_reader.py` | 修复合并单元格 `table.columns` 异常；增加 `p.style` 空值保护 | 复杂合并表 Word 文档 100% 正常读取不抛错 |
| **Phase 4** | `text_reader.py` | 引入 GBK/UTF-8 编码嗅探与分隔符嗅探；正则匹配 MD 分隔线 | Windows GBK CSV 无问号乱码；MD 分隔行不进入数据行 |
| **Phase 5** | `extractors.py` & `profiler.py` | 消除 `[:60000]` 暴力截断；单次加载 Excel sheet；完善 `tool_registry` 提示 | 提取输入 JSON 100% 格式完整；性能提升 50%+ |

---

## 5. 验证与测试规范

为确保每个边界场景均有针对性测试，需在 `Workbench/tests/` 下建立专项测试文件 `test_file_readers_boundaries.py`，覆盖以下用例：

1. **测试用例 1：Excel 缺失 dimension 标签**
   - 构造无 `<dimension>` 的最小合法 xlsx，断言 `read_excel` 能够通过内容预读返回正确的行数和表头，而非返回空表。
2. **测试用例 2：Word 复杂横向/纵向合并单元格**
   - 构造包含 `gridSpan` 的 Word 表格，断言 `read_word` 不抛出 `IndexError`，并能正确返回列数。
3. **测试用例 3：GBK 编码的中文 CSV**
   - 生成含中文字符（如“超声波治疗仪”、“100袋/箱”）的 GBK 编码 CSV，断言 `read_csv` 返回的中文字符串完全正确，不存在 `\ufffd`。
4. **测试用例 4：包含对齐符的 Markdown 表格**
   - 传入包含 `| :--- | :---: | ---: |` 的 Markdown 文本，断言该行未被包含在 `rows` 数据集内。
5. **测试用例 5：Office 临时文件屏蔽**
   - 在 assets 模拟创建 `~$报价.xlsx`，运行 `build_manifest`，断言该文件不在 `files` 清单中。
6. **测试用例 6：超大证据安全序列化**
   - 模拟构造 200 条产品的超大源输入，验证提取节点组装的 prompt payload 始终可被 `json.loads` 成功解析，无截断语法破损。
