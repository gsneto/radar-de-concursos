# Radar de Concursos

Fase 3: fluxo vertical local para **uma fonte oficial** — artigo da Prefeitura Municipal de Guajará-Mirim/RO sobre o concurso da educação nº 001/2026. Backend Python 3, SQLite e interface HTML/CSS/JavaScript. A fonte inicial produziu quatro cargos (69, 32, 3, 3). O histórico de documentos permite registrar, baixar e interpretar HTML/PDF textuais, sempre como **propostas** que exigem revisão. O edital nº 001/2026 foi obtido e processado como prova real (HTML da matéria e PDF da edição do Diário Oficial dos Municípios), sem validação automática de fatos. Consulte a [especificação do histórico](docs/superpowers/specs/2026-10-10-historico-documental-radar-design.md).

## Executar localmente

No PowerShell, na raiz do repositório, com Python 3 disponível:

```powershell
python -m unittest discover -s tests -v
python -m radar collect --db .\data\radar.sqlite3
python -m radar serve --db .\data\radar.sqlite3
```

Os testes documentais de PDF dependem de `pypdf` conforme `requirements.txt`. No ambiente local de desenvolvimento já preparado, use `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe` no lugar de `python` se o Python padrão não tiver a dependência. Uma falha `ModuleNotFoundError: pypdf` indica ambiente incompleto, não sucesso da suíte.

Crie a pasta `data` antes de usar esse caminho (`New-Item -ItemType Directory -Path .\data`) ou forneça outro caminho de banco existente, por exemplo `--db .\radar.sqlite3`. O servidor escuta em `127.0.0.1:8000` por padrão. Abra `http://127.0.0.1:8000/` e consulte `http://127.0.0.1:8000/api/concursos`. Interrompa o servidor com `Ctrl+C`. `collect` atualiza a fonte sob demanda; executar novamente não duplica os cargos. Se a página mudar ou estiver indisponível, a coleta falha sem apagar registros previamente armazenados. O SQLite local é ignorado pelo Git.

Para experimentar a interface vazia, use um novo banco ainda não criado: `python -m radar serve --db .\radar-vazio.sqlite3`. Falhas de API exibem estado de erro e botão para tentar novamente. O frontend não contém dados oficiais embutidos.

**Limite de atualidade:** `verified_at` marca quando o artigo foi consultado para a coleta, não quando o edital e as retificações foram conferidos. A situação atual do certame e das inscrições não foi verificada. Escolaridade, vagas de cadastro de reserva e vagas indígenas numéricas, local de prova e local de exercício permanecem desconhecidos (`null`) sem evidência por cargo. Antes de tomar decisões sobre inscrição ou carreira, consulte o edital e as retificações nos links da [página oficial](https://guajaramirim.ro.gov.br/prefeitura-de-guajara-mirim-abre-inscricoes-para-concurso-publico-da-educacao-com-107-vagas-e-cadastro-de-reserva/). Se a lista de cargos mudar entre coletas, o comando falha e mantém os registros anteriores para revisão manual; não substitui nem apaga cargos automaticamente.

Contagens globais positivas de cadastro de reserva ou de vagas indígenas sem distribuição explícita por cargo não são atribuídas aos registros de cargos; permanecem `null`. Declaração expressa de inexistência de cadastro de reserva com zero vagas pode ser representada como `0`. Consulte também o [registro de trabalho](docs/AUTONOMOUS_WORK_LOG.md) para limitações e prioridades atuais.

## Histórico documental local

Faça backup do banco antes de migrar um banco de uso real. Para testes, use um banco temporário. A migração é explícita, aditiva e transacional; pode ser repetida e não altera `concursos`. A versão corrente do esquema documental é **3** (base v2 mais reconciliação de cargos e hash de comparação); bancos v2 são atualizados pela mesma migração. A sincronização explícita cria identidades para linhas v1 sem alterar a lista. Código v1 continua lendo o mesmo banco; reversão da aplicação não exclui tabelas ou arquivos documentais.

```powershell
python -m radar documents-migrate --db .\data\radar.sqlite3
python -m radar documents-sync --db .\data\radar.sqlite3
python -m radar documents-register --db .\data\radar.sqlite3 --observation-id UUID --kind edital --url https://guajaramirim.ro.gov.br/edital.pdf --title Edital
python -m radar documents-fetch --db .\data\radar.sqlite3 --document-id UUID
python -m radar documents-analyze --db .\data\radar.sqlite3 --version-id UUID
python -m radar documents-review --db .\data\radar.sqlite3 --proposal-id UUID --decision validado --reviewer NOME --reason "Trecho conferido"
python -m radar documents-reconcile --db .\data\radar.sqlite3 --contest-id UUID --label "RÓTULO DO CARGO NO DOCUMENTO" --role-id UUID --reviewer NOME --reason "Cargo conferido no Anexo I"
python -m radar documents-link-amendment --db .\data\radar.sqlite3 --amendment-id UUID --original-id UUID --reviewer NOME --reason "Retificação do mesmo certame"
python -m radar documents-select --db .\data\radar.sqlite3 --proposal-id UUID --reviewer NOME --reason "Escolha fundamentada"
python -m radar documents-coverage --db .\data\radar.sqlite3 --contest-id UUID --state parcial --checked-url https://guajaramirim.ro.gov.br/edital.pdf --reviewer NOME --checked-at 2026-10-10T12:00:00+00:00 --note "Escopo conferido"
```

Consulte `GET /api/concursos/identidades` para identificar UUIDs e observações e `GET /api/concursos/{uuid}/detalhes` para documentos, versões, tentativas, eventos, propostas, evidências, revisões, `role_reconciliations` e seleções históricas (`active` marca a seleção validada vigente). Cada proposta pode trazer `reconciled_role_id` quando seu rótulo foi reconciliado. `GET /api/concursos` mantém o contrato anterior de 18 campos e seu `verified_at` refere-se **somente ao artigo**. Antes da migração, as rotas documentais retornam 503; antes da sincronização, o índice pode estar vazio. Os arquivos originais ficam no diretório local `NOME_DO_BANCO.documents/`, por SHA-256, sem rota pública de bytes.

Documento localizado não significa baixado; versão baixada não significa analisada; proposta não significa validada; cobertura não auditada ou parcial não prova ausência de retificações. Downloads documentais aceitam HTTPS público e URLs `.pdf`, `.html` ou `.htm` no host permitido; limite de 20 MiB, 15 segundos e até 3 redirecionamentos. Extração inicial suporta HTML UTF-8 e PDF **textual** até 400 páginas, sem OCR. PDF criptografado, malformado, digitalizado ou sem texto permanece sem propostas; análise inválida registra `error_code` e evento de falha. Inscrições com período impossível identificado geram diagnóstico `invalid_registration_period`, sem data proposta. Se um download falhar, consulte `download_attempts` e `events` no detalhe; uma versão anterior íntegra permanece. URLs com acesso restrito não devem ser contornadas.

### Fontes autorizadas

O adaptador de domínio (`radar/document_discovery.py`) autoriza, por enquanto: `guajaramirim.ro.gov.br` (arquivos `.pdf`/`.html`/`.htm`) e `www.diariomunicipal.com.br` (apenas caminhos `/arom/materia/`, `/arom/download/materia/` e `/arom/download/edicao/`). Ampliar a lista exige justificativa e revisão; a validação de esquema HTTPS, host, porta e endereço público permanece em cada requisição e redirecionamento.

### Extração de tabelas e cotas

O extrator HTML agrupa cada linha de tabela em um bloco citável (`locator` "linha de tabela"). A partir de um cabeçalho com `VAGAS TOTAIS` e `INDÍGENAS`, o quadro de cotas produz propostas de vagas totais e de vagas indígenas **por linha**, com a linha como evidência. A linha `TOTAL` vira proposta de escopo do concurso; as linhas de cargo ficam `ambiguo` com `ambiguity_reason` do rótulo do documento, pois o cargo do edital ainda não foi reconciliado com a identidade do Radar. O total indígena nunca é copiado para cada cargo e o cadastro de reserva (`+ CR*`) permanece desconhecido, sem virar zero. A varredura para no fim da tabela do cabeçalho, sem capturar tabelas posteriores.

Para PDF **textual**, o quadro é reconhecido pela âncora `QUADRO GERAL DE VAGAS` mais os tokens do cabeçalho e a linha `TOTAL`, lendo as linhas por cargo (seis inteiros por linha). Como a edição diária reúne vários atos, toda proposta de PDF não ancorada (inclusive o `TOTAL` do quadro e as datas genéricas) recebe `ambiguity_reason` de escopo (`PDF_SCOPE_REASON`), exigindo conferência humana; apenas as linhas por cargo trazem o rótulo para reconciliação. O quadro de cotas não é emitido para documentos já restritos a um cargo.

### Retificações e conflitos

Uma retificação é registrada como **documento distinto** (`--kind retificacao`), com sua própria identidade, hash e evidências; `documents-link-amendment` liga-a ao documento original por decisão humana (revisor e justificativa), gravando um evento `retificacao` com `related_document_id`. O detalhe expõe `related_document_ids` em cada documento. A versão e as evidências originais permanecem imutáveis; nenhuma proposta é promovida automaticamente.

O detalhe inclui `conflicts[]`, que agrupa propostas por escopo efetivo (cargo reconciliado, rótulo de cargo não reconciliado ou escopo do concurso) e campo, listando valores divergentes com `proposal_id`, `version_id` e `document_id`. Escopos diferentes (por exemplo, uma cota por cargo e o total do concurso) **não** geram conflito falso. Todo `evidence` inclui `document_id`, permitindo verificar qual documento fundamentou um valor selecionado. Um conflito só vira valor corrente após `documents-review` (validado) e `documents-select`, mantendo o histórico de decisões. Reprocessar a mesma retificação não duplica documento nem versão; conteúdo substantivamente diferente gera nova versão encadeada por `previous_version_id`.

> Nota de estado: nesta sessão **não** foi localizada uma retificação oficial real do edital 001/2026. O fluxo foi implementado e testado com uma fixture **sintética** identificada em `tests/fixtures/documents/retificacao-sintetica.html` (não é documento oficial). A validação com retificação real permanece pendente.

### Reconciliação de cargos

O rótulo de cargo do documento (ex.: `Prof. Magistério Nível II 30 h – Educação Infantil`) não casa automaticamente com a identidade canônica do Radar. `documents-reconcile` registra, por decisão humana com revisor e justificativa, o vínculo entre um rótulo evidenciado e um `role_id` do mesmo concurso. O sistema recusa rótulo sem evidência documental e recusa mapear o mesmo rótulo para cargos diferentes; a decisão é idempotente e fica em `reconciliacoes_cargo` (append-only). A projeção expõe `reconciled_role_id` por proposta e `role_reconciliations` no detalhe; ao selecionar um valor corrente, a seleção herda o cargo reconciliado quando a proposta não tem cargo direto. Não há correspondência por similaridade textual.

### Hash bruto e hash de comparação

Cada versão guarda duas impressões: o `sha256` **bruto** dos bytes armazenados (integridade, reprodução e evidência) e um `comparison_sha256` de **comparação**, que normaliza apenas o conteúdo de scripts de telemetria identificados estruturalmente (`bam.nr-data.net`, `NREUM.info`). Bytes brutos diferentes que só variam em telemetria passam a apontar para a mesma versão, reduzindo versões artificiais sem esconder mudanças substantivas no quadro de vagas, no período de inscrições ou nas regras de cotas. PDFs não têm elementos voláteis conhecidos; para eles o hash de comparação é igual ao bruto.

### Limite de idempotência por fonte

A idempotência é por conteúdo: bytes idênticos devolvem a mesma versão. Algumas fontes oficiais inserem telemetria volátil no HTML (por exemplo, o campo `applicationTime` do New Relic no Diário Oficial dos Municípios), de modo que duas consultas à mesma página geram bytes diferentes. O hash de comparação reconhece esse caso e **não** cria versão nova, mantendo o hash bruto da versão original; quando os bytes diferem de fato, cria uma versão adicional encadeada por `previous_version_id`. Para PDFs, a idempotência continua sendo apenas por bytes brutos.

## Configuração de agentes OpenCode

No PowerShell:

```powershell
opencode 'C:\Users\anton\OneDrive\Desktop\radar-de-concursos'
```

Dentro da sessão, converse normalmente com `orquestrador` (agente principal padrão). Após alterar `opencode.json` ou `.opencode/agents/`, encerre e reinicie o OpenCode para recarregar. Diagnósticos a partir do diretório do projeto:

```powershell
opencode --version
opencode models inferhub
opencode agent list
opencode debug agent orquestrador
opencode run --agent orquestrador 'Leia AGENTS.md e resuma o objetivo desta fase.'
```

Veja [fluxo](docs/AGENT_WORKFLOW.md), [modelos](docs/AGENT_MODELS.md), [Superpowers](docs/OPENCODE_SUPERPOWERS.md) e [desenho aprovado](docs/superpowers/specs/2026-10-09-radar-orquestracao-opencode-design.md). `opencode debug agent` pode produzir saída longa; evite salvar ou compartilhar dumps completos de configurações globais.

A [validação individual dos cinco agentes](docs/AGENT_VALIDATION.md) registra rotas exercitadas, skills carregadas nas sessões filhas, limites de teste e a decisão de manter Jev opcional.

Para repetir a prova somente leitura em processo novo, no diretório do projeto:

```powershell
opencode run --agent orquestrador --format json 'Teste RADAR-TEST-001: delegue pelo task ao agente qa a leitura exclusiva de docs/DELEGATION_PROBE.md, sem editar nada; peça dois fatos, arquivo consultado e problemas encontrados. Confira a resposta após o retorno e identifique a chamada task.'
```

Inspecione o evento `task` concluído com alvo `qa` e o `read` da sessão filha; a saída JSON pode conter mensagens completas, então não a publique sem revisão. O exemplo de invocação acima usa as opções efetivamente suportadas pela CLI; uma nova execução terá novos IDs de sessão.
