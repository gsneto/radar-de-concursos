/* Preferências locais da interface (nunca simulam sincronização com o servidor). */
(function (global) {
  'use strict';

  var KEY = 'radar.ui.v1';
  var memory = null;

  function storage() {
    try {
      return global.localStorage || null;
    } catch (error) {
      return null;
    }
  }

  function readAll() {
    if (memory) return memory;
    var raw = null;
    try {
      raw = storage() ? storage().getItem(KEY) : null;
    } catch (error) {
      raw = null;
    }
    if (!raw) {
      memory = {};
      return memory;
    }
    try {
      var parsed = JSON.parse(raw);
      memory = parsed && typeof parsed === 'object' ? parsed : {};
    } catch (error) {
      memory = {};
    }
    return memory;
  }

  function writeAll(value) {
    memory = value;
    try {
      if (storage()) storage().setItem(KEY, JSON.stringify(value));
    } catch (error) {
      /* modo privado/quota: a preferência vale só nesta sessão */
    }
  }

  function get(name, fallback) {
    var all = readAll();
    return Object.prototype.hasOwnProperty.call(all, name) ? all[name] : fallback;
  }

  function set(name, value) {
    var all = readAll();
    all[name] = value;
    writeAll(all);
    return value;
  }

  function remove(name) {
    var all = readAll();
    delete all[name];
    writeAll(all);
  }

  function session(name, value) {
    try {
      if (value === undefined) {
        var raw = global.sessionStorage ? global.sessionStorage.getItem(name) : null;
        return raw ? JSON.parse(raw) : null;
      }
      if (global.sessionStorage) {
        global.sessionStorage.setItem(name, JSON.stringify(value));
      }
      return value;
    } catch (error) {
      return null;
    }
  }

  global.RadarStore = {
    get: get,
    set: set,
    remove: remove,
    session: session
  };
})(typeof window !== 'undefined' ? window : globalThis);
