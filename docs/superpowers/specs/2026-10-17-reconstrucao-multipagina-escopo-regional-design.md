# Design — Fase 32: reconstrução multipágina e escopo regional

Data: 2026-10-17. Depende de: Fases 27–31 (container, identidade, revisão, fontes, extração,
OCR). Sem migração de esquema.

## Problema real

O quadro de vagas do IBFC 004/2026 ocupa as páginas **21–29** do edital: cabeçalho na p21,
linhas de NTE/município em 21–29 e `TOTAL 2.500` na p29. Tratar cada página como tabela
independente produzia três erros: total perdido, total atribuído à tabela errada e municípios
do último NTE lidos como números de lei no rodapé.

Além disso, o quadro **não tem coluna de cargo**: distribui vagas por NTE (regional
administrativa) e município. Atribuir esses números ao "cargo mais próximo" seria associação
por proximidade, proibida pelo projeto.

## Decisões

1. **Continuidade por evidências combinadas, nunca por adjacência.**
   Sinais e pesos: cabeçalho repetido (+3), numeração de NTE contínua (+3), retomada do NTE em
   curso (+2), página abre no meio da lista de municípios (+2), fecha com `TOTAL` (+2), linhas
   de município sem NTE na página (+1), `TOTAL` encerra (+1), nota de rodapé (+1), abre novo
   anexo (−3), NTE volta/reinicia (−2). Adjacência de página tem peso **0**: proximidade nunca
   comprova continuidade. Limiares: `forte` ≥ 5, `provavel` ≥ 2, `independente` ≤ −2, senão
   `ambigua`; sem cabeçalho nem total, `irreconstruivel`.
2. **O `TOTAL` encerra o quadro; a nota de rodapé não é cabeçalho.** `TOTAL DE VAGAS` no
   cabeçalho e `( * ) Total de vagas incluindo...` no rodapé não podem ser confundidos com o
   total numérico nem com um novo quadro.
3. **Rótulo de NTE é variável.** O documento usa `NTE 01 - SEDE: ...` e `NÚCLEO 06 - VALENÇA
   34`. Ambos são a mesma estrutura; `SEDE:` é opcional. O sub-cabeçalho repetido do NTE é
   removido por prefixo de palavra da sede (aceita abreviação `F. DE SANTANA` ×
   `FEIRA DE SANTANA`), nunca por quantidade fixa de tokens — senão o primeiro município é
   engolido.
4. **Camadas separadas e com certeza própria.** NTE é regional administrativa; não é
   município, local de prova nem lotação. A camada de NTE fecha com o `TOTAL` publicado; a
   camada de município é **diagnóstica** e só é publicável se cada NTE fechar com seus
   municípios. O nome do indicador é estreito de propósito — `soma_municipios_confere` confere
   a **soma**, não cada linha — e, quando não fecha, a limitação é explícita.
5. **Cargo vem do escopo do edital, com citação.** `função temporária de X`, `cargo de X` e
   `provimento do cargo de X` são padrões fortes; `função de X` é fraco e só é usado quando
   não há forte (evita "função de jurado" em critério de pontuação virar cargo). Um cargo ⇒
   `escopo_edital_unico`; mais de um ⇒ `ambiguo`, sem escolha automática.
6. **Proposta só do total do quadro.** Por padrão, apenas o `TOTAL` do quadro vira
   `vagas_total_publicado`, com motivo "total agregado publicado; não distribuir por
   modalidade" e `role_id` nulo. Os totais de NTE ficam no relatório estrutural; com
   `include_ntes=True` são emitidos como **recorte do NTE** (nunca como total do concurso).
   Proposta só é emitida com certeza `forte`/`provavel` e trecho localizável no bloco real.
   Nenhuma modalidade é derivada; nenhum município vira campo.
7. **PDF longo em lotes idempotentes.** `append_page_analysis` grava apenas páginas ainda não
   extraídas, remapeia índices de bloco e mantém o estado `parcial`. O lote tem limite por
   chamada, devolve `next_page` e grava checkpoint opcional para retomada.
8. **Documento parcial é justificado, não ignorado.** Ato de resultado/homologação/isenção é
   lista nominal: as páginas restantes repetem nome, nota e classificação. Não alimentam campo
   do concurso e o processamento exporia dados pessoais sem ganho. A justificativa fica
   registrada por documento.

## Contratos

- `table_continuity.analyze_tables(blocks)` → tabelas com `header_page`, `total_page`,
  `pages`, `ntes`, `soma_linhas`, `total`, `certeza`, `transitions`, `ambiguidades`.
- `table_continuity.continuity_report_all(db_path, limit=2000)` → só quadros com NTE ou total.
- `regional_scope.scope_report(db_path, version_id)` → cargo do escopo, tabela, NTEs,
  `soma_ntes`, `total_publicado`, `soma_municipios_confere`, limitações.
- `regional_scope.proposals_from_scope(report, label_prefix, include_ntes=False)` → proposta
  do total do quadro (e recortes de NTE só sob pedido explícito).
- `page_batches.partial_inventory(db_path)` / `batch_report` → parciais com decisão.
- `page_batches.page_index(db_path, version_id, pages=None, sample=60)` → índice por página,
  amostrando apenas as não lidas.
- `page_batches.append_pages(..., dry_run=True, max_pages=40, checkpoint=None)` → lote,
  com `next_page` e `dropped_proposals` para propostas de páginas já gravadas.

## Não objetivos

- Não instalar Camelot/tabula: a leitura é textual e determinística; adaptador opcional só se
  a prova real mostrar necessidade.
- Não derivar vagas indígenas nem modalidades do total agregado.
- Não confirmar campo automaticamente: propostas continuam candidatas.
- Não escrever na base real sem caminho de proposta testado.
