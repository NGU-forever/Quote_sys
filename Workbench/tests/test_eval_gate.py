"""评测回归门禁：离线 scripted 模式下 19 个 golden case 必须全绿。

等价于 CI 里执行 ``python -m eval.run_eval --provider scripted --enforce``。
真实模型的抽取质量评测（--provider live）会消耗真实额度，不放进自动化测试。
"""
import io
import unittest
from contextlib import redirect_stdout

from tests import db_support  # noqa: F401  # 统一测试库连接，必须在 app.* 之前导入

from eval import run_eval


class EvalGateTests(unittest.TestCase):
    def test_scripted_eval_passes_all_cases(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_eval.main(["--provider", "scripted", "--enforce"])
        output = buffer.getvalue()
        self.assertEqual(exit_code, 0, output)
        self.assertIn("case 通过率          : 1.000", output)


if __name__ == "__main__":
    unittest.main()
