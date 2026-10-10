# Radar de Concursos — desenho do sistema multiagente OpenCode

Data: 2026-10-09. Estado: desenho aprovado em conversa; especificação aguardando revisão.

## Objetivo e limites

O usuário conversa exclusivamente com um orquestrador no OpenCode para desenvolver, futuramente, um sistema de monitoramento de concursos públicos brasileiros. Nesta fase, o resultado é a configuração local, persistente e verificável desse orquestrador e de quatro especialistas, não a implementação do produto. O orquestrador traduz cada solicitação em tarefas contextualizadas, delega pelo mecanismo real do OpenCode, confere resultados e integra somente com evidências. Não solicitar ao usuário prompts separados nem escolhas rotineiras de agentes.

O repositório novo ficará em `C:\Users\anton\OneDrive\Desktop\radar-de-concursos`. Não foi localizado um kit Radar anterior nas áreas inspecionadas; caso apareça antes da implementação, examiná-lo e tratá-lo como fonte de verdade. Criar Git local sem remoto, preservando qualquer conteúdo pré-existente; não fazer commit, merge ou push sem instrução explícita. Os documentos desta especificação e a futura configuração não criam funcionalidades de produto.

## Ambiente constatado

- OpenCode CLI `1.18.35` disponível no PowerShell; diretório da sessão inicial `C:\Users\anton` não era repositório Git.
- Configuração global existente em `C:\Users\anton\.config\opencode\opencode.jsonc`, com provedores, MCPs, instruções e plugin Superpowers. Mantê-la intacta. Há configuração mínima também em `C:\Users\anton\.opencode\opencode.json`.
- O plugin `superpowers@git+https://github.com/obra/superpowers.git` consta da configuração; a skill `brainstorming` foi efetivamente carregada nesta sessão. Especialistas devem verificar disponibilidade das skills na própria sessão antes de usá-las.
- `opencode models inferhub` listou `inferhub/cb/gpt-5.5`, `inferhub/cb/deepseek-v4.1-flash`, `inferhub/cbcn/deepseek-v4-pro`, `inferhub/ali/deepseek-v4-pro-0813` e outras rotas. Listagem prova registro no catálogo, não aceitação de requisição nem custo real.
- `opencode agent list`, `opencode debug agent`, `opencode run --agent` e `opencode agent create --help` existem. A documentação oficial consultada confirma agentes Markdown de projeto, `default_agent` e seleção de subagentes via `permission.task`. Validar os formatos contra a versão instalada e o schema antes de aplicar.

## Arquitetura e precedência

Um `opencode.json` local declara `$schema` e `default_agent: "orquestrador"`; apenas campos indispensáveis ao projeto devem ser usados. `.opencode/agents/orquestrador.md` é o agente primário; `.opencode/agents/backend.md`, `collectors.md`, `frontend.md` e `qa.md` são subagentes. Cada Markdown contém frontmatter com modo, modelo, descrição e permissões, seguido de instruções permanentes de papel. Não criar cópias globais nem plugins customizados para uma capacidade já nativa.

`AGENTS.md` guarda contexto e regras compartilhadas do projeto; especificações/contratos canônicos futuros têm precedência para detalhes de domínio; instruções permanentes dos agentes delimitam seu escopo; o prompt da tarefa descreve os arquivos, diagnóstico, testes e critérios concretos sem revogar limites gerais ou contratos. Documentos de operação em `docs/AGENT_WORKFLOW.md`, `docs/AGENT_MODELS.md` e `docs/OPENCODE_SUPERPOWERS.md` explicam uso e verificação sem duplicar regras normativas conflitantes. Um README curto pode indicar os comandos reais de abertura e diagnóstico.

## Papéis e roteamento

- **Orquestrador** (primário): entende pedido e critérios, inspeciona Git/arquitetura, identifica dependências e riscos, consulta skills aplicáveis, planeja, decide sequência/paralelismo, cria um prompt único para cada subtarefa, delega via `task`, acompanha, examina diffs/testes, pede correções e relata evidências/pendências. Não presume que relato de agente é prova.
- **Backend**: API Python/FastAPI, regras, persistência, migrações, segurança e testes apenas se a stack for confirmada. Inspeciona contratos e não os muda unilateralmente.
- **Collectors**: conectores isolados de fontes oficiais, procedência, extração/normalização, atualização, duplicidade, idempotência e fixtures locais. Não inventa dados; dado extraído por IA não equivale a fato confirmado.
- **Frontend**: interface React/TypeScript apenas se confirmada, filtros, detalhes, integração, acessibilidade/responsividade e testes; não inventa dados de produção nem altera contrato unilateralmente.
- **QA**: avaliação independente de diffs, arquivos, testes, contratos, domínio, migrações e segurança. Pode escrever testes/corrigir problemas somente quando delegados explicitamente; não aprova com base apenas no relato do implementador.

O orquestrador preserva a distinção entre vagas imediatas e cadastro de reserva, local de prova e exercício, zero e desconhecido. Não soma modalidades/localidades sem regra verificada. Mantém fontes/evidências, histórico de retificações e data de verificação; elegibilidade educacional depende dos requisitos documentados, e preferências do usuário devem ser configuráveis no produto futuro.

## Modelos e limites de custo

Preferir `inferhub/cb/gpt-5.5` para o orquestrador, condicionado ao teste da rota. Para backend/Frontend rotineiros, selecionar entre rotas DeepSeek V4 Pro listadas e validadas; para collectors, `inferhub/cb/deepseek-v4.1-flash` se funcional; QA deve usar modelo diferente do implementador sempre que possível. Tarefas complexas podem justificar um modelo mais capaz através de reconfiguração explícita e documentada, não um identificador inventado. Configurar somente modelos aceitos e testar ao menos as rotas efetivamente utilizadas no teste controlado. `docs/AGENT_MODELS.md` registrará ID exato, motivo, fonte da confirmação, teste de rota e alternativas. Dados de preço do catálogo não são comprovante de cobrança.

## Ciclo de uma solicitação futura

1. Inspecionar estado Git, código, documentação, contratos e objetivo; identificar critérios de aceitação e riscos.
2. Aplicar as skills disponíveis pertinentes (Superpowers como metodologia, governança do projeto como fonte de domínio). Definir plano e dependências, inclusive limites de arquivo por tarefa.
3. Para cada delegação, gerar prompt próprio com identificador/objetivo, contexto, módulos, diagnóstico, responsabilidade, arquivos autorizados/proibidos, contratos, regras de domínio, skills, testes, aceitação, formato de relatório e condições de parada/escalonamento.
4. Invocar especialista nomeado por `task`. Paralelizar somente tarefas independentes sem escrita concorrente em arquivos/contratos; usar branch/worktree se útil e compatível com o estado real do Git. O orquestrador permanece dono da integração. Não criar hierarquias artificiais para superar limites de profundidade.
5. Conferir resposta e arquivos/diffs reais; executar testes pertinentes e validações de contrato, solicitar correções ao agente responsável e repetir conferência. Usar QA independente quando houver implementação a revisar. Integrar somente após compatibilidade demonstrada.
6. Relatar arquivos, comandos/testes executados, evidências de delegação, decisões, limitações e pendências. Não apresentar teste não executado como aprovado.

## Permissões e tratamento de falhas

O `orquestrador` terá permissão de delegar aos quatro especialistas nomeados. Os subagentes não terão delegação em cascata por padrão; restringir ferramentas e permissões no frontmatter conforme necessidade de seus papéis e mecanismo confirmado na versão. QA deve começar com revisão somente leitura; habilitar edição somente para tarefa expressamente delegada por configuração/procedimento verificável. Negar alterações em segredos e operações como `git push`, merge em `main`, publicação, exclusão destrutiva e migração destrutiva sem autorização; não depender apenas de instrução textual quando houver permissão técnica disponível. Verificar regras efetivas com `opencode debug agent` sem imprimir configurações que contenham credenciais. A combinação de controles OpenCode e responsabilidade humana não constitui isolamento de sistema operacional; registrar limitações das regras de shell por padrão e requerer autorização para operações de risco.

Se rota de modelo falhar, testar alternativa listada e corrigir definição local; se agente ou skill não aparecer após reiniciar, diagnosticar carregamento e registrar bloqueio. Se uma coleta/implementação não puder validar contrato, fonte, teste ou requisito crítico, parar a subtarefa e informar o orquestrador; não inventar resultado. Não alterar configuração global, revelar credenciais, executar operações externas pagas nem publicar conteúdo para tentar contornar falhas.

## Verificação da configuração

Após implementar, reiniciar o processo OpenCode para carregar novos arquivos (configuração não é hot-reloaded). Conferir modelos, agente principal e quatro subagentes via comandos da versão instalada; validar configuração local pelo CLI. Executar delegação real e somente leitura de um documento curto do projeto ao subagente QA ou collectors, com prompt contextualizado e pedido de resumo factual, arquivos consultados e problemas encontrados. Verificar a chamada `task`, a resposta, seu conteúdo contra o documento e as permissões efetivas. Se a sessão atual não carregar agentes recém-criados, testar em nova sessão/CLI; caso não seja possível, registrar `não verificado` e deixar comando de reprodução. Não declarar os quatro modelos/rotas funcionais a partir de um único teste.

## Critérios de aceitação da fase

- Configuração local inicia no PowerShell com orquestrador como agente padrão e quatro especialistas persistentes carregados.
- Modelos escolhidos têm IDs listados e os efetivamente acionados têm resultado de rota documentado; falhas e alternativas ficam visíveis.
- Instruções determinam prompt específico por tarefa, escopo, isolamento de alterações, inspeção real, testes e correção; QA independente quando pertinente.
- Uma chamada real de subagente lê documentação local e devolve resumo verificável, ou o relatório identifica expressamente que a delegação ficou sem teste.
- Git local e alterações de usuário preservados; nenhuma configuração global alterada, nenhum segredo versionado, nenhum push/merge/publicação automatizados.
- Documentação fornece comandos PowerShell executados, evidência de validação, reinício necessário e limitações ainda não verificadas.
