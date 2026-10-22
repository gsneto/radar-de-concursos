/* Serviço HTTP comum: timeouts, erros previsíveis e proteção contra respostas fora de ordem. */
(function (global) {
  'use strict';

  function ApiError(message, options) {
    this.name = 'ApiError';
    this.message = message;
    this.status = (options || {}).status || 0;
    this.code = (options || {}).code || 'erro_api';
    this.payload = (options || {}).payload || null;
    if (Error.captureStackTrace) Error.captureStackTrace(this, ApiError);
  }
  ApiError.prototype = Object.create(Error.prototype);
  ApiError.prototype.constructor = ApiError;

  function parseBody(response) {
    return response.text().then(function (text) {
      if (!text) return null;
      try {
        return JSON.parse(text);
      } catch (error) {
        throw new ApiError('Resposta inválida do servidor local.', {
          status: response.status, code: 'json_invalido'
        });
      }
    });
  }

  function request(path, options) {
    var config = options || {};
    var timeout = config.timeout === undefined ? 20000 : config.timeout;
    var controller = global.AbortController ? new global.AbortController() : null;
    var timer = null;
    if (controller && timeout > 0) {
      timer = global.setTimeout(function () { controller.abort(); }, timeout);
    }
    var init = {
      method: config.method || 'GET',
      headers: Object.assign({Accept: 'application/json'}, config.headers || {}),
      cache: 'no-store',
      signal: config.signal || (controller ? controller.signal : undefined)
    };
    if (config.body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(config.body);
    }
    var promise = global.fetch(path, init).then(function (response) {
      return parseBody(response).then(function (payload) {
        if (!response.ok) {
          var message = payload && typeof payload.error === 'string'
            ? payload.error
            : 'Falha na consulta (' + response.status + ').';
          throw new ApiError(message, {
            status: response.status,
            code: (payload && payload.code) || 'http_' + response.status,
            payload: payload
          });
        }
        return payload;
      });
    }).catch(function (error) {
      if (error && error.name === 'AbortError') {
        throw new ApiError('A consulta demorou demais para responder.', {code: 'timeout'});
      }
      if (error instanceof ApiError) throw error;
      throw new ApiError('Não foi possível falar com o servidor local.', {code: 'rede'});
    }).finally(function () {
      if (timer) global.clearTimeout(timer);
    });
    return promise;
  }

  function get(path, options) {
    return request(path, Object.assign({method: 'GET'}, options || {}));
  }

  function post(path, body, options) {
    return request(path, Object.assign({method: 'POST', body: body || {}}, options || {}));
  }

  function del(path, options) {
    return request(path, Object.assign({method: 'DELETE'}, options || {}));
  }

  /* Token de requisição: a última chamada vence; respostas antigas são descartadas. */
  function sequencer() {
    var current = 0;
    return {
      next: function () { current += 1; return current; },
      isCurrent: function (token) { return token === current; }
    };
  }

  global.RadarApi = {
    ApiError: ApiError,
    request: request,
    get: get,
    post: post,
    del: del,
    sequencer: sequencer
  };
})(typeof window !== 'undefined' ? window : globalThis);
