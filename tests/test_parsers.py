import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.parser import GuidelineParser
from scraper.supplementary_parser import SupplementaryParser


FIXTURES = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_guideline_parser_basic_fields(self):
        html = (FIXTURES / "guideline_page.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")
        parser = GuidelineParser(soup, "https://example.test/guidelines/test-offence-a/")
        guideline = parser.parse()

        self.assertEqual(guideline.offence_name, "Test offence A")
        self.assertTrue(guideline.legislation)
        self.assertTrue(guideline.effective_from)
        self.assertGreaterEqual(len(guideline.culpability_levels), 2)
        self.assertGreaterEqual(len(guideline.harm_levels), 2)
        self.assertGreaterEqual(len(guideline.sentencing_ranges), 1)
        self.assertIn("Previous convictions", guideline.aggravating_factors)
        self.assertIn("No previous convictions", guideline.mitigating_factors)
        self.assertGreaterEqual(len(guideline.additional_steps), 1)

    def test_supplementary_parser_sections(self):
        html = (FIXTURES / "supplementary_page.html").read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")
        parser = SupplementaryParser(
            soup, "https://example.test/supplementary-information/ancillary-orders/"
        )
        page = parser.parse(page_type="supplementary", source_tab="Supplementary information")

        self.assertEqual(page.page_title, "Ancillary orders")
        self.assertEqual(page.page_type, "supplementary")
        self.assertGreaterEqual(len(page.sections), 2)
        headings = [s.heading for s in page.sections]
        self.assertIn("Eligibility", headings)
        self.assertIn("Procedure", headings)

        eligibility = next(s for s in page.sections if s.heading == "Eligibility")
        self.assertIn("Point one", eligibility.bullets[0])

        procedure = next(s for s in page.sections if s.heading == "Procedure")
        self.assertTrue(procedure.tables)


if __name__ == "__main__":
    unittest.main()
