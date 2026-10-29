"""Testes de contrato/integração do fluxo vertical mínimo (Task 4 — QA).

QA independente: cruza collector -> storage -> server -> HTTP real, usando a
fixture oficial e banco temporário. Cada teste verifica o contrato v1 de
ponta a ponta, sem duplicar lógica de produção:

- fixture oficial -> ``collect`` -> ``upsert_records`` -> ``create_server``
  -> ``GET /api/concursos``: quatro registros, contrato exato, JSON válido,
  fonte/evidência oficiais e ``None`` preservado como JSON ``null``;
- idempotência e atualização por chave natural ``(source_url,
  competition_id, role)`` observadas pela API;
- zero distinto de desconhecido e local de prova distinto de exercício,
  com HTML sintético mínimo válido, observados pela API;
- HTML incompleto falha em ``collect`` antes de qualquer persistência;
  fluxo real do CLI (``_cmd_collect``) com fetch falhando ou retornando
  HTML quebrado não grava nem apaga dados existentes;
- ``GET /api/concursos`` com ``application/json``; a raiz serve o app;
  desconhecidos/traversal 404; métodos de escrita 405.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from radar import __main__ as radar_main
from radar.collector import collect
from radar.server import create_server
from radar.storage import list_records, upsert_records

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "guajara-oficial.html"

VERIFIED_AT = "2026-10-09T12:00:00-04:00"
VERIFIED_AT_LATER = "2026-10-10T09:00:00+00:00"

# Campos exatos do contrato v1, na ordem da spec.
CONTRACT_FIELDS = [
    "competition_id",
    "competition",
    "agency",
    "role",
    "education",
    "immediate_vacancies",
    "reserve_vacancies",
    "indigenous_vacancies",
    "registration_start",
    "registration_end",
    "registration_status",
    "exam_date",
    "exam_location",
    "work_location",
    "source_name",
    "source_url",
    "evidence_url",
    "verified_at",
]

OFFICIAL_SOURCE_URL = (
    "https://guajaramirim.ro.gov.br/"
    "prefeitura-de-guajara-mirim-abre-inscricoes-para-concurso-publico-"
    "da-educacao-com-107-vagas-e-cadastro-de-reserva/"
)

EXPECTED_OFFICIAL_ROLES = {
    ("Professor de Educação Infantil", 69),
    ("Professor dos Anos Iniciais do Ensino Fundamental", 32),
    ("Professor Intérprete de Libras", 3),
    ("Professor de Braille", 3),
}

# Variante sintética mínima (não corresponde à fonte real): declara zero
# explícito de vagas imediatas e de cadastro de reserva, omite cota
# indígena e informa local de prova distinto do de exercício.
SYNTHETIC_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Prefeitura de Exemplo abre inscrições para concurso da educação com 6 vagas</title>
</head>
<body>
<article>
  <h1>Prefeitura de Exemplo abre inscrições para concurso da educação com 6 vagas</h1>
  <p>A Prefeitura de Exemplo publicou o concurso público nº 003/2026 para cargos da educação.</p>
  <p>As inscrições foram realizadas de 05 a 20/08/2026.</p>
  <h2>Cargos e vagas</h2>
  <ul>
    <li><strong>4</strong> para Professor de Alfabetização;</li>
    <li><strong>2</strong> para Professor Intérprete de Libras;</li>
    <li><strong>0</strong> para Professor de Braille.</li>
  </ul>
  <p>Não haverá cadastro de reserva: 0 vagas.</p>
  <p>Local de prova: Cidade Alta/UF.</p>
  <p>Local de exercício: Cidade Baixa/UF.</p>
</article>
</body>
</html>
"""


def _load_official_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def _broken_official_html() -> str:
    """Fixture oficial com um cargo removido (soma 104 != 107 do título)."""
    html = _load_official_fixture()
    broken = html.replace(
        "    <li><strong>3</strong> para Professor de Braille.</li>\n", ""
    )
    assert broken != html, "fixture não pôde ser quebrada como esperado"
    return broken


class ServerTestCase(unittest.TestCase):
    """Base: banco temporário + servidor real em porta efêmera."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "radar.db")
        self.server = create_server(self.db_path, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self._tmp.cleanup()

    def request(self, method, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path)
            response = conn.getresponse()
            status = response.status
            headers = {k.lower(): v for k, v in response.getheaders()}
            body = response.read()
            return status, headers, body
        finally:
            conn.close()

    def persist_official_fixture(self, verified_at=VERIFIED_AT):
        records = collect(_load_official_fixture(), verified_at)
        upsert_records(self.db_path, records)
        return records


class OfficialFixtureEndToEndTest(ServerTestCase):
    """Fixture oficial -> collect -> upsert -> API, contrato v1 completo."""

    def test_api_returns_four_records_with_exact_contract(self):
        self.persist_official_fixture()
        status, headers, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body.decode("utf-8"))
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 4)
        for record in data:
            self.assertEqual(list(record.keys()), CONTRACT_FIELDS)
        observed = {(r["role"], r["immediate_vacancies"]) for r in data}
        self.assertEqual(observed, EXPECTED_OFFICIAL_ROLES)

    def test_none_fields_survive_as_json_null(self):
        self.persist_official_fixture()
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        raw = body.decode("utf-8")
        # Desconhecido permanece null no JSON cru, não vira 0 nem "".
        self.assertIn('"reserve_vacancies": null', raw)
        self.assertIn('"indigenous_vacancies": null', raw)
        self.assertIn('"education": null', raw)
        self.assertIn('"exam_location": null', raw)
        self.assertIn('"work_location": null', raw)
        data = json.loads(raw)
        for record in data:
            self.assertIsNone(record["reserve_vacancies"])
            self.assertIsNone(record["indigenous_vacancies"])
            self.assertIsNone(record["education"])
            self.assertIsNone(record["exam_date"])
            self.assertIsNone(record["exam_location"])
            self.assertIsNone(record["work_location"])

    def test_official_source_evidence_and_verification_flow(self):
        self.persist_official_fixture()
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        for record in data:
            self.assertEqual(record["source_url"], OFFICIAL_SOURCE_URL)
            self.assertEqual(record["evidence_url"], OFFICIAL_SOURCE_URL)
            self.assertEqual(
                record["source_name"], "Prefeitura Municipal de Guajará-Mirim/RO"
            )
            self.assertEqual(record["verified_at"], VERIFIED_AT)
            self.assertEqual(record["competition_id"], "001/2026")

    def test_known_dates_and_status_flow_through_api(self):
        self.persist_official_fixture()
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        for record in data:
            self.assertEqual(record["registration_start"], "2026-07-10")
            self.assertEqual(record["registration_end"], "2026-07-30")
            self.assertEqual(
                record["registration_status"], "encerradas conforme período divulgado"
            )


class IdempotencyEndToEndTest(ServerTestCase):
    """Repetição da coleta não duplica; atualização preserva a chave."""

    def test_second_persist_of_same_result_does_not_duplicate(self):
        self.persist_official_fixture()
        self.persist_official_fixture()
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data), 4)
        keys = [(r["source_url"], r["competition_id"], r["role"]) for r in data]
        self.assertEqual(len(set(keys)), 4)

    def test_same_key_with_new_verified_at_updates_in_place(self):
        self.persist_official_fixture(VERIFIED_AT)
        self.persist_official_fixture(VERIFIED_AT_LATER)
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data), 4)
        for record in data:
            self.assertEqual(record["verified_at"], VERIFIED_AT_LATER)
            self.assertNotEqual(record["verified_at"], VERIFIED_AT)


class ZeroVsUnknownAndLocationsEndToEndTest(ServerTestCase):
    """Zero afirmado permanece 0; ausência permanece null; locais separados."""

    def persist_synthetic(self, verified_at=VERIFIED_AT):
        records = collect(SYNTHETIC_HTML, verified_at)
        upsert_records(self.db_path, records)
        return records

    def test_explicit_zero_stays_zero_and_absent_stays_null_through_api(self):
        self.persist_synthetic()
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        raw = body.decode("utf-8")
        self.assertIn('"immediate_vacancies": 0', raw)
        self.assertIn('"reserve_vacancies": 0', raw)
        self.assertIn('"indigenous_vacancies": null', raw)
        data = json.loads(raw)
        by_role = {r["role"]: r for r in data}
        braille = by_role["Professor de Braille"]
        self.assertEqual(braille["immediate_vacancies"], 0)
        for record in data:
            self.assertEqual(record["reserve_vacancies"], 0)
            self.assertIsNone(record["indigenous_vacancies"])
            self.assertIsNotNone(record["immediate_vacancies"])

    def test_exam_and_work_locations_stay_separate_through_api(self):
        self.persist_synthetic()
        status, _, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        for record in data:
            self.assertEqual(record["exam_location"], "Cidade Alta/UF")
            self.assertEqual(record["work_location"], "Cidade Baixa/UF")
            self.assertNotEqual(record["exam_location"], record["work_location"])


class IncompleteHtmlDoesNotPersistTest(unittest.TestCase):
    """HTML incompleto falha em collect antes de qualquer persistência."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "radar.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_collect_rejects_incomplete_document(self):
        with self.assertRaises(ValueError):
            collect(_broken_official_html(), VERIFIED_AT)

    def test_incomplete_html_via_cli_flow_keeps_previous_data_intact(self):
        baseline = collect(_load_official_fixture(), VERIFIED_AT)
        upsert_records(self.db_path, baseline)
        before = list_records(self.db_path)
        self.assertEqual(len(before), 4)

        args = argparse.Namespace(db=self.db_path)
        with mock.patch.object(
            radar_main,
            "fetch_official",
            return_value=_broken_official_html(),
        ):
            with self.assertRaises(ValueError):
                radar_main._cmd_collect(args)

        after = list_records(self.db_path)
        self.assertEqual(after, before)
        self.assertEqual(len(after), 4)
        for record in after:
            self.assertEqual(record["verified_at"], VERIFIED_AT)

    def test_changed_role_name_does_not_mix_old_and_new_records(self):
        baseline = collect(_load_official_fixture(), VERIFIED_AT)
        upsert_records(self.db_path, baseline)
        before = list_records(self.db_path)
        renamed = _load_official_fixture().replace(
            "Professor de Braille.", "Professor Especialista em Braille."
        )
        self.assertEqual(len(collect(renamed, VERIFIED_AT_LATER)), 4)
        with mock.patch.object(radar_main, "fetch_official", return_value=renamed):
            with self.assertRaisesRegex(ValueError, "cargos da fonte alterados"):
                radar_main._cmd_collect(argparse.Namespace(db=self.db_path))
        self.assertEqual(list_records(self.db_path), before)


class FetchFailureFlowTest(unittest.TestCase):
    """Falha de fetch propaga e não grava nem apaga dados existentes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "radar.db")

    def tearDown(self):
        self._tmp.cleanup()

    def test_network_failure_does_not_create_database(self):
        missing = str(Path(self._tmp.name) / "nao-criado.db")
        args = argparse.Namespace(db=missing)
        with mock.patch.object(
            radar_main, "fetch_official", side_effect=URLError("offline")
        ):
            with self.assertRaises(URLError):
                radar_main._cmd_collect(args)
        self.assertFalse(Path(missing).exists())
        self.assertEqual(list_records(missing), [])

    def test_network_failure_preserves_existing_data(self):
        baseline = collect(_load_official_fixture(), VERIFIED_AT)
        upsert_records(self.db_path, baseline)
        before = list_records(self.db_path)
        self.assertEqual(len(before), 4)

        args = argparse.Namespace(db=self.db_path)
        with mock.patch.object(
            radar_main, "fetch_official", side_effect=URLError("offline")
        ):
            with self.assertRaises(URLError):
                radar_main._cmd_collect(args)

        after = list_records(self.db_path)
        self.assertEqual(after, before)
        for record in after:
            self.assertEqual(record["verified_at"], VERIFIED_AT)

    def test_main_collect_propagates_failure(self):
        missing = str(Path(self._tmp.name) / "tampouco.db")
        with mock.patch.object(
            radar_main, "fetch_official", side_effect=URLError("offline")
        ):
            with self.assertRaises(URLError):
                radar_main.main(["collect", "--db", missing])
        self.assertFalse(Path(missing).exists())


class ApiAndStaticPathsEndToEndTest(ServerTestCase):
    """Contratos HTTP da API e dos caminhos estáticos, com dados reais."""

    def test_static_paths_are_served(self):
        self.persist_official_fixture()
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200, "a raiz deve servir o app")
        self.assertIn("GSN Concursos", body.decode("utf-8"))

    def test_unknown_path_serves_spa_and_missing_asset_404(self):
        # SPA: rota sem extensão devolve o index; asset inexistente continua 404.
        status, _, body = self.request("GET", "/rota-inexistente")
        self.assertEqual(status, 200)
        self.assertIn(b'<div id="root">', body)
        status, _, _ = self.request("GET", "/rota-inexistente.js")
        self.assertEqual(status, 404)


    def test_path_traversal_returns_404(self):
        for path in (
            "/../radar/collector.py",
            "/assets/../../radar/server.py",
            "/..%2fradar%2fserver.py",
        ):
            status, _, body = self.request("GET", path)
            self.assertEqual(status, 404, "path %r deve ser bloqueado" % path)
            self.assertNotIn(b"def ", body)

    def test_write_methods_on_api_return_405(self):
        self.persist_official_fixture()
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, headers, _ = self.request(method, "/api/concursos")
            self.assertEqual(status, 405, "método %s deve ser 405" % method)
            self.assertIn("GET", headers.get("allow", ""))

    def test_api_content_type_is_json_with_contract_fields(self):
        self.persist_official_fixture()
        status, headers, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data), 4)
        for record in data:
            self.assertEqual(list(record.keys()), CONTRACT_FIELDS)


if __name__ == "__main__":
    unittest.main()
