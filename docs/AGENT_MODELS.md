# Modelos dos agentes

Confirmado por listagem `opencode models inferhub` no OpenCode 1.18.35 em 2026-10-09. Um modelo listado não equivale a requisição aceita. Custos do catálogo não foram verificados contra cobrança.

| Agente | ID configurado | Uso | Rota invocada nesta fase |
| --- | --- | --- | --- |
| orquestrador | `inferhub/cb/gpt-5.5` | planejamento e integração | sim: `opencode run` saiu 0 e concluiu `task` |
| backend | `inferhub/cbcn/deepseek-v4-pro` | regras, API e persistência | sim: tarefa documental e skill em sessão filha; implementação não testada |
| collectors | `inferhub/cb/deepseek-v4.1-flash` | conectores delimitados | sim: delegação somente leitura, `read` concluído |
| frontend | `inferhub/ali/deepseek-v4-pro-0813` | interface e integração | sim: tarefa documental e skill em sessão filha; implementação não testada |
| qa | `inferhub/cb/glm-5.3` | revisão independente, diferente da família dos implementadores | sim: sessão filha leu o arquivo e retornou os dois fatos |

As escolhas são preferências operacionais, não afirmações de benchmark. Se uma rota não funcionar, valide uma alternativa listada (por exemplo `inferhub/cb/gpt-5.4` para o orquestrador e `inferhub/ali/deepseek-v4.1-flash` para tarefas delimitadas), atualize apenas a definição local do agente correspondente e registre o resultado. Não introduza ID apenas pelo nome comercial. Para tarefas de complexidade distinta, escolha rota adequada, documente e valide antes de afirmar sua funcionalidade.

Testes controlados em 2026-10-09: as cinco rotas produziram respostas em sessões reais do OpenCode; backend e frontend foram confirmados na [validação da fase 2](AGENT_VALIDATION.md). Uma prova documental não comprova capacidade de implementar módulos, conectar fontes reais nem usar todas as ferramentas. A expressão inicial “the model 5.5” é ambígua e não identifica automaticamente `inferhub/cb/gpt-5.5`; mantenha o modelo central testado até esclarecer o ID pretendido e testar qualquer alternativa.
