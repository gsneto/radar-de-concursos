/* Histórico: evolução da base, ciclos e eventos documentais. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;
  var Charts = global.RadarCharts;

  var CYCLE_STATE = {
    concluido: ['Concluído', 'success'], parcial: ['Parcial', 'warning'],
    falhou: ['Falhou', 'danger'], interrompido: ['Interrompido', 'warning'],
    em_andamento: ['Em andamento', 'info']
  };
  var SOURCE_STATE = {
    concluido: ['Concluído', 'success'], parcial: ['Parcial', 'warning'],
    falhou: ['Falhou', 'danger'], nao_verificada: ['Não verificada', 'neutral']
  };
  var EVENT_LABEL = {
    descoberta: 'Descoberta', analise: 'Análise', download: 'Download', falha: 'Falha'
  };

  function render(root, ctx) {
    var doc = ctx.doc;
    var seq = ctx.api.sequencer();
    var token = seq.next();
    Dom.clear(root);

    var head = Dom.el(doc, 'header', 'page-head');
    var text = Dom.el(doc, 'div', 'page-head__text');
    text.appendChild(Dom.el(doc, 'p', 'eyebrow', 'Rastreabilidade'));
    text.appendChild(Dom.el(doc, 'h2', '', 'Histórico'));
    text.appendChild(Dom.el(doc, 'p', 'page-head__sub',
      'O que mudou na base nas últimas 24 horas, ciclo a ciclo, com documentos, versões e eventos.'));
    head.appendChild(text);
    root.appendChild(head);

    var body = Dom.el(doc, 'div');
    root.appendChild(body);
    body.appendChild(UI.loadingRows(doc, 6));

    ctx.api.get('/api/linha-do-tempo?limit=1')
      .then(function (payload) {
        if (!seq.isCurrent(token)) return;
        paint(body, ctx, payload);
      })
      .catch(function (error) {
        if (!seq.isCurrent(token)) return;
        Dom.clear(body);
        body.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Histórico indisponível',
          text: error.message,
          actions: [{label: 'Tentar novamente', primary: true, onClick: function () { render(root, ctx); }}]
        }));
      });
  }

  function paint(body, ctx, payload) {
    var doc = ctx.doc;
    Dom.clear(body);
    var novos = payload.novos || {};
    var snapshot = payload.snapshot_anterior || {};
    var kpis = Dom.el(doc, 'div', 'kpi-grid');
    kpis.appendChild(UI.kpi(doc, {
      label: 'Documentos novos (24h)', value: novos.documentos || 0, icon: 'doc', feature: true,
      sub: 'Base anterior: ' + Fmt.integer(snapshot.documentos || 0) + ' documentos'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Versões novas', value: novos.versoes || 0, icon: 'layers',
      sub: 'Conteúdo novo ou alterado identificado'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Propostas novas', value: novos.propostas || 0, icon: 'spark',
      sub: 'Extrações candidatas, sem confirmação automática'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Revisões', value: novos.revisoes || 0, icon: 'check',
      sub: 'Decisões humanas registradas no período'
    }));
    body.appendChild(kpis);

    var grid = Dom.el(doc, 'div', 'grid grid--main');
    grid.style.marginTop = '20px';
    body.appendChild(grid);

    var events = payload.eventos || {};
    var eventCard = UI.card(doc, {
      title: 'Eventos por tipo', sub: 'Contagem real no período de referência.'
    });
    var eventBody = eventCard.querySelector('.card__body');
    var keys = Object.keys(events);
    if (!keys.length) {
      eventBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'history', title: 'Nenhum evento no período',
        text: 'A base não registrou descobertas, downloads, análises ou falhas nas últimas 24 horas.'
      }));
    } else {
      eventBody.appendChild(Charts.barRows(doc, {
        ariaLabel: 'Eventos documentais por tipo',
        data: keys.sort(function (a, b) { return events[b] - events[a]; }).map(function (key) {
          return {
            label: EVENT_LABEL[key] || key, value: events[key],
            color: key === 'falha' ? 'var(--chart-4)' : 'var(--chart-1)'
          };
        })
      }));
    }
    grid.appendChild(eventCard);

    var reference = payload.referencia || {};
    var periodCard = UI.card(doc, {
      title: 'Janela de referência', sub: 'Comparação com o snapshot anterior.'
    });
    var periodBody = periodCard.querySelector('.card__body');
    periodBody.appendChild(UI.metaList(doc, [
      ['De', Fmt.dateTime(reference.desde)],
      ['Até', Fmt.dateTime(reference.ate)],
      ['Documentos', Fmt.integer(snapshot.documentos || 0) + ' → ' +
        Fmt.integer((snapshot.documentos || 0) + (novos.documentos || 0))],
      ['Versões', Fmt.integer(snapshot.versoes || 0) + ' → ' +
        Fmt.integer((snapshot.versoes || 0) + (novos.versoes || 0))],
      ['Propostas', Fmt.integer(snapshot.propostas || 0) + ' → ' +
        Fmt.integer((snapshot.propostas || 0) + (novos.propostas || 0))]
    ]));
    grid.appendChild(periodCard);

    var cycles = payload.ciclos || [];
    var cycleCard = UI.card(doc, {
      title: 'Ciclos de monitoramento', sub: 'Estado final, duração e resultado por fonte.'
    });
    var cycleBody = cycleCard.querySelector('.card__body');
    if (!cycles.length) {
      cycleBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'refresh', title: 'Nenhum ciclo registrado',
        text: 'Execute um ciclo na operação para começar o histórico.'
      }));
    } else {
      cycles.slice().reverse().forEach(function (cycle) {
        var box = Dom.el(doc, 'div', 'practice-card');
        var head = Dom.el(doc, 'div', 'practice-card__head');
        var title = Dom.el(doc, 'h4', '', 'Ciclo de ' + Fmt.dateTime(cycle.started_at));
        head.appendChild(title);
        var pair = CYCLE_STATE[cycle.state] || [cycle.state, 'neutral'];
        head.appendChild(UI.badge(doc, pair[0], pair[1]));
        box.appendChild(head);
        box.appendChild(Dom.el(doc, 'p', '',
          Fmt.integer(cycle.documents_found || 0) + ' documento(s) encontrado(s) · ' +
          Fmt.integer(cycle.documents_new || 0) + ' novo(s) · ' +
          Fmt.integer(cycle.versions_new || 0) + ' versão(ões) nova(s)'));
        var sources = Dom.el(doc, 'ul', 'list');
        (cycle.fontes || []).forEach(function (source) {
          var li = Dom.el(doc, 'li', 'list__item');
          var main = Dom.el(doc, 'div', 'list__main');
          var label = Fmt.safeUrl(source.source_url) || source.source_url;
          main.appendChild(Dom.el(doc, 'p', 'list__title', label));
          if (source.error_code) {
            main.appendChild(Dom.el(doc, 'p', 'list__meta', 'Erro: ' + source.error_code));
          }
          li.appendChild(main);
          var aside = Dom.el(doc, 'div', 'list__aside');
          var statePair = SOURCE_STATE[source.state] || [source.state, 'neutral'];
          aside.appendChild(UI.badge(doc, statePair[0], statePair[1]));
          li.appendChild(aside);
          sources.appendChild(li);
        });
        if ((cycle.fontes || []).length) box.appendChild(sources);
        cycleBody.appendChild(box);
      });
    }
    body.appendChild(cycleCard);
  }

  global.RadarHistory = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
