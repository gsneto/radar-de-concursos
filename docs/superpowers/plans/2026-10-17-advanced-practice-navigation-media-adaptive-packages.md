# Plano — Fase 24: navegação avançada, imagens, adaptativa e pacotes

TDD; lógica pura testada isoladamente; persistência/API com bancos temporários; prova real em
cópia da base; migração da base habitual com backup.

## Task 1 — Pesquisa e decisões
- [x] Comparar TRI, Elo, BKT e heurística; escolher heurística determinística explicável.
- [x] Definir validação de imagem sem `imghdr`/Pillow; recusar SVG.
- [x] Definir formato de pacote e defesas (Zip-Slip, zip bomb, licença).
- [x] Registrar em `docs/superpowers/specs/2026-10-17-...-research.md`.

## Task 2 — Schema v14 (aditivo)
- [x] Colunas de navegação/modo em `pratica_simulado_questoes` e `pratica_simulados`.
- [x] `pratica_flashcards.imagem_id`; tabelas `pratica_midias` e `pratica_pacotes`.
- [x] Migração aceita 0 e 2..13, idempotente, preservando dados.

## Task 3 — Mídia
- [x] `radar/media.py`: `detect_image`, `validate_image`, `store_image`, `media_path`,
      `read_media`, `delete_media`.
- [x] `tests/test_media.py` (PNG/JPEG/GIF/WebP, SVG, truncado, dimensão absurda, dedup,
      traversal, remoção).

## Task 4 — Adaptativa
- [x] `radar/adaptive.py`: histórico por tópico, fatores, score, ranking determinístico,
      plano de sessão, revisão de erros, rótulos e aviso.
- [x] `tests/test_adaptive.py` (confiança baixa, pesos, determinismo, exclusão, modos).

## Task 5 — Pacotes
- [x] `radar/packages.py`: leitura segura, manifesto, exportação, prévia, importação
      transacional/idempotente, histórico.
- [x] `tests/test_packages.py` (round-trip, reimportação, dry-run, Zip-Slip, zip bomb,
      mídia inválida, licença desconhecida, proveniência, local prevalece).

## Task 6 — Persistência
- [x] `practice_store`: `set_exam_mark`, `set_exam_position`, `exam_summary`,
      `attach_flashcard_image`, `remove_flashcard_image`, `get_media`, `flashcard_image`,
      `create_adaptive_session`, `next_adaptive_question`; metadados de modo/posição nas listas.
- [x] Testes de navegação, imagem e sessão adaptativa em `tests/test_practice.py`.

## Task 7 — API, CLI e interface
- [x] Rotas de resumo/marcar/posição/próxima, mídia, pacotes; upload base64 com limite.
- [x] CLI `estudos-flashcard imagem`, `estudos-simulado mark|position|summary|next`,
      `estudos-pacote`.
- [x] UI: mapa/marcação/retomada/confirmação, imagem de flashcard, seletor de modo e pacotes.
- [x] `tests/test_ui.py` ampliado.

## Task 8 — Documentação, revisão, prova real e commit
- [x] Design, pesquisa, plano, prova real; README e log de trabalho.
- [ ] Revisão independente e correção de achados.
- [ ] Migração da base habitual v13→v14 com backup e integridade.
- [ ] Commit e push para `radar-configuracao`.
