/* Radar de Concursos — interface sem dependências.
 * Consome apenas GET /api/concursos (API local) e renderiza com APIs textuais
 * seguras (textContent / createElement), sem injetar HTML a partir de dados da API.
 */
(function (global) {
  'use strict';

  var UNKNOWN = 'Desconhecido';

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
  // (ou inesperados) são exibidos sem transformação, sem ganhar/ perder informação.
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

  function el(document, tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function makeLink(document, url, text) {
    var a = el(document, 'a', 'card__link', text);
    a.setAttribute('href', url);
    a.setAttribute('target', '_blank');
    a.setAttribute('rel', 'noopener noreferrer');
    return a;
  }

  // value pode ser string (definida como textContent) ou elemento (ex.: link).
  function addPair(document, dl, label, value) {
    var dt = el(document, 'dt', 'card__dt', label);
    var dd = el(document, 'dd', 'card__dd');
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

  function renderRecordCard(document, record) {
    var article = el(document, 'article', 'card');

    var header = el(document, 'div', 'card__header');
    if (!isMissing(record.competition_id)) {
      header.appendChild(el(document, 'span', 'card__id', String(record.competition_id)));
    }
    header.appendChild(el(document, 'h3', 'card__title', formatText(record.competition)));
    article.appendChild(header);

    var dl = el(document, 'dl', 'card__dl');

    addPair(document, dl, 'Órgão', formatText(record.agency));
    addPair(document, dl, 'Cargo', formatText(record.role));
    addPair(document, dl, 'Escolaridade', formatText(record.education));

    // Modalidades de vaga mantidas separadas, sem somar.
    addPair(document, dl, 'Vagas imediatas', formatCount(record.immediate_vacancies));
    addPair(document, dl, 'Cadastro de reserva', formatCount(record.reserve_vacancies));
    addPair(document, dl, 'Vagas indígenas', formatCount(record.indigenous_vacancies));

    addPair(document, dl, 'Início das inscrições', formatDate(record.registration_start));
    addPair(document, dl, 'Fim das inscrições', formatDate(record.registration_end));
    addPair(document, dl, 'Inscrições segundo o período do artigo', formatText(record.registration_status));
    addPair(document, dl, 'Data da prova', formatDate(record.exam_date));

    // Local de prova distinto de local de exercício.
    addPair(document, dl, 'Local de prova', formatText(record.exam_location));
    addPair(document, dl, 'Local de exercício', formatText(record.work_location));

    addPair(document, dl, 'Fonte', sourceValue(document, record));
    addPair(document, dl, 'Evidência', evidenceValue(document, record));
    addPair(document, dl, 'Artigo consultado em', formatVerifiedAt(record.verified_at));

    article.appendChild(dl);
    return article;
  }

  function renderDocumentDetails(document, details) {
    var section = el(document, 'section', 'documents');
    var coverage = details.coverage || {};
    var coverageLabels = {nao_auditada: 'Não auditada', parcial: 'Parcial', auditada_ate: 'Auditada até a data indicada'};
    section.appendChild(el(document, 'h4', 'documents__heading', 'Histórico documental'));
    section.appendChild(el(document, 'p', 'documents__status', 'Cobertura: ' +
      (coverageLabels[coverage.state] || 'Desconhecida') + (coverage.checked_at ? ' · ' + coverage.checked_at : '')));
    if (!details.documents || details.documents.length === 0) {
      section.appendChild(el(document, 'p', 'documents__muted', 'Nenhum documento cadastrado.'));
    }
    (details.documents || []).forEach(function (item) {
      var row = el(document, 'div', 'documents__item');
      row.appendChild(el(document, 'strong', null, item.title));
      row.appendChild(el(document, 'span', null, ' · ' + item.kind + ' · ' + item.state));
      if (isHttpsUrl(item.official_url)) row.appendChild(makeLink(document, item.official_url, 'Abrir documento oficial'));
      (item.versions || []).forEach(function (version) {
        row.appendChild(el(document, 'p', 'documents__muted',
          'Versão ' + version.id + ' · Extração: ' + version.extraction_state));
      });
      (item.download_attempts || []).filter(function (attempt) { return attempt.state === 'falhou'; })
        .forEach(function () { row.appendChild(el(document, 'p', 'documents__error', 'Falha em tentativa de download.')); });
      section.appendChild(row);
    });
    (details.proposals || []).forEach(function (proposal) {
      if (!proposal.evidence || !proposal.evidence.quote || !proposal.evidence.version_id) return;
      section.appendChild(el(document, 'p', 'documents__proposal',
        proposal.field_name + ': ' + proposal.value + ' · ' + proposal.state +
         ' · Versão ' + proposal.evidence.version_id + ' · “' + proposal.evidence.quote + '”'));
    });
    (details.current_values || []).forEach(function (selection) {
      if (!selection.evidence || !selection.evidence.quote) return;
      section.appendChild(el(document, 'p', selection.active ? 'documents__status' : 'documents__muted',
        (selection.active ? 'Valor vigente' : 'Seleção histórica') + ': ' + selection.field_name +
        ' · Versão ' + selection.evidence.version_id + ' · “' + selection.evidence.quote + '”'));
    });
    return section;
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
        card.appendChild(el(document, 'p', 'documents__muted', 'Histórico documental ainda não sincronizado.'));
        return;
      }
      var button = el(document, 'button', 'button', 'Ver histórico documental');
      button.setAttribute('type', 'button');
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
          }).catch(function (err) {
            panel.textContent = 'Histórico documental indisponível. Tente novamente.';
            showError(err);
          }).finally(function () { button.disabled = false; });
      });
      card.appendChild(button);
      card.appendChild(panel);
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
              doc.getElementById('competition-list').children[index].appendChild(
                el(doc, 'p', 'documents__error', 'Histórico documental indisponível. A lista do artigo continua visível.'));
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
    var retry = doc.getElementById('retry-button');
    if (retry) retry.addEventListener('click', fetchData);
    fetchData();
  }

  var Radar = {
    UNKNOWN: UNKNOWN,
    isMissing: isMissing,
    formatCount: formatCount,
    formatText: formatText,
    formatDate: formatDate,
    formatVerifiedAt: formatVerifiedAt,
    isHttpsUrl: isHttpsUrl,
    renderRecordCard: renderRecordCard,
    renderDocumentDetails: renderDocumentDetails,
    matchIdentity: matchIdentity,
    renderList: renderList,
    setState: setState,
    fetchData: fetchData,
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
