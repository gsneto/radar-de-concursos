# Plano — Fase 31: OCR controlado, vagas agregadas, requisitos inline

## Task 1 — Auditoria
- [x] Branch `radar-configuracao`, HEAD `5d4ef11`, árvore limpa, sincronizada.
- [x] Suíte de base: **1368 testes, OK**.
- [x] Backups `-204553` e `-210200`, `integrity ok`, v18.
- [x] Documento sem texto identificado por registro/URL/versão/hash (não pelo nome).

## Task 2 — Diagnóstico do PDF
- [x] `producer = Microsoft: Print To PDF`, 0 fontes, 0 spans, 0 imagens, 4.645 desenhos.
- [x] Conclusão: texto em contornos vetoriais (não scan, não corrupção).

## Task 3 — OCR
- [x] `radar/ocr.py` v2: motores `windows_ocr` (WinRT/PowerShell 5.1, pt-BR) e `tesseract`
      (se instalado); disponibilidade, idiomas e limites.
- [x] `detect_need` distingue texto vetorial, imagem, sem texto e texto parcial.
- [x] `ocr_version` com dry-run padrão, páginas selecionadas, DPI, timeout, limites, códigos
      estáveis; camada derivada com nota completa; original intacto.
- [x] Propostas de OCR marcadas (`ocr:` + motivo).
- [x] Piloto na cópia e na base real: 2 páginas, 4.960 caracteres, 1.530 ms.

## Task 4 — Quadro de vagas agregado
- [x] `radar/vacancy_aggregate.py`: cabeçalho agregado, linhas, TOTAL, nota de rodapé.
- [x] Campo novo `vagas_total_publicado` (aditivo); nunca distribui por modalidade.
- [x] Conflito soma×total declarado no motivo.
- [x] Guarda em `vacancy_tables._field_for` contra cabeçalho agregado.
- [x] 9 testes (agregado, sem distribuição, conflito, evidência literal, guarda).

## Task 5 — Requisitos inline
- [x] `radar/inline_requirements.py`: rótulos, cargo do mesmo bloco, corte em `Atribuições`.
- [x] Curso extraído com padrão próprio e filtro de genéricos.
- [x] `si_compatibility` candidato com evidência.
- [x] Ligado em `document_fields` e `reprocess`; 7 testes.

## Task 6 — Revisão e duplicidades
- [x] `review.duplicate_groups` com duplicidade textual × repetição legítima.
- [x] Fatores de prioridade `vaga_indigena` (+4), `formacao_si` (+3), `duplicata` (+1),
      documentados e testados.
- [x] Rota `/api/revisao/duplicidades`, CLI `revisao-duplicados`, painel na UI.

## Task 7 — Prova real
- [x] Cópia isolada: +72 propostas, 0 inválidas, 2ª execução 0.
- [x] Base real: +72, 2ª execução 0, integridade ok, 0 revisões/valores.
- [x] OCR aplicado ao documento pendente; `pdf_sem_texto` = 0.
- [x] Suíte final: **1397 testes, OK**.

## Task 8 — Documentação e publicação
- [x] Design, pesquisa, plano e prova real; `requirements.txt` declara PyMuPDF.
- [ ] Revisão independente, README/log, commit e push.
