# Plano — Fase 32: reconstrução multipágina e escopo regional

Data: 2026-10-17. Base: `ab27a55` (Fase 31), 1404 testes.

## Etapas

1. **Auditoria de partida** — HEAD limpo, suíte verde, backup `-213823`, contagens reais.
2. **Continuidade de tabela** (`radar/table_continuity.py`)
   - assinatura por página (NTEs, municípios, `TOTAL`, cabeçalho, novo anexo, nota);
   - transição por sinais combinados e pesos documentados;
   - `TOTAL` encerra o quadro e nota de rodapé não é cabeçalho;
   - rótulo `NTE`/`NÚCLEO`, `SEDE:` opcional;
   - deduplicação de NTE e conflito página-consciente.
3. **Acréscimo de páginas** (`radar/document_store.append_page_analysis`)
   - idempotente por página, remapeamento de `block_index`, estado `parcial`.
4. **Escopo regional** (`radar/regional_scope.py`)
   - cargo do edital com citação e precedência forte/fraca;
   - distribuição por NTE e município;
   - reconciliação NTE × `TOTAL`; município só publicável se fechar;
   - propostas de total agregado por NTE + total do quadro.
5. **Lotes de páginas** (`radar/page_batches.py`)
   - inventário de parciais com classificação justificada;
   - índice por página amostrando só as não lidas;
   - `append_pages` com limite, `dry_run`, `next_page` e checkpoint.
6. **Superfície** — CLI `pipeline-continuidade`, `pipeline-regional`, `documentos-parciais`,
   `documentos-paginas`, `documentos-lote`; API `/api/pipeline/continuidade`,
   `/api/pipeline/parciais`, `/api/pipeline/escopo-regional`.
7. **Testes** — `tests/test_multipage.py` (19): continuidade, sub-cabeçalho, nota de rodapé,
   cargo único/ambíguo, município não confiável, propostas agregadas, classificação de ato de
   resultado, lote seco/aplicado/idempotente, checkpoint, índice, API.
8. **Verificação real** — 004/2026 (`b86226e9…`) e inventário dos 13 parciais.
9. **Revisão independente** e correções.
10. **Documentação** e commit/push em `radar-configuracao`.

## Critérios de aceite

- 004/2026: cabeçalho p21, total p29, 27 NTEs, soma 2500 = `TOTAL 2.500`, certeza `forte`.
- Cargo do escopo único com página e citação; nenhuma proposta com `role_id`.
- `municipios_confiavel=false` quando algum NTE não fechar, com limitação explícita.
- 13 parciais classificados e justificados; 0 processados por serem listas nominais.
- Suíte completa verde, sem regressão.

## Riscos

- Texto de tabela achatado pelo extrator: soma de municípios pode não fechar. Mitigação:
  camada de município é diagnóstica, nunca publicada sem reconciliação.
- Falso positivo de NTE em lista de resultado. Mitigação: quadro só é reportado com NTE ou
  total; ato de resultado não é processado.
- Lote aplicado em versão errada. Mitigação: `--version-id` explícito, `dry_run` por padrão,
  checkpoint e idempotência por página.
