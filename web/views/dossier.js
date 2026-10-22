/* Dossiê do concurso: resumo, cargo, vagas, prazos, localização, documentos e evidências. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;

  var TABS = [
    ['resumo', 'Resumo'],
    ['cargo', 'Cargo e requisitos'],
    ['vagas', 'Vagas e modalidades'],
    ['prazos', 'Prazos'],
    ['local', 'Localização'],
    ['documentos', 'Documentos'],
    ['evidencias', 'Evidências']
  ];

  var FIELD_LABEL = {
    immediate_vacancies: 'Vagas imediatas',
    vagas_total_publicado: 'Total publicado',
    reserve_vacancies: 'Cadastro de reserva',
    indigenous_vacancies: 'Vagas indígenas exclusivas',
    indigenous_reserve_vacancies: 'Reserva indígena',
    education: 'Escolaridade/requisito',
    accepted_courses: 'Cursos aceitos',
    si_compatibility: 'Compatibilidade com SI',
    registration_start: 'Início das inscrições',
    registration_end: 'Fim das inscrições',
    exam_date: 'Data da prova',
    exam_location: 'Local de prova',
    work_location: 'Local de exercício'
  };

  var DOC_TYPE = {
    edital_abertura: 'Edital de abertura', edital_retificado: 'Edital retificado',
    retificacao: 'Retificação', cronograma: 'Cronograma', comunicado: 'Comunicado',
    resultado: 'Resultado', convocacao: 'Convocação', homologacao: 'Homologação',
    gabarito: 'Gabarito', anexo: 'Anexo', pagina_concurso: 'Página do concurso',
    pagina_banca: 'Página da banca', outro: 'Documento'
  };

  var DOC_STATE = {
    baixado: ['Baixado', 'success'], localizado: ['Localizado', 'info'],
    inacessivel: ['Inacessível', 'warning'], invalido: ['Inválido', 'danger'],
    substituido: ['Substituído', 'neutral']
  };

  var EXTRACTION = {
    nao_iniciada: 'Não iniciada', em_andamento: 'Em andamento',
    parcial: 'Parcial', concluida: 'Concluída', falhou: 'Falhou'
  };

  var LOC_STATE = {
    confirmado_documentalmente: ['Confirmado documentalmente', 'success'],
    extraido_nao_revisado: ['Extraído, não revisado', 'info'],
    ambiguo: ['Ambíguo', 'warning'],
    em_conflito: ['Em conflito', 'danger'],
    nao_informado: ['Não informado', 'unknown'],
    nao_extraido: ['Não extraído', 'unknown'],
    a_divulgar: ['A divulgar', 'neutral']
  };

  var SI_STATE = {
    explicito: ['Aceitação expressa', 'success'],
    categoria_inclui_curso: ['Categoria de formação inclui o curso', 'success'],
    area_correlata_interpretacao: ['Área correlata: exige interpretação', 'warning'],
    outras_formacoes: ['Outras formações (sem citação de SI)', 'neutral'],
    nao_informado: ['Informação insuficiente', 'unknown'],
    nao_encontrado: ['Não encontrado no texto extraído', 'unknown'],
    extracao_incompleta: ['Extração incompleta', 'warning']
  };

  var INDIGENOUS_STATE = {
    explicito_imediato: ['Vaga exclusiva publicada', 'accent'],
    apenas_reserva: ['Apenas reserva (sem vaga imediata)', 'info'],
    mencao_sem_quantidade: ['Menção sem quantidade', 'neutral'],
    reserva_combinada_com_outros_grupos: ['Reserva combinada com outros grupos', 'warning'],
    nao_mencionado: ['Não mencionado no texto extraído', 'unknown'],
    fora_do_escopo_de_reserva: ['Menção fora do escopo de reserva', 'neutral'],
    reserva_sem_quantidade: ['Reserva sem quantidade', 'info']
  };

  function cleanValue(value) {
    if (typeof value !== 'string') return String(value);
    var text = value.trim();
    if (text.charAt(0) === '"' && text.charAt(text.length - 1) === '"') {
      try { return JSON.parse(text); } catch (error) { return text.slice(1, -1); }
    }
    return text;
  }

  function badge(doc, pair) {
    return UI.badge(doc, pair[0], pair[1]);
  }

  function statePair(map, key, fallback) {
    return map[key] || [fallback || String(key || 'Não informado').replace(/_/g, ' '), 'unknown'];
  }

  function safeLink(doc, url, label) {
    var href = Fmt.safeUrl(url);
    if (!href) return null;
    var link = Dom.el(doc, 'a', 'btn btn--ghost btn--sm', label || 'Abrir documento');
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.appendChild(Dom.icon(doc, 'external', 13));
    return link;
  }

  function quote(doc, text, source) {
    if (!text) return null;
    var node = Dom.el(doc, 'blockquote', 'quote', Fmt.truncate(text, 320));
    if (source) {
      var cite = Dom.el(doc, 'cite', '', source);
      node.appendChild(cite);
    }
    return node;
  }

  function render(root, ctx) {
    var doc = ctx.doc;
    var contestId = ctx.params.id;
    var query = ctx.query || new URLSearchParams();
    var tab = query.get('tab') || 'resumo';
    if (!TABS.some(function (pair) { return pair[0] === tab; })) tab = 'resumo';
    var seq = ctx.api.sequencer();
    var seqToken = seq.next();

    Dom.clear(root);
    root.appendChild(UI.loadingRows(doc, 6));

    var params = new URLSearchParams();
    params.set('contest_id', contestId);
    if (query.get('scope')) params.set('scope', query.get('scope'));
    if (query.get('role_id')) params.set('role_id', query.get('role_id'));

    Promise.all([
      ctx.api.get('/api/carteira/dossie?' + params.toString()),
      ctx.api.get('/api/concursos/' + encodeURIComponent(contestId) + '/detalhes')
    ]).then(function (results) {
      if (!seq.isCurrent(seqToken)) return;
      renderDossier(root, ctx, results[0], results[1], tab, contestId, query);
    }).catch(function (error) {
      Dom.clear(root);
      root.appendChild(UI.state(doc, {
        tone: 'error', icon: 'alert', title: 'Dossiê indisponível',
        text: error.message,
        hint: 'O concurso pode ter sido removido ou o servidor local está indisponível.',
        actions: [
          {label: 'Voltar', onClick: function () { ctx.router.back(); }},
          {label: 'Tentar novamente', primary: true, onClick: function () { render(root, ctx); }}
        ]
      }));
    });
  }

  function renderDossier(root, ctx, dossier, details, tab, contestId, query) {
    var doc = ctx.doc;
    var ident = dossier.identificacao || {};
    var prontidao = dossier.prontidao || {};
    var edital = ident.edital_principal || {};
    Dom.clear(root);

    var back = Dom.el(doc, 'a', 'dossier-head__back');
    back.href = '#/oportunidades';
    if (query.get('from') === 'oportunidades' && global.history && global.history.length > 1) {
      back.href = '#/oportunidades';
      back.addEventListener('click', function (event) {
        event.preventDefault();
        ctx.router.back();
      });
    }
    back.appendChild(Dom.icon(doc, 'arrowLeft', 14));
    back.appendChild(Dom.el(doc, 'span', '', 'Voltar aos resultados'));

    var head = Dom.el(doc, 'header', 'dossier-head');
    var main = Dom.el(doc, 'div', 'dossier-head__main');
    main.appendChild(back);
    main.appendChild(Dom.el(doc, 'h2', '', ident.contest_label || ident.contest_title || 'Concurso'));
    main.appendChild(Dom.el(doc, 'p', 'dossier-head__role',
      ident.role_name || 'Cargo ainda não reconciliado — os dados são do escopo do concurso.'));
    var meta = Dom.el(doc, 'div', 'dossier-head__meta');
    if (edital.issuer) meta.appendChild(Dom.el(doc, 'span', '', 'Banca: ' + edital.issuer));
    var local = ((dossier.localizacao || {}).prova || {}).text;
    if (local) meta.appendChild(Dom.el(doc, 'span', '', 'Prova: ' + local));
    if (ident.documentos) meta.appendChild(Dom.el(doc, 'span', '',
      Fmt.integer(ident.documentos) + ' documento(s) localizado(s)'));
    meta.appendChild(Dom.el(doc, 'span', '', 'Atualizado em ' + Fmt.date(dossier.generated_at)));
    main.appendChild(meta);
    var badges = Dom.el(doc, 'div', 'list__badges');
    badges.style.marginTop = '12px';
    badges.appendChild(UI.badge(doc, prontidao.estado_label || 'Sem estado',
      prontidao.estado === 'oportunidade_historica' ? 'neutral' : 'info'));
    if (dossier.conflitos && (dossier.conflitos.oportunidade || []).length) {
      badges.appendChild(UI.badge(doc, 'Conflito documental', 'danger'));
    }
    main.appendChild(badges);
    head.appendChild(main);

    var actions = Dom.el(doc, 'div', 'dossier-head__actions');
    var official = safeLink(doc, edital.official_url, 'Documento oficial');
    if (official) actions.appendChild(official);
    var operation = Dom.el(doc, 'a', 'btn btn--ghost btn--sm', 'Abrir na operação');
    operation.href = '#/operacao';
    actions.appendChild(operation);
    head.appendChild(actions);
    root.appendChild(head);

    var tabs = Dom.el(doc, 'div', 'tabs');
    tabs.setAttribute('role', 'tablist');
    tabs.setAttribute('aria-label', 'Seções do dossiê');
    TABS.forEach(function (pair) {
      var button = Dom.el(doc, 'button', 'tab', pair[1]);
      button.type = 'button';
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', pair[0] === tab ? 'true' : 'false');
      button.addEventListener('click', function () {
        var next = new URLSearchParams(query.toString());
        next.set('tab', pair[0]);
        ctx.router.replaceQuery(next);
        renderDossier(root, ctx, dossier, details, pair[0], contestId, next);
      });
      tabs.appendChild(button);
    });
    root.appendChild(tabs);

    var panel = Dom.el(doc, 'section');
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-label', (TABS.find(function (pair) { return pair[0] === tab; }) || [])[1] || 'Dossiê');
    root.appendChild(panel);

    if (tab === 'resumo') panel.appendChild(summaryTab(doc, dossier, details, ctx));
    else if (tab === 'cargo') panel.appendChild(cargoTab(doc, dossier));
    else if (tab === 'vagas') panel.appendChild(vagasTab(doc, dossier));
    else if (tab === 'prazos') panel.appendChild(prazosTab(doc, dossier, ctx));
    else if (tab === 'local') panel.appendChild(localTab(doc, dossier));
    else if (tab === 'documentos') panel.appendChild(documentsTab(doc, details));
    else panel.appendChild(evidenceTab(doc, dossier, details));
  }

  function summaryTab(doc, dossier, details, ctx) {
    var wrap = Dom.el(doc, 'div', 'panel-grid panel-grid--2');
    var vagas = dossier.vagas || {};
    var ident = dossier.identificacao || {};
    var edital = ident.edital_principal || {};

    var nextAction = UI.card(doc, {
      title: 'Próxima ação recomendada',
      sub: 'A recomendação não confirma nenhum campo.'
    });
    var body = nextAction.querySelector('.card__body');
    body.appendChild(Dom.el(doc, 'p', 'metric-tile__value',
      dossier.proxima_acao || 'Nenhuma ação pendente identificada.'));
    var readiness = dossier.prontidao || {};
    body.appendChild(Dom.el(doc, 'p', 'card__sub', readiness.estado_label || ''));
    (readiness.motivos || []).forEach(function (reason) {
      body.appendChild(Dom.el(doc, 'p', 'list__meta', '· ' + reason));
    });
    wrap.appendChild(nextAction);

    var numbers = UI.card(doc, {
      title: 'Números publicados', sub: 'Cada número pertence ao campo de origem.'
    });
    var numbersBody = numbers.querySelector('.card__body');
    var grid = Dom.el(doc, 'div', 'panel-grid panel-grid--2');
    grid.appendChild(UI.metricTile(doc, 'Total publicado',
      valueOf(vagas.total_publicado), stateOf(vagas.total_publicado)));
    grid.appendChild(UI.metricTile(doc, 'Vagas imediatas',
      valueOf(vagas.imediatas), stateOf(vagas.imediatas)));
    grid.appendChild(UI.metricTile(doc, 'Cadastro de reserva',
      valueOf(vagas.reserva), stateOf(vagas.reserva)));
    var indigenous = vagas.indigenas || {};
    grid.appendChild(UI.metricTile(doc, 'Reserva indígena',
      indigenous.estado_label || 'Não informado',
      'Âmbito: ' + (indigenous.ambito || 'não informado')));
    numbersBody.appendChild(grid);
    wrap.appendChild(numbers);

    var gaps = UI.card(doc, {title: 'Lacunas e conflitos', sub: 'O que ainda falta para decidir.'});
    var gapsBody = gaps.querySelector('.card__body');
    var lacunas = dossier.lacunas || [];
    if (!lacunas.length) {
      gapsBody.appendChild(Dom.el(doc, 'p', 'card__sub', 'Nenhuma lacuna registrada para este recorte.'));
    } else {
      var list = Dom.el(doc, 'ul', 'list');
      lacunas.slice(0, 6).forEach(function (gap) {
        var item = Dom.el(doc, 'li', 'list__item');
        var main = Dom.el(doc, 'div', 'list__main');
        main.appendChild(Dom.el(doc, 'p', 'list__title', Fmt.truncate(gap, 120)));
        item.appendChild(main);
        list.appendChild(item);
      });
      gapsBody.appendChild(list);
    }
    var conflicts = ((dossier.conflitos || {}).oportunidade) || [];
    if (conflicts.length) {
      gapsBody.appendChild(Dom.el(doc, 'p', 'list__meta',
        Fmt.integer(conflicts.length) + ' conflito(s) entre documentos/versões.'));
    }
    wrap.appendChild(gaps);

    var deadlines = UI.card(doc, {
      title: 'Próximos prazos', sub: 'Somente datas futuras com estado de verificação.',
      link: {label: 'Ver todos', href: '#/prazos'}
    });
    var deadlineBody = deadlines.querySelector('.card__body');
    var future = (dossier.prazos || []).filter(function (item) {
      return item.estado_temporal === 'futuro';
    }).slice(0, 4);
    if (!future.length) {
      deadlineBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'calendar', title: 'Sem prazo futuro registrado',
        text: 'Datas passadas permanecem no histórico; datas candidatas não são tratadas como confirmadas.'
      }));
    } else {
      var dlist = Dom.el(doc, 'ul', 'list');
      future.forEach(function (item) {
        var li = Dom.el(doc, 'li', 'list__item');
        var main = Dom.el(doc, 'div', 'list__main');
        main.appendChild(Dom.el(doc, 'p', 'list__title', item.grupo_label));
        main.appendChild(Dom.el(doc, 'p', 'list__meta',
          Fmt.date(item.valor) + ' · ' + item.estado_operacional_label));
        li.appendChild(main);
        var aside = Dom.el(doc, 'div', 'list__aside');
        aside.appendChild(Dom.el(doc, 'strong', '', Fmt.relativeDays(item.dias_restantes)));
        li.appendChild(aside);
        dlist.appendChild(li);
      });
      deadlineBody.appendChild(dlist);
    }
    wrap.appendChild(deadlines);

    var docs = UI.card(doc, {
      title: 'Documento principal', sub: 'A fonte oficial continua sendo a referência final.'
    });
    var docsBody = docs.querySelector('.card__body');
    if (!edital || !edital.title) {
      docsBody.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'doc', title: 'Edital não localizado',
        text: 'Há documentos do concurso, mas nenhum foi classificado como edital principal.'
      }));
    } else {
      docsBody.appendChild(docItem(doc, {
        title: edital.title, tipo: edital.tipo, issuer: edital.issuer,
        published_at: edital.published_at, official_url: edital.official_url,
        versions: edital.versoes, pages: edital.paginas_extraidas
      }, true));
      if ((ident.retificacoes || []).length) {
        docsBody.appendChild(Dom.el(doc, 'p', 'card__sub',
          Fmt.integer(ident.retificacoes.length) + ' retificação(ões) vinculada(s).'));
      }
    }
    wrap.appendChild(docs);
    return wrap;
  }

  function valueOf(field) {
    if (!field) return '—';
    var values = field.valores || [];
    if (!values.length) return '—';
    return values.map(cleanValue).join(' · ');
  }

  function stateOf(field) {
    if (!field) return 'Campo não extraído';
    var labels = {
      nao_extraido: 'Não extraído', multiplo_por_cargo: 'Múltiplo por cargo',
      candidato: 'Candidato', ambiguo: 'Ambíguo', confirmado: 'Confirmado'
    };
    return labels[field.estado] || String(field.estado || 'Não extraído').replace(/_/g, ' ');
  }

  function cargoTab(doc, dossier) {
    var formacao = dossier.formacao || {};
    var wrap = Dom.el(doc, 'div', 'panel-grid panel-grid--2');

    var requirement = UI.card(doc, {
      title: 'Requisito de formação',
      sub: 'Texto literal do edital para o cargo/escopo. Não é paráfrase.'
    });
    var body = requirement.querySelector('.card__body');
    var requisito = formacao.requisito;
    if (!requisito || !(requisito.valores || []).length) {
      body.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'book', title: 'Requisito não extraído',
        text: 'Ausência de extração não prova incompatibilidade; consulte o edital oficial.',
        actions: [{label: 'Ver documentos', onClick: function () {
          var tab = doc.querySelector('.tab[aria-selected="false"]');
          if (tab) tab.focus();
        }}]
      }));
    } else {
      body.appendChild(UI.badge(doc, stateOf(requisito), 'neutral'));
      var values = requisito.valores.map(cleanValue);
      values.slice(0, 4).forEach(function (text) {
        body.appendChild(quote(doc, text, 'Requisito publicado'));
      });
      if (values.length > 4) {
        body.appendChild(Dom.el(doc, 'p', 'card__sub',
          '+' + (values.length - 4) + ' variação(ões) por cargo.'));
      }
    }
    wrap.appendChild(requirement);

    var si = UI.card(doc, {
      title: 'Sistemas de Informação', sub: 'Compatibilidade calculada, nunca presumida.'
    });
    var siBody = si.querySelector('.card__body');
    var siState = formacao.si_por_cargo || {};
    var pair = statePair(SI_STATE, siState.estado, 'Informação insuficiente');
    siBody.appendChild(badge(doc, pair));
    if (siState.estado_label) {
      siBody.appendChild(Dom.el(doc, 'p', 'card__sub', siState.estado_label));
    }
    siBody.appendChild(Dom.el(doc, 'p', 'card__sub', formacao.nota || ''));
    wrap.appendChild(si);

    var courses = UI.card(doc, {
      title: 'Cursos aceitos', sub: 'Cursos citados no requisito, quando houver.'
    });
    var courseBody = courses.querySelector('.card__body');
    var accepted = formacao.cursos_aceitos;
    if (!accepted || !(accepted.valores || []).length) {
      courseBody.appendChild(Dom.el(doc, 'p', 'card__sub', 'Nenhum curso explicitamente listado.'));
    } else {
      accepted.valores.map(cleanValue).forEach(function (text) {
        courseBody.appendChild(quote(doc, text, 'Cursos aceitos'));
      });
    }
    wrap.appendChild(courses);

    var notes = UI.card(doc, {
      title: 'O que este dossiê não afirma', sub: 'Limites explícitos do modelo.'
    });
    var notesBody = notes.querySelector('.card__body');
    notesBody.appendChild(Dom.el(doc, 'p', 'card__sub',
      'Cargo de tecnologia não garante aceitação de Sistemas de Informação. ' +
      'Escolaridade mínima não é formação específica. Requisitos adicionais (registro, ' +
      'experiência, habilitação) são campos separados e podem não ter sido extraídos.'));
    wrap.appendChild(notes);
    return wrap;
  }

  function vagasTab(doc, dossier) {
    var vagas = dossier.vagas || {};
    var wrap = Dom.el(doc, 'div', 'panel-grid panel-grid--2');
    var cards = [
      ['Total publicado', vagas.total_publicado, 'Número do edital; não é distribuição por modalidade.'],
      ['Vagas imediatas', vagas.imediatas, 'Quantidade publicada para provimento imediato.'],
      ['Cadastro de reserva', vagas.reserva, 'Não é vaga imediata e não deve ser somado a ela.'],
    ];
    cards.forEach(function (entry) {
      var card = UI.card(doc, {title: entry[0], sub: entry[2]});
      var body = card.querySelector('.card__body');
      var field = entry[1] || {};
      body.appendChild(Dom.el(doc, 'p', 'metric-tile__value', valueOf(field)));
      body.appendChild(Dom.el(doc, 'p', 'card__sub', stateOf(field)));
      (field.evidencias || []).slice(0, 3).forEach(function (evidence) {
        body.appendChild(quote(doc, evidence.quote,
          (evidence.document_title || 'Documento') +
          (evidence.page_number ? ' · p. ' + evidence.page_number : '')));
      });
      wrap.appendChild(card);
    });

    var indigenous = UI.card(doc, {
      title: 'Reserva indígena', sub: 'Escopo e natureza declarados; nunca derivada de total agregado.'
    });
    var indBody = indigenous.querySelector('.card__body');
    var ind = vagas.indigenas || {};
    var pair = statePair(INDIGENOUS_STATE, ind.estado, 'Não informado');
    indBody.appendChild(badge(doc, pair));
    indBody.appendChild(Dom.el(doc, 'p', 'card__sub', ind.estado_label || ''));
    if (ind.nota) indBody.appendChild(Dom.el(doc, 'p', 'card__sub', ind.nota));
    if (ind.mencao && ind.mencao.quote) {
      indBody.appendChild(quote(doc, ind.mencao.quote,
        (ind.mencao.contexto_label || 'Menção') +
        (ind.mencao.page_number ? ' · p. ' + ind.mencao.page_number : '')));
    }
    var indCounts = Dom.el(doc, 'div', 'panel-grid panel-grid--2');
    indCounts.style.marginTop = '12px';
    indCounts.appendChild(UI.metricTile(doc, 'Propostas de vaga imediata',
      Fmt.integer((ind.imediata || []).length), 'Quantidade de leituras, não soma.'));
    indCounts.appendChild(UI.metricTile(doc, 'Propostas de reserva',
      Fmt.integer((ind.reserva || []).length), 'Quantidade de leituras, não soma.'));
    indBody.appendChild(indCounts);
    if (ind.derivado_de_agregado) {
      indBody.appendChild(UI.inlineError(doc,
        'A reserva foi derivada de total agregado — isso não é permitido pelo modelo.'));
    }
    wrap.appendChild(indigenous);

    var note = UI.card(doc, {title: 'Como ler estes números', sub: 'Regras de integridade aplicadas.'});
    var noteBody = note.querySelector('.card__body');
    noteBody.appendChild(Dom.el(doc, 'p', 'card__sub', vagas.nota || ''));
    noteBody.appendChild(Dom.el(doc, 'p', 'card__sub',
      'Vagas exclusivas, reservas unificadas e cadastro de reserva são categorias distintas. ' +
      'Este dossiê não rateia, não soma categorias incompatíveis e não transforma ausência em zero.'));
    wrap.appendChild(note);
    return wrap;
  }

  function prazosTab(doc, dossier, ctx) {
    var wrap = Dom.el(doc, 'div');
    var prazos = (dossier.prazos || []).slice().sort(function (a, b) {
      return (a.prioridade_grupo || 99) - (b.prioridade_grupo || 99);
    });
    if (!prazos.length) {
      wrap.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'calendar', title: 'Nenhum prazo extraído',
        text: 'O edital pode não ter datas legíveis ou a extração ainda não cobriu esse trecho.'
      }));
      return wrap;
    }
    var tableWrap = Dom.el(doc, 'div', 'table-wrap');
    var table = Dom.el(doc, 'table', 'data-table-main');
    var thead = Dom.el(doc, 'thead');
    var head = Dom.el(doc, 'tr');
    ['Evento', 'Data', 'Situação', 'Documento', 'Trecho'].forEach(function (label) {
      head.appendChild(Dom.el(doc, 'th', '', label));
    });
    thead.appendChild(head);
    table.appendChild(thead);
    var tbody = Dom.el(doc, 'tbody');
    prazos.forEach(function (item) {
      var tr = Dom.el(doc, 'tr');
      var event = Dom.el(doc, 'td');
      event.setAttribute('data-label', 'Evento');
      event.appendChild(Dom.el(doc, 'span', 'cell-strong', item.grupo_label));
      if (item.escopo_rotulo) {
        event.appendChild(Dom.el(doc, 'span', 'cell-sub', item.escopo_rotulo));
      }
      tr.appendChild(event);
      var date = Dom.el(doc, 'td', 'cell-num');
      date.setAttribute('data-label', 'Data');
      date.appendChild(Dom.el(doc, 'span', 'cell-strong',
        item.valor ? Fmt.date(item.valor) : '—'));
      if (item.dias_restantes !== null && item.dias_restantes !== undefined) {
        date.appendChild(Dom.el(doc, 'span', 'cell-sub', Fmt.relativeDays(item.dias_restantes)));
      }
      tr.appendChild(date);
      var state = Dom.el(doc, 'td');
      state.setAttribute('data-label', 'Situação');
      state.appendChild(UI.badge(doc, item.urgencia_label || item.estado_temporal,
        item.urgencia === 'vencido' ? 'neutral' :
          item.estado_operacional === 'conflito_documental' ? 'danger' : 'info'));
      state.appendChild(Dom.el(doc, 'span', 'cell-sub', item.estado_operacional_label || ''));
      tr.appendChild(state);
      var source = Dom.el(doc, 'td');
      source.setAttribute('data-label', 'Documento');
      source.appendChild(Dom.el(doc, 'span', 'cell-sub',
        (item.documento || 'Não identificado') +
        (item.pagina ? ' · p. ' + item.pagina : '')));
      var link = safeLink(doc, item.official_url, 'Abrir');
      if (link) source.appendChild(link);
      tr.appendChild(source);
      var quoteCell = Dom.el(doc, 'td');
      quoteCell.setAttribute('data-label', 'Trecho');
      quoteCell.appendChild(Dom.el(doc, 'span', 'cell-sub', Fmt.truncate(item.trecho, 140)));
      tr.appendChild(quoteCell);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    wrap.appendChild(tableWrap);
    wrap.appendChild(Dom.el(doc, 'p', 'card__sub',
      'Datas candidatas não são prazo confirmado. Uma publicação mais recente não altera ' +
      'todos os campos anteriores; cada evento tem documento, versão e trecho.'));
    return wrap;
  }

  function localTab(doc, dossier) {
    var local = dossier.localizacao || {};
    var wrap = Dom.el(doc, 'div', 'panel-grid panel-grid--2');
    [['Local de prova', local.prova], ['Lotação / exercício', local.lotacao]]
      .forEach(function (entry) {
        var card = UI.card(doc, {title: entry[0], sub: 'Resolvido separadamente; um não substitui o outro.'});
        var body = card.querySelector('.card__body');
        var info = entry[1] || {};
        var pair = statePair(LOC_STATE, info.state, 'Não informado');
        body.appendChild(badge(doc, pair));
        body.appendChild(Dom.el(doc, 'p', 'metric-tile__value',
          info.text || (info.municipios || []).join(', ') || '—'));
        body.appendChild(Dom.el(doc, 'p', 'card__sub',
          (info.reason || 'Sem motivo registrado.') +
          (info.confidence ? ' · confiança ' + info.confidence : '')));
        if (info.evidence && info.evidence.quote) {
          body.appendChild(quote(doc, info.evidence.quote,
            'p. ' + (info.evidence.page_number || '—')));
        }
        wrap.appendChild(card);
      });
    var note = UI.card(doc, {title: 'Regra aplicada', sub: 'Localização não é inferida.'});
    note.querySelector('.card__body').appendChild(Dom.el(doc, 'p', 'card__sub',
      local.nota || 'Prova e lotação são separadas.'));
    wrap.appendChild(note);
    return wrap;
  }

  function docItem(doc, item, principal) {
    var wrap = Dom.el(doc, 'div', 'doc-item');
    var icon = Dom.el(doc, 'span', 'doc-item__icon');
    icon.appendChild(Dom.icon(doc, 'doc', 16));
    wrap.appendChild(icon);
    var main = Dom.el(doc, 'div', 'doc-item__main');
    main.appendChild(Dom.el(doc, 'p', 'doc-item__title', item.title || 'Documento'));
    var statePairValue = statePair(DOC_STATE, item.state, 'Estado não informado');
    var meta = Dom.el(doc, 'p', 'doc-item__meta');
    meta.appendChild(Dom.el(doc, 'span', '', (DOC_TYPE[item.tipo] || DOC_TYPE[item.document_type] || 'Documento') + ' · '));
    var badgeNode = UI.badge(doc, statePairValue[0], statePairValue[1]);
    badgeNode.style.marginRight = '6px';
    meta.appendChild(badgeNode);
    if (item.issuer) meta.appendChild(Dom.el(doc, 'span', '', ' · ' + item.issuer));
    if (item.published_at) meta.appendChild(Dom.el(doc, 'span', '', ' · ' + Fmt.date(item.published_at)));
    if (item.versions) meta.appendChild(Dom.el(doc, 'span', '', ' · ' + Fmt.integer(item.versions) + ' versão(ões)'));
    if (item.pages) meta.appendChild(Dom.el(doc, 'span', '', ' · ' + Fmt.integer(item.pages) + ' pág. extraídas'));
    main.appendChild(meta);
    wrap.appendChild(main);
    var actions = Dom.el(doc, 'div', 'doc-item__actions');
    var link = safeLink(doc, item.official_url, 'Abrir');
    if (link) actions.appendChild(link);
    wrap.appendChild(actions);
    if (principal) wrap.style.paddingTop = '0';
    return wrap;
  }

  function documentsTab(doc, details) {
    var documents = (details && details.documents) || [];
    var wrap = Dom.el(doc, 'div');
    if (!documents.length) {
      wrap.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'doc', title: 'Nenhum documento localizado',
        text: 'O concurso existe na base, mas ainda não tem documento associado.'
      }));
      return wrap;
    }
    var card = UI.card(doc, {
      title: 'Documentos oficiais', sub: 'Documento principal, versões e retificações.'
    });
    var body = card.querySelector('.card__body');
    documents.forEach(function (document) {
      var item = docItem(doc, {
        title: document.title, tipo: document.document_type, issuer: document.issuer,
        published_at: document.published_at, official_url: document.official_url,
        state: document.state, versions: (document.versions || []).length
      });
      body.appendChild(item);
      if ((document.versions || []).length) {
        var detailsNode = Dom.el(doc, 'details', 'data-table');
        detailsNode.appendChild(Dom.el(doc, 'summary', '',
          'Versões e estado de extração (' + document.versions.length + ')'));
        var list = Dom.el(doc, 'ul', 'list');
        document.versions.forEach(function (version) {
          var li = Dom.el(doc, 'li', 'list__item');
          var main = Dom.el(doc, 'div', 'list__main');
          main.appendChild(Dom.el(doc, 'p', 'list__title',
            'Coletada em ' + Fmt.dateTime(version.fetched_at)));
          main.appendChild(Dom.el(doc, 'p', 'list__meta',
            (EXTRACTION[version.extraction_state] || version.extraction_state) +
            (version.byte_size ? ' · ' + Fmt.integer(version.byte_size) + ' bytes' : '') +
            (version.error_code ? ' · ' + version.error_code : '')));
          li.appendChild(main);
          list.appendChild(li);
        });
        detailsNode.appendChild(list);
        body.appendChild(detailsNode);
      }
    });
    wrap.appendChild(card);
    return wrap;
  }

  function evidenceTab(doc, dossier, details) {
    var proposals = (details && details.proposals) || [];
    var wrap = Dom.el(doc, 'div');
    if (!proposals.length) {
      wrap.appendChild(UI.state(doc, {
        tone: 'empty', icon: 'empty', title: 'Nenhuma evidência extraída',
        text: 'O documento pode estar sem camada de texto ou a extração ainda não foi executada.'
      }));
      return wrap;
    }
    var card = UI.card(doc, {
      title: 'Evidências extraídas', sub: 'Trecho literal, página e documento de origem.'
    });
    var body = card.querySelector('.card__body');
    var list = Dom.el(doc, 'ul', 'evidence-list');
    proposals.slice(0, 30).forEach(function (proposal) {
      var item = Dom.el(doc, 'li', 'evidence-item');
      var head = Dom.el(doc, 'div', 'evidence-item__head');
      head.appendChild(UI.badge(doc, FIELD_LABEL[proposal.field_name] || proposal.field_name, 'neutral'));
      if (proposal.page_number) head.appendChild(Dom.el(doc, 'span', '', 'p. ' + proposal.page_number));
      head.appendChild(Dom.el(doc, 'span', 'evidence-item__value',
        proposal.value === null || proposal.value === undefined ? '—' : String(proposal.value)));
      item.appendChild(head);
      if (proposal.quote) item.appendChild(quote(doc, proposal.quote, proposal.document_title));
      list.appendChild(item);
    });
    body.appendChild(list);
    if (proposals.length > 30) {
      body.appendChild(Dom.el(doc, 'p', 'card__sub',
        'Mostrando 30 de ' + proposals.length + ' propostas. A revisão completa fica na operação.'));
    }
    wrap.appendChild(card);
    return wrap;
  }

  global.RadarDossier = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
