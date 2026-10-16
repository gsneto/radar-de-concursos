# Monitoramento automático de editais e retificações — desenho arquitetural

## Intenção e limites

Transformar o histórico documental existente em um **mecanismo de monitoramento**: um comando repetível que consulta as fontes oficiais autorizadas, descobre documentos novos, compara os já conhecidos, registra novas versões quando há mudança, sinaliza o que precisa de análise humana e registra falhas — sem promover nada automaticamente.

Sucesso significa: (1) existir um comando local que executa **um ciclo** e termina; (2) cada ciclo ficar persistido com estado verificável; (3) o sistema distinguir documento novo, mudança substantiva, mudança só de telemetria e repetição; (4) uma falha de fonte ser registrada sem apagar o último resultado válido e sem impedir as demais fontes; (5) os 18 campos de `GET /api/concursos` permanecerem intactos; (6) a interface mostrar o estado do monitoramento; (7) a documentação explicar execução e agendamento.

Não-objetivos: processo residente contínuo; infraestrutura externa (Redis, Celery, filas); serviços pagos; varredura em massa; contornar bloqueios; declarar cobertura completa sem auditoria humana.

## Comparação de estratégias (A/B/C)

| Estratégia | Robustez | Recursos | Recuperação pós-reinício | Testabilidade | Windows/OpenCode |
|---|---|---|---|---|---|
| A. Só comando manual | Alta (nada implícito) | Mínimo | Não aplicável | Alta | Trivial — mas não é "automático" |
| B. Comando repetível + Agendador de Tarefas do Windows | Alta (o agendador reinicia a tarefa) | Mínimo (processo só durante o ciclo) | Sim (tarefa agendada roda de novo) | Alta (um ciclo por invocação) | Nativo; não depende de sessão de IA |
| C. Processo contínuo dedicado | Requer supervisão, watchdog e reinício | Contínuo (RAM/CPU ociosos) | Só com serviço/supervisor próprio | Baixa (estado de longa duração) | Mais frágil; sem ganho para fonte de baixa frequência |

**Escolha: B.** É a alternativa mais simples que entrega monitoramento efetivo e evolui depois. O comando executa **um** ciclo e encerra (nunca loop infinito interno). O Agendador de Tarefas do Windows fornece periodicidade e recuperação após reinício, sem depender de sessão do modelo aberta. Não adicionamos Redis/Celery/serviços pagos — não há necessidade demonstrada para uma fonte de baixa frequência.

## Limites de módulos e fluxo

1. `radar/document_discovery.py` — permanece a autoridade de **quais** URLs/links são aceitos por adaptador de fonte (`allowed_document_url`). O monitoramento reutiliza `discover_documents`; não cria allowlist paralela.
2. `radar/document_download.py` — permanece a autoridade de download validado (TLS, peer público, MIME, limites). O monitoramento reutiliza `download_document` com transporte injetável em teste.
3. `radar/document_store.py` — ganha apenas **tabelas novas** (ciclos) na migração aditiva `user_version=4`; nenhuma tabela/coluna existente é alterada ou removida. `comparison_fingerprint` e `record_version` permanecem a base de deduplicação.
4. `radar/monitoring.py` (novo) — orquestra o ciclo: consulta fonte, descobre, compara, registra versões, classifica mudanças, persiste ciclo e devolve resumo. Não contém regra de download nem de extração; delega.
5. `radar/document_extract.py` / `document_fields.py` / `document_review.py` — reutilizados como estão para a análise opcional do ciclo; o monitoramento **nunca** valida proposta.
6. `radar/server.py` — ganha **uma rota GET nova** de status; a lista v1 fica idêntica byte a byte.
7. `web/` — a interface existente ganha um painel de monitoramento; sem novo frontend.

Fluxo de um ciclo: fontes autorizadas → fetch da página de descoberta → candidatos (`discover_documents`) → registro idempotente de documentos novos → download/versão de documentos conhecidos (`record_version`) → classificação da mudança → persistência do ciclo e por-fonte → resumo. Análise de campos é opcional e nunca aprova.

## Detecção de mudanças sem falsos alertas

Base: `sha256` (bytes brutos) e `comparison_fingerprint` (conteúdo documental, normalizando apenas scripts de telemetria comprovada) já implementados.

Classificação por documento conhecido, após tentar baixar:

| Situação | Detecção | Resultado |
|---|---|---|
| Sem mudança (mesmos bytes) | `record_version` devolve versão existente (`UNIQUE(document_id,sha256)`) | nenhuma versão nova; **sem alerta** |
| Mudança só de telemetria | bytes novos, mas `comparison_sha256` já presente | nenhuma versão nova; **sem alerta**; situação registrada como volátil |
| Mudança substantiva | `record_version` cria versão nova | versão nova → **alerta** "mudança pendente de análise" |
| Mudança não classificável | `comparison_fingerprint` para não-HTML é o próprio `sha256`; qualquer diferença cria versão | versão nova → alerta; marcar para revisão |
| Documento novo | `register_document` cria id inédito | alerta "novo documento" |
| Repetição em consultas sucessivas | registro/versão idempotentes | **sem alerta duplicado** |
| Link ausente na página | não prova remoção | **sem** marcação de remoção; apenas nota de cobertura |

Regras firmes: a ausência de um link numa consulta isolada **não** marca documento como removido; uma alteração de HTML **não** é tratada como retificação; uma versão nova **não** promove propostas a valores validados; `valores_atuais` nunca é criado pelo monitoramento.

## Persistência do estado (migração aditiva v4)

Duas tabelas novas, append-friendly e idempotentes por chave:

| Tabela | Colunas | Restrições |
|---|---|---|
| `ciclos_monitoramento` | `id` UUID, `started_at`, `finished_at` opcional, `state` (`em_andamento`,`concluido`,`parcial`,`falhou`,`interrompido`), `documents_found`, `documents_new`, `versions_new`, `changes_pending`, `last_success_at` opcional | Uma linha por ciclo; `CHECK` nos estados e contadores `>= 0`. |
| `ciclos_fontes` | `id` UUID, `cycle_id` FK, `source_url`, `state` (`concluido`,`parcial`,`falhou`,`nao_verificada`), `checked_at`, `last_success_at` opcional, `http_status` opcional, `error_code` opcional, `documents_found`, `documents_new`, `versions_new`, `changes_pending`, `coverage_state`, `summary_json` | `UNIQUE(cycle_id, source_url)`; `CHECK` nos estados e contadores `>= 0`. |

Regras de estado:
- O ciclo começa `em_andamento`. Ao terminar: todas as fontes `concluido` → `concluido`; ao menos uma falha e ao menos uma ok → `parcial`; todas falharam → `falhou`.
- Se, ao iniciar, existir ciclo `em_andamento` anterior (interrompido), ele é marcado `interrompido` (recuperação) **antes** de abrir o novo — nenhum dado anterior é apagado.
- `last_success_at` só avança em ciclo/fonte com resultado válido; falha preserva o último valor.
- Fonte ainda não consultada → `nao_verificada`.

Migração: `migrate_document_schema` passa a aceitar `user_version` 0/2/3/4 e aplica v4 idempotentemente (`_apply_v4`, tolerante a banco parcialmente atualizado). Leitura (rotas) aceita 2/3/4 e **não** migra. Nenhuma migração destrutiva em banco real; v4 testada com bancos temporários novos e existentes (v2 e v3).

## Contratos públicos

- `GET /api/concursos` — **inalterado** (18 campos, mesma ordem e significados).
- `GET /api/concursos/identidades` e `GET /api/concursos/{uuid}/detalhes` — inalterados.
- **Novo** `GET /api/monitoramento` — leitura JSON, somente GET. Retorna:

```json
{
  "last_cycle": {"id": "...", "state": "concluido", "started_at": "...", "finished_at": "...",
                 "documents_found": 0, "documents_new": 0, "versions_new": 0, "changes_pending": 0},
  "sources": [{"source_url": "...", "state": "concluido", "checked_at": "...", "last_success_at": "...",
               "coverage_state": "nao_auditada", "documents_found": 0, "documents_new": 0,
               "versions_new": 0, "changes_pending": 0, "http_status": 200, "error_code": null}],
  "pending_analysis": 0,
  "coverage_state": "nao_auditada"
}
```

Sem `local_path` nem bytes. Banco não migrado → `503` (`{"error":"Migracao documental pendente"}`), sem criar tabelas. Nunca expõe `last_checked_at` como prova de cobertura total.

## Comando executável e agendamento

Comando: `python -m radar monitor --db PATH [--analyze]`.

1. Exige esquema documental migrado (senão erro claro apontando `documents-migrate`); não migra sozinho.
2. Executa `sync_v1_identifiers` (idempotente) para garantir observações.
3. Recupera ciclo `em_andamento` anterior como `interrompido`.
4. Abre o ciclo e consulta cada fonte autorizada **em try/except independente** (uma falha não impede as demais).
5. Descobre/registra documentos, baixa/compara conhecidos, classifica mudanças.
6. Persiste ciclo e por-fonte; imprime resumo JSON verificável.
7. Termina com código 0 em sucesso/parcial e não-zero apenas em erro de configuração irrecuperável. Nunca faz loop infinito.

Agendamento: instruções para o **Agendador de Tarefas do Windows** (`schtasks`/GUI), executando o comando a cada N horas com o venv do projeto. A preparação é documental; **não** habilitamos tarefas que gerem cobranças, downloads ilimitados ou efeitos externos sem pedido explícito.

## Revisão documental e validação humana

Documento novo ou versão nova: a versão é registrada e fica `nao_iniciada`. Com `--analyze`, o ciclo extrai blocos e propostas (reutilizando `document_analyze`), associando evidências à versão correta; campos afetados aparecem como propostas `extraido`/`ambiguo`, pendentes de revisão. Nunca invalida o edital inteiro por uma retificação pontual; nunca atualiza valor vigente por existir versão mais recente; todas as decisões anteriores são preservadas.

## Segurança, atualidade e falhas

Reutiliza as defesas de `document_download` (HTTPS, host/rota autorizados, peer público, MIME suportado, limites de bytes/tempo/redirecionamento) e de `document_discovery` (allowlist por fonte). Não envia cookies nem credenciais; não segue URL arbitrária. Falhas são persistidas com `error_code` redigido (tipo de erro), sem segredos, sem apagar o último resultado válido e sem avançar `last_success_at`. Uma fonte que não permite descoberta confiável é registrada como limitação (`coverage_state`), nunca simulada como cobertura completa.

## Testes

Fixtures locais, sem rede externa (transporte e fetch injetáveis). Cobrem: nenhum documento novo; um documento novo; mesma URL e mesmo conteúdo; mesmo conteúdo com telemetria volátil; mudança substantiva; nova retificação; documento inacessível; timeout de fonte; erro de download; falha de extração; execução repetida; recuperação de ciclo interrompido; persistência de falhas; ausência de alertas duplicados; preservação da API v1; registros desconhecidos/vazios; uma fonte falhando não impede as demais. Teste real da fonte oficial só se permitido e viável; caso contrário, documentar a limitação e não afirmar verificação real.
