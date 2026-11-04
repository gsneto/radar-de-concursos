# Plano — Cobertura de dados, redução de pendências e consolidação (Fase 47)

Base: `7d3311c`. Branch: `radar-configuracao`. Schema: v21 (sem migração).

## Tarefa 1 — Medir cobertura real de dados (`docs/COBERTURA_DADOS.md`)
- [ ] Levantar métricas exatas do banco `data/radar.sqlite3` (843 certames, 3.417 documentos,
      1.988 versões, 15.549 propostas, 839 itens de carteira, 597 itens de elegibilidade).
- [ ] Medir cobertura para o perfil do usuário (Sistemas de Informação, reserva indígena por
      cargo, deslocamento desde Paulo Afonso–BA e UFs BA/PE, prazos futuros).
- [ ] Comparar contra amostra de verdade externa das fontes habilitadas (FGV, Quadrix, DOU,
      Guajará-Mirim, PCI) e explicar os gargalos do funil.
- [ ] Classificar as 18 fontes catalogadas (habilitadas, habilitável com autorização,
      aguardando credencial/validação, bloqueadas/sem valor).
- [ ] Commitar `docs/COBERTURA_DADOS.md` + spec/plano da Fase 47.

## Tarefa 2 — Reduzir pendências de dados com evidência
- [ ] Fazer backup consistente do banco antes de processar pendências.
- [ ] Extrair as 6 versões já baixadas em estado `nao_iniciada` (3 editais de abertura,
      2 editais retificados, 1 retificação — FGV e Quadrix).
- [ ] Executar OCR opcional (`windows_ocr` + `pymupdf`) nas 6 versões `pdf_sem_texto`
      (camada derivada rastreada, respeitando limite de páginas).
- [ ] Baixar e extrair os documentos oficiais decisivos sem versão (`edital_abertura`,
      `edital_retificado`, `retificacao`, `cronograma`, `pagina_concurso` da FGV),
      respeitando `budget.py` e `source_policy`.
- [ ] Revalidar na fonte os documentos dos prazos futuros `candidato_nao_revalidado`.
- [ ] Atualizar `docs/COBERTURA_DADOS.md` com o comparativo **antes vs. depois** da redução
      de pendências.

## Tarefa 3 — Podar e consolidar (CLI, tabelas, docs e `radar/server.py`)
- [ ] Inventariar os 127 subcomandos da CLI e as 45 tabelas em `docs/BACKEND_INVENTORY.md`,
      classificando status e candidatos à consolidação.
- [ ] Atualizar `README.md` e `docs/READINESS_GATE.md` para refletir a arquitetura e os
      números reais.
- [ ] Refatorar `do_GET` / `do_POST` em `radar/server.py` reduzindo a cadeia de `elif` com
      tabela de despacho e mantendo `api_contract.verify()` e `test_server.py` /
      `test_contract.py` 100% verdes.
- [ ] Commitar consolidação de documentação e refatoração do servidor.

## Tarefa 4 — Qualidade: testes React, cobertura, hardening e operação
- [ ] Adicionar testes para as 6 páginas React sem suíte própria (`OverviewPage`,
      `OpportunitiesPage`, `DeadlinesPage`, `DossierPage`, `StudiesPage`, `SettingsPage`),
      cobrindo estados de carregamento, vazio, erro e acessibilidade.
- [ ] Adicionar testes de hardening do servidor local (DNS rebinding, Origin, path
      traversal, limites de payload) e documentar modelo de ameaça em `docs/DEPLOY.md`.
- [ ] Medir cobertura de testes (Python + React) e registrar em `docs/TEST_COVERAGE.md`.
- [ ] Validar scripts operacionais (`scripts/`) e rebuildar `web-react/dist` no Windows.
- [ ] Executar suíte completa no `.venv` e no `web-react`, commitar e fazer push em
      `radar-configuracao`.
