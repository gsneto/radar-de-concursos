# Design — Fase 39: identidade por código, escolaridade mínima e elegibilidade formal

Data: 2026-10-18. Base: Fase 38 (`34bd380`), schema v21 (inalterado). 1.702 testes.

## Problema

A Fase 38 entregou a matriz de elegibilidade, mas deixou três pendências concretas:

1. **84 cargos com identidade pendente** — sem explicar *por que* cada um estava pendente.
2. **Três cargos "compatíveis"** — sem distinguir aceitação por categoria de área correlata.
3. **Escolaridade mínima confundida com formação específica** — um requisito de "ensino médio"
   era lido como ambiguidade (ou, pior, como incompatibilidade), e um requisito de
   licenciatura podia virar "nível mínimo".

O caso piloto é o **Quadrix 3049 (CRECI-ES)**: os códigos 200–206 têm o mesmo título-base em
municípios diferentes; 207 é Assistente Especializado; 208 é Assistente de T.I.; 407 é Analista
de T.I. Cada código é uma **opção de inscrição** — não podem ser fundidos.

## Decisões

### 1. Três níveis de identidade, nunca fundidos

| Nível | Exemplo | Uso |
|---|---|---|
| **Família** | `Assistente Administrativo` | leitura de apoio, nunca transfere dado |
| **Cargo/código** | `200 … (PST)-Assistente Administrativo` | identidade individual |
| **Localidade** | `Cachoeiro de Itapemirim` | opção de inscrição, lotação da vaga |

A família é derivada do rótulo sem o código e **não** herda requisito, vaga ou reserva. O código
vem do próprio rótulo; a localidade vem do quadro de vagas (`vaga_municipio`), com evidência da
linha inteira. Município da vaga **não** é local de prova (campo separado, nunca sobrescrito).

### 2. Junção por código, com guarda de ambiguidade

O extrator pendura a leitura de formação no rótulo só-código (`"200"`), não no rótulo nomeado
(`"200 … Assistente Administrativo"`). A matriz passou a **juntar por código dentro do mesmo
concurso**, e só quando:

- o código é único entre os cargos **nomeados** do concurso (dois nomes com o mesmo código
  tornam a junção insegura);
- o rótulo-código tem leitura de SI (um rótulo só-código sem leitura não atribui nada).

A atribuição fica registrada (`atribuicao: "codigo_do_cargo"`), separada de
`escopo_do_cargo`, `unico_cargo_do_concurso` e `declaracao_do_concurso`.

### 3. Escolaridade mínima é um estado próprio

`edital_requirements` ganhou três funções determinísticas:

- `education_level(text)` → `medio`, `tecnico`, `superior`, `indefinido`;
- `area_clause(text)` → trecho que nomeia a área/curso, ou `None`;
- `names_specific_area(text)` → há área específica?

A classificação passou a distinguir:

| Estado | Significado | Elegibilidade |
|---|---|---|
| `aceito_expressamente` | texto cita "Sistemas de Informação" | compatível |
| `abrangido_por_categoria` | categoria ampla de TI com abertura explícita | compatível |
| `nivel_minimo_sem_area` | só nível (médio/superior), sem curso | **compatível por nível mínimo** |
| `ambiguo` | área de computação sem categoria formal | potencial (interpretar) |
| `incompativel_com_requisito_explicito` | área específica diferente | incompatível |

Regras de precedência:

- **incompatibilidade explícita vence** qualquer leitura concorrente;
- **aceitação explícita vence** ambiguidade concorrente (uma leitura ambígua não apaga o nome
  do curso);
- nível mínimo **refina** a ambiguidade causada pela ausência do nome do curso;
- decisão humana `validado`/`corrigido` **não é sobrescrita** pela releitura.

### 4. O texto é a evidência; o valor armazenado é histórico

A leitura é derivada do **trecho citado** com o classificador atual. O valor gravado na
proposta (do extrator da época) continua visível na ficha (`valor_armazenado`) e serve de
auditoria. Nada é reescrito, nada é apagado.

### 5. Área é lida da cláusula, não do texto inteiro

`area_clause` exige uma palavra de curso/formação seguida de "em …" ("curso … em Direito",
"nas áreas de TI"), e aceita o formato compacto do quadro ("Nível Superior - Direito").
Isso corrigiu dois falsos positivos reais:

- **"exercício do direito de dirigir"** virava exigência de Direito (o token "direito"
  aparecia no texto, não na área);
- **"área de computação"** era tratada como abertura de categoria (`"area de"` saiu dos
  marcadores de abertura).

### 6. Licenciatura é formação específica, não nível mínimo

"Licenciatura Plena com habilitação para o magistério", "habilitação específica para a
disciplina" e "licenciatura … na área de atuação" exigem licença para lecionar — um bacharelado
não satisfaz. O classificador passou a tratar esses qualificadores como formação específica;
"licenciatura em qualquer área" continua nível mínimo.

### 7. Auditoria das pendências com causa real

`eligibility.pending_audit` classifica cada rótulo pendente em uma causa exclusiva:

| Causa | Rótulos |
|---|---|
| `aguarda_decisao_humana` | 89 |
| `duplicata_de_identidade` | 36 |
| `sem_cargo_canonico` | 23 |
| `codigo_sem_nome` | 18 |

Não resolve nada: aponta a causa, a sugestão (quando existe) e a evidência.

### 8. Ficha de revisão de compatibilidade

`eligibility.compatibility_review` monta a ficha de cada cargo com leitura de formação:
estado anterior (valor armazenado), leitura atual do texto, nível educacional, área, localidade,
evidência e atribuição. É o insumo da decisão humana na mesa existente.

### 9. Localidade no quadro da Quadrix

`quadrix_tables` passou a emitir `vaga_municipio` por linha, com evidência que abrange a linha
inteira (código, cargo, valores e município). O recorte é conservador: exige município
iniciado por maiúscula seguido de carga horária (`… 40h`). 55 localidades em 6 concursos.

## Limites declarados

- A matriz continua candidata: nenhuma decisão humana foi criada.
- Família não transfere requisito, vaga ou reserva.
- Localidade da vaga não é local de prova.
- Reserva indígena mantém o escopo das fases anteriores (concurso × cargo).
- A extração nova vale para documentos reprocessados; nada foi reescrito.
- Requisito adicional (registro profissional, CNH, experiência) aparece na evidência, mas a
  fase avalia o requisito **educacional**.
