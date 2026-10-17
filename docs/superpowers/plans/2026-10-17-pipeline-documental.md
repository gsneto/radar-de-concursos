# Plano — Fase 30: pipeline documental end-to-end

## Task 1 — Auditoria
- [x] Branch `radar-configuracao`, HEAD `d9941a6`, árvore limpa, sincronizada.
- [x] Suíte de base: **1333 testes, OK**.
- [x] Backup consistente + `integrity_check` + `foreign_key_check`.
- [x] Diagnóstico: 48 anexos IBFC baixados e **não extraídos** (`nao_iniciada`, 0 blocos).

## Task 2 — Extração declarada
- [x] `extract_document()` com `blocks`, `truncated`, `total_pages`, `limitation`,
      `extractor_version` e códigos estáveis (`pdf_sem_texto`, `pdf_paginas_excedidas`, ...).
- [x] Prefixo de 40 páginas para PDF longo, com limitação registrada.
- [x] `record_analysis(note=)` grava versão do extrator e limitação no evento `analise`.
- [x] Sucesso limpa `error_code` de tentativa anterior.
- [x] `pypdf` silenciado: avisos não poluem a saída JSON da CLI.

## Task 3 — Pipeline e cobertura
- [x] `radar/pipeline.py`: etapas por documento, primeiro bloqueio, prévia sem gravar,
      extração controlada com limite, cobertura por concurso (7 categorias) e resumo global.
- [x] Deduplicação intra-versão em `record_analysis`; relatório de duplicidades históricas.
- [x] `radar/ocr.py`: necessidade de OCR com motivo + disponibilidade do motor (sem executar).

## Task 4 — Interface
- [x] API `/api/pipeline`, `/api/pipeline/cobertura`, `/api/pipeline/documentos`,
      `/api/pipeline/duplicidades`, `/api/pipeline/ocr`.
- [x] CLI `pipeline`, `pipeline-documentos`, `pipeline-cobertura`, `pipeline-duplicados`,
      `documentos-pendentes`, `documentos-extrair`, `ocr-pendentes`.
- [x] Painel de pipeline na UI.

## Task 5 — Prova real
- [x] Cópia isolada: 56 versões extraídas, 1 `pdf_sem_texto`, 1142 propostas.
- [x] Segunda execução na cópia: 0 novas (idempotente).
- [x] Base real: dry-run, apply, segunda execução 0, integridade ok.
- [x] 48/48 anexos IBFC com blocos e evidência por página.

## Task 6 — Testes e revisão
- [x] 25 testes novos em `tests/test_pipeline.py` (estados, dry-run, idempotência, versão nova,
      decisão humana, cobertura, duplicidades, OCR, API, contrato v1).
- [x] Suíte: **1361 testes, OK**.
- [x] Revisão independente.
- [ ] Commit e push.
