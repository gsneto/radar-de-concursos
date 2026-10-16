"""Resolvers de referência oficial (FGV e DOU): parsing, casamento e ambiguidade."""

import json
import unittest

from radar import official_resolvers as orv


def fgv_catalog(entries):
    rows = "".join(
        f'<div class="views-row"><div class="views-field views-field-title">'
        f'<span class="field-content"><a href="/concursos/{slug}" hreflang="pt-br">{title}</a>'
        f'</span></div></div>'
        for slug, title in entries)
    return f"<html><body><div class='view-content'>{rows}</div></body></html>"


def dou_search_html(items):
    payload = json.dumps({"jsonArray": items}, ensure_ascii=False)
    return ('<script type="application/json">{"jsonArray":[]}</script>'
            '<script>var x = ' + payload + ';</script>')


def dou_item(url_title, title, hierarchy="Ministério da Educação/UF X", content=""):
    return {"pubName": "DO3", "urlTitle": url_title, "title": title, "numberPage": "10",
            "pubDate": "01/10/2026", "hierarchyStr": hierarchy, "content": content}


class FgvResolverTest(unittest.TestCase):
    def test_matches_official_fgv_page(self):
        resolver = orv.FgvCatalogResolver(catalog_fetcher=lambda: fgv_catalog([
            ("tjap26", "Concurso Público para Tribunal de Justiça do Estado do Amapá - Juiz Substituto"),
            ("pms2026", "Concurso Público para Prefeitura Municipal do Salvador 2026")]))
        resolution = resolver.resolve({"title": "Tribunal de Justiça do Estado do Amapá"})
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["official_url"], "https://conhecimento.fgv.br/concursos/tjap26")
        self.assertIn(resolution["confidence"], ("alta", "media"))

    def test_no_match_returns_none(self):
        resolver = orv.FgvCatalogResolver(catalog_fetcher=lambda: fgv_catalog([
            ("x", "Concurso de Outra Coisa Qualquer")]))
        self.assertIsNone(resolver.resolve({"title": "Prefeitura de Cidade Distante"}))

    def test_fetch_failure_returns_none(self):
        def boom():
            raise TimeoutError("caiu")
        resolver = orv.FgvCatalogResolver(catalog_fetcher=boom)
        self.assertIsNone(resolver.resolve({"title": "Qualquer Concurso Público"}))


class DouResolverTest(unittest.TestCase):
    def test_matches_dou_materia(self):
        resolver = orv.DouSearchResolver(search_fetcher=lambda q: dou_search_html([
            dou_item("edital-cgu-1", "EDITAL DE CONCURSO PÚBLICO CGU", hierarchy="Controladoria-Geral da União"),
            dou_item("outro-2", "EXTRATO DE CONTRATO", hierarchy="Outro Órgão")]))
        resolution = resolver.resolve({"title": "CGU - Controladoria-Geral da União"})
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["official_url"], "https://www.in.gov.br/web/dou/-/edital-cgu-1")
        self.assertEqual(resolution["source"], "Diário Oficial da União (Seção 3)")

    def test_no_shared_tokens_returns_none(self):
        resolver = orv.DouSearchResolver(search_fetcher=lambda q: dou_search_html([
            dou_item("x", "EXTRATO DE CONTRATO", hierarchy="Prefeitura Distante")]))
        self.assertIsNone(resolver.resolve({"title": "Câmara de Boituva"}))

    def test_ignores_non_concurso_publications(self):
        # Licitação/contrato com o mesmo órgão não é referência de concurso.
        resolver = orv.DouSearchResolver(search_fetcher=lambda q: dou_search_html([
            dou_item("lic-1", "AVISO DE LICITAÇÃO CGU", hierarchy="Controladoria-Geral da União",
                     content="objeto: aquisição de equipamentos"),
            dou_item("contr-2", "EXTRATO DE CONTRATO CGU", hierarchy="Controladoria-Geral da União")]))
        self.assertIsNone(resolver.resolve({"title": "CGU - Controladoria-Geral da União"}))

    def test_prefers_concurso_edital_over_other(self):
        resolver = orv.DouSearchResolver(search_fetcher=lambda q: dou_search_html([
            dou_item("lic-1", "AVISO DE LICITAÇÃO CGU", hierarchy="Controladoria-Geral da União",
                     content="concurso de projetos"),
            dou_item("edital-2", "EDITAL DE CONCURSO PÚBLICO CGU", hierarchy="Controladoria-Geral da União")]))
        resolution = resolver.resolve({"title": "CGU - Controladoria-Geral da União"})
        self.assertEqual(resolution["official_url"], "https://www.in.gov.br/web/dou/-/edital-2")

    def test_empty_results_returns_none(self):
        resolver = orv.DouSearchResolver(search_fetcher=lambda q: dou_search_html([]))
        self.assertIsNone(resolver.resolve({"title": "Qualquer Coisa"}))

    def test_unparseable_returns_none(self):
        resolver = orv.DouSearchResolver(search_fetcher=lambda q: "<html>sem json</html>")
        self.assertIsNone(resolver.resolve({"title": "Qualquer Coisa"}))

    def test_fetch_failure_returns_none(self):
        def boom(q):
            raise TimeoutError("caiu")
        resolver = orv.DouSearchResolver(search_fetcher=boom)
        self.assertIsNone(resolver.resolve({"title": "Qualquer Coisa"}))


class DefaultChainTest(unittest.TestCase):
    def test_default_resolvers_are_fgv_and_dou(self):
        names = [r.name for r in orv.default_resolvers()]
        self.assertEqual(names, ["fgv", "dou"])


if __name__ == "__main__":
    unittest.main()
