/* Shell do produto: sidebar, topbar, rotas, drawer móvel e operação preservada. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;
  var Api = global.RadarApi;
  var Store = global.RadarStore;

  var ROUTES = [
    {id: 'overview', path: '#/visao-geral', title: 'Visão geral', nav: 'nav-overview',
      view: function () { return global.RadarOverview; }},
    {id: 'opportunities', path: '#/oportunidades', title: 'Oportunidades', nav: 'nav-opportunities',
      view: function () { return global.RadarOpportunities; }},
    {id: 'deadlines', path: '#/prazos', title: 'Prazos', nav: 'nav-deadlines',
      view: function () { return global.RadarDeadlines; }},
    {id: 'studies', path: '#/estudos', title: 'Estudos', nav: 'nav-studies',
      view: function () { return global.RadarStudies; }},
    {id: 'history', path: '#/historico', title: 'Histórico', nav: 'nav-history',
      view: function () { return global.RadarHistory; }},
    {id: 'settings', path: '#/configuracoes', title: 'Configurações', nav: 'nav-settings',
      view: function () { return global.RadarSettings; }},
    {id: 'operation', path: '#/operacao', title: 'Operação', nav: 'nav-operation',
      view: null}
  ];

  var cleanups = [];
  var legacyReady = false;
  var currentRoute = null;

  function parseHash() {
    var raw = global.location.hash || '#/visao-geral';
    var hash = raw.slice(1) || '/visao-geral';
    var parts = hash.split('?');
    var path = parts[0] || '/visao-geral';
    var query = new URLSearchParams(parts[1] || '');
    return {path: path, query: query, raw: raw};
  }

  function routeFor(path) {
    if (path.indexOf('/dossie/') === 0) {
      var id = decodeURIComponent(path.slice('/dossie/'.length).split('/')[0] || '');
      return {id: 'dossier', title: 'Dossiê', nav: 'nav-opportunities', params: {id: id}};
    }
    for (var i = 0; i < ROUTES.length; i += 1) {
      if (ROUTES[i].path.slice(1) === path) return ROUTES[i];
    }
    return ROUTES[0];
  }

  function runCleanups() {
    while (cleanups.length) {
      var fn = cleanups.pop();
      try { fn(); } catch (error) { /* limpeza não derruba a navegação */ }
    }
  }

  function setActiveNav(route) {
    var doc = global.document;
    var items = doc.querySelectorAll('.nav__item[data-route]');
    for (var i = 0; i < items.length; i += 1) {
      if (items[i].id === route.nav) items[i].setAttribute('aria-current', 'page');
      else items[i].removeAttribute('aria-current');
    }
    var tab = parseHash().query.get('tab');
    if (route.id === 'studies') {
      var sub = doc.querySelectorAll('.nav__sub[data-tab]');
      for (var j = 0; j < sub.length; j += 1) {
        if (sub[j].getAttribute('data-tab') === (tab || 'visao')) sub[j].setAttribute('aria-current', 'page');
        else sub[j].removeAttribute('aria-current');
      }
    }
  }

  function setContext(route, query) {
    var doc = global.document;
    var title = doc.getElementById('topbar-title');
    var crumb = doc.getElementById('breadcrumb-current');
    var label = route.title;
    if (route.id === 'studies' && query.get('tab')) {
      var tabLabel = {
        visao: 'Visão geral', sessoes: 'Sessões', questoes: 'Questões',
        flashcards: 'Flashcards', simulados: 'Simulados'
      }[query.get('tab')];
      if (tabLabel) label = 'Estudos · ' + tabLabel;
    }
    if (title) title.textContent = label;
    if (crumb) crumb.textContent = label;
    doc.title = label + ' · GSN Concursos';
  }

  function replaceQuery(params) {
    var next = params.toString();
    var current = parseHash();
    var hash = '#' + current.path;
    if (next) hash += '?' + next;
    if (global.history && global.history.replaceState) {
      global.history.replaceState(null, '', hash);
    } else {
      global.location.hash = hash;
    }
    var parsed = parseHash();
    setActiveNav(routeFor(parsed.path));
    setContext(routeFor(parsed.path), parsed.query);
  }

  function navigate(hash, options) {
    if (!hash) return;
    if (global.history && global.history.pushState && (!options || !options.replace)) {
      global.history.pushState(null, '', hash);
      renderRoute();
    } else {
      global.location.hash = hash;
    }
  }

  function back() {
    if (global.history && global.history.length > 1) global.history.back();
    else navigate('#/oportunidades');
  }

  function ensureLegacy() {
    if (legacyReady) return;
    legacyReady = true;
    if (global.Radar && typeof global.Radar.init === 'function') {
      try {
        global.Radar.init();
      } catch (error) {
        var panel = global.document.getElementById('legacy-root');
        if (panel) {
          var box = UI.inlineError(global.document,
            'A operação não pôde ser inicializada: ' + (error && error.message ? error.message : 'erro'));
          panel.insertBefore(box, panel.firstChild);
        }
      }
    }
    collapseLegacy();
  }

  /* Cada painel técnico vira um bloco recolhível: a página deixa de ter dezenas de
     milhares de pixels e continua com todos os controles originais. */
  function collapseLegacy() {
    var doc = global.document;
    var root = doc.getElementById('legacy-root');
    if (!root) return;
    var sections = Array.prototype.slice.call(root.querySelectorAll(':scope > section'));
    sections.forEach(function (section, index) {
      if (section.closest('details')) return;
      var heading = section.querySelector('h2');
      var details = doc.createElement('details');
      details.className = 'legacy-block';
      if (index < 2) details.open = true;
      var summary = doc.createElement('summary');
      summary.textContent = heading ? heading.textContent
        : (section.className.indexOf('notice') >= 0 ? 'Aviso sobre os dados'
          : (section.className || 'Painel técnico'));
      details.appendChild(summary);
      section.parentNode.insertBefore(details, section);
      details.appendChild(section);
      if (heading && heading.id) details.id = heading.id + '-block';
    });
    doc.addEventListener('click', function (event) {
      var link = event.target.closest ? event.target.closest('.operation-nav a[href^="#"]') : null;
      if (!link) return;
      // Atalho interno: não troca de rota (o hash é o roteador do produto).
      event.preventDefault();
      var id = link.getAttribute('href').slice(1);
      var target = doc.getElementById(id);
      if (!target) return;
      var block = target.closest('details');
      if (block) block.open = true;
      target.scrollIntoView({block: 'start', behavior: 'auto'});
    });
  }

  function renderRoute() {
    var doc = global.document;
    var parsed = parseHash();
    var route = routeFor(parsed.path);
    var root = doc.getElementById('view-root');
    var operation = doc.getElementById('view-operation');
    var shell = doc.getElementById('app');
    if (!root || !operation) return;

    runCleanups();
    currentRoute = route;
    setActiveNav(route);
    setContext(route, parsed.query);
    closeDrawer();

    if (route.id === 'operation') {
      root.hidden = true;
      operation.hidden = false;
      ensureLegacy();
      if (global.scrollTo) global.scrollTo({top: 0, behavior: 'auto'});
      return;
    }
    operation.hidden = true;
    root.hidden = false;

    var module = route.id === 'dossier' ? global.RadarDossier : route.view();
    if (!module || typeof module.render !== 'function') {
      Dom.clear(root);
      root.appendChild(UI.state(doc, {
        tone: 'error', icon: 'alert', title: 'Tela indisponível',
        text: 'Este módulo não foi carregado. Recarregue a página.'
      }));
      return;
    }
    var ctx = {
      doc: doc,
      query: parsed.query,
      params: route.params || {},
      api: Api,
      store: Store,
      router: {
        navigate: navigate,
        replaceQuery: replaceQuery,
        back: back
      },
      shell: {
        setCollapsed: setCollapsed
      },
      reload: function () { renderRoute(); },
      addCleanup: function (fn) { cleanups.push(fn); }
    };
    try {
      module.render(root, ctx);
    } catch (error) {
      Dom.clear(root);
      root.appendChild(UI.state(doc, {
        tone: 'error', icon: 'alert', title: 'Falha ao montar a tela',
        text: error && error.message ? error.message : 'Erro inesperado.',
        actions: [{label: 'Recarregar', onClick: function () { renderRoute(); }}]
      }));
    }
    if (global.scrollTo) global.scrollTo({top: 0, behavior: 'auto'});
  }

  function setCollapsed(collapsed) {
    var shell = global.document.getElementById('app');
    var button = global.document.getElementById('sidebar-collapse');
    if (!shell) return;
    shell.classList.toggle('is-collapsed', !!collapsed);
    if (button) {
      button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      button.setAttribute('aria-label', collapsed ? 'Expandir menu' : 'Recolher menu');
      button.setAttribute('title', collapsed ? 'Expandir menu' : 'Recolher menu');
    }
    Store.set('sidebarCollapsed', !!collapsed);
  }

  function openDrawer() {
    var doc = global.document;
    doc.body.classList.add('drawer-open');
    var backdrop = doc.getElementById('drawer-backdrop');
    if (backdrop) {
      backdrop.hidden = false;
      global.requestAnimationFrame(function () { backdrop.classList.add('is-visible'); });
    }
    var button = doc.getElementById('drawer-open');
    if (button) button.setAttribute('aria-expanded', 'true');
    var close = doc.getElementById('drawer-close');
    if (close) close.focus();
  }

  function closeDrawer() {
    var doc = global.document;
    if (!doc.body.classList.contains('drawer-open')) return;
    doc.body.classList.remove('drawer-open');
    var backdrop = doc.getElementById('drawer-backdrop');
    if (backdrop) {
      backdrop.classList.remove('is-visible');
      global.setTimeout(function () { backdrop.hidden = true; }, 180);
    }
    var button = doc.getElementById('drawer-open');
    if (button) button.setAttribute('aria-expanded', 'false');
  }

  function bindChrome() {
    var doc = global.document;
    var collapse = doc.getElementById('sidebar-collapse');
    if (collapse) {
      collapse.addEventListener('click', function () {
        var shell = doc.getElementById('app');
        setCollapsed(!shell.classList.contains('is-collapsed'));
      });
    }
    var open = doc.getElementById('drawer-open');
    if (open) open.addEventListener('click', openDrawer);
    var close = doc.getElementById('drawer-close');
    if (close) close.addEventListener('click', closeDrawer);
    var backdrop = doc.getElementById('drawer-backdrop');
    if (backdrop) backdrop.addEventListener('click', closeDrawer);
    doc.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeDrawer();
    });
    doc.addEventListener('click', function (event) {
      var target = event.target.closest ? event.target.closest('a[href^="#/"]') : null;
      if (!target) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
      var href = target.getAttribute('href');
      if (!href) return;
      event.preventDefault();
      navigate(href);
    });
    global.addEventListener('popstate', renderRoute);
    global.addEventListener('hashchange', function () {
      if (!global.history || !global.history.pushState) renderRoute();
    });

    var search = doc.getElementById('global-search');
    if (search) {
      search.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') return;
        var value = search.value.trim();
        if (!value) return;
        event.preventDefault();
        navigate('#/oportunidades?q=' + encodeURIComponent(value));
        search.blur();
      });
    }

    var navItems = doc.querySelectorAll('.nav__item');
    for (var k = 0; k < navItems.length; k += 1) {
      var labelNode = navItems[k].querySelector('span:last-child');
      if (labelNode && !navItems[k].getAttribute('title')) {
        navItems[k].setAttribute('title', labelNode.textContent.trim());
      }
    }

    var icons = doc.querySelectorAll('[data-icon]');
    for (var i = 0; i < icons.length; i += 1) {
      var name = icons[i].getAttribute('data-icon');
      icons[i].appendChild(Dom.icon(doc, name, 18));
    }
    var marks = doc.querySelectorAll('[data-brand-mark]');
    for (var j = 0; j < marks.length; j += 1) {
      marks[j].appendChild(Dom.brandMark(doc, 28));
    }
  }

  function boot() {
    bindChrome();
    var collapsed = !!Store.get('sidebarCollapsed', false);
    setCollapsed(collapsed);
    if (!global.location.hash) {
      if (global.history && global.history.replaceState) {
        global.history.replaceState(null, '', '#/visao-geral');
      } else {
        global.location.hash = '#/visao-geral';
      }
    }
    renderRoute();
  }

  global.RadarShell = {
    navigate: navigate,
    replaceQuery: replaceQuery,
    renderRoute: renderRoute,
    setCollapsed: setCollapsed,
    routeFor: routeFor,
    parseHash: parseHash
  };

  if (global.document) {
    if (global.document.readyState === 'loading') {
      global.document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);
