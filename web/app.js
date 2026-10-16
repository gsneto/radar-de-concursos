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
    indigenous_vacancies: 'Vagas indígenas',
    registration_start: 'Início das inscrições',
    registration_end: 'Fim das inscrições',
    registration_status: 'Situação das inscrições',
    exam_date: 'Data da prova',
    exam_location: 'Local de prova',
    work_location: 'Local de exercício',
    education: 'Escolaridade'
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
    var reload = function () { fetchData(); fetchMonitoring(); };
    var retry = doc.getElementById('retry-button');
    if (retry) retry.addEventListener('click', reload);
    fetchData();
    fetchMonitoring();
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
    matchIdentity: matchIdentity,
    renderList: renderList,
    setState: setState,
    fetchData: fetchData,
    fetchMonitoring: fetchMonitoring,
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
