# Design — Fase 37: auditoria de prazos, contagens por dimensão e ficha de decisão

Data: 2026-10-18. Base: Fase 36 (`9252d94`), schema v21 (inalterado). 1.637 testes.

## Problema

A Fase 36 entregou carteira e calendário, mas a investigação de um conflito ainda exigia
abrir documento por documento. Três problemas concretos motivaram esta fase:

1. **O conflito `4f495c42`** apresentava início em 19/10/2026 e 18/04/2027, e fim em
   21/10/2026, 26/11/2026 e 18/04/2027 — sem explicação de causa. Um prazo iminente (19/10)
   não podia ficar sem diagnóstico.
2. **As contagens do relatório não fechavam**: 10 revalidados + 6 em conflito + 71 passados
   + 14 sem data = 101, não 110. A soma das categorias do código fechava; o relatório misturou
   um recorte (16 futuros) com o universo (110).
3. **`estado_operacional` misturava dimensões independentes** (tempo, revalidação, conflito,
   revisão humana), o que tornava impossível somar sem ambiguidade.

## Decisões

### 1. Auditoria explica a causa, não escolhe valor

`radar/deadline_audit.py` classifica **cada candidato** em duas dimensões:

**Evento do trecho** (marcador mais próximo): `inscricao`, `isencao`, `prova`, `recurso`,
`outro`.

**Reprodutibilidade pelo extrator atual**: `reproduzido` (mesmo offset),
`reproduzido_em_outro_offset` (valor válido, localizador desatualizado),
`nao_reproduzido`, `sem_extrator` (campo sem extrator dedicado).

A causa do conflito é derivada dos candidatos, com precedência:

| Causa | Critério |
|---|---|
| `evento_diferente` | ao menos um candidato fala de isenção/prova/recurso, não do prazo |
| `divergencia_real` | dois ou mais valores com evento correto |
| `extracao_obsoleta` | candidato do evento correto que o extrator atual não reproduz |
| `evidencia_deslocada` | valor reproduzido, offset da evidência mudou |
| `coerente` | candidatos concordam (usado na ficha de qualquer prazo) |
| `indeterminado` | sem evidência suficiente |

**Nada é resolvido.** A ficha inclui `proposta_correcao` com a lista de propostas a rejeitar e
a ação recomendada, sempre com `requer_decisao_humana: true` e `nao_executado: true`.

### 2. O contexto é a oração, não a página

O extrator usava uma janela fixa de 240 caracteres antes do trecho para exigir "inscrição".
Isso atravessava frases: numa página que menciona "inscrição" e depois lista datas de prova,
a data de prova virava prazo de inscrição.

A classificação passou a usar **duas camadas**:

1. **Janela curta (160 caracteres)**: o sujeito que rege o período está imediatamente antes
   da primeira data ("A isenção … poderá ser solicitada no período das 16h do dia …").
2. **Frase (sem teto artificial, após a última fronteira)**: cobre frases longas
   ("inscrições … de 27 de fevereiro … até 10 de abril") sem alcançar a frase vizinha.

Se a oração imediatamente antes da data mistura dois eventos ("a isenção e as inscrições …
no período"), o **extrator** não atribui (`strict=True`); a **auditoria** usa o marcador mais
próximo e sinaliza `event_ambiguous`, porque diagnosticar não é decidir.

A citação também é consultada: se ela nomeia um único evento ("Inscrições até …",
"… prova discursiva"), esse evento prevalece. "Inscrição" só conta como evento quando não é
qualificador de outro ato ("taxa de inscrição", "valor da inscrição", "inscritos"): nesses
casos o evento é a isenção ou o pagamento.

### 3. Contagens por dimensão, com denominador explícito

`deadline_calendar.calendar` passa a devolver quatro dimensões **independentes**, cada uma
somando o total:

| Dimensão | Valores |
|---|---|
| `por_temporal` | futuro, hoje, expirado, data_invalida, sem_data |
| `por_revalidacao` | fonte_inalterada, fonte_alterada, fonte_indisponivel, sem_permissao, erro, sem_verificacao |
| `por_conflito` | conflito, sem_conflito |
| `por_revisao` | decisão humana vigente ou sem_decisao |

`por_situacao` continua existindo como **estado derivado** para orientar a ação
(`revalidado_na_fonte`, `conflito_documental`, …), e `por_estado` fica como alias compatível.
O bloco `denominador` declara unidade, universo, filtros, referência e o tratamento de
propostas rejeitadas.

Consequência: `fonte_inalterada` **não** substitui `futuro`/`expirado` — são dimensões
diferentes. Um prazo pode ser futuro **e** revalidado **e** em conflito ao mesmo tempo.

### 4. Verificação de uma versão específica

A revalidação normal só olha prazos futuros sem conflito. Para o caso auditado era preciso
verificar o documento de um prazo **em conflito**:
`deadline_revalidation.verify_version(version_id, ...)` compara o sha256 servido hoje com o
armazenado, respeita a política da fonte, recusa redirecionamento para outro host/HTTP e grava
apenas metadados. `dry_run` não consulta a rede (mesmo contrato de `execute`).

### 5. Superfície

- `GET /api/prazos/auditoria`, `GET /api/prazos/caso`, `POST /api/prazos/verificar-documento`.
- CLI `prazos-auditoria`, `prazos-caso`, `prazos-verificar-documento`.
- UI: contagens por dimensão no cabeçalho dos prazos; botão **Ficha** em cada prazo com
  comparação de trechos, evento, reprodutibilidade, sha256, URL e proposta de correção.

## Limites declarados

- A auditoria não altera propostas, não cria decisões e não revalida em massa.
- `sem_extrator` não confirma nem refuta o valor: sinaliza conferência manual.
- Fonte inalterada continua não confirmando prazo.
- Nenhum valor é escolhido por recência, frequência ou proximidade.
- A extração corrigida vale para documentos futuros; os já extraídos permanecem como estão
  até decisão humana (rejeitar) ou reprocessamento.
