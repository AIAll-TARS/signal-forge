import tempfile
import unittest
from pathlib import Path
from signal_forge.brief import markdown
from signal_forge.scoring import Analyst
from signal_forge.sources import load_sources
from signal_forge.store import Store

class SignalForgeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name) / "test.db"); self.store.init()
    def tearDown(self): self.store.close(); self.dir.cleanup()

    def test_import_minimal_yaml(self):
        path = Path(self.dir.name) / "sources.yaml"
        path.write_text("sources:\n  - name: Feed\n    url: https://example.test/rss\n    authority: primary\n    topics: [policy-regulation, market-economics]\n    scan_method: rss\n")
        sources = load_sources(path)
        self.assertEqual(sources[0]["topics"], ["policy-regulation", "market-economics"])
        _, created = self.store.add_source(sources[0]); self.assertTrue(created)
        _, created = self.store.add_source(sources[0]); self.assertFalse(created)

    def test_dedupe_canonical_url_and_content(self):
        first, created = self.store.add_item({"title":"A", "url":"https://example.test/a?utm_source=x#part", "content":"same article"})
        second, created2 = self.store.add_item({"title":"B", "url":"https://example.test/a", "content":"different"})
        third, created3 = self.store.add_item({"title":"C", "url":"https://example.test/c", "content":"same  article"})
        self.assertTrue(created); self.assertFalse(created2); self.assertFalse(created3)
        self.assertEqual(first, second); self.assertEqual(first, third)

    def test_scoring_and_briefing(self):
        sid, _ = self.store.add_source({"name":"Official", "url":"https://example.test/feed", "authority":"primary", "scan_method":"rss", "topics":[]})
        iid, _ = self.store.add_item({"source_id":sid, "title":"Poland biomethane support regulation", "url":"https://example.test/item", "content":"A new Polish biomethane subsidy regulation affects gas grid injection and project financing."})
        item = dict(self.store.unanalysed()[0]); result = Analyst().analyze(item)
        self.assertGreaterEqual(result["score"], 75); self.assertEqual(result["priority"], "critical")
        self.store.save_analysis(iid, result)
        output = markdown(self.store.items())
        self.assertIn("Poland biomethane support regulation", output)
        self.assertIn("Why it matters", output)

if __name__ == "__main__": unittest.main()
