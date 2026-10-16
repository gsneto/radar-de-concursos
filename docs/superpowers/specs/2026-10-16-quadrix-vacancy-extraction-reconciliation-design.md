# Fase 13 — Extração de vagas da Quadrix e reconciliação multifonte

Data: 2026-10-16. Base: `722a8a3` (Fase 12), 401 testes OK.

## Problema

A Fase 12 recuperou editais da Quadrix, mas eles geraram **0 propostas de vagas**. Além
disso, a reconciliação PCI ↔ fontes oficiais precisava ser medida com dados reais.

## Diagnóstico (causa comprovada)

Os editais da Quadrix são PDF **textual**, extraído pelo `document_extract` como **um
bloco por página, sem separador de célula** (`" | "`). O extrator genérico
(`vacancy_tables`) e o caminho de PDF (`document_fields._pdf_table_proposals`) dependem,
respectivamente, de linhas com separador (HTML) e do layout fixo do DOU (`QUADRO GERAL
DE VAGAS` + 6 colunas). O edital da Quadrix não tem esse marcador → nenhuma tabela
reconhecida.

Estrutura real observada (certames 3049/3052/3072 — modelo codificado):

```
Cod Cargo/Ocupação | Vagas efetivas | Cadastro de reserva | Total de vagas | Local | Carga | Salário
                    AC PCD PN PI PQ   AC PCD PN PI PQ
200 Assistente ... - - - - -        18 2 8 1 1          30  Cidade 40h R$ ...
```

E (certame 3056 — modelo por especialidade, sem código):

```
Especialidade | Vagas imediatas | Cadastro de reserva | Total de vagas
              AC PCD PPP HIPO    AC PCD PPP HIPO
Administração 23 10 9 5         70 28 29 14          188
```

A legenda do próprio edital confirma: **PI = pessoas indígenas**, PCD = deficiência,
PN = pessoas negras, PQ = quilombolas, PPP = pretos e pardos, HIPO = hipossuficientes.

## Frente A — estratégia específica (`radar/quadrix_tables.py`)

Módulo isolado, usado **junto** ao extrator genérico (não é cópia dele). Reconhece:

- Cabeçalho de duas linhas: o grupo "Vagas efetivas/imediatas" e "Cadastro de reserva"
  repetem as mesmas modalidades (`AC PCD …`); a leitura segue o **cabeçalho**, não
  posições fixas.
- Linhas `[código] rótulo <modalidades imediatas> <modalidades de reserva> <total>`.

Regras documentadas:
- `immediate_vacancies` = soma das modalidades do grupo imediato; `reserve_vacancies` =
  soma do grupo de reserva; `indigenous_vacancies` = valor da modalidade indígena
  (`PI`/`IND`) **do grupo imediato**, quando a coluna existir.
- A célula `-` é o marcador explícito de "sem vaga" (zero) da banca; a soma é **conferida
  contra a coluna Total** — linha cuja soma não confere é descartada.
- Sem coluna indígena, **nenhuma** proposta indígena é gerada (não se inventa zero).
- Toda proposta é pendente de revisão (`role_id=None`, motivo = rótulo do cargo, código
  preservado no rótulo quando houver). Nada é validado automaticamente.

Integração: `document_fields.extract_field_proposals` chama a estratégia para blocos de
PDF, sem alterar o comportamento aprovado para HTML/DOU.

## Frente B — reconciliação multifonte e métricas

- `confirmation.metrics` ganhou `by_source`: por origem (PCI/DOU/FGV/Quadrix) conta
  documentos, recuperados, processados e propostas — distinguindo descoberta de
  enriquecimento.
- `confirmation.priority_report` (CLI `confirmacao-prioridades`): itens da fila com os
  **sinais que explicam a prioridade** (TI, menção indígena, inscrições abertas, prazo,
  referência pronta) e evidências documentais já extraídas (propostas imediatas/indígenas).
  Não é pontuação opaca.
- `confirmation.reconcile` (Fase 11) classifica PCI ↔ outras fontes em
  `coincidente`/`novo`/`ambiguo`/`sem_dados`, sem fundir por similaridade simples e
  preservando a proveniência PCI.

## Limitações

- A extração cobre os dois layouts observados; um terceiro formato exigiria nova regra.
  Uma tabela que **atravessa páginas** com o cabeçalho repetido é tratada por página (a
  página de continuação, se trouxer o cabeçalho, é lida; sem cabeçalho, a linha é omitida
  de forma conservadora — nunca se propõe valor incerto).
- Quadrix: a coluna indígena existe em parte dos editais, mas **as vagas indígenas
  imediatas são 0** nos certames amostrados (a reserva indígena aparece no cadastro de
  reserva). O valor 0 é "zero confirmado" (coluna presente), não campo ausente.
- PDF digitalizado (sem texto) permanece não extraível; sem OCR.
