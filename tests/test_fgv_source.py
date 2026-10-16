"""Terceira fonte (FGV Conhecimento): catálogo, detalhe, documentos e idempotência."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import fgv_source as fgv
from radar.document_store import connect_documents, migrate_document_schema
from radar.monitoring import run_cycle
from radar.storage import list_records

_TS = "2026-10-16T12:00:00+00:00"


def catalog_html(entries):
    rows = "".join(
        f'<div class="views-row"><div class="views-field views-field-title">'
        f'<span class="field-content"><a href="/concursos/{slug}" hreflang="pt-br">{title}</a>'
        f'</span></div></div>'
        for slug, title in entries)
    return f"<html><body><div class='view-content'>{rows}</div></body></html>"


def detail_html(title, status, docs):
    # docs: lista de (data_iso, rótulo, url)
    items = "".join(
        f'<div class="field__item"><div class="paragraph paragraph--type--texto-data paragraph--view-mode--default">'
        f'<div class="field field--name-field-td-data"><div class="field__item">'
        f'<time datetime="{date}T12:00:00Z" class="datetime">{date}</time></div></div>'
        f'<div class="field field--name-field-td-texto"><div class="field__item">'
        f'<p><a href="{url}">{label}</a></p></div></div></div></div>'
        for date, label, url in docs)
    return (f"<html><head><title>{title} | FGV Conhecimento</title></head><body>"
            f'<h1 class="page-title">{title}</h1>'
            f'<div class="field field--name-field-concurso-status"><small class="field__item">{status}</small></div>'
            f'<div class="field field--name-field-concurso-arquivos">'
            f'<h3 class="field__label">Arquivos do concurso</h3>{items}</div>'
            f'</body></html>')


class CatalogParseTest(unittest.TestCase):
    def test_parses_entries(self):
        entries = fgv.parse_catalog(catalog_html([("tjap26", "Concurso TJAP"), ("pms2026", "Concurso PMS")]))
        self.assertEqual([e["slug"] for e in entries], ["tjap26", "pms2026"])
        self.assertEqual(entries[0]["url"], "https://conhecimento.fgv.br/concursos/tjap26")
        self.assertEqual(entries[0]["title"], "Concurso TJAP")

    def test_deduplicates_and_ignores_non_concurso_links(self):
        html = (catalog_html([("tjap26", "A")])
                + '<a href="/reshuem26">Processo Seletivo</a>'
                + '<a href="/concursos/tjap26">A repetido</a>')
        entries = fgv.parse_catalog(html)
        self.assertEqual([e["slug"] for e in entries], ["tjap26"])

    def test_empty_catalog_raises(self):
        with self.assertRaises(ValueError):
            fgv.parse_catalog("")

    def test_catalog_url_and_detail_url(self):
        self.assertEqual(fgv.catalog_url(0), "https://conhecimento.fgv.br/concursos")
        self.assertEqual(fgv.catalog_url(2), "https://conhecimento.fgv.br/concursos?page=2")
        self.assertEqual(fgv.detail_url("tjap26"), "https://conhecimento.fgv.br/concursos/tjap26")
        with self.assertRaises(ValueError):
            fgv.detail_url("http://evil/x")


class DetailParseTest(unittest.TestCase):
    def test_parses_title_status_and_documents(self):
        html = detail_html("Concurso PMS Guarda", "Em Andamento", [
            ("2026-09-18", "Edital de Abertura", "https://conhecimento.fgv.br/sites/default/files/concursos/edital.pdf"),
            ("2026-09-28", "1ª Retificação", "https://conhecimento.fgv.br/sites/default/files/concursos/ret.pdf"),
            ("2026-10-13", "Resultado preliminar", "/sites/default/files/concursos/res.pdf"),
        ])
        detail = fgv.parse_detail(html)
        self.assertEqual(detail["title"], "Concurso PMS Guarda")
        self.assertEqual(detail["status"], "Em Andamento")
        self.assertEqual(len(detail["documents"]), 3)
        self.assertEqual(detail["documents"][0]["date"], "2026-09-18")

    def test_ignores_non_document_links(self):
        html = detail_html("X", "Em Andamento", [])
        html = html.replace("</body>", '<div class="paragraph paragraph--type--texto-data">'
                            '<div class="field__item"><p><a href="https://conhecimento.fgv.br/pagina">Página</a></p>'
                            '</div></div></body>')
        detail = fgv.parse_detail(html)
        self.assertEqual(detail["documents"], [])

    def test_classify_document(self):
        self.assertEqual(fgv.classify_document("Edital de Abertura"), "edital")
        self.assertEqual(fgv.classify_document("1ª Retificação do edital"), "retificacao")
        self.assertEqual(fgv.classify_document("Retificação do Edital nº 2"), "retificacao")
        # Um edital apenas "retificado" continua sendo edital.
        self.assertEqual(fgv.classify_document("Edital (retificado em 28/09/2026)"), "edital")
        self.assertEqual(fgv.classify_document("Resultado final"), "outro")
        self.assertEqual(fgv.classify_document("Comunicado"), "outro")


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        self.catalog = catalog_html([("tjap26", "Concurso TJAP"), ("pms2026", "Concurso PMS")])
        self.details = {
            "tjap26": detail_html("Concurso TJAP", "Em Andamento", [
                ("2026-10-05", "Edital", "https://conhecimento.fgv.br/sites/default/files/concursos/tjap.pdf"),
                ("2026-10-13", "Retificação", "https://conhecimento.fgv.br/sites/default/files/concursos/tjap-ret.pdf"),
            ]),
            "pms2026": detail_html("Concurso PMS", "Em Andamento", [
                ("2026-09-18", "Edital", "https://conhecimento.fgv.br/sites/default/files/concursos/pms.pdf"),
            ]),
        }

    def _discover(self, **kw):
        return fgv.discover(self.db, self.catalog,
                            catalog_fetcher=lambda p: "",
                            detail_fetcher=lambda slug: self.details[slug],
                            max_pages=1, discovered_at=_TS, **kw)

    def _register(self, candidates):
        from radar.document_store import register_document
        for candidate in candidates:
            register_document(self.db, candidate)

    def test_discovers_new_concursos_with_per_contest_identity(self):
        candidates = self._discover(max_new_details=5)
        # 2 páginas (uma por concurso) + 2 do TJAP + 1 da PMS
        self.assertEqual(len(candidates), 5)
        pages = [c for c in candidates if c["source_identifier"].endswith(":pagina")]
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(c["kind"] == "outro" for c in pages))
        with closing(connect_documents(self.db)) as conn:
            obs = conn.execute("SELECT competition_id FROM observacoes_concurso ORDER BY competition_id").fetchall()
        self.assertEqual([o[0] for o in obs], ["pms2026", "tjap26"])  # identidade por concurso
        kinds = sorted(c["kind"] for c in candidates if not c["source_identifier"].endswith(":pagina"))
        self.assertEqual(kinds, ["edital", "edital", "retificacao"])

    def test_second_run_is_idempotent_after_registration(self):
        # Simula o ciclo: descobre e registra; a segunda descoberta não reemite.
        self._register(self._discover(max_new_details=5))
        again = self._discover(max_new_details=5)
        self.assertEqual(again, [])

    def test_detail_without_documents_does_not_block_next_concurso(self):
        # Regressão: um concurso sem documentos (mas consultado) não pode estancar
        # a descoberta nem ser reconsultado.
        self.details["tjap26"] = detail_html("Concurso TJAP", "Em Andamento", [])
        candidates = self._discover(max_new_details=1)
        # tjap26 consultado (só a página); pms2026 não entra no orçamento deste ciclo.
        self.assertEqual([c["source_identifier"] for c in candidates], ["tjap26:pagina"])
        self._register(candidates)
        # tjap26 agora tem a página registrada → não é reconsultado; pms2026 é novo.
        again = self._discover(max_new_details=1)
        self.assertEqual([c["source_identifier"] for c in again if c["source_identifier"].endswith(":pagina")],
                         ["pms2026:pagina"])

    def test_max_new_details_limits_detail_fetch(self):
        candidates = self._discover(max_new_details=1)
        # Apenas o primeiro concurso (tjap26) tem detalhe consultado: página + 2 docs.
        self.assertEqual(len(candidates), 3)
        self.assertTrue(all("tjap26" in c["source_identifier"] for c in candidates))

    def test_empty_first_page_raises(self):
        with self.assertRaises(ValueError):
            fgv.discover(self.db, "<html><body>sem concursos</body></html>",
                         catalog_fetcher=lambda p: "", max_pages=1, discovered_at=_TS)

    def test_detail_fetch_failure_does_not_raise(self):
        def boom(slug):
            raise TimeoutError("caiu")
        candidates = fgv.discover(self.db, self.catalog, catalog_fetcher=lambda p: "",
                                  detail_fetcher=boom, max_pages=1, discovered_at=_TS)
        self.assertEqual(candidates, [])


class FgvCycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        self.catalog = catalog_html([("tjap26", "Concurso TJAP")])
        self.detail = detail_html("Concurso TJAP", "Em Andamento", [
            ("2026-10-05", "Edital", "https://conhecimento.fgv.br/sites/default/files/concursos/tjap.pdf"),
            ("2026-10-13", "Retificação", "https://conhecimento.fgv.br/sites/default/files/concursos/tjap-ret.pdf"),
        ])

    def _source(self):
        return fgv.fgv_source(
            catalog_fetcher=lambda p: self.catalog if p == 0 else "",
            detail_fetcher=lambda slug: self.detail,
            max_pages=1, max_new_details=5)

    def _transport(self):
        def transport(url, timeout, limit):
            return dict(status=200, final_url=url, content_type="application/pdf",
                        peer_ip="8.8.8.8", body=b"%PDF-1.4\nconteudo")
        return transport

    def test_cycle_registers_documents_downloads_once_and_keeps_v1(self):
        first = run_cycle(self.db, sources=[self._source()], transport=self._transport())
        self.assertEqual(first["state"], "concluido")
        self.assertEqual(first["documents_new"], 3)  # página + edital + retificação
        self.assertEqual(first["versions_new"], 3)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM documentos").fetchone()[0], 3)
            self.assertEqual(conn.execute("SELECT count(*) FROM concursos_identidade").fetchone()[0], 1)
            kinds = sorted(r[0] for r in conn.execute("SELECT kind FROM documentos"))
        self.assertEqual(kinds, ["edital", "outro", "retificacao"])
        # v1 intacto
        self.assertEqual(list_records(self.db), [])
        # Segunda execução: nada novo, sem baixar de novo.
        calls = []

        def counting(url, timeout, limit):
            calls.append(url)
            return dict(status=200, final_url=url, content_type="application/pdf",
                        peer_ip="8.8.8.8", body=b"%PDF-1.4\nconteudo")

        second = run_cycle(self.db, sources=[self._source()], transport=counting)
        self.assertEqual(second["documents_new"], 0)
        self.assertEqual(second["versions_new"], 0)
        self.assertEqual(calls, [])

    def test_failure_preserves_and_reports(self):
        def boom():
            raise TimeoutError("fgv fora do ar")
        source = self._source()
        source["fetch"] = boom
        result = run_cycle(self.db, sources=[source])
        self.assertEqual(result["state"], "falhou")
        self.assertEqual(result["sources"][0]["state"], "falhou")


class NetworkSafetyTest(unittest.TestCase):
    def test_fgv_hosts_authorized_restrictively(self):
        from radar.document_discovery import allowed_document_url
        self.assertTrue(allowed_document_url("https://conhecimento.fgv.br/concursos/tjap26"))
        self.assertTrue(allowed_document_url(
            "https://conhecimento.fgv.br/sites/default/files/concursos/tjap.pdf"))
        self.assertFalse(allowed_document_url("https://conhecimento.fgv.br/user/login"))
        self.assertFalse(allowed_document_url("https://evil.example/concursos/x"))
        self.assertFalse(allowed_document_url("http://conhecimento.fgv.br/concursos/x"))


if __name__ == "__main__":
    unittest.main()
