# Design — Fase 36: carteira operacional, prazos atuais e revalidação

Data: 2026-10-18. Base: Fase 35 (`1fe3741`), schema v20 → **v21**. 1.587 testes.

## Problema

As fases anteriores produziram mecanismos: coleta, versões, extração com evidência, revisão
humana, reconciliação de cargos, conflitos e prazos. A Fase 35 terminou com 246 rótulos, 53
conflitos e 104 prazos candidatos, mas **nenhuma visão operacional**: não havia resposta
direta para "o que merece atenção agora", "qual prazo precisa ser verificado", "quais cargos
aceitam Sistemas de Informação" ou "o que fazer a seguir".

A Fase 36 não adiciona fontes nem extração. Ela transforma o que já existe em uma **carteira
inicial** com evidência rastreável, lacunas visíveis e próxima ação — sem converter candidato
em fato.

## Decisões

### 1. Prazo tem estado operacional, não só situação temporal

`radar/deadline_calendar.py` parte do relatório da Fase 35 e acrescenta o que fazer:

| Estado operacional | Significado |
|---|---|
| `nao_localizado` | nenhum documento autoritativo traz o prazo |
| `data_ilegivel` | data não interpretável |
| `conflito_documental` | valores divergentes; nenhum valor único é exposto |
| `alterado_por_retificacao` | retificação alterou o campo; leitura precisa de confirmação |
| `passado_com_evidencia` | prazo passado, preservado como histórico |
| `revalidado_na_fonte` | documento oficial byte-idêntico ao da coleta; **prazo não confirmado** |
| `fonte_nao_confirmada` | fonte/identidade não confirmada |
| `candidato_nao_revalidado` | candidato futuro sem verificação registrada |

Precedência: `sem_data` → `data_ilegivel` → retificação que altera (quando o único valor
anterior é o edital de abertura) → conflito → passado → revalidado → fonte → candidato.

**Regra central:** conflito não escolhe valor. Quando há três leituras (abertura, retificação
e outro ato), o item é `conflito_documental`, `valor` e `valor_candidato` ficam nulos e todos
os candidatos aparecem com documento, página, trecho, versão e hash. Retificação só resolve a
divergência quando o único valor anterior é o edital de abertura.

**Retificação que repete o valor não altera.** O calendário compara a proposta da retificação
com o edital de abertura; repetir o mesmo texto não é causa de mudança.

### 2. Urgência com fuso explícito

`America/Recife` é a referência de "hoje"; UTC é registrado em paralelo. Uma data brasileira
não expira três horas antes por causa da meia-noite UTC. A urgência é derivada dos dias
restantes: `hoje`, `ate_7_dias`, `ate_30_dias`, `futuro`, `vencido`, `sem_data`.

### 3. Revalidação verifica o documento, não o prazo

`radar/deadline_revalidation.py` responde uma pergunta estreita: **o documento oficial servido
hoje é o mesmo que originou o prazo?** Baixa somente a URL já conhecida, com timeout e limite
de 25 MB, calcula sha256 e compara com a versão armazenada.

| Resultado | Significado |
|---|---|
| `fonte_inalterada` | bytes idênticos; o prazo continua candidato |
| `fonte_alterada` | documento mudou; a nova versão cabe ao ciclo de monitoramento |
| `fonte_indisponivel` | erro de rede/HTTP |
| `sem_permissao` | política da fonte não autoriza |
| `sem_documento` / `erro` | ausência de URL/versão ou falha inesperada |

- `dry_run` (padrão em API/CLI) **não consulta a rede** e não grava.
- `apply` grava apenas metadados em `revalidacoes_prazo` (append-only): URL, status, hashes,
  resultado, autor e data. Nunca o conteúdo.
- Redirecionamento para outro host ou para HTTP é recusado: a política da fonte vale no
  destino, não só na URL original.
- Nenhuma proposta, prazo ou decisão é alterado. O ciclo de monitoramento continua sendo o
  único que incorpora versões novas.

### 4. Carteira por concurso × cargo, com prontidão determinística

`radar/portfolio.py` reutiliza `opportunities` (agrupamento/dossiê), `decisive_fields`
(vagas, SI, prazos, local), `deadline_calendar` e `coverage_states`. Não há cadastro paralelo.

Estados de prontidão, exclusivos, com precedência:

1. `documentacao_insuficiente`
2. `edital_oficial_necessario`
3. `conflito_documental_pendente`
4. `prazo_precisa_revalidacao`
5. `oportunidade_historica` (todos os prazos conhecidos passaram)
6. `identidade_cargo_pendente`
7. `campos_decisivos_ausentes`
8. `candidatos_prontos_para_revisao`
9. `dossie_revisado_campos_nao_confirmados`
10. `informacao_confirmada` (só com decisão humana válida)

Cada estado traz motivos. A ordem é uma decisão de produto: um prazo urgente vem antes da
identidade pendente porque é o que impede a candidatura; um concurso com todos os prazos
passados vem antes da identidade porque não há candidatura ativa.

### 5. Prioridade é uma tupla explicada, não uma pontuação opaca

Ordem: urgência do prazo → compatibilidade com SI (expressa > categoria > correlata) →
reserva indígena (apenas no escopo do concurso) → documento oficial → identidade reconciliada.
Cada item lista os motivos em texto. Não há número único escondendo diferenças.

### 6. SI é do cargo, nunca do concurso

O relatório de campos decisivos tem estado por cargo e um agregado. A carteira usa o estado
**do cargo**; quando o cargo não tem leitura, retorna `nao_encontrado` — não herda o estado de
outro cargo. Para o escopo do concurso inteiro, o agregado é exibido como "melhor estado entre
cargos", explicitamente qualificado.

Rótulo só com código ("400") casa com "400 Agente Fiscal" apenas quando a correspondência é
única. Rótulo sem a anotação do extrator ("— motivo") também é reconhecido.

### 7. Vagas indígenas são do concurso

`decisive_fields` não distribui vagas indígenas por cargo. A carteira marca
`ambito: "concurso"` e não usa a reserva como sinal de prioridade de um cargo específico. O
dossiê mostra o estado do concurso e os quantitativos com evidência; nada é derivado do total
agregado.

### 8. Dossiê operacional reutiliza a mesa

`portfolio_dossier` compõe `opportunity_dossier` + campos decisivos + calendário:

- identificação (concurso, cargo, reconciliação, edital, retificações);
- vagas (total agregado, imediatas, reserva, indígenas com âmbito);
- formação (requisito literal, cursos aceitos, SI por cargo);
- prazos (calendário + linha "pagamento" declarando que o modelo não extrai esse prazo);
- localização (prova e lotação separadas);
- conflitos, lacunas, prontidão e próxima ação.

Cada seção aponta para a evidência na mesa. O botão "Abrir na mesa de revisão" abre o dossiê
existente na própria página — não uma rota JSON.

### 9. Destaques: conjunto inicial controlado e diverso

`portfolio_highlights` inclui apenas oportunidades com edital oficial e ao menos um sinal:
prazo futuro, SI expresso/categoria/correlato ou reserva indígena. Rótulo que não é cargo fica
fora. No máximo **dois cargos por concurso**, para que um edital grande não ocupe a carteira.
Cada item declara o motivo da inclusão.

### 10. Schema v21

Nova tabela `revalidacoes_prazo` (append-only, FKs para concurso/documento/versão, CHECK de
resultado) e índice `idx_revalidacoes_prazo`. Migração v20→v21 idempotente, sem tocar dados
existentes. v20 continua legível; as rotas novas degradam para "sem verificação" quando a
tabela não existe.

### 11. API, CLI e UI aditivas

Rotas: `GET /api/carteira`, `/api/carteira/destaques`, `/api/carteira/dossie`,
`/api/prazos/calendario`, `/api/prazos/revalidacao`, `/api/prazos/revalidacao/historico`,
`POST /api/prazos/revalidacao`. Comandos: `carteira`, `carteira-destaques`, `carteira-dossie`,
`prazos-calendario`, `prazos-revalidar`, `prazos-revalidacao-historico`. `/api/prazos`
permanece para compatibilidade.

## Limites declarados

- Revalidar o documento não confirma o prazo: confirma que o ato servido hoje é o mesmo.
- Conflito permanece pendente até decisão humana; a carteira não escolhe vencedor.
- Nenhuma decisão, revisão ou valor vigente é criado pela fase.
- A carteira só inclui concursos com propostas extraídas; concurso sem documento não vira
  linha inventada.
- Pagamento não é extraído pelo modelo; o dossiê declara a lacuna.
- A classificação não substitui a mesa de revisão; ela aponta onde ir.
