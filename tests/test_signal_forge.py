import tempfile
import unittest
from pathlib import Path
from signal_forge.brief import markdown
from signal_forge.pipeline import run_collect, watch_once
from signal_forge.scoring import Analyst
from signal_forge.sources import dump_sources, load_sources, save_source, sync_registry
from signal_forge.store import Store
from unittest.mock import patch

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

    def test_source_file_roundtrip_and_sync(self):
        seed = Path(__file__).resolve().parents[1] / "config" / "sources.seed.yaml"
        loaded = load_sources(seed)
        path = Path(self.dir.name) / "sources.yaml"
        dump_sources(path, loaded)
        again = load_sources(path)
        fields = lambda rows: [(row["name"], row["url"], row["topics"], row["scan_method"]) for row in rows]
        self.assertEqual(fields(loaded), fields(again))
        stats = sync_registry(self.store, path)
        self.assertEqual(stats["active"], len(loaded))
        self.assertEqual(len(self.store.sources()), len(loaded))
        dump_sources(path, [loaded[0] | {"active": False}, loaded[1]])
        stats = sync_registry(self.store, path)
        self.assertEqual(stats["active"], 1)
        self.assertEqual([row["name"] for row in self.store.sources()], [loaded[1]["name"]])

    def test_save_source_appends_without_dropping_the_list(self):
        path = Path(self.dir.name) / "sources.yaml"
        dump_sources(path, [{"name": "Kept", "url": "https://example.test/kept", "authority": "primary", "topics": ["policy"], "scan_method": "rss"}])
        created = save_source(path, {"name": "Added, feed", "url": "https://example.test/added", "topics": ["market"], "scan_method": "rss"})
        self.assertTrue(created)
        names = [row["name"] for row in load_sources(path)]
        self.assertEqual(names, ["Kept", "Added, feed"])
        self.assertFalse(save_source(path, {"name": "Added, feed", "url": "https://example.test/added?utm_source=x", "scan_method": "rss"}))
        self.assertEqual(len(load_sources(path)), 2)

    def test_watch_once_skips_pages_and_stores_a_feed(self):
        path = Path(self.dir.name) / "sources.yaml"
        dump_sources(path, [
            {"name": "Page", "url": "https://example.test/page", "scan_method": "news_page", "topics": []},
            {"name": "Feed", "url": "https://example.test/feed", "scan_method": "rss", "topics": ["policy"]},
        ])
        item = {"title": "Biomethane tender", "url": "https://example.test/item", "content": "Poland biomethane tender", "topics": ["policy"]}
        with patch("signal_forge.pipeline.collect_feed", return_value=[item]) as fetch:
            result = watch_once(self.store, path)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(self.store.last_log("watch")["status"], "ok")
        self.assertEqual(len(self.store.items()), 1)

if __name__ == "__main__": unittest.main()
