# Prova real — Fase 25: cobertura, diagnóstico e enriquecimento

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **1004 testes, OK**.
- Final: **1062 testes, OK** (58 novos): `test_data_quality.py` (30), `test_enrichment.py` (20),
  `test_coverage_api.py` (7), `test_ui.py` (+1).

## Cobertura medida no banco real (antes)

Consultas somente leitura em `data/radar.sqlite3` (v14, `integrity_check=ok`).

| Etapa do funil | Quantidade |
|---|---|
| Concursos | 593 |
| Com algum documento | 499 |
| Com edital oficial | 16 |
| Com edital analisado | 16 |
| Com propostas extraídas | 15 |
| Com campo validado por humano | 0 |

Distribuição de causas: **477** `apenas_agregador`, **94** `sem_documento`, **15**
`extraido_ambiguo`, **6** `documento_oficial_sem_edital`, **1** `edital_sem_campos`.

Documentos: 636 no total — 594 `kind='outro'`, 27 `edital`, 15 `retificacao`; ~370 vindos de
`pciconcursos.com.br/noticias/` (agregador). Propostas: 751, **todas** com
`ambiguity_reason`; `revisoes_campo`, `valores_atuais`, `reconciliacoes_cargo` e
`cargos_identidade` vazios.

Métricas por dimensão (denominador = concursos efetivamente avaliados):

| Dimensão | Universo | Denominador | Fora | % confirmado | % com dado |
|---|---|---|---|---|---|
| edital_oficial | 593 | 499 | 94 | 3,2 | 3,2 |
| retificacao (opcional) | 593 | 16 | 577 | não publicado | 50,0 |
| cargos | 593 | 16 | 577 | 0,0 | 81,2 |
| vagas_imediatas | 593 | 16 | 577 | 0,0 | 56,2 |
| vagas_indigenas | 593 | 16 | 577 | 0,0 | 37,5 |
| escolaridade | 593 | 16 | 577 | 0,0 | 56,2 |
| compatibilidade_si | 593 | 16 | 577 | 0,0 | 56,2 |
| local_prova | 593 | 16 | 577 | 0,0 | **0,0** |
| prazo_inscricao | 593 | 16 | 577 | 0,0 | 75,0 |
| conteudo_programatico | 593 | 16 | 577 | não publicado | **0,0** |
| prazo_pagamento | 593 | 0 | 593 | — | não mapeado |

Leitura honesta: o gargalo dominante é **fonte** (577 concursos sem edital oficial), não parser.
Depois dele, o gargalo é **confirmação** (0 validações, 100% de ambiguidade). `local_prova` e
`conteudo_programatico` são **0% mesmo entre os 16 com edital** — lacuna de extração real, não
"não aplicável".

## Enriquecimento aplicado

`materialize_document_roles` criou identidades de cargo a partir do rótulo literal evidenciado:

| Momento | `cargos_identidade` | rótulos evidenciados | propostas elegíveis a reconciliação |
|---|---|---|---|
| antes | 0 | 125 | 481 |
| depois | 125 | 125 | 481 |

Idempotente: segunda execução criou 0. Nada mais mudou — propostas 751, documentos 636,
evidências 751, revisões 0, valores atuais 0, `integrity_check=ok`, `foreign_key_check` vazio.

O que **não** foi feito, por regra de domínio: nenhuma proposta foi reatribuída, nenhuma
ambiguidade resolvida, nada validado. O ganho é tornar o caminho humano possível — antes
`reconcile_role_label` não tinha `role_id` para receber decisão.

## Incidente durante a execução (registrado)

Ao testar o CLI, o arquivo de configuração temporário não foi criado e o comando
`cobertura-papeis --apply` caiu na base habitual. Ele criou **226** identidades, incluindo 8
rótulos contaminados (`... — requisitos presentes...`, `escolaridade declarada (...)`).

Tratamento:
1. backup consistente imediato: `data/radar.sqlite3.bak-20261017-120840`;
2. verificação de que apenas `cargos_identidade` mudou (nenhuma FK apontava para as linhas);
3. correção do `clean_label` e criação de testes para o caso;
4. remoção das 226 linhas com verificação prévia de referências (0 referências);
5. reaplicação limpa: 125 identidades, 0 nomes suspeitos.

Lição registrada: `--apply` deve exigir confirmação explícita de destino; o padrão `dry_run`
não protege contra configuração ausente.

## Validação funcional (CLI e API)

```
cobertura: escopo 593/499/16/16/15; causas 477+94+15+6+1 = 593
lacunas: 593 itens; topo = concursos com edital analisado e propostas ambíguas (prioridade 11)
cobertura-papeis (dry-run): 125 rótulos, 481 propostas, 0 gravadas
cobertura-papeis --apply: 125 identidades; 2ª execução: 0
resumo: rotulos 125, com_identidade 125, com_decisao_humana 0
GET /api/cobertura 200 · /api/cobertura/resumo 200 · /api/lacunas?limit=5 200
POST /api/cobertura/papeis {"dry_run": true} 200 · entradas inválidas 400
GET /api/concursos: contrato de 18 campos inalterado (test_contract.py + teste novo)
```

## Limitações

- Percentual de campo só existe onde houve edital analisado; 577 concursos aparecem em
  `fora_do_denominador`, nunca como zero.
- `prazo_pagamento` não existe no modelo: reportado como `nao_mapeado`.
- A causa é a melhor explicação com os dados atuais; sem prova fica `inconclusivo`.
- Não foram integradas novas bancas (Cebraspe, IBFC, AOCP, FCC): a lacuna dominante é associação
  e existência de edital, e adicionar scrapers antes disso aumentaria volume sem confirmação.
  A métrica que justificaria a expansão está registrada na pesquisa da fase.
