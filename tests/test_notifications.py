"""Notificações nativas: política, dedup, frequência, limites e segurança."""

import json
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import notifications, ops, ops_config
from radar.document_store import (connect_documents, ensure_observation, migrate_document_schema,
                                  record_analysis, record_version, register_document)


def _now():
    return datetime.now(timezone.utc).isoformat()


class NotificationsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir()
        self.db = str(self.root / "data" / "radar.sqlite3")
        migrate_document_schema(self.db)
        self.cfg = ops_config.load_config()
        self.cfg.update({"project_root": str(self.root), "db_path": self.db,
                         "logs_dir": str(self.root / "logs")})
        self.cfg["notifications"] = dict(ops_config.DEFAULTS["notifications"], local=True,
                                         min_interval_seconds=0)

    def _seed_alert(self, *, kind="prazo_isencao", severity="critico", contest="c1",
                    title="Isenção proxima", detail="Fim: 2026-10-20", dedup=None):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            created = ops._insert_alert(
                conn, kind=kind, severity=severity, contest_id=contest,
                dedup_key=dedup or f"{kind}:{contest}:{title}", title=title, detail=detail,
                event_at=_now())
            conn.commit()
        return created


class PolicyTest(NotificationsBase):
    def test_disabled_channel_sends_nothing(self):
        self.cfg["notifications"]["local"] = False
        self._seed_alert()
        calls = []
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: calls.append(a) or {"accepted": True})
        self.assertFalse(result["enabled"])
        self.assertEqual(calls, [])
        self.assertEqual(result["sent"], 0)

    def test_critical_alert_is_eligible(self):
        self._seed_alert(kind="prazo_isencao", severity="critico")
        sent = []
        result = notifications.dispatch(self.db, self.cfg,
                                        runner=lambda t, b, l: sent.append((t, b, l)) or {"accepted": True})
        self.assertEqual(result["sent"], 1)
        self.assertTrue(sent)
        self.assertIn("isenção", sent[0][0].lower())

    def test_info_alert_is_not_eligible_by_default(self):
        self._seed_alert(kind="novo_candidato", severity="info")
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["considered"], 0)

    def test_category_filter(self):
        self._seed_alert(kind="novo_candidato", severity="critico")  # categoria fora da lista
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["considered"], 0)

    def test_dedup_does_not_resend(self):
        self._seed_alert()
        first = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        second = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["sent"], 0)
        self.assertEqual(second["considered"], 0)

    def test_error_is_retried_next_cycle(self):
        self._seed_alert()
        bad = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": False, "error": "boom"})
        self.assertEqual(bad["errors"], 1)
        good = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(good["sent"], 1)

    def test_limits_per_cycle_and_reports_backlog(self):
        for i in range(8):
            self._seed_alert(contest=f"c{i}", title=f"prazo {i}", dedup=f"k{i}")
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["sent"], self.cfg["notifications"]["max_per_cycle"])
        self.assertEqual(result["backlog"], 8 - self.cfg["notifications"]["max_per_cycle"])
        # O excedente é retomado no ciclo seguinte (nada descartado).
        second = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(second["sent"], 3)

    def test_snoozed_alert_is_not_notified(self):
        self._seed_alert()
        alert_id = ops.list_alerts(self.db)[0]["id"]
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        ops.mark_alert(self.db, alert_id, snooze_until=future)
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["sent"], 0)

    def test_seen_alert_is_not_notified(self):
        self._seed_alert()
        alert_id = ops.list_alerts(self.db)[0]["id"]
        ops.mark_alert(self.db, alert_id, seen=True)
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["sent"], 0)

    def test_severity_escalation_creates_new_notification(self):
        # Novo alerta (dedup diferente) com severidade maior é notificado de novo.
        self._seed_alert(severity="atencao", dedup="esc:proximo")
        self.cfg["notifications"]["min_severity"] = "atencao"
        notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self._seed_alert(severity="critico", dedup="esc:expirado")
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["sent"], 1)

    def test_min_interval_suppresses_second_cycle(self):
        # Intervalo mínimo entre envios: ciclos muito próximos não disparam rajada.
        self.cfg["notifications"]["min_interval_seconds"] = 30
        self._seed_alert(dedup="a")
        first = notifications.dispatch(self.db, self.cfg,
                                       runner=lambda *a: {"accepted": True}, now=_now())
        self.assertEqual(first["sent"], 1)
        self._seed_alert(dedup="b")
        second = notifications.dispatch(self.db, self.cfg,
                                        runner=lambda *a: {"accepted": True}, now=_now())
        self.assertEqual(second["sent"], 0)
        self.assertGreaterEqual(second["backlog"], 1)  # retomado, não descartado

    def test_zero_interval_does_not_suppress(self):
        self.cfg["notifications"]["min_interval_seconds"] = 0
        self._seed_alert(dedup="a")
        notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self._seed_alert(dedup="b")
        result = notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        self.assertEqual(result["sent"], 1)

    def test_negative_limit_does_not_drop_last(self):
        self._seed_alert(dedup="a")
        result = notifications.dispatch(self.db, self.cfg,
                                        runner=lambda *a: {"accepted": True}, limit=-1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["errors"], 0)


class MessageTest(NotificationsBase):
    def test_message_has_no_secrets_and_uses_local_launch(self):
        self._seed_alert(contest="abc-123", detail="Fim: 2026-10-20")
        sent = []
        notifications.dispatch(self.db, self.cfg,
                               runner=lambda t, b, l: sent.append((t, b, l)) or {"accepted": True})
        title, body, launch = sent[0]
        self.assertNotIn("password", (title + body).lower())
        self.assertNotIn("token", (title + body).lower())
        self.assertTrue(launch.startswith(self.cfg["notifications"]["base_url"]))
        self.assertIn("abc-123", launch)

    def test_launch_url_is_built_from_base_not_from_payload(self):
        # Uma URL hostil no payload não vira destino executado.
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            ops._insert_alert(conn, kind="retificacao", severity="atencao", contest_id=None,
                              dedup_key="hostil", title="Retificação",
                              detail="javascript:alert(1)", event_at=_now())
            conn.commit()
        sent = []
        notifications.dispatch(self.db, self.cfg,
                               runner=lambda t, b, l: sent.append(l) or {"accepted": True})
        self.assertTrue(sent[0].startswith(self.cfg["notifications"]["base_url"]))
        self.assertNotIn("javascript", sent[0].lower())


class StateTest(NotificationsBase):
    def test_notification_state_reports_pending(self):
        self._seed_alert()
        before = notifications.notification_state(self.db)
        self.assertGreaterEqual(before["pending"], 1)
        notifications.dispatch(self.db, self.cfg, runner=lambda *a: {"accepted": True})
        after = notifications.notification_state(self.db)
        self.assertEqual(after["by_state"].get("enviada"), 1)

    def test_native_support_detection(self):
        # O canal nativo é suportado apenas no Windows com o script presente.
        import sys
        self.assertEqual(notifications.native_supported(), sys.platform == "win32")

    @unittest.skipUnless(sys.platform == "win32", "identidade de app é específica do Windows")
    def test_app_identity_registered(self):
        # A identidade é registrada de forma idempotente num diretório isolado (não toca o
        # Menu Iniciar real do usuário).
        target = str(Path(self.tmp.name) / "shortcuts")
        Path(target).mkdir()
        first = notifications.ensure_app_identity(shortcut_dir=target)
        second = notifications.ensure_app_identity(shortcut_dir=target)
        self.assertTrue(first["ok"], first.get("error"))
        self.assertTrue(second["ok"], second.get("error"))
        self.assertTrue(Path(first["shortcut"]).exists())


if __name__ == "__main__":
    unittest.main()
