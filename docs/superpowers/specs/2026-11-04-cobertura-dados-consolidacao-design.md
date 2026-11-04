# Cobertura de dados, redução de pendências e consolidação — design (Fase 47)

Data: 2026-11-04. Base: `7d3311c`, branch `radar-configuracao`, schema v21.

## Objetivo

Executar a Fase 47 sob a diretriz **"Cobertura de dados primeiro"**: medir a cobertura real
de dados do Radar contra o universo do banco e uma amostra externa das bancas oficiais,
reduzir pendências documentais com evidência (sem confirmação automática), podar/consolidar
a superfície técnica (CLI, tabelas, documentação desatualizada e despacho HTTP em
`radar/server.py`) e medir/elevar a qualidade (cobertura de testes Python e React, hardening
do servidor e validação operacional).

Restrição de escopo: **não adicionar telas novas, comandos de CLI novos nem fases de
feature**.

## Decisões

### 1. Medição de cobertura real (`docs/COBERTURA_DADOS.md`)

A cobertura é medida em duas camadas complementares:
1. **Funil interno real (`data/radar.sqlite3`, snapshot de 2026-11-04)**:
   - 843 certames (`concursos_identidade` exceto `container_fonte`) e 1 container (`dou-secao-3`);
   - 3.417 documentos registrados, 1.988 versões baixadas, 1.975 versões com blocos/texto,
     15.549 propostas com 15.549 evidências literais;
   - Estado de cobertura oficial por certame: `apenas_agregador` (703 / 83,4%),
     `oficial_sem_edital` (69 / 8,2%), `campos_candidatos` (55 / 6,5%),
     `oficial_sem_extracao` (8 / 0,9%), `conflito` (5 / 0,6%), `edital_extraido` (2 / 0,2%),
     `oficial_nao_importado` (1 / 0,1%), `campos_confirmados` (0 / 0,0%).
2. **Recorte do perfil do usuário (Sistemas de Informação, reserva indígena, deslocamento desde Paulo Afonso–BA)**:
   - 839 oportunidades na carteira operacional e 597 na matriz de elegibilidade;
   - Reserva indígena em linha de cargo: 31 com vaga imediata (`cargo_imediata`), 55 com
     zero imediato e reserva (`cargo_zero_imediato_com_reserva`), 14 distribuídas por cargo,
     11 em reserva combinada; separado de 86 menções fora do escopo de reserva e 357 com
     zero explícito;
   - Sistemas de Informação: 1 explícito, 3 em categoria que inclui o curso, 18 por nível
     mínimo, 5 em área correlata (interpretação humana), 81 incompatíveis por requisito
     expresso, 489 ainda sem requisito localizado no texto;
   - Geografia: 9 oportunidades com local de prova na BA (`uf=BA`), 18 certames com
     distância em linha reta calculável desde Paulo Afonso–BA (`(-9.3983, -38.2147)`).
3. **Classificação das 18 fontes catalogadas**:
   - **Habilitadas e operacionais (6)**: `guajara`, `dou-secao-3`, `fgv-conhecimento`,
     `quadrix`, `pci`, `ibge-localidades`;
   - **Habilitável agora (com autorização do usuário) (1)**: `ibfc` (conector pronto,
     desligado por padrão em `radar_ops.json` por opt-in de CDN);
   - **Aguardando credencial ou validação de termos por serviço (5)**: `dados-gov-br`,
     `conecta-gov-br`, `concursosnobrasil`, `acheconcursos`, `jcconcursos`;
   - **Bloqueadas por licença/robots ou sem valor operacional (6)**: `api-concursos-kaua`,
     `quest-api`, `qconcursos`, `questoesdeconcursos`, `api-concursos-vinimartinsc`,
     `concursos-api-deno`.

### 2. Redução de pendências documentais com evidência

Diagnóstico das pendências reais no banco:
- **6 versões em `nao_iniciada`**: arquivos PDF já baixados em `data/radar.sqlite3.documents/`
  (3 `edital_abertura`, 2 `edital_retificado`, 1 `retificacao`, das bancas FGV e Quadrix)
  que ainda não passaram por extração. Ação: executar a extração determinística de texto e
  propostas sem confirmação automática.
- **6 versões em `falhou` (`pdf_sem_texto`)**: PDFs escaneados da FGV; como `pymupdf` e
  `windows_ocr` (`pt-BR`) estão disponíveis localmente, executar OCR explícito (camada
  derivada rastreada, nunca confirmação automática) dentro do limite de páginas.
- **1.429 documentos sem versão**: 1.407 (98,5%) são documentos secundários de etapas
  posteriores (`resultado`: 823, `None`: 207, `homologacao`: 145, `gabarito`: 88,
  `convocacao`: 66, `outro`: 55, `comunicado`: 23) e apenas **22 são documentos decisivos**
  (`edital_abertura`: 1, `edital_retificado`: 3, `retificacao`: 9, `cronograma`: 2,
  `pagina_concurso`: 7). Ação: baixar e extrair prioritariamente os documentos decisivos
  oficiais respeitando `budget.py` e `source_policy`.
- **111 conflitos documentais classificados** e **3 prazos futuros `candidato_nao_revalidado`**:
  revalidar os documentos oficiais dos prazos futuros na fonte (registrando hash e data em
  `revalidacoes_prazo`) e documentar o plano de revisão humana por causa de conflito.

### 3. Poda e consolidação sem quebra

- Inventariar os **127 subcomandos da CLI** (`radar/__main__.py`) e as **45 tabelas SQLite**
  em `docs/BACKEND_INVENTORY.md`, classificando cada grupo em ativo, legado/compatibilidade
  ou candidato a consolidação (sem remover subcomando nem tabela sem autorização).
- Atualizar `README.md` (que ainda descrevia "uma fonte oficial" e "HTML/CSS/JS sem
  dependências") e `docs/READINESS_GATE.md` (atualizando para o estado real da Fase 47).
- Refatorar o despacho HTTP de `do_GET` e `do_POST` em `radar/server.py` usando tabelas
  declarativas de rotas exatas + handlers, preservando a AST/marcadores exigidos por
  `radar/api_contract.py` (`verify()`) e garantindo testes de caracterização verdes antes e
  depois.

### 4. Qualidade, testes, segurança e operação

- Medir cobertura de testes Python (`trace`/contagem por módulo ou `coverage` se instalado)
  e React (`vitest`), registrando baseline em `docs/TEST_COVERAGE.md`.
- Adicionar testes unitários/integração em `web-react/src/features/` para as 6 páginas ainda
  sem arquivo `.test.tsx` próprio (`OverviewPage`, `OpportunitiesPage`, `DeadlinesPage`,
  `DossierPage`, `StudiesPage`, `SettingsPage`), cobrindo estados de carregamento, vazio,
  erro e acessibilidade (rótulos, foco/teclado), e rebuildar `web-react/dist` no Windows.
- Revisar e testar hardening do servidor local (`_host_allowed`, `_origin_allowed`,
  `Content-Length`, path traversal, semáforo de rotas caras) e documentar o modelo de ameaça
  em `docs/DEPLOY.md`.
- Validar os scripts operacionais (`scripts/verify_tasks.ps1`, `scripts/run_cycle.ps1`,
  `scripts/notify.ps1`) sem alterar tarefas agendadas do sistema sem necessidade.
