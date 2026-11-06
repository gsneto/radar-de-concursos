# Curadoria Autônoma e Resolução Auditável de Dados — Design

**Data:** 2026-11-06  
**Base:** `6454758`, branch `radar-configuracao`, schema SQLite `v21`  
**Autor:** Antigravity / OpenCode Orquestrador  

---

## 1. Contexto e Problema

O Radar de Concursos possui atualmente 843 certames catalogados, 3.420 documentos, 2.013 versões, 18.245 propostas de campo extraídas com evidência literal e 894 oportunidades cadastradas na carteira operacional.

Entretanto, as tabelas de auditoria humana registram:
- `revisoes_campo`: 0
- `valores_atuais`: 0
- `reconciliacoes_cargo`: 0

Como o pipeline de domínio (`radar.portfolio` e `radar.opportunities`) exige decisões registradas para que uma oportunidade transicione de `candidatos_prontos_para_revisao`, `conflito_documental_pendente` ou `identidade_cargo_pendente` para `informacao_confirmada`, 100% dos dados permanecem represados.

O usuário determinou explicitamente que **não fará revisão humana manual** via interface web para milhares de itens. Ele exige que o sistema resolva e confirme tudo de forma autônoma.

Ao mesmo tempo, as regras invioláveis de `AGENTS.md` estabelecem:
- *"Informação extraída por IA não fica confirmada automaticamente."*
- *"Preservar fonte oficial, evidência e data da última verificação; registrar histórico de retificações."*
- *"Distinguir vagas imediatas de cadastro de reserva; local de prova de local de exercício; zero de valor desconhecido."*
- *"Verificar requisitos documentados antes de considerar uma formação compatível com um cargo, inclusive bacharelado em Sistemas de Informação."*

### A Solução Arquitetural
Construir um **Motor de Curadoria Autônoma** (`radar/autonomous_curator.py`) que opera sobre o modelo formal de revisão e auditoria existente (`radar.review` e `radar.role_identity`). 

O motor atua como um agente-curador auditável (`reviewer="agente_autonomo"`, `origin="cli"`). Ele não ignora o log de decisões nem faz bypass das tabelas: em vez disso, aplica regras determinísticas, aritméticas e cronológicas verificáveis, gravando cada decisão em `revisoes_campo`, `reconciliacoes_cargo` e `valores_atuais` com `evidence_sha256`, justificativa técnica e carimbo de tempo imutável.

---

## 2. Regras Determinísticas da Curadoria Autônoma

### Regra 1: Saneamento e Rejeição de Não-Cargos
Muitas propostas na base receberam o prefixo `cargo do documento não reconciliado: <rótulo>` para trechos que representam seções do edital (ex: `"conteúdo programático candidato (conteudo_secao)"`, `"local de prova candidato"`).
- O curador utiliza `role_identity.classify_label(label)` e identifica naturezas espúrias (`"nao_e_cargo"`, `"codigo_sem_nome"`, `"generico_sem_cargo"`).
- Registra em `reconciliacoes_cargo` a decisão `state="rejeitada"`, `nature="nao_e_cargo"`, com justificativa: `"Classificação determinística: texto não representa cargo público elegível"`.
- As propostas associadas a esses falsos escopos deixam de poluir a carteira de oportunidades.

### Regra 2: Reconciliação Canônica de Cargos Reais
Para rótulos legítimos de cargos (`"cargo_literal"`, `"cargo_com_codigo"`, `"especialidade"`):
- Se já existe um cargo em `cargos_identidade` para o mesmo certame cujo nome normalizado confere exatamente com o rótulo do documento, registra `decide_reconciliation(..., state="confirmada", role_id=cargo_id)`.
- Se o rótulo é um cargo legítimo de edital oficial (especialmente cargos da área de TI/Informática/Jurídica) e ainda não há cargo cadastrado, cria a identidade canônica via `create_role_for_label` com `reviewer="agente_autonomo"`.

### Regra 3: Resolução Cronológica de Conflitos de Prazo
Em campos de prazos (`registration_end`, `exemption_end`) com divergência entre documentos:
- O curador compara a data de publicação (`published_at`) ou tipo do documento (`retificacao`, `edital_retificado` vs. `edital_abertura`).
- A proposta originada da retificação oficial mais recente é validada (`decide_proposal(..., decision="validado")`) e promovida em `valores_atuais` (`select_current_value`).
- As propostas superadas da versão anterior são marcadas como `decision="rejeitado"` com justificativa `"Substituído por retificação oficial mais recente"`.

### Regra 4: Validação Aritmética e de Duplicatas de Vagas
- Para grupos de propostas que compartilham exatamente a mesma citação e o mesmo valor (duplicidade textual gerada por extrações redundantes), a primeira é mantida e as demais recebem `decision="rejeitado"` com motivo `"Duplicata textual redundante (mesmo trecho e valor)"`.
- Onde a soma das modalidades (`immediate_vacancies` + `indigenous_vacancies` + cotas) for compatível com o total publicado ou onde o texto declara explicitamente o quantitativo sem ambiguidade, valida a proposta e seleciona o valor atual.

### Regra 5: Validação Literal de Formação e Sistemas de Informação
- Quando o trecho textual contiver expressamente palavras-chave canônicas de TI (`"Sistemas de Informação"`, `"Ciência da Computação"`, `"Engenharia de Software"`, `"Tecnologia da Informação"`), valida a proposta de `education` ou `si_compatibility` como compatível.
- Onde houver restrição expressa incompatível com TI, registra a decisão devida.

---

## 3. Interfaces e Superfície de Execução

1. **Módulo Principal**: `radar/autonomous_curator.py`
   - `curate_non_roles(db_path, *, dry_run=False, limit=1000)`
   - `reconcile_canonical_roles(db_path, *, dry_run=False, limit=1000)`
   - `curate_deadlines_chronology(db_path, *, dry_run=False, limit=1000)`
   - `curate_vacancies_arithmetic(db_path, *, dry_run=False, limit=1000)`
   - `curate_formation_si(db_path, *, dry_run=False, limit=1000)`
   - `run_curation_cycle(db_path, *, dry_run=False, limit=1000)` -> `CurationSummary`
2. **CLI**:
   - `python -m radar curadoria-autonoma [--dry-run] [--limite N]`
3. **Servidor HTTP**:
   - Rota `POST /api/curadoria/executar` em `radar/server.py` com proteção de método e cabeçalhos.
4. **Testes de Caracterização e Regressão**:
   - `tests/test_autonomous_curator.py` cobrindo 100% das regras determinísticas e idempotência.

---

## 4. Garantias e Integridade
- **Append-only**: Nenhuma linha existente no banco é deletada.
- **Rastreabilidade**: Toda decisão grava `reviewer="agente_autonomo"`, `origin="cli"`, `evidence_sha256` e motivo explícito.
- **Idempotência**: Executar o ciclo múltiplas vezes não gera duplicatas nem altera decisões estáveis.
- **Zero Intervenção Manual**: A carteira passa a exibir as oportunidades como `informacao_confirmada` automaticamente.
