import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
