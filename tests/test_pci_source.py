"""PCI Concursos (MCP): cliente, parsing, descoberta, dedup, parcial e ciclo."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import pci_source as pci
from radar.document_store import connect_documents, migrate_document_schema, register_document
from radar.monitoring import run_cycle
from radar.storage import list_records

_TS = "2026-10-16T12:00:00+00:00"


def concurso(pid, titulo, uf="SP", link=None, inicio="2026-09-21", fim="2026-11-09", **extra):
    item = {
        "id": pid, "titulo": titulo, "cargos_resumo": "Vários Cargos", "cargos": ["CARGO A"],
        "vagas_salario": "7 vagas até R$ 8.595,15", "formacao": "Superior",
        "regiao": "SUDESTE", "uf": uf,
        "datas": {"inicio": inicio, "fim": fim, "texto": "", "aberto": True, "dias_restantes": 24},
        "noticia": {"id": pid, "titulo": f"{titulo} abre concurso",
                    "link": link or f"https://www.pciconcursos.com.br/noticias/{pid}"},
        "apostila": None,
    }
    item.update(extra)
    return item


def tool_payload(data, is_error=False, text=None):
    if text is not None:
        body = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        body = {"content": [{"type": "text", "text": json.dumps({"meta": {"total": len(data)}, "data": data},
                                                                ensure_ascii=False)}], "isError": is_error}
    return {"jsonrpc": "2.0", "id": 1, "result": body}


class FakeResponse:
    def __init__(self, body):
        self._body = body
    def read(self, n=-1):
        return self._body[:n] if n and n > 0 else self._body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class McpClientTest(unittest.TestCase):
    def _client(self, responses):
        calls = []
        def opener(request, timeout):
            calls.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse(json.dumps(responses.pop(0)).encode("utf-8"))
        return pci.McpClient(opener=opener), calls

    def test_initialize_and_list_tools(self):
        client, calls = self._client([
            {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": pci.PCI_PROTOCOL_VERSION,
             "serverInfo": {"name": "x"}}},
            {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "listar_concursos"}]}},
        ])
        self.assertEqual(client.initialize()["result"]["protocolVersion"], pci.PCI_PROTOCOL_VERSION)
        tools = client.list_tools()
        self.assertEqual([t["name"] for t in tools], ["listar_concursos"])
        self.assertEqual(calls[0]["method"], "initialize")
        self.assertEqual(calls[1]["method"], "tools/list")

    def test_call_uses_tool_name_and_arguments(self):
        client, calls = self._client([tool_payload([concurso(1, "X")])])
        payload = client.call("buscar_por_cargo", {"cargo": "analista"})
        self.assertEqual(calls[0]["method"], "tools/call")
        self.assertEqual(calls[0]["params"], {"name": "buscar_por_cargo", "arguments": {"cargo": "analista"}})
        self.assertIn("result", payload)

    def test_connection_failure_raises_protocol_error(self):
        def opener(request, timeout):
            raise TimeoutError("sem rede")
        client = pci.McpClient(opener=opener)
        with self.assertRaises(pci.PciProtocolError):
            client.list_tools()

    def test_non_json_response_raises_protocol_error(self):
        client = pci.McpClient(opener=lambda r, timeout: FakeResponse(b"<html>nao json</html>"))
        with self.assertRaises(pci.PciProtocolError):
            client.list_tools()

    def test_sse_response_is_parsed(self):
        sse = b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n'
        client = pci.McpClient(opener=lambda r, timeout: FakeResponse(sse))
        self.assertEqual(client.list_tools(), [])


class ParseResultTest(unittest.TestCase):
    def test_structured_json(self):
        is_error, obj, text, reason = pci.parse_tool_result(tool_payload([concurso(1, "X")]))
        self.assertFalse(is_error)
        self.assertIsNone(reason)
        self.assertEqual(len(obj["data"]), 1)

    def test_tool_error_flag(self):
        is_error, obj, text, reason = pci.parse_tool_result(tool_payload([], is_error=True))
        self.assertTrue(is_error)
        self.assertEqual(reason, "tool_error")
        self.assertIsNone(obj)

    def test_unreadable_text_is_error_not_connection(self):
        is_error, obj, text, reason = pci.parse_tool_result(tool_payload([], text="Desculpe, não entendi."))
        self.assertTrue(is_error)
        self.assertEqual(reason, "unreadable")
        self.assertIsNone(obj)

    def test_jsonrpc_error(self):
        is_error, obj, text, reason = pci.parse_tool_result({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601}})
        self.assertTrue(is_error)
        self.assertEqual(reason, "rpc_error")

    def test_empty_valid_result(self):
        is_error, obj, text, reason = pci.parse_tool_result(tool_payload([]))
        self.assertFalse(is_error)
        self.assertEqual(obj["data"], [])


class NormalizeTest(unittest.TestCase):
    def test_valid(self):
        cand = pci.normalize(concurso(295181, "Câmara de Boituva"), "q", _TS)
        self.assertEqual(cand["competition_id"], "pci-295181")
        self.assertEqual(cand["uf"], "SP")
        self.assertEqual(cand["data_inicio"], "2026-09-21")
        self.assertTrue(cand["url"].startswith("https://www.pciconcursos.com.br/"))

    def test_missing_id_or_link_is_dropped(self):
        self.assertIsNone(pci.normalize({"titulo": "X", "noticia": {"link": "https://x"}}, "q", _TS))
        self.assertIsNone(pci.normalize(concurso(1, "X", link="http://inseguro"), "q", _TS))
        no_title = concurso(1, "")
        no_title["noticia"]["titulo"] = ""
        self.assertIsNone(pci.normalize(no_title, "q", _TS))

    def test_unknown_fields_stay_none(self):
        item = concurso(1, "X")
        item.pop("formacao")
        item["uf"] = None
        cand = pci.normalize(item, "q", _TS)
        self.assertIsNone(cand["formacao"])
        self.assertIsNone(cand["uf"])


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)

    def _caller(self, results):
        def caller(tool, args):
            if tool in results:
                return tool_payload(results[tool])
            return tool_payload([])
        return caller

    def _queries(self):
        return (("listar_concursos", {}), ("buscar_por_cargo", {"cargo": "analista de sistemas"}))

    def test_discovers_new_and_dedups_by_id(self):
        results = {"listar_concursos": [concurso(1, "A"), concurso(2, "B")],
                   "buscar_por_cargo": [concurso(2, "B"), concurso(3, "C")]}
        out = pci.discover(self.db, caller=self._caller(results), queries=self._queries(), now=lambda: _TS)
        self.assertEqual(len(out["candidates"]), 3)  # 1,2,3 (2 deduplicado)
        self.assertFalse(out["partial"])
        self.assertEqual(out["summary"]["results_observed"], 4)
        self.assertEqual(out["summary"]["unique_concursos"], 3)
        # documento de descoberta com proveniência
        doc = out["candidates"][0]
        self.assertEqual(doc["kind"], "outro")
        self.assertEqual(doc["issuer"], pci.PCI_AGENCY)
        self.assertIn(b"Descoberta pelo PCI", doc["inline_content"])

    def test_idempotent_after_registration(self):
        results = {"listar_concursos": [concurso(1, "A")]}
        out = pci.discover(self.db, caller=self._caller(results), queries=self._queries(), now=lambda: _TS)
        for cand in out["candidates"]:
            register_document(self.db, cand)
        again = pci.discover(self.db, caller=self._caller(results), queries=self._queries(), now=lambda: _TS)
        self.assertEqual(again["candidates"], [])

    def test_slug_change_does_not_duplicate(self):
        # Dedup por identidade estável (pci-<id>), mesmo se o slug da notícia mudar.
        first = {"listar_concursos": [concurso(1, "A", link="https://www.pciconcursos.com.br/noticias/a-antigo")]}
        out = pci.discover(self.db, caller=self._caller(first), queries=self._queries(), now=lambda: _TS)
        for cand in out["candidates"]:
            register_document(self.db, cand)
        changed = {"listar_concursos": [concurso(1, "A", link="https://www.pciconcursos.com.br/noticias/a-novo")]}
        again = pci.discover(self.db, caller=self._caller(changed), queries=self._queries(), now=lambda: _TS)
        self.assertEqual(again["candidates"], [])

    def test_partial_when_one_query_fails(self):
        def caller(tool, args):
            if tool == "listar_concursos":
                raise pci.PciProtocolError("timeout")
            return tool_payload([concurso(1, "A")])
        out = pci.discover(self.db, caller=caller, queries=self._queries(), now=lambda: _TS)
        self.assertTrue(out["partial"])
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(out["summary"]["queries_ok"], 1)
        self.assertTrue(out["summary"]["errors"])

    def test_all_queries_failing_is_not_partial_but_no_success(self):
        def caller(tool, args):
            raise pci.PciProtocolError("down")
        out = pci.discover(self.db, caller=caller, queries=self._queries(), now=lambda: _TS)
        self.assertFalse(out["partial"])
        self.assertTrue(out["failed"])
        self.assertEqual(out["summary"]["queries_ok"], 0)
        self.assertEqual(out["candidates"], [])

    def test_empty_valid_result_is_not_error(self):
        out = pci.discover(self.db, caller=self._caller({}), queries=self._queries(), now=lambda: _TS)
        self.assertFalse(out["partial"])
        self.assertEqual(out["summary"]["errors"], [])

    def test_max_new_concursos_bounds_and_is_incremental(self):
        results = {"listar_concursos": [concurso(i, f"C{i}") for i in range(1, 6)]}
        first = pci.discover(self.db, caller=self._caller(results), queries=self._queries(),
                             max_new_concursos=2, now=lambda: _TS)
        self.assertEqual(len(first["candidates"]), 2)
        for cand in first["candidates"]:
            register_document(self.db, cand)
        second = pci.discover(self.db, caller=self._caller(results), queries=self._queries(),
                              max_new_concursos=2, now=lambda: _TS)
        self.assertEqual(len(second["candidates"]), 2)  # próximos 2
        ids = {c["source_identifier"] for c in first["candidates"]} | {c["source_identifier"] for c in second["candidates"]}
        self.assertEqual(len(ids), 4)  # sem repetição

    def test_overlap_hint_counts_matching_title_from_other_source(self):
        from radar.document_store import ensure_observation
        other = ensure_observation(self.db, "https://conhecimento.fgv.br/concursos/x", "x")
        register_document(self.db, {"observation_id": other, "kind": "edital",
            "official_url": "https://conhecimento.fgv.br/concursos/x", "title": "Câmara de Boituva",
            "discovery_url": "https://conhecimento.fgv.br/concursos/x", "discovery_method": "automatico",
            "discovered_at": _TS, "issuer": "FGV"})
        results = {"listar_concursos": [concurso(1, "Câmara de Boituva"), concurso(2, "Outro")]}
        out = pci.discover(self.db, caller=self._caller(results), queries=self._queries(), now=lambda: _TS)
        self.assertEqual(out["summary"]["overlap_hint"], 1)


class PciCycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)

    def _source(self, results):
        def caller(tool, args):
            if tool in results:
                return tool_payload(results[tool])
            return tool_payload([])
        client = type("C", (), {"call": staticmethod(caller), "list_tools": staticmethod(lambda: [{"name": "listar_concursos"}]), "initialize": staticmethod(lambda: {})})()
        return pci.pci_source(client=client, queries=(("listar_concursos", {}),), max_new_concursos=5)

    def test_cycle_registers_discoveries_and_keeps_v1(self):
        source = self._source({"listar_concursos": [concurso(1, "A"), concurso(2, "B")]})
        first = run_cycle(self.db, sources=[source])
        self.assertEqual(first["state"], "concluido")
        self.assertEqual(first["documents_new"], 2)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM documentos").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT count(*) FROM concursos_identidade").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT count(*) FROM propostas_campo").fetchone()[0], 0)
            has_v1 = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='concursos'").fetchone()
        self.assertFalse(has_v1)  # v1 (18 campos) não é criado nem escrito pela PCI
        self.assertEqual(list_records(self.db), [])
        second = run_cycle(self.db, sources=[source])
        self.assertEqual(second["documents_new"], 0)

    def test_cycle_partial_state_recorded(self):
        def caller(tool, args):
            if tool == "listar_concursos":
                raise pci.PciProtocolError("timeout")
            return tool_payload([concurso(1, "A")])
        client = type("C", (), {"call": staticmethod(caller), "list_tools": staticmethod(lambda: []), "initialize": staticmethod(lambda: {})})()
        source = pci.pci_source(client=client, queries=(("listar_concursos", {}),
                                                        ("buscar_por_cargo", {"cargo": "x"})))
        result = run_cycle(self.db, sources=[source])
        self.assertEqual(result["state"], "parcial")
        with closing(connect_documents(self.db)) as conn:
            summary = json.loads(conn.execute(
                "SELECT summary_json FROM ciclos_fontes").fetchone()[0])
        self.assertEqual(summary["queries_version"], pci.PCI_QUERIES_VERSION)
        self.assertEqual(summary["queries_ok"], 1)
        self.assertTrue(summary["source_errors"])

    def test_cycle_all_queries_failing_is_failure_not_success(self):
        def caller(tool, args):
            raise pci.PciProtocolError("down")
        client = type("C", (), {"call": staticmethod(caller), "list_tools": staticmethod(lambda: []), "initialize": staticmethod(lambda: {})})()
        source = pci.pci_source(client=client, queries=(("listar_concursos", {}),
                                                        ("buscar_por_cargo", {"cargo": "x"})))
        result = run_cycle(self.db, sources=[source])
        self.assertEqual(result["state"], "falhou")

    def test_cycle_failure_when_source_unreachable(self):
        def boom():
            raise pci.PciProtocolError("sem conexão")
        client = type("C", (), {"call": staticmethod(lambda t, a: tool_payload([])), "list_tools": staticmethod(boom), "initialize": staticmethod(lambda: {})})()
        source = pci.pci_source(client=client, queries=(("listar_concursos", {}),))
        result = run_cycle(self.db, sources=[source])
        self.assertEqual(result["state"], "falhou")
        self.assertEqual(result["sources"][0]["state"], "falhou")


class SafetyTest(unittest.TestCase):
    def test_endpoint_is_https_pci_host(self):
        self.assertTrue(pci.PCI_ENDPOINT.startswith("https://mcp.pciconcursos.com.br/"))

    def test_apostilas_tool_not_in_query_set(self):
        tools = {tool for tool, _ in pci.PCI_QUERIES}
        self.assertNotIn("buscar_apostilas", tools)
        self.assertTrue(tools.issubset(set(pci.PCI_CONCURSO_TOOLS)))

    def test_discovery_content_has_no_apostila_fields(self):
        cand = pci.normalize(concurso(1, "X"), "q", _TS)
        doc = pci.to_candidate(cand, "obs")
        self.assertNotIn(b"apostila", doc["inline_content"].lower())


if __name__ == "__main__":
    unittest.main()
