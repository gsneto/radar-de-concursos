"""Frontend de produto (Fase 45): shell, design system, views e assets servidos.

Os testes são estáticos e de contrato local: não dependem de rede nem de navegador.
A validação visual no navegador é registrada em docs/superpowers/plans.
"""

import os
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from radar.server import create_server
from tests.test_role_identity_f35 import make_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

CORE = ["core/dom.js", "core/format.js", "core/api.js", "core/store.js"]
COMPONENTS = ["components/ui.js", "components/charts.js"]
VIEWS = ["views/overview.js", "views/opportunities.js", "views/dossier.js",
         "views/studies.js", "views/deadlines.js", "views/history.js",
         "views/settings.js"]


def read(*parts):
    with open(os.path.join(WEB, *parts), encoding="utf-8") as handle:
        return handle.read()


class ShellTest(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")

    def test_shell_landmarks_and_single_h1(self):
        self.assertEqual(self.html.count("<h1"), 1)
        self.assertIn('class="sidebar"', self.html)
        self.assertIn('class="topbar"', self.html)
        self.assertIn('id="view-root"', self.html)
        self.assertIn('id="view-operation"', self.html)
        self.assertIn('id="main-content"', self.html)
        self.assertIn('class="skip-link"', self.html)
        self.assertIn("<footer", self.html)

    def test_navigation_groups_and_routes(self):
        for target in ("#/visao-geral", "#/oportunidades", "#/prazos", "#/estudos",
                       "#/historico", "#/configuracoes", "#/operacao"):
            self.assertIn('href="%s"' % target, self.html)
        self.assertEqual(self.html.count('class="nav__label"'), 3)

    def test_technical_panels_preserved(self):
        for panel in ("monitoring-panel", "alerts-panel", "triage-panel",
                      "priorities-panel", "coverage-panel", "pipeline-panel",
                      "official-coverage-panel", "sources-panel", "review-panel",
                      "mesa-panel", "carteira-panel", "rec-panel", "conf-panel",
                      "prazo-panel", "nominais-panel", "timeline-panel",
                      "assoc-panel", "blocked-panel", "study-panel"):
            self.assertIn('id="%s"' % panel, self.html, panel)
        self.assertIn('id="preferences-form"', self.html)

    def test_assets_are_local_and_deferred_init(self):
        for script in ["core/dom.js", "core/format.js", "core/api.js",
                       "core/store.js", "components/ui.js", "components/charts.js",
                       "views/overview.js", "views/opportunities.js",
                       "views/dossier.js", "views/studies.js", "views/deadlines.js",
                       "views/history.js", "views/settings.js", "app.js", "shell.js"]:
            self.assertIn('src="%s"' % script, self.html, script)
        self.assertIn('href="product.css"', self.html)
        self.assertIn("RADAR_DEFER_INIT", self.html)
        self.assertNotIn("http://", self.html.replace("http://www.w3.org", ""))
        self.assertNotIn("https://fonts", self.html)

    def test_mobile_drawer_controls(self):
        self.assertIn('id="drawer-open"', self.html)
        self.assertIn('id="drawer-close"', self.html)
        self.assertIn('id="drawer-backdrop"', self.html)
        self.assertIn('aria-controls="sidebar"', self.html)


class DesignSystemTest(unittest.TestCase):
    def setUp(self):
        self.css = read("product.css")

    def test_tokens_defined(self):
        for token in ("--app-bg", "--surface", "--sidebar-bg", "--ink", "--muted",
                      "--rule", "--brand", "--accent", "--chart-1", "--space-4",
                      "--text-sm", "--radius", "--shadow-1", "--sidebar-w",
                      "--sidebar-w-collapsed", "--topbar-h", "--content-max",
                      "--focus", "--transition"):
            self.assertIn(token + ":", self.css, token)

    def test_responsive_breakpoints(self):
        for width in ("1200px", "1024px", "900px", "760px", "520px"):
            self.assertIn("@media (max-width: %s)" % width, self.css)

    def test_reduced_motion_and_hidden_rule(self):
        self.assertIn("prefers-reduced-motion: reduce", self.css)
        self.assertIn("[hidden]", self.css)
        self.assertIn("display: none !important", self.css)

    def test_no_remote_assets(self):
        self.assertNotIn("http://", self.css.replace("http://www.w3.org", ""))
        self.assertNotIn("@import", self.css)


class ViewContractTest(unittest.TestCase):
    def test_views_are_plain_iife_modules(self):
        for relative in CORE + COMPONENTS + VIEWS:
            source = read(*relative.split("/"))
            self.assertIn("(function (global)", source, relative)
            self.assertIsNone(re.search(r"\.innerHTML\s*=", source), relative)
            self.assertNotIn("document.write", source, relative)

    def test_views_use_real_endpoints(self):
        overview = read("views", "overview.js")
        for endpoint in ("/api/carteira", "/api/cobertura/resumo", "/api/linha-do-tempo",
                         "/api/estudos/painel", "/api/prazos/calendario"):
            self.assertIn(endpoint, overview, endpoint)
        opportunities = read("views", "opportunities.js")
        self.assertIn("/api/carteira", opportunities)
        studies = read("views", "studies.js")
        for endpoint in ("/api/estudos/painel", "/api/estudos/sessoes",
                         "/api/estudos/flashcards", "/api/estudos/simulados",
                         "/api/estudos/desempenho", "/api/estudos/exportar"):
            self.assertIn(endpoint, studies, endpoint)
        dossier = read("views", "dossier.js")
        self.assertIn("/api/concursos/", dossier)
        self.assertIn("/detalhes", dossier)

    def test_charts_are_accessible(self):
        charts = read("components", "charts.js")
        self.assertIn("role: 'img'", charts)
        self.assertIn("aria-labelledby", charts)
        self.assertIn("svgEl(doc, 'title'", charts)
        self.assertIn("svgEl(doc, 'desc'", charts)
        ui = read("components", "ui.js")
        self.assertIn("tableFallback", ui)
        self.assertIn("role', 'progressbar'", ui)

    def test_api_service_handles_timeout_and_stale_responses(self):
        api = read("core", "api.js")
        self.assertIn("AbortController", api)
        self.assertIn("timeout", api)
        self.assertIn("sequencer", api)
        self.assertIn("no-store", api)
        self.assertIn("application/json", api)

    def test_store_is_local_only(self):
        store = read("core", "store.js")
        self.assertIn("localStorage", store)
        self.assertIn("radar.ui.v1", store)
        self.assertNotIn("fetch(", store)

    def test_no_placeholder_data_in_views(self):
        for relative in VIEWS:
            source = read(*relative.split("/"))
            lowered = source.lower()
            for forbidden in ("lorem ipsum", "dados fictícios", "mockdata",
                              "placeholder-data"):
                self.assertNotIn(forbidden, lowered, relative)


class AssetServingTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        self.server = create_server(self.db, port=0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path):
        def headers_of(message):
            return {key.lower(): value for key, value in message.items()}
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d%s" % (self.port, path), timeout=10) as response:
                return response.status, headers_of(response.headers), response.read()
        except urllib.error.HTTPError as error:
            return error.code, headers_of(error.headers), error.read()

    def test_new_assets_are_served(self):
        for path, content_type in (("/product.css", "text/css"),
                                   ("/shell.js", "javascript"),
                                   ("/core/api.js", "javascript"),
                                   ("/components/charts.js", "javascript"),
                                   ("/views/overview.js", "javascript")):
            status, headers, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertIn(content_type, headers.get("content-type", ""), path)
            self.assertTrue(len(body) > 0, path)

    def test_assets_disable_aggressive_cache(self):
        status, headers, _ = self.request("/shell.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("cache-control"), "no-cache")

    def test_nested_traversal_blocked(self):
        for path in ("/core/../radar/server.py", "/views/../../radar/server.py",
                     "/web/core/../../radar/server.py", "/core/server.py"):
            status, _, body = self.request(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"def _serve_file", body)

    def test_only_js_and_css_under_allowed_dirs(self):
        status, _, _ = self.request("/core/dom.py")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
