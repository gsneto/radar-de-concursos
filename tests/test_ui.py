"""Testes de interface do Radar de Concursos (Task 3 — frontend).

Cobre, sem instalar dependências:
- estrutura semântica/acessível do HTML (landmarks, heading, aria-live, botão de
  tentar novamente);
- chamada à API local ``GET /api/concursos`` e renderização segura (sem
  ``innerHTML`` para dados oriundos da API);
- estados loading/error/empty/data;
- regras de domínio: distinção prova/exercício, vagas imediatas/reserva/indígenas,
  ``null`` como "Desconhecido" e zero preservado como zero;
- comportamento funcional do JS via Node (runtime já disponível), usando um DOM
  de falso que lança exceção se ``innerHTML`` for tocado no caminho de render.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
INDEX_PATH = os.path.join(WEB, "index.html")
APP_PATH = os.path.join(WEB, "app.js")
STYLES_PATH = os.path.join(WEB, "styles.css")

NODE = shutil.which("node")

# Campos exatos do contrato congelado de GET /api/concursos.
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


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestHtmlStructure(unittest.TestCase):
    """Estrutura semântica e acessibilidade do index.html."""

    def test_index_exists(self):
        self.assertTrue(os.path.exists(INDEX_PATH), "web/index.html deve existir")
        html = read(INDEX_PATH)
        self.assertIn("Radar de Concursos", html)

    def test_main_landmark_and_header_footer(self):
        html = read(INDEX_PATH)
        self.assertIn("<main", html)
        self.assertIn("<header", html)
        self.assertIn("<footer", html)

    def test_single_h1_heading(self):
        html = read(INDEX_PATH)
        self.assertEqual(html.count("<h1"), 1, "deve haver exatamente um <h1>")
        self.assertIn("<h1", html)

    def test_state_containers_present(self):
        html = read(INDEX_PATH)
        for state in ("loading", "error", "empty", "data"):
            self.assertIn(
                'id="state-%s"' % state, html,
                "deve existir contêiner para o estado %s" % state,
            )
        self.assertIn('id="competition-list"', html)

    def test_live_region_present(self):
        html = read(INDEX_PATH)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('role="status"', html)

    def test_retry_button_present(self):
        html = read(INDEX_PATH)
        self.assertIn('id="retry-button"', html)
        self.assertIn("type=\"button\"", html)

    def test_loads_assets(self):
        html = read(INDEX_PATH)
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)

    def test_monitoring_panel_present(self):
        html = read(INDEX_PATH)
        self.assertIn('id="monitoring-panel"', html)
        self.assertIn("Monitoramento", html)

    def test_favicon_declared_without_external_resource(self):
        html = read(INDEX_PATH)
        self.assertIn('rel="icon"', html)
        self.assertIn("data:image/svg+xml", html)
        self.assertNotIn("favicon.ico", html)

    def test_no_hardcoded_production_data(self):
        html = read(INDEX_PATH)
        # Nenhum dado real/candidato fictício embutido na página.
        for forbidden in (
            "Guajará-Mirim",
            "Professor de Educação Infantil",
            "001/2026",
        ):
            self.assertNotIn(forbidden, html)


class TestAppStatic(unittest.TestCase):
    """Propriedades estáticas do app.js (chamada à API + renderização segura)."""

    def test_fetches_api_endpoint(self):
        js = read(APP_PATH)
        self.assertIn("/api/concursos", js)
        self.assertIn("fetch(", js)

    def test_uses_safe_rendering(self):
        js = read(APP_PATH)
        self.assertIn("textContent", js)
        self.assertIn("createElement", js)
        self.assertNotIn("innerHTML", js)

    def test_references_all_contract_fields(self):
        js = read(APP_PATH)
        for field in CONTRACT_FIELDS:
            self.assertIn(
                field, js,
                "app.js deve referenciar o campo %r do contrato" % field,
            )

    def test_has_unknown_label(self):
        js = read(APP_PATH)
        self.assertIn("Desconhecido", js)

    def test_renders_document_intelligence_fields(self):
        js = read(APP_PATH)
        for field in ("conflicts", "role_reconciliations", "related_document_ids",
                      "document_id", "reconciled_role_id", "current_values"):
            self.assertIn(field, js, "app.js deve apresentar %r" % field)

    def test_renders_monitoring_fields(self):
        js = read(APP_PATH)
        for token in ("renderMonitoring", "/api/monitoramento", "last_cycle",
                      "pending_analysis", "coverage_state", "Nova publicação",
                      "Alteração em documento conhecido", "Verificação incompleta",
                      "alert--failed"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)

    def test_renders_human_labels_for_raw_enums(self):
        js = read(APP_PATH)
        for token in ("EXTRACTION_LABEL", "FIELD_LABEL", "Não iniciada",
                      "Vagas indígenas", "field-key"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)

    def test_renders_alerts_and_auto_refresh(self):
        js = read(APP_PATH)
        for token in ("renderAlerts", "/api/alertas", "fetchAlerts", "startAutoRefresh",
                      "autoRefreshSeconds", "setInterval", "Prazo de isenção",
                      "Fonte indisponível", "alerts-panel"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        self.assertIn('id="alerts-panel"', html)
        self.assertIn("data-refresh-seconds", html)


    def test_renders_triage_center(self):
        js = read(APP_PATH)
        for token in ("renderTriage", "/api/triagem", "fetchTriage", "renderTriageGroup",
                      "triage-panel", "alertAction", "/api/alertas/", "snoozeOneDay",
                      "Ação necessária hoje", "Adiar 1 dia", "Dispensar", "Reabrir",
                      "focusContestFromHash", "data-contest-id"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        self.assertIn('id="triage-panel"', html)
        css = read(STYLES_PATH)
        for token in (".triage__panel", ".triage-group", ".triage-action", ".card--focused"):
            self.assertIn(token, css, "styles.css deve apresentar %r" % token)


    def test_renders_priorities(self):
        js = read(APP_PATH)
        for token in ("renderPriorities", "/api/prioridades", "fetchPriorities",
                      "renderPriorityItem", "priorities-panel", "/api/preferencias",
                      "savePreferences", "loadPreferencesForm", "linha reta",
                      "distância geográfica"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        self.assertIn('id="priorities-panel"', html)
        self.assertIn('id="preferences-form"', html)
        css = read(STYLES_PATH)
        for token in (".priorities__panel", ".priority-item", ".factor--unknown", ".prefs"):
            self.assertIn(token, css, "styles.css deve apresentar %r" % token)


    def test_renders_study_panel(self):
        js = read(APP_PATH)
        for token in ("renderStudy", "fetchStudy", "/api/estudos/painel", "/api/estudos/sessoes",
                      "/api/estudos/disciplinas", "/api/estudos/topicos", "/api/estudos/progresso",
                      "/api/estudos/revisoes", "Marcar revisada",
                      "renderStudyTimer", "formatClock", "study-panel", "timer-display",
                      "timerAction", "study__stat"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        for token in ('id="study-panel"', 'id="timer-display"', 'id="study-form"',
                      'id="timer-start"', 'id="timer-finish"'):
            self.assertIn(token, html)
        css = read(STYLES_PATH)
        for token in (".study__panel", ".study__stat", ".study-disc", ".timer__display"):
            self.assertIn(token, css, "styles.css deve apresentar %r" % token)

    def test_renders_prep_and_profile(self):
        js = read(APP_PATH)
        for token in ("renderPrep", "fetchPrep", "/api/estudos/conteudo", "/api/estudos/preparacao",
                      "/api/estudos/perfil", "/api/estudos/lacuna", "renderPerfil", "fetchPerfil",
                      "savePerfil", "prep-panel", "perfil-panel", "Enviar para estudos"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        for token in ('id="prep-panel"', 'id="perfil-panel"', 'id="prep-concurso"',
                      'id="perfil-form"', 'id="perfil-nivel"'):
            self.assertIn(token, html)
        css = read(STYLES_PATH)
        for token in (".prep__panel", ".prep__stats", ".prep__basis"):
            self.assertIn(token, css, "styles.css deve apresentar %r" % token)

    def test_renders_exam_navigation_and_packages(self):
        js = read(APP_PATH)
        for token in ("practice__map", "goTo(", "is-marked", "is-answered",
                      "Marcar para revisão", "aria-pressed", "Anterior", "Próxima",
                      "/resumo", "em branco", "global.confirm", "MODE_LABELS",
                      "readFileAsBase64", "FileReader", "practice__image",
                      "/api/estudos/midia/", "renderPackagePreview", "pac-preview",
                      "pac-import", "pac-export", "/api/estudos/pacotes/previa",
                      "/api/estudos/pacotes/importar", "exam-modo-aviso"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        for token in ('id="exam-modo"', 'id="exam-modo-aviso"', 'role="status"',
                      'id="exam-disciplina"', 'id="exam-topico"',
                      'id="pac-form"', 'id="pac-panel"', 'id="pac-file"',
                      'id="pac-licenca"', 'id="pac-preview"', 'id="pac-import"',
                      'id="pac-export"'):
            self.assertIn(token, html, "index.html deve conter %r" % token)
        css = read(os.path.join(WEB, "styles.css"))
        for token in (".practice__map", ".practice__image", ".practice__map-btn.is-marked"):
            self.assertIn(token, css, "styles.css deve conter %r" % token)

    def test_renders_practice(self):
        js = read(APP_PATH)
        for token in ("renderFlashcards", "renderQuestions", "renderExams",
                      "renderPerformance", "renderExamRunner", "fetchPractice",
                      "/api/estudos/flashcards", "/api/estudos/questoes",
                      "/api/estudos/tentativas", "/api/estudos/simulados",
                      "/api/estudos/desempenho", "fc-panel", "q-panel", "exam-panel",
                      "perf-panel", "Mostrar resposta", "/responder", "/finalizar",
                      "Responder / retomar"):
            self.assertIn(token, js, "app.js deve apresentar %r" % token)
        html = read(os.path.join(WEB, "index.html"))
        for token in ('id="fc-panel"', 'id="q-panel"', 'id="exam-panel"', 'id="perf-panel"',
                      'id="fc-form"', 'id="q-form"', 'id="exam-form"'):
            self.assertIn(token, html)
        css = read(STYLES_PATH)
        for token in (".practice__panel", ".practice__answer", ".practice__result"):
            self.assertIn(token, css, "styles.css deve apresentar %r" % token)


class TestStylesStatic(unittest.TestCase):
    """Responsividade e acessibilidade do styles.css."""

    def test_responsive_media_query(self):
        css = read(STYLES_PATH)
        self.assertIn("@media", css)

    def test_focus_styles(self):
        css = read(STYLES_PATH)
        self.assertIn(":focus", css)

    def test_reduced_motion_respected(self):
        css = read(STYLES_PATH)
        self.assertIn("prefers-reduced-motion", css)

    def test_hidden_states_are_suppressed(self):
        css = read(STYLES_PATH)
        # O estado com hidden deve ser oculto mesmo com display: flex no .state.
        self.assertIn(".state[hidden]", css)


# ---------------------------------------------------------------------------
# Harness Node invocado nos testes funcionais. Rodado sem dependências extras.
# ---------------------------------------------------------------------------

NODE_HARNESS = r"""
const path = require('path');
const assert = require('assert');
const appPath = process.argv[2];
const Radar = require(appPath);

// --- Funções puras de domínio ---
function eq(a, b, msg) { assert.strictEqual(a, b, msg); }

eq(Radar.formatCount(null), 'Desconhecido');
eq(Radar.formatCount(undefined), 'Desconhecido');
eq(Radar.formatCount(''), 'Desconhecido');
eq(Radar.formatCount(0), '0');
eq(Radar.formatCount(69), '69');
eq(Radar.formatText(null), 'Desconhecido');
eq(Radar.formatText(''), 'Desconhecido');
eq(Radar.formatText('X'), 'X');
eq(Radar.formatDate(null), 'Desconhecido');
eq(Radar.formatDate('2026-07-10'), '10/07/2026');
eq(Radar.formatDate('2026-07-30'), '30/07/2026');
eq(Radar.formatVerifiedAt(null), 'Desconhecido');
eq(Radar.formatVerifiedAt('2026-10-09T18:00:00+00:00'), '2026-10-09T18:00:00+00:00');

eq(Radar.isHttpsUrl('https://example.com'), true);
eq(Radar.isHttpsUrl('http://example.com'), false);
eq(Radar.isHttpsUrl('javascript:alert(1)'), false);
eq(Radar.isHttpsUrl('ftp://example.com'), false);
eq(Radar.isHttpsUrl(null), false);
eq(Radar.isHttpsUrl(undefined), false);
eq(Radar.isHttpsUrl(123), false);

// --- DOM de falso (lança se innerHTML for tocado) ---
function makeDoc() {
  function makeEl(tag) {
    const el = {
      tagName: String(tag).toUpperCase(),
      children: [],
      attrs: Object.create(null),
      _text: '',
      _classes: [],
    };
    el.appendChild = function (c) { el.children.push(c); return c; };
    el.addEventListener = function () { return undefined; };
    el.setAttribute = function (k, v) { el.attrs[k] = String(v); };
    el.getAttribute = function (k) {
      return Object.prototype.hasOwnProperty.call(el.attrs, k) ? el.attrs[k] : null;
    };
    const classList = {
      add: function () {
        for (let i = 0; i < arguments.length; i++) {
          const n = arguments[i];
          if (el._classes.indexOf(n) === -1) el._classes.push(n);
        }
      },
      remove: function (n) { el._classes = el._classes.filter(function (c) { return c !== n; }); },
      contains: function (n) { return el._classes.indexOf(n) !== -1; },
    };
    el.classList = classList;
    Object.defineProperty(el, 'href', {
      get: function () { return el.attrs.href || ''; },
      set: function (v) { el.attrs.href = String(v); },
    });
    Object.defineProperty(el, 'textContent', {
      get: function () { return el._text; },
      set: function (v) { el._text = String(v == null ? '' : v); },
    });
    Object.defineProperty(el, 'className', {
      get: function () { return el._classes.join(' '); },
      set: function (v) { el._classes = String(v).split(/\s+/).filter(Boolean); },
    });
    Object.defineProperty(el, 'innerHTML', {
      get: function () { throw new Error('innerHTML accessed in render path'); },
      set: function () { throw new Error('innerHTML used in render path'); },
    });
    return el;
  }
  return { createElement: makeEl };
}

function collectDlPairs(root) {
  const out = [];
  (function walk(el) {
    if (!el || !el.children) return;
    if (el.tagName === 'DL') {
      const kids = el.children;
      for (let i = 0; i < kids.length; i++) {
        if (kids[i].tagName === 'DT' && kids[i + 1] && kids[i + 1].tagName === 'DD') {
          out.push([kids[i].textContent, kids[i + 1].textContent]);
        }
      }
    }
    el.children.forEach(walk);
  })(root);
  return out;
}

function collectAnchors(root) {
  const out = [];
  (function walk(el) {
    if (!el || !el.children) return;
    if (el.tagName === 'A') out.push(el);
    el.children.forEach(walk);
  })(root);
  return out;
}

function flattenText(el) {
  if (!el) return '';
  let s = el._text || '';
  (el.children || []).forEach(function (c) { s += ' ' + flattenText(c); });
  return s;
}

// --- Renderização de um registro ---
const doc = makeDoc();
const record = {
  competition_id: '001/2026',
  competition: 'Concurso Público de Teste',
  agency: 'Prefeitura de Teste',
  role: 'Professor',
  education: null,
  immediate_vacancies: 0,
  reserve_vacancies: null,
  indigenous_vacancies: 3,
  registration_start: '2026-07-10',
  registration_end: '2026-07-30',
  registration_status: 'Encerradas',
  exam_date: null,
  exam_location: 'Sala A',
  work_location: 'Porto Velho',
  source_name: 'Prefeitura Oficial',
  source_url: 'https://guajaramirim.ro.gov.br/',
  evidence_url: null,
  verified_at: '2026-10-09T18:00:00+00:00',
};

const root = Radar.renderRecordCard(doc, record);
const pairs = collectDlPairs(root);
const map = {};
pairs.forEach(function (p) { map[p[0]] = p[1]; });

eq(map['Vagas imediatas'], '0', 'zero deve ser preservado');
eq(map['Cadastro de reserva'], 'Desconhecido', 'null deve virar Desconhecido');
eq(map['Vagas indígenas'], '3');
eq(map['Local de prova'], 'Sala A', 'local de prova distinto');
eq(map['Local de exercício'], 'Porto Velho', 'local de exercício distinto');
eq(map['Escolaridade'], 'Desconhecido');
eq(map['Data da prova'], 'Desconhecido');
eq(map['Artigo consultado em'], '2026-10-09T18:00:00+00:00');

const anchors = collectAnchors(root);
assert.ok(anchors.some(function (a) { return a.getAttribute('href') === record.source_url; }), 'fonte https deve ser link');
assert.ok(anchors.every(function (a) { return /noopener/.test(a.getAttribute('rel') || ''); }), 'link deve ter rel seguro');
assert.ok(!anchors.some(function (a) { return a.getAttribute('href') === record.evidence_url; }), 'evidência null não deve ser link');
assert.ok(flattenText(root).indexOf('Evidência') !== -1, 'rótulo Evidência presente');

// Vulnerabilidades (javascript:) nunca viram href.
const bad = Object.assign({}, record, {
  source_url: 'javascript:alert(1)',
  evidence_url: 'https://e.gov/edital.pdf',
});
const root2 = Radar.renderRecordCard(doc, bad);
const anchors2 = collectAnchors(root2);
assert.ok(!anchors2.some(function (a) { const h = a.getAttribute('href') || ''; return h.indexOf('javascript') !== -1; }), 'scheme hostil não pode virar link');
assert.ok(anchors2.some(function (a) { return a.getAttribute('href') === 'https://e.gov/edital.pdf'; }), 'evidência https deve ser link');

// renderList limpa e populariza o contêiner sem innerHTML.
const list = doc.createElement('ul');
Radar.renderList(doc, [record], list);
assert.strictEqual(list.children.length, 1, 'renderList deve popular o contêiner');

const documentDetails = Radar.renderDocumentDetails(doc, {
  coverage: {state: 'nao_auditada'},
  documents: [{kind:'edital', title:'<img src=x onerror=alert(1)>', official_url:'http://evil.test/pdf',
    state:'baixado', versions:[{id:'v1', extraction_state:'parcial'}], download_attempts:[]}],
  proposals: [{field_name:'immediate_vacancies', value:10, state:'extraido',
    evidence:{quote:'10 vagas imediatas', version_id:'v1'}}], current_values:[]
});
assert.ok(flattenText(documentDetails).includes('Não auditada'), 'cobertura não confirmada');
assert.ok(flattenText(documentDetails).includes('10 vagas imediatas'), 'citação visível');
assert.ok(flattenText(documentDetails).includes('v1'), 'versão visível');
assert.ok(flattenText(documentDetails).includes('<img src=x onerror=alert(1)>'), 'texto hostil não executado');
assert.strictEqual(collectAnchors(documentDetails).length, 0, 'URL HTTP não vira link');

const selectedDetails = Radar.renderDocumentDetails(doc, {
  coverage:{state:'parcial'}, documents:[], proposals:[],
  current_values:[
    {id:'old', field_name:'immediate_vacancies', active:false, evidence:{quote:'10 vagas', version_id:'v1'}},
    {id:'new', field_name:'immediate_vacancies', active:true, evidence:{quote:'12 vagas', version_id:'v2'}}
  ]
});
assert.ok(flattenText(selectedDetails).includes('Valor vigente'), 'seleção humana válida deve ficar visível');
assert.ok(flattenText(selectedDetails).includes('12 vagas'), 'evidência da seleção deve ficar visível');
assert.ok(flattenText(selectedDetails).includes('Seleção histórica'), 'seleção substituída não deve parecer vigente');

// Painel de inteligência: conflitos, reconciliações, vínculos e proveniência.
const richDetails = Radar.renderDocumentDetails(doc, {
  coverage: {state: 'parcial'},
  roles: [{id: 'role-1', name: 'Professor de Educação Infantil'}],
  role_reconciliations: [{label: 'Prof. Nivel II Infantil', role_id: 'role-1'}],
  documents: [
    {id: 'doc-edital', kind: 'edital', document_type: 'edital_abertura', title: 'Edital 001', official_url: 'https://g.gov/e.pdf',
     state: 'baixado', versions: [{id: 'ver-edital', extraction_state: 'parcial'}], related_document_ids: []},
    {id: 'doc-retif', kind: 'retificacao', title: 'Retificação 001', official_url: 'https://g.gov/r.pdf',
     state: 'baixado', versions: [{id: 'ver-retif', extraction_state: 'parcial'}], related_document_ids: ['doc-edital']}
  ],
  proposals: [{id: 'p1', field_name: 'immediate_vacancies', value: 107, state: 'extraido',
    evidence: {quote: '107 vagas', version_id: 'ver-edital', document_id: 'doc-edital'}}],
  current_values: [],
  conflicts: [{field_name: 'indigenous_vacancies', scope_type: 'contest', role_id: null, scope_label: null,
    values: [
      {proposal_id: 'p1', value: 3, version_id: 'ver-edital', document_id: 'doc-edital'},
      {proposal_id: 'p2', value: 4, version_id: 'ver-retif', document_id: 'doc-retif'}
    ]},
    {field_name: 'immediate_vacancies', scope_type: 'role', role_id: 'role-1', scope_label: null,
    values: [
      {proposal_id: 'p3', value: 69, version_id: 'ver-edital', document_id: 'doc-edital'},
      {proposal_id: 'p4', value: 70, version_id: 'ver-retif', document_id: 'doc-retif'}
    ]}]
});
const richText = flattenText(richDetails);
assert.ok(richText.includes('Conflito'), 'conflito sinalizado');
assert.ok(richText.includes('indigenous_vacancies'), 'campo em conflito visível');
assert.ok(richText.includes('Professor de Educação Infantil'), 'cargo reconciliado e escopo do conflito visível');
assert.ok(richText.includes('Escopo do concurso'), 'escopo do concurso rotulado');
assert.ok(richText.includes('Edital 001') && richText.includes('Retificação 001'), 'origem do conflito pelo título do documento');
assert.ok(richText.includes('Reconciliação de cargos'), 'seção de reconciliação presente');
assert.ok(richText.includes('Professor de Educação Infantil'), 'cargo reconciliado visível');
assert.ok(richText.includes('Vinculado a'), 'vínculo entre documentos visível');
assert.ok(richText.includes('Documento doc-edit') || richText.includes('doc-edital') || richText.includes('Documento doc-'), 'documento de origem da evidência identificável');
assert.ok(richText.includes('Edital de abertura'), 'tipo documental fino exibido (edital de abertura)');

// Painel de monitoramento: distingue nova publicação de alteração técnica.
const monitoring = Radar.renderMonitoring(doc, {
  last_cycle: {id: 'c1', state: 'concluido', started_at: '2026-10-15T12:00:00+00:00',
    finished_at: '2026-10-15T12:01:00+00:00', documents_found: 3, documents_new: 1,
    versions_new: 2, changes_pending: 2},
  sources: [{source_url: 'https://guajaramirim.ro.gov.br/artigo/', state: 'concluido',
    checked_at: '2026-10-15T12:00:30+00:00', last_success_at: '2026-10-14T12:00:00+00:00',
    http_status: null, error_code: null, documents_found: 3, documents_new: 1,
    versions_new: 2, changes_pending: 2, coverage_state: 'nao_auditada',
    summary: {documents_found: 3, documents_new: 1, versions_new: 2, changes: 1, errors: []}}],
  pending_analysis: 2, coverage_state: 'nao_auditada'
});
const mtext = flattenText(monitoring);
assert.ok(mtext.includes('Nova publicação'), 'nova publicação sinalizada');
assert.ok(mtext.includes('Alteração em documento conhecido'), 'alteração técnica distinta da publicação');
assert.ok(mtext.includes('Alteração em documento conhecido: 1'), 'alerta de alteração usa changes, não versions_new');
assert.ok(!mtext.includes('Alteração em documento conhecido: 2'), 'versão de documento novo não conta como alteração');
assert.ok(mtext.includes('Última verificação'), 'última verificação visível');
assert.ok(mtext.includes('Cobertura ainda não verificada'), 'cobertura não verificada visível');
assert.ok(mtext.includes('Último sucesso'), 'último sucesso preservado visível');
assert.strictEqual(collectAnchors(monitoring).length, 1, 'fonte https vira link único');

// Ciclo com falha não pode sugerir sucesso ("sem novidades").
const failedCycle = Radar.renderMonitoring(doc, {
  last_cycle: {id: 'c2', state: 'falhou', started_at: '2026-10-16T01:32:50+00:00',
    finished_at: '2026-10-16T01:32:50+00:00', documents_found: 0, documents_new: 0,
    versions_new: 0, changes_pending: 0},
  sources: [{source_url: 'https://guajaramirim.ro.gov.br/artigo/', state: 'falhou',
    checked_at: '2026-10-16T01:32:50+00:00', last_success_at: null, http_status: null,
    error_code: 'TimeoutError', documents_found: 0, documents_new: 0, versions_new: 0,
    changes_pending: 0, coverage_state: 'nao_auditada', summary: {changes: 0}}],
  pending_analysis: 0, coverage_state: 'nao_auditada'
});
const ftext = flattenText(failedCycle);
assert.ok(!ftext.includes('Nenhuma publicação nova ou alteração'), 'falha não pode parecer "sem novidades"');
assert.ok(ftext.includes('Verificação incompleta'), 'falha de fonte sinalizada');
assert.ok(ftext.includes('Falhou'), 'estado da fonte falha visível');

// Ciclo parcial sem fonte falha ainda é verificação incompleta (sem silêncio).
const partialCycle = Radar.renderMonitoring(doc, {
  last_cycle: {id: 'c3', state: 'parcial', started_at: '2026-10-16T02:00:00+00:00',
    finished_at: '2026-10-16T02:01:00+00:00', documents_found: 1, documents_new: 0,
    versions_new: 0, changes_pending: 0},
  sources: [{source_url: 'https://g.gov/artigo/', state: 'parcial', checked_at: '2026-10-16T02:00:30+00:00',
    last_success_at: null, http_status: null, error_code: null, documents_found: 1, documents_new: 0,
    versions_new: 0, changes_pending: 0, coverage_state: 'nao_auditada',
    summary: {changes: 0, errors: [{document_id: 'd1', error_code: 'TimeoutError'}]}}],
  pending_analysis: 0, coverage_state: 'nao_auditada'
});
const ptext = flattenText(partialCycle);
assert.ok(ptext.includes('Verificação incompleta'), 'ciclo parcial exige aviso de verificação incompleta');
assert.ok(!ptext.includes('Nenhuma publicação nova ou alteração'), 'ciclo parcial não pode parecer "sem novidades"');
assert.ok(ptext.includes('Falhas parciais'), 'erros parciais da fonte são visíveis');

// Ciclo em andamento não pode sugerir sucesso.
const runningCycle = Radar.renderMonitoring(doc, {
  last_cycle: {id: 'c4', state: 'em_andamento', started_at: '2026-10-16T03:00:00+00:00',
    finished_at: null, documents_found: 0, documents_new: 0, versions_new: 0, changes_pending: 0},
  sources: [], pending_analysis: 0, coverage_state: 'nao_auditada'
});
const rtext = flattenText(runningCycle);
assert.ok(!rtext.includes('Nenhuma publicação nova ou alteração'), 'ciclo em andamento não é "sem novidades"');
assert.ok(rtext.includes('Verificação incompleta'), 'ciclo em andamento exige aviso');
assert.ok(rtext.includes('ainda está em andamento'), 'redação de ciclo em andamento é precisa');

// Estado de extração legível (enum cru não deve aparecer).
const extDetails = Radar.renderDocumentDetails(doc, {
  coverage: {state: 'nao_auditada'},
  documents: [{kind: 'edital', title: 'Doc', official_url: 'https://g.gov/e.pdf', state: 'baixado',
    versions: [{id: 'v9', extraction_state: 'nao_iniciada'}], download_attempts: []}],
  proposals: [], current_values: []
});
const extText = flattenText(extDetails);
assert.ok(extText.includes('Não iniciada'), 'estado de extração exibido em português');
assert.ok(!extText.includes('nao_iniciada'), 'enum cru de extração não aparece');

// Campo com rótulo legível + chave técnica preservada.
assert.ok(richText.includes('Vagas indígenas'), 'rótulo legível do campo visível');
assert.ok(richText.includes('indigenous_vacancies'), 'chave técnica do campo preservada');

const emptyMonitoring = Radar.renderMonitoring(doc, {last_cycle: null, sources: [],
  pending_analysis: 0, coverage_state: 'nao_auditada'});
assert.ok(flattenText(emptyMonitoring).includes('ainda não executado'), 'sem ciclo é explícito');

// Alertas persistentes: rótulo humano, severidade e dedupe visível.
const alerts = Radar.renderAlerts(doc, {alerts: [
  {id: 'a1', kind: 'prazo_isencao', severity: 'atencao', title: 'Isenção da taxa proximo',
   detail: 'Fim da solicitação: 2026-10-20', created_at: '2026-10-16T12:00:00+00:00'},
  {id: 'a2', kind: 'falha_fonte', severity: 'critico', title: 'Fonte indisponível',
   detail: 'TimeoutError', created_at: '2026-10-16T12:01:00+00:00'}
], counts: {total: 2, unseen: 2}});
const alertsText = flattenText(alerts);
assert.ok(alertsText.includes('Prazo de isenção'), 'tipo de alerta com rótulo humano');
assert.ok(alertsText.includes('Fonte indisponível'), 'alerta de fonte exibido');
assert.ok(alertsText.includes('não visto'), 'contagem de não vistos exibida');
assert.ok(!alertsText.includes('prazo_isencao'), 'enum cru do alerta não aparece');

const emptyAlerts = Radar.renderAlerts(doc, {alerts: [], counts: {total: 0, unseen: 0}});
assert.ok(flattenText(emptyAlerts).includes('Nenhum alerta'), 'sem alertas é explícito');

// Atualização periódica: intervalo padrão conservador (sem body configurado → 60 s).
eq(Radar.autoRefreshSeconds(), 60, 'intervalo padrão de atualização');

// Central de triagem: agrupa por concurso, urgência por data documentada e ações.
const triage = Radar.renderTriage(doc, {
  counts: {total: 4, unseen: 3},
  groups: [
    {contest_id: 'contest-abc', urgency: 'hoje', alert_count: 1, exemption_end: '2026-10-15',
     sources: ['PCI'], alerts: [
       {id: 't1', kind: 'prazo_isencao', severity: 'critico', title: 'Isenção expirada',
        detail: 'Fim: 2026-10-15', created_at: '2026-10-16T12:00:00+00:00'}]},
    {contest_id: 'contest-def', urgency: 'proximos', alert_count: 2, exemption_end: null,
     sources: [], alerts: [
       {id: 't2', kind: 'retificacao', severity: 'atencao', title: 'Retificação publicada',
        detail: null, created_at: '2026-10-16T12:01:00+00:00'}]},
    {contest_id: null, urgency: 'falhas', alert_count: 1, exemption_end: null,
     sources: ['Dou'], alerts: [
       {id: 't3', kind: 'falha_fonte', severity: 'atencao', title: 'Fonte indisponível',
        detail: 'TimeoutError', created_at: '2026-10-16T12:02:00+00:00'}]}
  ]
});
const ttext = flattenText(triage);
assert.ok(ttext.includes('Ação necessária hoje'), 'bucket de urgência imediata rotulado');
assert.ok(ttext.includes('Prazos próximos'), 'bucket de prazos próximos rotulado');
assert.ok(ttext.includes('Falhas de coleta'), 'bucket de falhas rotulado');
assert.ok(ttext.includes('Sem concurso identificado'), 'alerta sem concurso é explicitado, não fundido');
assert.ok(ttext.includes('Sem prazo documentado'), 'prazo desconhecido é explícito (não finge expirado)');
assert.ok(ttext.includes('3 evento(s)') || ttext.includes('evento(s)'), 'contagem de eventos exibida');
assert.ok(ttext.includes('não visto'), 'resumo de não vistos exibido');
assert.ok(ttext.includes('Marcar visto') && ttext.includes('Adiar 1 dia') && ttext.includes('Dispensar'),
  'ações da triagem presentes');
assert.ok(ttext.includes('Abrir concurso'), 'navegação para o concurso presente');
assert.ok(!ttext.includes('prazo_isencao') && !ttext.includes('falha_fonte'),
  'enum cru de alerta não vaza na triagem');
assert.strictEqual(collectAnchors(triage).length, 2, 'somente grupos com contest_id geram link');

const emptyTriage = Radar.renderTriage(doc, {groups: [], counts: {total: 0, unseen: 0}});
assert.ok(flattenText(emptyTriage).includes('Nenhum alerta'), 'triagem vazia é explícita');

// Priorização: rótulos, prova x lotação, distância honesta e desconhecido explícito.
const prio = Radar.renderPriorities(doc, {items: [
  {contest_id: 'c1', score: 14, max_score: 17, coverage: 0.82, label: 'boa_aderencia',
   label_text: 'Boa aderência atual', exceptional: false,
   indigenous_immediate: 3, indigenous_reserve: null,
   si_compatibility: {state: 'aceito_expressamente', value: 'aceito_expressamente'},
   location: {prova: {state: 'confirmado_documentalmente', uf: 'BA', municipios: ['Salvador']},
              lotacao: {state: 'nao_informado', uf: null, municipios: []}},
   distance: {known: true, distance_km: 12.5, kind: 'geografica_linha_reta', reason: null},
   urgency: null,
   factors: [{key: 'compatibilidade_si', points: 4, max: 4, known: true,
              reason: 'o edital cita expressamente Sistemas de Informação'},
             {key: 'vagas_indigenas_reserva', points: null, max: 2, known: false,
              reason: 'cadastro de reserva indígena não informado'}]},
  {contest_id: 'c2', score: 11, max_score: 17, coverage: 0.6, label: 'oportunidade_importante_distante',
   label_text: 'Oportunidade importante (distante)', exceptional: true,
   indigenous_immediate: 12, indigenous_reserve: 2,
   si_compatibility: {state: 'aceito_expressamente', value: 'aceito_expressamente'},
   location: {prova: {state: 'extraido_nao_revisado', uf: 'AM', municipios: ['Manaus']},
              lotacao: {state: 'nao_informado', uf: null, municipios: []}},
   distance: {known: true, distance_km: 2900.0, kind: 'geografica_linha_reta', reason: null},
   urgency: null, factors: []},
  {contest_id: 'c3', score: 4, max_score: 17, coverage: 0.3, label: 'sem_dados_suficientes',
   label_text: 'Sem dados suficientes', exceptional: false,
   indigenous_immediate: null, indigenous_reserve: null,
   si_compatibility: {state: 'nao_extraido', value: null},
   location: {prova: {state: 'nao_informado', uf: null, municipios: []},
              lotacao: {state: 'nao_informado', uf: null, municipios: []}},
   distance: {known: false, distance_km: null, kind: 'geografica_linha_reta',
              reason: 'município/UF de destino não confirmados'},
   urgency: {kind: 'exemption_end', state: 'expirado', days: -5, date: '2020-01-01'}, factors: []}
]});
const prioText = flattenText(prio);
assert.ok(prioText.includes('Boa aderência atual'), 'rótulo legível da prioridade');
assert.ok(prioText.includes('Oportunidade importante (distante)'), 'oportunidade distante visível');
assert.ok(prioText.includes('excepcional'), 'marca de excepcional visível');
assert.ok(prioText.includes('linha reta'), 'distância identificada como linha reta');
assert.ok(prioText.includes('Distância desconhecida'), 'distância desconhecida explícita');
assert.ok(prioText.includes('Salvador/BA'), 'prova exibida');
assert.ok(prioText.includes('Lotação'), 'lotação exibida separada da prova');
assert.ok(prioText.includes('desconhecido'), 'fator desconhecido explicitado');
assert.ok(prioText.includes('Cadastro de reserva indígena'), 'reserva separada das imediatas');
assert.ok(!prioText.includes('distância rodoviária') && !prioText.includes('km rodovi'),
  'nunca apresenta distância rodoviária como valor');
assert.ok(!prioText.includes('probabilidade') && !prioText.includes('chance de'), 'sem falsa probabilidade');
assert.ok(prioText.includes('prazo expirado'), 'urgência exibida à parte');
assert.strictEqual(collectAnchors(prio).length, 3, 'um link de concurso por item');

// Estudos: relógio formatado e painel derivado de dados persistidos.
eq(Radar.formatClock(0), '00:00:00');
eq(Radar.formatClock(59), '00:00:59');
eq(Radar.formatClock(3661), '01:01:01');
eq(Radar.formatClock(-5), '00:00:00');

const study = Radar.renderStudy(doc, {
  disciplinas: 1, topicos: 2, total_segundos: 3661, semana_segundos: 1800,
  sessoes_concluidas: 3, revisoes_pendentes: 1,
  conteudo: {overall: {done: 1, total: 2, pct: 50}},
  minutos_por_disciplina: [{disciplina_id: 'd1', nome: 'TI', minutos: 61}],
  revisoes: [{progresso_id: 'p-abc12345', data: '2026-01-02'}],
  lista_disciplinas: [{id: 'd1', nome: 'TI', topicos: [
    {id: 't1', nome: 'Redes', state: 'concluido'},
    {id: 't2', nome: 'Banco', state: 'nao_iniciado'}]}]
});
const studyText = flattenText(study);
assert.ok(studyText.includes('TI'), 'disciplina exibida');
assert.ok(studyText.includes('Redes') && studyText.includes('Banco'), 'tópicos exibidos');
assert.ok(studyText.includes('50%'), 'progresso derivado dos dados');
assert.ok(studyText.includes('01:01:01'), 'tempo total formatado');
assert.ok(studyText.includes('Revisões pendentes'), 'revisões pendentes exibidas');
assert.ok(!studyText.includes('innerHTML'), 'render sem innerHTML');

// Preparação: cobertura, conteúdo, estados e lacunas.
const prep = Radar.renderPrep(doc, {
  coverage_state: 'extraido_nao_revisado',
  topicos: [
    {value: 'Redes de computadores', disciplina: 'INFORMÁTICA', estado: 'extraido_nao_revisado',
     page_number: 3, conceito_key: 'informatica::redes'},
    {value: 'Banco de dados', disciplina: 'INFORMÁTICA', estado: 'confirmado',
     page_number: 3, conceito_key: 'informatica::banco'}]
}, {coverage: {pct: 50, denominator: 2, basis: 'cobertura sobre 2 tópico(s) identificado(s)',
    counts: {identificados: 2, confirmados: 1, conhecidos: 1, nao_conhecidos: 0, revisar: 0}},
   gaps: [{rotulo: 'Banco de dados', disciplina: 'INFORMÁTICA', nivel: 'nao_avaliado'}],
   coverage_state: 'extraido_nao_revisado'});
const prepText = flattenText(prep);
assert.ok(prepText.includes('50%'), 'cobertura exibida');
assert.ok(prepText.includes('não revisado'), 'estado do conteúdo exibido');
assert.ok(prepText.includes('pág. 3'), 'página da evidência exibida');
assert.ok(prepText.includes('Enviar para estudos'), 'ação de enviar lacuna');
assert.ok(prepText.includes('cobertura sobre 2'), 'denominador explicado');

const perfil = Radar.renderPerfil(doc, [
  {conceito_key: 'informatica::redes', disciplina: 'INFORMÁTICA', rotulo: 'Redes', nivel: 'basico', revisar: 0}]);
const perfilText = flattenText(perfil);
assert.ok(perfilText.includes('Redes') && perfilText.includes('Básico'), 'perfil exibido com nível');

// Prática: flashcards (resposta oculta), questões e desempenho.
const fc = Radar.renderFlashcards(doc, {fila: [
  {id: 'c1', frente: 'O que é SM-2?', verso: 'Algoritmo de repetição espaçada'}]},
  {ativos: 1, novos: 1, pendentes: 1, pct_acerto: null, basis: 'sem revisões registradas'});
const fcText = flattenText(fc);
assert.ok(fcText.includes('O que é SM-2?'), 'frente do cartão exibida');
assert.ok(fcText.includes('Resposta oculta'), 'resposta oculta antes de revelar');
assert.ok(!fcText.includes('Algoritmo de repetição espaçada'), 'verso não vaza antes da revelação');
assert.ok(fcText.includes('Mostrar resposta'), 'botão de revelar presente');

const qs = Radar.renderQuestions(doc, [{id: 'q1', enunciado: 'Quanto é 2+2?', versao: 1,
  disciplina: 'Mat', topico: 'Arit',
  alternativas: [{id: 'A', texto: '3'}, {id: 'B', texto: '4'}]}]);
const qText = flattenText(qs);
assert.ok(qText.includes('Quanto é 2+2?') && qText.includes('B) 4'), 'questão e alternativas exibidas');
assert.ok(!qText.includes('gabarito'), 'gabarito não é revelado na listagem');

const perf = Radar.renderPerformance(doc, {geral: {total: 3, acertos: 2, brancos: 1, pct: 67,
  basis: '67% sobre 2 tentativa(s) respondida(s)'}, por_disciplina: [
  {grupo: 'Mat', total: 2, acertos: 2, pct: 100}]});
const perfText = flattenText(perf);
assert.ok(perfText.includes('67% sobre 2'), 'denominador do desempenho explicado');
assert.ok(perfText.includes('Mat: 2/2'), 'desempenho por disciplina');

console.log('OK');
"""


@unittest.skipUnless(NODE, "Node não disponível no ambiente; testes funcionais do JS ignorados")
class TestAppFunctional(unittest.TestCase):
    """Comportamento funcional do app.js executado pelo Node."""

    def test_app_js_functional_behavior(self):
        self.assertTrue(os.path.exists(APP_PATH), "web/app.js deve existir")
        fd, tmp = tempfile.mkstemp(suffix=".js", prefix="radar_ui_", text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(NODE_HARNESS)
            result = subprocess.run(
                [NODE, tmp, APP_PATH],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

        if result.returncode != 0:
            self.fail(
                "Node falhou (rc=%s): stdout=%r stderr=%r"
                % (result.returncode, result.stdout, result.stderr)
            )
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
