# PCI Concursos (MCP) como canal complementar de descoberta — desenho e decisão

Data: 2026-10-16

## Intenção

Adicionar a **PCI Concursos** (via seu servidor MCP público) como **canal
complementar de descoberta** de concursos que ainda não apareceram nas fontes
oficiais (Guajará-Mirim, DOU Seção 3, FGV). A PCI é um **agregador não oficial**:
os resultados são **descobertas**, não comprovação documental. A confirmação
continua exigindo documento oficial e segue a revisão humana do projeto.

Estados mantidos separados: **descoberto** (a PCI listou), **confirmado
documentalmente** (há edital/evidência) e **elegibilidade analisada**.

## Condições de uso verificadas (2026-10-16)

- Página oficial: `https://www.pciconcursos.com.br/mcp-e-gpt` — "BETA PÚBLICA ·
  ACESSO GRATUITO"; conector "oficial da PCI Concursos" para clientes MCP.
- Endpoint: `https://mcp.pciconcursos.com.br/mcp`.
- Aviso da própria PCI: "pode não cobrir todos os editais abertos... use o
  conector como **complemento** à sua pesquisa, e não como única fonte".
- Não há indicação explícita sobre retenção/redistribuição permanente do acervo.
  **Decisão:** modo mais restrito justificável — armazenar apenas **referências,
  metadados mínimos, URLs de origem e proveniência** (título, UF/região, cargos
  resumidos, vagas/salário anunciado, formação, datas, link da notícia e a consulta
  que originou o registro). Não copiar o acervo em massa nem redistribuir conteúdo.
- Não se faz scraping direto do site para contornar o MCP; não se usa endpoint
  privado; não se contorna controle de acesso. `buscar_apostilas` **não** é usada.

## Protocolo e ferramentas (verificados por conexão real)

- Transporte: **Streamable HTTP**, JSON-RPC 2.0, protocolo `2025-06-18`;
  respostas `application/json` (sem sessão). `initialize` → `tools/list` → `tools/call`.
- Ferramentas: `listar_concursos` `{regiao? enum(norte,nordeste,centro-oeste,sudeste,sul), professores? bool}`;
  `pesquisar_concursos` `{termo req, uf? 2 letras}`; `buscar_por_cargo` `{cargo req, uf?}`;
  `buscar_por_cidade` `{uf req, cidade req}`; `buscar_apostilas` (não usada).
- As ferramentas de concursos filtram por **inscrições abertas** — limite da
  fonte, registrado como tal (não é cobertura de previstos/encerrados).
- Resposta: `result.content[0].text` é uma **string JSON** com `meta`
  (`total`, `data_atual`) e `data[]` de concursos.

## Estratégia de consulta (conjunto versionado)

`PCI_QUERIES_VERSION = 1`, executado em ordem:

1. `listar_concursos {}` — **lista nacional completa** dos abertos (observado: 466).
2. `buscar_por_cargo {"cargo": "analista de sistemas"}` — prioridade TI.
3. `buscar_por_cargo {"cargo": "técnico em informática"}` — prioridade TI.
4. `pesquisar_concursos {"termo": "sistemas de informação"}` — relevância SI.

Regiões (`listar_concursos {regiao}`) são **subconjuntos** da consulta 1 e por isso
não são repetidas. Cada consulta é registrada no resumo do ciclo. Descoberta é
**incremental**: `max_new_concursos` limita novos concursos por ciclo; concursos
conhecidos são ignorados, então o restante entra nos ciclos seguintes.

## Arquitetura (`radar/pci_source.py`)

Cliente MCP mínimo (stdlib, sem dependências novas):

- `McpClient` — `initialize`, `list_tools`, `call(name, args)` (JSON-RPC via urllib;
  aceita `application/json` e `text/event-stream`).
- `parse_tool_result(payload)` — devolve `(is_error, obj, text, reason)`, com
  `reason` distinguindo `rpc_error` (erro JSON-RPC), `tool_error` (isError da
  ferramenta), `unreadable` (texto não interpretável) ou `None` (sucesso).
- `normalize(item, query_label, discovered_at)` — candidato de descoberta com
  metadados mínimos.
- `discover(db_path, *, caller, queries, max_new_concursos, now)` — executa as
  consultas, deduplica por **identidade estável** (`competition_id = "pci-<id>"`,
  independente do slug mutável da notícia), garante a observação por concurso
  (`source_url = notícia`), registra um **documento de descoberta** (kind `outro`,
  conteúdo embutido com os metadados) e devolve
  `{candidates, summary, partial, failed}`.
- `pci_source(...)` — descritor para o monitoramento (`multi_contest`,
  `download_new_only`); o `fetch` faz `initialize` + `tools/list`.

Reutiliza `ensure_observation` e `register_document` (sem banco paralelo). O
documento de descoberta tem `issuer = "PCI Concursos (agregador)"` e kind `outro`
— distinguível de um edital confirmado (kind `edital`). Nenhuma proposta é
extraída desses metadados; nada é confirmado automaticamente.

## Integração com o monitoramento

`monitoring._run_source` ganha suporte a fonte multi-concurso cujo `discover`
devolve um **dict** `{candidates, summary, partial}` (FGV continua devolvendo uma
lista — compatível). O `summary` extra (consultas, chamadas, resultados, erros,
sobreposição) é persistido em `ciclos_fontes.summary_json`; `partial=True` rebaixa
o estado da fonte para `parcial`. Falha total de conexão → `falhou`; resposta vazia
válida **não** é falha.

## Deduplicação multifonte

- **Dentro da PCI:** idempotente por `UNIQUE(observation_id, official_url)`.
- **Entre fontes:** associação a um concurso de outra fonte é **candidata a
  revisão** (não automática). O conector calcula uma pista de sobreposição
  (título normalizado) apenas como **métrica**, sem fundir registros.
- A origem de descoberta do DOU/FGV nunca é sobrescrita.

## Limites e decisões

- A PCI só devolve **inscrições abertas**; não cobre previstos/encerrados.
- Metadados mínimos; sem cópia de acervo; sem apostilas.
- Candidatos permanecem **pendentes de confirmação** oficial (a PCI não fornece o
  URL do edital; fornece o link da notícia).
- Nenhuma tarefa agendada real; nenhuma migração de banco.

## Como manter ou desativar

Manter: revisar `PCI_QUERIES`/`PCI_QUERIES_VERSION` quando a interface mudar.
Desativar: remover `pci_source()` de `monitoring.default_sources()`. Nenhum dado
histórico é apagado ao desativar.
