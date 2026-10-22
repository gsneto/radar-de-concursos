/* Configurações: preferências reais do backend + preferências visuais locais. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;

  var UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
    'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];
  var PRIORITY = {equilibrado: 'Equilibrado', proximidade: 'Proximidade', prazo: 'Prazo'};

  function render(root, ctx) {
    var doc = ctx.doc;
    var seq = ctx.api.sequencer();
    var token = seq.next();
    Dom.clear(root);

    var head = Dom.el(doc, 'header', 'page-head');
    var text = Dom.el(doc, 'div', 'page-head__text');
    text.appendChild(Dom.el(doc, 'p', 'eyebrow', 'Preferências'));
    text.appendChild(Dom.el(doc, 'h2', '', 'Configurações'));
    text.appendChild(Dom.el(doc, 'p', 'page-head__sub',
      'Preferências geográficas e de prioridade são gravadas no arquivo local do Radar. ' +
      'A busca nacional continua disponível; a região apenas prioriza.'));
    head.appendChild(text);
    root.appendChild(head);

    var loading = UI.loadingRows(doc, 4);
    root.appendChild(loading);

    ctx.api.get('/api/preferencias')
      .then(function (prefs) {
        if (!seq.isCurrent(token)) return;
        loading.remove();
        root.appendChild(preferencesCard(ctx, prefs || {}));
        root.appendChild(visualCard(ctx));
        root.appendChild(aboutCard(ctx));
      })
      .catch(function (error) {
        if (!seq.isCurrent(token)) return;
        loading.remove();
        root.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Preferências indisponíveis',
          text: error.message,
          actions: [{label: 'Tentar novamente', primary: true, onClick: function () { render(root, ctx); }}]
        }));
      });
  }

  function preferencesCard(ctx, prefs) {
    var doc = ctx.doc;
    var card = UI.card(doc, {
      title: 'Preferências de busca',
      sub: 'Aplicadas à priorização da carteira, nunca à exclusão de oportunidades.'
    });
    var body = card.querySelector('.card__body');
    var form = Dom.el(doc, 'form');
    var grid = Dom.el(doc, 'div', 'form-grid');

    grid.appendChild(field(doc, 'Município de referência', input(doc, 'pref-municipio',
      prefs.reference_municipio || '', 'Ex.: Recife'), 'Opcional. Usado para distância em linha reta.'));
    var uf = select(doc, 'pref-uf', UFS.reduce(function (acc, value) {
      acc[value] = value; return acc;
    }, {}), prefs.reference_uf || '', 'Não definir');
    grid.appendChild(field(doc, 'UF de referência', uf, 'Opcional. Não restringe a busca nacional.'));
    var states = Dom.el(doc, 'input', 'input');
    states.id = 'pref-states';
    states.value = (prefs.interest_states || []).join(', ');
    grid.appendChild(field(doc, 'Estados de interesse', states,
      'Separados por vírgula. Priorizam, não eliminam.'));
    var distance = Dom.el(doc, 'input', 'input');
    distance.id = 'pref-distance';
    distance.type = 'number';
    distance.min = '0';
    distance.max = '5000';
    distance.value = prefs.practical_distance_km === null || prefs.practical_distance_km === undefined
      ? '' : String(prefs.practical_distance_km);
    grid.appendChild(field(doc, 'Distância prática (km)', distance,
      'Distância em linha reta; não é distância rodoviária.'));
    var priority = select(doc, 'pref-priority', PRIORITY, prefs.priority || 'equilibrado', '');
    grid.appendChild(field(doc, 'Prioridade', priority,
      'Muda a ordem da carteira, não os fatos.'));
    form.appendChild(grid);

    var actions = Dom.el(doc, 'div', 'form-actions');
    var save = Dom.el(doc, 'button', 'btn btn--primary', 'Salvar preferências');
    save.type = 'submit';
    var status = Dom.el(doc, 'span', 'form-status', '');
    actions.appendChild(save);
    actions.appendChild(status);
    form.appendChild(actions);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      save.disabled = true;
      status.textContent = 'Salvando…';
      status.className = 'form-status';
      var payload = {
        reference_municipio: document.getElementById('pref-municipio').value.trim() || null,
        reference_uf: document.getElementById('pref-uf').value || null,
        interest_states: document.getElementById('pref-states').value.split(',')
          .map(function (value) { return value.trim().toUpperCase(); }).filter(Boolean),
        practical_distance_km: parseInt(document.getElementById('pref-distance').value, 10) || null,
        priority: document.getElementById('pref-priority').value || 'equilibrado'
      };
      ctx.api.post('/api/preferencias', payload)
        .then(function () {
          status.textContent = 'Preferências salvas no arquivo local.';
          status.className = 'form-status form-status--ok';
          save.disabled = false;
        })
        .catch(function (error) {
          status.textContent = error.message;
          status.className = 'form-status form-status--error';
          save.disabled = false;
        });
    });
    body.appendChild(form);
    body.appendChild(Dom.el(doc, 'p', 'card__sub',
      'Persistência: arquivo de configuração local do Radar. Não há sincronização entre dispositivos.'));
    return card;
  }

  function visualCard(ctx) {
    var doc = ctx.doc;
    var card = UI.card(doc, {
      title: 'Interface', sub: 'Preferências visuais guardadas apenas neste navegador.'
    });
    var body = card.querySelector('.card__body');
    var list = Dom.el(doc, 'ul', 'list');
    var li = Dom.el(doc, 'li', 'list__item');
    var main = Dom.el(doc, 'div', 'list__main');
    main.appendChild(Dom.el(doc, 'p', 'list__title', 'Menu lateral recolhido'));
    main.appendChild(Dom.el(doc, 'p', 'list__meta',
      'A preferência é lembrada localmente e não altera os dados.'));
    li.appendChild(main);
    var aside = Dom.el(doc, 'div', 'list__aside');
    var label = Dom.el(doc, 'label', 'switch');
    var checkbox = Dom.el(doc, 'input');
    checkbox.type = 'checkbox';
    checkbox.checked = !!ctx.store.get('sidebarCollapsed', false);
    checkbox.addEventListener('change', function () {
      ctx.store.set('sidebarCollapsed', checkbox.checked);
      ctx.shell.setCollapsed(checkbox.checked);
    });
    label.appendChild(checkbox);
    label.appendChild(Dom.el(doc, 'span', '', 'Ativo'));
    aside.appendChild(label);
    li.appendChild(aside);
    list.appendChild(li);
    body.appendChild(list);
    return card;
  }

  function aboutCard(ctx) {
    var doc = ctx.doc;
    var card = UI.card(doc, {
      title: 'Sobre esta versão', sub: 'Contrato e limites do produto.'
    });
    var body = card.querySelector('.card__body');
    body.appendChild(UI.metaList(doc, [
      ['Interface', 'Radar de Concursos — frontend de produto (Fase 45)'],
      ['Dados', 'SQLite local; nenhuma confirmação automática de campo'],
      ['API', 'Contrato v1 preservado em GET /api/concursos'],
      ['Privacidade', 'Sem conta, sem telemetria e sem envio de dados para terceiros'],
      ['Operação', 'Painéis técnicos continuam em Operação']
    ]));
    var link = Dom.el(doc, 'a', 'btn btn--ghost btn--sm', 'Abrir operação');
    link.href = '#/operacao';
    link.style.marginTop = '12px';
    body.appendChild(link);
    return card;
  }

  function field(doc, label, control, hint) {
    var wrap = Dom.el(doc, 'div', 'form-field');
    var lab = Dom.el(doc, 'label', '', label);
    lab.setAttribute('for', control.id);
    wrap.appendChild(lab);
    wrap.appendChild(control);
    if (hint) wrap.appendChild(Dom.el(doc, 'small', '', hint));
    return wrap;
  }

  function input(doc, id, value, placeholder) {
    var node = Dom.el(doc, 'input', 'input');
    node.id = id;
    node.type = 'text';
    node.value = value;
    if (placeholder) node.placeholder = placeholder;
    return node;
  }

  function select(doc, id, options, value, emptyLabel) {
    var node = Dom.el(doc, 'select', 'select');
    node.id = id;
    if (emptyLabel !== null && emptyLabel !== undefined) {
      var first = Dom.el(doc, 'option', '', emptyLabel || 'Selecione');
      first.value = '';
      node.appendChild(first);
    }
    Object.keys(options).forEach(function (key) {
      var option = Dom.el(doc, 'option', '', options[key]);
      option.value = key;
      if (key === value) option.selected = true;
      node.appendChild(option);
    });
    return node;
  }

  global.RadarSettings = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
