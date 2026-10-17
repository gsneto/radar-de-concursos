# Fase 23 - Mineração open source, flashcards, questões, simulados e desempenho

Data: 2026-10-16. Base: `5b0f56d` (Fase 22), 829 testes OK (baseline confirmada).

Consulta dos repositórios: 2026-10-16. Diretório de auditoria (fora do Git):
`%TEMP%/radar-phase23-audit/`. Nenhum clone, cache ou conteúdo de terceiros foi adicionado ao
repositório.

## 1. Repositórios investigados

| Repositório | Commit | Licença | Stack | Decisão |
|---|---|---|---|---|
| `rmssantos/examsim` | `aaabb22` | MIT (software) + **CONTENT-LICENSE próprio** | HTML/JS + Python | **DESCARTAR** (motor acoplado ao navegador; **conteúdo não redistribuível**) |
| `open-spaced-repetition/py-fsrs` | `9446cb0` | MIT | Python (dep. `typing-extensions`) | **DESCARTAR** (nova dependência; viola stdlib-only) |
| `JAChesney/spaced-repetition-app` | `70c46cf` | **Ausente** | Python + Flet | **DESCARTAR** (sem licença) |
| `mqqikq/flashcards-api` | `894ff4a` | **MIT** | Python + FastAPI | **COPIAR E ADAPTAR** (só o `scheduler.py`, puro) |
| `XR-9/javascript-quiz-app` | `52c5dcc` | **Ausente** | JS vanilla | **DESCARTAR** (sem licença) |
| `open-spaced-repetition/sm-2` | `b6272ad` | MIT | Python | **DESCARTAR** (mesma família do já adotado; versionamento declarado instável) |
| `joshuamotoaki/gen-cards` | `161b3b7` | MIT | Tauri/Svelte | **DESCARTAR** (stack incompatível, sem algoritmo isolável) |

### 1.1 `mqqikq/flashcards-api` — COPIAR E ADAPTAR (único código reutilizado)

- Arquivo de origem: `app/scheduler.py` (função `schedule_review`, SM-2-lite), 8 testes em
  `tests/test_scheduler.py`.
- Licença MIT preservada em `THIRD_PARTY_NOTICES.md`.
- Destino: `radar/flashcards.py` (`schedule_review`).
- Motivo: função **pura** (só `dataclass` + `datetime`), sem dependências, testada e com
  semântica adequada ao escopo.
- Adaptações: retorno em `dict` (sem dataclass própria), `utc_today` explícito, `LAPSE_THRESHOLD`
  nomeado; o algoritmo foi **preservado** (testes reproduzem os casos do original).

### 1.2 Por que **não** FSRS

`py-fsrs` é maduro, mas exige `typing-extensions` — o Radar é *stdlib-only* por decisão de
arquitetura. Além disso, o Radar já tem um agendador (revisão de **tópicos**, Fase 21) e adotar
FSRS criaria **dois** modelos concorrentes sem ganho comprovado no escopo. O SM-2-lite foi
escolhido por ser determinístico, testável e sem dependências. A comparação está registrada no
docstring de `radar/flashcards.py`.

### 1.3 Por que o ExamSim foi descartado

O software é MIT, mas o motor vive em HTML/JS acoplado ao navegador (sem módulo isolável), e o
`CONTENT-LICENSE.md` proíbe explicitamente redistribuir questões, alternativas, explicações e
materiais editoriais. **Nada** foi copiado — nem código de conteúdo, nem pacotes. O motor de
simulados foi implementado do zero, com persistência no SQLite do Radar.

## 2. O que foi implementado (código novo)

- `radar/questions.py` — validação de formato, correção e estatísticas (denominador explícito).
- `radar/exams.py` — seleção sem duplicação (determinística por `seed`), cronômetro no servidor,
  expiração, correção a partir das questões **aplicadas**.
- `radar/practice_store.py` — persistência (`pratica_*`), versões de questão, tentativas,
  simulados com resposta progressiva, desempenho agregado.
- Schema **v12** aditivo em `radar/document_store.py`.
- API `/api/estudos/flashcards|questoes|tentativas|simulados|desempenho`; CLI
  `estudos-flashcard|questao|simulado|desempenho`; seção **Prática** no frontend.

## 3. Flashcards

- Criar/editar/arquivar; frente e verso; vínculo opcional a disciplina/tópico; tags.
- Fila: **novos primeiro, depois vencidos**; arquivados fora; `limit` corta a exibição sem
  descartar (voltam na próxima consulta).
- Avaliação 0–5; revisão **só** conta quando avaliada (abrir não conclui).
- Histórico em `pratica_flashcard_revisoes`; editar o cartão **não** apaga o histórico.
- Estatísticas derivadas das revisões registradas; sem revisões → percentual não calculável.

## 4. Banco de questões

- Formatos: **escolha única** e **verdadeiro/falso**. Gabarito precisa corresponder a uma
  alternativa existente; formato ambíguo é rejeitado.
- Edição cria **nova versão** (`pratica_questao_versoes`); tentativas antigas guardam
  `questao_versao` e permanecem interpretáveis.
- Arquivar não apaga tentativas; questão arquivada não pode ser respondida.
- Tentativa registra resposta, correção, duração, origem (`pratica`/`simulado`) e escopo.
- **Procedência/licença** são campos próprios; **nenhum** conteúdo de terceiros foi importado.

## 5. Simulados

- Seleção sem duplicação, com `seed` determinístico; exclui respondidas por padrão.
- Cada questão guarda a **versão aplicada**; a revisão reflete o que foi feito.
- Respostas salvas **progressivamente** (`save_exam_answer`), recuperáveis após recarregar.
- Cronômetro calculado no **servidor** (`iniciado_em`); prova cujo tempo expirou enquanto o app
  estava fechado é finalizada como `expirado` na próxima leitura.
- Correção: acertos, erros, brancos (contam no denominador, informado no `basis`), tempo usado,
  por disciplina e por tópico, lista de erradas.

## 6. Desempenho e integração

- `performance_report` agrega tentativas persistidas, com denominador explícito (brancos fora
  por padrão).
- Resultados **não** sobrescrevem a familiaridade declarada no perfil (Fase 22); são dimensões
  separadas. Percentual de acerto **não** é probabilidade de aprovação.
- Vínculo por `conceito_key`/disciplina/tópico permite cruzar com o conteúdo programático sem
  duplicar.

## 7. Exportação e backup

- Formato `radar-estudos` passa a **v2**, acrescentando as entidades de prática; arquivos **v1
  continuam importáveis** (entidades de prática opcionais).
- Importação: valida, faz prévia, é idempotente, preserva o local, reporta conflitos e trata FKs
  ausentes. Simulado em andamento importado é finalizado.
- Backup consistente via API do SQLite com `integrity_check`; restauração em banco isolado.

## 8. Compatibilidade

- Contrato v1 (18 campos) **inalterado**; migração **aditiva** v11→v12→v13; nenhuma dependência
  nova.
- Fases 20–22 preservadas (testes de regressão verdes).

## 8.1 Correções da revisão independente

- `finish_exam` **idempotente** (flag `tentativas_gravadas` no schema v13, transição condicional
  atômica) — antes, prova expirada duplicava tentativas.
- **Snapshot** de `disciplina`/`topico` em `pratica_simulado_questoes` (v13): editar a questão
  não reatribui o escopo da prova já aplicada.
- `GET /simulados/<id>/resultado` **recusa** prova em andamento (409); novo
  `GET /simulados/<id>/questoes` devolve a prova **sem gabarito** para retomada.
- Importação de `questao_versoes` passa a casar por `(questao_id, versao)` e reconcilia
  `pratica_questoes.versao` (antes corrompia a cadeia ou abortava).
- Validação de **domínios** no arquivo de importação; `IntegrityError` vira erro de arquivo.
- UI de realização do simulado: cronômetro do servidor, salvamento progressivo e retomada.

## 9. Limitações

- Sem importação de pacotes de questões de terceiros (licenciamento de conteúdo).
- Sem simulado adaptativo/estatística psicométrica; sem flashcards com imagens.
- A UI do simulado cobre responder, retomar, cronômetro e finalizar; navegação avançada
  (pular, mapa de questões, marcar para revisão) fica para a próxima fase.
