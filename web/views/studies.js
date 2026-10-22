/* Estudos: painel, cronômetro, sessões, revisões, flashcards, questões e simulados. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;
  var Charts = global.RadarCharts;

  var TABS = [
    ['visao', 'Visão geral'],
    ['sessoes', 'Sessões'],
    ['questoes', 'Questões'],
    ['flashcards', 'Flashcards'],
    ['simulados', 'Simulados']
  ];

  var QUALITY = [
    [1, 'Errei'], [2, 'Difícil'], [3, 'Ok'], [4, 'Bom'], [5, 'Fácil']
  ];

  function tabFrom(query) {
    var value = query.get('tab') || 'visao';
    return TABS.some(function (pair) { return pair[0] === value; }) ? value : 'visao';
  }

  function render(root, ctx) {
    var doc = ctx.doc;
    var query = ctx.query || new URLSearchParams();
    var tab = tabFrom(query);
    var seq = ctx.api.sequencer();
    Dom.clear(root);
    root.appendChild(UI.loadingRows(doc, 5));

    var token = seq.next();
    Promise.all([
      ctx.api.get('/api/estudos/painel'),
      ctx.api.get('/api/estudos/sessoes?limit=50'),
      ctx.api.get('/api/estudos/disciplinas'),
      ctx.api.get('/api/estudos/revisoes'),
      ctx.api.get('/api/estudos/desempenho'),
      ctx.api.get('/api/estudos/flashcards/fila?limit=20'),
      ctx.api.get('/api/estudos/flashcards/estatisticas'),
      ctx.api.get('/api/estudos/questoes?incluir_arquivadas=0'),
      ctx.api.get('/api/estudos/simulados?limit=30')
    ]).then(function (results) {
      if (!seq.isCurrent(token)) return;
      renderPage(root, ctx, tab, {
        painel: results[0], sessoes: results[1], disciplinas: results[2],
        revisoes: results[3], desempenho: results[4], fila: results[5],
        flashcards: results[6], questoes: results[7], simulados: results[8]
      });
    }).catch(function (error) {
      Dom.clear(root);
      root.appendChild(UI.state(doc, {
        tone: 'error', icon: 'alert', title: 'Estudos indisponíveis',
        text: error.message,
        hint: 'Verifique o servidor local e tente novamente.',
        actions: [{label: 'Tentar novamente', primary: true, onClick: function () { render(root, ctx); }}]
      }));
    });
  }

  function renderPage(root, ctx, tab, data) {
    var doc = ctx.doc;
    Dom.clear(root);

    var head = Dom.el(doc, 'header', 'page-head');
    var text = Dom.el(doc, 'div', 'page-head__text');
    text.appendChild(Dom.el(doc, 'p', 'eyebrow', 'Aprendizagem'));
    text.appendChild(Dom.el(doc, 'h2', '', 'Estudos'));
    text.appendChild(Dom.el(doc, 'p', 'page-head__sub',
      'Sessões, revisões, questões e simulados registrados no servidor local. ' +
      'Nenhum percentual é exibido sem denominador.'));
    head.appendChild(text);
    var actions = Dom.el(doc, 'div', 'page-head__actions');
    var exportButton = Dom.el(doc, 'button', 'btn btn--ghost', 'Exportar dados');
    exportButton.type = 'button';
    exportButton.addEventListener('click', function () { exportStudy(ctx, exportButton); });
    actions.appendChild(exportButton);
    var importLabel = Dom.el(doc, 'label', 'btn btn--ghost', 'Importar dados');
    var importInput = Dom.el(doc, 'input');
    importInput.type = 'file';
    importInput.accept = 'application/json,.json';
    importInput.className = 'visually-hidden';
    importLabel.appendChild(importInput);
    importInput.addEventListener('change', function () {
      if (importInput.files && importInput.files[0]) importStudy(ctx, importInput.files[0]);
      importInput.value = '';
    });
    actions.appendChild(importLabel);
    head.appendChild(actions);
    root.appendChild(head);

    var tabs = Dom.el(doc, 'div', 'tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', 'Seções de estudos');
    TABS.forEach(function (pair) {
      var button = Dom.el(doc, 'button', 'tab', pair[1]);
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', pair[0] === tab ? 'true' : 'false');
      button.addEventListener('click', function () {
        var next = new URLSearchParams(ctx.query ? ctx.query.toString() : '');
        next.set('tab', pair[0]);
        ctx.router.replaceQuery(next);
        renderPage(root, ctx, pair[0], data);
      });
      tabs.appendChild(button);
    });
    root.appendChild(tabs);

    var panel = Dom.el(doc, 'section');
    panel.setAttribute('role', 'tabpanel');
    root.appendChild(panel);

    if (tab === 'visao') overview(panel, ctx, data);
    else if (tab === 'sessoes') sessionsTab(panel, ctx, data);
    else if (tab === 'questoes') questionsTab(panel, ctx, data);
    else if (tab === 'flashcards') flashcardsTab(panel, ctx, data);
    else examsTab(panel, ctx, data);
  }

  function overview(panel, ctx, data) {
    var doc = ctx.doc;
    var painel = data.painel || {};
    var desempenho = (data.desempenho || {}).geral || {};
    var wrap = Dom.el(doc, 'div', 'dashboard');

    var kpis = Dom.el(doc, 'div', 'kpi-grid');
    kpis.appendChild(UI.kpi(doc, {
      label: 'Tempo estudado', display: Fmt.duration(painel.total_segundos || 0),
      icon: 'clock', feature: true,
      sub: Fmt.duration(painel.semana_segundos || 0) + ' nos últimos 7 dias'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Sessões concluídas', value: painel.sessoes_concluidas || 0, icon: 'sessions',
      sub: (painel.sessao_aberta ? 'Uma sessão está aberta' : 'Nenhuma sessão aberta')
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Revisões pendentes', value: painel.revisoes_pendentes || 0, icon: 'refresh',
      sub: (painel.revisoes_pendentes || 0) ? 'Agenda de revisão espaçada' : 'Nada vencido'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Questões respondidas', value: desempenho.respondidas || 0, icon: 'questions',
      sub: desempenho.pct === null || desempenho.pct === undefined
        ? 'Percentual não calculável'
        : Fmt.percent(desempenho.pct) + ' de acerto · ' + (desempenho.basis || '')
    }));
    wrap.appendChild(kpis);

    var grid = Dom.el(doc, 'div', 'grid grid--main');
    wrap.appendChild(grid);

    var timerCard = UI.card(doc, {
      title: 'Sessão de estudo', sub: 'O cronômetro roda no servidor; fechar a aba não apaga a sessão.'
    });
    timerCard.querySelector('.card__body').appendChild(timerBlock(ctx, data));
    grid.appendChild(timerCard);

    var progressCard = UI.card(doc, {
      title: 'Tempo por disciplina', sub: 'Somente sessões concluídas.'
    });
    var progressBody = progressCard.querySelector('.card__body');
    var minutes = painel.minutos_por_disciplina || [];
    if (!minutes.length) {
      progressBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'studies', title: 'Sem tempo registrado',
        text: 'Conclua uma sessão para ver a distribuição por disciplina.'
      }));
    } else {
      progressBody.appendChild(Charts.barRows(doc, {
        ariaLabel: 'Minutos estudados por disciplina',
        data: minutes.map(function (item) {
          return {
            label: item.nome, value: item.minutos,
            display: Fmt.integer(item.minutos) + ' min',
            title: item.nome + ': ' + item.minutos + ' min'
          };
        })
      }));
    }
    grid.appendChild(progressCard);

    var lower = Dom.el(doc, 'div', 'grid grid--2');
    wrap.appendChild(lower);

    var activity = UI.card(doc, {
      title: 'Atividade recente', sub: 'Minutos concluídos por dia nos últimos 14 dias.'
    });
    activity.querySelector('.card__body').appendChild(activityChart(ctx, data));
    lower.appendChild(activity);

    var revisions = UI.card(doc, {
      title: 'Revisões de hoje', sub: 'Agenda persistida, sem sequência inventada.'
    });
    revisions.querySelector('.card__body').appendChild(revisionList(ctx, data));
    lower.appendChild(revisions);

    var next = UI.card(doc, {
      title: 'Próximo passo', sub: 'Ações reais disponíveis agora.'
    });
    var nextBody = next.querySelector('.card__body');
    var list = Dom.el(doc, 'ul', 'list');
    if (!(data.disciplinas || []).length) {
      list.appendChild(actionRow(doc, 'Criar a primeira disciplina', 'Organize o tempo por matéria.', 'Disciplinas', function () {
        var tab = doc.querySelector('.tab');
        if (tab) tab.click();
      }));
    }
    list.appendChild(actionRow(doc, 'Responder questões', 'Pratique com correção no servidor.', 'Questões', function () {
      var buttons = doc.querySelectorAll('.tab');
      if (buttons[2]) buttons[2].click();
    }));
    list.appendChild(actionRow(doc, 'Revisar flashcards', 'Fila de novos e vencidos.', 'Flashcards', function () {
      var buttons = doc.querySelectorAll('.tab');
      if (buttons[3]) buttons[3].click();
    }));
    list.appendChild(actionRow(doc, 'Montar simulado', 'Tempo controlado e resultado persistido.', 'Simulados', function () {
      var buttons = doc.querySelectorAll('.tab');
      if (buttons[4]) buttons[4].click();
    }));
    nextBody.appendChild(list);
    lower.appendChild(next);
    panel.appendChild(wrap);
  }

  function actionRow(doc, title, sub, cta, onClick) {
    var li = Dom.el(doc, 'li', 'list__item');
    var main = Dom.el(doc, 'div', 'list__main');
    main.appendChild(Dom.el(doc, 'p', 'list__title', title));
    main.appendChild(Dom.el(doc, 'p', 'list__meta', sub));
    li.appendChild(main);
    var aside = Dom.el(doc, 'div', 'list__aside');
    var button = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', cta);
    button.type = 'button';
    button.addEventListener('click', onClick);
    aside.appendChild(button);
    li.appendChild(aside);
    return li;
  }

  function timerBlock(ctx, data) {
    var doc = ctx.doc;
    var session = (data.painel || {}).sessao_aberta;
    var wrap = Dom.el(doc, 'div', 'timer-card');
    var display = Dom.el(doc, 'div', 'timer-display', Fmt.clock(session ? session.elapsed_seconds || 0 : 0));
    display.id = 'study-timer-display';
    wrap.appendChild(display);

    var meta = Dom.el(doc, 'div', 'timer-meta');
    var disciplineName = '';
    if (session && session.disciplina_id) {
      var found = (data.disciplinas || []).find(function (item) { return item.id === session.disciplina_id; });
      disciplineName = found ? found.nome : '';
    }
    meta.appendChild(Dom.el(doc, 'span', '', session
      ? (session.estado === 'pausada' ? 'Sessão pausada' : 'Sessão em andamento') +
        (disciplineName ? ' · ' + disciplineName : '')
      : 'Nenhuma sessão aberta'));
    meta.appendChild(Dom.el(doc, 'span', '', 'Modo ' + ((session && session.modo) || 'livre')));
    wrap.appendChild(meta);

    var actions = Dom.el(doc, 'div', 'timer-actions');
    if (!session) {
      var select = Dom.el(doc, 'select', 'select');
      select.setAttribute('aria-label', 'Disciplina da sessão');
      var empty = Dom.el(doc, 'option', '', 'Sem disciplina');
      empty.value = '';
      select.appendChild(empty);
      (data.disciplinas || []).forEach(function (item) {
        var option = Dom.el(doc, 'option', '', item.nome);
        option.value = item.id;
        select.appendChild(option);
      });
      actions.appendChild(select);
      var start = Dom.el(doc, 'button', 'btn btn--primary', 'Iniciar sessão');
      start.type = 'button';
      start.addEventListener('click', function () {
        start.disabled = true;
        ctx.api.post('/api/estudos/sessoes', {
          action: 'start', disciplina_id: select.value || null, modo: 'livre'
        }).then(function () { ctx.reload(); })
          .catch(function (error) { start.disabled = false; alertInline(actions, error.message); });
      });
      actions.appendChild(start);
    } else {
      if (session.estado === 'pausada') {
        actions.appendChild(timerButton(ctx, 'Retomar', 'resume', session.id));
      } else {
        actions.appendChild(timerButton(ctx, 'Pausar', 'pause', session.id));
      }
      actions.appendChild(timerButton(ctx, 'Concluir', 'finish', session.id, 'btn--primary'));
      actions.appendChild(timerButton(ctx, 'Descartar', 'discard', session.id, 'btn--ghost'));
    }
    wrap.appendChild(actions);

    if (session && session.inicio) {
      var started = new Date(session.inicio);
      var base = session.elapsed_seconds || 0;
      var baseTime = Date.now();
      var interval = global.setInterval(function () {
        if (!doc.body.contains(display)) {
          global.clearInterval(interval);
          return;
        }
        var extra = session.estado === 'em_andamento' ? (Date.now() - baseTime) / 1000 : 0;
        display.textContent = Fmt.clock(base + extra);
      }, 1000);
      ctx.addCleanup(function () { global.clearInterval(interval); });
    }
    return wrap;
  }

  function timerButton(ctx, label, action, id, variant) {
    var doc = ctx.doc;
    var button = Dom.el(doc, 'button', 'btn ' + (variant || 'btn--ghost'), label);
    button.type = 'button';
    button.addEventListener('click', function () {
      button.disabled = true;
      ctx.api.post('/api/estudos/sessoes', {action: action, id: id})
        .then(function () { ctx.reload(); })
        .catch(function (error) {
          button.disabled = false;
          alertInline(button.parentNode, error.message);
        });
    });
    return button;
  }

  function alertInline(container, message) {
    var old = container.querySelector('.inline-error');
    if (old) old.remove();
    container.appendChild(UI.inlineError(container.ownerDocument, message));
  }

  function activityChart(ctx, data) {
    var doc = ctx.doc;
    var sessions = (data.sessoes || []).filter(function (session) {
      return session.estado === 'concluida' && session.fim;
    });
    if (!sessions.length) {
      return UI.state(doc, {
        tone: 'empty', icon: 'sessions', title: 'Sem atividade registrada',
        text: 'Conclua uma sessão para alimentar o gráfico.'
      });
    }
    var byDay = {};
    sessions.forEach(function (session) {
      var key = String(session.fim).slice(0, 10);
      byDay[key] = (byDay[key] || 0) + Math.round((session.duracao_segundos || 0) / 60);
    });
    var days = [];
    var today = new Date();
    for (var i = 13; i >= 0; i -= 1) {
      var day = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
      var key = day.getFullYear() + '-' + String(day.getMonth() + 1).padStart(2, '0') + '-' +
        String(day.getDate()).padStart(2, '0');
      days.push({
        label: day.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'}),
        value: byDay[key] || 0,
        title: day.toLocaleDateString('pt-BR') + ': ' + (byDay[key] || 0) + ' min'
      });
    }
    var wrap = Dom.el(doc, 'div');
    wrap.appendChild(Charts.columnChart(doc, {
      id: 'chart-study', data: days, height: 190, color: 'var(--chart-2)',
      title: 'Minutos estudados por dia',
      description: 'Gráfico de colunas com minutos concluídos nos últimos 14 dias.'
    }));
    wrap.appendChild(UI.tableFallback(doc, {
      summary: 'Ver dias em tabela', columns: ['Dia', 'Minutos'],
      rows: days.map(function (item) { return [item.label, item.value]; })
    }));
    return wrap;
  }

  function revisionList(ctx, data) {
    var doc = ctx.doc;
    var revisions = (data.revisoes || []);
    if (!revisions.length) {
      return UI.state(doc, {
        tone: 'empty', icon: 'check', title: 'Nenhuma revisão pendente',
        text: 'A agenda aparece quando um tópico é concluído e entra na revisão espaçada.'
      });
    }
    var list = Dom.el(doc, 'ul', 'list');
    revisions.slice(0, 6).forEach(function (revision) {
      var li = Dom.el(doc, 'li', 'list__item');
      var main = Dom.el(doc, 'div', 'list__main');
      main.appendChild(Dom.el(doc, 'p', 'list__title', 'Revisão de ' + Fmt.date(revision.data)));
      main.appendChild(Dom.el(doc, 'p', 'list__meta', 'Tópico ' + (revision.topico_id || 'não informado')));
      li.appendChild(main);
      var aside = Dom.el(doc, 'div', 'list__aside');
      var button = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Marcar revisada');
      button.type = 'button';
      button.addEventListener('click', function () {
        button.disabled = true;
        ctx.api.post('/api/estudos/revisoes', {
          progresso_id: revision.progresso_id, resultado: 'concluida'
        }).then(function () { ctx.reload(); })
          .catch(function (error) { button.disabled = false; alertInline(li, error.message); });
      });
      aside.appendChild(button);
      li.appendChild(aside);
      list.appendChild(li);
    });
    return list;
  }

  function sessionsTab(panel, ctx, data) {
    var doc = ctx.doc;
    var wrap = Dom.el(doc, 'div', 'dashboard');
    var formCard = UI.card(doc, {
      title: 'Disciplinas e tópicos', sub: 'A base do plano de estudos. Tudo fica no banco local.'
    });
    var body = formCard.querySelector('.card__body');
    var form = Dom.el(doc, 'form', 'filter-row');
    var name = Dom.el(doc, 'input', 'input');
    name.placeholder = 'Nome da disciplina';
    name.setAttribute('aria-label', 'Nome da disciplina');
    form.appendChild(name);
    var submit = Dom.el(doc, 'button', 'btn btn--primary', 'Criar disciplina');
    submit.type = 'submit';
    form.appendChild(submit);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (!name.value.trim()) return;
      submit.disabled = true;
      ctx.api.post('/api/estudos/disciplinas', {nome: name.value.trim()})
        .then(function () { ctx.reload(); })
        .catch(function (error) { submit.disabled = false; alertInline(form, error.message); });
    });
    body.appendChild(form);
    var disciplines = data.disciplinas || [];
    if (disciplines.length) {
      var list = Dom.el(doc, 'ul', 'list');
      disciplines.forEach(function (discipline) {
        var li = Dom.el(doc, 'li', 'list__item');
        var main = Dom.el(doc, 'div', 'list__main');
        main.appendChild(Dom.el(doc, 'p', 'list__title', discipline.nome));
        var topicCount = (data.painel || {}).topicos || 0;
        main.appendChild(Dom.el(doc, 'p', 'list__meta', 'Disciplina ativa'));
        li.appendChild(main);
        var aside = Dom.el(doc, 'div', 'list__aside');
        var add = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Adicionar tópico');
        add.type = 'button';
        add.addEventListener('click', function () {
          var topic = global.prompt('Nome do tópico para ' + discipline.nome);
          if (!topic || !topic.trim()) return;
          add.disabled = true;
          ctx.api.post('/api/estudos/topicos', {
            disciplina_id: discipline.id, nome: topic.trim()
          }).then(function () { ctx.reload(); })
            .catch(function (error) { add.disabled = false; alertInline(li, error.message); });
        });
        aside.appendChild(add);
        li.appendChild(aside);
        list.appendChild(li);
      });
      body.appendChild(list);
    } else {
      body.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'studies', title: 'Nenhuma disciplina criada',
        text: 'Crie a primeira disciplina para registrar sessões e tópicos.'
      }));
    }
    wrap.appendChild(formCard);

    var history = UI.card(doc, {
      title: 'Histórico de sessões', sub: 'Duração e estado calculados pelo servidor.'
    });
    var historyBody = history.querySelector('.card__body');
    var sessions = data.sessoes || [];
    if (!sessions.length) {
      historyBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'sessions', title: 'Nenhuma sessão registrada',
        text: 'Inicie o cronômetro na visão geral.'
      }));
    } else {
      var table = Dom.el(doc, 'table', 'data-table-main');
      var thead = Dom.el(doc, 'thead');
      var head = Dom.el(doc, 'tr');
      ['Início', 'Duração', 'Estado', 'Modo'].forEach(function (label) {
        head.appendChild(Dom.el(doc, 'th', '', label));
      });
      thead.appendChild(head);
      table.appendChild(thead);
      var tbody = Dom.el(doc, 'tbody');
      sessions.slice(0, 30).forEach(function (session) {
        var tr = Dom.el(doc, 'tr');
        var start = Dom.el(doc, 'td', 'cell-sub', Fmt.dateTime(session.inicio || session.created_at));
        start.setAttribute('data-label', 'Início');
        tr.appendChild(start);
        var duration = Dom.el(doc, 'td', 'cell-num', Fmt.duration(session.duracao_segundos));
        duration.setAttribute('data-label', 'Duração');
        tr.appendChild(duration);
        var state = Dom.el(doc, 'td');
        state.setAttribute('data-label', 'Estado');
        state.appendChild(UI.badge(doc, session.estado, session.estado === 'concluida' ? 'success' : 'neutral'));
        tr.appendChild(state);
        var mode = Dom.el(doc, 'td', 'cell-sub', session.modo || 'livre');
        mode.setAttribute('data-label', 'Modo');
        tr.appendChild(mode);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      var scroll = Dom.el(doc, 'div', 'table-wrap');
      scroll.appendChild(table);
      historyBody.appendChild(scroll);
    }
    wrap.appendChild(history);
    panel.appendChild(wrap);
  }

  function questionsTab(panel, ctx, data) {
    var doc = ctx.doc;
    var wrap = Dom.el(doc, 'div', 'dashboard');
    var performance = data.desempenho || {};
    var geral = performance.geral || {};
    var kpis = Dom.el(doc, 'div', 'kpi-grid');
    kpis.appendChild(UI.kpi(doc, {
      label: 'Tentativas', value: geral.respondidas || 0, icon: 'questions', feature: true,
      sub: (geral.total || 0) + ' questão(ões) com tentativa registrada'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Acertos', value: geral.acertos || 0, icon: 'check',
      sub: geral.pct === null || geral.pct === undefined ? 'Percentual não calculável' : Fmt.percent(geral.pct)
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Erros', value: geral.erros || 0, icon: 'alert',
      sub: (geral.brancos || 0) + ' em branco'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Disciplinas com desempenho', value: (performance.por_disciplina || []).length,
      icon: 'book', sub: 'Somente com tentativas'
    }));
    wrap.appendChild(kpis);

    var card = UI.card(doc, {
      title: 'Praticar questões', sub: 'Correção no servidor; o gabarito é revelado após responder.'
    });
    var body = card.querySelector('.card__body');
    var questions = data.questoes || [];
    if (!questions.length) {
      body.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'questions', title: 'Nenhuma questão cadastrada',
        text: 'Crie questões na operação para praticar aqui. Nenhum conteúdo de terceiros é importado.'
      }));
    } else {
      questions.slice(0, 8).forEach(function (question) {
        body.appendChild(questionCard(ctx, question));
      });
    }
    wrap.appendChild(card);

    if ((performance.por_disciplina || []).length) {
      var byDiscipline = UI.card(doc, {
        title: 'Desempenho por disciplina', sub: 'Percentual sobre tentativas respondidas.'
      });
      var list = Dom.el(doc, 'ul', 'list');
      performance.por_disciplina.forEach(function (item) {
        var li = Dom.el(doc, 'li', 'list__item');
        var main = Dom.el(doc, 'div', 'list__main');
        main.appendChild(Dom.el(doc, 'p', 'list__title', item.grupo));
        main.appendChild(Dom.el(doc, 'p', 'list__meta',
          item.acertos + ' acertos · ' + item.erros + ' erros · ' + item.brancos + ' em branco'));
        li.appendChild(main);
        var aside = Dom.el(doc, 'div', 'list__aside');
        aside.appendChild(Dom.el(doc, 'strong', '',
          item.pct === null || item.pct === undefined ? '—' : Fmt.percent(item.pct)));
        li.appendChild(aside);
        list.appendChild(li);
      });
      byDiscipline.querySelector('.card__body').appendChild(list);
      wrap.appendChild(byDiscipline);
    }
    panel.appendChild(wrap);
  }

  function questionCard(ctx, question) {
    var doc = ctx.doc;
    var card = Dom.el(doc, 'div', 'practice-card');
    var head = Dom.el(doc, 'div', 'practice-card__head');
    var title = Dom.el(doc, 'h4', '', Fmt.truncate(question.enunciado, 220));
    head.appendChild(title);
    card.appendChild(head);
    var meta = Dom.el(doc, 'p', '', '');
    meta.textContent = [question.disciplina, question.topico, question.dificuldade]
      .filter(Boolean).join(' · ') || 'Sem classificação';
    card.appendChild(meta);
    var list = Dom.el(doc, 'ul', 'alternatives');
    var alternatives = question.alternativas || [];
    var answered = false;
    alternatives.forEach(function (alternative) {
      var letter = typeof alternative === 'string' ? alternative : alternative.letra;
      var text = typeof alternative === 'string' ? '' : alternative.texto;
      var li = Dom.el(doc, 'li');
      var label = Dom.el(doc, 'label', 'alternative');
      var input = Dom.el(doc, 'input');
      input.type = 'radio';
      input.name = 'q-' + question.id;
      input.value = letter;
      label.appendChild(input);
      label.appendChild(Dom.el(doc, 'span', '', letter + (text ? ' · ' + text : '')));
      li.appendChild(label);
      list.appendChild(li);
    });
    card.appendChild(list);
    var actions = Dom.el(doc, 'div', 'filter-row');
    actions.style.marginTop = '10px';
    var submit = Dom.el(doc, 'button', 'btn btn--primary btn--sm', 'Responder');
    submit.type = 'button';
    var status = Dom.el(doc, 'span', 'form-status', '');
    actions.appendChild(submit);
    actions.appendChild(status);
    card.appendChild(actions);
    submit.addEventListener('click', function () {
      if (answered) return;
      var selected = card.querySelector('input[type="radio"]:checked');
      if (!selected) {
        status.textContent = 'Escolha uma alternativa.';
        status.className = 'form-status form-status--error';
        return;
      }
      submit.disabled = true;
      ctx.api.post('/api/estudos/tentativas', {
        questao_id: question.id, resposta: selected.value
      }).then(function (result) {
        answered = true;
        status.textContent = result.correta
          ? 'Correta. Gabarito ' + result.gabarito + '.'
          : 'Incorreta. Gabarito ' + result.gabarito + '.';
        status.className = 'form-status ' + (result.correta ? 'form-status--ok' : 'form-status--error');
      }).catch(function (error) {
        submit.disabled = false;
        status.textContent = error.message;
        status.className = 'form-status form-status--error';
      });
    });
    return card;
  }

  function flashcardsTab(panel, ctx, data) {
    var doc = ctx.doc;
    var wrap = Dom.el(doc, 'div', 'dashboard');
    var stats = data.flashcards || {};
    var kpis = Dom.el(doc, 'div', 'kpi-grid');
    kpis.appendChild(UI.kpi(doc, {
      label: 'Cartões ativos', value: stats.ativos || 0, icon: 'flashcards', feature: true,
      sub: (stats.novos || 0) + ' novos · ' + (stats.pendentes || 0) + ' pendentes'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Revisões registradas', value: stats.revisoes || 0, icon: 'refresh',
      sub: stats.pct_acerto === null || stats.pct_acerto === undefined
        ? (stats.basis || 'Percentual não calculável')
        : Fmt.percent(stats.pct_acerto) + ' de acerto'
    }));
    kpis.appendChild(UI.kpi(doc, {
      label: 'Arquivados', value: stats.arquivados || 0, icon: 'layers',
      sub: 'Fora da fila de revisão'
    }));
    wrap.appendChild(kpis);

    var queue = data.fila || {};
    var cards = (queue.novos || []).concat(queue.vencidos || []);
    var card = UI.card(doc, {
      title: 'Fila de revisão', sub: 'Novos e vencidos, na ordem do servidor.'
    });
    var body = card.querySelector('.card__body');
    if (!cards.length) {
      body.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'check', title: 'Nenhum cartão pendente',
        text: (queue.futuros || []).length
          ? (queue.futuros.length + ' cartão(ões) agendado(s) para o futuro.')
          : 'Crie flashcards na operação para iniciar a revisão espaçada.'
      }));
    } else {
      cards.slice(0, 6).forEach(function (flashcard) {
        body.appendChild(flashcardCard(ctx, flashcard));
      });
    }
    wrap.appendChild(card);
    panel.appendChild(wrap);
  }

  function flashcardCard(ctx, flashcard) {
    var doc = ctx.doc;
    var card = Dom.el(doc, 'div', 'practice-card');
    card.appendChild(Dom.el(doc, 'h4', '', flashcard.frente));
    var answer = Dom.el(doc, 'p', '', flashcard.verso);
    answer.hidden = true;
    card.appendChild(answer);
    var actions = Dom.el(doc, 'div', 'filter-row');
    actions.style.marginTop = '10px';
    var reveal = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Mostrar resposta');
    reveal.type = 'button';
    reveal.addEventListener('click', function () {
      answer.hidden = false;
      reveal.disabled = true;
    });
    actions.appendChild(reveal);
    QUALITY.forEach(function (pair) {
      var button = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', pair[1]);
      button.type = 'button';
      button.addEventListener('click', function () {
        button.disabled = true;
        ctx.api.post('/api/estudos/flashcards', {
          action: 'review', id: flashcard.id, qualidade: pair[0]
        }).then(function () { ctx.reload(); })
          .catch(function (error) { button.disabled = false; alertInline(card, error.message); });
      });
      actions.appendChild(button);
    });
    card.appendChild(actions);
    return card;
  }

  function examsTab(panel, ctx, data) {
    var doc = ctx.doc;
    var wrap = Dom.el(doc, 'div', 'dashboard');
    var formCard = UI.card(doc, {
      title: 'Montar simulado', sub: 'Questões são selecionadas sem repetição; o tempo é do servidor.'
    });
    var body = formCard.querySelector('.card__body');
    var form = Dom.el(doc, 'form', 'filter-row');
    var name = Dom.el(doc, 'input', 'input');
    name.placeholder = 'Nome do simulado';
    name.setAttribute('aria-label', 'Nome do simulado');
    form.appendChild(name);
    var limit = Dom.el(doc, 'input', 'input');
    limit.type = 'number';
    limit.min = '1';
    limit.max = '100';
    limit.value = '10';
    limit.setAttribute('aria-label', 'Quantidade de questões');
    form.appendChild(limit);
    var minutes = Dom.el(doc, 'input', 'input');
    minutes.type = 'number';
    minutes.min = '0';
    minutes.placeholder = 'Minutos (opcional)';
    minutes.setAttribute('aria-label', 'Duração em minutos');
    form.appendChild(minutes);
    var submit = Dom.el(doc, 'button', 'btn btn--primary', 'Criar simulado');
    submit.type = 'submit';
    form.appendChild(submit);
    var status = Dom.el(doc, 'span', 'form-status', '');
    form.appendChild(status);
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      submit.disabled = true;
      var duration = parseInt(minutes.value, 10) || 0;
      ctx.api.post('/api/estudos/simulados', {
        nome: name.value.trim() || 'Simulado',
        limit: parseInt(limit.value, 10) || 10,
        duracao_segundos: duration > 0 ? duration * 60 : null
      }).then(function () { ctx.reload(); })
        .catch(function (error) {
          submit.disabled = false;
          status.textContent = error.message;
          status.className = 'form-status form-status--error';
        });
    });
    body.appendChild(form);
    wrap.appendChild(formCard);

    var listCard = UI.card(doc, {title: 'Simulados', sub: 'Abra para responder ou ver o resultado.'});
    var listBody = listCard.querySelector('.card__body');
    var exams = data.simulados || [];
    if (!exams.length) {
      listBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'exams', title: 'Nenhum simulado criado',
        text: 'Monte o primeiro simulado acima. Não há conteúdo de terceiros.'
      }));
    } else {
      var list = Dom.el(doc, 'ul', 'list');
      exams.forEach(function (exam) {
        var li = Dom.el(doc, 'li', 'list__item');
        var main = Dom.el(doc, 'div', 'list__main');
        main.appendChild(Dom.el(doc, 'p', 'list__title', exam.nome));
        var meta = (exam.modo || 'tradicional') + ' · ' +
          (exam.duracao_segundos ? Fmt.duration(exam.duracao_segundos) : 'sem limite');
        main.appendChild(Dom.el(doc, 'p', 'list__meta', meta));
        var badges = Dom.el(doc, 'div', 'list__badges');
        badges.appendChild(UI.badge(doc, exam.estado,
          exam.estado === 'finalizado' ? 'success' : exam.estado === 'expirado' ? 'warning' : 'info'));
        main.appendChild(badges);
        li.appendChild(main);
        var aside = Dom.el(doc, 'div', 'list__aside');
        var open = Dom.el(doc, 'button', 'btn btn--ghost btn--sm',
          exam.estado === 'em_andamento' ? 'Continuar' : 'Abrir');
        open.type = 'button';
        open.addEventListener('click', function () { openExam(ctx, exam, listCard); });
        aside.appendChild(open);
        li.appendChild(aside);
        list.appendChild(li);
      });
      listBody.appendChild(list);
    }
    wrap.appendChild(listCard);
    panel.appendChild(wrap);
  }

  function openExam(ctx, exam, container) {
    var doc = ctx.doc;
    var dialog = Dom.el(doc, 'div', 'card');
    dialog.style.marginTop = '16px';
    Dom.clear(container.querySelector('.card__body')).appendChild(dialog);
    dialog.appendChild(UI.loadingRows(doc, 3));
    ctx.api.get('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/questoes')
      .then(function (payload) {
        Dom.clear(dialog);
        var questions = payload.questoes || [];
        if (!questions.length) {
          dialog.appendChild(UI.state(doc, {
            tone: 'empty', icon: 'exams', title: 'Simulado sem questões',
            text: 'Não há questões elegíveis para os filtros usados.'
          }));
          return;
        }
        var head = Dom.el(doc, 'div', 'card__head');
        head.appendChild(Dom.el(doc, 'h4', 'card__title', exam.nome));
        var close = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Fechar');
        close.type = 'button';
        close.addEventListener('click', function () { ctx.reload(); });
        head.appendChild(close);
        dialog.appendChild(head);
        var current = 0;
        var answers = {};
        var body = Dom.el(doc, 'div');
        dialog.appendChild(body);
        var actions = Dom.el(doc, 'div', 'filter-row');
        actions.style.marginTop = '12px';
        dialog.appendChild(actions);
        var status = Dom.el(doc, 'span', 'form-status', '');
        actions.appendChild(status);

        function paintQuestion() {
          Dom.clear(body);
          var question = questions[current];
          body.appendChild(Dom.el(doc, 'p', 'list__meta',
            'Questão ' + (current + 1) + ' de ' + questions.length +
            (question.disciplina ? ' · ' + question.disciplina : '')));
          body.appendChild(Dom.el(doc, 'h4', 'card__title', question.enunciado || 'Questão'));
          var list = Dom.el(doc, 'ul', 'alternatives');
          (question.alternativas || []).forEach(function (alternative) {
            var letter = typeof alternative === 'string' ? alternative : alternative.letra;
            var text = typeof alternative === 'string' ? '' : alternative.texto;
            var li = Dom.el(doc, 'li');
            var label = Dom.el(doc, 'label', 'alternative');
            var input = Dom.el(doc, 'input');
            input.type = 'radio';
            input.name = 'exam-' + exam.id;
            input.value = letter;
            if (answers[question.ordem] === letter) input.checked = true;
            input.addEventListener('change', function () { answers[question.ordem] = letter; });
            label.appendChild(input);
            label.appendChild(Dom.el(doc, 'span', '', letter + (text ? ' · ' + text : '')));
            li.appendChild(label);
            list.appendChild(li);
          });
          body.appendChild(list);
          Dom.clear(actions);
          if (current > 0) {
            var prev = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Anterior');
            prev.type = 'button';
            prev.addEventListener('click', function () { current -= 1; paintQuestion(); });
            actions.appendChild(prev);
          }
          if (current < questions.length - 1) {
            var next = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Próxima');
            next.type = 'button';
            next.addEventListener('click', function () { saveAnswer(); current += 1; paintQuestion(); });
            actions.appendChild(next);
          }
          var finish = Dom.el(doc, 'button', 'btn btn--primary btn--sm', 'Finalizar');
          finish.type = 'button';
          finish.addEventListener('click', function () {
            finish.disabled = true;
            saveAnswer();
            ctx.api.post('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/finalizar', {})
              .then(function () {
                return ctx.api.get('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/resultado');
              })
              .then(function (result) { showResult(dialog, result.resultado || result, ctx); })
              .catch(function (error) { finish.disabled = false; alertInline(dialog, error.message); });
          });
          actions.appendChild(finish);
          actions.appendChild(status);
        }

        function saveAnswer() {
          var question = questions[current];
          var answer = answers[question.ordem];
          if (answer === undefined) return Promise.resolve();
          return ctx.api.post('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/responder', {
            ordem: question.ordem, resposta: answer
          }).catch(function (error) { status.textContent = error.message; });
        }

        paintQuestion();
      })
      .catch(function (error) {
        Dom.clear(dialog);
        dialog.appendChild(UI.state(doc, {
          tone: 'error', icon: 'alert', title: 'Simulado indisponível', text: error.message
        }));
      });
  }

  function showResult(container, result, ctx) {
    var doc = ctx.doc;
    Dom.clear(container);
    container.appendChild(Dom.el(doc, 'h4', 'card__title', 'Resultado'));
    var tiles = Dom.el(doc, 'div', 'panel-grid panel-grid--3');
    tiles.appendChild(UI.metricTile(doc, 'Acertos', result.acertos + '/' + result.total,
      result.basis || ''));
    tiles.appendChild(UI.metricTile(doc, 'Brancos', result.brancos || 0,
      'Contam no denominador'));
    tiles.appendChild(UI.metricTile(doc, 'Percentual',
      result.pct === null || result.pct === undefined ? '—' : Fmt.percent(result.pct),
      result.expirado ? 'Tempo expirado' : 'Tempo controlado pelo servidor'));
    container.appendChild(tiles);
    var again = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Voltar aos simulados');
    again.type = 'button';
    again.style.marginTop = '12px';
    again.addEventListener('click', function () { ctx.reload(); });
    container.appendChild(again);
  }

  function exportStudy(ctx, button) {
    button.disabled = true;
    ctx.api.get('/api/estudos/exportar').then(function (payload) {
      var blob = new global.Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
      var url = global.URL.createObjectURL(blob);
      var link = ctx.doc.createElement('a');
      link.href = url;
      link.download = 'radar-estudos-' + new Date().toISOString().slice(0, 10) + '.json';
      ctx.doc.body.appendChild(link);
      link.click();
      link.remove();
      global.setTimeout(function () { global.URL.revokeObjectURL(url); }, 1000);
      button.disabled = false;
    }).catch(function (error) {
      button.disabled = false;
      alertInline(button.parentNode, error.message);
    });
  }

  function importStudy(ctx, file) {
    var reader = new global.FileReader();
    reader.onload = function () {
      var payload;
      try {
        payload = JSON.parse(String(reader.result));
      } catch (error) {
        global.alert('Arquivo JSON inválido.');
        return;
      }
      ctx.api.post('/api/estudos/importar', {payload: payload, dry_run: true})
        .then(function (report) {
          var message = 'Prévia: ' + (report.created || 0) + ' criado(s), ' +
            (report.updated || 0) + ' atualizado(s), ' + (report.skipped || 0) + ' ignorado(s). ' +
            'Aplicar agora?';
          if (global.confirm(message)) {
            return ctx.api.post('/api/estudos/importar', {payload: payload, dry_run: false});
          }
          return null;
        })
        .then(function (report) {
          if (report) {
            global.alert('Importação concluída: ' + (report.created || 0) + ' criado(s).');
            ctx.reload();
          }
        })
        .catch(function (error) { global.alert(error.message); });
    };
    reader.readAsText(file);
  }

  global.RadarStudies = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
