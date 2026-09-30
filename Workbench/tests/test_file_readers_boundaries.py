"""文件解析模块（Excel / Word / Text）边界与鲁棒性加固专项测试。"""
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from openpyxl import Workbook

from app.agent.readers.common import is_ignored_file
from app.agent.readers.excel_reader import _parse_range, read_excel
from app.agent.readers.manifest import build_manifest
from app.agent.readers.text_reader import read_csv, read_markdown
from app.agent.readers.word_reader import read_word


class FileReadersBoundaryTests(unittest.TestCase):
    def test_01_office_lock_and_hidden_files_are_ignored(self):
        self.assertTrue(is_ignored_file("~$报价表.xlsx"))
        self.assertTrue(is_ignored_file(".DS_Store"))
        self.assertTrue(is_ignored_file("._test.docx"))
        self.assertFalse(is_ignored_file("产品最低价格.xlsx"))

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "normal.xlsx").write_bytes(b"dummy")
            (root / "~$normal.xlsx").write_bytes(b"dummy")
            (root / ".hidden.txt").write_bytes(b"dummy")
            manifest = build_manifest(root)
            file_names = [f["name"] for f in manifest["files"]]
            self.assertIn("normal.xlsx", file_names)
            self.assertNotIn("~$normal.xlsx", file_names)
            self.assertNotIn(".hidden.txt", file_names)


    def test_02_excel_range_and_missing_dimension_probed(self):
        # 1. 测试反向 range 与单单元格解析
        # 正常
        r1 = _parse_range("A1:D10", 20, 10)
        self.assertEqual(r1, (1, 1, 10, 4))
        # 倒置
        r2 = _parse_range("D10:A1", 20, 10)
        self.assertEqual(r2, (1, 1, 10, 4))
        # 带工作表前缀
        r3 = _parse_range("Sheet1!B2:E8", 20, 10)
        self.assertEqual(r3, (2, 2, 8, 5))
        # 单单元格
        r4 = _parse_range("C3", 20, 10)
        self.assertEqual(r4, (3, 3, 3, 3))

        # 2. 测试 missing dimension 或 max_row 为 0/None 的自适应流式探测
        with tempfile.TemporaryDirectory() as tmp:
            wb_path = Path(tmp) / "no_dim.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.title = "SKU表"
            ws.append(["sku_id", "name", "min_price"])
            ws.append(["P901", "测试机", 1200])
            ws.append(["#N/A", "错误值测试", None])
            wb.save(wb_path)

            # 读取该 sheet
            res = read_excel(wb_path, sheet="SKU表", max_rows=10)
            self.assertTrue(res["ok"])
            self.assertEqual(res["headers"], ["sku_id", "name", "min_price"])
            # #N/A 应被清洗为 None
            self.assertIsNone(res["sample_rows"][1][0])
            self.assertEqual(res["row_count"], 2)

    def test_03_word_merged_cells_and_null_style_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_path = Path(tmp) / "merged_and_null_style.docx"
            doc = Document()
            # 1. 包含表格
            table = doc.add_table(rows=2, cols=3)
            table.cell(0, 0).merge(table.cell(0, 1))
            table.cell(0, 0).text = "合并表头"
            table.cell(0, 2).text = "价格"
            table.cell(1, 0).text = "P001"
            table.cell(1, 1).text = "超声仪"
            table.cell(1, 2).text = "3500"

            # 2. 包含段落
            p1 = doc.add_paragraph("正常段落测试")
            p2 = doc.add_paragraph("无样式段落测试")

            doc.save(doc_path)

            # 模拟段落 p.style 为 None
            from unittest.mock import PropertyMock, patch

            with patch("docx.text.paragraph.Paragraph.style", new_callable=PropertyMock) as mock_style:
                mock_style.return_value = None
                with patch("docx.table.Table.columns", new_callable=PropertyMock) as mock_cols:
                    mock_cols.side_effect = IndexError("list index out of range")
                    res = read_word(doc_path, headings_only=False, max_paragraphs=10)

            self.assertTrue(res["ok"])
            self.assertEqual(len(res["tables"]), 1)
            tbl_info = res["tables"][0]
            # 即使 table.columns 抛出 IndexError，防御逻辑仍能通过 rows 获取列数
            self.assertGreaterEqual(tbl_info["columns"], 2)
            self.assertEqual(tbl_info["rows"], 2)
            self.assertEqual(len(res["paragraph_preview"]), 2)
            self.assertEqual(res["paragraph_preview"][0]["style"], "Normal")

    def test_04_text_and_csv_encoding_and_markdown_alignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # 1. GBK 编码中文 CSV 测试
            csv_path = tmp_path / "gbk_data.csv"
            chinese_text = "编号,产品名称,底价,单位\nP101,超声波治疗仪,3200,台\nC101,电极贴片,15,盒\n"
            csv_path.write_bytes(chinese_text.encode("gbk"))

            csv_res = read_csv(csv_path, max_rows=10)
            self.assertTrue(csv_res["ok"])
            self.assertEqual(csv_res["headers"], ["编号", "产品名称", "底价", "单位"])
            self.assertEqual(csv_res["sample_rows"][0], ["P101", "超声波治疗仪", "3200", "台"])
            self.assertEqual(csv_res["sample_rows"][1], ["C101", "电极贴片", "15", "盒"])
            # 确认没有 \ufffd 乱码
            self.assertNotIn("\ufffd", "".join(csv_res["headers"]))
            self.assertNotIn("\ufffd", "".join(csv_res["sample_rows"][0]))

            # 2. Markdown 带对齐符（如 :---, :---:, ---:）的分隔行过滤
            md_path = tmp_path / "alignment.md"
            md_content = (
                "# 产品价格表\n\n"
                "| sku_id | 产品名 | 底价 |\n"
                "| :--- | :---: | ---: |\n"
                "| P001 | 便携治疗仪 | 2000 |\n"
                "| C001 | 专用凝胶 | 50 |\n"
            )
            md_path.write_text(md_content, encoding="utf-8")

            md_res = read_markdown(md_path, max_rows=10)
            self.assertTrue(md_res["ok"])
            self.assertEqual(len(md_res["tables"]), 1)
            tbl = md_res["tables"][0]
            self.assertEqual(tbl["headers"], ["sku_id", "产品名", "底价"])
            # 只有 2 行真实业务数据，对齐行不能进入 rows
            self.assertEqual(len(tbl["rows"]), 2)
            self.assertEqual(tbl["rows"][0], ["P001", "便携治疗仪", "2000"])
            self.assertEqual(tbl["rows"][1], ["C001", "专用凝胶", "50"])

    def test_05_large_evidence_json_serializable(self):
        from app.agent.graph.nodes.extractors import _read_source
        from app.agent.schemas import ProductCandidate

        # 模拟生成一个包含 150 条行数据的超大 csv
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "large_products.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["sku_id", "category", "name", "min_price", "unit"])
                for i in range(150):
                    writer.writerow([f"SKU_{i:04d}", "device", f"测试设备型号_{i}", 1000 + i, "台"])

            with patch.object(Path, "resolve", return_value=csv_path):
                source = {"file": "large_products.csv", "type": "text"}
                with patch("app.agent.graph.nodes.extractors.safe_file_path", return_value=csv_path):
                    evidence = [_read_source(source)]
                    dumped = json.dumps({"sources": evidence}, ensure_ascii=False, default=str)
                    # 必须能够无误被 json.loads 解析，绝不发生中途截断语法错误
                    loaded = json.loads(dumped)
                    self.assertIn("sources", loaded)
                    self.assertEqual(len(loaded["sources"][0]["content"]["sample_rows"]), 100)
