import json
import unittest

from anhui_admission import build_item, classify_material, collect_anhui_admission
from campus_crawler import export_results, extract_date, normalize_url, root_domain, score_text


class CampusCrawlerTests(unittest.TestCase):
    def test_normalize_url_adds_scheme(self):
        self.assertEqual(normalize_url("www.example.edu.cn"), "https://www.example.edu.cn/")

    def test_root_domain_for_edu_cn(self):
        self.assertEqual(root_domain("yz.example.edu.cn"), "example.edu.cn")

    def test_extract_chinese_date(self):
        self.assertEqual(extract_date("发布时间：2026年6月24日"), "2026-06-24")

    def test_admission_scoring(self):
        score, reason = score_text("admission", "/2026/硕士招生简章.html", "研究生招生")
        self.assertGreaterEqual(score, 5)
        self.assertIn("招生", reason)

    def test_json_export_preserves_chinese(self):
        content, content_type, extension = export_results([{"title": "招生简章"}], "json")
        self.assertEqual(extension, "json")
        self.assertEqual(content_type, "application/json")
        self.assertEqual(json.loads(content)[0]["title"], "招生简章")

    def test_classify_anhui_plan(self):
        material_type, score, reason = classify_material(
            "/2026/plan.html", "2026年在皖招生计划"
        )
        self.assertEqual(material_type, "plan")
        self.assertGreaterEqual(score, 12)
        self.assertIn("在皖招生计划", reason)

    def test_admission_item_has_source_fields(self):
        item = build_item(
            school_name="示例大学",
            year=2026,
            title="示例大学2026年本科招生章程",
            url="https://example.edu.cn/2026/charter.html",
            source_page="https://example.edu.cn/",
            source_authority="示例大学官方招生网站",
            material_type="charter",
            score=10,
            reason="测试",
        )
        self.assertEqual(item["province"], "安徽")
        self.assertEqual(item["year"], "2026")
        self.assertEqual(item["query_year"], "2026")
        self.assertEqual(item["material_label"], "招生章程")

    def test_anhui_admission_requires_school_name(self):
        with self.assertRaisesRegex(ValueError, "院校名称"):
            collect_anhui_admission("", "", 2026, 1)


if __name__ == "__main__":
    unittest.main()
