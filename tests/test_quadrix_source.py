"""Nova fonte oficial Quadrix: catálogo, página de certame, documentos e ciclo."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import quadrix_source as qx
from radar.document_discovery import allowed_document_url
from radar.document_store import connect_documents, migrate_document_schema
from radar.monitoring import run_cycle
from radar.storage import list_records

_TS = "2026-10-16T12:00:00+00:00"
_ANEXOS = "https://anexos-r2.selecao.net.br/uploads/861/concursos/{cid}/anexos/{name}"


def catalog_html(entries):
    items = []
    for cid, title, tipo in entries:
        items.append(
            '<li class="item"><table><tr>'
            f'<td class="col-1"><a href="/informacoes/{cid}/"><img class="logomarca-cliente"/></a></td>'
            '<td class="col-2"><div class="dados">'
            f'<p class="tipo">{tipo} </p>'
            f'<h3><a href="/informacoes/{cid}/" >{title}</a></h3>'
            '<p class="edital"><span class="editaln">Edital n&ordm;</span> 01/2026</p>'
            '<p class="inscricoes-info-mobile-only">Inscri&ccedil;&otilde;es de '
            "<b>05/10/2026</b> a <b>10/11/2026</b></p>"
            "</div></td></tr></table></li>")
    return ("<html><body><div class='listaConcursos'><ul class='lista'>"
            + "".join(items) + "</ul></div></body></html>")


def detail_html(title, documents):
    lis = []
    for label, url, date in documents:
        lis.append(
            '<li class="pdf" style="display:flex;justify-content:space-between;">'
            f'<a style="flex:1" data-astv="{label}" href="{url}" target="_blank">'
            f"{label} <span>{date}</span></a>"
            '<span style="white-space:nowrap;display:none;">'
            f'<a href="/leitor-vlibras/pdf?pdf={url}">VLibras</a></span></li>')
    return ("<html><head><title>Quadrix</title></head><body>"
            "<h1>Concursos</h1>"
            f"<h2>{title}</h2>"
            f"<ul class=\"listaDocumentos\">{''.join(lis)}</ul></body></html>")


class ParseCatalogTest(unittest.TestCase):
    def test_extracts_entries(self):
        html = catalog_html([("3049", "CRECI-ES", "Concurso P&uacute;blico"),
                             ("3056", "Sedes/DF", "Concurso P&uacute;blico")])
        entries = qx.parse_catalog(html)
        self.assertEqual([e["id"] for e in entries], ["3049", "3056"])
        self.assertEqual(entries[0]["url"], "https://www.quadrix.org.br/informacoes/3049/")
        self.assertEqual(entries[1]["title"], "Sedes/DF")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            qx.parse_catalog("")

    def test_dedupes_repeated_id(self):
        html = catalog_html([("1", "A", "x"), ("1", "A", "x")])
        self.assertEqual(len(qx.parse_catalog(html)), 1)


class ParseDetailTest(unittest.TestCase):
    def test_extracts_documents_with_type_and_date(self):
        html = detail_html("Sedes/DF", [
            ("Edital nº 1 (Abertura)", _ANEXOS.format(cid=3056, name="ed.pdf"), "09/09/2026"),
            ("Edital nº 6 (Retificação)", _ANEXOS.format(cid=3056, name="ret.pdf"), "18/09/2026"),
        ])
        detail = qx.parse_detail(html)
        self.assertEqual(detail["title"], "Sedes/DF")
        self.assertEqual(len(detail["documents"]), 2)
        first = detail["documents"][0]
        self.assertEqual(first["document_type"], "edital_abertura")
        self.assertEqual(first["kind"], "edital")
        self.assertEqual(first["date"], "09/09/2026")
        self.assertEqual(detail["documents"][1]["document_type"], "retificacao")
        self.assertEqual(detail["documents"][1]["kind"], "retificacao")

    def test_ignores_vlibras_reader_link(self):
        html = detail_html("X", [("Edital", _ANEXOS.format(cid=1, name="e.pdf"), "01/01/2026")])
        # O link /leitor-vlibras/pdf?pdf=... não é um arquivo (não termina em .pdf)
        urls = [d["url"] for d in qx.parse_detail(html)["documents"]]
        self.assertEqual(urls, [_ANEXOS.format(cid=1, name="e.pdf")])


class ClassifyTest(unittest.TestCase):
    def test_fine_types(self):
        cases = {
            "Edital nº 1 (Abertura)": "edital_abertura",
            "Edital nº 1 (Abertura) - atualizado conforme retificações": "edital_retificado",
            "Edital nº 6 (Retificação)": "retificacao",
            "1ª Retificação do edital": "retificacao",
            "Anexo I - Quadro de vagas": "anexo",
            "Cronograma - atualizado conforme retificações": "cronograma",
            "Cronograma - atualizado": "cronograma",
            "Comunicado 09/10/2026": "comunicado",
            "Resultado preliminar (prova objetiva)": "resultado",
            "Edital nº 4 (Convocação-provas)": "convocacao",
            "Homologação do resultado final": "homologacao",
            "Gabarito definitivo": "gabarito",
            "Provas aplicadas (versão padrão)": "prova",
            "Documento qualquer": "outro",
        }
        for title, expected in cases.items():
            self.assertEqual(qx.classify_document(title), expected, title)

    def test_kind_mapping(self):
        self.assertEqual(qx.kind_for("edital_abertura"), "edital")
        self.assertEqual(qx.kind_for("edital_retificado"), "edital")
        self.assertEqual(qx.kind_for("retificacao"), "retificacao")
        self.assertEqual(qx.kind_for("anexo"), "outro")


class SecurityTest(unittest.TestCase):
    def test_anexos_cdn_authorized_only_under_uploads(self):
        self.assertTrue(allowed_document_url(_ANEXOS.format(cid=3056, name="e.pdf")))
        self.assertFalse(allowed_document_url("https://anexos-r2.selecao.net.br/outro/e.pdf"))
        self.assertFalse(allowed_document_url("http://anexos-r2.selecao.net.br/uploads/e.pdf"))

    def test_site_host_not_authorized_for_uploads(self):
        # robots do site proíbe /uploads/; não autorizamos o host do site.
        self.assertFalse(allowed_document_url("https://www.quadrix.org.br/uploads/x.pdf"))


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        self.catalog = catalog_html([("3056", "Sedes/DF", "Concurso Público"),
                                     ("3049", "CRECI-ES", "Concurso Público")])
        self.details = {
            "3056": detail_html("Sedes/DF", [
                ("Edital nº 1 (Abertura)", _ANEXOS.format(cid=3056, name="ed.pdf"), "09/09/2026"),
                ("Edital nº 6 (Retificação)", _ANEXOS.format(cid=3056, name="ret.pdf"), "18/09/2026"),
            ]),
            "3049": detail_html("CRECI-ES", [
                ("Edital nº 1 (Abertura)", _ANEXOS.format(cid=3049, name="ed.pdf"), "01/10/2026"),
            ]),
        }

    def _discover(self, **kw):
        return qx.discover(self.db, self.catalog,
                           catalog_fetcher=lambda status, page, size: "",
                           detail_fetcher=lambda cid: self.details[cid],
                           statuses=(), discovered_at=_TS, **kw)["candidates"]

    def test_discovers_new_with_per_contest_identity(self):
        candidates = self._discover(max_new_details=5)
        # 2 páginas + 2 docs (Sedes) + 1 doc (CRECI)
        self.assertEqual(len(candidates), 5)
        pages = [c for c in candidates if c["document_type"] == "pagina_concurso"]
        self.assertEqual(len(pages), 2)
        with closing(connect_documents(self.db)) as conn:
            obs = conn.execute(
                "SELECT competition_id FROM observacoes_concurso ORDER BY competition_id").fetchall()
        self.assertEqual([o[0] for o in obs], ["quadrix-3049", "quadrix-3056"])

    def test_document_type_persisted(self):
        from radar.document_store import register_document, get_competition_details
        for candidate in self._discover(max_new_details=5):
            register_document(self.db, candidate)
        with closing(connect_documents(self.db)) as conn:
            types = sorted(r[0] for r in conn.execute(
                "SELECT tipo_documental FROM documentos WHERE tipo_documental IS NOT NULL"))
            contest_id = conn.execute(
                "SELECT contest_id FROM observacoes_concurso WHERE competition_id='quadrix-3056'").fetchone()[0]
        self.assertIn("edital_abertura", types)
        self.assertIn("retificacao", types)
        self.assertIn("pagina_concurso", types)
        # API de detalhe expõe o tipo (aditivo; contrato v1 intacto).
        detail = get_competition_details(self.db, contest_id)
        doc_types = {d["document_type"] for d in detail["documents"]}
        self.assertIn("edital_abertura", doc_types)

    def test_max_new_details_limits_fetch(self):
        candidates = self._discover(max_new_details=1)
        self.assertTrue(all("3056" in c["source_identifier"] for c in candidates))
        self.assertEqual(len(candidates), 3)  # página + 2 docs do primeiro concurso

    def test_refresh_picks_up_new_document_on_known_contest(self):
        from radar.document_store import register_document
        for candidate in self._discover(max_new_details=5):
            register_document(self.db, candidate)
        # Nova retificação publicada depois da primeira visita.
        self.details["3056"] = detail_html("Sedes/DF", [
            ("Edital nº 1 (Abertura)", _ANEXOS.format(cid=3056, name="ed.pdf"), "09/09/2026"),
            ("Edital nº 6 (Retificação)", _ANEXOS.format(cid=3056, name="ret.pdf"), "18/09/2026"),
            ("Edital nº 7 (Retificação)", _ANEXOS.format(cid=3056, name="ret7.pdf"), "20/10/2026"),
        ])
        candidates = self._discover(max_new_details=0, max_refresh_details=2)
        new_docs = [c for c in candidates if c["title"] == "Edital nº 7 (Retificação)"]
        self.assertEqual(len(new_docs), 1)
        self.assertEqual(new_docs[0]["kind"], "retificacao")

    def test_second_run_without_refresh_is_empty(self):
        from radar.document_store import register_document
        for candidate in self._discover(max_new_details=5):
            register_document(self.db, candidate)
        again = self._discover(max_new_details=5, max_refresh_details=0)
        self.assertEqual(again, [])

    def test_empty_first_page_raises(self):
        with self.assertRaises(ValueError):
            qx.discover(self.db, "<html><body>vazio</body></html>",
                        catalog_fetcher=lambda s, p, z: "", statuses=())

    def test_detail_fetch_failure_does_not_raise(self):
        def boom(cid):
            raise TimeoutError("caiu")
        result = qx.discover(self.db, self.catalog, catalog_fetcher=lambda s, p, z: "",
                             detail_fetcher=boom, statuses=())
        self.assertEqual(result["candidates"], [])


class QuadrixCycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        self.catalog = catalog_html([("3056", "Sedes/DF", "Concurso Público")])
        self.detail = detail_html("Sedes/DF", [
            ("Edital nº 1 (Abertura)", _ANEXOS.format(cid=3056, name="ed.pdf"), "09/09/2026"),
            ("Edital nº 6 (Retificação)", _ANEXOS.format(cid=3056, name="ret.pdf"), "18/09/2026"),
        ])

    def _source(self):
        return qx.quadrix_source(
            catalog_fetcher=lambda status, page, size: self.catalog if status == "abertos" else "",
            detail_fetcher=lambda cid: self.detail, statuses=(), max_new_details=5)

    def _transport(self, pdf=True):
        def transport(url, timeout, limit):
            body = b"%PDF-1.4\nconteudo" if pdf else b"<html>sem campos</html>"
            ctype = "application/pdf" if pdf else "text/html"
            return dict(status=200, final_url=url, content_type=ctype, peer_ip="8.8.8.8", body=body)
        return transport

    def test_cycle_registers_downloads_once_and_keeps_v1(self):
        first = run_cycle(self.db, sources=[self._source()], transport=self._transport())
        self.assertEqual(first["state"], "concluido")
        self.assertEqual(first["documents_new"], 3)  # página + edital + retificação
        with closing(connect_documents(self.db)) as conn:
            kinds = sorted(r[0] for r in conn.execute("SELECT kind FROM documentos"))
        self.assertEqual(kinds, ["edital", "outro", "retificacao"])
        self.assertEqual(list_records(self.db), [])  # v1 intacto

        calls = []

        def counting(url, timeout, limit):
            calls.append(url)
            return self._transport()(url, timeout, limit)

        second = run_cycle(self.db, sources=[self._source()], transport=counting)
        self.assertEqual(second["documents_new"], 0)
        self.assertEqual(second["versions_new"], 0)
        self.assertEqual(calls, [])

    def test_failure_preserves_and_reports(self):
        source = self._source()

        def boom():
            raise TimeoutError("quadrix fora do ar")

        source["fetch"] = boom
        result = run_cycle(self.db, sources=[source])
        self.assertEqual(result["state"], "falhou")


if __name__ == "__main__":
    unittest.main()
