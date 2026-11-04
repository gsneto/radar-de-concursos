"""Testes da Fase 47: campos de quadro/Quadrix em record_analysis e menor distância entre municípios de prova."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from radar import geography, preferences, priority
from radar.document_store import (
    connect_documents,
    ensure_observation,
    migrate_document_schema,
    record_analysis,
    record_version,
    register_document,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


class RecordAnalysisQuadrixAndWideFieldsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)

    def test_record_analysis_aceita_vaga_municipio_e_colunas_unificadas(self):
        obs = ensure_observation(self.db, "https://www.quadrix.org.br/todos-os-concursos", "quadrix-3055")
        conn = connect_documents(self.db)
        try:
            contest_id = conn.execute(
                "SELECT contest_id FROM observacoes_concurso WHERE id=?", (obs,)
            ).fetchone()[0]
        finally:
            conn.close()

        did = register_document(
            self.db,
            dict(
                observation_id=obs,
                kind="edital",
                official_url="https://anexos-r2.selecao.net.br/uploads/3055/edital.pdf",
                title="Edital 1",
                discovery_url="https://www.quadrix.org.br/todos-os-concursos",
                discovery_method="automatico",
                discovered_at=_now(),
            ),
        )
        text = "200 Fiscal Belo Horizonte/MG 5 1 2 0+CR"
        blocks = [{"page_number": 1, "locator": "p1", "start_offset": 0, "end_offset": len(text), "text": text}]
        vid = record_version(
            self.db,
            did,
            b"%PDF-1.4 test",
            dict(
                fetched_at=_now(),
                fetched_url="https://anexos-r2.selecao.net.br/uploads/3055/edital.pdf",
                content_type="application/pdf",
            ),
        )
        proposals = [
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="vaga_municipio",
                value_json=json.dumps("Belo Horizonte/MG"),
                value_type="string",
                extraction_method="quadrix-quadro",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote="Belo Horizonte/MG", start_offset=11, end_offset=28),
            ),
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="unified_ppiq_vacancies",
                value_json=json.dumps(1),
                value_type="integer",
                extraction_method="quadro-colunas-pdf",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote=text, start_offset=0, end_offset=len(text)),
            ),
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="unified_pi_pq_vacancies",
                value_json=json.dumps(2),
                value_type="integer",
                extraction_method="quadro-colunas-pdf",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote=text, start_offset=0, end_offset=len(text)),
            ),
            dict(
                contest_id=contest_id,
                role_id=None,
                field_name="indigenous_reserve_notation",
                value_json=json.dumps("0+CR"),
                value_type="string",
                extraction_method="quadro-colunas-pdf",
                ambiguity_reason="escopo de cargo: 200 Fiscal",
                evidence=dict(block_index=0, quote="0+CR", start_offset=35, end_offset=39),
            ),
        ]
        record_analysis(self.db, vid, blocks, proposals, partial=False)

        conn = connect_documents(self.db)
        try:
            saved = dict(
                conn.execute(
                    "SELECT field_name, value_json FROM propostas_campo WHERE contest_id=?",
                    (contest_id,),
                ).fetchall()
            )
        finally:
            conn.close()

        self.assertEqual(json.loads(saved["vaga_municipio"]), "Belo Horizonte/MG")
        self.assertEqual(json.loads(saved["unified_ppiq_vacancies"]), 1)
        self.assertEqual(json.loads(saved["unified_pi_pq_vacancies"]), 2)
        self.assertEqual(json.loads(saved["indigenous_reserve_notation"]), "0+CR")


class ClosestExamMunicipioDistanceTest(unittest.TestCase):
    def test_escolhe_municipio_com_coordenada_e_menor_distancia(self):
        ref = {"municipio": "Paulo Afonso", "uf": "BA"}
        # Colatina e Guarapari não têm coordenada no seed; Vitória tem.
        out = geography.closest_distance_from_reference(
            ["Colatina", "Guarapari", "Vitória"], "ES", reference=ref
        )
        self.assertTrue(out["known"])
        self.assertIsNotNone(out["distance_km"])
        self.assertEqual(out.get("municipio"), "Vitória")


class ServerDispatchAndHardeningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from radar.server import create_server

        cls._tmp = tempfile.TemporaryDirectory()
        cls.db = str(Path(cls._tmp.name) / "radar.sqlite3")
        migrate_document_schema(cls.db)
        cls.server = create_server(cls.db, port=0)
        cls.port = cls.server.server_address[1]
        cls._thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def _request(self, method: str, path: str, *, headers=None, body: bytes | None = None):
        import http.client

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def test_tabela_get_dispatch_aponta_apenas_para_metodos_existentes_e_mantem_contrato(self):
        from radar import api_contract
        from radar.server import _RadarRequestHandler

        dispatch = _RadarRequestHandler._GET_DISPATCH
        self.assertGreaterEqual(len(dispatch), 65)
        for route, handler_name in dispatch.items():
            self.assertTrue(route.startswith("/api/"), route)
            self.assertTrue(hasattr(_RadarRequestHandler, handler_name), (route, handler_name))
            self.assertTrue(callable(getattr(_RadarRequestHandler, handler_name)))

        root = Path(__file__).resolve().parent.parent
        contract = api_contract.verify(str(root / "radar" / "server.py"))
        self.assertTrue(contract["ok"], contract)

    def test_despacho_get_atende_todos_os_dominios_principais(self):
        paths = [
            "/api/concursos",
            "/api/saude",
            "/api/pipeline",
            "/api/revisao/pilotos",
            "/api/carteira?limit=5",
            "/api/elegibilidade?limit=5",
            "/api/prazos?limit=5",
            "/api/estudos/painel",
            "/api/fontes",
        ]
        for path in paths:
            status, headers, raw = self._request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("application/json", headers.get("Content-Type", ""), path)
            self.assertEqual(headers.get("Cache-Control"), "no-store", path)
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff", path)
            json.loads(raw.decode("utf-8"))

    def test_bloqueia_dns_rebinding_por_host_header(self):
        for bad_host in ("evil.example.com", f"evil.example.com:{self.port}", "127.0.0.1:9999"):
            status, _, raw = self._request("GET", "/api/concursos", headers={"Host": bad_host})
            self.assertEqual(status, 403, bad_host)
            self.assertIn("host nao autorizado", raw.decode("utf-8"))

    def test_bloqueia_csrf_por_origin_externa_e_content_type_nao_json(self):
        payload = b'{"nome":"Direito Constitucional"}'
        status, _, raw = self._request(
            "POST",
            "/api/estudos/disciplinas",
            headers={
                "Origin": "https://attacker.example",
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            },
            body=payload,
        )
        self.assertEqual(status, 403)
        self.assertIn("origem nao autorizada", raw.decode("utf-8"))

        status_ct, _, raw_ct = self._request(
            "POST",
            "/api/estudos/disciplinas",
            headers={
                "Origin": f"http://127.0.0.1:{self.port}",
                "Content-Type": "text/plain",
                "Content-Length": str(len(payload)),
            },
            body=payload,
        )
        self.assertEqual(status_ct, 415)
        self.assertIn("Content-Type deve ser application/json", raw_ct.decode("utf-8"))

    def test_bloqueia_corpo_acima_do_limite_e_path_traversal(self):
        huge = b'{"nome":"' + (b"A" * 10000) + b'"}'
        status, _, raw = self._request(
            "POST",
            "/api/estudos/disciplinas",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(huge)),
            },
            body=huge,
        )
        self.assertEqual(status, 400)
        self.assertIn("grande demais", raw.decode("utf-8"))

        for traversal in (
            "/../../radar/server.py",
            "/assets/../../radar/server.py",
            "/..%2f..%2fREADME.md",
        ):
            st, _, body = self._request("GET", traversal)
            self.assertNotIn(b"class _RadarRequestHandler", body, traversal)
            self.assertIn(st, (200, 404), traversal)


if __name__ == "__main__":
    unittest.main()
