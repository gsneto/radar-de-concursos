# Prova real — fechamento do backend (Fase 44)

Data: 2026-10-19. Base: `b2fddc2`, branch `radar-configuracao`, schema v21. Backup:
`data/radar.sqlite3.bak-20261019-072446`.

## Estado inicial e final

| Item | Inicial | Final |
|---|---|---|
| Testes | 1.877 OK (1 ignorado) | **1.906 OK (1 ignorado)** |
| Documentos | 1.276 | 1.276 |
| Versões | 1.110 | 1.110 |
| Blocos | 17.515 | 17.515 |
| Propostas/evidências | 9.340 / 9.340 | 9.340 / 9.340 |
| Revisões / valores / reconciliações / lotes | 0 | **0** |
| Integridade / FK | ok / 0 | **ok / 0** |
| Schema | 21 | **21 (sem migração)** |
| Fontes habilitadas | 5 na config, 0 na API | **5 na config e na API** |

O banco cresceu entre a referência da Fase 43 (1.232 documentos, 1.072 versões, 9.211
propostas) e o início desta fase por causa do ciclo agendado. Nenhum número foi
presumido; o snapshot foi lido do banco real.

## Contrato de API

```
python -m radar api-contrato --verificar
{"ok": true, "rotas_no_servidor": 129, "rotas_no_contrato": 129,
 "faltando_no_contrato": [], "sobrando_no_contrato": []}
```

- 129 entradas método+rota, 112 caminhos, 24 domínios.
- `GET /api/concursos` v1 preservado (18 campos; `test_contract.py`).
- Rotas declaradas por sufixo verificadas por marcador no código-fonte.
- Documentação gerada: `docs/API.md`.

## Prontidão

```
python -m radar prontidao --db .\data\radar.sqlite3
status: pronto_com_pendencias
ready: true
```

Checks aprovados: schema, integridade, FK, proveniência, evidência literal, hash
documental, conflitos, catálogo de fontes, estudos e contrato de API.
Pendências: 2 credenciais externas, último ciclo `parcial`, 166 documentos sem versão,
1.104 extrações parciais históricas, 5 versões sem texto, 60 conflitos documentais.
Nenhuma pendência é bloqueante; nenhuma delas impede o frontend.

## Segurança

| Cenário | Resultado |
|---|---|
| `POST` com `Origin: https://evil.example` | 403, nada gravado |
| `POST` com `Origin: null` | 403 |
| `POST` com `Host: evil.example` (GET e POST) | 403 |
| `POST` sem `Origin` com `Content-Type: text/plain` | 415 |
| `POST` com `Origin` loopback na mesma porta | 200 |
| `PUT`/`PATCH` | 405 |
| `GET /api/saude/prontidao` | caminho absoluto redigido; cache 60 s |
| 3+ GETs pesados simultâneos | excedente recebe 429 |
| Path traversal | 404; resolução contra `WEB_DIR` |
| SQL nas consultas novas | parametrizado ou literal interno |

Revisão independente de segurança: 0 crítico, 0 alto, 2 médios corrigidos (Host/DNS
rebinding e concorrência de GETs pesados), 2 baixos documentados.

## Estados de extração

| Cenário | Estado |
|---|---|
| HTML/PDF pequeno extraído integralmente | `concluida` |
| PDF de 3 páginas lido com `prefix_pages=1` | `parcial` |
| OCR derivado | `parcial` |
| Lote final de páginas (`partial=False`) | `concluida` |
| Versão sem blocos | `falhou` (ou erro antes do UPDATE) |
| Nota JSON não-objeto | não quebra; tratada como não parcial |

## Estudos — fluxo ponta a ponta (cópia isolada)

| Passo | Resultado |
|---|---|
| Criar disciplina/tópico | 200 |
| Iniciar sessão | 200, `em_andamento` |
| Pausar/retomar | 200 |
| Concluir | 200, `concluida` |
| Concluir de novo com o mesmo id | 200, mesma sessão (idempotente) |
| Criar/revisar flashcard | 200; SM-2-lite avança intervalo |
| Criar questão/tentativa | 200; correção no servidor |
| Criar simulado | 200; 1 questão aplicada |
| Responder/marcar/posicionar | 200 |
| Finalizar duas vezes | 200; tentativas gravadas uma vez |
| Resultado | 200; 1 acerto, 0 brancos |
| Desempenho | 100% sobre 1 respondida |
| Exportar/importar dry-run | 200; 12 itens existentes ignorados |

## Desempenho medido

Metodologia: servidor local + `urllib`, base real de 67 MB, uma chamada fria e uma quente;
escritas em cópia isolada. Antes/depois:

| Operação | Antes | Depois |
|---|---|---|
| `GET /api/carteira?limit=50` | 4,07 s / 4,20 s | **1,09 s / 0,016 s** |
| `GET /api/quadro-vagas` | 2,83 s | **2,88 s / 0,009 s** |
| `GET /api/saude/prontidao` | 0,63–0,78 s | **0,64 s / cache 60 s** |
| `GET /api/revisao/grupos?contexto=1` | 5,28 s / 1,03 s | 5,25 s / 1,03 s |
| `GET /api/concursos` | 0,10 s / 0,003 s | inalterado |
| Sessão de estudo | 0,008 s / 0,007 s | inalterado |

Causas corrigidas: varredura O(n×m) em `decisive_fields`, quatro páginas de oportunidades
e reparse de PDF no quadro. Nenhum índice novo; nenhum serviço externo.

## Revisão independente — achados e correções

| Achado | Severidade | Correção |
|---|---|---|
| `verify()` comparava só caminho, não método; contrato listava `GET /api/concursos/{id}` inexistente e omitia `GET /api/revisao/proposta/{id}` | Alto | Comparação por `(método, rota)`; rotas removidas/adicionadas; teste que altera um branch e exige falha |
| `readiness` ignorava `config` e reportava 0 fontes habilitadas | Alto | `budget.state_report(config=config)` e passagem de `config_path` |
| `readiness` quebrava em banco vazio/schema pendente; HTTP fechava conexão | Alto | Retorno `bloqueado` antes das consultas; `try/except` no handler → 503 JSON |
| Cache da carteira usava data UTC, não local | Alto | Chave por hora local; `referencia`/`generated_at` recalculados na saída |
| `ready` verdadeiro com check não bloqueante reprovado | Médio | Qualquer `reprovado` → `bloqueado`; estudos bloqueante; evidência vazia vira pendência |
| Ciclo `parcial`/`falhou` aparecia como aprovado | Médio | Aprova só `concluido`; demais viram pendência |
| Endpoints novos ignoravam `server.config_path` | Médio | `load_config(self.server.config_path)` |
| Lote final nunca virava `concluida` | Médio | `partial=False` no último lote + `mark_extraction_complete` |
| `_note_is_partial` quebrava com JSON escalar/lista | Baixo | `isinstance(meta, dict)` |
| `server_routes` deixava arquivo aberto | Baixo | `with io.open(...)` |
| Linha morta no cálculo de `next_run` | Baixo | Removida |
| Sem validação de `Host` (DNS rebinding) | Médio (segurança) | `_host_allowed()` em GET/POST/DELETE |
| GETs pesados sem limite de concorrência | Médio (segurança) | Semáforo de 2 + 429; cache de prontidão e single-flight |

## Banco e recuperação

- Backup por API antes de qualquer alteração: `radar.sqlite3.bak-20261019-072446`.
- Nenhuma migração; nenhuma linha apagada; nenhuma decisão humana criada.
- `integrity_check` = `ok`; `foreign_key_check` = 0.
- Tarefa agendada `Radar de Concursos - Ciclo` permanece `Ready`; não foi alterada.
- Ciclo `em_andamento` é marcado `interrompido` na execução seguinte; falha de fonte é
  isolada; retomada de páginas e reprocessamento são idempotentes.

## Conclusão

**BACKEND PRONTO PARA INÍCIO DO FRONTEND.** Os únicos itens não concluídos são externos
(credenciais/termos de 2 fontes) ou não bloqueantes (pendências documentais históricas,
conflitos aguardando decisão humana, itens P2). O backend expõe contratos verificáveis,
estados explícitos e recuperação para todos eles.
