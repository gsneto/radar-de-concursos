"""Central de triagem e backlog de alertas (agrupamento, urgência, incremental)."""

import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import ops
from radar.document_store import (connect_documents, ensure_observation, migrate_document_schema,
                                  register_document)


def _now():
    return datetime.now(timezone.utc).isoformat()


class TriageBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)

    def _alert(self, *, kind, severity, contest=None, title, detail=None, dedup=None, event_at=None):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            ops._insert_alert(conn, kind=kind, severity=severity, contest_id=contest,
                              dedup_key=dedup or f"{kind}:{contest}:{title}", title=title,
                              detail=detail, event_at=event_at or _now())
            conn.commit()

    def _contest(self, competition_id, title):
        obs = ensure_observation(self.db, f"https://exemplo.test/{competition_id}", competition_id)
        register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url=f"https://exemplo.test/{competition_id}/e.pdf",
            title=title, discovery_url=f"https://exemplo.test/{competition_id}",
            discovery_method="automatico", discovered_at=_now()))
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                (obs,)).fetchone()[0]


class GroupingTest(TriageBase):
    def test_groups_by_contest(self):
        c1 = self._contest("pci-1", "Concurso A")
        self._alert(kind="novo_candidato", severity="info", contest=c1, title="Novo A")
        self._alert(kind="retificacao", severity="atencao", contest=c1, title="Retif A")
        self._alert(kind="prazo_isencao", severity="atencao", contest=c1, title="Isenção A")
        report = ops.triage(self.db)
        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["groups"][0]["contest_id"], c1)
        self.assertEqual(report["groups"][0]["alert_count"], 3)

    def test_different_contests_with_similar_titles_stay_separate(self):
        c1 = self._contest("pci-1", "Prefeitura de Boituva")
        c2 = self._contest("pci-2", "Prefeitura de Boituva")
        self._alert(kind="novo_candidato", severity="info", contest=c1, title="A")
        self._alert(kind="novo_candidato", severity="info", contest=c2, title="A")
        report = ops.triage(self.db)
        self.assertEqual(len(report["groups"]), 2)  # nunca une por título

    def test_alerts_without_contest_group_together(self):
        self._alert(kind="falha_fonte", severity="atencao", contest=None, title="Fonte X")
        report = ops.triage(self.db)
        self.assertEqual(report["groups"][0]["contest_id"], None)


class UrgencyTest(TriageBase):
    def _deadline(self, contest, days):
        from radar.document_store import record_analysis, record_version
        obs = ensure_observation(self.db, f"https://exemplo.test/{contest}", contest)
        with closing(connect_documents(self.db)) as conn:
            contest_id = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                      (obs,)).fetchone()[0]
        did = register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url=f"https://exemplo.test/{contest}/e.pdf",
            title="Edital", discovery_url=f"https://exemplo.test/{contest}",
            discovery_method="automatico", discovered_at=_now()))
        version = record_version(self.db, did, b"%PDF-1.4 x", dict(
            fetched_at=_now(), fetched_url=f"https://exemplo.test/{contest}/e.pdf",
            content_type="application/pdf"))
        deadline = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
        block = dict(page_number=1, locator="p", start_offset=0, end_offset=1, text="x")
        record_analysis(self.db, version, [block], [dict(
            contest_id=contest_id, role_id=None, field_name="exemption_end",
            value_json=f'"{deadline}"', value_type="string", extraction_method="t",
            ambiguity_reason="x", evidence=dict(block_index=0, quote="x", start_offset=0, end_offset=1))])
        return contest_id

    def test_near_deadline_is_proximos(self):
        contest = self._deadline("pci-9", 3)
        self._alert(kind="prazo_isencao", severity="atencao", contest=contest, title="Isenção proxima")
        group = ops.triage(self.db)["groups"][0]
        self.assertEqual(group["urgency"], "proximos")
        self.assertIsNotNone(group["exemption_end"])

    def test_expired_deadline_is_hoje_bucket(self):
        contest = self._deadline("pci-9", -1)
        self._alert(kind="prazo_isencao", severity="critico", contest=contest, title="Isenção expirado")
        self.assertEqual(ops.triage(self.db)["groups"][0]["urgency"], "hoje")

    def test_unknown_deadline_is_not_treated_as_expired(self):
        contest = self._contest("pci-8", "Sem prazo")
        self._alert(kind="prazo_isencao", severity="atencao", contest=contest, title="Isenção?")
        group = ops.triage(self.db)["groups"][0]
        self.assertIsNone(group["exemption_end"])
        self.assertNotEqual(group["urgency"], "hoje")

    def test_retificacao_bucket(self):
        contest = self._contest("pci-7", "Com retificação")
        self._alert(kind="retificacao", severity="atencao", contest=contest, title="Retif")
        self.assertEqual(ops.triage(self.db)["groups"][0]["urgency"], "retificacoes")

    def test_exemption_end_prefers_most_recent_proposal(self):
        # Uma proposta antiga (expirada) não pode rejuvenescer/envelhecer o prazo: vale a
        # proposta mais recente.
        future = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
        contest = self._deadline("pci-11", 30)
        with closing(connect_documents(self.db)) as conn, conn:
            ev = conn.execute("SELECT id FROM evidencias LIMIT 1").fetchone()[0]
            conn.execute(
                """INSERT INTO propostas_campo(id,contest_id,role_id,field_name,value_json,
                value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at)
                VALUES('old-prop',?,NULL,'exemption_end','"2020-01-01"','string',?,'t',NULL,
                '2026-01-01T00:00:00+00:00')""", (contest, ev))
        self._alert(kind="prazo_isencao", severity="atencao", contest=contest, title="Isenção")
        group = ops.triage(self.db)["groups"][0]
        self.assertEqual(group["exemption_end"], future)
        self.assertNotEqual(group["urgency"], "hoje")


class MigrationSeedingTest(TriageBase):
    """Regressão C1: migrar um banco com histórico não pode duplicar alertas."""

    def _document_with_version(self, contest):
        from radar.document_store import record_version
        obs = ensure_observation(self.db, f"https://exemplo.test/{contest}", contest)
        did = register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url=f"https://exemplo.test/{contest}/e.pdf",
            title="Edital", discovery_url=f"https://exemplo.test/{contest}",
            discovery_method="automatico", discovered_at=_now()))
        record_version(self.db, did, b"%PDF-1.4 x", dict(
            fetched_at=_now(), fetched_url=f"https://exemplo.test/{contest}/e.pdf",
            content_type="application/pdf"))
        return did

    def test_migration_seeds_watermarks_over_existing_history(self):
        from radar.document_store import migrate_document_schema
        did = self._document_with_version("pci-m1")
        with closing(connect_documents(self.db)) as conn:
            fetched_at = conn.execute(
                "SELECT fetched_at FROM versoes_documento WHERE document_id=?", (did,)).fetchone()[0]
            # Alerta pré-existente no formato ANTIGO de chave (base v8, Fase 18).
            conn.execute(
                """INSERT INTO alertas(id,kind,severity,dedup_key,title,event_at,created_at)
                VALUES('old-alert','documento_recuperado','info',?,'Documento oficial recuperado',?,?)""",
                (f"documento_recuperado:{did}:{fetched_at}", fetched_at, fetched_at))
            conn.commit()
        # Migração roda DEPOIS de já existir histórico (caso real da base v8->v9).
        migrate_document_schema(self.db)
        with closing(connect_documents(self.db)) as conn:
            seeded = conn.execute("SELECT key FROM ops_state WHERE key LIKE 'alerts.watermark.%'").fetchall()
        self.assertEqual({r[0] for r in seeded},
                         {"alerts.watermark.documentos", "alerts.watermark.versoes"})
        # O primeiro ciclo após a migração NÃO reprocessa o histórico (nada duplicado).
        result = ops.generate_alerts(self.db, now=_now())
        self.assertEqual(result["created"]["novo_candidato"], 0)
        self.assertEqual(result["created"]["documento_recuperado"], 0)
        with closing(connect_documents(self.db)) as conn:
            total = conn.execute(
                "SELECT count(*) FROM alertas WHERE kind='documento_recuperado'").fetchone()[0]
        self.assertEqual(total, 1)  # apenas o alerta antigo, sem duplicata

    def test_new_documents_after_migration_are_alerted(self):
        from radar.document_store import migrate_document_schema
        self._document_with_version("pci-m2")
        migrate_document_schema(self.db)  # semeia watermark no histórico
        self._document_with_version("pci-m3")  # documento novo, depois do watermark
        result = ops.generate_alerts(self.db, now=_now())
        self.assertEqual(result["created"]["novo_candidato"], 1)
        self.assertEqual(result["created"]["documento_recuperado"], 1)

    def test_reprocessing_does_not_duplicate_documento_recuperado(self):
        self._document_with_version("pci-m4")
        ops.generate_alerts(self.db, now=_now())
        with closing(connect_documents(self.db)) as conn, conn:
            # Simula reprocessamento: apaga o watermark de versões.
            conn.execute("DELETE FROM ops_state WHERE key='alerts.watermark.versoes'")
        again = ops.generate_alerts(self.db, now=_now())
        with closing(connect_documents(self.db)) as conn:
            total = conn.execute(
                "SELECT count(*) FROM alertas WHERE kind='documento_recuperado'").fetchone()[0]
            distinct = conn.execute(
                "SELECT count(DISTINCT dedup_key) FROM alertas WHERE kind='documento_recuperado'"
            ).fetchone()[0]
        self.assertEqual(total, distinct)  # sem duplicatas
        self.assertEqual(again["created"]["documento_recuperado"], 0)  # dedup por chave estável


class ActionsTest(TriageBase):
    def test_seen_removes_from_triage_but_keeps_history(self):
        self._alert(kind="falha_fonte", severity="atencao", title="Fonte X")
        alert_id = ops.list_alerts(self.db)[0]["id"]
        ops.mark_alert(self.db, alert_id, seen=True)
        self.assertEqual(ops.triage(self.db)["groups"], [])
        self.assertEqual(len(ops.list_alerts(self.db, unseen_only=False)), 1)  # histórico preservado
        # Reabrir volta a aparecer.
        ops.mark_alert(self.db, alert_id, seen=False)
        self.assertEqual(len(ops.triage(self.db)["groups"]), 1)

    def test_snooze_hides_until_date_then_returns(self):
        self._alert(kind="falha_fonte", severity="atencao", title="Fonte X")
        alert_id = ops.list_alerts(self.db)[0]["id"]
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        ops.mark_alert(self.db, alert_id, snooze_until=future)
        self.assertEqual(ops.triage(self.db)["groups"], [])
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        ops.mark_alert(self.db, alert_id, snooze_until=past)
        self.assertEqual(len(ops.triage(self.db)["groups"]), 1)

    def test_snooze_rejects_invalid_date(self):
        self._alert(kind="falha_fonte", severity="atencao", title="Fonte X")
        alert_id = ops.list_alerts(self.db)[0]["id"]
        with self.assertRaises(ValueError):
            ops.mark_alert(self.db, alert_id, snooze_until="nao-e-data")

    def test_dismiss_does_not_delete_document(self):
        contest = self._contest("pci-6", "Concurso")
        self._alert(kind="novo_candidato", severity="info", contest=contest, title="A")
        alert_id = ops.list_alerts(self.db)[0]["id"]
        ops.mark_alert(self.db, alert_id, dismissed=True)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM documentos").fetchone()[0], 1)


class BacklogTest(TriageBase):
    def _many_documents(self, count):
        for i in range(count):
            obs = ensure_observation(self.db, f"https://exemplo.test/pci-{i}", f"pci-{i}")
            register_document(self.db, dict(
                observation_id=obs, kind="outro",
                official_url=f"https://exemplo.test/pci-{i}/e.pdf", title=f"Concurso {i}",
                discovery_url=f"https://exemplo.test/pci-{i}", discovery_method="automatico",
                discovered_at=f"2026-10-16T12:00:{i:02d}+00:00"))

    def test_backlog_over_limit_drains_incrementally(self):
        self._many_documents(120)
        first = ops.generate_alerts(self.db, now=_now(), max_new_alerts=50)
        self.assertEqual(first["created"]["novo_candidato"], 50)
        self.assertEqual(first["backlog"]["documentos"], 70)
        second = ops.generate_alerts(self.db, now=_now(), max_new_alerts=50)
        self.assertEqual(second["created"]["novo_candidato"], 50)  # continua de onde parou
        third = ops.generate_alerts(self.db, now=_now(), max_new_alerts=50)
        self.assertEqual(third["created"]["novo_candidato"], 20)
        self.assertEqual(third["backlog"]["documentos"], 0)
        # Nada duplicado: total = 120 alertas distintos.
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM alertas WHERE kind='novo_candidato'").fetchone()[0], 120)

    def test_no_duplicates_between_cycles(self):
        self._many_documents(60)
        ops.generate_alerts(self.db, now=_now(), max_new_alerts=30)
        again = ops.generate_alerts(self.db, now=_now(), max_new_alerts=30)
        self.assertEqual(again["created"]["novo_candidato"], 30)
        with closing(connect_documents(self.db)) as conn:
            total = conn.execute("SELECT count(*) FROM alertas").fetchone()[0]
            distinct = conn.execute("SELECT count(DISTINCT dedup_key) FROM alertas").fetchone()[0]
        self.assertEqual(total, distinct)

    def test_watermark_persisted_in_ops_state(self):
        self._many_documents(10)
        ops.generate_alerts(self.db, now=_now(), max_new_alerts=5)
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute("SELECT value FROM ops_state WHERE key='alerts.watermark.documentos'").fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
