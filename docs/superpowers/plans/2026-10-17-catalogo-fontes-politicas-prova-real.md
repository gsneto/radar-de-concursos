# Prova real — Fase 29: catálogo de fontes, políticas e aquisição

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v18).

## Suíte de testes

- Baseline (antes da fase): **1255 testes, OK**.
- Final: **1333 testes, OK** (+78): `test_sources.py` (51), ajuste IBFC e revisões (+27).

## Estado da base

| Momento | Schema | Concursos | Documentos | Versões | Propostas | Revisões | Valores |
|---|---|---|---|---|---|---|---|
| Início | v16 | 635 | 789 | 789 | 3608 | 0 | 0 |
| Após v17/v18 | **v18** | 635 | 789 | 789 | 3608 | 0 | 0 |

Migração v17 (eventos) e v18 (catálogo/consumo) com **delta zero** nas tabelas históricas.
`integrity_check = ok`, `foreign_key_check = []`, segunda execução idempotente.

## Catálogo

| Item | Valor |
|---|---|
| Fontes catalogadas | **18** |
| Habilitadas | 7 |
| Aguardando validação de uso | 4 |
| Bloqueadas | 4 |
| Aguardando credencial | 1 |
| Não implementadas | 2 |
| Erros de validação do catálogo | **0** |
| Revisão de política vencida | 0 |

Distribuição: 12 concursos, 3 auxiliares, 3 educacionais.

## Persistência por tipo (amostra verificada)

| Fonte | metadados | documento | notícia | questão |
|---|---|---|---|---|
| guajara | permitida | permitida | não verificada | — |
| dou-secao-3 | permitida | permitida | — | — |
| ibfc | permitida | permitida (com decisão registrada) | — | — |
| pci | permitida | não declarado | não verificada | — |
| jcconcursos | não verificada | — | **uso transitório** | — |
| ibge-localidades | permitida | — | — | — |
| quest-api | — | — | — | bloqueada |
| qconcursos | — | — | — | bloqueada |

Testes provam que: permissão sem evidência é recusada pelo validador; `persistencia_nao_verificada`
não grava; `uso_transitorio` não é persistido nem logado; fonte `desativada` bloqueia mesmo com
permissão; mutar o retorno do catálogo não altera a política.

## Integração real (IBGE)

```
GET https://servicodados.ibge.gov.br/api/v1/localidades/municipios -> 200, JSON
snapshot: 5.570 municípios, 27 UFs, atualizado_em 2026-10-17T21:26:27Z
```

Validação de 43 propostas de local (somente leitura):

| Status | Quantidade |
|---|---|
| `confere_ibge` | 41 |
| `lista_ou_texto_livre` | 17 (não é município único) |
| `nao_encontrado` | **2** |

Os 2 achados são `Taboão/SP` e `Taboão` (concurso `89169a73…`): **Taboão não é município** — o
correto é Taboão da Serra. O parecer vai para revisão humana; nenhuma proposta foi alterada
(`propostas_campo`, `revisoes_campo` e `valores_atuais` intactos, provado em teste).

## Orçamento e consumo

- Limites por execução gravados em `fontes_consumo.limits_json` e impostos por `UPDATE`
  condicional: tentar exceder levanta `limite_excedido` e **nada é gravado**.
- Custo pago exige `cost.verified` e `cost.authorized`; sem isso → `custo_nao_verificado`.
- Falha não cobra créditos nem valor.
- Intervalo mínimo entre execuções respeitado (`intervalo_minimo`).
- Janela mensal consultada por `SUM(calls)` do mês.
- `fontes_estado` é preenchido por `open_run`/`finish_run` (chamadas, status da última execução,
  erro), sem segredos.

## API e CLI

```
GET /api/fontes                -> 18 fontes + catálogo + revisão vencida
GET /api/fontes/ibge-localidades -> fonte + conector + política + revisões
GET /api/fontes/jcconcursos    -> 200 com connector=null (catalogada, não implementada)
GET /api/fontes-consumo?limit=5
```

CLI: `fontes [--validar]`, `fontes-consumo`, `fontes-revisar`, `fontes-politica`,
`localidades [--validar] [--force]`. Contrato v1 com 18 campos preservado.

## Revisão independente

**0 críticos, 8 importantes, menores.** Todos os importantes corrigidos com teste:

1. `record_call` não impunha limites e aceitava custo arbitrário → agora é `UPDATE` condicional
   atômico com validação de custo; teste prova que exceder não grava.
2. `fontes_estado` não era preenchido e misturava status → `open_run` garante estado,
   `last_run_status` separado e `last_error` em falha.
3. `desativada` continuava autorizando e havia uma segunda `can_persist` divergente → lista
   positiva de status e delegação única; teste com `desativada`.
4. Gzip bomb e redirect livre no IBGE → limite após descompressão e redirect restrito ao host
   oficial; testes com gzip de 8 MB+ e host malicioso.
5. `GET /api/fontes/<id>` respondia 400 para 8 fontes catalogadas → 200 com `implemented=false`.
6. `discover()` dos conectores estava quebrado (assinatura errada) → despacho por tipo de
   descritor, com erro explícito quando falta configuração.
7. Política não estava no caminho de escrita → gate em `monitoring`: corpo não autorizado é
   descartado e não baixado; metadados permanecem.
8. Permissão com licença "não declarada" → `decision_note` obrigatória e registrada para
   FGV/Quadrix/IBFC/PCI; validador recusa sem ela.

Menores corrigidos: `limits_json` na validação; `run_id` único; falha não cobra créditos;
retry só para erro transitório e falha de persistência auditável; testes de segredo mais fortes;
relatório usa a decisão efetiva (não a permissão bruta); `aria-live` do painel; UF sem snapshot
padronizada; parâmetro `decision` renomeado.

## Limitações honestas

- **Nenhuma fonte nova além do IBGE foi integrada.** As demais foram catalogadas com o motivo
  real: sem licença, robots 403, API 401, conteúdo de terceiro ou código sem licença.
- **Nenhuma conta, assinatura ou pagamento** foi criada. `dados.gov.br` e `quest-api` continuam
  aguardando credencial/contrato.
- O IBGE valida **município/UF**, não a procedência do local no edital: um município correto no
  lugar errado continua exigindo revisão humana.
- A janela mensal usa `started_at`; se o relógio do sistema mudar, o corte acompanha o relógio.
- Conteúdo de agregador já gravado antes da política é **preservado** (histórico); a política
  vale para novas gravações, e o corpo do PCI deixa de ser armazenado a partir de agora.
