"""Adaptador da segunda fonte oficial (DOU Seção 3): parsing, filtro e integridade."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_fields import extract_field_proposals
from radar.document_store import (
    connect_documents,
    ensure_observation,
    migrate_document_schema,
    record_analysis,
    record_version,
)
from radar.dou_source import (
    DOU_COMPETITION_ID,
    DOU_SOURCE_URL,
    article_url,
    classify_kind,
    content_bytes,
    decode_body,
    discover,
    edition_url,
    fetch_edition,
    is_relevant,
    parse_edition,
    to_candidate,
)

_TS = "2026-10-16T12:00:00+00:00"


def _item(url_title, title, art_type, content, hierarchy="Ministério da Educação/UF X", pub_date="01/10/2026"):
    return {
        "pubName": "DO3", "urlTitle": url_title, "numberPage": "10", "subTitulo": "", "titulo": "",
        "title": title, "pubDate": pub_date, "content": content, "editionNumber": "186",
        "hierarchyLevelSize": 2, "artType": art_type, "pubOrder": "DO300025:00105",
        "hierarchyStr": hierarchy, "hierarchyList": hierarchy.split("/"),
    }


def _edition_html(items, section="DO3"):
    payload = json.dumps({"dateUrl": "01-10-2026", "section": section, "jsonArray": items}, ensure_ascii=False)
    return (
        '<html><head></head><body>'
        '<script type="application/json">{"jsonArray":[]}</script>'
        '<script>var x = ' + payload + ';</script>'
        '</body></html>'
    )


class ParseEditionTest(unittest.TestCase):
    def test_extracts_items_from_embedded_json(self):
        html = _edition_html([_item("edital-x/2026-111", "EDITAL Nº 1/2026", "Edital", "concurso público")])
        edition = parse_edition(html)
        self.assertEqual(edition["section"], "DO3")
        self.assertEqual(len(edition["items"]), 1)
        self.assertEqual(edition["items"][0]["urlTitle"], "edital-x/2026-111")

    def test_missing_json_raises(self):
        with self.assertRaises(ValueError):
            parse_edition("<html><body>sem dados</body></html>")

    def test_empty_html_raises(self):
        with self.assertRaises(ValueError):
            parse_edition("")

    def test_decodes_cp1252_fallback(self):
        self.assertEqual(decode_body("ÇÃ".encode("cp1252")), "ÇÃ")
        self.assertEqual(decode_body("ação".encode("utf-8")), "ação")
        with self.assertRaises(ValueError):
            decode_body(b"")

    def test_edition_url_format(self):
        self.assertEqual(edition_url("do3", "01-10-2026"),
                         "https://www.in.gov.br/leiturajornal?data=01-10-2026&secao=do3")
        with self.assertRaises(ValueError):
            edition_url("do3", "2026-10-01")


class RelevanceAndKindTest(unittest.TestCase):
    def test_relevance_requires_concurso_mention(self):
        self.assertTrue(is_relevant(_item("a", "EDITAL", "Edital", "abre concurso público")))
        self.assertFalse(is_relevant(_item("b", "PORTARIA", "Portaria", "dispõe sobre licitação")))

    def test_kind_classification(self):
        self.assertEqual(classify_kind(_item("a", "EDITAL Nº 1", "Edital", "")), "edital")
        self.assertEqual(classify_kind(_item("b", "AVISO DE RETIFICAÇÃO", "Aviso de Retificação", "")), "retificacao")
        self.assertEqual(classify_kind(_item("c", "RESULTADO", "Resultado", "")), "outro")

    def test_article_url_and_missing_slug(self):
        self.assertEqual(article_url(_item("edital-x/2026-111", "T", "Edital", "")),
                         "https://www.in.gov.br/web/dou/-/edital-x/2026-111")
        with self.assertRaises(ValueError):
            article_url({"urlTitle": ""})


class DiscoverTest(unittest.TestCase):
    def test_discover_filters_and_deduplicates(self):
        items = [
            _item("edital-a-1", "EDITAL Nº 1/2026", "Edital", "concurso público com 10 vagas"),
            _item("edital-a-1", "EDITAL Nº 1/2026", "Edital", "concurso público com 10 vagas"),
            _item("portaria-b-2", "PORTARIA", "Portaria", "sem relação"),
        ]
        candidates = discover(_edition_html(items), "obs-1", _TS)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["kind"], "edital")
        self.assertEqual(candidates[0]["observation_id"], "obs-1")
        self.assertTrue(candidates[0]["inline_content"].startswith(b"<p>"))

    def test_to_candidate_metadata(self):
        candidate = to_candidate(_item("edital-a-1", "EDITAL", "Edital", "concurso", hierarchy="Ministério da Educação/UF X"),
                                 "obs-1", _TS)
        self.assertEqual(candidate["official_url"], "https://www.in.gov.br/web/dou/-/edital-a-1")
        self.assertEqual(candidate["issuer"], "Ministério da Educação/UF X")
        self.assertEqual(candidate["published_at"], "2026-10-01")
        self.assertEqual(candidate["discovery_url"], DOU_SOURCE_URL)
        self.assertEqual(candidate["discovery_method"], "automatico")

    def test_content_bytes_requires_text(self):
        with self.assertRaises(ValueError):
            content_bytes(_item("a", "T", "Edital", ""))


class ArticleBodyTest(unittest.TestCase):
    def _page(self, inner):
        return ('<html><body><div class="container"><div class="texto-dou">'
                + inner + '</div><footer>rodapé</footer></div></body></html>')

    def test_extracts_texto_dou_without_portal_chrome(self):
        from radar.dou_source import extract_article_body
        body = extract_article_body(self._page("<p class='identifica'>EDITAL</p><p>10 vagas</p>"))
        text = body.decode("utf-8")
        self.assertIn("EDITAL", text)
        self.assertIn("10 vagas", text)
        self.assertNotIn("rodapé", text)

    def test_extracts_nested_divs_inside_body(self):
        from radar.dou_source import extract_article_body
        body = extract_article_body(self._page("<div><p>tabela</p></div><p>fim</p>"))
        self.assertIn("tabela", body.decode("utf-8"))
        self.assertIn("fim", body.decode("utf-8"))

    def test_missing_body_raises(self):
        from radar.dou_source import extract_article_body
        with self.assertRaises(ValueError):
            extract_article_body("<html><body>sem corpo</body></html>")
        with self.assertRaises(ValueError):
            extract_article_body("")

    def test_fetch_article_rejects_foreign_url(self):
        from radar.dou_source import fetch_article
        with self.assertRaises(ValueError):
            fetch_article("https://example.com/web/dou/-/x")

    def test_discover_uses_article_fetcher_and_falls_back_on_failure(self):
        from radar.dou_source import discover
        items = [
            _item("edital-ok-1", "EDITAL Nº 1/2026", "Edital", "concurso público"),
            _item("edital-fail-2", "EDITAL Nº 2/2026", "Edital", "concurso público"),
        ]
        html = _edition_html(items)

        def fetcher(url):
            if url.endswith("edital-fail-2"):
                raise TimeoutError("sem rede")
            return b"<p>ATO OFICIAL COMPLETO</p>"

        candidates = discover(html, "obs-1", _TS, article_fetcher=fetcher)
        by_slug = {c["official_url"].rsplit("/", 1)[-1]: c for c in candidates}
        self.assertEqual(by_slug["edital-ok-1"]["inline_content"], b"<p>ATO OFICIAL COMPLETO</p>")
        # Falha do fetcher mantém o conteúdo do JSON (não perde o documento).
        self.assertIn(b"concurso", by_slug["edital-fail-2"]["inline_content"])


class FetchEditionTest(unittest.TestCase):
    def test_fetch_uses_opener_and_enforces_limit(self):
        captured = {}

        class Response:
            def __init__(self, body):
                self._body = body
            def read(self, n=-1):
                return self._body[:n] if n and n > 0 else self._body
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return Response(_edition_html([_item("a", "EDITAL", "Edital", "concurso")]).encode("utf-8"))

        html = fetch_edition("do3", "01-10-2026", opener=opener)
        self.assertIn("jsonArray", html)
        self.assertIn("data=01-10-2026", captured["url"])

        def big_opener(request, timeout):
            return Response(b"x" * (8 * 1024 * 1024 + 2))

        with self.assertRaises(ValueError):
            fetch_edition("do3", "01-10-2026", opener=big_opener)


class VacancyIntegrityTest(unittest.TestCase):
    """A extração reutiliza as regras conservadoras e nunca confirma sozinha."""

    def test_indigenous_immediate_and_explicit_zero_reserve(self):
        text = ("O concurso público oferece 10 vagas para pessoas indígenas e não haverá cadastro "
                "de reserva: 0 vagas. Inscrições de 1 a 20/10/2026.")
        blocks = [dict(page_number=None, locator="conteudo-dou", start_offset=0,
                       end_offset=len(text), text=text)]
        proposals = extract_field_proposals(blocks, None, "contest-dou", None)
        fields = {p["field_name"]: json.loads(p["value_json"]) for p in proposals}
        self.assertEqual(fields.get("indigenous_vacancies"), 10)
        self.assertEqual(fields.get("reserve_vacancies"), 0)
        self.assertEqual(fields.get("registration_start"), "2026-10-01")
        self.assertEqual(fields.get("registration_end"), "2026-10-20")

    def test_global_total_is_not_replicated_per_role(self):
        text = "O concurso público totaliza 107 vagas imediatas."
        blocks = [dict(page_number=None, locator="conteudo-dou", start_offset=0,
                       end_offset=len(text), text=text)]
        proposals = extract_field_proposals(blocks, None, "contest-dou", None)
        immediate = [p for p in proposals if p["field_name"] == "immediate_vacancies"]
        # O total global é extraído, mas nunca atribuído a um cargo (escopo do DOU).
        self.assertEqual(len(immediate), 1)
        self.assertEqual(json.loads(immediate[0]["value_json"]), 107)
        self.assertTrue(all(p["role_id"] is None for p in proposals))

    def test_cadastro_de_reserva_without_number_is_not_zero(self):
        text = "Haverá cadastro de reserva conforme o edital do concurso público."
        blocks = [dict(page_number=None, locator="conteudo-dou", start_offset=0,
                       end_offset=len(text), text=text)]
        proposals = extract_field_proposals(blocks, None, "contest-dou", None)
        self.assertNotIn("reserve_vacancies", {p["field_name"] for p in proposals})


class EnsureObservationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)

    def test_ensure_observation_is_idempotent(self):
        first = ensure_observation(self.db, DOU_SOURCE_URL, DOU_COMPETITION_ID)
        second = ensure_observation(self.db, DOU_SOURCE_URL, DOU_COMPETITION_ID)
        self.assertEqual(first, second)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM concursos_identidade").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM observacoes_concurso").fetchone()[0], 1)

    def test_ensure_observation_rejects_non_https(self):
        with self.assertRaises(ValueError):
            ensure_observation(self.db, "http://in.gov.br/x", "id")

    def test_inline_content_records_version_and_proposals(self):
        from radar.document_store import get_competition_details, register_document
        observation_id = ensure_observation(self.db, DOU_SOURCE_URL, DOU_COMPETITION_ID)
        item = _item("edital-concurso-1", "EDITAL DE CONCURSO PÚBLICO Nº 1/2026", "Edital",
                     "O concurso público oferece 5 vagas para pessoas indígenas. "
                     "Inscrições de 1 a 20/10/2026.")
        candidate = to_candidate(item, observation_id, _TS)
        document_id = register_document(self.db, candidate)
        version_id = record_version(self.db, document_id, candidate["inline_content"],
                                    dict(fetched_at=_TS, fetched_url=candidate["official_url"],
                                         content_type="text/html"))
        from radar.document_extract import extract_blocks
        blocks = extract_blocks(candidate["inline_content"], "text/html")
        proposals = extract_field_proposals(blocks, version_id, _contest_id(self.db), None)
        record_analysis(self.db, version_id, blocks, proposals)
        detail = get_competition_details(self.db, _contest_id(self.db))
        self.assertEqual(detail["documents"][0]["versions"][0]["extraction_state"], "parcial")
        self.assertTrue(any(p["field_name"] == "indigenous_vacancies" for p in detail["proposals"]))
        # Nada é validado automaticamente.
        self.assertEqual(detail["current_values"], [])


def _contest_id(db):
    with closing(connect_documents(db)) as conn:
        return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE source_url=?",
                            (DOU_SOURCE_URL,)).fetchone()[0]


if __name__ == "__main__":
    unittest.main()
