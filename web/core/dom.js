/* Utilitários de DOM seguros (sem innerHTML em dados de API). */
(function (global) {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';

  function el(doc, tag, className, text) {
    var node = doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function svgEl(doc, tag, attrs) {
    var node = doc.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  function clear(node) {
    if (!node) return node;
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function append(node) {
    for (var i = 1; i < arguments.length; i += 1) {
      var child = arguments[i];
      if (child === null || child === undefined) continue;
      if (Array.isArray(child)) {
        child.forEach(function (item) { if (item) node.appendChild(item); });
      } else if (typeof child === 'string') {
        node.appendChild(node.ownerDocument.createTextNode(child));
      } else {
        node.appendChild(child);
      }
    }
    return node;
  }

  var ICONS = {
    overview: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
    opportunities: 'M21 21l-4.35-4.35M17 10.5a6.5 6.5 0 11-13 0 6.5 6.5 0 0113 0z',
    calendar: 'M8 2v4M16 2v4M3 9h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z',
    studies: 'M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5V6.5A2.5 2.5 0 016.5 4H20v16H6.5A2.5 2.5 0 004 19.5z',
    plan: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2M9 12h6M9 16h6',
    sessions: 'M12 8v4l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    questions: 'M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3M12 17h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    flashcards: 'M7 8h10M7 12h6M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z',
    exams: 'M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11',
    history: 'M3 3v5h5M3.05 13A9 9 0 1021 12M12 7v5l4 2',
    settings: 'M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 003.68 15a1.65 1.65 0 00-1.51-1H2a2 2 0 110-4h.09A1.65 1.65 0 003.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06A1.65 1.65 0 009 4.6a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06A1.65 1.65 0 0019.4 9c.2.63.78 1.09 1.51 1.09H21a2 2 0 110 4h-.09c-.73 0-1.31.46-1.51 1.09z',
    operation: 'M4 6h16M4 12h16M4 18h10',
    search: 'M21 21l-4.35-4.35M17 10.5a6.5 6.5 0 11-13 0 6.5 6.5 0 0113 0z',
    arrowRight: 'M5 12h14M13 6l6 6-6 6',
    arrowLeft: 'M19 12H5M11 18l-6-6 6-6',
    chevronLeft: 'M15 18l-6-6 6-6',
    chevronRight: 'M9 18l6-6-6-6',
    close: 'M18 6L6 18M6 6l12 12',
    menu: 'M4 6h16M4 12h16M4 18h16',
    external: 'M14 3h7v7M10 14L21 3M21 14v5a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h5',
    doc: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M9 13h6M9 17h6',
    clock: 'M12 8v4l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    target: 'M12 22a10 10 0 100-20 10 10 0 000 20zM12 18a6 6 0 100-12 6 6 0 000 12zM12 14a2 2 0 100-4 2 2 0 000 4z',
    layers: 'M12 2l9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5',
    pin: 'M21 10c0 7-9 12-9 12S3 17 3 10a9 9 0 1118 0zM12 13a3 3 0 100-6 3 3 0 000 6z',
    spark: 'M13 2L3 14h7l-1 8 11-13h-8l1-7z',
    refresh: 'M21 12a9 9 0 11-3-6.7M21 3v6h-6',
    download: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3',
    upload: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12',
    play: 'M8 5v14l11-7z',
    pause: 'M6 4h4v16H6zM14 4h4v16h-4z',
    check: 'M20 6L9 17l-5-5',
    alert: 'M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z',
    empty: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7M4 13h4l2 3h4l2-3h4M4 13v5a2 2 0 002 2h12a2 2 0 002-2v-5',
    book: 'M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5V6.5A2.5 2.5 0 016.5 4H20v16H6.5A2.5 2.5 0 004 19.5z',
    filter: 'M22 3H2l8 9.46V19l4 2v-8.54L22 3z'
  };

  function icon(doc, name, size) {
    var svg = svgEl(doc, 'svg', {
      viewBox: '0 0 24 24',
      width: size || 18,
      height: size || 18,
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '1.8',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      'aria-hidden': 'true',
      focusable: 'false'
    });
    var path = svgEl(doc, 'path', {d: ICONS[name] || ICONS.overview});
    svg.appendChild(path);
    return svg;
  }

  function brandMark(doc, size) {
    var svg = svgEl(doc, 'svg', {
      viewBox: '0 0 32 32',
      width: size || 30,
      height: size || 30,
      'aria-hidden': 'true',
      focusable: 'false'
    });
    svg.appendChild(svgEl(doc, 'circle', {
      cx: '16', cy: '16', r: '10.5', fill: 'none', stroke: '#8f9bff',
      'stroke-width': '1.6', opacity: '0.55'
    }));
    svg.appendChild(svgEl(doc, 'circle', {
      cx: '16', cy: '16', r: '6', fill: 'none', stroke: '#c7ccff',
      'stroke-width': '1.4', opacity: '0.7'
    }));
    svg.appendChild(svgEl(doc, 'path', {
      d: 'M16 16 L26 6.5', stroke: '#2dd4bf', 'stroke-width': '2.2',
      'stroke-linecap': 'round'
    }));
    svg.appendChild(svgEl(doc, 'circle', {cx: '16', cy: '16', r: '2.2', fill: '#eef1ff'}));
    svg.appendChild(svgEl(doc, 'circle', {cx: '26', cy: '6.5', r: '1.7', fill: '#2dd4bf'}));
    return svg;
  }

  global.RadarDom = {
    el: el,
    svgEl: svgEl,
    clear: clear,
    append: append,
    icon: icon,
    brandMark: brandMark
  };
})(typeof window !== 'undefined' ? window : globalThis);
