# Plano — Fase 41: quadros complexos de vagas indígenas

Data: 2026-10-18. Base `78b4a36` (F40), schema v21, 1.775 testes.

## Objetivo

Interpretar corretamente três formatos que a F40 deixou pendentes, com mecanismos
reutilizáveis: quadro largo por colunas (SEDUC-PA), notação de cadastro de reserva (TJAP) e
distribuição em texto corrido (TJRS).

## Passos

1. **Semântica de modalidades** — `radar/modality_legend.py`:
   `parse_definitions`, `kind`, `cr_notation`, `asterisk_note`.
2. **Quadro largo** — `radar/vacancy_columns.py`:
   `page_words` (PyMuPDF, caminho ou bytes), `assemble_rows` (cabeçalho + blocos
   multilinha), `parse_wide_table` (regionais, total geral, costura entre páginas,
   pendências), `parse_notation_table` (notação de reserva), `report` (leitura).
3. **Texto corrido** — `radar/vacancy_inline.py`:
   `parse_distribution` (total + cargo + lista) e `extract_distribution`.
4. **Integração** — `document_fields.extract_field_proposals` (novo `pdf_bytes`),
   `reprocess.propose_for_version` (artefato armazenado), `monitoring` e `pipeline`
   passando os bytes.
5. **Elegibilidade** — mapear `unified_*` e `indigenous_reserve_notation`; reserva de cargo
   sem número vira `reserva_sem_quantidade`; matriz expõe `vacancies.unified`.
6. **Superfície** — rota `GET /api/quadro-vagas` e comando `quadro-vagas`.
7. **Testes** — `tests/test_vacancy_columns_f41.py` (31 casos).
8. **Documentação e prova real**; revisão independente; commit e push.

## Critérios de aceite

- SEDUC-PA: 381 linhas, 24 regionais fechando, total geral 2.000, PI=30, PPIQ=180,
  PI/PQ=138; nenhuma unificada contada como exclusiva.
- TJAP: imediato 15; `CR*` como reserva sem quantidade; sem número indígena inventado;
  asterisco sem nota registrado.
- TJRS: total 30 e indígena 1, com cargo amarrado na mesma frase.
- Reprocessamento idempotente; nenhuma revisão/valor/reconciliação criada.
- Suíte completa verde; contrato v1 e schema inalterados.

## Fora de escopo

- Anexo II-A como fonte de vagas (é ordem de convocação).
- Rateio de coluna unificada ou de percentual.
- Migração de schema.
