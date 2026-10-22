/* Componentes visuais reutilizáveis (estados, cartões, badges, progresso). */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;

  function badge(doc, text, tone) {
    var node = Dom.el(doc, 'span', 'badge badge--' + (tone || 'neutral'), text);
    return node;
  }

  function dotBadge(doc, text, tone) {
    var node = badge(doc, text, tone);
    var dot = Dom.el(doc, 'span', 'badge__dot');
    node.insertBefore(dot, node.firstChild);
    return node;
  }

  function card(doc, options) {
    var opts = options || {};
    var node = Dom.el(doc, 'section', 'card' + (opts.className ? ' ' + opts.className : ''));
    if (opts.id) node.id = opts.id;
    if (opts.labelledBy) node.setAttribute('aria-labelledby', opts.labelledBy);
    if (opts.head !== false) {
      var head = Dom.el(doc, 'div', 'card__head');
      var text = Dom.el(doc, 'div');
      var title = Dom.el(doc, 'h3', 'card__title', opts.title || '');
      if (opts.id) title.id = opts.id + '-title';
      text.appendChild(title);
      if (opts.sub) text.appendChild(Dom.el(doc, 'p', 'card__sub', opts.sub));
      head.appendChild(text);
      if (opts.link) {
        var link = Dom.el(doc, 'a', 'card__link', opts.link.label);
        link.href = opts.link.href;
        head.appendChild(link);
      }
      node.appendChild(head);
    }
    var body = Dom.el(doc, 'div', 'card__body');
    if (opts.body) body.appendChild(opts.body);
    node.appendChild(body);
    return node;
  }

  function state(doc, options) {
    var opts = options || {};
    var wrap = Dom.el(doc, 'div', 'state state--' + (opts.tone || 'empty'));
    if (opts.role) wrap.setAttribute('role', opts.role);
    var iconBox = Dom.el(doc, 'div', 'state__icon');
    iconBox.appendChild(Dom.icon(doc, opts.icon || 'empty', 22));
    wrap.appendChild(iconBox);
    if (opts.title) wrap.appendChild(Dom.el(doc, 'p', 'state__title', opts.title));
    if (opts.text) wrap.appendChild(Dom.el(doc, 'p', 'state__text', opts.text));
    if (opts.hint) wrap.appendChild(Dom.el(doc, 'p', 'state__hint', opts.hint));
    if (opts.actions && opts.actions.length) {
      var actions = Dom.el(doc, 'div', 'state__actions');
      opts.actions.forEach(function (action) {
        var node;
        if (action.href) {
          node = Dom.el(doc, 'a', 'btn ' + (action.primary ? 'btn--primary' : ''), action.label);
          node.href = action.href;
        } else {
          node = Dom.el(doc, 'button', 'btn ' + (action.primary ? 'btn--primary' : ''), action.label);
          node.type = 'button';
          if (action.onClick) node.addEventListener('click', action.onClick);
        }
        actions.appendChild(node);
      });
      wrap.appendChild(actions);
    }
    return wrap;
  }

  function loadingRows(doc, count) {
    var wrap = Dom.el(doc, 'div', 'skeleton-stack');
    wrap.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < (count || 4); i += 1) {
      wrap.appendChild(Dom.el(doc, 'div', 'skeleton skeleton--row'));
    }
    return wrap;
  }

  function kpi(doc, options) {
    var opts = options || {};
    var node = Dom.el(doc, 'article', 'kpi' + (opts.feature ? ' kpi--feature' : ''));
    var top = Dom.el(doc, 'div', 'kpi__top');
    top.appendChild(Dom.el(doc, 'span', 'kpi__label', opts.label));
    if (opts.icon) {
      var iconBox = Dom.el(doc, 'span', 'kpi__icon');
      iconBox.appendChild(Dom.icon(doc, opts.icon, 15));
      top.appendChild(iconBox);
    }
    node.appendChild(top);
    var value = Dom.el(doc, 'p', 'kpi__value',
      opts.display !== undefined ? opts.display : Fmt.integer(opts.value));
    if (opts.unit) value.appendChild(Dom.el(doc, 'small', '', opts.unit));
    node.appendChild(value);
    if (opts.sub) node.appendChild(Dom.el(doc, 'p', 'kpi__sub', opts.sub));
    if (opts.mini) {
      var mini = Dom.el(doc, 'div', 'kpi__mini');
      mini.appendChild(opts.mini);
      node.appendChild(mini);
    }
    return node;
  }

  function progress(doc, options) {
    var opts = options || {};
    var wrap = Dom.el(doc, 'div', 'progress');
    var head = Dom.el(doc, 'div', 'progress__head');
    head.appendChild(Dom.el(doc, 'span', 'progress__label', opts.label || ''));
    var total = Number(opts.total) || 0;
    var value = Number(opts.value) || 0;
    var pct = total > 0 ? Math.min(100, Math.round((value / total) * 1000) / 10) : null;
    head.appendChild(Dom.el(doc, 'span', 'progress__value',
      pct === null ? '—' : Fmt.percent(pct)));
    wrap.appendChild(head);
    var track = Dom.el(doc, 'div', 'progress__track');
    track.setAttribute('role', 'progressbar');
    track.setAttribute('aria-valuemin', '0');
    track.setAttribute('aria-valuemax', String(total || 100));
    track.setAttribute('aria-valuenow', String(total ? value : 0));
    track.setAttribute('aria-label', opts.label || 'Progresso');
    var fill = Dom.el(doc, 'div', 'progress__fill');
    fill.style.width = (pct === null ? 0 : pct) + '%';
    if (opts.color) fill.style.background = opts.color;
    track.appendChild(fill);
    wrap.appendChild(track);
    if (opts.hint) wrap.appendChild(Dom.el(doc, 'p', 'state__hint', opts.hint));
    return wrap;
  }

  function stacked(doc, segments) {
    var bar = Dom.el(doc, 'div', 'stacked');
    bar.setAttribute('role', 'img');
    var summary = segments.map(function (segment) {
      return segment.label + ': ' + Fmt.integer(segment.value);
    }).join('; ');
    bar.setAttribute('aria-label', summary || 'Sem dados');
    segments.forEach(function (segment) {
      if (!segment.value) return;
      var piece = Dom.el(doc, 'span', 'stacked__seg');
      piece.style.width = segment.pct + '%';
      piece.style.background = segment.color;
      piece.title = segment.label + ': ' + Fmt.integer(segment.value);
      bar.appendChild(piece);
    });
    return bar;
  }

  function legend(doc, segments) {
    var list = Dom.el(doc, 'ul', 'legend');
    segments.forEach(function (segment) {
      var item = Dom.el(doc, 'li');
      var dot = Dom.el(doc, 'span', 'legend__dot');
      dot.style.background = segment.color;
      item.appendChild(dot);
      item.appendChild(Dom.el(doc, 'span', '', segment.label));
      item.appendChild(Dom.el(doc, 'span', 'legend__value', Fmt.integer(segment.value)));
      list.appendChild(item);
    });
    return list;
  }

  function tableFallback(doc, options) {
    var details = Dom.el(doc, 'details', 'data-table');
    var summary = Dom.el(doc, 'summary', '', options.summary || 'Ver dados em tabela');
    details.appendChild(summary);
    var table = Dom.el(doc, 'table', 'chart-table');
    if (options.caption) {
      var caption = Dom.el(doc, 'caption', '', options.caption);
      table.appendChild(caption);
    }
    var thead = Dom.el(doc, 'thead');
    var headRow = Dom.el(doc, 'tr');
    (options.columns || []).forEach(function (column) {
      headRow.appendChild(Dom.el(doc, 'th', '', column));
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = Dom.el(doc, 'tbody');
    (options.rows || []).forEach(function (row) {
      var tr = Dom.el(doc, 'tr');
      row.forEach(function (cell) {
        tr.appendChild(Dom.el(doc, 'td', '', cell));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    details.appendChild(table);
    return details;
  }

  function inlineError(doc, message) {
    var box = Dom.el(doc, 'div', 'inline-error');
    box.setAttribute('role', 'alert');
    box.appendChild(Dom.icon(doc, 'alert', 15));
    box.appendChild(Dom.el(doc, 'span', '', message));
    return box;
  }

  function metaList(doc, pairs) {
    var dl = Dom.el(doc, 'dl', 'definition');
    pairs.forEach(function (pair) {
      if (!pair) return;
      dl.appendChild(Dom.el(doc, 'dt', '', pair[0]));
      dl.appendChild(Dom.el(doc, 'dd', '', pair[1]));
    });
    return dl;
  }

  function metricTile(doc, label, value, hint) {
    var tile = Dom.el(doc, 'div', 'metric-tile');
    tile.appendChild(Dom.el(doc, 'p', 'metric-tile__label', label));
    tile.appendChild(Dom.el(doc, 'p', 'metric-tile__value', value));
    if (hint) tile.appendChild(Dom.el(doc, 'p', 'metric-tile__hint', hint));
    return tile;
  }

  global.RadarUI = {
    badge: badge,
    dotBadge: dotBadge,
    card: card,
    state: state,
    loadingRows: loadingRows,
    kpi: kpi,
    progress: progress,
    stacked: stacked,
    legend: legend,
    tableFallback: tableFallback,
    inlineError: inlineError,
    metaList: metaList,
    metricTile: metricTile
  };
})(typeof window !== 'undefined' ? window : globalThis);
