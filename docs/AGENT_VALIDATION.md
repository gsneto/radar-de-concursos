# Fase 2 — validação de modelos e agentes

Data: 2026-10-09. Escopo: configuração e tarefas documentais, sem implementação do produto nem alteração de modelos.

## Ambiente e Git

- OpenCode CLI `1.18.35`. `opencode debug config` aponta `default_agent=orquestrador`. `opencode agent list` e `opencode debug agent <nome>` carregaram os cinco agentes abaixo no projeto.
- Git local na branch `radar-configuracao`, sem commits e sem remoto. Antes da criação deste relatório havia 16 arquivos não rastreados; nenhum foi descartado ou sobrescrito. Não houve commit, push ou merge.
- Listagem de arquivos não rastreados, pesquisa por nomes e padrões de chave/token/PEM e `git check-ignore -v .env .env.example` não encontraram segredo em arquivos candidatos; `.env` está ignorado e `.env.example` não. A busca por padrões não prova ausência absoluta de segredos: inspecione novamente antes de qualquer `git add` e selecione explicitamente os arquivos desejados.

## Divergência do modelo central

O arquivo `.opencode/agents/orquestrador.md` usa `inferhub/cb/gpt-5.5`, resolvido pelo OpenCode como `providerID=inferhub`, `modelID=cb/gpt-5.5`. Este ID está no catálogo e **respondeu** em sessões reais com chamadas `task`. A preferência inicial dizia literalmente **“the model 5.5”**, expressão que não identifica inequivocamente um ID nem prova que corresponda a GPT 5.5. No catálogo consultado por `opencode models inferhub` constam `inferhub/cb/gpt-5.5`, `inferhub/gpt-5.5` e `inferhub/kiro-opus-5.5`; em `opencode models opencode` constam `opencode/gpt-5.5` e `opencode/gpt-5.5-pro`. Somente **`inferhub/cb/gpt-5.5`** foi exercitado aqui. Não foi demonstrado que os IDs alternativos correspondam à preferência textual, estejam autorizados na conta ou tenham rota estável.

**Recomendação:** manter o modelo central atual, cuja rota funcionou, sem troca automática. Antes de considerar outro ID, esclarecer qual modelo concreto a preferência representa, conferir catálogo/condições e testar a rota com tarefa pequena; custo e qualidade comparativa não foram medidos.

## Agentes e provas

| Agente | Modelo configurado | Invocação real | Ferramentas observadas na sessão filha | Resultado e pendências |
| --- | --- | --- | --- | --- |
| orquestrador | `inferhub/cb/gpt-5.5` | `opencode run --agent orquestrador --format json` (saída 0) | `task` concluída para backend/frontend; também QA/collectors | Gerou prompts de auditoria específicos e conferiu documentos; execução de ações de escrita e integração de produto não testada. |
| backend | `inferhub/cbcn/deepseek-v4-pro` | `task` concluída; `ses_edd15de35ffeg3KVFr3mVEzDjY` | `read` de `AGENTS.md`, definição do agente, README e spec; `skill verification-before-completion` concluída | Citou corretamente `AGENTS.md:11` (vagas imediatas ≠ reserva) e FastAPI condicional na definição. Não testados bash, edição, testes de backend ou API. |
| collectors | `inferhub/cb/deepseek-v4.1-flash` | `task` concluída; `ses_edd0d2c5dffeqwTUUVZ1uvBKy7` | `read` de `AGENTS.md`; `skill verification-before-completion` concluída | Identificou fonte oficial/data de verificação; teste anterior `ses_edd2d70c1ffeXrKheZN5PYCtP5` leu `docs/AGENT_WORKFLOW.md`. Não testados coletor real, browser, normalização ou falhas externas. |
| frontend | `inferhub/ali/deepseek-v4-pro-0813` | `task` concluída; `ses_edd148674ffeEpo0H4zawFEbR1` | `read` de `AGENTS.md`, definição do agente, README e spec; `skill verification-before-completion` concluída | Citou corretamente `AGENTS.md:14` (não inventar dados) e React/TypeScript condicional na definição. Não testados browser, edição, build ou integração de API. |
| qa | `inferhub/cb/glm-5.3` | `task` concluída; `ses_edd0eb732ffecCqaiE1NY6Z5HD` | `read` de `AGENTS.md`; `skill verification-before-completion` concluída | Identificou zero ≠ desconhecido; teste anterior `ses_edd33c812ffeWbw2hsxDOHDpZM` leu e transcreveu o documento de prova. Não testados bash, suíte de produto ou autorização de escrita (negada na configuração). |

Evidência: execução nova do `opencode run` com saída JSON produziu eventos `tool=task`, `state.status=completed` e alvos `backend`, `frontend`, `qa`, `collectors`. `opencode export <session-filho>` mostrou modelo efetivo, `read` concluído em caminhos locais e `skill` concluída com argumento `verification-before-completion` para **cada uma das quatro sessões filhas**; trechos devolvidos foram comparados aos arquivos do repositório. Reaproveitar as duas provas documentais anteriores evitou repetir testes extensos. Não foi necessária aprovação de ferramenta nos testes de leitura. `opencode debug skill` listou 50 skills, incluindo brainstorming, writing-plans, test-driven-development, systematic-debugging e verification-before-completion; listagem no principal, isoladamente, não é evidência de acesso em sessões filhas — as quatro chamadas `skill` acima são.

`opencode debug agent` confirmou `task` permitido aos quatro especialistas apenas no primário, `task: deny` nos filhos; `edit: deny` para QA e regras diretas negando `git push*`/`git merge*` nos cinco agentes. São regras efetivas carregadas, mas **não foram exercitadas por tentativa de operação proibida**. As permissões do OpenCode não formam uma sandbox contra comandos equivalentes indiretos. Não há código de produto nem suíte de produto para executar nesta fase.

## Distribuição recomendada e Jev

Manter a distribuição configurada: as cinco rotas responderam em tarefas pequenas, QA usa família de modelo diferente da dos implementadores, e não há dados de custo/desempenho comparativo que justifiquem troca. Resposta documental não comprova aptidão para tarefas complexas, uso de todas as ferramentas nem disponibilidade futura das rotas.

Jev permanece **opcional e não integrado**, conforme decisão posterior do usuário de deixar para depois. A documentação TypeSafe apresenta o endpoint específico `POST https://api.typesafe.ai/v1/systemone`, perguntas tipadas `choice`/`score`/`noul`, modelo anunciado `jev-1.13.0` e preço publicado de US$ 0,042 por milhão de tokens de entrada; não é substituto do modelo de chat OpenCode. A verificação anterior alcançou o endpoint (GET respondeu 405) mas não havia `TYPESAFE_API_KEY`, portanto acesso autenticado e custo real da conta seguem desconhecidos. Uma futura ferramenta local opcional precisaria validar esquemas, impor timeout/fallback e comparar resultados/custos no mesmo conjunto de casos. **Nesta fase não houve instalação, configuração, chamada paga nem alteração da arquitetura para Jev**; o fluxo sem Jev já foi usado nos testes acima.

## Reproduzir sem expor credenciais

No PowerShell, na raiz do projeto: `opencode --version`; `opencode models inferhub`; `opencode agent list`; `opencode debug agent backend`; `opencode debug skill`. Para comprovar invocação por agente, rodar `opencode run --agent orquestrador --format json '<pedido de delegação somente leitura por task>'` e conferir `tool=task`, alvo e estado; usar `opencode export <session-filho>` com cuidado, pois exportações brutas contêm texto das sessões. Não colar dumps completos nem segredos em relatórios. Após alterações de agente/configuração, abrir processo novo do OpenCode.
