# Pesquisa — Fase 40: por que 55 cargos não são lacunas e 89 menções não são reserva

Data: 2026-10-18. Base de produção: 1.232 documentos, 1.055 versões, 7.648 propostas,
schema v21, `integrity_check ok`, chaves estrangeiras vazias.

## Método

1. Consultar a matriz (`radar.eligibility.matrix`) e contar estados por cargo e por concurso.
2. Para cada concurso com estado suspeito, ler os blocos do edital já armazenado
   (`blocos_documento`) em volta de cada ocorrência de "indígena" e da tabela de vagas.
3. Comparar com as propostas extraídas (`propostas_campo`) para separar **ausência de dado**
   de **dado publicado que o extrator não converteu**.

## Achado 1 — os 55 casos são zero explícito com reserva publicada

Os 55 cargos pertencem a seis concursos Quadrix: `4bcc186d` (3049), `c268e937` (3053),
`e4271152` (3052), `d494705a` (3072), `6ae3cd17` (3070), `e3c874e0` (3071).

Cada um tem propostas de `indigenous_vacancies` (valor 0) e
`indigenous_reserve_vacancies` (valor 1 ou 2). A linha de evidência mostra a tabela inteira,
por exemplo:

```
207 … 1 - - - - 25 2 10 1 1 40
```

O `-` é a coluna de vagas efetivas indígenas; o número em "cadastro de reserva" é a reserva.
Portanto: **zero imediato publicado, reserva quantificada** — não é lacuna, e o total do
concurso nunca foi rateado entre cargos.

## Achado 2 — as 89 menções são majoritariamente outro contexto

Triagem por documento (trecho em volta da ocorrência):

| Contexto | Exemplos |
|---|---|
| RANI / identificação | `quadrix-3056`, `quadrix-3057`, `quadrix-3069`, `quadrix-3073` |
| Vestuário/adorno | `ibfc-490` |
| Conteúdo programático | `prefsjceducacao25`, `4a184dc2`, `76128bdf`, `784d730a`, `b42f21a1`, `c197838a` |
| Heteroidentificação | `mprjpromotor2026`, Receita Federal |

Nenhum desses trechos publica percentual ou vaga. Tratá-los como reserva produziria cota
inexistente.

## Achado 3 — cinco concursos têm regra de reserva real, com formatos diferentes

| Concurso | Texto | Situação |
|---|---|---|
| `2a04e7e4` SEPLAG-RJ | `20% … reservadas aos candidatos negros (pretos e pardos) ou indígenas`; legenda `N/I = Candidatos negros e indígenas`; tabela por cargo com coluna N/I (2, 2, 5, 1) | **combinada**: quantidade indígena não separável |
| `14c68b75` MPRJ | reserva combinada de negros e indígenas | **combinada** |
| `4b5579c4` TJAP | quadro `10+CR 1+CR 4+CR CR* CR* 15+CR` | indígenas = `CR*`: reserva sem quantidade |
| `7c54d7df` TJRS | `3% … aos indígenas … 1 (uma) vaga para indígenas` | regra explícita; quantidade não extraída |
| `8e229b08` IBFC | `Serão reservadas às pessoas negras e às pessoas indígenas … 20% das vagas` | **combinada** |
| `f4235e23` SEDUC-PA | `30% … pretas e pardas, indígenas e quilombolas` + Anexo II com colunas `PI`, `PPIQ`, `PI/PQ` por cargo e DRE (p. 63–83) | regra explícita; tabela por cargo **não extraída** |

O Anexo II da SEDUC-PA é a maior oportunidade identificada: cada linha traz
`AC PcD PP PI PQ PPIQ PI/PQ Total`, e a soma das sete primeiras colunas fecha o total
(por exemplo `8 1 3 1 1 0 0 14`). A coluna `PI` é indígena exclusiva; `PPIQ` e `PI/PQ` são
buckets unificados e não podem ser somados a `PI`.

## Achado 4 — dois caminhos do produto repetiam o falso positivo

- `radar/eligibility.py` classificava qualquer menção como `mencao_sem_quantidade`.
- `radar/decisive_fields.py` fazia o mesmo para a carteira, com um regex de cabeçalho
  (`\bPI\b|indígena`) que também casava conteúdo programático.

Os dois passaram a compartilhar `radar/indigenous_scope.py`.

## Resultado na base real

Matriz (159 cargos):

| Estado indígena | Cargos |
|---|---|
| `mencao_fora_do_escopo_de_reserva` | 83 |
| `cargo_zero_imediato_com_reserva` | 55 |
| `distribuido_por_cargo` | 9 |
| `mencao_sem_quantidade` | 3 |
| `cargo_explicito_zero` | 3 |
| `ausente_no_documento` | 2 |
| `reserva_combinada_com_outros_grupos` | 3 |
| `cargo_imediata` | 1 |

Carteira (634 concursos): 12 `mencao_fora_do_escopo_de_reserva`, 3 `mencao_sem_quantidade`,
3 `reserva_combinada_com_outros_grupos`, 6 `apenas_reserva`, 2
`explicito_sem_vaga_imediata`, 1 `explicito_imediato`, 3 `nao_mencionado`, 604
`nao_pesquisado`.

## O que não foi feito

- Extração do Anexo II da SEDUC-PA (parser por linha com validação aritmética).
- Extração de `CR*` (TJAP) e de "1 vaga para indígenas" (TJRS) como propostas.
- Qualquer rateio de coluna combinada.
