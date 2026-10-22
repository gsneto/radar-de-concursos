/* Gráficos SVG acessíveis, sem biblioteca externa. */
(function (global) {
  'use strict';

  var Dom = global.RadarDom;
  var Fmt = global.RadarFormat;

  function niceMax(value) {
    var max = Math.max(1, Number(value) || 0);
    var magnitude = Math.pow(10, Math.floor(Math.log10(max)));
    var normalized = max / magnitude;
    var step;
    if (normalized <= 1) step = 1;
    else if (normalized <= 2) step = 2;
    else if (normalized <= 5) step = 5;
    else step = 10;
    return step * magnitude;
  }

  function columnChart(doc, options) {
    var opts = options || {};
    var data = (opts.data || []).filter(function (item) {
      return item && isFinite(Number(item.value));
    });
    var width = opts.width || 680;
    var height = opts.height || 220;
    var pad = {top: 14, right: 10, bottom: 30, left: 38};
    var plotW = width - pad.left - pad.right;
    var plotH = height - pad.top - pad.bottom;
    var max = niceMax(Math.max.apply(null, data.map(function (item) {
      return Number(item.value) || 0;
    }).concat([1])));

    var svg = Dom.svgEl(doc, 'svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'chart',
      role: 'img',
      'aria-labelledby': (opts.id || 'chart') + '-title ' + (opts.id || 'chart') + '-desc',
      preserveAspectRatio: 'none',
      focusable: 'false'
    });
    var title = Dom.svgEl(doc, 'title', {id: (opts.id || 'chart') + '-title'});
    title.textContent = opts.title || 'Gráfico';
    svg.appendChild(title);
    var desc = Dom.svgEl(doc, 'desc', {id: (opts.id || 'chart') + '-desc'});
    desc.textContent = opts.description || '';
    svg.appendChild(desc);

    for (var g = 0; g <= 4; g += 1) {
      var y = pad.top + (plotH / 4) * g;
      svg.appendChild(Dom.svgEl(doc, 'line', {
        x1: pad.left, y1: y, x2: width - pad.right, y2: y, class: 'chart__grid'
      }));
      var tick = Dom.svgEl(doc, 'text', {
        x: pad.left - 7, y: y + 3, 'text-anchor': 'end'
      });
      tick.textContent = Fmt.integer(Math.round(max - (max / 4) * g));
      svg.appendChild(tick);
    }

    if (!data.length) {
      var empty = Dom.svgEl(doc, 'text', {
        x: pad.left + plotW / 2, y: pad.top + plotH / 2, 'text-anchor': 'middle'
      });
      empty.textContent = opts.emptyLabel || 'Sem dados no período';
      svg.appendChild(empty);
      return svg;
    }

    var slot = plotW / data.length;
    var barW = Math.max(4, Math.min(34, slot * 0.58));
    var labelEvery = Math.ceil(data.length / 7);
    data.forEach(function (item, index) {
      var value = Number(item.value) || 0;
      var barH = max ? (value / max) * plotH : 0;
      var x = pad.left + slot * index + (slot - barW) / 2;
      var y = pad.top + plotH - barH;
      var rect = Dom.svgEl(doc, 'rect', {
        x: x, y: y, width: barW, height: Math.max(value > 0 ? 2 : 0, barH),
        rx: 3, fill: item.color || opts.color || 'var(--chart-1)'
      });
      var tip = Dom.svgEl(doc, 'title');
      tip.textContent = item.title || (item.label + ': ' + Fmt.integer(value));
      rect.appendChild(tip);
      svg.appendChild(rect);
      if (value > 0 && slot > 26) {
        var valueText = Dom.svgEl(doc, 'text', {
          x: x + barW / 2, y: y - 5, 'text-anchor': 'middle', class: 'chart__value'
        });
        valueText.textContent = Fmt.integer(value);
        svg.appendChild(valueText);
      }
      if (index % labelEvery === 0 || index === data.length - 1) {
        var label = Dom.svgEl(doc, 'text', {
          x: pad.left + slot * index + slot / 2,
          y: height - 8,
          'text-anchor': 'middle'
        });
        label.textContent = item.label;
        svg.appendChild(label);
      }
    });

    svg.appendChild(Dom.svgEl(doc, 'line', {
      x1: pad.left, y1: pad.top + plotH, x2: width - pad.right, y2: pad.top + plotH,
      class: 'chart__axis'
    }));
    return svg;
  }

  function barRows(doc, options) {
    var opts = options || {};
    var data = opts.data || [];
    var max = Math.max.apply(null, data.map(function (item) {
      return Number(item.value) || 0;
    }).concat([1]));
    var list = Dom.el(doc, 'ul', 'bar-list');
    if (opts.ariaLabel) list.setAttribute('aria-label', opts.ariaLabel);
    data.forEach(function (item) {
      var value = Number(item.value) || 0;
      var row = Dom.el(doc, 'li', 'bar-row');
      row.appendChild(Dom.el(doc, 'span', 'bar-row__label', item.label));
      var track = Dom.el(doc, 'span', 'bar-row__track');
      var fill = Dom.el(doc, 'span', 'bar-row__fill');
      fill.style.width = (max ? (value / max) * 100 : 0) + '%';
      if (item.color) fill.style.background = item.color;
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(Dom.el(doc, 'span', 'bar-row__value',
        item.display === undefined ? Fmt.integer(value) : item.display));
      if (item.title) row.title = item.title;
      list.appendChild(row);
    });
    return list;
  }

  function sparkline(doc, options) {
    var opts = options || {};
    var data = (opts.data || []).map(Number).filter(function (value) { return isFinite(value); });
    var width = opts.width || 120;
    var height = opts.height || 34;
    var svg = Dom.svgEl(doc, 'svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      class: 'chart',
      role: 'img',
      'aria-label': opts.label || 'Série',
      focusable: 'false'
    });
    if (data.length < 2) return svg;
    var max = Math.max.apply(null, data);
    var min = Math.min.apply(null, data);
    var span = max - min || 1;
    var points = data.map(function (value, index) {
      var x = (index / (data.length - 1)) * width;
      var y = height - 2 - ((value - min) / span) * (height - 4);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    svg.appendChild(Dom.svgEl(doc, 'polyline', {
      points: points,
      fill: 'none',
      stroke: opts.color || 'var(--chart-1)',
      'stroke-width': '2',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round'
    }));
    return svg;
  }

  global.RadarCharts = {
    columnChart: columnChart,
    barRows: barRows,
    sparkline: sparkline
  };
})(typeof window !== 'undefined' ? window : globalThis);
