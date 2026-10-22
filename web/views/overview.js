/* Dashboard principal: oportunidades, prazos, cobertura e estudos com dados reais. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;
  var Charts = global.RadarCharts;

  var READINESS_LABEL = {
    oportunidade_historica: 'Oportunidade histórica',
    identidade_cargo_pendente: 'Identidade pendente',
    campos_decisivos_ausentes: 'Campos ausentes',
    conflito_documental_pendente: 'Conflito documental'
  };
  var READINESS_COLOR = {
    oportunidade_historica: '#94a3b8',
    identidade_cargo_pendente: '#f59e0b',
    campos_decisivos_ausentes: '#6366f1',
    conflito_documental_pendente: '#dc2626'
  };
  var READINESS_TONE = {
    oportunidade_historica: 'neutral',
    identidade_cargo_pendente: 'warning',
    campos_decisivos_ausentes: 'info',
    conflito_documental_pendente: 'danger'
  };

  function readinessLabel(state) {
    return READINESS_LABEL[state] || String(state || 'Sem estado').replace(/_/g, ' ');
  }

  function toneFor(state) {
    return READINESS_TONE[state] || 'unknown';
  }

  function dossierHref(item) {
    var params = new URLSearchParams();
    if (item.scope) params.set('scope', item.scope);
    if (item.role_id) params.set('role_id', item.role_id);
    var query = params.toString();
    return '#/dossie/' + encodeURIComponent(item.contest_id) + (query ? '?' + query : '');
  }

  function nextDeadline(item) {
    var list = (item.prazos || []).filter(function (deadline) {
      return deadline.estado_temporal === 'futuro' && deadline.dias_restantes !== null;
    });
    list.sort(function (a, b) { return a.dias_restantes - b.dias_restantes; });
    return list[0] || null;
  }

  function priorityItem(doc, item) {
    var li = Dom.el(doc, 'li', 'list__item');
    var main = Dom.el(doc, 'div', 'list__main');
    var title = Dom.el(doc, 'a', 'list__title', item.contest_label || item.competition_id || 'Concurso');
    title.href = dossierHref(item);
    main.appendChild(title);
    var role = item.role_name || 'Cargo não reconciliado';
    var deadline = nextDeadline(item);
    var meta = role;
    if (item.localizacao && item.localizacao.prova && item.localizacao.prova.text) {
      meta += ' · ' + item.localizacao.prova.text;
    }
    main.appendChild(Dom.el(doc, 'p', 'list__meta', meta));
    var badges = Dom.el(doc, 'div', 'list__badges');
    badges.appendChild(UI.badge(doc, item.prontidao.estado_label, toneFor(item.prontidao.estado)));
    if (deadline) {
      badges.appendChild(UI.badge(doc, Fmt.relativeDays(deadline.dias_restantes), 'warning'));
    }
    if (item.si && item.si.estado && item.si.estado !== 'nao_informado') {
      badges.appendChild(UI.badge(doc, 'SI: ' + shortSi(item.si.estado),
        item.si.estado === 'explicito' ? 'success' : 'neutral'));
    }
    if (item.indigenas && item.indigenas.estado === 'explicito_imediato') {
      badges.appendChild(UI.badge(doc, shortIndigenous(item.indigenas.estado), 'accent'));
    }
    main.appendChild(badges);
    li.appendChild(main);
    var aside = Dom.el(doc, 'div', 'list__aside');
    var action = Dom.el(doc, 'a', 'list__action', 'Abrir dossiê');
    action.href = dossierHref(item);
    aside.appendChild(action);
    li.appendChild(aside);
    return li;
  }

  function shortSi(state) {
    return ({
      explicito: 'aceitação expressa',
      categoria_inclui_curso: 'categoria inclui',
      area_correlata_interpretacao: 'exige interpretação',
      outras_formacoes: 'outras formações',
      nao_informado: 'não informado'
    })[state] || String(state).replace(/_/g, ' ');
  }

  function shortOperational(state) {
    return ({
      revalidado_na_fonte: 'Fonte revalidada',
      passado_com_evidencia: 'Passado com evidência',
      conflito_documental: 'Conflito documental',
      nao_localizado: 'Não localizado',
      candidato_nao_revalidado: 'Sem verificação'
    })[state] || 'Sem verificação';
  }

  function shortIndigenous(state) {
    return ({
      explicito_imediato: 'vaga exclusiva',
      apenas_reserva: 'só reserva',
      mencao_sem_quantidade: 'menção sem quantidade',
      reserva_combinada_com_outros_grupos: 'reserva combinada',
      nao_mencionado: 'não mencionado'
    })[state] || String(state).replace(/_/g, ' ');
  }

  function deadlineItem(doc, item) {
    var li = Dom.el(doc, 'li', 'list__item');
    var date = Dom.el(doc, 'div', 'date-block');
    var parsed = new Date(item.valor + 'T12:00:00');
    date.appendChild(Dom.el(doc, 'strong', '',
      isNaN(parsed.getTime()) ? '—' : String(parsed.getDate()).padStart(2, '0')));
    date.appendChild(Dom.el(doc, 'span', '',
      isNaN(parsed.getTime()) ? '' : parsed.toLocaleDateString('pt-BR', {month: 'short'})));
    li.appendChild(date);
    var main = Dom.el(doc, 'div', 'list__main');
    main.appendChild(Dom.el(doc, 'p', 'list__title', item.grupo_label));
    main.appendChild(Dom.el(doc, 'p', 'list__meta',
      (item.documento || 'Documento não identificado') +
      (item.pagina ? ' · p. ' + item.pagina : '')));
    var badges = Dom.el(doc, 'div', 'list__badges');
    badges.appendChild(UI.badge(doc, Fmt.relativeDays(item.dias_restantes),
      item.urgencia === 'ate_7_dias' ? 'danger' : 'warning'));
    badges.appendChild(UI.badge(doc, shortOperational(item.estado_operacional),
      item.estado_operacional === 'conflito_documental' ? 'danger' : 'neutral'));
    main.appendChild(badges);
    li.appendChild(main);
    var aside = Dom.el(doc, 'div', 'list__aside');
    var link = Dom.el(doc, 'a', 'list__action', 'Ver concurso');
    link.href = '#/dossie/' + encodeURIComponent(item.contest_id);
    aside.appendChild(link);
    li.appendChild(aside);
    return li;
  }

  function buildHeader(doc) {
    var head = Dom.el(doc, 'header', 'page-head');
    var text = Dom.el(doc, 'div', 'page-head__text');
    text.appendChild(Dom.el(doc, 'p', 'eyebrow', 'Painel'));
    text.appendChild(Dom.el(doc, 'h2', '', 'Visão geral'));
    text.appendChild(Dom.el(doc, 'p', 'page-head__sub',
      'Oportunidades monitoradas, prazos que merecem atenção e o retrato real da cobertura documental. ' +
      'Nenhum campo é confirmado automaticamente.'));
    head.appendChild(text);
    var actions = Dom.el(doc, 'div', 'page-head__actions');
    var chip = Dom.el(doc, 'span', 'date-chip');
    chip.appendChild(Dom.icon(doc, 'calendar', 15));
    chip.appendChild(Dom.el(doc, 'span', '', Fmt.longToday()));
    actions.appendChild(chip);
    var cta = Dom.el(doc, 'a', 'btn btn--primary', 'Explorar oportunidades');
    cta.href = '#/oportunidades';
    actions.appendChild(cta);
    head.appendChild(actions);
    return head;
  }

  function render(root, ctx) {
    var doc = ctx.doc;
    Dom.clear(root);
    root.appendChild(buildHeader(doc));

    var dashboard = Dom.el(doc, 'div', 'dashboard');
    root.appendChild(dashboard);

    var kpiGrid = Dom.el(doc, 'div', 'kpi-grid');
    dashboard.appendChild(kpiGrid);

    var mainGrid = Dom.el(doc, 'div', 'grid grid--main');
    dashboard.appendChild(mainGrid);
    var activityCard = UI.card(doc, {
      id: 'card-activity', title: 'Atividade documental',
      sub: 'Novas versões identificadas em cada ciclo de monitoramento.'
    });
    mainGrid.appendChild(activityCard);

    var coverageCard = UI.card(doc, {
      id: 'card-coverage', title: 'Cobertura documental',
      sub: 'Do universo de concursos até o primeiro campo confirmado.',
      link: {label: 'Ver cobertura', href: '#/operacao'}
    });
    mainGrid.appendChild(coverageCard);

    var midGrid = Dom.el(doc, 'div', 'grid grid--2');
    dashboard.appendChild(midGrid);
    var priorityCard = UI.card(doc, {
      id: 'card-priority', title: 'Oportunidades prioritárias',
      sub: 'Ordenadas pela política operacional do servidor, com o motivo em destaque.',
      link: {label: 'Ver todas', href: '#/oportunidades'}
    });
    midGrid.appendChild(priorityCard);
    var deadlineCard = UI.card(doc, {
      id: 'card-deadlines', title: 'Prazos próximos',
      sub: 'Somente datas futuras com documento e estado de verificação.',
      link: {label: 'Calendário', href: '#/prazos'}
    });
    midGrid.appendChild(deadlineCard);

    var bottomGrid = Dom.el(doc, 'div', 'grid grid--2');
    dashboard.appendChild(bottomGrid);
    var readinessCard = UI.card(doc, {
      id: 'card-readiness', title: 'Carteira por prontidão',
      sub: 'Cada oportunidade tem um estado determinístico e explicado.'
    });
    bottomGrid.appendChild(readinessCard);
    var studyCard = UI.card(doc, {
      id: 'card-study', title: 'Estudos',
      sub: 'Tempo, sessões e revisões registrados por você.',
      link: {label: 'Abrir estudos', href: '#/estudos'}
    });
    bottomGrid.appendChild(studyCard);

    var state = {
      carteira: null, cobertura: null, timeline: null, estudos: null, prazos: null
    };
    var errors = {};

    function paintKpis() {
      Dom.clear(kpiGrid);
      var portfolio = state.carteira || {};
      var cobertura = state.cobertura || {};
      var escopo = cobertura.escopo || {};
      var urgency = portfolio.por_urgencia || {};
      var ate7 = Number(urgency.ate_7_dias || 0);
      var ate30 = Number(urgency.ate_30_dias || 0);
      var readiness = portfolio.por_prontidao || {};
      var segments = Object.keys(readiness).map(function (key) {
        return {
          key: key, label: readinessLabel(key), value: readiness[key],
          color: READINESS_COLOR[key] || '#94a3b8',
          pct: portfolio.total ? (readiness[key] / portfolio.total) * 100 : 0
        };
      }).sort(function (a, b) { return b.value - a.value; });

      kpiGrid.appendChild(UI.kpi(doc, {
        label: 'Oportunidades na carteira', value: portfolio.total,
        icon: 'target', feature: true,
        sub: ate7 + ate30 > 0
          ? Fmt.integer(ate7 + ate30) + ' com prazo nos próximos 30 dias · ' +
            Fmt.integer(ate7) + ' em até 7 dias'
          : 'Nenhum prazo futuro registrado para as oportunidades atuais.',
        mini: segments.length ? UI.stacked(doc, segments) : null
      }));
      kpiGrid.appendChild(UI.kpi(doc, {
        label: 'Concursos monitorados', value: escopo.concursos, icon: 'layers',
        sub: Fmt.integer(escopo.com_edital_analisado || 0) +
          ' com edital oficial analisado · ' + Fmt.integer(escopo.com_documento || 0) +
          ' com algum documento'
      }));
      kpiGrid.appendChild(UI.kpi(doc, {
        label: 'Prazos em até 30 dias', value: ate7 + ate30, icon: 'calendar',
        sub: Fmt.integer(ate7) + ' em até 7 dias · ' +
          Fmt.integer(urgency.vencido || 0) + ' vencidos preservados como histórico'
      }));
      var study = state.estudos || {};
      kpiGrid.appendChild(UI.kpi(doc, {
        label: 'Tempo estudado', display: Fmt.duration(study.total_segundos || 0),
        icon: 'clock',
        sub: Fmt.integer(study.sessoes_concluidas || 0) + ' sessões concluídas · ' +
          Fmt.integer(study.revisoes_pendentes || 0) + ' revisões pendentes'
      }));
    }

    function paintActivity() {
      var body = activityCard.querySelector('.card__body') || activityCard;
      Dom.clear(body);
      if (errors.timeline) {
        body.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Atividade indisponível',
          text: errors.timeline, actions: [{label: 'Tentar novamente', onClick: load}]
        }));
        return;
      }
      var cycles = (state.timeline && state.timeline.ciclos) || [];
      if (!cycles.length) {
        body.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'history', title: 'Nenhum ciclo registrado',
          text: 'A atividade aparece depois do primeiro ciclo de monitoramento.',
          actions: [{label: 'Ver operação', href: '#/operacao'}]
        }));
        return;
      }
      var recent = cycles.slice(-8);
      var data = recent.map(function (cycle) {
        var parsed = new Date(cycle.started_at);
        var label = isNaN(parsed.getTime())
          ? '—'
          : parsed.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'}) +
            ' ' + String(parsed.getHours()).padStart(2, '0') + 'h';
        return {
          label: label,
          value: cycle.versions_new || 0,
          title: label + ': ' + Fmt.integer(cycle.versions_new || 0) + ' versão(ões) nova(s), ' +
            Fmt.integer(cycle.documents_new || 0) + ' documento(s) novo(s) · ' + cycle.state
        };
      });
      body.appendChild(Charts.columnChart(doc, {
        id: 'chart-activity', data: data, height: 210,
        title: 'Novas versões por ciclo de monitoramento',
        description: 'Gráfico de colunas com o número de versões novas em cada um dos últimos ciclos.',
        color: 'var(--chart-1)'
      }));
      body.appendChild(UI.tableFallback(doc, {
        summary: 'Ver ciclos em tabela',
        caption: 'Versões e documentos novos por ciclo',
        columns: ['Ciclo', 'Versões novas', 'Documentos novos', 'Estado'],
        rows: recent.map(function (cycle, index) {
          return [data[index].label, Fmt.integer(cycle.versions_new || 0),
            Fmt.integer(cycle.documents_new || 0), cycle.state || '—'];
        })
      }));
    }

    function paintCoverage() {
      var body = coverageCard.querySelector('.card__body') || coverageCard;
      Dom.clear(body);
      if (errors.cobertura) {
        body.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Cobertura indisponível',
          text: errors.cobertura, actions: [{label: 'Tentar novamente', onClick: load}]
        }));
        return;
      }
      var funil = (state.cobertura && state.cobertura.funil) || [];
      if (!funil.length) {
        body.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'layers', title: 'Sem dados de cobertura',
          text: 'A cobertura é calculada a partir dos documentos coletados.'
        }));
        return;
      }
      var labels = {
        concursos: 'Concursos', com_documento: 'Com documento',
        com_edital_oficial: 'Com edital oficial', com_edital_analisado: 'Edital analisado',
        com_propostas: 'Com propostas', com_campo_confirmado: 'Com campo confirmado'
      };
      var base = funil[0].de || funil[0].quantidade || 0;
      body.appendChild(Charts.barRows(doc, {
        ariaLabel: 'Funil de cobertura documental',
        data: funil.map(function (stage) {
          return {
            label: labels[stage.etapa] || stage.etapa,
            value: stage.quantidade,
            display: Fmt.integer(stage.quantidade),
            color: stage.etapa === 'com_campo_confirmado' ? 'var(--chart-2)' : 'var(--chart-1)',
            title: stage.quantidade + ' de ' + stage.de + ' (' + Fmt.percent(Fmt.percentOf(stage.quantidade, base)) + ')'
          };
        })
      }));
      body.appendChild(Dom.el(doc, 'p', 'card__sub',
        'Base: ' + Fmt.integer(base) + ' concursos. Etapas não são somadas entre si.'));
      var causas = (state.cobertura && state.cobertura.causas) || {};
      var entries = Object.keys(causas).sort(function (a, b) { return causas[b] - causas[a]; }).slice(0, 3);
      if (entries.length) {
        var list = Dom.el(doc, 'ul', 'legend');
        entries.forEach(function (key) {
          var item = Dom.el(doc, 'li');
          item.appendChild(Dom.el(doc, 'span', 'legend__dot')).style.background = 'var(--slate-300)';
          item.appendChild(Dom.el(doc, 'span', '', humanizeCause(key)));
          item.appendChild(Dom.el(doc, 'span', 'legend__value', Fmt.integer(causas[key])));
          list.appendChild(item);
        });
        body.appendChild(list);
      }
    }

    function humanizeCause(key) {
      return ({
        apenas_agregador: 'Apenas agregador',
        documento_oficial_sem_edital: 'Documento oficial sem edital',
        edital_sem_campos: 'Edital sem campos',
        sem_documento: 'Sem documento',
        extraido_ambiguo: 'Extração ambígua'
      })[key] || String(key).replace(/_/g, ' ');
    }

    function paintPriorities() {
      var body = priorityCard.querySelector('.card__body') || priorityCard;
      Dom.clear(body);
      if (errors.carteira) {
        body.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Carteira indisponível',
          text: errors.carteira, actions: [{label: 'Tentar novamente', onClick: load}]
        }));
        return;
      }
      var items = (state.carteira && state.carteira.itens) || [];
      if (!items.length) {
        body.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'opportunities', title: 'Nenhuma oportunidade na carteira',
          text: 'A carteira é montada a partir de documentos oficiais analisados.',
          actions: [{label: 'Ver operação', href: '#/operacao'}]
        }));
        return;
      }
      var list = Dom.el(doc, 'ul', 'list');
      items.slice(0, 5).forEach(function (item) {
        list.appendChild(priorityItem(doc, item));
      });
      body.appendChild(list);
    }

    function paintDeadlines() {
      var body = deadlineCard.querySelector('.card__body') || deadlineCard;
      Dom.clear(body);
      if (errors.prazos) {
        body.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Prazos indisponíveis',
          text: errors.prazos, actions: [{label: 'Tentar novamente', onClick: load}]
        }));
        return;
      }
      var raw = (state.prazos && state.prazos.itens) || [];
      var seen = {};
      var items = raw.filter(function (item) {
        var key = item.grupo + '|' + item.valor + '|' + item.contest_id;
        if (seen[key]) return false;
        seen[key] = true;
        return true;
      });
      if (!items.length) {
        body.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'calendar', title: 'Nenhum prazo futuro em 7 dias',
          text: 'Datas passadas continuam no histórico; datas candidatas não viram prazo confirmado.',
          actions: [{label: 'Abrir calendário', href: '#/prazos'}]
        }));
        return;
      }
      var list = Dom.el(doc, 'ul', 'list');
      items.slice(0, 6).forEach(function (item) {
        list.appendChild(deadlineItem(doc, item));
      });
      body.appendChild(list);
    }

    function paintReadiness() {
      var body = readinessCard.querySelector('.card__body') || readinessCard;
      Dom.clear(body);
      if (errors.carteira) {
        body.appendChild(UI.inlineError(doc, errors.carteira));
        return;
      }
      var portfolio = state.carteira || {};
      var readiness = portfolio.por_prontidao || {};
      var keys = Object.keys(readiness).sort(function (a, b) { return readiness[b] - readiness[a]; });
      if (!keys.length) {
        body.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'target', title: 'Sem oportunidades classificadas',
          text: 'A prontidão aparece quando houver documentos analisados.'
        }));
        return;
      }
      var total = portfolio.total || keys.reduce(function (sum, key) { return sum + readiness[key]; }, 0);
      var segments = keys.map(function (key) {
        return {
          label: readinessLabel(key), value: readiness[key],
          color: READINESS_COLOR[key] || '#94a3b8',
          pct: total ? (readiness[key] / total) * 100 : 0
        };
      });
      body.appendChild(UI.stacked(doc, segments));
      body.appendChild(UI.legend(doc, segments));
      body.appendChild(Dom.el(doc, 'p', 'card__sub',
        'Total: ' + Fmt.integer(total) + ' oportunidades. Estados não são probabilidade de aprovação.'));
    }

    function paintStudy() {
      var body = studyCard.querySelector('.card__body') || studyCard;
      Dom.clear(body);
      if (errors.estudos) {
        body.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Estudos indisponíveis',
          text: errors.estudos, actions: [{label: 'Tentar novamente', onClick: load}]
        }));
        return;
      }
      var study = state.estudos || {};
      var content = study.conteudo || {};
      var topics = content.topics || {done: 0, total: 0};
      var hasData = (study.total_segundos || 0) > 0 || (study.sessoes_concluidas || 0) > 0 ||
        (topics.total || 0) > 0 || (study.disciplinas || 0) > 0;
      if (!hasData) {
        body.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'studies', title: 'Seu estudo começa aqui',
          text: 'Nenhuma disciplina, sessão ou revisão registrada. Crie uma disciplina e inicie o cronômetro.',
          actions: [{label: 'Abrir estudos', href: '#/estudos', primary: true}]
        }));
        return;
      }
      var tiles = Dom.el(doc, 'div', 'panel-grid panel-grid--2');
      tiles.appendChild(UI.metricTile(doc, 'Tempo total', Fmt.duration(study.total_segundos || 0),
        'Somatório das sessões concluídas'));
      tiles.appendChild(UI.metricTile(doc, 'Sessões', Fmt.integer(study.sessoes_concluidas || 0),
        Fmt.integer(study.revisoes_pendentes || 0) + ' revisões pendentes'));
      body.appendChild(tiles);
      if ((topics.total || 0) > 0) {
        var progress = UI.progress(doc, {
          label: 'Tópicos concluídos', value: topics.done, total: topics.total
        });
        progress.style.marginTop = '16px';
        body.appendChild(progress);
      }
      var cta = Dom.el(doc, 'a', 'btn btn--ghost btn--sm', 'Continuar estudando');
      cta.href = '#/estudos';
      cta.style.marginTop = '14px';
      body.appendChild(cta);
    }

    function paintAll() {
      paintKpis();
      paintActivity();
      paintCoverage();
      paintPriorities();
      paintDeadlines();
      paintReadiness();
      paintStudy();
    }

    function load() {
      var seq = ctx.api.sequencer();
      errors = {};
      paintAll();
      var token = seq.next();

      function fail(key, error) {
        if (!seq.isCurrent(token)) return;
        errors[key] = error && error.message ? error.message : 'Falha ao consultar.';
        paintAll();
      }

      ctx.api.get('/api/carteira?limit=6')
        .then(function (payload) { if (seq.isCurrent(token)) { state.carteira = payload; paintAll(); } })
        .catch(function (error) { fail('carteira', error); });

      ctx.api.get('/api/cobertura/resumo')
        .then(function (payload) { if (seq.isCurrent(token)) { state.cobertura = payload; paintAll(); } })
        .catch(function (error) { fail('cobertura', error); });

      ctx.api.get('/api/linha-do-tempo?limit=1')
        .then(function (payload) { if (seq.isCurrent(token)) { state.timeline = payload; paintAll(); } })
        .catch(function (error) { fail('timeline', error); });

      ctx.api.get('/api/estudos/painel')
        .then(function (payload) { if (seq.isCurrent(token)) { state.estudos = payload; paintAll(); } })
        .catch(function (error) { fail('estudos', error); });

      ctx.api.get('/api/prazos/calendario?limit=6&urgency=ate_7_dias')
        .then(function (payload) { if (seq.isCurrent(token)) { state.prazos = payload; paintAll(); } })
        .catch(function (error) { fail('prazos', error); });
    }

    load();
  }

  global.RadarOverview = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
