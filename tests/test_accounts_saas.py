import hmac
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from threading import Thread

from radar import accounts, knowledge_store, my_contests, practice_store, study_backup, study_store
from radar.document_store import connect_documents, ensure_observation, migrate_document_schema
from radar.server import create_server


class TestAccountsAndMultiUserIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        migrate_document_schema(self.db_path)
        accounts.ensure_accounts_schema(self.db_path)

    def tearDown(self):
        Path(self.db_path).unlink(missing_ok=True)

    def test_register_login_and_scoping_isolation(self):
        admin = accounts.register_user(
            self.db_path,
            name="Admin Fundador",
            email="admin@gsnconcursos.com.br",
            password="Password123",
            allow_bootstrap_admin=True,
        )
        self.assertEqual(admin["role"], "admin")
        self.assertEqual(admin["plan"], "founder")

        alice = accounts.register_user(
            self.db_path,
            name="Alice Silva",
            email="alice@example.com",
            password="Password123",
        )
        self.assertEqual(alice["role"], "student")
        self.assertEqual(alice["plan"], "free")

        bob = accounts.register_user(
            self.db_path,
            name="Bob Souza",
            email="bob@example.com",
            password="Password456",
        )
        self.assertEqual(bob["role"], "student")

        # Authentication check
        self.assertIsNone(accounts.authenticate_user(self.db_path, email="alice@example.com", password="wrong"))
        ok_alice = accounts.authenticate_user(self.db_path, email="ALICE@example.com", password="Password123")
        self.assertIsNotNone(ok_alice)
        self.assertEqual(ok_alice["id"], alice["id"])

        # Isolation: My Contests can select the exact same contest_id per user
        obs_id = ensure_observation(self.db_path, "https://exemplo.gov.br/concurso-ti", "ti-2026")
        conn = connect_documents(self.db_path)
        try:
            cid = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?", (obs_id,)).fetchone()[0]
        finally:
            conn.close()
        my_contests.add_my_contest(self.db_path, cid, user_id=alice["id"])
        my_contests.add_my_contest(self.db_path, cid, user_id=bob["id"])
        self.assertEqual(len(my_contests.list_my_contests(self.db_path, user_id=alice["id"])), 1)
        self.assertEqual(len(my_contests.list_my_contests(self.db_path, user_id=bob["id"])), 1)
        self.assertEqual(len(my_contests.list_my_contests(self.db_path, user_id="")), 0)
        my_contests.remove_my_contest(self.db_path, cid, user_id=alice["id"])
        self.assertEqual(len(my_contests.list_my_contests(self.db_path, user_id=alice["id"])), 0)
        self.assertEqual(len(my_contests.list_my_contests(self.db_path, user_id=bob["id"])), 1)

        # Isolation: Flashcards & Study Sessions
        practice_store.create_flashcard(self.db_path, frente="F1 Alice", verso="V1", user_id=alice["id"])
        practice_store.create_flashcard(self.db_path, frente="F1 Bob", verso="V2", user_id=bob["id"])
        self.assertEqual(len(practice_store.list_flashcards(self.db_path, user_id=alice["id"])), 1)
        self.assertEqual(practice_store.list_flashcards(self.db_path, user_id=alice["id"])[0]["frente"], "F1 Alice")
        self.assertEqual(len(practice_store.list_flashcards(self.db_path, user_id=bob["id"])), 1)

        # Two different students can run active timers simultaneously
        s_alice = study_store.start_session(self.db_path, user_id=alice["id"])
        s_bob = study_store.start_session(self.db_path, user_id=bob["id"])
        self.assertNotEqual(s_alice["id"], s_bob["id"])
        study_store.finish_session(self.db_path, s_alice["id"], user_id=alice["id"])
        study_store.finish_session(self.db_path, s_bob["id"], user_id=bob["id"])

    def test_billing_webhook_pre_and_post_registration(self):
        # Webhook arrives BEFORE user registers
        res = accounts.apply_billing_event(
            self.db_path,
            provider="kiwify",
            email="comprador@ti.br",
            plan="pro",
            event_type="purchase_approved",
        )
        self.assertTrue(res["ok"])
        self.assertFalse(res["user_updated"])

        # Buyer registers later and receives Pro automatically
        buyer = accounts.register_user(
            self.db_path,
            name="Comprador TI",
            email="comprador@ti.br",
            password="SecretPassword",
        )
        self.assertEqual(buyer["plan"], "pro")
        self.assertEqual(buyer["plan_status"], "active")


class TestAuthAndBillingHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        migrate_document_schema(self.db_path)
        accounts.ensure_accounts_schema(self.db_path)
        self.old_secret = os.environ.get("RADAR_BILLING_SECRET")
        os.environ["RADAR_BILLING_SECRET"] = "segredo-webhook-teste"
        self.server = create_server(self.db_path, host="127.0.0.1", port=0)
        self.port = self.server.server_port
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        if self.old_secret is None:
            os.environ.pop("RADAR_BILLING_SECRET", None)
        else:
            os.environ["RADAR_BILLING_SECRET"] = self.old_secret
        Path(self.db_path).unlink(missing_ok=True)

    def _req(self, method, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req_headers = dict(headers or {})
        if data is not None:
            req_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers=req_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8")), dict(resp.headers)
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8")
            return err.code, (json.loads(raw) if raw else None), dict(err.headers)

    def test_auth_flow_and_webhook_secret(self):
        status, me, _ = self._req("GET", "/api/auth/me")
        self.assertEqual(status, 200)
        self.assertFalse(me["authenticated"])
        self.assertTrue(me["billing_configured"])

        # Register student
        status, reg, headers = self._req(
            "POST",
            "/api/auth/register",
            {"name": "Estudante Teste", "email": "aluno@teste.com", "password": "Password123"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(reg["user"]["role"], "student")
        cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
        self.assertTrue(cookie.startswith("gsn_session="))

        # Session recognized via cookie
        status, me2, _ = self._req("GET", "/api/auth/me", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertTrue(me2["authenticated"])
        self.assertEqual(me2["user"]["email"], "aluno@teste.com")

        # Student cannot access admin endpoint
        status, _, _ = self._req("GET", "/api/admin/users", headers={"Cookie": cookie})
        self.assertEqual(status, 403)

        # Webhook rejects missing/bad secret and accepts valid secret
        status, _, _ = self._req("POST", "/api/billing/webhook", {"email": "aluno@teste.com", "plan": "pro"})
        self.assertEqual(status, 403)

        status, wh, _ = self._req(
            "POST",
            "/api/billing/webhook",
            {"email": "aluno@teste.com", "plan": "pro", "provider": "kiwify"},
            headers={"X-Webhook-Secret": "segredo-webhook-teste"},
        )
        self.assertEqual(status, 200)
        self.assertTrue(wh["user_updated"])

        # Student plan is now Pro
        status, me3, _ = self._req("GET", "/api/auth/me", headers={"Cookie": cookie})
        self.assertEqual(me3["user"]["plan"], "pro")

    def test_idor_rbac_require_auth_and_webhook_origin(self):
        # Register Alice and Bob
        _, reg_a, h_a = self._req(
            "POST",
            "/api/auth/register",
            {"name": "Alice", "email": "alice.idor@teste.com", "password": "Password123"},
        )
        cookie_a = h_a.get("Set-Cookie", "").split(";", 1)[0]
        alice_id = reg_a["user"]["id"]

        _, reg_b, h_b = self._req(
            "POST",
            "/api/auth/register",
            {"name": "Bob", "email": "bob.idor@teste.com", "password": "Password123"},
        )
        cookie_b = h_b.get("Set-Cookie", "").split(";", 1)[0]

        # 1. Flashcard IDOR defense: Bob cannot update or review Alice's flashcard
        st_fc, fc_a, _ = self._req(
            "POST",
            "/api/estudos/flashcards",
            {"action": "create", "frente": "Segredo Alice", "verso": "Resposta"},
            headers={"Cookie": cookie_a},
        )
        self.assertEqual(st_fc, 200)
        st_idor_upd, _, _ = self._req(
            "POST",
            "/api/estudos/flashcards",
            {"action": "update", "id": fc_a["id"], "frente": "Hackeado"},
            headers={"Cookie": cookie_b},
        )
        self.assertEqual(st_idor_upd, 400)
        st_idor_rev, _, _ = self._req(
            "POST",
            "/api/estudos/flashcards",
            {"action": "review", "id": fc_a["id"], "qualidade": 5},
            headers={"Cookie": cookie_b},
        )
        self.assertEqual(st_idor_rev, 400)

        # 2. Exam IDOR defense: Bob cannot read or finish Alice's simulado
        practice_store.create_question(
            self.db_path,
            enunciado="Qual a porta padrão do HTTPS?",
            alternativas=[{"letra": "A", "texto": "443"}, {"letra": "B", "texto": "80"}],
            gabarito="A",
            disciplina="Redes de Computadores",
        )
        st_ex, exam_a, _ = self._req(
            "POST",
            "/api/estudos/simulados",
            {"nome": "Simulado Alice", "limit": 1},
            headers={"Cookie": cookie_a},
        )
        self.assertEqual(st_ex, 200)
        st_idor_get, _, _ = self._req(
            "GET",
            f"/api/estudos/simulados/{exam_a['id']}",
            headers={"Cookie": cookie_b},
        )
        self.assertEqual(st_idor_get, 404)
        st_idor_fin, _, _ = self._req(
            "POST",
            f"/api/estudos/simulados/{exam_a['id']}/finalizar",
            {},
            headers={"Cookie": cookie_b},
        )
        self.assertEqual(st_idor_fin, 400)

        # 3. Knowledge profile & export isolation
        knowledge_store.set_profile(
            self.db_path, disciplina="Redes", rotulo="TCP", nivel="avancado", user_id=alice_id
        )
        self.assertEqual(len(knowledge_store.list_profile(self.db_path, user_id=alice_id)), 1)
        self.assertEqual(len(knowledge_store.list_profile(self.db_path, user_id=reg_b["user"]["id"])), 0)
        exp_b = study_backup.export_study_data(self.db_path, user_id=reg_b["user"]["id"])
        self.assertEqual(exp_b["counts"]["flashcards"], 0)
        self.assertEqual(exp_b["counts"]["simulados"], 0)
        self.assertEqual(exp_b["counts"]["perfil"], 0)

        # 4. RBAC: Student gets 403 on admin/editorial routes
        for method, route, payload in [
            ("POST", "/api/curadoria/executar", {"dry_run": True}),
            ("POST", "/api/estudos/aulas", {"titulo": "Aula X", "disciplina": "Redes"}),
            ("POST", "/api/estudos/questoes", {"action": "create", "enunciado": "Q"}),
            ("GET", "/api/pipeline", None),
            ("GET", "/api/revisao/grupos", None),
        ]:
            st_rbac, _, _ = self._req(method, route, payload, headers={"Cookie": cookie_a})
            self.assertEqual(st_rbac, 403, f"Esperado 403 em {method} {route}")

        # 5. Per-user preferences: Alice saving UF="SP" does not overwrite Bob's preferences
        st_pref_a, pref_a, _ = self._req(
            "POST",
            "/api/preferencias",
            {"reference_uf": "SP"},
            headers={"Cookie": cookie_a},
        )
        self.assertEqual(st_pref_a, 200)
        self.assertEqual(pref_a["reference_uf"], "SP")
        _, pref_b, _ = self._req("GET", "/api/preferencias", headers={"Cookie": cookie_b})
        self.assertNotEqual(pref_b["reference_uf"], "SP")

        # 6. Webhook with external Origin + X-Hotmart-Hottok succeeds, and RADAR_REQUIRE_AUTH=1 blocks anon
        old_req = os.environ.get("RADAR_REQUIRE_AUTH")
        os.environ["RADAR_REQUIRE_AUTH"] = "1"
        try:
            st_anon, _, _ = self._req("GET", "/api/meus-concursos")
            self.assertEqual(st_anon, 401)
            st_pub_health, _, _ = self._req("GET", "/api/saude")
            self.assertIn(st_pub_health, (200, 503))
            st_wh_ext, wh_ext, _ = self._req(
                "POST",
                "/api/billing/webhook",
                {"email": "bob.idor@teste.com", "plan": "pro", "provider": "hotmart"},
                headers={
                    "Origin": "https://pay.hotmart.com",
                    "X-Hotmart-Hottok": "segredo-webhook-teste",
                },
            )
            self.assertEqual(st_wh_ext, 200)
            self.assertTrue(wh_ext["user_updated"])
        finally:
            if old_req is None:
                os.environ.pop("RADAR_REQUIRE_AUTH", None)
            else:
                os.environ["RADAR_REQUIRE_AUTH"] = old_req


if __name__ == "__main__":
    unittest.main()
