# Design — Fase 41: quadro de vagas por colunas, reserva unificada e cadastro de reserva

Data: 2026-10-18. Base: Fase 40 (`78b4a36`), schema v21 (inalterado). 1.775 testes.

## Problema

Três concursos publicam vagas indígenas de formas que o extrator de texto achatado não
representa:

1. **SEDUC-PA** — Anexo II (páginas impressas 63–83) com oito colunas de modalidade
   (`AC PcD PP PI PQ PPIQ PI/PQ Total`), células multilinha, cabeçalho repetido a cada
   página e totalização por regional.
2. **TJAP** — quadro de uma linha com notação `10+CR`, `1+CR`, `4+CR`, `CR*`, `CR*` e total
   `15 + CR`. O asterisco não tem nota localizável no edital.
3. **TJRS** — distribuição publicada em texto corrido ("1 (uma) vaga para indígenas"),
   fora de qualquer tabela.

Antes da fase, os três concursos tinham **zero** propostas de vagas: a leitura era apenas
textual, e a matriz tratava tudo como "menção".

## Decisões

### 1. A semântica das siglas vem do documento, não de uma taxonomia global

`radar/modality_legend.py` lê as definições publicadas no próprio edital
(`I – AC: Ampla Concorrência; … VI – PPIQ: vaga unificada …`) e devolve, por sigla:
rótulo, se é **unificada** e quais grupos ela abrange, com o trecho literal. `kind()`
responde `exclusive`, `unified`, `aggregate` ou `unknown`.

Sem definição no documento, a sigla não é interpretada: a linha vira pendência
(`sigla_sem_definicao`) e nenhuma proposta é gerada para ela. A única exceção é a coluna
`Total`, que é publicada pelo próprio nome e continua legível (com a validação aritmética).
A mesma sigla em outro edital não herda significado.

### 2. Leitura posicional do quadro largo (SEDUC-PA)

`radar/vacancy_columns.py` lê as palavras do PDF com caixa delimitadora (PyMuPDF, já
dependência do projeto) e reconstrói a tabela:

- **cabeçalho** = sequência exata das oito siglas na ordem publicada; ele ancora as
  colunas por coordenada horizontal;
- **linhas** = âncoras verticais na primeira coluna numérica;
- **célula multilinha** = bloco de linhas contíguas da mesma coluna, atribuído à linha cujo
  número está no centro do bloco (evita cortar "Assistente de Gestão …");
- **regional** = o nome vem da linha de totalização (`TOTAL – DRE - XINGUARA`), que também
  valida aritmeticamente a soma das linhas daquela regional;
- **total geral** = validado contra a soma das regionais;
- **linha que atravessa página** = o rótulo é completado com as palavras que continuam no
  topo da página seguinte; a evidência permanece na página em que os números foram
  publicados, com nota no motivo.

A evidência é sempre um trecho literal do bloco armazenado, com offsets exatos. O texto do
bloco continua vindo do pypdf (`extract_v2`); o PyMuPDF é usado apenas para as
coordenadas, nunca para reescrever o texto.

### 3. Campos separados por natureza

| Coluna | Campo persistido | Natureza |
|---|---|---|
| `Total` | `immediate_vacancies` | total publicado da linha (imediato) |
| `PI` | `indigenous_vacancies` | vaga **exclusiva** indígena |
| `PPIQ` | `unified_ppiq_vacancies` | vaga **unificada** (PP + PI + PQ) |
| `PI/PQ` | `unified_pi_pq_vacancies` | vaga **unificada** (PI + PQ) |
| `CR*` (TJAP) | `indigenous_reserve_notation` | reserva publicada **sem quantidade** |

`AC`, `PcD`, `PP` e `PQ` não são persistidos: aparecem no relatório da linha e no trecho
literal, e servem à validação aritmética. Nenhuma coluna unificada é somada à exclusiva,
rateada entre grupos ou contada duas vezes.

### 4. Notação de cadastro de reserva

`modality_legend.cr_notation` interpreta `N`, `N+CR`, `CR`, `CR*`, `N + CR` e `-`:

- `CR`/`CR*` **nunca** viram zero nem vaga imediata;
- `CR*` gera proposta de notação (natureza reserva, asterisco presente) e pendência
  `asterisco_sem_nota` quando o edital não publica a explicação do símbolo;
- percentual no corpo do edital não é convertido em quantidade.

### 5. Distribuição em texto corrido (TJRS)

`radar/vacancy_inline.py` exige três amarrações estruturais na mesma passagem:

1. total publicado ("provimento de 30 (trinta) vagas");
2. cargo na mesma frase ("no cargo de JUIZ DE DIREITO SUBSTITUTO");
3. lista de distribuição ("restando a seguinte distribuição: …").

Sem o cargo, nenhuma proposta é gerada — não se associa quantidade por proximidade. A soma
das modalidades é conferida contra o total; divergência é registrada, não corrigida.

### 6. Estado indígena reconhece reserva sem quantidade no cargo

`radar/eligibility.py` passa a tratar reserva de cargo sem número (notação `CR*`) como
`reserva_sem_quantidade`, distinta de `cargo_explicito_zero` e de `mencao_sem_quantidade`.
Os campos unificados entram na matriz em `vacancies.unified`, nunca em
`vacancies.indigenous_reserve`.

### 7. Superfície aditiva

- `GET /api/quadro-vagas?contest_id=&version_id=` (somente leitura);
- `python -m radar quadro-vagas --db … [--contest-id …] [--version-id …]`;
- contrato de `GET /api/concursos` (18 campos) inalterado; schema v21 inalterado.

## Limites declarados

- **Linhas textualmente idênticas em regionais diferentes** (14 no Anexo II): o parser
  reutiliza ocorrências distintas do texto e estende a evidência até o marcador da regional,
  de modo que cada linha mantenha trecho próprio. Quando nem isso é possível, a segunda
  ocorrência fica registrada como `linha_repetida_no_bloco`.
- **Anexo II-A** (matriz de convocação) não é lido como vagas: o intervalo do quadro
  termina no início do Anexo II-A, e o cabeçalho só é aceito quando as siglas estão na
  mesma linha.
- O asterisco do TJAP não tem nota no edital; a limitação fica explícita.
- Nada é confirmado automaticamente: toda proposta é candidata e passa pela revisão humana.
