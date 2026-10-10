"""Hash bruto vs. hash de comparação: reduz versões artificiais sem esconder mudanças."""

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_store import (
    comparison_fingerprint,
    get_competition_details,
    migrate_document_schema,
    record_version,
    register_document,
)

_TELEMETRY = (
    '<script>window.NREUM||(NREUM={{}});NREUM.info={{"beacon":"bam.nr-data.net",'
    '"applicationTime":{time},"queueTime":0,"agent":""}}</script>'
)


def _html(app_time, body):
    return ("<html><head>" + _TELEMETRY.format(time=app_time) + "</head><body>"
            + body + "</body></html>").encode("utf-8")


class ComparisonHashTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
            conn.commit()
        url = "https://guajaramirim.ro.gov.br/edital.html"
        self.url = url
        self.doc = register_document(self.db, dict(observation_id="o", kind="edital",
            official_url=url, title="Edital", discovery_url=url, discovery_method="manual",
            discovered_at="2026-10-10T00:00:00+00:00"))

    def _record(self, body, app_time, at):
        return record_version(self.db, self.doc, _html(app_time, body), dict(
            fetched_at=at, fetched_url=self.url, content_type="text/html"))

    def test_telemetry_variation_keeps_comparison_hash_but_changes_raw_hash(self):
        a, b = _html(112, "<p>Edital</p>"), _html(143, "<p>Edital</p>")
        self.assertNotEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())
        self.assertEqual(comparison_fingerprint(a, "text/html"), comparison_fingerprint(b, "text/html"))

    def test_substantive_changes_alter_comparison_hash(self):
        base = comparison_fingerprint(_html(1, "<p>107 vagas</p>"), "text/html")
        quota = comparison_fingerprint(_html(1, "<p>108 vagas</p>"), "text/html")
        period = comparison_fingerprint(_html(1, "<p>Inscrições 10/07/2026</p>"), "text/html")
        rules = comparison_fingerprint(_html(1, "<p>cota indígena 3%</p>"), "text/html")
        self.assertNotEqual(base, quota)
        self.assertNotEqual(base, period)
        self.assertNotEqual(base, rules)

    def test_non_html_comparison_hash_equals_raw_hash(self):
        pdf = b"%PDF-1.6 fake"
        self.assertEqual(comparison_fingerprint(pdf, "application/pdf"),
                         hashlib.sha256(pdf).hexdigest())

    def test_same_content_with_new_telemetry_does_not_create_new_version(self):
        first = self._record("<p>107 vagas</p>", 112, "2026-10-10T01:00:00+00:00")
        again = self._record("<p>107 vagas</p>", 143, "2026-10-10T02:00:00+00:00")
        self.assertEqual(first, again)
        self.assertEqual(len(get_competition_details(self.db, "c")["documents"][0]["versions"]), 1)

    def test_reprocessing_identical_bytes_is_idempotent(self):
        first = self._record("<p>107 vagas</p>", 112, "2026-10-10T01:00:00+00:00")
        again = self._record("<p>107 vagas</p>", 112, "2026-10-10T02:00:00+00:00")
        self.assertEqual(first, again)
        self.assertEqual(len(get_competition_details(self.db, "c")["documents"][0]["versions"]), 1)

    def test_substantively_different_document_creates_new_linked_version(self):
        first = self._record("<p>107 vagas</p>", 112, "2026-10-10T01:00:00+00:00")
        second = self._record("<p>108 vagas</p>", 112, "2026-10-10T02:00:00+00:00")
        self.assertNotEqual(first, second)
        with closing(sqlite3.connect(self.db)) as conn:
            previous = conn.execute(
                "SELECT previous_version_id FROM versoes_documento WHERE id=?", (second,)).fetchone()[0]
        self.assertEqual(previous, first)

    def test_evidence_points_to_stored_raw_bytes(self):
        first = self._record("<p>107 vagas</p>", 112, "2026-10-10T01:00:00+00:00")
        with closing(sqlite3.connect(self.db)) as conn:
            sha, comparison = conn.execute(
                "SELECT sha256,comparison_sha256 FROM versoes_documento WHERE id=?", (first,)).fetchone()
        stored = _html(112, "<p>107 vagas</p>")
        self.assertEqual(sha, hashlib.sha256(stored).hexdigest())
        self.assertEqual(comparison, comparison_fingerprint(stored, "text/html"))
