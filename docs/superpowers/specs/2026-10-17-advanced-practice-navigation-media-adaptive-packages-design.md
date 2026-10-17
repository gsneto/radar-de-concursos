# Design — Fase 24: navegação avançada, imagens, prática adaptativa e pacotes

Data: 2026-10-17. Base: Fase 23 publicada (`01f6dfb`), schema v13, 912 testes.

## Objetivo

Fechar as lacunas de uso real da Prática sem inflar o produto com modelos que os dados não
sustentam:

1. **Navegação de simulado** — mapa de questões, pulo direto, marcação para revisão, retomada
   na posição salva e confirmação antes de finalizar com questões em branco.
2. **Flashcards com imagem** — anexar/trocar/remover imagem com validação real do conteúdo.
3. **Prática adaptativa explicável** — selecionar a próxima questão por fraqueza, mostrando
   *por que* aquela questão foi escolhida.
4. **Pacotes portáveis** — exportar/importar questões e flashcards (com mídia) entre bases,
   com prévia, idempotência e defesa contra arquivos hostis.

Não é objetivo: estimar nota, probabilidade de aprovação, TRI/IRT, ranking entre candidatos,
sincronização em nuvem, editor colaborativo ou importação de bancos comerciais.

## Decisões de projeto

### 1. Adaptação: heurística determinística, não TRI/Elo

- **TRI/IRT** exige parâmetros calibrados por item (dificuldade, discriminação) e volume de
  respostas que o produto não tem. Inventar parâmetros seria precisão falsa.
- **Elo** exigiria ratings por item e um segundo modelo de "habilidade" que conflita com o
  perfil declarado (que é a fonte de verdade do usuário).
- Escolha: **score de fraqueza** com pesos fixos e motivos rastreáveis por fator:
  `erro_recente` (3), `pouco_praticado` (2), `revisao_atrasada` (2), `lacuna_perfil` (2),
  `dificuldade` (1); máximo 10. Desempate por `sha256(versao:seed:id)`, portanto reprodutível.
- **Honestidade estatística**: com menos de `MIN_EVIDENCE=3` tentativas no tópico a confiança é
  **baixa** e o peso de erro é limitado a 1. A UI e a API declaram que o percentual de uma
  sessão adaptativa **não é comparável** ao de um simulado de conjunto fixo.
- O resultado da prática **nunca** sobrescreve o perfil declarado; apenas alimenta o histórico.

### 2. Imagens: validação por assinatura, armazenamento por hash

- `imghdr` foi removido no Python 3.13 e não há Pillow no runtime; a validação é feita por
  **magic bytes** + checagem de cabeçalho de dimensão para PNG, JPEG, GIF e WebP.
- **SVG é recusado** (pode conter script) e qualquer conteúdo não reconhecido é rejeitado.
- O arquivo é gravado em `data/estudo-midia/<sha256>.<ext>` — **fora do webroot**, nomeado pelo
  hash (dedup natural, sem path traversal, sem sobrescrita).
- A rota `GET /api/estudos/midia/<id>` serve o arquivo com `Content-Type` **fixo** vindo do
  banco e `X-Content-Type-Options: nosniff`; o cliente nunca dita o tipo.
- Upload via JSON base64 com limite de tamanho (o servidor simples não tem parser
  `multipart/form-data`); a decisão está documentada e o limite é aplicado antes e depois da
  decodificação.
- Remover a imagem do cartão apaga a mídia quando nenhum outro cartão a referencia.

### 3. Pacotes: JSON + ZIP com manifesto, não Anki/QTI

- Anki `.apkg` e QTI são formatos grandes, com semântica própria e risco de aceitar conteúdo
  sem licença. O pacote `radar-pacote` v1 é explícito e auditável:
  `manifest.json` + `registros.json` + `midia/<sha256>.<ext>`.
- **Defesas**: nome de membro normalizado (bloqueia absoluto, UNC, unidade e `..`), limites por
  membro (8 MiB), total (40 MiB), quantidade (500), JSON (4 MiB) e razão de compressão (120×);
  tamanho real medido no stream, nunca no metadado.
- **Licença**: `propria`, `autorizada`, `cc_by`, `cc_by_sa`, `public_domain`, `desconhecida`.
  Desconhecida entra como `licenca_verificada=False` com aviso e **nunca** é promovida
  automaticamente.
- Importação é **transacional**, **idempotente** e **não destrutiva**: conflito preserva o
  registro local e é reportado; `dry_run` simula sem gravar; a proveniência fica em
  `pratica_pacotes`.

### 4. Schema v14 (aditivo)

| Objeto | Mudança |
|---|---|
| `pratica_simulado_questoes` | `marcada_revisao`, `motivo_selecao` |
| `pratica_simulados` | `questao_atual`, `modo`, `algoritmo_versao` |
| `pratica_flashcards` | `imagem_id` |
| `pratica_midias` (nova) | id, sha256, mime, extensão, bytes, dimensões, origem, licença |
| `pratica_pacotes` (nova) | proveniência e contagens de cada importação |

Migração aceita 0 e 2..13, é idempotente e preserva todos os dados. `SCHEMA_VERSION=14`.

## Contratos de API

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/estudos/simulados/<id>/resumo` | respondidas, brancos, marcadas, posição, tempo restante (sem gabarito) |
| POST | `/api/estudos/simulados/<id>/marcar` | `{ordem, marcada}`; não altera resposta |
| POST | `/api/estudos/simulados/<id>/posicao` | `{ordem}` para retomada |
| POST | `/api/estudos/simulados/<id>/proxima` | acrescenta a próxima questão adaptativa |
| POST | `/api/estudos/simulados` | aceita `modo`; modos adaptativos retornam `{simulado, plano, aviso}` |
| POST | `/api/estudos/flashcards/<id>/imagem` | `{dados_base64, licenca}` |
| DELETE | `/api/estudos/flashcards/<id>/imagem` | desvincula e remove mídia órfã |
| GET | `/api/estudos/midia/<id>` | bytes com tipo fixo e `nosniff` |
| GET | `/api/estudos/pacotes` | histórico de importações |
| GET | `/api/estudos/pacotes/exportar` | ZIP do conteúdo próprio |
| POST | `/api/estudos/pacotes/previa` | valida e aponta conflitos sem gravar |
| POST | `/api/estudos/pacotes/importar` | importa (ou `dry_run`) |

Códigos: 400 para entrada inválida, 404 para recurso ausente, 409/503 preservados onde já
existiam. Erros sempre em JSON; nenhuma rota nova revela gabarito de prova em andamento.

## CLI

- `estudos-flashcard imagem --id <id> --file <img> [--licenca ...]`, `--remover`.
- `estudos-simulado mark|position|summary|next` e `create --modo adaptativa|revisao_erros|personalizada`.
- `estudos-pacote export|preview|import|list` com `--dry-run`.

## Interface

- Simulado: mapa numerado (respondida/marcada), navegação anterior/próxima, marcação com
  `aria-pressed`, retomada na posição salva, confirmação explícita quando há brancos e aviso de
  modo adaptativo.
- Flashcards: prévia da imagem, anexar/trocar/remover.
- Formulário de simulado: seletor de modo com aviso de comparabilidade.
- Pacotes: seleção de arquivo, prévia com contagens/conflitos/licença, importação e lista.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Adaptativa virar "nota mágica" | fatores e motivos expostos; aviso de não comparabilidade; confiança baixa com pouca evidência |
| Imagem maliciosa | magic bytes, SVG recusado, tipo fixo, `nosniff`, fora do webroot |
| ZIP hostil | limites de membro/total/quantidade/razão + normalização de caminho |
| Conteúdo sem licença | estado explícito, aviso, nunca liberado automaticamente |
| Importação destruir dados | transação, conflito preserva local, `dry_run`, proveniência auditável |
| Migração da base real | backup consistente + `integrity_check` antes/depois |

## Critérios de aceite

- Suíte completa verde, incluindo novos testes de mídia, adaptativa, pacotes, navegação e UI.
- Base real migrada para v14 com integridade `ok` e contagens preservadas.
- Nenhum gabarito vazando em prova em andamento; contrato v1 de `/api/concursos` intacto.
- Revisão independente sem críticos abertos.
