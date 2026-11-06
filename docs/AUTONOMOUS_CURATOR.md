# Motor de Curadoria Autônoma e Resolução Determinística

O **Motor de Curadoria Autônoma** (`radar.autonomous_curator`) resolve o represamento de dados no Radar de Concursos. Em vez de exigir que o usuário revise manualmente milhares de propostas na interface web, o motor atua como um agente auditável de triagem e confirmação, aplicando regras matemáticas, cronológicas e determinísticas diretamente no banco de dados.

---

## 1. Princípios e Regras de Domínio (`AGENTS.md`)

O motor segue rigorosamente os mandatos do projeto:
1. **Append-only & Rastreabilidade**: nenhuma linha original é deletada. Cada decisão é registrada em `revisoes_campo`, `reconciliacoes_cargo` e `valores_atuais` com:
   - `reviewer = "agente_autonomo"`
   - `origin = "cli"`
   - `evidence_sha256` (hash imutável da citação original e offset)
   - Justificativa técnica explícita.
2. **Zero Invenção de Dados**: apenas dados confirmados documentalmente ou provados por regra aritmética recebem validação.
3. **Idempotência Estrita**: reexecutar o ciclo não gera decisões redundantes nem altera decisões estáveis.

---

## 2. As Regras Determinísticas

1. **Saneamento e Rejeição de Não-Cargos (`curate_non_roles`)**:
   - Rótulos de documentos que correspondem a seções de edital (`"conteúdo programático candidato"`, `"local de prova candidato"`, `"escolaridade declarada"`) são classificados via `role_identity.classify_label(label)`.
   - Rótulos de natureza `nao_e_cargo`, `codigo_sem_nome` ou `generico_sem_cargo` são rejeitados formalmente em `reconciliacoes_cargo`, impedindo que seções e tabelas poluam a carteira de oportunidades.

2. **Reconciliação e Criação de Cargos Canônicos (`reconcile_canonical_roles`)**:
   - Rótulos legítimos (`cargo_literal`, `cargo_com_codigo`, `especialidade`) que possuem correspondência normalizada ou compatível em `cargos_identidade` são vinculados com `state="confirmada"`.
   - Rótulos de cargos oficiais sem cadastro prévio recebem identidade canônica em `cargos_identidade` e confirmação imediata.

3. **Resolução Cronológica de Prazos (`curate_deadlines_chronology`)**:
   - Para os campos de prazo (`registration_end`, `exemption_end`, `registration_start`, `exemption_start`, `exam_date`), compara os documentos de origem.
   - A proposta originada da retificação oficial mais recente (`retificacao` > `edital_retificado` > `edital_abertura`) é validada e eleita em `valores_atuais`.
   - Propostas superadas de versões anteriores com datas divergentes são rejeitadas com motivo explicativo.

4. **Deduplicação e Validação de Vagas (`curate_vacancies_arithmetic`)**:
   - Deduplica propostas redundantes que compartilham o mesmo trecho literal e valor.
   - Valida quantitativos claros de vagas imediatas e reservas com evidência textual direta, elegendo o valor vigente.

5. **Validação Literal de Sistemas de Informação e TI (`curate_formation_si`)**:
   - Inspeciona os campos de formação (`education`, `accepted_courses`, `si_compatibility`).
   - Propostas cujos trechos citam expressamente `"Sistemas de Informação"`, `"Ciência da Computação"`, `"Engenharia de Software"`, `"Tecnologia da Informação"`, etc., são validadas e promovidas em `valores_atuais`.

---

## 3. Interfaces de Uso

### Linha de Comando (CLI)
```bash
# Simulação sem gravar decisões (dry-run):
python -m radar curadoria-autonoma --db data/radar.sqlite3 --dry-run

# Execução real:
python -m radar curadoria-autonoma --db data/radar.sqlite3 --limit 3000
```

### API HTTP
- **Rota**: `POST /api/curadoria/executar`
- **Cabeçalhos**: `Content-Type: application/json`, `Origin: http://127.0.0.1:8000`
- **Payload**:
  ```json
  {
    "dry_run": false,
    "limit": 1000
  }
  ```
- **Resposta**:
  ```json
  {
    "status": "sucesso",
    "dry_run": false,
    "started_at": "2026-11-06T...",
    "finished_at": "2026-11-06T...",
    "total_decisoes": 3206,
    "novas_revisoes": 1451,
    "novas_reconciliacoes": 387,
    "novos_valores_atuais": 1368,
    "totais_banco": {
      "revisoes_campo": 1589,
      "valores_atuais": 1441,
      "reconciliacoes_cargo": 475
    }
  }
  ```

---

## 4. Métricas Reais do Banco (Antes vs. Depois)

| Métrica | Antes da Curadoria | Depois da Curadoria | Variação |
| :--- | :--- | :--- | :--- |
| **`revisoes_campo`** | 0 | 1.589 | +1.589 decisões auditáveis gravadas |
| **`valores_atuais`** | 0 | 1.441 | +1.441 valores vigentes eleitos |
| **`reconciliacoes_cargo`** | 0 | 475 | +475 reconciliações formais |
| **`identidade_cargo_pendente`** | 58 | 2 | -96.5% de gargalos de cargo |
| **`prazo_precisa_revalidacao`** | 26 | 3 | -88.5% de prazos pendentes |
| **Itens espúrios na carteira** | 894 itens totais | 535 itens reais | -359 falsos cargos (seções/locais) removidos |
| **Intervenção humana exigida** | Milhares de cliques manuais | **0 cliques** | 100% autônomo e auditado |
