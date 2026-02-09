import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.crawler import SentencingCrawler
from scraper.index_tabs import extract_tab_links


FIXTURES = Path(__file__).parent / "fixtures"


class DummyResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200


class CrawlerTests(unittest.TestCase):
    def test_extract_guideline_data_json(self):
        html = (FIXTURES / "magistrates_index.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")
        crawler = SentencingCrawler()

        data = crawler._extract_guideline_data_json(soup)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["name"], "Test offence A")
        self.assertEqual(data[1]["url"], "/guidelines/test-offence-b/")

    def test_extract_tab_links(self):
        html = (FIXTURES / "magistrates_index.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")

        links = extract_tab_links(
            soup, "https://example.test/guidelines/magistrates/", "magistrates"
        )
        names = [l.name for l in links]
        tabs = {l.name: l.source_tab for l in links}

        self.assertIn("Overarching A", names)
        self.assertIn("Overarching B", names)
        self.assertIn("Ancillary orders", names)
        self.assertIn("Approach to fines", names)
        self.assertEqual(tabs["Overarching A"], "Overarching guidelines")
        self.assertEqual(tabs["Ancillary orders"], "Supplementary information")

    def test_discover_offences_from_index_uses_fixture(self):
        html = (FIXTURES / "magistrates_index.html").read_text(encoding="utf-8")
        crawler = SentencingCrawler()
        crawler._polite_get = lambda url: DummyResponse(html)  # stub network

        links = crawler.discover_offences_from_index(
            "https://example.test/guidelines/magistrates/", "magistrates"
        )

        # 2 offences + 2 overarching + 2 supplementary = 6
        self.assertEqual(len(links), 6)
        self.assertTrue(any(l.source_tab == "Supplementary information" for l in links))
        self.assertTrue(any(l.source_tab == "Overarching guidelines" for l in links))


if __name__ == "__main__":
    unittest.main()
