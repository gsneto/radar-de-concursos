# Design — Fase 40: zero publicado, reserva combinada e menção fora de reserva

Data: 2026-10-18. Base: Fase 39 (`7ad7171`), schema v21 (inalterado). 1.748 testes.

## Problema

A Fase 39 fechou a matriz de elegibilidade com 159 cargos, mas dois estados indígenas
misturavam situações que a fonte distingue:

1. **55 cargos** apareciam como `cargo_sem_imediata_com_reserva`. A investigação mostrou que
   **não são lacunas**: os seis concursos Quadrix publicam `-` na coluna de vagas efetivas
   (zero imediato explícito) e um número positivo no cadastro de reserva. O mesmo rótulo,
   porém, também cobria o caso em que a tabela simplesmente não tem coluna de vaga imediata
   indígena — situações diferentes.
2. **89 menções lexicais** a "indígena" viravam `mencao_sem_quantidade`. A maioria não é
   reserva: RANI (Registro Administrativo de Nascimento Indígena), vestuário/adorno,
   conteúdo programático (usucapião indígena, demarcação de terras) e procedimento de
   heteroidentificação. Tratar essas menções como reserva é inventar cota.

Além disso, dois concursos publicam reserva indígena **apenas em coluna combinada** com
outros grupos (SEPLAG-RJ: legenda `N/I = Candidatos negros e indígenas`; MPRJ; IBFC), e a
quantidade indígena não é separável.

## Decisões

### 1. Zero publicado é estado próprio, não lacuna

| Estado | Significado |
|---|---|
| `cargo_zero_imediato_com_reserva` | tabela do cargo publica zero imediato **e** reserva quantificada |
| `cargo_sem_imediata_com_reserva` | reserva publicada, sem coluna de vaga imediata na mesma tabela |
| `cargo_explicito_zero` | zero imediato sem reserva quantificada |
| `cargo_imediata` | vaga imediata indígena publicada para o cargo |

O estado novo só é atribuído quando existe proposta de vaga imediata com valor zero
(`values` presente) **e** proposta de reserva com valor positivo. Zero não é inferido de
ausência.

### 2. Contexto da menção decide se há reserva

`radar/indigenous_scope.py` classifica a vizinhança de cada ocorrência de "indígena"
(±220 caracteres), não o documento inteiro:

| Contexto | Uso |
|---|---|
| `regra_de_reserva` | percentual/vaga ligado a indígenas, sem outro grupo no meio |
| `regra_de_reserva_combinada` | reserva de negros/pretos/quilombolas **e** indígenas na mesma regra |
| `documento_de_identificacao` | RANI, documento civil com pertencimento étnico |
| `vestuario_ou_adorno` | adorno, cocar, vestuário |
| `conteudo_programatico` | direitos territoriais, demarcação, usucapião indígena |
| `procedimento_de_heteroidentificacao` | autodeclaração, comissão, verificação documental |
| `outro` | nenhum marcador reconhecido |

Regras de prioridade:

- reserva exclusiva vence combinada;
- combinada vence os demais contextos;
- reserva mencionada sem percentual continua sendo `regra_de_reserva` (quantidade não
  extraída), desde que não haja marcador de outro contexto;
- **ano entre parênteses não é percentual** (`2010 (Estatuto da Igualdade Racial)` não pode
  virar "10% para indígenas");
- olhar o documento inteiro converteria conteúdo programático em reserva só porque outra
  seção fala de vagas.

### 3. Reserva combinada não vira cota indígena

`reserva_combinada_com_outros_grupos` nomeia o caso em que a única publicação é uma coluna
compartilhada. A elegibilidade permanece `compativel_sem_vaga_indigena`, com motivo
explícito; nenhum número é derivado por rateio.

### 4. Menção fora de reserva não é lacuna nem reserva

`mencao_fora_do_escopo_de_reserva` mantém a evidência (trecho, página, contexto) e não
entra em `mencao_sem_quantidade`. `mencao_sem_quantidade` fica reservado a regra de reserva
cuja quantidade não foi extraída.

### 5. O mesmo classificador serve à carteira

`radar/decisive_fields.py` passa a usar `indigenous_scope.classify`, com os estados
`reserva_combinada_com_outros_grupos` e `mencao_fora_do_escopo_de_reserva`. A carteira
(`radar/portfolio.py`) inclui combinada entre as lacunas e retira a menção fora de reserva;
a próxima ação para combinada é "separar a reserva indígena da coluna combinada no edital".

### 6. Vocabulário versionado

`eligibility_v3`: o significado de `cargo_sem_imediata_com_reserva` mudou e dois estados
novos entraram. Contrato HTTP permanece aditivo (18 campos de `GET /api/concursos` intactos).

## Limites declarados

- Nenhuma quantidade é rateada a partir de coluna combinada, percentual ou total agregado.
- A extração da tabela por cargo do Anexo II da SEDUC-PA (colunas PI/PPIQ/PI-PQ, p. 63–83)
  não foi implementada nesta fase; o estado permanece `mencao_sem_quantidade` no concurso.
- Menção classificada não confirma reserva: exige revisão humana antes de qualquer uso.
