# Plano — Fase 26: descoberta oficial, associação e extração

## Task 1 — Auditoria
- [x] Branch `radar-configuracao`, HEAD `5d10cbb`, arvore limpa, sincronizada.
- [x] Suite de linha de base: **1062 testes, OK** (execucao real).
- [x] Funil e causas recalculados no banco real (somente leitura).
- [x] Forense dos 16 concursos com edital: causa raiz de `local_prova` e
      `conteudo_programatico` comprovada no codigo e nos dados.

## Task 2 — Conteudo programatico
- [x] `program_content.logical_lines` + `_split_inline` + `_heading_and_remainder`:
      re-segmentacao do paragrafo de PDF sem alterar o texto.
- [x] `BLOCO N` vira disciplina apenas quando o resto parece titulo.
- [x] Testes inline (7) + regressao de offset.

## Task 3 — Local de prova
- [x] `radar/exam_location.py` com regras de aceite/rejeicao, lista de cidades preservada,
      `a_divulgar` como declaracao.
- [x] Ligado em `document_fields.extract_field_proposals`.
- [x] `location.parse_location` reconhece `a_divulgar`.
- [x] Testes (22), incluindo lotacao, UF falsa, passado, singular.

## Task 4 — Reprocessamento idempotente
- [x] `radar/reprocess.py`: le blocos gravados, valida citacao, insere so o novo.
- [x] Chave de idempotencia revalidada dentro da transacao.
- [x] Exige `ambiguity_reason` no limite de escrita; exclui paginas de agregador/banca/orgao.
- [x] Testes (11), incluindo "propostas e evidencias existentes nao mudam".

## Task 5 — Classificacao documental
- [x] `document_types.classify_document` + `source_class`; agregador nunca vira ato.
- [x] `enrichment.backfill_document_types` (somente NULL, nunca altera `kind`).
- [x] Testes (10).

## Task 6 — Associacao documento-concurso
- [x] `radar/association.py`: diagnostico somente leitura (identidade de secao, muitos atos sem
      propostas, titulos divergentes, URL compartilhada, documento sem observacao).
- [x] Testes (13).

## Task 7 — API, CLI e prova real
- [x] `GET /api/associacoes`, `POST /api/documentos/tipos`, `POST /api/documentos/reprocessar`;
      CLI `associacoes`, `documentos-tipos`, `documentos-reprocessar`.
- [x] Piloto em copia: dry-run sem efeito, apply +1117, idempotente, 0 citacoes invalidas.
- [x] Base real: backup, dry-run, apply, reaplicacao dos ajustes da revisao, verificacao.
- [x] Suite final: **1120 testes, OK**.

## Task 8 — Revisao independente e publicacao
- [x] Revisao: **3 criticos, 9 importantes, 6 menores**; todos os criticos/importantes corrigidos.
- [x] Documentacao (design, pesquisa, plano, prova real), README e log.
- [ ] Commit e push.
