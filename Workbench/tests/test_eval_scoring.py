"""评测打分函数单测（纯逻辑，不依赖数据库）。"""
import unittest

from eval import scoring


class PrfTests(unittest.TestCase):
    def test_perfect_match(self):
        result = scoring.prf({"a", "b"}, {"a", "b"})
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (2, 0, 0))
        self.assertEqual(result["f1"], 1.0)

    def test_partial_match(self):
        result = scoring.prf({"a", "b"}, {"a", "c"})
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (1, 1, 1))
        self.assertAlmostEqual(result["precision"], 0.5)
        self.assertAlmostEqual(result["recall"], 0.5)
        self.assertAlmostEqual(result["f1"], 0.5)

    def test_both_empty_is_perfect(self):
        result = scoring.prf(set(), set())
        self.assertEqual(result["f1"], 1.0)

    def test_all_missing(self):
        result = scoring.prf({"a"}, set())
        self.assertEqual(result["recall"], 0.0)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["f1"], 0.0)

    def test_all_extra(self):
        result = scoring.prf(set(), {"x"})
        self.assertEqual(result["precision"], 0.0)
        self.assertEqual(result["fn"], 0)
        self.assertEqual(result["f1"], 0.0)


class FieldAccuracyTests(unittest.TestCase):
    def test_numeric_tolerance_and_mismatch_report(self):
        expected = [{"sku_id": "P1", "name": "甲", "min_price": 10, "unit": "台"}]
        actual = [{"sku_id": "P1", "name": "乙", "min_price": 10.0, "unit": None}]
        result = scoring.field_accuracy(expected, actual, lambda item: item["sku_id"], ("name", "min_price", "unit"))
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["correct"], 1)  # min_price 10 == 10.0
        self.assertAlmostEqual(result["accuracy"], 1 / 3, places=4)
        self.assertEqual(len(result["mismatches"]), 2)

    def test_list_fields_compared_elementwise(self):
        expected = [{"id": "A", "sku_ids": ["P1", "P2"]}]
        actual = [{"id": "A", "sku_ids": ["P2", "P1"]}]
        result = scoring.field_accuracy(expected, actual, lambda item: item["id"], ("sku_ids",))
        self.assertEqual(result["correct"], 0)

    def test_unmatched_entities_are_not_counted(self):
        result = scoring.field_accuracy(
            [{"id": "A", "name": "甲"}], [], lambda item: item["id"], ("name",)
        )
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["accuracy"], 1.0)


class AggregateTests(unittest.TestCase):
    def _score(self, key, passed, tp=1, fp=0, fn=0, corrections=0):
        empty = {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
        return {
            "key": key,
            "passed": passed,
            "products": {**empty, "tp": tp, "fp": fp, "fn": fn},
            "packages": dict(empty),
            "bindings": dict(empty),
            "product_fields": {"total": 2, "correct": 2},
            "package_fields": {"total": 1, "correct": 1},
            "corrections": corrections,
            "llm": {"calls": 2, "total_tokens": 100, "latency_ms": 50, "cost": 0.01},
            "error": None,
        }

    def test_micro_average_and_rates(self):
        summary = scoring.aggregate(
            [self._score("a", True), self._score("b", False, tp=1, fp=1, fn=1, corrections=2)]
        )
        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["passed"], 1)
        self.assertAlmostEqual(summary["pass_rate"], 0.5)
        self.assertEqual(summary["micro"]["products"]["tp"], 2)
        self.assertEqual(summary["micro"]["products"]["fp"], 1)
        self.assertEqual(summary["failed_cases"], ["b"])
        self.assertEqual(summary["self_heal_runs"], 1)
        self.assertEqual(summary["llm_calls"], 4)
        self.assertAlmostEqual(summary["llm_cost"], 0.02)
        self.assertAlmostEqual(summary["product_field_accuracy"], 1.0)

    def test_hallucination_rate(self):
        summary = scoring.aggregate([self._score("a", False, tp=3, fp=1)])
        self.assertAlmostEqual(summary["hallucination_rate"], 0.25)

    def test_empty_input(self):
        summary = scoring.aggregate([])
        self.assertEqual(summary["cases"], 0)
        self.assertEqual(summary["pass_rate"], 0.0)
        self.assertEqual(summary["hallucination_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
