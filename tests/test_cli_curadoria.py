"""Testes do subcomando da CLI curadoria-autonoma."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from radar.__main__ import main
from tests.test_autonomous_curator import make_test_db


class TestCliCuradoria(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_test_db()
        self.addCleanup(self.tmp.cleanup)

    def test_cli_curadoria_dry_run(self):
        f = io.StringIO()
        with redirect_stdout(f):
            main(["curadoria-autonoma", "--db", self.db, "--dry-run", "--limit", "10"])
        out = json.loads(f.getvalue())
        self.assertEqual(out["status"], "sucesso")
        self.assertTrue(out["dry_run"])
        self.assertIn("total_decisoes", out)


if __name__ == "__main__":
    unittest.main()
