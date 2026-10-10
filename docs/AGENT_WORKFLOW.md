# Fluxo de agentes

O usuário fala apenas com `orquestrador`, agente primário padrão do projeto. O orquestrador inspeciona Git, docs, código e stack; define aceitação, contratos, riscos, tarefas e ordem. Só delega via `task` se isso fizer sentido. Decisões de produto sem base são escaladas ao usuário; decisões rotineiras de roteamento pertencem ao orquestrador.

## Prompt obrigatório por tarefa

Cada delegação recebe conteúdo adaptado, com: 1 ID e objetivo; 2 contexto funcional; 3 arquivos/módulos pertinentes; 4 diagnóstico real; 5 responsabilidade do agente; 6 escopo permitido; 7 proibições; 8 dependências/contratos; 9 regras de domínio aplicáveis; 10 skills disponíveis a consultar; 11 testes a escrever/executar; 12 critérios objetivos; 13 formato do retorno (arquivos, decisões, testes, achados); 14 condições para parar/avisar. O texto permanente dos agentes define o papel; o prompt não amplia permissão.

## Execução e integração

O orquestrador estabelece contratos antes das implementações dependentes, divide áreas de escrita e só paraleliza tarefas sem arquivos/contratos compartilhados. Usa isolamento por branch/worktree se necessário e compatível com Git. Após cada retorno, consulta arquivos/diff, executa testes pertinentes e verifica afirmações; devolve defeitos concretos para correção. Solicita QA independente sempre que houver mudança relevante a revisar e registra se o modelo coincide com o do implementador. Integra somente quando as verificações reais passam. Não há merge em `main`, push nem publicação automática. Subagentes não podem invocar outros subagentes nesta configuração.

Todos os agentes têm regras diretas `bash` para negar `git push*`, `git merge*` e `git reset --hard*`; os cinco agentes negam `pc_*` para evitar uma segunda rota de execução local e QA é somente leitura por padrão. Permissões do OpenCode aplicam-se à ferramenta e ao padrão de comando: **não são sandbox do sistema operacional** e não impedem equivalentes indiretos dentro de programas permitidos. Alterações com efeitos relevantes ainda exigem coordenação e autorização humana. Backend não usa o navegador; frontend pode usá-lo para testes de UI e collectors para fontes oficiais.

## Prova controlada

O documento `docs/DELEGATION_PROBE.md` tem duas frases verificáveis. Em processo novo, chamar `opencode run --agent orquestrador --format json` com pedido para delegar leitura somente ao `qa`. Conferir evento real da ferramenta `task`, retorno do subagente e aderência ao texto. Uma resposta sem evento `task` não comprova delegação.

**Resultado em 2026-10-09:** `opencode run --agent orquestrador --format json '<prompt RADAR-TEST-001 de leitura somente pelo qa>'` terminou com código 0. Evento `task` concluído com alvo `qa`; sessão primária `ses_edd351727ffehpOsE7cYr7pKzn`, sessão filha `ses_edd33c812ffeWbw2hsxDOHDpZM`. Inspeção da sessão filha com `opencode export <id>` em memória mostrou `read` concluído no caminho local `docs/DELEGATION_PROBE.md`; o retorno QA transcreveu corretamente as duas frases e declarou nenhum problema e nenhuma escrita. O orquestrador examinou o documento depois da delegação. Não foi necessária aprovação manual de ferramenta. Isto comprova **uma** delegação e as rotas do orquestrador e QA; não exercita backend, collectors, frontend, paralelismo ou segurança contra bypass de shell. Para repetir, use o comando concreto em `README.md` e `--format json` para verificar o evento.

**Segunda prova em 2026-10-09:** `opencode run --agent orquestrador --format json '<prompt RADAR-TEST-002 de leitura somente pelo collectors>'` terminou com código 0 e evento `task` concluído para `collectors`. A sessão filha `ses_edd2d70c1ffeXrKheZN5PYCtP5` registrou `read` concluído em `docs/AGENT_WORKFLOW.md` e relatou corretamente o resultado da seção Prova controlada. Sem alterações observadas no documento. Isso valida outra rota e agente, não coleta real.
