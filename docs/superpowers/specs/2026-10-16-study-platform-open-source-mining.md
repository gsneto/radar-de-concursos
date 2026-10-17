# Fase 21 - Mineração open source, reutilização e plataforma de estudos

Data: 2026-10-16. Base: `dc1eb6c` (Fase 20), 704 testes OK (baseline confirmada por execução).

Consulta de repositórios: 2026-10-16. Diretório de auditoria (fora do Git):
`%TEMP%/radar-open-source-audit/`. Nenhum clone/cache foi adicionado ao repositório.

## 1. Repositórios obrigatórios analisados

| # | Repositório | Commit | Licença | Stack | Veredito |
|---|---|---|---|---|---|
| 1 | matheussilva421/estudo-organizado | `eb8cc6cf` | **MIT** | JS vanilla (PWA + IndexedDB) | **Reutilizar/adaptar** |
| 2 | michel-softwares/track-concursos | `feb1c5c2` | **Proprietária** ("todos os direitos reservados", uso pessoal não comercial, sem modificação/redistribuição) | Python + webview | **Descartar (licença)** |
| 3 | ispectr3/RadarConcursos | — | — | — | **Indisponível** (`Repository not found`) |
| 4 | remoshan/smart-student-productivity-dashboard | `39f348c0` | **MIT** | React + Vite | **Extrair lógica** (stack incompatível) |
| 5 | Bo0ndo2/Study-Planner | `fca34a4a` | **Ausente** | Next.js/TS | **Descartar (sem licença)** |
| 6 | olavodd42/banco-provas | `556c109a` | **Ausente** | Python + frontend | **Descartar (sem licença)** |
| 7 | feliperjj/Banco-Questoes | `39bd2d1f` | **Ausente** | Python | **Descartar (sem licença)** |
| 8 | kauafernandomelo/api-concursos-publicos | `0145be4a` | **Ausente** | Python | **Descartar (sem licença)** |
| 9 | danielnery46/buscar-concursos | `1808ca00` | **Apache-2.0** (NOTICE) | React/TS + Supabase | **Descartar p/ código** (stack; foco em scraping/supabase) |

Repositório 3 não existe no momento da consulta — registrado, não inventado. Repositórios sem
arquivo de licença **não autorizam** cópia: nenhum código deles foi usado.

## 2. Buscas adicionais realizadas (2026-10-16)

Palavras-chave pesquisadas (PT/EN): `concurso`, `concursos públicos`, `study planner`,
`study tracker`, `cronograma de estudos`, `ciclo de estudos`, `edital verticalizado`,
`study dashboard`, `Pomodoro`, `spaced repetition`, `flashcards`, `question bank`,
`exam preparation`, `study schedule generator`, `study time tracker`, `academic planner`,
`exam scraper`, `diário oficial scraper`.

Achados relevantes com licença permissiva:
- `open-spaced-repetition/sm-2` e `alankan886/SuperMemo2` (MIT) — implementações SM-2. Não
  adotadas como **dependência** (o Radar é stdlib-only); a matemática SM-2 é publicada, mas o
  projeto já dispõe de uma agenda de revisão espaçada testada no candidato MIT (item 1), que foi
  a escolhida para evitar nova dependência.

Limitação declarada: **não** se pesquisou todo o GitHub nem todo o universo open source; as
buscas acima e a lista de repositórios foram o escopo efetivo.

## 3. Código efetivamente reutilizado

### 3.1 `matheussilva421/estudo-organizado` (MIT, `eb8cc6cf`) — COPIAR E ADAPTAR

Licença MIT preservada em `THIRD_PARTY_NOTICES.md` (atribuição a Matheus Silva). Arquivos de
origem (JS) → destino (Python) com modificações:

| Origem | Símbolo | Destino no Radar | Adaptação |
|---|---|---|---|
| `src/js/logic/revisions.js` | `calcRevisionDates` | `radar/study.py::revision_dates` | Python puro; datas ISO; `freqs` parametrizável; `adiamentos >= 0`; sem cache global |
| `src/js/logic/revisions.js` | `getPendingRevisoes` | `radar/study.py::pending_revisions` | Entrada por lista de progressos (sem `state` global); a pendência persistida é lida pela agenda (`study_store`) |
| `src/js/logic/progress.js` | `calculateContentProgress` | `radar/study.py::content_progress` | Removido o eixo "aulas"; mantido o eixo "tópicos" |
| `src/js/logic/progress.js` | `totalStudySeconds` | `radar/study.py::total_study_seconds` | Sessões persistidas; ignora `descartada` |
| `src/js/logic/cycle-progress.js` | `computeStudiedMinutesByDiscipline` | `radar/study.py::minutes_by_discipline` | Idem |
| `src/js/logic/timer.js` | `getElapsedSeconds` | `radar/study.py::elapsed_seconds` | Base + segmento em andamento; piso em 0; teto de 24 h (`capped_elapsed`, novo) |

Modificações são localizadas e o comportamento original é preservado (verificado por testes em
`tests/test_study.py`), **exceto** onde registrado: `adiamentos` limitado a `>= 0`; semântica de
datas local→UTC/`date`; acréscimo de `capped_elapsed`. Nada de infraestrutura (IndexedDB,
Firebase, DOM) foi importado.

### 3.2 `remoshan/smart-student-productivity-dashboard` (MIT, `39f348c0`) — EXTRAIR A LÓGICA

- `src/hooks/usePomodoro.js`: ciclo foco/pausa curta/pausa longa (`LONG_BREAK_INTERVAL`).
  A **ideia** do ciclo Pomodoro foi reimplementada no cronômetro próprio (hook React é
  incompatível com o frontend vanilla). Atribuição registrada.
- `src/utils/analytics.js`: agregados por período — conceito já coberto por
  `total_study_seconds(days=7)`; nenhum código copiado.

### 3.3 `danielnery46/buscar-concursos` (Apache-2.0)

Nenhum código copiado: a stack (React/TS + Supabase) é incompatível e o projeto é focado em
scraping/autenticação, já resolvidos no Radar. Registrado como candidato avaliado.

## 4. Código novo (sem cópia)

- `radar/study_store.py` — persistência (disciplinas, tópicos, progresso por edital, sessões,
  revisões) em SQLite, schema v10. Não há implementação de origem reaproveitável que use o mesmo
  banco e a mesma semântica; escrito do zero para integrar ao Radar.
- Migração v10 e rotas `GET/POST /api/estudos/*`, CLI `estudos-*` e painel no frontend — novos.
- `radar/study.py::validate_session` — guarda própria contra tempos impossíveis (não existe no
  projeto de origem, que confia no relógio do navegador).

## 5. Funcionalidade integrada (fatia vertical)

Gestão de estudos de ponta a ponta: **disciplinas → tópicos → progresso (por edital) →
cronômetro (livre/Pomodoro) → sessões persistidas → painel com tempo/progresso/revisões
pendentes**, com API aditiva, CLI e interface. Testes: `tests/test_study.py` (18),
`tests/test_study_store.py` (19), ampliação de `test_ui.py`.

## 6. Dependências

Nenhuma dependência nova. O Radar permanece **stdlib-only**; o código adaptado foi portado para
Python puro e o frontend continua vanilla JS.

## 7. Limitações e pendências

- Cronômetro não bloqueia a aba nem notifica o fim do Pomodoro (o alerta sonoro do projeto de
  origem usava áudio externo; deliberadamente não integrado).
- Sem flashcards/banco de questões (só o **software**; conteúdo de provas tem direitos
  separados e não foi copiado).
- Perfil de conhecimento × conteúdo programático permanece para fase futura (ver design Fase 21).
- Provedor de coordenadas e import/export de dados pessoais não implementados nesta fatia.
