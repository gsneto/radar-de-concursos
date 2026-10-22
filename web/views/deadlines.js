/* Prazos: calendário real, com urgência, grupo e estado de verificação. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;

  var GROUPS = {
    inscricao_inicio: 'Início das inscrições', inscricao_fim: 'Fim das inscrições',
    isencao_inicio: 'Início da isenção', isencao_fim: 'Fim da isenção',
    recurso_isencao: 'Recurso da isenção',
    resultado_isencao_preliminar: 'Resultado preliminar da isenção',
    resultado_isencao_final: 'Resultado final da isenção',
    pagamento: 'Pagamento da taxa'
  };
  var URGENCIES = {
    hoje: 'Hoje', ate_7_dias: 'Até 7 dias', ate_30_dias: 'Até 30 dias',
    futuro: 'Futuro', vencido: 'Vencido', sem_data: 'Sem data'
  };

  function render(root, ctx) {
    var doc = ctx.doc;
    var query = ctx.query || new URLSearchParams();
    var group = query.get('group') || '';
    var urgency = query.get('urgency') || '';
    var seq = ctx.api.sequencer();
    var token = seq.next();

    Dom.clear(root);
    var head = Dom.el(doc, 'header', 'page-head');
    var text = Dom.el(doc, 'div', 'page-head__text');
    text.appendChild(Dom.el(doc, 'p', 'eyebrow', 'Calendário'));
    text.appendChild(Dom.el(doc, 'h2', '', 'Prazos'));
    text.appendChild(Dom.el(doc, 'p', 'page-head__sub',
      'Cada evento pertence a um grupo e a um documento. Data candidata não é prazo confirmado; ' +
      'datas passadas permanecem como histórico.'));
    head.appendChild(text);
    root.appendChild(head);

    var filters = Dom.el(doc, 'section', 'filters');
    filters.setAttribute('aria-label', 'Filtros de prazos');
    var row = Dom.el(doc, 'div', 'filter-row');
    var groupSelect = select(doc, 'pr-group', GROUPS, group, 'Todos os eventos');
    var urgencySelect = select(doc, 'pr-urgency', URGENCIES, urgency, 'Todas');
    row.appendChild(filterField(doc, 'Evento', groupSelect));
    row.appendChild(filterField(doc, 'Urgência', urgencySelect));
    var spacer = Dom.el(doc, 'span', 'spacer');
    row.appendChild(spacer);
    var refresh = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Atualizar');
    refresh.type = 'button';
    refresh.addEventListener('click', function () { load(); });
    row.appendChild(refresh);
    filters.appendChild(row);
    root.appendChild(filters);
    groupSelect.addEventListener('change', function () { group = groupSelect.value; load(); });
    urgencySelect.addEventListener('change', function () { urgency = urgencySelect.value; load(); });

    var summary = Dom.el(doc, 'div', 'kpi-grid');
    root.appendChild(summary);
    var results = Dom.el(doc, 'div');
    results.id = 'deadline-results';
    root.appendChild(results);

    function filterField(doc, label, control) {
      var wrap = Dom.el(doc, 'div', 'field');
      var lab = Dom.el(doc, 'label', '', label);
      lab.setAttribute('for', control.id);
      wrap.appendChild(lab);
      wrap.appendChild(control);
      return wrap;
    }

    function select(doc, id, options, value, allLabel) {
      var node = Dom.el(doc, 'select', 'select');
      node.id = id;
      var first = Dom.el(doc, 'option', '', allLabel);
      first.value = '';
      node.appendChild(first);
      Object.keys(options).forEach(function (key) {
        var option = Dom.el(doc, 'option', '', options[key]);
        option.value = key;
        if (key === value) option.selected = true;
        node.appendChild(option);
      });
      return node;
    }

    function load() {
      var tokenNow = seq.next();
      var params = new URLSearchParams();
      if (group) params.set('group', group);
      if (urgency) params.set('urgency', urgency);
      ctx.router.replaceQuery(params);
      Dom.clear(results);
      results.appendChild(UI.loadingRows(doc, 5));
      ctx.api.get('/api/prazos/calendario?limit=200&' + params.toString())
        .then(function (payload) {
          if (!seq.isCurrent(tokenNow)) return;
          paint(payload);
        })
        .catch(function (error) {
          if (!seq.isCurrent(tokenNow)) return;
          Dom.clear(results);
          results.appendChild(UI.state(doc, {
            tone: 'error', icon: 'alert', title: 'Prazos indisponíveis',
            text: error.message,
            actions: [{label: 'Tentar novamente', onClick: load}]
          }));
        });
    }

    function paint(payload) {
      Dom.clear(summary);
      var urgencia = payload.por_urgencia || {};
      summary.appendChild(UI.kpi(doc, {
        label: 'Prazos futuros', value: (urgencia.ate_7_dias || 0) + (urgencia.ate_30_dias || 0),
        icon: 'calendar', feature: true,
        sub: (urgencia.ate_7_dias || 0) + ' em até 7 dias · ' + (urgencia.hoje || 0) + ' hoje'
      }));
      summary.appendChild(UI.kpi(doc, {
        label: 'Vencidos preservados', value: urgencia.vencido || 0, icon: 'history',
        sub: 'Histórico com evidência; não são prazo vigente'
      }));
      summary.appendChild(UI.kpi(doc, {
        label: 'Sem data', value: urgencia.sem_data || 0, icon: 'empty',
        sub: 'Campo não localizado ou sem data documental'
      }));
      summary.appendChild(UI.kpi(doc, {
        label: 'Com conflito', value: (payload.por_conflito || {}).conflito || 0,
        icon: 'alert', sub: 'Documentos/versões divergentes'
      }));

      Dom.clear(results);
      var items = payload.itens || [];
      if (!items.length) {
        results.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'calendar', title: 'Nenhum prazo com esses filtros',
          text: 'Ajuste o evento ou a urgência. A ausência de prazo não significa inexistência.',
          actions: [{label: 'Limpar filtros', onClick: function () {
            group = ''; urgency = '';
            ctx.router.replaceQuery(new URLSearchParams());
            render(root, Object.assign({}, ctx, {query: new URLSearchParams()}));
          }}]
        }));
        return;
      }
      var card = UI.card(doc, {
        title: 'Eventos',
        sub: Fmt.integer(payload.total) + ' prazo(s) na referência ' +
          ((payload.referencia || {}).hoje_local || '') +
          ' (' + ((payload.referencia || {}).fuso || 'local') + ')'
      });
      var body = card.querySelector('.card__body');
      var table = Dom.el(doc, 'table', 'data-table-main');
      var thead = Dom.el(doc, 'thead');
      var headRow = Dom.el(doc, 'tr');
      ['Evento', 'Data', 'Urgência', 'Situação', 'Documento', ''].forEach(function (label) {
        headRow.appendChild(Dom.el(doc, 'th', '', label));
      });
      thead.appendChild(headRow);
      table.appendChild(thead);
      var tbody = Dom.el(doc, 'tbody');
      items.forEach(function (item) {
        var tr = Dom.el(doc, 'tr');
        var event = Dom.el(doc, 'td');
        event.setAttribute('data-label', 'Evento');
        event.appendChild(Dom.el(doc, 'span', 'cell-strong', item.grupo_label));
        if (item.escopo_rotulo) event.appendChild(Dom.el(doc, 'span', 'cell-sub', item.escopo_rotulo));
        tr.appendChild(event);
        var date = Dom.el(doc, 'td', 'cell-num');
        date.setAttribute('data-label', 'Data');
        date.appendChild(Dom.el(doc, 'span', 'cell-strong',
          item.valor ? Fmt.date(item.valor) : '—'));
        if (item.dias_restantes !== null && item.dias_restantes !== undefined) {
          date.appendChild(Dom.el(doc, 'span', 'cell-sub', Fmt.relativeDays(item.dias_restantes)));
        }
        tr.appendChild(date);
        var urgencyCell = Dom.el(doc, 'td');
        urgencyCell.setAttribute('data-label', 'Urgência');
        urgencyCell.appendChild(UI.badge(doc, item.urgencia_label || item.urgencia,
          item.urgencia === 'vencido' ? 'neutral' :
            item.urgencia === 'ate_7_dias' ? 'danger' : 'warning'));
        tr.appendChild(urgencyCell);
        var state = Dom.el(doc, 'td');
        state.setAttribute('data-label', 'Situação');
        state.appendChild(Dom.el(doc, 'span', 'cell-sub', item.estado_operacional_label));
        tr.appendChild(state);
        var source = Dom.el(doc, 'td');
        source.setAttribute('data-label', 'Documento');
        source.appendChild(Dom.el(doc, 'span', 'cell-sub',
          (item.documento || 'Não identificado') +
          (item.pagina ? ' · p. ' + item.pagina : '')));
        tr.appendChild(source);
        var action = Dom.el(doc, 'td', 'row-action');
        action.setAttribute('data-label', '');
        var link = Dom.el(doc, 'a', 'btn btn--ghost btn--sm', 'Ver concurso');
        link.href = '#/dossie/' + encodeURIComponent(item.contest_id) + '?tab=prazos';
        action.appendChild(link);
        tr.appendChild(action);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      var scroll = Dom.el(doc, 'div', 'table-wrap');
      scroll.appendChild(table);
      body.appendChild(scroll);
      body.appendChild(Dom.el(doc, 'p', 'card__sub', payload.limitacao || ''));
      results.appendChild(card);
    }

    load();
  }

  global.RadarDeadlines = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
