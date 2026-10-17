"""Fonte oficial piloto IBFC: catálogo, detalhe e identidade por certame (Fase 27)."""

import unittest
from contextlib import closing
from pathlib import Path
import tempfile
from uuid import uuid4

from radar import ibfc_source
from radar.document_store import connect_documents, migrate_document_schema
from radar.monitoring import run_cycle
from radar.storage import list_records

NOW = "2026-10-17T12:00:00+00:00"

CATALOG = """
<div class="panel-body">
  <a href="/informacoes/497/" class="lista-concurso">
    <div class="col-lg-2"><img src="//static-cdn.selecao.net.br/x.png"></div>
    <div class="col-lg-10">
      <span class="texto_cliente"><p>IBFC - Jovem Aprendiz</p></span>
    </div>
    <div class="col-lg-10">
      <span class="texto_edital">Edital n&ordm; <b>29/2026</b><br />
        Inscri&ccedil;&otilde;es de <b>13/10/2026</b> a <b>01/12/2026</b><br />
        <a href="/informacoes/497/"><span class="inscricoesabertas">Inscri&ccedil;&otilde;es Abertas!</span></a>
      </span>
    </div>
    <hr class="traco">
  </a>
  <a href="/informacoes/490/" class="lista-concurso">
    <div class="col-lg-10">
      <span class="texto_cliente"><h5><strong>Secretaria da Educa&ccedil;&atilde;o da Bahia</strong></h5></span>
    </div>
    <div class="col-lg-10">
      <span class="texto_edital">Edital n&ordm; <b>02, 03 e 04/2026</b><br />
        Inscri&ccedil;&otilde;es de <b>26/01/2026</b> a <b>23/02/2026</b><br />
      </span>
    </div>
  </a>
</div>
"""

DETAIL = """
<h2>Concursos</h2>
<h2>Secretaria da Educa&ccedil;&atilde;o da Bahia</h2>
<div id="aba-anexos-lista"></div>
<div class="tab" id="tab1">
  <ul>
    <li class="pdf" style="display:flex;">
      <a style="flex:1;" href="https://anexos-r2.selecao.net.br/uploads/747/concursos/490/anexos/aaa.pdf" target="_blank">
        Edital de Abertura n&ordm; 004/2026 - T&eacute;cnico
        <span>23/01/2026</span>
      </a>
      <span><a href="/leitor-rybena?pdf=https://anexos-r2.selecao.net.br/uploads/747/concursos/490/anexos/aaa.pdf">Acessibilidade</a></span>
    </li>
    <li class="pdf" style="display:flex;">
      <a style="flex:1;" href="https://anexos.cdn.selecao.net.br/uploads/747/concursos/490/anexos/bbb.pdf" target="_blank">
        Retifica&ccedil;&atilde;o n&deg; 01 do Edital no 004/2026
        <span>28/01/2026</span>
      </a>
    </li>
    <li class="pdf" style="display:flex;">
      <a style="flex:1;" href="https://anexos-r2.selecao.net.br/uploads/747/concursos/490/anexos/ccc.pdf" target="_blank">
        Comunicado - Altera&ccedil;&atilde;o de Local de Prova
        <span>24/03/2026</span>
      </a>
    </li>
  </ul>
</div>
"""


class CatalogTest(unittest.TestCase):
    def test_extrai_entradas(self):
        entries = ibfc_source.parse_catalog(CATALOG)
        self.assertEqual([e["id"] for e in entries], ["497", "490"])
        first = entries[0]
        self.assertEqual(first["title"], "IBFC - Jovem Aprendiz")
        self.assertEqual(first["edital"], "29/2026")
        self.assertEqual(first["inscricao_inicio"], "13/10/2026")
        self.assertEqual(first["inscricao_fim"], "01/12/2026")
        self.assertTrue(first["inscricoes_abertas"])
        self.assertEqual(first["url"], "https://concursos.ibfc.org.br/informacoes/497/")

    def test_segunda_entrada_sem_status_aberto(self):
        entries = ibfc_source.parse_catalog(CATALOG)
        self.assertFalse(entries[1]["inscricoes_abertas"])
        self.assertEqual(entries[1]["edital"], "02, 03 e 04/2026")

    def test_catalogo_vazio_falha(self):
        with self.assertRaises(ValueError):
            ibfc_source.parse_catalog("")

    def test_entidade_html_resolvida(self):
        entries = ibfc_source.parse_catalog(CATALOG)
        self.assertIn("Educação", entries[1]["title"])


class DetailTest(unittest.TestCase):
    def test_extrai_documentos(self):
        detail = ibfc_source.parse_detail(DETAIL)
        self.assertEqual(detail["title"], "Secretaria da Educação da Bahia")
        self.assertEqual(len(detail["documents"]), 3)
        first = detail["documents"][0]
        self.assertEqual(first["title"], "Edital de Abertura nº 004/2026 - Técnico")
        self.assertEqual(first["date"], "23/01/2026")
        self.assertEqual(first["document_type"], "edital_abertura")
        self.assertEqual(first["kind"], "edital")

    def test_classifica_retificacao_e_comunicado(self):
        docs = {d["url"].rsplit("/", 1)[-1]: d for d in
                ibfc_source.parse_detail(DETAIL)["documents"]}
        self.assertEqual(docs["bbb.pdf"]["document_type"], "retificacao")
        self.assertEqual(docs["bbb.pdf"]["kind"], "retificacao")
        self.assertEqual(docs["ccc.pdf"]["document_type"], "comunicado")

    def test_nao_duplica_pelo_link_de_acessibilidade(self):
        self.assertEqual(len(ibfc_source.parse_detail(DETAIL)["documents"]), 3)

    def test_detalhe_vazio_falha(self):
        with self.assertRaises(ValueError):
            ibfc_source.parse_detail("")


class FetchPolicyTest(unittest.TestCase):
    def test_anexo_em_cdn_bloqueado_por_robots_nao_e_baixado(self):
        docs = ibfc_source.parse_detail(DETAIL)["documents"]
        entry = {"id": "490", "url": ibfc_source.detail_url("490"), "title": "x"}
        candidates = {d["title"]: ibfc_source.to_candidate(d, entry, "obs", NOW)
                      for d in docs}
        retificacao = next(c for t, c in candidates.items() if t.startswith("Retificação"))
        self.assertFalse(retificacao["fetch_allowed"])
        self.assertEqual(retificacao["fetch_blocked_reason"], "robots_disallow_anexos_cdn")
        edital = next(c for t, c in candidates.items() if t.startswith("Edital"))
        self.assertTrue(edital["fetch_allowed"])

    def test_candidato_carrega_metadados(self):
        docs = ibfc_source.parse_detail(DETAIL)["documents"]
        entry = {"id": "490", "url": ibfc_source.detail_url("490"), "title": "x"}
        candidate = ibfc_source.to_candidate(docs[0], entry, "obs", NOW)
        self.assertEqual(candidate["published_at"], "2026-01-23")
        self.assertEqual(candidate["issuer"], "IBFC")
        self.assertTrue(candidate["source_identifier"].startswith("ibfc-490:"))


class IdentityTest(unittest.TestCase):
    def test_identidade_externa_e_por_certame(self):
        self.assertEqual(ibfc_source.competition_id("497"), "ibfc-497")
        self.assertNotEqual(ibfc_source.competition_id("497"),
                            ibfc_source.competition_id("498"))

    def test_identificador_invalido(self):
        with self.assertRaises(ValueError):
            ibfc_source.competition_id("abc")
        with self.assertRaises(ValueError):
            ibfc_source.detail_url("../etc")

    def test_catalogo_status_invalido(self):
        with self.assertRaises(ValueError):
            ibfc_source.catalog_url("hack")


class AttemptBlockedHostsTest(unittest.TestCase):
    """Configuração opt-in: só o conector IBFC pode tentar hosts com robots restritivo."""

    def _entry(self):
        return {"id": "485", "url": "https://concursos.ibfc.org.br/informacoes/485/",
                "title": "Concurso", "edital": "01/2025"}

    def _document(self, host):
        return {"url": f"https://{host}/uploads/747/concursos/485/anexos/a.pdf",
                "title": "Edital", "kind": "edital", "document_type": "edital_abertura",
                "date": "2025-07-07"}

    def test_sem_configuracao_cdn_continua_nao_baixando(self):
        candidate = ibfc_source.to_candidate(
            self._document("anexos.cdn.selecao.net.br"), self._entry(), "obs", "2026-10-17")
        self.assertFalse(candidate["fetch_allowed"])
        self.assertEqual(candidate["fetch_blocked_reason"], "robots_disallow_anexos_cdn")
        self.assertIsNone(candidate["download_allowed_hosts"])

    def test_configuracao_permite_tentativa_explicita(self):
        candidate = ibfc_source.to_candidate(
            self._document("anexos.cdn.selecao.net.br"), self._entry(), "obs", "2026-10-17",
            attempt_blocked_hosts=("anexos.cdn.selecao.net.br",))
        self.assertTrue(candidate["fetch_allowed"])
        self.assertIsNone(candidate["fetch_blocked_reason"])
        self.assertEqual(candidate["download_allowed_hosts"],
                         ["anexos.cdn.selecao.net.br"])
        self.assertIsNone(candidate["robots_policy"])

    def test_host_nao_listado_nao_recebe_autorizacao(self):
        candidate = ibfc_source.to_candidate(
            self._document("outro.cdn.example"), self._entry(), "obs", "2026-10-17",
            attempt_blocked_hosts=("anexos.cdn.selecao.net.br",))
        self.assertFalse(candidate["fetch_allowed"])
        self.assertIsNone(candidate["download_allowed_hosts"])

    def test_r2_permanece_autorizado_sem_configuracao(self):
        candidate = ibfc_source.to_candidate(
            self._document("anexos-r2.selecao.net.br"), self._entry(), "obs", "2026-10-17")
        self.assertTrue(candidate["fetch_allowed"])
        self.assertIsNone(candidate["download_allowed_hosts"])

    def test_fonte_declara_hosts_apenas_quando_configurada(self):
        default = ibfc_source.ibfc_source()
        self.assertEqual(default["download_allowed_hosts"], [])
        configured = ibfc_source.ibfc_source(
            attempt_blocked_hosts=("anexos.cdn.selecao.net.br",))
        self.assertEqual(configured["download_allowed_hosts"],
                         ["anexos.cdn.selecao.net.br"])

    def test_autorizacao_global_nao_muda(self):
        from radar.document_discovery import allowed_document_url
        url = "https://anexos.cdn.selecao.net.br/uploads/747/concursos/485/anexos/a.pdf"
        self.assertFalse(allowed_document_url(url))
        self.assertTrue(allowed_document_url(
            url, extra_hosts=("anexos.cdn.selecao.net.br",)))
        self.assertFalse(allowed_document_url(
            "https://outro.example/uploads/a.pdf",
            extra_hosts=("anexos.cdn.selecao.net.br",)))


class DiscoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "ibfc.sqlite3")
        migrate_document_schema(self.db)

    def _source(self, catalog_html=CATALOG, detail_html=DETAIL, **kwargs):
        return {**ibfc_source.ibfc_source(
            catalog_fetcher=lambda status: catalog_html,
            detail_fetcher=lambda contest_id: detail_html),
            "download_new_only": True, **kwargs}

    def _discover(self, catalog_html=CATALOG, detail_html=DETAIL, **kwargs):
        return ibfc_source.discover(
            self.db, catalog_html,
            catalog_fetcher=lambda status: catalog_html,
            detail_fetcher=lambda contest_id: detail_html, **kwargs)

    def _transport(self):
        def transport(url, *, timeout, limit):
            return dict(status=200, final_url=url, content_type="application/pdf",
                        peer_ip="8.8.8.8", body=b"%PDF-1.4\nconteudo")
        return transport

    def test_cria_um_concurso_por_certame(self):
        run_cycle(self.db, sources=[self._source()], transport=self._transport())
        with closing(connect_documents(self.db)) as conn:
            rows = conn.execute(
                "SELECT competition_id FROM observacoes_concurso ORDER BY competition_id"
            ).fetchall()
        self.assertEqual([r[0] for r in rows], ["ibfc-490", "ibfc-497"])

    def test_documentos_ficam_no_proprio_certame(self):
        run_cycle(self.db, sources=[self._source()], transport=self._transport())
        with closing(connect_documents(self.db)) as conn:
            counts = conn.execute(
                """SELECT o.competition_id, COUNT(d.id) FROM observacoes_concurso o
                   JOIN documentos d ON d.observation_id=o.id GROUP BY o.competition_id"""
            ).fetchall()
        self.assertEqual(dict(counts), {"ibfc-490": 4, "ibfc-497": 4})

    def test_idempotente(self):
        first = run_cycle(self.db, sources=[self._source()], transport=self._transport())
        self.assertEqual(first["state"], "concluido")
        with closing(connect_documents(self.db)) as conn:
            before = conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
        second = run_cycle(self.db, sources=[self._source()], transport=self._transport())
        with closing(connect_documents(self.db)) as conn:
            after = conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(second["documents_new"], 0)
        self.assertEqual(list_records(self.db), [])  # contrato v1 intacto

    def test_falha_de_detalhe_nao_aborta(self):
        def boom(contest_id):
            if contest_id == "497":
                raise OSError("rede")
            return DETAIL
        result = ibfc_source.discover(
            self.db, CATALOG, catalog_fetcher=lambda status: CATALOG,
            detail_fetcher=boom)
        self.assertEqual(len(result["summary"]["errors"]), 1)
        self.assertTrue(result["candidates"])
        # convenção do projeto: sucesso parcial é sinalizado, não escondido
        self.assertTrue(result["partial"])

    def test_catalogo_vazio_marca_falha(self):
        result = ibfc_source.discover(
            self.db, "", catalog_fetcher=lambda status: "",
            detail_fetcher=lambda contest_id: DETAIL)
        self.assertTrue(result["failed"])
        self.assertEqual(result["candidates"], [])

    def test_max_new_details_respeitado(self):
        ibfc_source.discover(self.db, CATALOG, catalog_fetcher=lambda status: CATALOG,
                             detail_fetcher=lambda contest_id: DETAIL, max_new_details=1)
        with closing(connect_documents(self.db)) as conn:
            contests = conn.execute(
                "SELECT COUNT(*) FROM observacoes_concurso").fetchone()[0]
        self.assertEqual(contests, 1)

    def test_documento_bloqueado_por_robots_nao_e_baixado(self):
        calls = []

        def transport(url, *, timeout, limit):
            calls.append(url)
            return dict(status=200, final_url=url, content_type="application/pdf",
                        peer_ip="8.8.8.8", body=b"%PDF-1.4\nconteudo")

        run_cycle(self.db, sources=[self._source()], transport=transport)
        self.assertFalse(any("anexos.cdn.selecao.net.br" in url for url in calls),
                         "CDN com robots.txt Disallow: / não pode ser baixado")
        self.assertTrue(any("anexos-r2.selecao.net.br" in url for url in calls))
        with closing(connect_documents(self.db)) as conn:
            versions = conn.execute(
                """SELECT COUNT(*) FROM versoes_documento v JOIN documentos d ON d.id=v.document_id
                   WHERE d.official_url LIKE '%anexos.cdn%'""").fetchone()[0]
        self.assertEqual(versions, 0)

    def test_resumo_reporta_downloads_bloqueados(self):
        result = run_cycle(self.db, sources=[self._source()], transport=self._transport())
        blocked = result["sources"][0]["downloads_bloqueados"]
        # dois certames no fixture, um anexo em CDN bloqueado em cada
        self.assertEqual(blocked.get("robots_disallow_anexos_cdn"), 2)


if __name__ == "__main__":
    unittest.main()
