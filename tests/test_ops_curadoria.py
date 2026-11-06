"""Testes de integração entre o ciclo operacional (ops.py) e a curadoria autônoma."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from radar import ops, ops_config
from radar.document_store import (
    connect_documents,
    migrate_document_schema,
    register_document,
    SCHEMA_VERSION,
)


class OpsCuradoriaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        self.db_path = str(self.root / "data" / "radar.sqlite3")
        migrate_document_schema(self.db_path)
        self.cfg = ops_config.load_config()
        self.cfg.update({
            "project_root": str(self.root),
            "python": str(Path(__import__("sys").executable)),
            "db_path": self.db_path,
            "logs_dir": str(self.root / "logs"),
        })

    def _dummy_source(self):
        return {
            "source_id": "dummy",
            "source_url": "https://example.com/dummy",
            "discover": lambda *args, **kwargs: [],
        }

    def test_run_cycle_executes_autonomous_curation(self):
        """Verifica se o run_cycle dispara a curadoria autônoma e registra em result['curation']."""
        result = ops.run_cycle(self.cfg, sources=[self._dummy_source()])
        self.assertIn("curation", result)
        curation = result["curation"]
        self.assertIsInstance(curation, dict)
        self.assertEqual(curation.get("status"), "sucesso")
        self.assertIn("total_decisoes", curation)
        self.assertIn("totais_banco", curation)
        self.assertIn("revisoes_campo", curation["totais_banco"])

    def test_select_sources_recognizes_ibfc(self):
        """Verifica se _select_sources reconhece e seleciona a fonte IBFC quando habilitada."""
        cfg = dict(self.cfg)
        cfg["sources"] = {
            "ibfc": {"enabled": True, "min_interval_hours": 6}
        }
        selected = ops._select_sources(cfg)
        self.assertTrue(any(s.get("id") == "ibfc" or s.get("source_id") == "ibfc" for s in selected))
    def test_select_sources_recognizes_cebraspe(self):
        """Verifica se _select_sources reconhece e seleciona a fonte Cebraspe quando habilitada."""
        cfg = dict(self.cfg)
        cfg["sources"] = {
            "cebraspe": {"enabled": True, "min_interval_hours": 6}
        }
        selected = ops._select_sources(cfg)
        self.assertTrue(any(s.get("id") == "cebraspe" or s.get("source_id") == "cebraspe" for s in selected))
