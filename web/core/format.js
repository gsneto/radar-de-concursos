/* Formatação determinística de números, datas e rótulos (pt-BR). */
(function (global) {
  'use strict';

  var UNKNOWN = 'Não informado';

  function isMissing(value) {
    return value === null || value === undefined || value === '';
  }

  function number(value, options) {
    if (isMissing(value)) return UNKNOWN;
    var parsed = typeof value === 'number' ? value : Number(value);
    if (!isFinite(parsed)) return UNKNOWN;
    return parsed.toLocaleString('pt-BR', options || {});
  }

  function integer(value) {
    return number(value, {maximumFractionDigits: 0});
  }

  function percent(value, digits) {
    if (isMissing(value)) return UNKNOWN;
    var parsed = typeof value === 'number' ? value : Number(value);
    if (!isFinite(parsed)) return UNKNOWN;
    return parsed.toLocaleString('pt-BR', {
      minimumFractionDigits: digits === undefined ? 1 : digits,
      maximumFractionDigits: digits === undefined ? 1 : digits
    }) + '%';
  }

  function date(value, options) {
    if (isMissing(value)) return UNKNOWN;
    var parsed = new Date(value);
    if (isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleDateString('pt-BR', options || {day: '2-digit', month: 'short', year: 'numeric'});
  }

  function shortDate(value) {
    if (isMissing(value)) return '—';
    var parsed = new Date(value);
    if (isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'});
  }

  function dateTime(value) {
    if (isMissing(value)) return UNKNOWN;
    var parsed = new Date(value);
    if (isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }

  function longToday(now) {
    var parsed = now ? new Date(now) : new Date();
    if (isNaN(parsed.getTime())) parsed = new Date();
    return parsed.toLocaleDateString('pt-BR', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    });
  }

  function duration(seconds) {
    if (isMissing(seconds)) return UNKNOWN;
    var total = Math.max(0, Math.round(Number(seconds) || 0));
    var hours = Math.floor(total / 3600);
    var minutes = Math.floor((total % 3600) / 60);
    if (hours > 0) return hours + 'h ' + String(minutes).padStart(2, '0') + 'min';
    if (minutes > 0) return minutes + 'min';
    if (total > 0) return total + 's';
    return '0 min';
  }

  function clock(seconds) {
    var total = Math.max(0, Math.round(Number(seconds) || 0));
    var hours = Math.floor(total / 3600);
    var minutes = Math.floor((total % 3600) / 60);
    var rest = total % 60;
    return String(hours).padStart(2, '0') + ':' + String(minutes).padStart(2, '0') + ':' +
      String(rest).padStart(2, '0');
  }

  function days(value) {
    if (isMissing(value)) return null;
    var parsed = typeof value === 'number' ? value : Number(value);
    return isFinite(parsed) ? parsed : null;
  }

  function relativeDays(value) {
    var parsed = days(value);
    if (parsed === null) return 'Sem data';
    if (parsed === 0) return 'Hoje';
    if (parsed === 1) return 'Amanhã';
    if (parsed > 1) return 'Em ' + parsed + ' dias';
    return 'Há ' + Math.abs(parsed) + ' dias';
  }

  function truncate(value, limit) {
    var text = isMissing(value) ? '' : String(value);
    var max = limit || 160;
    if (text.length <= max) return text;
    return text.slice(0, max - 1).trimEnd() + '…';
  }

  function titleCase(value) {
    if (isMissing(value)) return '';
    return String(value).replace(/\s+/g, ' ').trim();
  }

  function safeUrl(value) {
    if (isMissing(value)) return null;
    try {
      var parsed = new URL(String(value), global.location ? global.location.href : 'http://127.0.0.1');
      if (parsed.protocol === 'https:' || parsed.protocol === 'http:') return parsed.href;
      return null;
    } catch (error) {
      return null;
    }
  }

  function plural(value, singular, pluralWord) {
    var count = Number(value) || 0;
    return count === 1 ? singular : (pluralWord || singular + 's');
  }

  function percentOf(part, total) {
    if (!total) return null;
    return Math.round((Number(part) / Number(total)) * 1000) / 10;
  }

  global.RadarFormat = {
    UNKNOWN: UNKNOWN,
    isMissing: isMissing,
    number: number,
    integer: integer,
    percent: percent,
    date: date,
    shortDate: shortDate,
    dateTime: dateTime,
    longToday: longToday,
    duration: duration,
    clock: clock,
    days: days,
    relativeDays: relativeDays,
    truncate: truncate,
    titleCase: titleCase,
    safeUrl: safeUrl,
    plural: plural,
    percentOf: percentOf
  };
})(typeof window !== 'undefined' ? window : globalThis);
