"""Operação autônoma: configuração, ciclo, instância única, alertas e saúde."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import ops, ops_config
from radar.document_store import (connect_documents, ensure_observation,
                                  migrate_document_schema, record_version, register_document)

_TS = "2026-10-16T12:00:00+00:00"


def _iso(dt):
    return dt.isoformat()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _close_ops_logger():
    """Fecha os handlers do logger de operações (libera o arquivo no Windows)."""
    import logging
    logger = logging.getLogger(ops.LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()

    def _config(self, **over):
        cfg = ops_config.load_config()
        cfg.update({"project_root": str(self.root), "python": str(Path(__import__("sys").executable)),
                    "db_path": str(self.root / "data" / "radar.sqlite3"),
                    "logs_dir": str(self.root / "logs")})
        cfg.update(over)
        return cfg

    def test_valid_config_has_no_errors(self):
        self.assertEqual(ops_config.validate_config(self._config()), [])

    def test_missing_python_is_invalid(self):
        errors = ops_config.validate_config(self._config(python=str(self.root / "nope")))
        self.assertTrue(any("python" in e for e in errors))

    def test_missing_project_root_is_invalid(self):
        errors = ops_config.validate_config(self._config(project_root=str(self.root / "nope")))
        self.assertTrue(any("project_root" in e for e in errors))

    def test_creatable_db_directory_is_valid(self):
        # O ciclo cria o diretório do banco; um caminho ainda inexistente é válido.
        errors = ops_config.validate_config(self._config(db_path=str(self.root / "novo" / "x.sqlite3")))
        self.assertEqual(errors, [])

    def test_db_path_under_a_file_is_invalid(self):
        blocker = self.root / "arquivo.txt"
        blocker.write_text("x", encoding="utf-8")
        errors = ops_config.validate_config(self._config(db_path=str(blocker / "x.sqlite3")))
        self.assertTrue(any("banco" in e for e in errors))

    def test_source_selection_respects_config(self):
        from radar import ops as _ops
        cfg = self._config()
        for name in cfg["sources"]:
            cfg["sources"][name]["enabled"] = (name != "fgv")
        picked = _ops._select_sources(cfg)
        ids = {s.get("id") for s in picked}
        self.assertNotIn("fgv-conhecimento", ids)   # desabilitada
        self.assertIn("quadrix", ids)
        self.assertIn("pci", ids)
        self.assertIn("dou-secao-3", ids)

    def test_no_enabled_source_is_invalid(self):
        cfg = self._config()
        cfg["sources"] = {k: {"enabled": False, "min_interval_hours": 6} for k in cfg["sources"]}
        self.assertTrue(any("fonte" in e for e in ops_config.validate_config(cfg)))

    def test_batch_limit_must_be_positive_int(self):
        self.assertTrue(any("batch_limit" in e for e in
                            ops_config.validate_config(self._config(batch_limit=0))))

    def test_env_override_and_relative_resolution(self):
        import os
        os.environ["RADAR_DB"] = "data/outro.sqlite3"
        try:
            cfg = ops_config.load_config()
        finally:
            del os.environ["RADAR_DB"]
        self.assertTrue(cfg["db_path"].endswith("data\\outro.sqlite3") or
                        cfg["db_path"].endswith("data/outro.sqlite3"))
        self.assertTrue(Path(cfg["db_path"]).is_absolute())

    def test_save_default_config_is_idempotent_without_overwrite(self):
        path = self.root / "radar_ops.json"
        ops_config.save_default_config(path)
        first = path.read_text(encoding="utf-8")
        ops_config.save_default_config(path)  # não sobrescreve
        self.assertEqual(path.read_text(encoding="utf-8"), first)
        payload = json.loads(first)
        self.assertNotIn("password", json.dumps(payload).lower())


class OpsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(_close_ops_logger)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        self.db = str(self.root / "data" / "radar.sqlite3")
        migrate_document_schema(self.db)
        self.cfg = ops_config.load_config()
        self.cfg.update({"project_root": str(self.root),
                         "python": str(Path(__import__("sys").executable)),
                         "db_path": self.db, "logs_dir": str(self.root / "logs")})
        self.logger = ops.setup_logging(self.cfg["logs_dir"])

    def _fake_source(self, *, source_url="https://exemplo.test/a/", register=None, fail=False):
        def fetch():
            if fail:
                raise TimeoutError("fonte fora do ar")
            return "<html></html>"

        def discover(db_path, html):
            if register:
                register(db_path)
            return []
        return {"id": "fake", "source_url": source_url, "name": "Fake",
                "multi_contest": True, "fetch": fetch, "discover": discover}


class CycleTest(OpsBase):
    def _register_doc(self, db_path, *, kind="retificacao", at=None):
        at = at or _now()
        obs = ensure_observation(db_path, "https://exemplo.test/a/", "X-1")
        did = register_document(db_path, dict(
            observation_id=obs, kind=kind, official_url="https://exemplo.test/a/e.pdf",
            title="Doc", discovery_url="https://exemplo.test/a/", discovery_method="automatico",
            discovered_at=at))
        record_version(db_path, did, b"%PDF-1.4 x", dict(
            fetched_at=at, fetched_url="https://exemplo.test/a/e.pdf", content_type="application/pdf"))

    def test_cycle_runs_and_persists(self):
        r = ops.run_cycle(self.cfg, sources=[self._fake_source(register=self._register_doc)],
                          logger=self.logger)
        self.assertEqual(r["state"], "concluido")
        self.assertEqual(len(r["sources"]), 1)
        self.assertTrue(Path(self.db).exists())

    def test_isolated_source_failure_does_not_stop_others(self):
        good = self._fake_source(source_url="https://exemplo.test/good/")
        bad = self._fake_source(source_url="https://exemplo.test/bad/", fail=True)
        r = ops.run_cycle(self.cfg, sources=[bad, good], logger=self.logger)
        self.assertEqual(r["state"], "parcial")
        states = {s["source_url"]: s["state"] for s in r["sources"]}
        self.assertEqual(states["https://exemplo.test/bad/"], "falhou")
        self.assertEqual(states["https://exemplo.test/good/"], "concluido")

    def test_all_sources_failing_is_falhou(self):
        r = ops.run_cycle(self.cfg, sources=[self._fake_source(fail=True)], logger=self.logger)
        self.assertEqual(r["state"], "falhou")

    def test_new_document_generates_alerts_and_is_idempotent(self):
        r = ops.run_cycle(self.cfg, sources=[self._fake_source(register=self._register_doc)],
                          logger=self.logger)
        self.assertGreaterEqual(r["alerts"]["total"], 2)  # novo_candidato + retificacao + recuperado
        r2 = ops.run_cycle(self.cfg, sources=[self._fake_source(register=self._register_doc)],
                           logger=self.logger)
        self.assertEqual(r2["alerts"]["total"], 0)  # dedup por chave

    def test_invalid_config_aborts_without_touching_db(self):
        cfg = dict(self.cfg, python=str(self.root / "nope"))
        r = ops.run_cycle(cfg, sources=[self._fake_source()], logger=self.logger)
        self.assertEqual(r["state"], "falhou")
        self.assertTrue(r["config_errors"])

    def test_second_concurrent_run_is_skipped(self):
        lock = ops.InstanceLock(str(self.root / "data" / ops.LOCK_FILENAME))
        self.assertTrue(lock.acquire())
        try:
            r = ops.run_cycle(self.cfg, sources=[self._fake_source()], logger=self.logger)
            self.assertEqual(r["state"], "ignorado")
        finally:
            lock.release()
        # Após liberar, o ciclo volta a rodar.
        r2 = ops.run_cycle(self.cfg, sources=[self._fake_source()], logger=self.logger)
        self.assertIn(r2["state"], ("concluido", "parcial"))


class InstanceLockTest(OpsBase):
    def test_lock_is_exclusive_and_released(self):
        path = str(self.root / "data" / ops.LOCK_FILENAME)
        a = ops.InstanceLock(path)
        self.assertTrue(a.acquire())
        b = ops.InstanceLock(path)
        self.assertFalse(b.acquire())  # segundo bloqueio falha
        a.release()
        c = ops.InstanceLock(path)
        self.assertTrue(c.acquire())
        c.release()

    def test_lock_release_allows_retake(self):
        path = str(self.root / "data" / ops.LOCK_FILENAME)
        with ops.InstanceLock(path):
            pass
        with ops.InstanceLock(path):  # não fica preso
            pass

    def test_exclusive_fallback_acquires_and_recovers(self):
        # Regressão (fallback POSIX): adquire, rejeita o segundo, e recupera marcador
        # abandonado (PID inexistente) sem recursão infinita.
        path = str(self.root / "data" / ops.LOCK_FILENAME)
        a = ops.InstanceLock(path)
        self.assertTrue(a._acquire_exclusive())
        b = ops.InstanceLock(path)
        self.assertFalse(b._acquire_exclusive())  # arquivo existe e PID vivo
        a.release()
        # Marcador abandonado (PID inválido) é recuperável.
        Path(path).write_text(json.dumps({"pid": 999999999, "started_at": _now()}), encoding="utf-8")
        c = ops.InstanceLock(path)
        self.assertTrue(c._acquire_exclusive())
        c.release()


class AlertTest(OpsBase):
    def _deadline_proposal(self, db_path, days_from_now):
        from contextlib import closing
        obs = ensure_observation(db_path, "https://exemplo.test/a/", "X-1")
        with closing(connect_documents(db_path)) as conn:
            contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                   (obs,)).fetchone()[0]
        did = register_document(db_path, dict(
            observation_id=obs, kind="outro", official_url="https://exemplo.test/a/e.pdf",
            title="Edital", discovery_url="https://exemplo.test/a/", discovery_method="automatico",
            discovered_at=_now()))
        version = record_version(db_path, did, b"%PDF-1.4 x", dict(
            fetched_at=_now(), fetched_url="https://exemplo.test/a/e.pdf",
            content_type="application/pdf"))
        deadline = (datetime.now(timezone.utc) + timedelta(days=days_from_now)).date().isoformat()
        from radar.document_store import record_analysis
        block = dict(page_number=1, locator="p", start_offset=0, end_offset=1, text="x")
        record_analysis(db_path, version, [block], [dict(
            contest_id=contest, role_id=None, field_name="exemption_end",
            value_json=json.dumps(deadline), value_type="string", extraction_method="t",
            ambiguity_reason="x", evidence=dict(block_index=0, quote="x", start_offset=0, end_offset=1))])
        return contest

    def _prazo_alert(self):
        return next(a for a in ops.list_alerts(self.db) if a["kind"] == "prazo_isencao")

    def test_near_exemption_deadline_creates_alert(self):
        self._deadline_proposal(self.db, 3)
        created = ops.generate_alerts(self.db, now=_now())
        self.assertEqual(created["created"]["prazo_isencao"], 1)
        alert = self._prazo_alert()
        self.assertEqual(alert["kind"], "prazo_isencao")
        self.assertEqual(alert["severity"], "atencao")

    def test_expired_deadline_is_critical(self):
        self._deadline_proposal(self.db, -1)
        ops.generate_alerts(self.db, now=_now())
        self.assertEqual(self._prazo_alert()["severity"], "critico")

    def test_deadline_escalates_from_atencao_to_critico(self):
        # Regressão: um prazo que primeiro entra no horizonte (atencao) deve gerar um
        # alerta crítico quando expira (chave de dedup inclui o estado).
        from datetime import timedelta as _td
        self._deadline_proposal(self.db, 3)
        first = ops.generate_alerts(self.db, now=_now())
        self.assertEqual(first["created"]["prazo_isencao"], 1)
        self.assertEqual(self._prazo_alert()["severity"], "atencao")
        later = (datetime.now(timezone.utc) + _td(days=10)).isoformat()
        second = ops.generate_alerts(self.db, now=later)
        self.assertEqual(second["created"]["prazo_isencao"], 1)  # escala para crítico
        severities = {a["severity"] for a in ops.list_alerts(self.db) if a["kind"] == "prazo_isencao"}
        self.assertIn("critico", severities)

    def test_malformed_deadline_value_does_not_abort(self):
        # Regressão: um value_json não-string (linha fora do padrão) não pode derrubar a
        # geração de alertas. Inserido direto no banco (record_analysis valida datas).
        from contextlib import closing as _closing
        from uuid import uuid4
        from radar.document_store import connect_documents as _conn
        obs = ensure_observation(self.db, "https://exemplo.test/a/", "X-1")
        with _closing(_conn(self.db)) as conn:
            contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                   (obs,)).fetchone()[0]
        did = register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url="https://exemplo.test/a/e.pdf",
            title="Edital", discovery_url="https://exemplo.test/a/", discovery_method="automatico",
            discovered_at=_now()))
        version = record_version(self.db, did, b"%PDF-1.4 x", dict(
            fetched_at=_now(), fetched_url="https://exemplo.test/a/e.pdf",
            content_type="application/pdf"))
        block_id = str(uuid4())
        with _closing(_conn(self.db)) as conn, conn:
            conn.execute("INSERT INTO blocos_documento VALUES (?,?,?,?,?,?,?)",
                         (block_id, version, 1, "p", 0, 1, "x"))
            evidence_id = str(uuid4())
            conn.execute("INSERT INTO evidencias VALUES (?,?,?,?,?,?,?,?,?)",
                         (evidence_id, version, block_id, "x", 1, "p", 0, 1, _now()))
            conn.execute(
                """INSERT INTO propostas_campo VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid4()), contest, None, "exemption_end", json.dumps("null"), "string",
                 evidence_id, "t", "x", _now()))
        created = ops.generate_alerts(self.db, now=_now())  # não deve levantar
        self.assertEqual(created["created"]["prazo_isencao"], 0)

    def test_far_deadline_creates_no_alert(self):
        self._deadline_proposal(self.db, 90)
        created = ops.generate_alerts(self.db, now=_now())
        self.assertEqual(created["created"]["prazo_isencao"], 0)

    def test_unknown_deadline_does_not_alert(self):
        created = ops.generate_alerts(self.db, now=_now())
        self.assertEqual(created["total"], 0)

    def test_mark_alert_seen_and_dismissed(self):
        self._deadline_proposal(self.db, 2)
        ops.generate_alerts(self.db, now=_now())
        alert_id = self._prazo_alert()["id"]
        self.assertTrue(ops.mark_alert(self.db, alert_id, seen=True))
        remaining = {a["id"] for a in ops.list_alerts(self.db, unseen_only=True)}
        self.assertNotIn(alert_id, remaining)
        self.assertTrue(ops.mark_alert(self.db, alert_id, dismissed=True))
        self.assertNotIn(alert_id, {a["id"] for a in ops.list_alerts(self.db, unseen_only=True)})

    def test_mark_alert_snooze_preserves_history(self):
        self._deadline_proposal(self.db, 2)
        ops.generate_alerts(self.db, now=_now())
        alert_id = self._prazo_alert()["id"]
        future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        self.assertTrue(ops.mark_alert(self.db, alert_id, snooze_until=future))
        # Some da triagem agora, mas o histórico permanece.
        self.assertNotIn(alert_id, {a["id"] for a in ops.triage(self.db)["groups"][0]["alerts"]})
        self.assertIn(alert_id, {a["id"] for a in ops.list_alerts(self.db)})

    def test_source_failure_generates_alert(self):
        r = ops.run_cycle(self.cfg, sources=[self._fake_source(fail=True)], logger=self.logger)
        alerts = [a for a in ops.list_alerts(self.db) if a["kind"] == "falha_fonte"]
        self.assertEqual(len(alerts), 1)


class HealthTest(OpsBase):
    def test_health_without_db(self):
        cfg = dict(self.cfg, db_path=str(self.root / "data" / "novo.sqlite3"))
        h = ops.health(cfg, check_server=False)
        self.assertEqual(h["status"], "banco_indisponivel")
        self.assertFalse(h["ready"])

    def test_health_invalid_config(self):
        h = ops.health(dict(self.cfg, python=str(self.root / "nope")), check_server=False)
        self.assertEqual(h["status"], "configuracao_invalida")

    def test_health_after_cycle(self):
        ops.run_cycle(self.cfg, sources=[self._fake_source(register=lambda db: self._touch(db))],
                      logger=self.logger)
        h = ops.health(self.cfg, check_server=False)
        self.assertTrue(h["ready"])
        self.assertEqual(h["status"], "pronto")
        self.assertIsNotNone(h["last_cycle"])
        self.assertIn("queue", h)
        self.assertIn("alerts", h)
        self.assertEqual(h["database"]["schema_version"], 11)

    def _touch(self, db_path):
        obs = ensure_observation(db_path, "https://exemplo.test/a/", "X-1")
        register_document(db_path, dict(
            observation_id=obs, kind="outro", official_url="https://exemplo.test/a/e.pdf",
            title="Edital", discovery_url="https://exemplo.test/a/", discovery_method="automatico",
            discovered_at=_now()))

    def test_health_reports_partial_as_limited(self):
        good = self._fake_source(source_url="https://exemplo.test/good/")
        bad = self._fake_source(source_url="https://exemplo.test/bad/", fail=True)
        ops.run_cycle(self.cfg, sources=[bad, good], logger=self.logger)
        h = ops.health(self.cfg, check_server=False)
        self.assertEqual(h["status"], "funcionando_com_limitacoes")


class LoggingTest(OpsBase):
    def test_cycle_writes_rotating_log(self):
        ops.run_cycle(self.cfg, sources=[self._fake_source()], logger=self.logger)
        log = Path(self.cfg["logs_dir"]) / ops.LOG_FILENAME
        self.assertTrue(log.exists())
        text = log.read_text(encoding="utf-8")
        self.assertIn("run=", text)
        self.assertNotIn("password", text.lower())


if __name__ == "__main__":
    unittest.main()
