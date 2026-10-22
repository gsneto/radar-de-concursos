/* Oportunidades: busca, filtros combináveis, ordenação e paginação reais. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;
  var UI = global.RadarUI;

  var PAGE_SIZE = 20;
  var PRONTIDAO = {
    oportunidade_historica: 'Oportunidade histórica',
    identidade_cargo_pendente: 'Identidade pendente',
    campos_decisivos_ausentes: 'Campos ausentes',
    conflito_documental_pendente: 'Conflito documental'
  };
  var SI = {
    explicito: 'Aceitação expressa',
    categoria_inclui_curso: 'Categoria inclui o curso',
    area_correlata_interpretacao: 'Exige interpretação',
    outras_formacoes: 'Outras formações',
    nao_informado: 'Não informado'
  };
  var INDIGENA = {
    explicito_imediato: 'Vaga exclusiva',
    apenas_reserva: 'Apenas reserva',
    mencao_sem_quantidade: 'Menção sem quantidade',
    reserva_combinada_com_outros_grupos: 'Reserva combinada',
    nao_mencionado: 'Não mencionado'
  };
  var PRAZO = {
    hoje: 'Hoje', ate_7_dias: 'Até 7 dias', ate_30_dias: 'Até 30 dias',
    futuro: 'Futuro', vencido: 'Vencido', sem_data: 'Sem data'
  };
  var DOCUMENTAL = {
    campos_confirmados: 'Campos confirmados',
    campos_candidatos: 'Campos candidatos',
    edital_extraido: 'Edital extraído',
    conflito: 'Documentação conflitante',
    oficial_sem_extracao: 'Oficial sem extração',
    oficial_sem_edital: 'Oficial sem edital',
    identidade_pendente: 'Identidade pendente',
    obtencao_nao_autorizada: 'Obtenção não autorizada',
    oficial_nao_importado: 'Oficial não importado',
    apenas_agregador: 'Apenas agregador',
    fonte_nao_catalogada: 'Fonte não catalogada',
    sem_documento: 'Sem documento'
  };
  var UFS = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
    'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'];
  var TONE = {
    oportunidade_historica: 'neutral', identidade_cargo_pendente: 'warning',
    campos_decisivos_ausentes: 'info', conflito_documental_pendente: 'danger'
  };

  function humanize(map, value) {
    return map[value] || String(value || '—').replace(/_/g, ' ');
  }

  function readFilters(query) {
    return {
      q: query.get('q') || '',
      uf: query.get('uf') || '',
      prontidao: query.get('prontidao') || '',
      si: query.get('si') || '',
      indigena: query.get('indigena') || '',
      prazo: query.get('prazo') || '',
      documental: query.get('documental') || '',
      conflito: query.get('conflito') || ''
    };
  }

  function toQuery(filters, offset, sort) {
    var params = new URLSearchParams();
    Object.keys(filters).forEach(function (key) {
      if (filters[key]) params.set(key, filters[key]);
    });
    if (offset) params.set('offset', String(offset));
    if (sort && sort !== 'prioridade') params.set('sort', sort);
    return params;
  }

  function apiQuery(filters, offset) {
    var params = new URLSearchParams();
    if (filters.q) params.set('search', filters.q);
    if (filters.uf) params.set('uf', filters.uf);
    if (filters.prontidao) params.set('prontidao', filters.prontidao);
    if (filters.si) params.set('si', filters.si);
    if (filters.indigena) params.set('indigena', filters.indigena);
    if (filters.prazo) params.set('prazo', filters.prazo);
    if (filters.documental) params.set('documental', filters.documental);
    if (filters.conflito) params.set('conflito', filters.conflito);
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', String(offset));
    return params.toString();
  }

  function dossierHref(item) {
    var params = new URLSearchParams();
    if (item.scope) params.set('scope', item.scope);
    if (item.role_id) params.set('role_id', item.role_id);
    params.set('from', 'oportunidades');
    var query = params.toString();
    return '#/dossie/' + encodeURIComponent(item.contest_id) + (query ? '?' + query : '');
  }

  function nextDeadline(item) {
    var list = (item.prazos || []).filter(function (deadline) {
      return deadline.estado_temporal === 'futuro' && deadline.dias_restantes !== null;
    }).sort(function (a, b) { return a.dias_restantes - b.dias_restantes; });
    return list[0] || null;
  }

  function sortItems(items, sort) {
    var copy = items.slice();
    if (sort === 'prazo') {
      copy.sort(function (a, b) {
        var da = nextDeadline(a);
        var db = nextDeadline(b);
        var va = da ? da.dias_restantes : 9999;
        var vb = db ? db.dias_restantes : 9999;
        return va - vb || String(a.contest_label || '').localeCompare(String(b.contest_label || ''));
      });
    } else if (sort === 'atualizacao') {
      copy.sort(function (a, b) {
        return String(b.ultima_atualizacao || '').localeCompare(String(a.ultima_atualizacao || ''));
      });
    } else if (sort === 'concurso') {
      copy.sort(function (a, b) {
        return String(a.contest_label || '').localeCompare(String(b.contest_label || ''));
      });
    }
    return copy;
  }

  function field(doc, label, control) {
    var wrap = Dom.el(doc, 'div', 'field');
    var id = control.id;
    var lab = Dom.el(doc, 'label', '', label);
    lab.setAttribute('for', id);
    wrap.appendChild(lab);
    wrap.appendChild(control);
    return wrap;
  }

  function select(doc, id, options, value, allLabel) {
    var node = Dom.el(doc, 'select', 'select');
    node.id = id;
    var first = Dom.el(doc, 'option', '', allLabel || 'Todos');
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

  function render(root, ctx) {
    var doc = ctx.doc;
    var query = ctx.query || new URLSearchParams();
    var filters = readFilters(query);
    var sort = query.get('sort') || 'prioridade';
    var offset = Math.max(0, parseInt(query.get('offset') || '0', 10) || 0);
    var lastResult = null;
    var seq = ctx.api.sequencer();

    Dom.clear(root);

    var head = Dom.el(doc, 'header', 'page-head');
    var text = Dom.el(doc, 'div', 'page-head__text');
    text.appendChild(Dom.el(doc, 'p', 'eyebrow', 'Busca'));
    text.appendChild(Dom.el(doc, 'h2', '', 'Oportunidades'));
    text.appendChild(Dom.el(doc, 'p', 'page-head__sub',
      'Cada linha é um concurso e cargo com documento oficial, lacunas explícitas e próxima ação. ' +
      'A busca nacional não é limitada pelas preferências regionais.'));
    head.appendChild(text);
    var headActions = Dom.el(doc, 'div', 'page-head__actions');
    var clear = Dom.el(doc, 'button', 'btn btn--ghost', 'Limpar filtros');
    clear.type = 'button';
    clear.addEventListener('click', function () { apply({}, 0, 'prioridade'); });
    headActions.appendChild(clear);
    head.appendChild(headActions);
    root.appendChild(head);

    var filtersBox = Dom.el(doc, 'section', 'filters');
    filtersBox.setAttribute('aria-label', 'Filtros de oportunidades');
    var searchWrap = Dom.el(doc, 'div', 'searchbar');
    searchWrap.appendChild(Dom.icon(doc, 'search', 17));
    var search = Dom.el(doc, 'input');
    search.type = 'search';
    search.id = 'op-search';
    search.placeholder = 'Buscar por concurso, órgão, cargo ou especialidade';
    search.value = filters.q;
    search.setAttribute('aria-label', 'Buscar oportunidades');
    searchWrap.appendChild(search);
    filtersBox.appendChild(searchWrap);

    var row = Dom.el(doc, 'div', 'filter-row');
    var uf = select(doc, 'op-uf', UFS.reduce(function (acc, ufValue) {
      acc[ufValue] = ufValue; return acc;
    }, {}), filters.uf, 'Todas as UFs');
    row.appendChild(field(doc, 'UF', uf));
    var readiness = select(doc, 'op-prontidao', PRONTIDAO, filters.prontidao, 'Todas');
    row.appendChild(field(doc, 'Prontidão', readiness));
    var si = select(doc, 'op-si', SI, filters.si, 'Todas');
    row.appendChild(field(doc, 'Sistemas de Informação', si));
    var indigenous = select(doc, 'op-indigena', INDIGENA, filters.indigena, 'Todas');
    row.appendChild(field(doc, 'Reserva indígena', indigenous));
    var deadline = select(doc, 'op-prazo', PRAZO, filters.prazo, 'Todos');
    row.appendChild(field(doc, 'Prazo', deadline));
    var spacer = Dom.el(doc, 'span', 'spacer');
    row.appendChild(spacer);
    var sortSelect = Dom.el(doc, 'select', 'select');
    sortSelect.id = 'op-sort';
    [['prioridade', 'Prioridade (servidor)'], ['prazo', 'Prazo (página)'],
     ['atualizacao', 'Atualização (página)'], ['concurso', 'Concurso (página)']]
      .forEach(function (pair) {
        var option = Dom.el(doc, 'option', '', pair[1]);
        option.value = pair[0];
        if (pair[0] === sort) option.selected = true;
        sortSelect.appendChild(option);
      });
    row.appendChild(field(doc, 'Ordenar', sortSelect));
    var advancedButton = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Filtros avançados');
    advancedButton.type = 'button';
    advancedButton.setAttribute('aria-expanded', 'false');
    advancedButton.setAttribute('aria-controls', 'op-advanced');
    row.appendChild(advancedButton);
    filtersBox.appendChild(row);

    var advanced = Dom.el(doc, 'div', 'filter-row');
    advanced.id = 'op-advanced';
    advanced.hidden = !(filters.documental || filters.conflito);
    var documental = select(doc, 'op-documental', DOCUMENTAL, filters.documental, 'Todas');
    advanced.appendChild(field(doc, 'Situação documental', documental));
    var conflict = Dom.el(doc, 'select', 'select');
    conflict.id = 'op-conflito';
    [['', 'Todos'], ['sim', 'Com conflito'], ['nao', 'Sem conflito']].forEach(function (pair) {
      var option = Dom.el(doc, 'option', '', pair[1]);
      option.value = pair[0];
      if (pair[0] === filters.conflito) option.selected = true;
      conflict.appendChild(option);
    });
    advanced.appendChild(field(doc, 'Conflito', conflict));
    filtersBox.appendChild(advanced);
    advancedButton.addEventListener('click', function () {
      advanced.hidden = !advanced.hidden;
      advancedButton.setAttribute('aria-expanded', advanced.hidden ? 'false' : 'true');
    });

    var chips = Dom.el(doc, 'div', 'chips');
    chips.id = 'op-chips';
    filtersBox.appendChild(chips);
    root.appendChild(filtersBox);

    var meta = Dom.el(doc, 'div', 'results-meta');
    var count = Dom.el(doc, 'span');
    count.id = 'op-count';
    count.textContent = 'Carregando oportunidades…';
    meta.appendChild(count);
    var hint = Dom.el(doc, 'span', '', 'Ordenação por prioridade segue a ordem determinística do servidor.');
    meta.appendChild(hint);
    root.appendChild(meta);

    var results = Dom.el(doc, 'div');
    results.id = 'op-results';
    root.appendChild(results);

    var pager = Dom.el(doc, 'nav', 'pagination');
    pager.setAttribute('aria-label', 'Paginação de oportunidades');
    root.appendChild(pager);

    function currentFilters() {
      return {
        q: search.value.trim(), uf: uf.value, prontidao: readiness.value, si: si.value,
        indigena: indigenous.value, prazo: deadline.value, documental: documental.value,
        conflito: conflict.value
      };
    }

    function apply(next, nextOffset, nextSort) {
      var params = toQuery(next, nextOffset, nextSort);
      ctx.router.replaceQuery(params);
      render(root, Object.assign({}, ctx, {query: params}));
    }

    function commit() {
      apply(currentFilters(), 0, sortSelect.value);
    }

    search.addEventListener('change', commit);
    search.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        commit();
      }
    });
    [uf, readiness, si, indigenous, deadline, documental, conflict, sortSelect]
      .forEach(function (control) {
        control.addEventListener('change', function () {
          apply(currentFilters(), 0, sortSelect.value);
        });
      });

    function renderChips() {
      Dom.clear(chips);
      var active = [];
      if (filters.q) active.push(['q', 'Busca: ' + filters.q]);
      if (filters.uf) active.push(['uf', 'UF: ' + filters.uf]);
      if (filters.prontidao) active.push(['prontidao', humanize(PRONTIDAO, filters.prontidao)]);
      if (filters.si) active.push(['si', 'SI: ' + humanize(SI, filters.si)]);
      if (filters.indigena) active.push(['indigena', 'Indígena: ' + humanize(INDIGENA, filters.indigena)]);
      if (filters.prazo) active.push(['prazo', 'Prazo: ' + humanize(PRAZO, filters.prazo)]);
      if (filters.documental) active.push(['documental', humanize(DOCUMENTAL, filters.documental)]);
      if (filters.conflito) active.push(['conflito', filters.conflito === 'sim' ? 'Com conflito' : 'Sem conflito']);
      active.forEach(function (pair) {
        var chip = Dom.el(doc, 'span', 'chip');
        chip.appendChild(Dom.el(doc, 'span', '', pair[1]));
        var remove = Dom.el(doc, 'button', '', '×');
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Remover filtro ' + pair[1]);
        remove.addEventListener('click', function () {
          var next = Object.assign({}, filters);
          next[pair[0]] = '';
          apply(next, 0, sort);
        });
        chip.appendChild(remove);
        chips.appendChild(chip);
      });
      if (active.length) {
        var clearAll = Dom.el(doc, 'button', 'chip', 'Limpar');
        clearAll.type = 'button';
        clearAll.addEventListener('click', function () { apply({}, 0, 'prioridade'); });
        chips.appendChild(clearAll);
      }
    }

    function badgeFor(item) {
      var wrap = Dom.el(doc, 'div', 'row-badges');
      wrap.appendChild(UI.badge(doc, item.prontidao.estado_label, TONE[item.prontidao.estado] || 'unknown'));
      if (item.si && item.si.estado) {
        wrap.appendChild(UI.badge(doc, humanize(SI, item.si.estado),
          item.si.estado === 'explicito' ? 'success' : 'neutral'));
      }
      if (item.indigenas && item.indigenas.estado) {
        wrap.appendChild(UI.badge(doc, humanize(INDIGENA, item.indigenas.estado),
          item.indigenas.estado === 'explicito_imediato' ? 'accent' : 'neutral'));
      }
      return wrap;
    }

    function locationText(item) {
      var prova = (item.localizacao || {}).prova || {};
      if (prova.text) return prova.text;
      if (prova.uf) return prova.uf;
      if (prova.state === 'a_divulgar') return 'A divulgar';
      return 'Não informado';
    }

    function renderRows(items) {
      Dom.clear(results);
      if (!items.length) {
        results.appendChild(UI.state(doc, {
          tone: 'empty', icon: 'search', title: 'Nenhuma oportunidade com esses filtros',
          text: 'Ajuste a busca ou remova filtros. A ausência de resultado não significa ausência de concursos.',
          actions: [{label: 'Limpar filtros', onClick: function () { apply({}, 0, 'prioridade'); }}]
        }));
        return;
      }
      var wrap = Dom.el(doc, 'div', 'table-wrap');
      var table = Dom.el(doc, 'table', 'data-table-main');
      var caption = Dom.el(doc, 'caption', 'visually-hidden', 'Lista de oportunidades');
      table.appendChild(caption);
      var thead = Dom.el(doc, 'thead');
      var headRow = Dom.el(doc, 'tr');
      ['Oportunidade', 'Local', 'Prazo', 'Formação', 'Reserva', 'Situação', ''].forEach(function (label) {
        headRow.appendChild(Dom.el(doc, 'th', '', label));
      });
      thead.appendChild(headRow);
      table.appendChild(thead);
      var tbody = Dom.el(doc, 'tbody');
      items.forEach(function (item) {
        var tr = Dom.el(doc, 'tr');
        var cell = Dom.el(doc, 'td');
        cell.setAttribute('data-label', 'Oportunidade');
        var link = Dom.el(doc, 'a', 'cell-strong', item.contest_label || item.competition_id || 'Concurso');
        link.href = dossierHref(item);
        cell.appendChild(link);
        cell.appendChild(Dom.el(doc, 'span', 'cell-sub',
          item.role_name || 'Cargo não reconciliado'));
        tr.appendChild(cell);
        var local = Dom.el(doc, 'td', 'cell-sub', locationText(item));
        local.setAttribute('data-label', 'Local');
        tr.appendChild(local);
        var deadlineCell = Dom.el(doc, 'td');
        deadlineCell.setAttribute('data-label', 'Prazo');
        var next = nextDeadline(item);
        if (next) {
          deadlineCell.appendChild(Dom.el(doc, 'span', 'cell-strong', next.grupo_label));
          deadlineCell.appendChild(Dom.el(doc, 'span', 'cell-sub',
            Fmt.shortDate(next.valor) + ' · ' + Fmt.relativeDays(next.dias_restantes)));
        } else {
          deadlineCell.appendChild(Dom.el(doc, 'span', 'cell-sub', 'Sem prazo futuro'));
        }
        tr.appendChild(deadlineCell);
        var siCell = Dom.el(doc, 'td');
        siCell.setAttribute('data-label', 'Formação');
        siCell.appendChild(UI.badge(doc, humanize(SI, (item.si || {}).estado),
          (item.si || {}).estado === 'explicito' ? 'success' : 'neutral'));
        tr.appendChild(siCell);
        var indCell = Dom.el(doc, 'td');
        indCell.setAttribute('data-label', 'Reserva');
        indCell.appendChild(UI.badge(doc, humanize(INDIGENA, (item.indigenas || {}).estado),
          (item.indigenas || {}).estado === 'explicito_imediato' ? 'accent' : 'neutral'));
        tr.appendChild(indCell);
        var stateCell = Dom.el(doc, 'td');
        stateCell.setAttribute('data-label', 'Situação');
        stateCell.appendChild(UI.badge(doc, item.prontidao.estado_label,
          TONE[item.prontidao.estado] || 'unknown'));
        tr.appendChild(stateCell);
        var actionCell = Dom.el(doc, 'td', 'row-action');
        actionCell.setAttribute('data-label', '');
        var action = Dom.el(doc, 'a', 'btn btn--ghost btn--sm', 'Abrir');
        action.href = dossierHref(item);
        actionCell.appendChild(action);
        tr.appendChild(actionCell);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      wrap.appendChild(table);
      results.appendChild(wrap);
    }

    function renderPager(total, items) {
      Dom.clear(pager);
      var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      var page = Math.floor(offset / PAGE_SIZE) + 1;
      var status = Dom.el(doc, 'span', 'pagination__status',
        'Página ' + page + ' de ' + totalPages + ' · ' + Fmt.integer(total) + ' resultado(s)');
      pager.appendChild(status);
      var pages = Dom.el(doc, 'div', 'pagination__pages');
      var prev = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Anterior');
      prev.type = 'button';
      prev.disabled = offset === 0;
      prev.addEventListener('click', function () {
        apply(currentFilters(), Math.max(0, offset - PAGE_SIZE), sort);
      });
      pages.appendChild(prev);
      var next = Dom.el(doc, 'button', 'btn btn--ghost btn--sm', 'Próxima');
      next.type = 'button';
      next.disabled = offset + PAGE_SIZE >= total;
      next.addEventListener('click', function () {
        apply(currentFilters(), offset + PAGE_SIZE, sort);
      });
      pages.appendChild(next);
      pager.appendChild(pages);
    }

    function load() {
      var token = seq.next();
      Dom.clear(results);
      results.appendChild(UI.loadingRows(doc, 5));
      count.textContent = 'Carregando oportunidades…';
      renderChips();
      ctx.api.get('/api/carteira?' + apiQuery(filters, offset))
        .then(function (payload) {
          if (!seq.isCurrent(token)) return;
          lastResult = payload;
          var items = sortItems(payload.itens || [], sort);
          count.textContent = Fmt.integer(payload.total) + ' oportunidade(s) encontrada(s)';
          renderRows(items);
          renderPager(payload.total, items);
        })
        .catch(function (error) {
          if (!seq.isCurrent(token)) return;
          count.textContent = 'Falha ao carregar oportunidades';
          Dom.clear(results);
          results.appendChild(UI.state(doc, {
            tone: 'error', icon: 'alert', title: 'Não foi possível carregar a carteira',
            text: error.message,
            hint: 'Verifique o servidor local e tente novamente.',
            actions: [{label: 'Tentar novamente', onClick: load}]
          }));
          Dom.clear(pager);
        });
    }

    load();
  }

  global.RadarOpportunities = {render: render};
})(typeof window !== 'undefined' ? window : globalThis);
