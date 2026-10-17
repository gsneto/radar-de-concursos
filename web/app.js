/* Radar de Concursos — central de inteligência documental (sem dependências).
 * Consome apenas as rotas GET locais (/api/concursos, /api/concursos/identidades
 * e /api/concursos/{uuid}/detalhes) e renderiza com APIs textuais seguras
 * (textContent / createElement), sem injetar HTML a partir de dados da API.
 */
(function (global) {
  'use strict';

  var UNKNOWN = 'Desconhecido';

  // Rótulos de estado de campo sustentados pelos dados reais do backend.
  var FIELD_STATE = {
    extraido: {label: 'Extraído', variant: 'extracted'},
    ambiguo: {label: 'Ambíguo', variant: 'ambiguous'},
    pendente_revisao: {label: 'Pendente de revisão', variant: 'ambiguous'},
    validado: {label: 'Validado', variant: 'validated'},
    rejeitado: {label: 'Rejeitado', variant: 'conflict'},
    desconhecido: {label: 'Desconhecido', variant: 'unknown'}
  };

  var COVERAGE_LABEL = {
    nao_auditada: 'Não auditada',
    parcial: 'Parcial',
    auditada_ate: 'Auditada até a data indicada'
  };

  var DOC_STATE_LABEL = {
    localizado: 'Localizado',
    baixado: 'Baixado',
    inacessivel: 'Inacessível',
    invalido: 'Inválido',
    substituido: 'Substituído'
  };

  var KIND_LABEL = {
    edital: 'Edital',
    retificacao: 'Retificação',
    outro: 'Documento'
  };

  // Classificação documental fina (tipo_documental); cai no KIND_LABEL se ausente.
  var DOCUMENT_TYPE_LABEL = {
    edital_abertura: 'Edital de abertura',
    edital_retificado: 'Edital retificado',
    retificacao: 'Retificação',
    anexo: 'Anexo',
    cronograma: 'Cronograma',
    comunicado: 'Comunicado',
    resultado: 'Resultado',
    convocacao: 'Convocação',
    homologacao: 'Homologação',
    gabarito: 'Gabarito',
    prova: 'Prova',
    pagina_concurso: 'Página do concurso',
    outro: 'Documento'
  };

  // Estado do ciclo e da fonte de monitoramento (rótulos sustentados pelo backend).
  var CYCLE_STATE = {
    em_andamento: {label: 'Em andamento', variant: 'unknown'},
    concluido: {label: 'Concluído', variant: 'validated'},
    parcial: {label: 'Parcial', variant: 'ambiguous'},
    falhou: {label: 'Falhou', variant: 'conflict'},
    interrompido: {label: 'Interrompido', variant: 'conflict'}
  };

  var SOURCE_STATE = {
    concluido: {label: 'Concluído', variant: 'validated'},
    parcial: {label: 'Parcial', variant: 'ambiguous'},
    falhou: {label: 'Falhou', variant: 'conflict'},
    nao_verificada: {label: 'Não verificada', variant: 'unknown'}
  };

  // Estado de extração de uma versão (enum do backend → rótulo humano).
  var EXTRACTION_LABEL = {
    nao_iniciada: 'Não iniciada',
    em_andamento: 'Em andamento',
    parcial: 'Parcial',
    concluida: 'Concluída',
    falhou: 'Falhou'
  };

  // Nome legível dos campos do contrato, mantendo a chave técnica ao lado para
  // rastreabilidade. Campos desconhecidos caem no próprio nome original.
  var FIELD_LABEL = {
    immediate_vacancies: 'Vagas imediatas',
    reserve_vacancies: 'Cadastro de reserva',
    indigenous_vacancies: 'Vagas indígenas (imediatas)',
    indigenous_reserve_vacancies: 'Vagas indígenas (cadastro de reserva)',
    registration_start: 'Início das inscrições',
    registration_end: 'Fim das inscrições',
    registration_status: 'Situação das inscrições',
    exam_date: 'Data da prova',
    exam_location: 'Local de prova',
    work_location: 'Local de exercício',
    education: 'Requisitos de formação',
    accepted_courses: 'Cursos aceitos',
    si_compatibility: 'Compatibilidade com Sistemas de Informação',
    exemption_start: 'Início da isenção da taxa',
    exemption_end: 'Fim da isenção da taxa',
    exemption_result_preliminary: 'Resultado preliminar da isenção',
    exemption_appeal: 'Recurso da isenção',
    exemption_result_final: 'Resultado definitivo da isenção'
  };

  function isMissing(value) {
    return value === null || value === undefined || value === '';
  }

  // null/ausente = desconhecido; zero é preservado como "0".
  function formatCount(value) {
    if (isMissing(value)) return UNKNOWN;
    return String(value);
  }

  function formatText(value) {
    if (isMissing(value)) return UNKNOWN;
    return String(value);
  }

  // Datas conhecidas vêm em ISO YYYY-MM-DD; exibimos DD/MM/YYYY. Demais formatos
  // (ou inesperados) são exibidos sem transformação, sem ganhar/perder informação.
  function formatDate(value) {
    if (isMissing(value)) return UNKNOWN;
    var s = String(value);
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (m) return m[3] + '/' + m[2] + '/' + m[1];
    return s;
  }

  // verified_at em ISO UTC com offset é exibido integralmente, preservando o offset.
  function formatVerifiedAt(value) {
    if (isMissing(value)) return UNKNOWN;
    return String(value);
  }

  // Link só é clicável quando houver URL HTTPS válida.
  function isHttpsUrl(value) {
    return typeof value === 'string' && /^https:\/\//i.test(value.trim());
  }

  // Identificadores técnicos são reduzidos a um prefixo legível; o valor completo
  // permanece disponível em detalhes secundários para rastreabilidade.
  function shortId(value) {
    if (isMissing(value)) return UNKNOWN;
    var s = String(value);
    return s.length > 12 ? s.slice(0, 8) : s;
  }

  function stateInfo(state) {
    return FIELD_STATE[state] || {label: formatText(state), variant: 'unknown'};
  }

  function fieldLabel(name) {
    return FIELD_LABEL[name] || formatText(name);
  }

  function extractionLabel(state) {
    return EXTRACTION_LABEL[state] || formatText(state);
  }

  function el(document, tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function badge(document, text, variant) {
    return el(document, 'span', 'badge badge--' + variant, text);
  }

  // Rótulo legível do campo + chave técnica discreta (rastreabilidade).
  function fieldCell(document, className, name) {
    var cell = el(document, 'span', className);
    cell.appendChild(el(document, 'span', 'field-label', fieldLabel(name)));
    cell.appendChild(el(document, 'span', 'field-key', ' ' + String(name)));
    return cell;
  }

  function stateBadge(document, state) {
    var info = stateInfo(state);
    return badge(document, info.label, info.variant);
  }

  function makeLink(document, url, text) {
    var a = el(document, 'a', 'link', text);
    a.setAttribute('href', url);
    a.setAttribute('target', '_blank');
    a.setAttribute('rel', 'noopener noreferrer');
    return a;
  }

  // value pode ser string (definida como textContent) ou elemento (ex.: link).
  function addPair(document, dl, label, value) {
    var dt = el(document, 'dt', 'kv__k', label);
    var dd = el(document, 'dd', 'kv__v');
    if (typeof value === 'string') {
      dd.textContent = value;
    } else {
      dd.appendChild(value);
    }
    dl.appendChild(dt);
    dl.appendChild(dd);
  }

  function sourceValue(document, record) {
    var name = formatText(record.source_name);
    if (isHttpsUrl(record.source_url)) {
      return makeLink(document, record.source_url, name);
    }
    return name;
  }

  function evidenceValue(document, record) {
    if (isHttpsUrl(record.evidence_url)) {
      return makeLink(document, record.evidence_url, 'Abrir evidência');
    }
    return UNKNOWN;
  }

  function group(document, title, pairs) {
    var section = el(document, 'section', 'group');
    section.appendChild(el(document, 'h4', 'group__title', title));
    var dl = el(document, 'dl', 'kv');
    pairs.forEach(function (pair) { addPair(document, dl, pair[0], pair[1]); });
    section.appendChild(dl);
    return section;
  }

  function renderRecordCard(document, record) {
    var article = el(document, 'article', 'card');

    var header = el(document, 'div', 'card__header');
    var idrow = el(document, 'div', 'card__idrow');
    if (!isMissing(record.competition_id)) {
      idrow.appendChild(el(document, 'span', 'chip chip--id', String(record.competition_id)));
    }
    idrow.appendChild(el(document, 'span', 'card__agency', formatText(record.agency)));
    header.appendChild(idrow);
    header.appendChild(el(document, 'h3', 'card__title', formatText(record.competition)));
    article.appendChild(header);

    var groups = el(document, 'div', 'card__groups');
    groups.appendChild(group(document, 'Identificação', [
      ['Cargo', formatText(record.role)],
      ['Escolaridade', formatText(record.education)]
    ]));
    groups.appendChild(group(document, 'Vagas', [
      ['Vagas imediatas', formatCount(record.immediate_vacancies)],
      ['Cadastro de reserva', formatCount(record.reserve_vacancies)],
      ['Vagas indígenas', formatCount(record.indigenous_vacancies)]
    ]));
    groups.appendChild(group(document, 'Datas', [
      ['Início das inscrições', formatDate(record.registration_start)],
      ['Fim das inscrições', formatDate(record.registration_end)],
      ['Inscrições segundo o período do artigo', formatText(record.registration_status)],
      ['Data da prova', formatDate(record.exam_date)]
    ]));
    groups.appendChild(group(document, 'Locais', [
      ['Local de prova', formatText(record.exam_location)],
      ['Local de exercício', formatText(record.work_location)]
    ]));
    groups.appendChild(group(document, 'Proveniência', [
      ['Fonte', sourceValue(document, record)],
      ['Evidência', evidenceValue(document, record)],
      ['Artigo consultado em', formatVerifiedAt(record.verified_at)]
    ]));
    article.appendChild(groups);
    return article;
  }

  function evidenceBlock(document, evidence) {
    var wrap = el(document, 'div', 'evidence');
    if (!evidence || isMissing(evidence.quote)) {
      wrap.appendChild(el(document, 'p', 'muted', 'Sem trecho de evidência.'));
      return wrap;
    }
    wrap.appendChild(el(document, 'blockquote', 'evidence__quote', '“' + evidence.quote + '”'));
    var meta = [];
    if (!isMissing(evidence.document_id)) meta.push('Documento ' + shortId(evidence.document_id));
    if (!isMissing(evidence.version_id)) meta.push('Versão ' + shortId(evidence.version_id));
    if (!isMissing(evidence.page_number)) meta.push('Página ' + evidence.page_number);
    if (!isMissing(evidence.locator)) meta.push(String(evidence.locator));
    if (meta.length) wrap.appendChild(el(document, 'p', 'evidence__meta', meta.join(' · ')));
    return wrap;
  }

  function docTitleMap(documents) {
    var map = {};
    (documents || []).forEach(function (doc) { map[doc.id] = doc; });
    return map;
  }

  function documentOrigin(document, byId, documentId) {
    if (isMissing(documentId)) return UNKNOWN;
    var doc = byId[documentId];
    return doc && !isMissing(doc.title) ? doc.title : ('Documento ' + shortId(documentId));
  }

  function renderDocumentsColumn(document, documents) {
    var column = el(document, 'div', 'panel__col');
    column.appendChild(el(document, 'h5', 'panel__subtitle', 'Documentos e versões'));
    if (!documents || documents.length === 0) {
      column.appendChild(el(document, 'p', 'muted', 'Nenhum documento cadastrado.'));
      return column;
    }
    var byId = docTitleMap(documents);
    documents.forEach(function (item) {
      var row = el(document, 'article', 'doc');
      var head = el(document, 'div', 'doc__head');
      head.appendChild(el(document, 'strong', 'doc__title', formatText(item.title)));
      var typeLabel = DOCUMENT_TYPE_LABEL[item.document_type] || KIND_LABEL[item.kind] || formatText(item.kind);
      head.appendChild(badge(document, typeLabel, 'kind'));
      head.appendChild(badge(document, DOC_STATE_LABEL[item.state] || formatText(item.state), 'neutral'));
      row.appendChild(head);

      if (isHttpsUrl(item.official_url)) {
        row.appendChild(makeLink(document, item.official_url, 'Abrir documento oficial'));
      }
      (item.related_document_ids || []).forEach(function (related) {
        row.appendChild(el(document, 'p', 'doc__related',
          'Vinculado a: ' + documentOrigin(document, byId, related)));
      });
      (item.versions || []).forEach(function (version) {
        var line = el(document, 'div', 'version');
        line.appendChild(el(document, 'span', 'version__id', 'Versão ' + shortId(version.id)));
        line.appendChild(badge(document, 'Extração: ' + extractionLabel(version.extraction_state), 'neutral'));
        if (!isMissing(version.error_code)) {
          line.appendChild(badge(document, formatText(version.error_code), 'conflict'));
        }
        row.appendChild(line);
      });
      (item.download_attempts || []).forEach(function (attempt) {
        if (attempt.state === 'falhou') {
          row.appendChild(el(document, 'p', 'error-text',
            'Falha em tentativa de download' + (attempt.error_code ? ': ' + attempt.error_code : '')));
        }
      });
      column.appendChild(row);
    });
    return column;
  }

  function renderConflicts(document, conflicts, byId, roles) {
    if (!conflicts || conflicts.length === 0) return null;
    var roleNames = {};
    (roles || []).forEach(function (role) { roleNames[role.id] = role.name; });
    var wrap = el(document, 'div', 'conflicts');
    wrap.appendChild(el(document, 'h5', 'panel__subtitle', 'Conflitos entre documentos'));
    conflicts.forEach(function (conflict) {
      var item = el(document, 'div', 'conflict');
      var head = el(document, 'div', 'conflict__head');
      head.appendChild(fieldCell(document, 'conflict__field', conflict.field_name));
      head.appendChild(badge(document, 'Conflito', 'conflict'));
      var scope;
      if (conflict.scope_label) {
        scope = conflict.scope_label;
      } else if (conflict.scope_type === 'role') {
        scope = roleNames[conflict.role_id] || ('Cargo ' + shortId(conflict.role_id));
      } else if (conflict.scope_type === 'contest') {
        scope = 'Escopo do concurso';
      } else {
        scope = 'Escopo não identificado';
      }
      head.appendChild(el(document, 'span', 'conflict__scope', scope));
      item.appendChild(head);
      (conflict.values || []).forEach(function (value) {
        var row = el(document, 'div', 'conflict__value');
        row.appendChild(el(document, 'span', 'conflict__val', String(value.value)));
        row.appendChild(el(document, 'span', 'conflict__origin',
          documentOrigin(document, byId, value.document_id)));
        item.appendChild(row);
      });
      wrap.appendChild(item);
    });
    return wrap;
  }

  function renderFacts(document, details, byId) {
    var column = el(document, 'div', 'panel__col');
    column.appendChild(el(document, 'h5', 'panel__subtitle', 'Fatos e evidências'));

    var conflicts = renderConflicts(document, details.conflicts, byId, details.roles);
    if (conflicts) column.appendChild(conflicts);

    var proposals = details.proposals || [];
    if (proposals.length === 0) {
      column.appendChild(el(document, 'p', 'muted', 'Nenhuma proposta extraída.'));
    }
    proposals.forEach(function (proposal) {
      var row = el(document, 'div', 'fact');
      var head = el(document, 'div', 'fact__head');
      head.appendChild(fieldCell(document, 'fact__field', proposal.field_name));
      head.appendChild(el(document, 'span', 'fact__value', String(proposal.value)));
      head.appendChild(stateBadge(document, proposal.state));
      row.appendChild(head);
      if (proposal.reconciled_role_id) {
        row.appendChild(el(document, 'p', 'fact__note',
          'Cargo reconciliado: ' + shortId(proposal.reconciled_role_id)));
      }
      if (!isMissing(proposal.ambiguity_reason)) {
        row.appendChild(el(document, 'p', 'fact__note', 'Motivo: ' + proposal.ambiguity_reason));
      }
      row.appendChild(evidenceBlock(document, proposal.evidence));
      column.appendChild(row);
    });

    (details.current_values || []).forEach(function (selection) {
      var row = el(document, 'div', selection.active ? 'fact fact--current' : 'fact');
      var head = el(document, 'div', 'fact__head');
      head.appendChild(el(document, 'span', 'fact__field', formatText(selection.field_name)));
      head.appendChild(badge(document, selection.active ? 'Valor vigente' : 'Seleção histórica',
        selection.active ? 'validated' : 'unknown'));
      row.appendChild(head);
      if (!isMissing(selection.selected_by)) {
        row.appendChild(el(document, 'p', 'fact__note', 'Selecionado por ' + selection.selected_by));
      }
      row.appendChild(evidenceBlock(document, selection.evidence));
      column.appendChild(row);
    });
    return column;
  }

  function renderReconciliations(document, reconciliations, roles) {
    if (!reconciliations || reconciliations.length === 0) return null;
    var names = {};
    (roles || []).forEach(function (role) { names[role.id] = role.name; });
    var wrap = el(document, 'div', 'recons');
    wrap.appendChild(el(document, 'h5', 'panel__subtitle', 'Reconciliação de cargos'));
    reconciliations.forEach(function (recon) {
      var row = el(document, 'div', 'recon');
      row.appendChild(el(document, 'span', 'recon__label', formatText(recon.label)));
      row.appendChild(el(document, 'span', 'recon__arrow', '→'));
      row.appendChild(el(document, 'span', 'recon__role',
        names[recon.role_id] || ('Cargo ' + shortId(recon.role_id))));
      wrap.appendChild(row);
    });
    return wrap;
  }

  function renderDocumentDetails(document, details) {
    var section = el(document, 'section', 'documents');
    var coverage = details.coverage || {};
    var heading = el(document, 'div', 'documents__header');
    heading.appendChild(el(document, 'h4', 'documents__heading', 'Histórico documental'));
    heading.appendChild(badge(document, 'Cobertura: ' + (COVERAGE_LABEL[coverage.state] || 'Desconhecida'),
      coverage.state === 'auditada_ate' ? 'validated' : (coverage.state === 'parcial' ? 'ambiguous' : 'unknown')));
    section.appendChild(heading);
    if (coverage.checked_at) {
      section.appendChild(el(document, 'p', 'documents__status', 'Conferido em ' + coverage.checked_at));
    }

    var recons = renderReconciliations(document, details.role_reconciliations, details.roles);
    if (recons) section.appendChild(recons);

    var byId = docTitleMap(details.documents);
    var grid = el(document, 'div', 'panel');
    grid.appendChild(renderDocumentsColumn(document, details.documents));
    grid.appendChild(renderFacts(document, details, byId));
    section.appendChild(grid);
    return section;
  }

  function cycleStateBadge(document, state) {
    var info = CYCLE_STATE[state] || {label: formatText(state), variant: 'unknown'};
    return badge(document, info.label, info.variant);
  }

  function sourceStateBadge(document, state) {
    var info = SOURCE_STATE[state] || {label: formatText(state), variant: 'unknown'};
    return badge(document, info.label, info.variant);
  }

  function renderMonitoring(document, status) {
    var section = el(document, 'div', 'monitoring__inner');
    status = status || {};
    var last = status.last_cycle;
    if (!last) {
      section.appendChild(el(document, 'p', 'muted', 'Monitoramento ainda não executado.'));
      section.appendChild(el(document, 'p', 'monitoring__hint',
        'Execute "python -m radar monitor" para iniciar o acompanhamento das fontes.'));
      return section;
    }

    var head = el(document, 'div', 'monitoring__head');
    head.appendChild(el(document, 'span', 'monitoring__last',
      'Última verificação: ' + formatVerifiedAt(last.finished_at || last.started_at)));
    head.appendChild(cycleStateBadge(document, last.state));
    section.appendChild(head);

    // Alertas: distinguir nova publicação de alteração em documento conhecido e
    // nunca sugerir sucesso quando alguma fonte não foi consultada com êxito.
    var alerts = el(document, 'ul', 'monitoring__alerts');
    var sources = status.sources || [];
    var newDocs = last.documents_new || 0;
    // "changes" (por fonte) conta apenas alterações em documentos já conhecidos;
    // "versions_new" inclui a primeira versão de documentos novos e não deve
    // ser apresentado como alteração.
    var changedDocs = sources.reduce(function (sum, source) {
      var summary = source.summary || {};
      return sum + (typeof summary.changes === 'number' ? summary.changes : 0);
    }, 0);
    var failedSources = sources.filter(function (source) {
      return source.state === 'falhou' || source.state === 'nao_verificada';
    });
    // Só um ciclo "concluido" permite a mensagem tranquilizadora. Qualquer outro
    // estado (falhou, parcial, interrompido, em andamento) é verificação incompleta.
    var okCycle = last.state === 'concluido';

    if (newDocs > 0) {
      alerts.appendChild(el(document, 'li', 'alert alert--new',
        'Nova publicação: ' + newDocs + ' documento(s) novo(s) encontrado(s).'));
    }
    if (changedDocs > 0) {
      alerts.appendChild(el(document, 'li', 'alert alert--change',
        'Alteração em documento conhecido: ' + changedDocs + ' documento(s) com nova versão aguardando análise.'));
    }
    if (failedSources.length > 0) {
      alerts.appendChild(el(document, 'li', 'alert alert--failed',
        'Verificação incompleta: ' + failedSources.length +
        ' fonte(s) não foram consultadas com sucesso. O resultado acima pode estar desatualizado.'));
    } else if (!okCycle) {
      var cycleLabel = CYCLE_STATE[last.state] ? CYCLE_STATE[last.state].label : formatText(last.state);
      var incomplete = last.state === 'em_andamento'
        ? 'Verificação incompleta: o último ciclo ainda está em andamento.'
        : 'Verificação incompleta: o último ciclo terminou como "' + cycleLabel + '".';
      alerts.appendChild(el(document, 'li', 'alert alert--failed',
        incomplete + ' O resultado acima pode estar desatualizado.'));
    }
    if (newDocs === 0 && changedDocs === 0 && failedSources.length === 0 && okCycle) {
      alerts.appendChild(el(document, 'li', 'alert alert--quiet',
        'Nenhuma publicação nova ou alteração desde a última verificação.'));
    }
    section.appendChild(alerts);

    var dl = el(document, 'dl', 'kv');
    addPair(document, dl, 'Documentos encontrados', formatCount(last.documents_found));
    addPair(document, dl, 'Alterações pendentes de análise', formatCount(status.pending_analysis));
    addPair(document, dl, 'Cobertura', COVERAGE_LABEL[status.coverage_state] || 'Desconhecida');
    section.appendChild(dl);

    if (status.coverage_state !== 'auditada_ate') {
      section.appendChild(el(document, 'p', 'monitoring__hint',
        'Cobertura ainda não verificada: a ausência de novos links não prova que não existam retificações.'));
    }

    var list = el(document, 'div', 'monitoring__sources');
    list.appendChild(el(document, 'h5', 'panel__subtitle', 'Fontes'));
    if (sources.length === 0) {
      list.appendChild(el(document, 'p', 'muted', 'Nenhuma fonte consultada.'));
    }
    sources.forEach(function (source) {
      var row = el(document, 'div', 'source');
      var top = el(document, 'div', 'source__head');
      if (isHttpsUrl(source.source_url)) {
        top.appendChild(makeLink(document, source.source_url, formatText(source.source_url)));
      } else {
        top.appendChild(el(document, 'span', 'source__url', formatText(source.source_url)));
      }
      top.appendChild(sourceStateBadge(document, source.state));
      row.appendChild(top);
      var meta = [];
      if (!isMissing(source.checked_at)) meta.push('Consultada em ' + source.checked_at);
      if (!isMissing(source.last_success_at)) meta.push('Último sucesso ' + source.last_success_at);
      if (!isMissing(source.error_code)) meta.push('Erro: ' + source.error_code);
      var sourceErrors = (source.summary && source.summary.errors) || [];
      if (sourceErrors.length) {
        var codes = sourceErrors.map(function (e) { return e.error_code; }).join(', ');
        meta.push('Falhas parciais: ' + codes);
      }
      if (meta.length) row.appendChild(el(document, 'p', 'source__meta', meta.join(' · ')));
      row.appendChild(el(document, 'p', 'source__counts',
        'Novos: ' + formatCount(source.documents_new) +
        ' · Versões novas: ' + formatCount(source.versions_new) +
        ' · Pendentes: ' + formatCount(source.changes_pending)));
      list.appendChild(row);
    });
    section.appendChild(list);
    return section;
  }

  // Alertas persistentes da operação autônoma (rótulos sustentados pelo backend).
  var ALERT_KIND_LABEL = {
    novo_candidato: 'Novo candidato',
    documento_recuperado: 'Documento recuperado',
    retificacao: 'Retificação',
    falha_fonte: 'Fonte indisponível',
    prazo_isencao: 'Prazo de isenção',
    lote_confirmacao: 'Lote de confirmação'
  };
  var ALERT_SEVERITY = {
    info: {label: 'Info', variant: 'neutral'},
    atencao: {label: 'Atenção', variant: 'ambiguous'},
    critico: {label: 'Crítico', variant: 'conflict'}
  };

  function renderAlerts(document, payload) {
    var section = el(document, 'div', 'alerts__inner');
    payload = payload || {};
    var alerts = payload.alerts || [];
    var counts = payload.counts || {};
    if (alerts.length === 0) {
      section.appendChild(el(document, 'p', 'muted', 'Nenhum alerta registrado.'));
      return section;
    }
    var head = el(document, 'p', 'alerts__count',
      (counts.unseen || 0) + ' não visto(s) de ' + (counts.total || alerts.length) + ' alerta(s).');
    section.appendChild(head);
    var list = el(document, 'ul', 'alerts__list');
    alerts.forEach(function (item) {
      var row = el(document, 'li', 'alert-row alert-row--' + (item.severity || 'info'));
      var headRow = el(document, 'div', 'alert-row__head');
      headRow.appendChild(badge(document, ALERT_KIND_LABEL[item.kind] || formatText(item.kind), 'kind'));
      var sev = ALERT_SEVERITY[item.severity] || ALERT_SEVERITY.info;
      headRow.appendChild(badge(document, sev.label, sev.variant));
      headRow.appendChild(el(document, 'span', 'alert-row__when', formatVerifiedAt(item.created_at)));
      row.appendChild(headRow);
      row.appendChild(el(document, 'p', 'alert-row__title', formatText(item.title)));
      if (item.detail) {
        row.appendChild(el(document, 'p', 'alert-row__detail', formatText(item.detail)));
      }
      list.appendChild(row);
    });
    section.appendChild(list);
    return section;
  }

  function fetchAlerts() {
    var doc = global.document;
    var container = doc && doc.getElementById('alerts-panel');
    if (!container) return Promise.resolve();
    return global.fetch('/api/alertas?limit=20', {headers: {Accept: 'application/json'}})
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (payload) {
        container.textContent = '';
        container.appendChild(renderAlerts(doc, payload));
      })
      .catch(function (err) {
        showError(err);
        container.textContent = '';
        container.appendChild(el(doc, 'p', 'muted',
          'Alertas indisponíveis. O histórico documental continua acessível.'));
      });
  }

  // --- Central de triagem (Fase 19) ------------------------------------------

  var TRIAGE_BUCKET = {
    hoje: {label: 'Ação necessária hoje', variant: 'conflict'},
    proximos: {label: 'Prazos próximos', variant: 'ambiguous'},
    retificacoes: {label: 'Retificações e alterações', variant: 'ambiguous'},
    novos: {label: 'Novos editais para avaliar', variant: 'extracted'},
    falhas: {label: 'Falhas de coleta', variant: 'conflict'},
    outros: {label: 'Outros', variant: 'neutral'}
  };

  function triageFilter() {
    var doc = global.document;
    var body = doc && doc.body;
    return body && body.getAttribute ? body.getAttribute('data-triage-filter') : '';
  }

  function contestHashId() {
    var hash = (global.location && global.location.hash) ? global.location.hash : '';
    var match = /#concurso=([^&]+)/.exec(hash);
    return match ? decodeURIComponent(match[1]) : null;
  }

  function focusContestFromHash() {
    var doc = global.document;
    var contestId = contestHashId();
    if (!doc || !contestId) return;
    var node = doc.querySelector ? doc.querySelector('[data-contest-id="' + contestId + '"]') : null;
    if (!node) return;
    if (typeof node.scrollIntoView === 'function') node.scrollIntoView({block: 'start'});
    if (node.classList && node.classList.add) {
      node.classList.add('card--focused');
      if (typeof global.setTimeout === 'function') {
        global.setTimeout(function () { node.classList.remove('card--focused'); }, 2500);
      }
    }
  }

  function setTriageFilter(value) {
    var doc = global.document;
    if (doc && doc.body && doc.body.setAttribute) {
      doc.body.setAttribute('data-triage-filter', value || '');
    }
  }

  function alertAction(id, action, until) {
    var payload = {action: action};
    if (until) payload.until = until;
    return global.fetch('/api/alertas/' + encodeURIComponent(id), {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify(payload)
    }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return fetchTriage();
    }).catch(function (err) { showError(err); });
  }

  function snoozeOneDay(id) {
    var until = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
    return alertAction(id, 'snooze', until);
  }

  function renderTriage(document, payload) {
    var section = el(document, 'div', 'triage__inner');
    payload = payload || {};
    var groups = payload.groups || [];
    var counts = payload.counts || {};
    var filter = triageFilter();

    var head = el(document, 'p', 'triage__summary',
      (counts.unseen || 0) + ' alerta(s) não visto(s) de ' + (counts.total || 0) + '.');
    section.appendChild(head);

    // Filtros por categoria (ação real: restringe os grupos exibidos).
    var filters = el(document, 'div', 'triage__filters');
    var options = [['', 'Todos']].concat(Object.keys(TRIAGE_BUCKET).map(function (k) {
      return [k, TRIAGE_BUCKET[k].label];
    }));
    options.forEach(function (pair) {
      var active = (filter || '') === pair[0];
      var btn = el(document, 'button', 'triage__filter' + (active ? ' is-active' : ''), pair[1]);
      btn.type = 'button';
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      btn.addEventListener('click', function () {
        setTriageFilter(pair[0]);
        fetchTriage();
      });
      filters.appendChild(btn);
    });
    section.appendChild(filters);

    var shown = groups.filter(function (g) { return !filter || g.urgency === filter; });
    if (shown.length === 0) {
      section.appendChild(el(document, 'p', 'muted', 'Nenhum alerta nesta categoria.'));
      return section;
    }
    shown.forEach(function (group) {
      section.appendChild(renderTriageGroup(document, group));
    });
    return section;
  }

  function renderTriageGroup(document, group) {
    var card = el(document, 'article', 'triage-group triage-group--' + (group.urgency || 'outros'));
    var head = el(document, 'div', 'triage-group__head');
    var bucket = TRIAGE_BUCKET[group.urgency] || TRIAGE_BUCKET.outros;
    head.appendChild(badge(document, bucket.label, bucket.variant));
    head.appendChild(el(document, 'span', 'triage-group__count', group.alert_count + ' evento(s)'));
    card.appendChild(head);

    var title = el(document, 'h3', 'triage-group__title',
      group.contest_id ? 'Concurso ' + shortId(group.contest_id) : 'Sem concurso identificado');
    card.appendChild(title);

    var meta = el(document, 'p', 'triage-group__meta');
    var parts = [];
    if (group.exemption_end) parts.push('Isenção até ' + formatDate(group.exemption_end));
    if (group.sources && group.sources.length) parts.push('Fonte: ' + group.sources.join(', '));
    meta.textContent = parts.length ? parts.join(' · ') : 'Sem prazo documentado para este grupo.';
    card.appendChild(meta);

    var list = el(document, 'ul', 'triage-group__alerts');
    (group.alerts || []).forEach(function (item) {
      list.appendChild(renderTriageAlert(document, item));
    });
    card.appendChild(list);

    if (group.contest_id) {
      var link = el(document, 'a', 'link', 'Abrir concurso');
      link.setAttribute('href', '#concurso=' + encodeURIComponent(group.contest_id));
      card.appendChild(link);
    }
    return card;
  }

  function renderTriageAlert(document, item) {
    var row = el(document, 'li', 'triage-alert triage-alert--' + (item.severity || 'info'));
    var line = el(document, 'div', 'triage-alert__line');
    line.appendChild(badge(document, ALERT_KIND_LABEL[item.kind] || formatText(item.kind), 'kind'));
    var sev = ALERT_SEVERITY[item.severity] || ALERT_SEVERITY.info;
    line.appendChild(badge(document, sev.label, sev.variant));
    line.appendChild(el(document, 'span', 'triage-alert__when', formatVerifiedAt(item.created_at)));
    row.appendChild(line);
    row.appendChild(el(document, 'p', 'triage-alert__title', formatText(item.title)));
    if (item.detail) row.appendChild(el(document, 'p', 'triage-alert__detail', formatText(item.detail)));

    var actions = el(document, 'div', 'triage-alert__actions');
    var seenBtn = el(document, 'button', 'triage-action', 'Marcar visto');
    seenBtn.type = 'button';
    seenBtn.addEventListener('click', function () { alertAction(item.id, 'seen'); });
    actions.appendChild(seenBtn);
    var snoozeBtn = el(document, 'button', 'triage-action', 'Adiar 1 dia');
    snoozeBtn.type = 'button';
    snoozeBtn.addEventListener('click', function () { snoozeOneDay(item.id); });
    actions.appendChild(snoozeBtn);
    var reopenBtn = el(document, 'button', 'triage-action', 'Reabrir');
    reopenBtn.type = 'button';
    reopenBtn.addEventListener('click', function () { alertAction(item.id, 'reopen'); });
    actions.appendChild(reopenBtn);
    var dismissBtn = el(document, 'button', 'triage-action triage-action--danger', 'Dispensar');
    dismissBtn.type = 'button';
    dismissBtn.addEventListener('click', function () { alertAction(item.id, 'dismiss'); });
    actions.appendChild(dismissBtn);
    if (isHttpsUrl(item.source_id)) {
      actions.appendChild(makeLink(document, item.source_id, 'Ver fonte'));
    }
    row.appendChild(actions);
    return row;
  }

  function fetchTriage() {
    var doc = global.document;
    var container = doc && doc.getElementById('triage-panel');
    if (!container) return Promise.resolve();
    return global.fetch('/api/triagem?limit=200', {headers: {Accept: 'application/json'}})
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (payload) {
        container.textContent = '';
        container.appendChild(renderTriage(doc, payload));
      })
      .catch(function (err) {
        showError(err);
        container.textContent = '';
        container.appendChild(el(doc, 'p', 'muted',
          'Triagem indisponível. Os alertas persistentes continuam acessíveis.'));
      });
  }

  // --- Priorização de oportunidades (Fase 20) --------------------------------

  var SI_LABEL = {
    aceito_expressamente: 'Aceita Sistemas de Informação (explícito)',
    abrangido_por_categoria: 'Abrangido por categoria de TI',
    ambiguo: 'Compatibilidade ambígua',
    incompativel_com_requisito_explicito: 'Incompatível (requisito explícito)',
    nao_extraido: 'Não extraído',
    nao_informado: 'Não informado'
  };
  var LOC_STATE_LABEL = {
    confirmado_documentalmente: 'confirmado',
    extraido_nao_revisado: 'extraído (não revisado)',
    ambiguo: 'ambíguo',
    em_conflito: 'em conflito',
    nao_informado: 'não informado no documento',
    nao_extraido: 'não extraído'
  };

  function prioFilter(name) {
    var doc = global.document;
    var body = doc && doc.body;
    return body && body.getAttribute ? (body.getAttribute('data-prio-' + name) || '') : '';
  }

  function setPrioFilter(name, value) {
    var doc = global.document;
    if (doc && doc.body && doc.body.setAttribute) {
      doc.body.setAttribute('data-prio-' + name, value || '');
    }
  }

  function formatDistance(distance) {
    if (!distance || !distance.known) {
      return 'Distância desconhecida' + (distance && distance.reason ? ' (' + distance.reason + ')' : '');
    }
    // Sempre identificada como geográfica em linha reta (nunca rodoviária).
    return distance.distance_km + ' km em linha reta (distância geográfica)';
  }

  function locationText(view) {
    if (!view) return 'Desconhecido';
    var state = LOC_STATE_LABEL[view.state] || view.state || 'desconhecido';
    if (view.municipios && view.municipios.length) {
      return view.municipios.join(', ') + (view.uf ? '/' + view.uf : '') + ' — ' + state;
    }
    if (view.uf) return view.uf + ' (estado) — ' + state;
    if (view.scope && view.scope !== 'desconhecida') return 'abrangência ' + view.scope + ' — ' + state;
    return 'Sem localização — ' + state;
  }

  function renderPriorities(document, payload) {
    var section = el(document, 'div', 'priorities__inner');
    payload = payload || {};
    var items = payload.items || [];

    section.appendChild(el(document, 'p', 'priorities__summary',
      items.length + ' oportunidade(s) avaliada(s). Ordenadas por prioridade explicável. '
      + 'Distâncias são geográficas (linha reta), não rodoviárias.'));

    var filters = el(document, 'div', 'priorities__filters');
    var ufFilter = prioFilter('uf');
    var siFilter = prioFilter('si');
    var unknownOnly = prioFilter('unknown') === '1';

    var ufSelect = el(document, 'select', 'priorities__select');
    ufSelect.appendChild(el(document, 'option', '', 'Todos os estados'));
    var ufs = {};
    items.forEach(function (i) { if (i.location && i.location.prova && i.location.prova.uf) ufs[i.location.prova.uf] = 1; });
    Object.keys(ufs).sort().forEach(function (uf) {
      var opt = el(document, 'option', '', uf);
      opt.setAttribute('value', uf);
      if (uf === ufFilter) opt.setAttribute('selected', 'selected');
      ufSelect.appendChild(opt);
    });
    ufSelect.addEventListener('change', function () {
      setPrioFilter('uf', ufSelect.value); fetchPriorities();
    });
    filters.appendChild(ufSelect);

    var siSelect = el(document, 'select', 'priorities__select');
    siSelect.appendChild(el(document, 'option', '', 'Toda compatibilidade'));
    ['aceito_expressamente', 'abrangido_por_categoria', 'ambiguo',
     'incompativel_com_requisito_explicito', 'nao_extraido', 'nao_informado'].forEach(function (state) {
      var opt = el(document, 'option', '', SI_LABEL[state]);
      opt.setAttribute('value', state);
      if (state === siFilter) opt.setAttribute('selected', 'selected');
      siSelect.appendChild(opt);
    });
    siSelect.addEventListener('change', function () {
      setPrioFilter('si', siSelect.value); fetchPriorities();
    });
    filters.appendChild(siSelect);

    var unknownBtn = el(document, 'button', 'triage__filter' + (unknownOnly ? ' is-active' : ''),
      'Só localização não confirmada');
    unknownBtn.type = 'button';
    unknownBtn.addEventListener('click', function () {
      setPrioFilter('unknown', unknownOnly ? '' : '1'); fetchPriorities();
    });
    filters.appendChild(unknownBtn);
    section.appendChild(filters);

    var shown = items.filter(function (i) {
      var prova = i.location && i.location.prova;
      if (ufFilter && (!prova || prova.uf !== ufFilter)) return false;
      if (siFilter && (!i.si_compatibility || i.si_compatibility.state !== siFilter)) return false;
      if (unknownOnly && prova && prova.state === 'confirmado_documentalmente') return false;
      return true;
    });
    if (shown.length === 0) {
      section.appendChild(el(document, 'p', 'muted', 'Nenhuma oportunidade nesta combinação de filtros.'));
      return section;
    }
    shown.forEach(function (item) { section.appendChild(renderPriorityItem(document, item)); });
    return section;
  }

  function renderPriorityItem(document, item) {
    var card = el(document, 'article', 'priority-item priority-item--' + (item.label || 'sem_dados_suficientes'));
    var head = el(document, 'div', 'priority-item__head');
    head.appendChild(badge(document, item.label_text || item.label, 'kind'));
    head.appendChild(el(document, 'span', 'priority-item__score',
      'prioridade ' + item.score + '/' + item.max_score + ' (' + Math.round((item.coverage || 0) * 100) + '% dos dados)'));
    if (item.exceptional) head.appendChild(badge(document, 'excepcional', 'validated'));
    card.appendChild(head);

    card.appendChild(el(document, 'h3', 'priority-item__title', 'Concurso ' + shortId(item.contest_id)));

    var grid = el(document, 'div', 'priority-item__grid');
    grid.appendChild(el(document, 'p', 'priority-item__line',
      'Prova: ' + locationText(item.location && item.location.prova)));
    grid.appendChild(el(document, 'p', 'priority-item__line',
      'Lotação: ' + locationText(item.location && item.location.lotacao)));
    grid.appendChild(el(document, 'p', 'priority-item__line', formatDistance(item.distance)));
    grid.appendChild(el(document, 'p', 'priority-item__line',
      'Vagas indígenas imediatas: ' + formatCount(item.indigenous_immediate)
      + ' · Cadastro de reserva indígena: ' + formatCount(item.indigenous_reserve)));
    grid.appendChild(el(document, 'p', 'priority-item__line',
      'Compatibilidade: ' + (SI_LABEL[item.si_compatibility && item.si_compatibility.state]
        || 'não informada')));
    if (item.urgency) {
      var urgency = item.urgency.state === 'expirado' ? 'prazo expirado'
        : (item.urgency.state === 'proximo' ? 'prazo próximo' : item.urgency.state);
      grid.appendChild(el(document, 'p', 'priority-item__line',
        'Urgência (' + item.urgency.kind + '): ' + urgency + ' — ' + formatDate(item.urgency.date)));
    }
    card.appendChild(grid);

    // Fatores que explicam a pontuação (rastreável).
    var factors = el(document, 'ul', 'priority-item__factors');
    (item.factors || []).forEach(function (factor) {
      if (!factor.known) {
        factors.appendChild(el(document, 'li', 'factor factor--unknown',
          factor.key + ': desconhecido — ' + factor.reason));
        return;
      }
      factors.appendChild(el(document, 'li', 'factor',
        factor.key + ': ' + factor.points + '/' + factor.max + ' — ' + factor.reason));
    });
    card.appendChild(factors);

    var links = el(document, 'div', 'priority-item__links');
    var link = el(document, 'a', 'link', 'Abrir concurso');
    link.setAttribute('href', '#concurso=' + encodeURIComponent(item.contest_id));
    links.appendChild(link);
    card.appendChild(links);
    return card;
  }

  function fetchPriorities() {
    var doc = global.document;
    var container = doc && doc.getElementById('priorities-panel');
    if (!container) return Promise.resolve();
    return global.fetch('/api/prioridades?limit=200', {headers: {Accept: 'application/json'}})
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (payload) {
        container.textContent = '';
        container.appendChild(renderPriorities(doc, payload));
        if (payload && payload.preferences) loadPreferencesForm(doc, payload.preferences);
        if (payload && payload.items) fillContestSelect(doc, payload.items);
      })
      .catch(function (err) {
        showError(err);
        container.textContent = '';
        container.appendChild(el(doc, 'p', 'muted',
          'Priorização indisponível. Alertas e triagem continuam acessíveis.'));
      });
  }

  function loadPreferencesForm(doc, prefs) {
    var map = {municipio: 'pref-municipio', uf: 'pref-uf', interest: 'pref-interest',
               distance: 'pref-distance', priority: 'pref-priority'};
    var values = {
      municipio: prefs.reference_municipio || '',
      uf: prefs.reference_uf || '',
      interest: (prefs.interest_states || []).join(','),
      distance: prefs.practical_distance_km,
      priority: prefs.priority || 'equilibrado'
    };
    Object.keys(map).forEach(function (key) {
      var node = doc.getElementById(map[key]);
      if (node) node.value = values[key];
    });
  }

  function savePreferences() {
    var doc = global.document;
    var status = doc.getElementById('prefs-status');
    var payload = {
      reference_municipio: doc.getElementById('pref-municipio').value.trim() || null,
      reference_uf: (doc.getElementById('pref-uf').value.trim() || '').toUpperCase() || null,
      interest_states: doc.getElementById('pref-interest').value.split(',')
        .map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean),
      practical_distance_km: parseInt(doc.getElementById('pref-distance').value, 10),
      priority: doc.getElementById('pref-priority').value
    };
    return global.fetch('/api/preferencias', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify(payload)
    }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).then(function () {
      if (status) status.textContent = 'Preferências salvas.';
      return fetchPriorities();
    }).catch(function (err) {
      if (status) status.textContent = 'Não foi possível salvar (verifique UF e distância).';
      showError(err);
    });
  }

  // --- Estudos: cronômetro, sessões e painel (Fase 21) ------------------------

  var studyTimer = null;

  function formatClock(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    return [h, m, s].map(function (n) { return String(n).padStart(2, '0'); }).join(':');
  }

  function studyRequest(path, options) {
    return global.fetch(path, options).then(function (res) {
      return res.json().then(function (payload) {
        if (!res.ok) throw new Error(payload && payload.error ? payload.error : ('HTTP ' + res.status));
        return payload;
      });
    });
  }

  function studyPost(path, body) {
    return studyRequest(path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', Accept: 'application/json'},
      body: JSON.stringify(body || {})
    });
  }

  function stopStudyClock() {
    if (studyTimer && typeof global.clearInterval === 'function') {
      global.clearInterval(studyTimer);
    }
    studyTimer = null;
  }

  function renderStudyTimer(document, current) {
    var display = document.getElementById('timer-display');
    var context = document.getElementById('timer-context');
    if (!display) { stopStudyClock(); return; }
    if (!current) {
      display.textContent = '00:00:00';
      if (context) context.textContent = 'sem sessão';
      stopStudyClock();
      return;
    }
    var base = current.elapsed_seconds || 0;
    var startedAt = current.estado === 'em_andamento' ? Date.now() : null;
    function tick() {
      var extra = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;
      display.textContent = formatClock(base + extra);
    }
    tick();
    stopStudyClock();
    if (startedAt && typeof global.setInterval === 'function') {
      studyTimer = global.setInterval(tick, 1000);
    }
    if (context) {
      var estado = current.estado === 'em_andamento' ? 'em andamento'
        : (current.estado === 'pausada' ? 'pausada' : current.estado);
      context.textContent = estado + ' · ' + (current.modo || 'livre');
    }
  }

  function renderStudy(document, data) {
    data = data || {};
    var wrap = el(document, 'div', 'study__inner');

    var stats = el(document, 'div', 'study__stats');
    var overall = (data.conteudo && data.conteudo.overall) || {done: 0, total: 0, pct: 0};
    [
      ['Disciplinas', data.disciplinas || 0],
      ['Tópicos', data.topicos || 0],
      ['Progresso', overall.pct + '% (' + overall.done + '/' + overall.total + ')'],
      ['Tempo total', formatClock(data.total_segundos || 0)],
      ['Últimos 7 dias', formatClock(data.semana_segundos || 0)],
      ['Sessões concluídas', data.sessoes_concluidas || 0],
      ['Revisões pendentes', data.revisoes_pendentes || 0]
    ].forEach(function (pair) {
      var card = el(document, 'div', 'study__stat');
      card.appendChild(el(document, 'span', 'study__stat-value', String(pair[1])));
      card.appendChild(el(document, 'span', 'study__stat-label', pair[0]));
      stats.appendChild(card);
    });
    wrap.appendChild(stats);

    if (data.minutos_por_disciplina && data.minutos_por_disciplina.length) {
      var byDisc = el(document, 'ul', 'study__by-disc');
      data.minutos_por_disciplina.forEach(function (row) {
        byDisc.appendChild(el(document, 'li', 'study__by-disc-row',
          row.nome + ': ' + row.minutos + ' min'));
      });
      wrap.appendChild(el(document, 'h3', 'study__subtitle', 'Tempo por disciplina'));
      wrap.appendChild(byDisc);
    }

    if (data.revisoes && data.revisoes.length) {
      wrap.appendChild(el(document, 'h3', 'study__subtitle', 'Revisões pendentes'));
      var revs = el(document, 'ul', 'study__revisions');
      data.revisoes.slice(0, 10).forEach(function (rev) {
        var row = el(document, 'li', 'study__revision');
        row.appendChild(el(document, 'span', 'study__revision-label',
          'Tópico ' + shortId(rev.topico_id || rev.progresso_id) + ' — revisar desde ' + formatDate(rev.data)));
        var done = el(document, 'button', 'triage-action', 'Marcar revisada');
        done.type = 'button';
        done.addEventListener('click', function () {
          studyPost('/api/estudos/revisoes', {progresso_id: rev.progresso_id})
            .then(fetchStudy).catch(showError);
        });
        row.appendChild(done);
        revs.appendChild(row);
      });
      wrap.appendChild(revs);
    }

    wrap.appendChild(el(document, 'h3', 'study__subtitle', 'Disciplinas e tópicos'));
    var disciplinas = data.lista_disciplinas || [];
    if (!disciplinas.length) {
      wrap.appendChild(el(document, 'p', 'muted', 'Nenhuma disciplina cadastrada ainda.'));
    }
    disciplinas.forEach(function (disc) {
      var card = el(document, 'article', 'study-disc');
      card.appendChild(el(document, 'h4', 'study-disc__title', disc.nome));
      var list = el(document, 'ul', 'study-disc__topics');
      (disc.topicos || []).forEach(function (top) {
        var row = el(document, 'li', 'study-topic study-topic--' + top.state);
        row.appendChild(el(document, 'span', 'study-topic__name', top.nome));
        var select = el(document, 'select', 'study-topic__state');
        [['nao_iniciado', 'Não iniciado'], ['estudando', 'Estudando'],
         ['revisado', 'Revisado'], ['concluido', 'Concluído']].forEach(function (opt) {
          var option = el(document, 'option', '', opt[1]);
          option.setAttribute('value', opt[0]);
          if (opt[0] === top.state) option.setAttribute('selected', 'selected');
          select.appendChild(option);
        });
        select.addEventListener('change', function () {
          studyPost('/api/estudos/progresso', {topico_id: top.id, state: select.value})
            .then(fetchStudy).catch(showError);
        });
        row.appendChild(select);
        list.appendChild(row);
      });
      if (!(disc.topicos || []).length) {
        list.appendChild(el(document, 'li', 'muted', 'Sem tópicos.'));
      }
      card.appendChild(list);
      var form = el(document, 'form', 'study-disc__add');
      var input = el(document, 'input', 'study-disc__input');
      input.setAttribute('type', 'text');
      input.setAttribute('placeholder', 'Novo tópico');
      input.setAttribute('aria-label', 'Novo tópico em ' + disc.nome);
      var btn = el(document, 'button', 'button button--ghost', 'Adicionar');
      btn.setAttribute('type', 'submit');
      form.appendChild(input);
      form.appendChild(btn);
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        if (!input.value.trim()) return;
        studyPost('/api/estudos/topicos', {disciplina_id: disc.id, nome: input.value.trim()})
          .then(fetchStudy).catch(showError);
      });
      card.appendChild(form);
      wrap.appendChild(card);
    });
    return wrap;
  }

  function fetchStudy() {
    var doc = global.document;
    var panel = doc && doc.getElementById('study-panel');
    if (!panel) return Promise.resolve();
    return global.fetch('/api/estudos/painel', {headers: {Accept: 'application/json'}})
      .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
      .then(function (data) {
        return Promise.all([
          global.fetch('/api/estudos/disciplinas', {headers: {Accept: 'application/json'}})
            .then(function (r) { return r.json(); }),
          global.fetch('/api/estudos/topicos', {headers: {Accept: 'application/json'}})
            .then(function (r) { return r.json(); })
        ]).then(function (parts) {
          var disciplinas = parts[0], topicos = parts[1];
          var byDisc = {};
          topicos.forEach(function (t) { byDisc[t.disciplina_id] = byDisc[t.disciplina_id] || []; });
          var states = {};
          (data.progresso || []).forEach(function (p) { states[p.topico_id] = p.state; });
          topicos.forEach(function (t) {
            byDisc[t.disciplina_id].push({id: t.id, nome: t.nome, state: states[t.id] || 'nao_iniciado'});
          });
          data.lista_disciplinas = disciplinas.map(function (d) {
            return {id: d.id, nome: d.nome, topicos: byDisc[d.id] || []};
          });
          panel.textContent = '';
          panel.appendChild(renderStudy(doc, data));
          renderStudyTimer(doc, data.sessao_aberta);
          fillDisciplinaSelect(doc, disciplinas);
        });
      })
      .catch(function (err) {
        showError(err);
        panel.textContent = '';
        panel.appendChild(el(doc, 'p', 'muted', 'Estudos indisponíveis.'));
      });
  }

  function fillDisciplinaSelect(doc, disciplinas) {
    var select = doc.getElementById('timer-disciplina');
    if (!select) return;
    var current = select.value;
    select.textContent = '';
    var none = el(doc, 'option', '', 'Sem disciplina');
    none.setAttribute('value', '');
    select.appendChild(none);
    disciplinas.forEach(function (d) {
      var opt = el(doc, 'option', '', d.nome);
      opt.setAttribute('value', d.id);
      select.appendChild(opt);
    });
    if (current) select.value = current;
  }

  function timerAction(action) {
    var doc = global.document;
    var body = {action: action};
    if (action === 'start') {
      var disc = doc.getElementById('timer-disciplina');
      var modo = doc.getElementById('timer-modo');
      body.disciplina_id = (disc && disc.value) || null;
      body.modo = (modo && modo.value) || 'livre';
    }
    var status = doc.getElementById('study-status');
    return studyPost('/api/estudos/sessoes', body)
      .then(function () { if (status) status.textContent = ''; return fetchStudy(); })
      .catch(function (err) {
        if (status) status.textContent = err.message || 'Falha na sessão.';
        showError(err);
      });
  }

  // --- Preparação e conteúdo programático (Fase 22) ---------------------------

  var LEVEL_LABEL = {
    nao_avaliado: 'Não avaliado', nao_conheco: 'Ainda não conheço', basico: 'Básico',
    intermediario: 'Intermediário', avancado: 'Avançado'
  };
  var CONTENT_STATE_LABEL = {
    confirmado: 'confirmado por revisão', extraido_nao_revisado: 'extraído (não revisado)',
    ambiguo: 'ambíguo', rejeitado: 'rejeitado'
  };

  function prepContestId() {
    var doc = global.document;
    var select = doc && doc.getElementById('prep-concurso');
    return select ? select.value : '';
  }

  function renderPrep(document, program, report) {
    var wrap = el(document, 'div', 'prep__inner');
    var counts = (report && report.coverage && report.coverage.counts) || {};
    var coverage = (report && report.coverage) || {};
    var state = (program && program.coverage_state) || 'nao_localizado';
    var stateLabel = {
      nao_localizado: 'Conteúdo programático não localizado',
      extraido_nao_revisado: 'Conteúdo extraído, ainda não revisado',
      extraido_parcial: 'Conteúdo parcialmente extraído/revisado'
    }[state] || state;

    wrap.appendChild(el(document, 'p', 'prep__state', 'Situação: ' + stateLabel));

    var stats = el(document, 'div', 'prep__stats');
    var pctText = coverage.pct === null || coverage.pct === undefined ? 'não calculável'
      : (coverage.pct + '%');
    [
      ['Tópicos identificados', counts.identificados || 0],
      ['Confirmados (revisão)', counts.confirmados || 0],
      ['Cobertura do perfil', pctText],
      ['Conhecidos', counts.conhecidos || 0],
      ['Ainda não conheço', counts.nao_conhecidos || 0],
      ['Precisam revisar', counts.revisar || 0]
    ].forEach(function (pair) {
      var card = el(document, 'div', 'study__stat');
      card.appendChild(el(document, 'span', 'study__stat-value', String(pair[1])));
      card.appendChild(el(document, 'span', 'study__stat-label', pair[0]));
      stats.appendChild(card);
    });
    wrap.appendChild(stats);
    wrap.appendChild(el(document, 'p', 'prep__basis', coverage.basis || ''));

    // Conteúdo por disciplina.
    var byDisc = {};
    (program && program.topicos ? program.topicos : []).forEach(function (t) {
      var disc = t.disciplina || 'Sem disciplina';
      byDisc[disc] = byDisc[disc] || [];
      byDisc[disc].push(t);
    });
    var discNames = Object.keys(byDisc);
    if (!discNames.length) {
      wrap.appendChild(el(document, 'p', 'muted', 'Nenhum conteúdo programático identificado.'));
    }
    discNames.sort().forEach(function (disc) {
      var card = el(document, 'article', 'study-disc');
      card.appendChild(el(document, 'h4', 'study-disc__title', disc));
      var list = el(document, 'ul', 'study-disc__topics');
      byDisc[disc].forEach(function (topic) {
        var row = el(document, 'li', 'study-topic study-topic--' + topic.estado);
        row.appendChild(el(document, 'span', 'study-topic__name', topic.value));
        row.appendChild(badge(document, CONTENT_STATE_LABEL[topic.estado] || topic.estado, 'kind'));
        if (!isMissing(topic.page_number)) {
          row.appendChild(el(document, 'span', 'prep__page', 'pág. ' + topic.page_number));
        }
        var gap = el(document, 'button', 'triage-action', 'Enviar para estudos');
        gap.type = 'button';
        gap.addEventListener('click', function () {
          studyPost('/api/estudos/lacuna',
            {contest_id: prepContestId(), conceito_key: topic.conceito_key})
            .then(function () { if (global.alert) global.alert('Tópico enviado para o módulo de estudos.'); })
            .catch(showError);
        });
        row.appendChild(gap);
        list.appendChild(row);
      });
      card.appendChild(list);
      wrap.appendChild(card);
    });

    if (report && report.gaps && report.gaps.length) {
      wrap.appendChild(el(document, 'h3', 'study__subtitle', 'Principais lacunas'));
      var gaps = el(document, 'ul', 'study__revisions');
      report.gaps.slice(0, 15).forEach(function (g) {
        gaps.appendChild(el(document, 'li', 'study__revision',
          (g.disciplina ? g.disciplina + ' — ' : '') + g.rotulo + ' (' + (LEVEL_LABEL[g.nivel] || g.nivel) + ')'));
      });
      wrap.appendChild(gaps);
    }
    return wrap;
  }

  function fetchPrep() {
    var doc = global.document;
    var panel = doc && doc.getElementById('prep-panel');
    var contest = prepContestId();
    if (!panel) return Promise.resolve();
    if (!contest) {
      panel.textContent = '';
      panel.appendChild(el(doc, 'p', 'muted', 'Selecione um concurso para ver o conteúdo programático.'));
      return Promise.resolve();
    }
    return Promise.all([
      global.fetch('/api/estudos/conteudo?contest_id=' + encodeURIComponent(contest), {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : {}; }),
      global.fetch('/api/estudos/preparacao?contest_id=' + encodeURIComponent(contest), {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : {}; })
    ]).then(function (parts) {
      panel.textContent = '';
      panel.appendChild(renderPrep(doc, parts[0], parts[1]));
    }).catch(function (err) {
      showError(err);
      panel.textContent = '';
      panel.appendChild(el(doc, 'p', 'muted', 'Preparação indisponível.'));
    });
  }

  function fillContestSelect(document, items) {
    var select = document.getElementById('prep-concurso');
    if (!select) return;
    var current = select.value;
    select.textContent = '';
    var none = el(document, 'option', '', 'Selecione um concurso');
    none.setAttribute('value', '');
    select.appendChild(none);
    (items || []).slice(0, 100).forEach(function (item) {
      var opt = el(document, 'option', '', 'Concurso ' + shortId(item.contest_id));
      opt.setAttribute('value', item.contest_id);
      select.appendChild(opt);
    });
    if (current) select.value = current;
  }

  function renderPerfil(document, entries) {
    var wrap = el(document, 'div', 'prep__inner');
    if (!entries || !entries.length) {
      wrap.appendChild(el(document, 'p', 'muted', 'Perfil vazio: registre o que você já conhece.'));
      return wrap;
    }
    var list = el(document, 'ul', 'study__revisions');
    entries.forEach(function (entry) {
      var row = el(document, 'li', 'study__revision');
      var label = (entry.disciplina ? entry.disciplina + ' — ' : '') + entry.rotulo
        + ' (' + (LEVEL_LABEL[entry.nivel] || entry.nivel) + (entry.revisar ? ', revisar' : '') + ')';
      row.appendChild(el(document, 'span', 'study__revision-label', label));
      var del = el(document, 'button', 'triage-action triage-action--danger', 'Remover');
      del.type = 'button';
      del.addEventListener('click', function () {
        global.fetch('/api/estudos/perfil?conceito_key=' + encodeURIComponent(entry.conceito_key),
          {method: 'DELETE'})
          .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return fetchPerfil(); })
          .catch(showError);
      });
      row.appendChild(del);
      list.appendChild(row);
    });
    wrap.appendChild(list);
    return wrap;
  }

  function fetchPerfil() {
    var doc = global.document;
    var panel = doc && doc.getElementById('perfil-panel');
    if (!panel) return Promise.resolve();
    return global.fetch('/api/estudos/perfil', {headers: {Accept: 'application/json'}})
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (entries) {
        panel.textContent = '';
        panel.appendChild(renderPerfil(doc, entries));
      }).catch(function (err) { showError(err); });
  }

  function savePerfil() {
    var doc = global.document;
    var status = doc.getElementById('perfil-status');
    var payload = {
      disciplina: doc.getElementById('perfil-disciplina').value.trim() || null,
      rotulo: doc.getElementById('perfil-rotulo').value.trim(),
      nivel: doc.getElementById('perfil-nivel').value,
      revisar: doc.getElementById('perfil-revisar').checked
    };
    if (!payload.rotulo) {
      if (status) status.textContent = 'Informe o tópico.';
      return;
    }
    return studyPost('/api/estudos/perfil', payload).then(function () {
      if (status) status.textContent = 'Salvo.';
      doc.getElementById('perfil-rotulo').value = '';
      return Promise.all([fetchPerfil(), fetchPrep()]);
    }).catch(function (err) {
      if (status) status.textContent = err.message || 'Falha ao salvar.';
      showError(err);
    });
  }

  // --- Prática: flashcards, questões e simulados (Fase 23) --------------------

  var QUALITY_LABEL = {0: 'Esqueci', 1: 'Errei', 2: 'Difícil', 3: 'Ok', 4: 'Bom', 5: 'Fácil'};

  function renderFlashcards(document, queue, stats) {
    var wrap = el(document, 'div', 'practice__inner');
    stats = stats || {};
    var summary = el(document, 'p', 'prep__state',
      'Cartões ativos: ' + (stats.ativos || 0) + ' · novos: ' + (stats.novos || 0)
      + ' · pendentes: ' + (stats.pendentes || 0)
      + (stats.pct_acerto === null || stats.pct_acerto === undefined
        ? ' · acerto não calculável' : ' · acerto: ' + stats.pct_acerto + '%'));
    wrap.appendChild(summary);
    wrap.appendChild(el(document, 'p', 'prep__basis', stats.basis || ''));

    var cards = (queue && queue.fila) || [];
    if (!cards.length) {
      wrap.appendChild(el(document, 'p', 'muted', 'Nenhum cartão pendente.'));
      return wrap;
    }
    cards.slice(0, 20).forEach(function (card) {
      var row = el(document, 'article', 'study-disc');
      row.appendChild(el(document, 'h4', 'study-disc__title', card.frente));
      var answer = el(document, 'p', 'muted', 'Resposta oculta');
      var reveal = el(document, 'button', 'triage-action', 'Mostrar resposta');
      reveal.type = 'button';
      reveal.addEventListener('click', function () {
        answer.textContent = card.verso;
        answer.className = 'practice__answer';
      });
      row.appendChild(reveal);
      row.appendChild(answer);
      var actions = el(document, 'div', 'triage-alert__actions');
      [0, 3, 4, 5].forEach(function (quality) {
        var btn = el(document, 'button', 'triage-action', QUALITY_LABEL[quality]);
        btn.type = 'button';
        btn.addEventListener('click', function () {
          studyPost('/api/estudos/flashcards', {action: 'review', id: card.id, qualidade: quality})
            .then(fetchPractice).catch(showError);
        });
        actions.appendChild(btn);
      });
      row.appendChild(actions);
      wrap.appendChild(row);
    });
    return wrap;
  }

  function renderQuestions(document, questions) {
    var wrap = el(document, 'div', 'practice__inner');
    if (!questions || !questions.length) {
      wrap.appendChild(el(document, 'p', 'muted', 'Nenhuma questão cadastrada.'));
      return wrap;
    }
    questions.slice(0, 20).forEach(function (q) {
      var card = el(document, 'article', 'study-disc');
      card.appendChild(el(document, 'h4', 'study-disc__title', q.enunciado));
      var meta = el(document, 'p', 'prep__basis',
        (q.disciplina || 'sem disciplina') + ' · ' + (q.topico || 'sem tópico')
        + ' · versão ' + q.versao);
      card.appendChild(meta);
      var options = el(document, 'div', 'triage-alert__actions');
      (q.alternativas || []).forEach(function (alt) {
        var btn = el(document, 'button', 'triage-action', alt.id + ') ' + alt.texto);
        btn.type = 'button';
        btn.addEventListener('click', function () {
          studyPost('/api/estudos/tentativas', {questao_id: q.id, resposta: alt.id})
            .then(function (result) {
              var feedback = el(document, 'p', result.correta ? 'practice__ok' : 'practice__fail',
                result.correta ? 'Correta!' : 'Incorreta. Gabarito: ' + result.gabarito);
              card.appendChild(feedback);
              return fetchPractice();
            }).catch(showError);
        });
        options.appendChild(btn);
      });
      card.appendChild(options);
      wrap.appendChild(card);
    });
    return wrap;
  }

  function renderExams(document, exams) {
    var wrap = el(document, 'div', 'practice__inner');
    if (!exams || !exams.length) {
      wrap.appendChild(el(document, 'p', 'muted', 'Nenhum simulado criado.'));
      return wrap;
    }
    exams.slice(0, 10).forEach(function (exam) {
      var card = el(document, 'article', 'study-disc');
      card.appendChild(el(document, 'h4', 'study-disc__title', exam.nome));
      card.appendChild(el(document, 'p', 'prep__basis',
        'estado: ' + exam.estado + ' · iniciado ' + formatVerifiedAt(exam.iniciado_em)));
      if (exam.estado === 'em_andamento') {
        var open = el(document, 'button', 'triage-action', 'Responder / retomar');
        open.type = 'button';
        open.addEventListener('click', function () {
          studyRequest('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/questoes')
            .then(function (payload) { renderExamRunner(document, card, payload); })
            .catch(showError);
        });
        card.appendChild(open);
      } else {
        var link = el(document, 'button', 'triage-action', 'Ver resultado');
        link.type = 'button';
        link.addEventListener('click', function () {
          studyRequest('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/resultado')
            .then(function (payload) { showExamResult(document, card, payload); }).catch(showError);
        });
        card.appendChild(link);
      }
      wrap.appendChild(card);
    });
    return wrap;
  }

  function renderExamRunner(document, card, payload) {
    var exam = payload.simulado || {};
    var questions = payload.questoes || [];
    var box = el(document, 'div', 'practice__result');
    var clock = el(document, 'p', 'timer__display', '');
    var remaining = payload.restante_segundos;
    function tick() {
      if (remaining === null || remaining === undefined) { clock.textContent = 'sem limite'; return; }
      clock.textContent = formatClock(remaining);
    }
    tick();
    box.appendChild(clock);
    if (remaining !== null && remaining !== undefined && typeof global.setInterval === 'function') {
      var timer = global.setInterval(function () {
        remaining = Math.max(0, remaining - 1);
        tick();
        if (remaining === 0) {
          global.clearInterval(timer);
          studyPost('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/finalizar', {})
            .then(fetchPractice).catch(showError);
        }
      }, 1000);
    }
    questions.forEach(function (q) {
      var item = el(document, 'div', 'study-disc');
      item.appendChild(el(document, 'p', 'study-disc__title',
        (q.ordem + 1) + '. ' + q.enunciado));
      var options = el(document, 'div', 'triage-alert__actions');
      (q.alternativas || []).forEach(function (alt) {
        var btn = el(document, 'button', 'triage-action'
          + (q.resposta === alt.id ? ' is-active' : ''), alt.id + ') ' + alt.texto);
        btn.type = 'button';
        btn.addEventListener('click', function () {
          studyPost('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/responder',
            {ordem: q.ordem, resposta: alt.id}).then(function () {
              q.resposta = alt.id;
              Array.prototype.forEach.call(options.children, function (node) {
                node.classList.remove('is-active');
              });
              btn.classList.add('is-active');
            }).catch(showError);
        });
        options.appendChild(btn);
      });
      item.appendChild(options);
      box.appendChild(item);
    });
    var finish = el(document, 'button', 'button', 'Finalizar simulado');
    finish.type = 'button';
    finish.addEventListener('click', function () {
      studyPost('/api/estudos/simulados/' + encodeURIComponent(exam.id) + '/finalizar', {})
        .then(function () { return fetchPractice(); }).catch(showError);
    });
    box.appendChild(finish);
    card.appendChild(box);
  }

  function showExamResult(document, card, payload) {
    var res = payload.resultado || {};
    var box = el(document, 'div', 'practice__result');
    box.appendChild(el(document, 'p', 'practice__answer',
      'Acertos: ' + (res.acertos || 0) + '/' + (res.total || 0)
      + (res.pct === null || res.pct === undefined ? '' : ' (' + res.pct + '%)')));
    box.appendChild(el(document, 'p', 'prep__basis', res.basis || ''));
    (res.por_disciplina || []).forEach(function (g) {
      box.appendChild(el(document, 'p', 'study__revision',
        g.grupo + ': ' + g.acertos + '/' + g.total
        + (g.pct === null ? '' : ' (' + g.pct + '%)')));
    });
    card.appendChild(box);
  }

  function renderPerformance(document, report) {
    var wrap = el(document, 'div', 'practice__inner');
    var geral = (report && report.geral) || {};
    wrap.appendChild(el(document, 'p', 'prep__state',
      'Tentativas: ' + (geral.total || 0) + ' · acertos: ' + (geral.acertos || 0)
      + ' · brancos: ' + (geral.brancos || 0)));
    wrap.appendChild(el(document, 'p', 'prep__basis', geral.basis || ''));
    var byDisc = (report && report.por_disciplina) || [];
    if (byDisc.length) {
      wrap.appendChild(el(document, 'h3', 'study__subtitle', 'Desempenho por disciplina'));
      var list = el(document, 'ul', 'study__revisions');
      byDisc.forEach(function (g) {
        list.appendChild(el(document, 'li', 'study__revision',
          g.grupo + ': ' + g.acertos + '/' + g.total + (g.pct === null ? '' : ' (' + g.pct + '%)')));
      });
      wrap.appendChild(list);
    }
    return wrap;
  }

  function fetchPractice() {
    var doc = global.document;
    if (!doc || !doc.getElementById('fc-panel')) return Promise.resolve();
    return Promise.all([
      global.fetch('/api/estudos/flashcards/fila?limit=20', {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : {}; }),
      global.fetch('/api/estudos/flashcards/estatisticas', {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : {}; }),
      global.fetch('/api/estudos/questoes', {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : []; }),
      global.fetch('/api/estudos/simulados', {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : []; }),
      global.fetch('/api/estudos/desempenho', {headers: {Accept: 'application/json'}})
        .then(function (r) { return r.ok ? r.json() : {}; })
    ]).then(function (parts) {
      var targets = [['fc-panel', renderFlashcards(doc, parts[0], parts[1])],
                     ['q-panel', renderQuestions(doc, parts[2])],
                     ['exam-panel', renderExams(doc, parts[3])],
                     ['perf-panel', renderPerformance(doc, parts[4])]];
      targets.forEach(function (pair) {
        var node = doc.getElementById(pair[0]);
        if (node) { node.textContent = ''; node.appendChild(pair[1]); }
      });
    }).catch(function (err) {
      showError(err);
      var node = doc.getElementById('fc-panel');
      if (node) {
        node.textContent = '';
        node.appendChild(el(doc, 'p', 'muted', 'Prática indisponível.'));
      }
    });
  }

  // Atualização periódica (sem recarregar a página). Intervalo configurável por
  // `data-refresh-seconds` no <body>; padrão conservador de 60 s.
  function autoRefreshSeconds() {
    var doc = global.document;
    var body = doc && doc.body;
    var raw = body && body.getAttribute ? body.getAttribute('data-refresh-seconds') : null;
    var seconds = parseInt(raw, 10);
    if (!seconds || seconds < 15) return 60;
    return Math.min(seconds, 600);
  }

  function startAutoRefresh() {
    if (typeof global.setInterval !== 'function') return null;
    var interval = autoRefreshSeconds() * 1000;
    return global.setInterval(function () {
      fetchData();
      fetchMonitoring();
      fetchAlerts();
      fetchTriage();
      fetchPriorities();
      // A seção de Estudos NÃO é reconstruída no auto-refresh: preserva o formulário em uso
      // e o relógio do cronômetro (que tem seu próprio intervalo).
    }, interval);
  }

  function fetchMonitoring() {
    var doc = global.document;
    var container = doc && doc.getElementById('monitoring-panel');
    if (!container) return Promise.resolve();
    return global.fetch('/api/monitoramento', {headers: {Accept: 'application/json'}})
      .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
      .then(function (status) {
        clearContainer(container);
        container.appendChild(renderMonitoring(doc, status));
      }).catch(function (err) {
        showError(err);
        clearContainer(container);
        container.appendChild(el(doc, 'p', 'error-text', 'Status de monitoramento indisponível.'));
      });
  }

  function matchIdentity(record, identities) {
    return (identities || []).find(function (identity) {
      return (identity.observations || []).some(function (observation) {
        return observation.source_url === record.source_url && observation.competition_id === record.competition_id;
      });
    });
  }

  function attachDocumentControls(document, records, identities, container) {
    records.forEach(function (record, index) {
      var card = container.children[index];
      var identity = matchIdentity(record, identities);
      if (!identity) {
        card.appendChild(el(document, 'p', 'muted', 'Histórico documental ainda não sincronizado.'));
        return;
      }
      card.setAttribute('data-contest-id', identity.id);
      card.setAttribute('id', 'concurso-' + identity.id);
      var footer = el(document, 'div', 'card__docs');
      var button = el(document, 'button', 'button button--ghost', 'Ver histórico documental');
      button.setAttribute('type', 'button');
      button.setAttribute('aria-expanded', 'false');
      var panel = el(document, 'div', 'documents__panel');
      button.addEventListener('click', function () {
        button.disabled = true;
        panel.textContent = 'Carregando histórico documental…';
        global.fetch('/api/concursos/' + encodeURIComponent(identity.id) + '/detalhes',
          {headers: {Accept: 'application/json'}}).then(function (response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
          }).then(function (details) {
            clearContainer(panel);
            panel.appendChild(renderDocumentDetails(document, details));
            button.setAttribute('aria-expanded', 'true');
          }).catch(function (err) {
            panel.textContent = 'Histórico documental indisponível. Tente novamente.';
            showError(err);
          }).finally(function () { button.disabled = false; });
      });
      footer.appendChild(button);
      footer.appendChild(panel);
      card.appendChild(footer);
    });
  }

  function clearContainer(container) {
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
  }

  function renderList(document, records, container) {
    clearContainer(container);
    records.forEach(function (record) {
      container.appendChild(renderRecordCard(document, record));
    });
  }

  function setState(name) {
    var doc = global.document;
    if (!doc) return;
    ['loading', 'error', 'empty', 'data'].forEach(function (state) {
      var node = doc.getElementById('state-' + state);
      if (node) node.hidden = (state !== name);
    });
    var live = doc.getElementById('live');
    if (live) {
      var messages = {
        loading: 'Carregando concursos.',
        error: 'Não foi possível carregar os dados.',
        empty: 'Nenhum concurso disponível.',
        data: 'Concursos carregados.'
      };
      live.textContent = messages[name] || '';
    }
  }

  function showError(err) {
    if (global.console && typeof global.console.error === 'function') {
      global.console.error(err);
    }
  }

  function fetchData() {
    var doc = global.document;
    setState('loading');
    return global.fetch('/api/concursos', {
      headers: { Accept: 'application/json' }
    }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).then(function (data) {
      if (!Array.isArray(data)) throw new Error('Formato inesperado da API');
      if (data.length === 0) {
        setState('empty');
      } else {
        renderList(doc, data, doc.getElementById('competition-list'));
        setState('data');
        return global.fetch('/api/concursos/identidades', {headers: {Accept: 'application/json'}})
          .then(function (res) { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
          .then(function (identities) {
            attachDocumentControls(doc, data, identities, doc.getElementById('competition-list'));
          }).catch(function (err) {
            showError(err);
            data.forEach(function (_, index) {
              var card = doc.getElementById('competition-list').children[index];
              if (card) {
                card.appendChild(el(doc, 'p', 'error-text',
                  'Histórico documental indisponível. A lista do artigo continua visível.'));
              }
            });
          });
      }
    }).catch(function (err) {
      showError(err);
      setState('error');
    });
  }

  function init() {
    var doc = global.document;
    if (!doc) return;
    var reload = function () { fetchData(); fetchMonitoring(); fetchAlerts(); fetchTriage(); fetchPriorities(); fetchStudy(); };
    var retry = doc.getElementById('retry-button');
    if (retry) retry.addEventListener('click', reload);
    var prefsForm = doc.getElementById('preferences-form');
    if (prefsForm) prefsForm.addEventListener('submit', function (event) {
      event.preventDefault();
      savePreferences();
    });
    var studyForm = doc.getElementById('study-form');
    if (studyForm) studyForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var input = doc.getElementById('study-disciplina-nome');
      if (!input || !input.value.trim()) return;
      studyPost('/api/estudos/disciplinas', {nome: input.value.trim()})
        .then(function () { input.value = ''; return fetchStudy(); }).catch(showError);
    });
    [['timer-start', 'start'], ['timer-pause', 'pause'], ['timer-resume', 'resume'],
     ['timer-finish', 'finish'], ['timer-discard', 'discard']].forEach(function (pair) {
      var btn = doc.getElementById(pair[0]);
      if (btn) btn.addEventListener('click', function () { timerAction(pair[1]); });
    });
    var perfilForm = doc.getElementById('perfil-form');
    if (perfilForm) perfilForm.addEventListener('submit', function (event) {
      event.preventDefault();
      savePerfil();
    });
    var prepSelect = doc.getElementById('prep-concurso');
    if (prepSelect) prepSelect.addEventListener('change', function () { fetchPrep(); });
    var prepReload = doc.getElementById('prep-reload');
    if (prepReload) prepReload.addEventListener('click', function () { fetchPrep(); });
    var fcForm = doc.getElementById('fc-form');
    if (fcForm) fcForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var frente = doc.getElementById('fc-frente').value.trim();
      var verso = doc.getElementById('fc-verso').value.trim();
      if (!frente || !verso) return;
      studyPost('/api/estudos/flashcards', {frente: frente, verso: verso}).then(function () {
        doc.getElementById('fc-frente').value = '';
        doc.getElementById('fc-verso').value = '';
        return fetchPractice();
      }).catch(showError);
    });
    var fcRefresh = doc.getElementById('fc-refresh');
    if (fcRefresh) fcRefresh.addEventListener('click', function () { fetchPractice(); });
    var qForm = doc.getElementById('q-form');
    if (qForm) qForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var alternativas = doc.getElementById('q-alternativas').value.split('|')
        .map(function (s) { return s.trim(); }).filter(Boolean);
      studyPost('/api/estudos/questoes', {
        enunciado: doc.getElementById('q-enunciado').value.trim(),
        alternativas: alternativas,
        gabarito: doc.getElementById('q-gabarito').value.trim(),
        disciplina: doc.getElementById('q-disciplina').value.trim() || null
      }).then(function () {
        ['q-enunciado', 'q-alternativas', 'q-gabarito'].forEach(function (id) {
          doc.getElementById(id).value = '';
        });
        return fetchPractice();
      }).catch(function (err) {
        var status = doc.getElementById('q-status');
        if (status) status.textContent = err.message || 'Falha ao criar questão.';
      });
    });
    var examForm = doc.getElementById('exam-form');
    if (examForm) examForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var minutos = parseInt(doc.getElementById('exam-duracao').value, 10) || 0;
      studyPost('/api/estudos/simulados', {
        nome: doc.getElementById('exam-nome').value.trim() || 'Simulado',
        limit: parseInt(doc.getElementById('exam-limit').value, 10) || 10,
        duracao_segundos: minutos > 0 ? minutos * 60 : null
      }).then(function () { return fetchPractice(); }).catch(function (err) {
        var status = doc.getElementById('exam-status');
        if (status) status.textContent = err.message || 'Falha ao montar simulado.';
      });
    });
    fetchData().then(focusContestFromHash).catch(function () {});
    fetchMonitoring();
    fetchAlerts();
    fetchTriage();
    fetchPriorities();
    fetchStudy();
    fetchPerfil();
    fetchPractice();
    startAutoRefresh();
    if (global.addEventListener) {
      global.addEventListener('hashchange', function () { focusContestFromHash(); });
    }
  }

  var Radar = {
    UNKNOWN: UNKNOWN,
    isMissing: isMissing,
    formatCount: formatCount,
    formatText: formatText,
    formatDate: formatDate,
    formatVerifiedAt: formatVerifiedAt,
    isHttpsUrl: isHttpsUrl,
    shortId: shortId,
    renderRecordCard: renderRecordCard,
    renderDocumentDetails: renderDocumentDetails,
    renderMonitoring: renderMonitoring,
    renderAlerts: renderAlerts,
    renderTriage: renderTriage,
    renderPriorities: renderPriorities,
    renderStudy: renderStudy,
    renderPrep: renderPrep,
    renderPerfil: renderPerfil,
    renderFlashcards: renderFlashcards,
    renderQuestions: renderQuestions,
    renderExams: renderExams,
    renderPerformance: renderPerformance,
    formatClock: formatClock,
    matchIdentity: matchIdentity,
    renderList: renderList,
    setState: setState,
    fetchData: fetchData,
    fetchMonitoring: fetchMonitoring,
    fetchAlerts: fetchAlerts,
    autoRefreshSeconds: autoRefreshSeconds,
    startAutoRefresh: startAutoRefresh,
    init: init
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = Radar;
  } else {
    global.Radar = Radar;
  }

  // Bootstrap no navegador (em Node, outro ambiente sem document, nada acontece).
  if (typeof global.document !== 'undefined') {
    if (global.document.readyState === 'loading') {
      global.document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }
})(typeof window !== 'undefined' ? window : globalThis);
