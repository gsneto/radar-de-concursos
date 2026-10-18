# Design — Fase 38: matriz de elegibilidade por cargo e escopo da reserva indígena

Data: 2026-10-18. Base: Fase 37 (`36db3fd`), schema v21 (inalterado). 1.668 testes.

## Problema

A Fase 36 montou a carteira e a Fase 37 auditou prazos. Faltava a pergunta central do
produto: **este cargo aceita o Bacharelado em Sistemas de Informação, e existe vaga
indígena para este cargo?**

O relatório anterior mostrava 12 destaques, mas três deles entravam apenas por "prazo futuro +
menção a indígena", sem qualquer requisito de formação sustentado — e um deles era um cargo
cuja exigência era bacharelado em Direito. A reserva indígena estava sendo lida como sinal de
elegibilidade, o que a fase precisava impedir.

## Decisões

### 1. Elegibilidade é do cargo, com precedência explícita

`radar/eligibility.py` classifica cada oportunidade em um estado exclusivo:

| Estado | Critério |
|---|---|
| `incompativel_por_requisito` | requisito extraído aponta formação diferente do perfil |
| `compativel_com_vaga_indigena_cargo` | requisito sustenta + vaga indígena imediata **do cargo** |
| `compativel_sem_vaga_indigena` | requisito sustenta (expresso ou categoria) |
| `compativel_por_interpretacao` | requisito cita área de computação/TI sem abertura explícita |
| `identidade_pendente` | sem leitura de SI e rótulo não reconciliado |
| `informacao_insuficiente` | sem leitura de SI em cargo reconciliado |

**Incompatibilidade vem primeiro.** Um cargo com reserva indígena e requisito de Direito
continua `incompativel_por_requisito` — a reserva nunca promove o cargo.

### 2. "Ambíguo" só é potencial quando o texto é de formação na área

Duas guardas novas, derivadas do próprio trecho:

- **Marcador de requisito**: o texto citado precisa falar de curso/graduação/bacharelado/
  licenciatura/diploma/certificado/técnico/ensino médio/nível superior. Um trecho de
  currículo ou ata não sustenta nem "potencial".
- **Marcador de computação/TI**: "ambíguo" só vira `compativel_por_interpretacao` se o trecho
  cita computação, informática, TI, sistemas de informação, análise de sistemas etc.
  "Conhecimentos básicos em informática" é habilidade, não formação — não conta.

Sem as guardas, 26 cargos apareciam como "potencial"; com elas, apenas os que realmente citam
a área.

### 3. Reserva indígena tem escopo declarado

Estados por cargo:

| Estado | Significado |
|---|---|
| `cargo_imediata` | tabela publica vaga indígena imediata **para o cargo** |
| `cargo_sem_imediata_com_reserva` | zero imediato + reserva indígena publicada para o cargo |
| `cargo_explicito_zero` | zero publicado para o cargo, sem reserva |
| `concurso_imediata_sem_distribuicao` | quantidade existe só no âmbito do concurso |
| `distribuido_por_cargo` | linha do concurso: informação está por cargo, não se distribui |
| `reserva_sem_quantidade` | reserva mencionada sem quantidade |
| `mencao_sem_quantidade` | menção textual a indígenas sem quantidade |
| `ausente_no_documento` | documento examinado sem a modalidade |
| `nao_localizado` | sem documento analisado |

Regras: "CR" não vira zero nem vaga imediata; "-" na tabela é ausência declarada, não
quantidade inventada; total agregado nunca vira vaga indígena; a linha do concurso **não**
distribui a quantidade entre cargos.

### 4. Quadro de vagas em texto de PDF

O edital do TJSC publica o quadro como texto corrido:

```
Cargo | Ampla Concorrência | Pessoa com Deficiência | Negros | Indígenas | Quilombolas | Total
Juiz Substituto 9 1 4 1 CR 15+ CR
```

`document_fields._inline_vacancy_proposals` reconhece o cabeçalho pelas modalidades (exige
âncora "quadro de vagas"/"cargo" colada, cabeçalho compacto, AMPLA + INDÍGENA + TOTAL) e lê
uma célula por coluna. Guardas:

- número de células tem de bater com o número de colunas (célula extra = não mapear);
- "N + CR" é uma célula só (15 imediatas + cadastro de reserva);
- "CR" puro não gera quantidade;
- linhas seguintes continuam sendo lidas (quadro multi-cargo);
- prosa, numeração de tópicos e currículo não passam no cabeçalho.

Efeito na base: 3 documentos passaram a ter quadro de vagas (TJSC 15/1, TRF5 11/0,
ddb0dac5 1/0 e 5/0), +8 propostas candidatas, nenhuma decisão.

### 5. Rótulos: escopo canônico sem fundir cargos

O mesmo cargo aparece com grafias diferentes (caixa, acento) entre documentos. A matriz
normaliza o **rótulo** (`normalize_role`) para casar tabela e requisito do mesmo cargo, e
mantém a lista de rótulos originais visível (`rotulos`). Código sem nome (`"400"`) e rótulo
de outro campo não viram linha de elegibilidade.

### 6. Atribuição de requisito declarado sem cargo (edital de cargo único)

Quando o documento declara a formação sem rótulo de cargo ("escolaridade declarada (Nível
Superior - Direito)"), a matriz só atribui ao cargo quando há **um único cargo no quadro de
vagas** e **uma única leitura**. A atribuição fica registrada
(`atribuicao: "unico_cargo_do_concurso"`) e é revisável. Sem essa condição, o cargo fica
`identidade_pendente` — nunca recebe o requisito de outro cargo.

### 7. Destaques por elegibilidade

`eligibility.highlights` inclui apenas `compativel_com_vaga_indigena_cargo`,
`compativel_sem_vaga_indigena` e `compativel_por_interpretacao`, no máximo dois cargos por
concurso, com motivo legível. Cargo incompatível por requisito expresso fica fora **mesmo com
vaga indígena imediata**. A linha do concurso não entra (não é cargo).

### 8. Perfil configurável

`PROFILES` define o perfil pretendido (padrão `si_bacharelado`). O perfil não está codificado
nos extratores: a classificação de requisitos continua em `edital_requirements` e a leitura do
perfil é só a camada de elegibilidade.

## Limites declarados

- Elegibilidade é candidata, não confirmação; nenhuma decisão humana é criada.
- Requisito ausente não é incompatibilidade.
- Reserva do concurso não é vaga do cargo.
- A matriz não substitui a mesa de revisão; aponta onde ir.
- A extração corrigida vale para documentos novos ou reprocessados; nada é reescrito.
