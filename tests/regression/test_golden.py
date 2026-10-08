"""Full primary captures and golden legal/form/table invariants."""
import json
from pathlib import Path
import tempfile
import unittest
from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, walk_content
from vietnam_legal_rag.ingestion.validation.forms import FORM_NODE_PROPERTIES
from tests.support import ROOT, nodes


class CapturedFixtureListRegressionTests(unittest.TestCase):
    def test_all_captures_regenerated_from_raw_and_current_fixture_invariants(self):
        root = ROOT
        primary = json.loads((root / "tests/fixtures/vbpl_primary_captures.json").read_text())["document_ids"]
        captures = sorted(p for p in (root / "data/raw/vbpl").rglob("manifest.json")
                          if json.loads(p.read_text())["document_id"] in primary)
        self.assertEqual({json.loads(p.read_text())["document_id"] for p in captures}, set(primary))
        self.assertEqual(len(captures), 5, "Run with all five representative RAW captures")
        with tempfile.TemporaryDirectory() as temporary:
            for capture in captures:
                with self.subTest(capture=capture.parent.name):
                    destination = Path(temporary) / capture.parent.name
                    manifest = extract_document(capture.parent, destination)
                    self.assertTrue(all(manifest["quality"][k] for k in ("meaningful_text_preserved", "schema_valid", "deterministic")))
                    self.assertEqual(manifest["issue_summary"]["error"], 0)
                    self.assertEqual(manifest["issue_summary"]["fatal"], 0)
                    current = json.loads((destination / "content.json").read_text())
                    prior_folder = root / "data/extracted/vbpl" / capture.parent.name
                    prior = json.loads((prior_folder / "content.json").read_text())
                    self.assertEqual(current["hierarchy_validation"]["legal_hierarchy"], prior["hierarchy_validation"]["legal_hierarchy"])
                    self.assertEqual(current["hierarchy_validation"]["annex_hierarchy"], prior["hierarchy_validation"]["annex_hierarchy"])
                    physical = lambda r: [{k: v for k, v in c.items() if k != "content"} for n in nodes(r, "table") for c in n["cells"]]
                    self.assertEqual(physical(current), physical(prior))
                    for name in ("properties.json", "history.json", "relations.json"):
                        self.assertEqual((destination / name).read_bytes(), (prior_folder / name).read_bytes())
                    for artifact in destination.glob("*.json"):
                        schema_validator().validate(json.loads(artifact.read_text()))
                    fields = nodes(current, "form_field") + nodes(current, "form_subfield")
                    self.assertTrue(all(all(k in n for k in FORM_NODE_PROPERTIES) for n in fields))
                    self.assertTrue(current["hierarchy_validation"]["order_valid"])
                    self.assertEqual(current["form_validation"]["unexplained_structured_paragraphs"], 0)
                    if capture.parent.name == "a9bea550-bbe3-11f1-a338-51a5cc429fc7":
                        self.assertEqual(current["hierarchy_validation"]["legal_hierarchy"],
                                         {"parts": 0, "chapters": 4, "sections": 0, "subsections": 0, "articles": 15, "clauses": 36, "points": 5})
                        h = current["hierarchy_validation"]
                        self.assertEqual(h["annex_hierarchy"], {"annexes": 4, "numbered_sections": 5, "numbered_items": 26, "max_depth": 2})
                        self.assertTrue(h["semantic_complete"])
                        self.assertTrue(manifest["quality"]["semantic_complete"])
                        for key, value in {"forms": 16, "fields": 80, "subfields": 14, "footnotes": 52, "placeholder_references": 65,
                                           "suspicious_value_text": 0, "semantic_empty_string_fields": 0, "unexplained_form_label_paragraphs": 0,
                                           "form_nodes_missing_field_kind": 0, "form_nodes_missing_field_evidence": 0}.items():
                            self.assertEqual(current["form_validation"][key], value, key)
                        self.assertFalse(any(manifest["issue_summary"][s] for s in ("warning", "error", "fatal")))
                        annex = next(n for n in nodes(current, "annex") if n["number"] == "III")
                        item = next(n for n in walk_content([annex]) if n["type"] == "numbered_item" and n["number"] == "1.6")
                        listing = item["children"][0]
                        self.assertEqual(listing["type"], "list")
                        self.assertEqual(len(listing["children"]), 2)
                        sublists = [next(n for n in parent["children"] if n["type"] == "list") for parent in listing["children"]]
                        self.assertEqual([len(n["children"]) for n in sublists], [5, 4])
                        self.assertEqual([len(n["children"]) for n in sublists[0]["children"]], [0, 0, 5, 2, 0])
                        self.assertEqual(listing["children"][1]["children"][0]["type"], "paragraph")
                        form = next(n for n in walk_content([nodes(current, "annex")[0]]) if n["type"] == "form" and n["number"] == "05")
                        plus = [n for n in form["children"] if n["type"] == "list" and n["style"] == "plus"]
                        self.assertEqual(len(plus), 1)
                        self.assertEqual(len(plus[0]["children"]), 2)


if __name__ == "__main__":
    unittest.main()
